"""Combined detector results versus the Qt model, with independent geometries."""

import base64
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from dioptas.desktop.session import DesktopSession
from dioptas.model.DioptasModel import DioptasModel
from dioptas.model.Configuration import Configuration
from dioptas.model.util.calc import convert_units


def call(session, command, **args):
    result = session.invoke(command, args)
    assert result["ok"], result.get("error")
    return result


def make_project(tmp_path, disjoint=False):
    model = DioptasModel()
    model.attach_configuration(Configuration())
    DesktopSession._disable_automatic_processing(model)
    for i, c in enumerate(model.configurations):
        h, w = [(64, 80), (72, 60)][i]
        yy, xx = np.mgrid[:h, :w]
        pixels = (100 + 0.5 * xx + yy + 20 * np.sin(xx / 6)).astype(np.float32)
        path = tmp_path / f"detector-{i}.tif"
        Image.fromarray(pixels).save(path)
        c.img_model.load(str(path))
        c.calibration_model.set_pyFAI(
            dict(
                dist=[0.12, 0.17][i],
                pixel1=[120e-6, 170e-6][i],
                pixel2=[140e-6, 130e-6][i],
                poni1=h * [120e-6, 170e-6][i] / 2,
                poni2=w * [140e-6, 130e-6][i] / 2,
                rot1=0.20 if i and disjoint else i * 0.012,
                rot2=i * 0.008,
                rot3=i * 0.03,
                wavelength=0.5e-10,
                polarization_factor=0.7,
            )
        )
        c.integration_rad_points = 120
        c.cake_azimuth_points = 36
        c.img_model.factor = [1.25, 0.75][i]
        mask = np.zeros((h, w), dtype=bool)
        mask[10:24, 14:30] = True
        c.mask_model.set_mask_data(mask)
        c.use_mask = True
    model.select_configuration(0)
    project = tmp_path / "detectors.dio"
    model.save(str(project))
    return project


def array(raster):
    return np.frombuffer(base64.b64decode(raster["data"]), dtype="<f4").reshape(
        raster["height"], raster["width"]
    )


@pytest.mark.parametrize("unit", ["2th_deg", "q_A^-1", "d_A"])
@pytest.mark.parametrize("disjoint", [False, True])
def test_combination_matches_qt_and_preserves_individuals(tmp_path, unit, disjoint):
    project = make_project(tmp_path, disjoint)
    session = DesktopSession(engine="pyfai")
    call(session, "open_project", path=str(project))
    individual = call(session, "settings", unit=unit)
    geometries = [
        c.calibration_model.get_pyFAI_config() for c in session._model.configurations
    ]
    masks = [c.mask_model.get_mask().copy() for c in session._model.configurations]
    result = call(session, "combination_settings", patterns=True, cakes=True)
    qt = DioptasModel()
    qt.load(str(project))
    DesktopSession._disable_automatic_processing(qt)
    qt.integration_unit = unit
    qt.combine_patterns = True
    expected = qt.pattern
    np.testing.assert_allclose(result["pattern"]["x"], expected.data[0], rtol=1e-10)
    np.testing.assert_allclose(result["pattern"]["y"], expected.data[1], rtol=1e-10)
    qt.combine_cakes = True
    np.testing.assert_allclose(array(result["cake"]), qt.cake_data, rtol=6e-8)
    np.testing.assert_allclose(
        result["cake"]["radialRange"], [qt.cake_tth[0], qt.cake_tth[-1]]
    )
    assert result["cake"]["unit"] == ("q_A^-1" if unit == "q_A^-1" else "2th_deg")
    assert result["image"]["fullWidth"] == 80
    for c, geometry, mask in zip(session._model.configurations, geometries, masks):
        assert c.calibration_model.get_pyFAI_config() == geometry
        np.testing.assert_array_equal(c.mask_model.get_mask(), mask)
        assert not c.auto_integrate_pattern and not c.auto_integrate_cake
    restored = call(session, "combination_settings", patterns=False, cakes=False)
    np.testing.assert_array_equal(restored["pattern"]["x"], individual["pattern"]["x"])
    np.testing.assert_array_equal(restored["pattern"]["y"], individual["pattern"]["y"])
    np.testing.assert_array_equal(array(restored["cake"]), array(individual["cake"]))


def test_factor_selection_export_and_persistence(tmp_path):
    session = DesktopSession(engine="pyfai")
    project = make_project(tmp_path)
    call(session, "open_project", path=str(project))
    original = call(session, "combination_settings", patterns=True, cakes=True)
    call(session, "configuration_select", index=1)
    scaled = call(session, "combination_settings", factor=2.5)
    assert scaled["state"]["shape"] == [72, 60]
    assert scaled["state"]["combination"]["factor"] == 2.5
    assert session._model.configurations[0].img_model.factor == 1.25
    assert not np.allclose(original["pattern"]["y"], scaled["pattern"]["y"])
    # Saving must write the displayed combined curve, and must not save the
    # selected detector's ordinary pattern by mistake.
    xy = tmp_path / "combined.xy"
    call(session, "save_combined_pattern", path=str(xy))
    data = np.loadtxt(xy)
    np.testing.assert_allclose(data[:, 0], scaled["pattern"]["x"], rtol=1e-5)
    np.testing.assert_allclose(data[:, 1], scaled["pattern"]["y"], rtol=1e-5)
    csv = tmp_path / "combined.csv"
    call(session, "integration_save_image", path=str(csv), source="cake")
    saved_cake = np.loadtxt(csv, delimiter=",")
    np.testing.assert_allclose(saved_cake[1:, 1:], array(scaled["cake"]), atol=0.51)
    out = tmp_path / "saved.dio"
    call(session, "save_project", path=str(out))
    reopened = DesktopSession(engine="pyfai")
    restored = call(reopened, "open_project", path=str(out))
    assert restored["state"]["configurationIndex"] == 1
    assert restored["state"]["combination"]["patterns"]
    assert restored["state"]["combination"]["cakes"]
    np.testing.assert_allclose(restored["pattern"]["y"], scaled["pattern"]["y"])
    qt = DioptasModel()
    qt.load(str(out))
    assert [c.img_model.factor for c in qt.configurations] == [1.25, 2.5]
    before = session.configuration.calibration_model.get_pyFAI_config()
    call(session, "configuration_select", index=0)
    call(session, "configuration_select", index=1)
    assert session.configuration.calibration_model.get_pyFAI_config() == before
    assert not session.invoke("combination_settings", {"factor": float("nan")})["ok"]
    assert session.configuration.img_model.factor == 2.5
    assert not session.invoke("configuration_select", {"index": 10})["ok"]


def test_unready_and_cake_inspection_units(tmp_path):
    session = DesktopSession(engine="pyfai")
    assert not session.invoke("combination_settings", {"patterns": True})["ok"]
    call(session, "open_project", path=str(make_project(tmp_path)))
    call(session, "settings", unit="q_A^-1")
    result = call(session, "combination_settings", cakes=True)
    q = sum(result["cake"]["radialRange"]) / 2
    clicked = call(
        session, "validation_position", source="cake", x=q, unit="q_A^-1", azimuth=20
    )["linked"]
    expected = convert_units(
        q,
        session.configuration.calibration_model.pattern_geometry.wavelength,
        "q_A^-1",
        "2th_deg",
    )
    assert clicked["twoTheta"] == pytest.approx(expected)
    # Per-configuration calibration workflow values follow selection too.
    session._fit_dirty = True
    session._fit_rms = 0.123
    call(session, "configuration_select", index=1)
    assert not session._fit_dirty and session._fit_rms is None
    call(session, "configuration_select", index=0)
    assert session._fit_dirty and session._fit_rms == 0.123


def test_optional_native_combination_capability_fallback(tmp_path, monkeypatch):
    from dioptas.desktop import combination

    session = DesktopSession(engine="pyfai")
    call(session, "open_project", path=str(make_project(tmp_path)))
    expected = call(session, "combination_settings", patterns=True, cakes=True)
    from types import SimpleNamespace

    session._engine = SimpleNamespace(id="dioptrin", label="Dioptrin")
    monkeypatch.setattr(
        combination, "native_unavailable", lambda *args: "2D API not installed"
    )
    actual = call(session, "integrate")
    assert (
        actual["state"]["combination"]["backends"]["cake"]
        == "pyFAI (2D API not installed)"
    )
    np.testing.assert_array_equal(actual["pattern"]["y"], expected["pattern"]["y"])
    np.testing.assert_array_equal(array(actual["cake"]), array(expected["cake"]))


@pytest.mark.parametrize("unit", ["2th_deg", "q_A^-1", "d_A"])
@pytest.mark.parametrize("disjoint", [False, True])
def test_native_shared_grid_matches_qt_combination(tmp_path, unit, disjoint):
    native = pytest.importorskip("dioptrin")
    if not hasattr(native.MultiIntegrator, "integrate2d"):
        pytest.skip("Optional Dioptrin shared-grid 2D API not installed")
    session = DesktopSession(engine="pyfai")
    call(session, "open_project", path=str(make_project(tmp_path, disjoint)))
    call(session, "settings", unit=unit)
    expected = call(session, "combination_settings", patterns=True, cakes=True)
    call(session, "calibration_engine", engine="dioptrin")
    actual = call(session, "integrate")
    assert actual["state"]["combination"]["backends"] == {
        "pattern": "Dioptrin",
        "cake": "Dioptrin",
    }
    np.testing.assert_allclose(
        actual["pattern"]["x"], expected["pattern"]["x"], rtol=2e-6
    )
    np.testing.assert_allclose(
        actual["cake"]["radialRange"], expected["cake"]["radialRange"], rtol=2e-6
    )
    pattern_error = np.linalg.norm(
        np.asarray(actual["pattern"]["y"]) - expected["pattern"]["y"]
    ) / np.linalg.norm(expected["pattern"]["y"])
    assert pattern_error < 0.01, pattern_error
    # Different full-polygon algorithms can populate different edge bins. Check
    # those differences explicitly, rather than excluding them without an audit.
    from scipy.ndimage import binary_dilation

    a, b = array(actual["cake"]), array(expected["cake"])
    native_coverage, qt_coverage = a != 0, b != 0
    common = native_coverage & qt_coverage
    assert np.linalg.norm((a - b)[common]) / np.linalg.norm(b[common]) < 0.01
    assert np.all(~native_coverage | binary_dilation(qt_coverage))
    assert np.all(~qt_coverage | binary_dilation(native_coverage))
    assert np.count_nonzero(native_coverage ^ qt_coverage) / a.size < 0.006
    assert np.linalg.norm(a - b) / np.linalg.norm(b) < 0.08
    # Identical images/factors multiplied by a constant must scale the merged
    # signal exactly without altering bins, geometry, or coverage weighting.
    retained = session._native_combination.copy()
    for c in session._model.configurations:
        c.img_model.factor *= 3
    triple = call(session, "integrate")
    assert all(
        session._native_combination[key] is value for key, value in retained.items()
    )
    np.testing.assert_allclose(
        triple["pattern"]["y"], np.asarray(actual["pattern"]["y"]) * 3, rtol=2e-7
    )
    np.testing.assert_allclose(
        array(triple["cake"]), array(actual["cake"]) * 3, rtol=2e-7
    )
    saved = tmp_path / "native.xy"
    call(session, "save_combined_pattern", path=str(saved))
    np.testing.assert_allclose(
        np.loadtxt(saved)[:, 1], triple["pattern"]["y"], rtol=1e-5
    )
    native_project = tmp_path / "native.dio"
    call(session, "save_project", path=str(native_project))
    reopened = DesktopSession(engine="dioptrin")
    reopened_result = call(reopened, "open_project", path=str(native_project))
    assert reopened_result["state"]["combination"]["backends"]["cake"] == "Dioptrin"
    np.testing.assert_allclose(
        reopened_result["pattern"]["y"], triple["pattern"]["y"], rtol=1e-10
    )
    cake_csv = tmp_path / "native-cake.csv"
    call(session, "integration_save_image", source="cake", path=str(cake_csv))
    np.testing.assert_allclose(
        np.loadtxt(cake_csv, delimiter=",")[1:, 1:],
        session._cake_arrays()[0],
        atol=0.51,
    )
    reopened.close()
    previous = session._native_combination
    mask = session._model.configurations[1].mask_model.get_mask().copy()
    mask[:] = True
    session._model.configurations[1].mask_model.set_mask_data(mask)
    call(session, "integrate")
    assert session._native_combination is not previous
    session.close()
    assert session._native_combination is None


@pytest.mark.parametrize("unit", ["2th_deg", "q_A^-1"])
@pytest.mark.parametrize("disjoint", [False, True])
def test_native_adapter_counting_absolute_scale_and_coverage(tmp_path, unit, disjoint):
    native = pytest.importorskip("dioptrin")
    if not hasattr(native.MultiIntegrator, "integrate2d"):
        pytest.skip("Optional Dioptrin shared-grid 2D API not installed")
    from pyFAI.multi_geometry import MultiGeometry
    from dioptas.desktop.combination_engine import (
        native_combination_key,
        make_native_multi,
    )

    session = DesktopSession(engine="pyfai")
    call(session, "open_project", path=str(make_project(tmp_path, disjoint)))
    configs = session._model.configurations
    key, masks, rr, ar = native_combination_key(configs, unit, 0.7)
    multi = make_native_multi(configs, unit, 0.7, masks, rr, method="counting")
    images = [
        np.ascontiguousarray(c.img_model.img_data, dtype=np.float64) for c in configs
    ]
    actual = multi.integrate2d(
        images, 120, 36, normalization="absolute", azimuthal_range=ar
    )
    qt = MultiGeometry(
        [c.calibration_model.pattern_geometry for c in configs],
        unit=unit,
        radial_range=(rr[0], rr[1] / (1 + np.finfo(np.float32).eps)),
        azimuth_range=np.rad2deg(ar),
        threadpoolsize=0,
    )
    expected = qt.integrate2d(
        images,
        120,
        36,
        correctSolidAngle=True,
        polarization_factor=0.7,
        lst_mask=masks,
        method=("no", "histogram", "cython"),
    )
    a = np.asarray(actual.intensity).reshape(36, 120)
    np.testing.assert_array_equal(a != 0, expected.intensity != 0)
    np.testing.assert_allclose(a, expected.intensity, rtol=2e-6)
    np.testing.assert_allclose(actual.radial, expected.radial, rtol=2e-6)


def test_native_disabled_solid_angle_uses_qt_combination(tmp_path):
    pytest.importorskip("dioptrin")
    project = make_project(tmp_path)
    native = DesktopSession(engine="dioptrin")
    qt = DesktopSession(engine="pyfai")
    results = []
    for session in (native, qt):
        call(session, "open_project", path=str(project))
        call(session, "integration_settings", solid_angle=False)
        results.append(call(session, "combination_settings", patterns=True, cakes=True))
    assert (
        "solid-angle correction is disabled"
        in results[0]["state"]["combination"]["backends"]["cake"]
    )
    np.testing.assert_array_equal(
        results[0]["pattern"]["y"], results[1]["pattern"]["y"]
    )
    np.testing.assert_array_equal(array(results[0]["cake"]), array(results[1]["cake"]))


def test_configuration_custom_calibrants_remain_owned_and_persist(tmp_path):
    session = DesktopSession(engine="pyfai")
    call(session, "open_project", path=str(make_project(tmp_path)))
    for index in (0, 1):
        call(session, "configuration_select", index=index)
        name = f"detector-reference-{index}"
        source = tmp_path / f"{name}.D"
        source.write_text("4.5\n3.2\n2.1\n" if index == 0 else "4.2\n2.5\n1.8\n")
        call(session, "open_calibrant", path=str(source))
        source.unlink()
    output = tmp_path / "custom-references.dio"
    call(session, "save_project", path=str(output))
    reopened = DesktopSession(engine="pyfai")
    call(reopened, "open_project", path=str(output))
    for index, spacings in [
        (0, [4.5, 3.2, 2.1]),
        (1, [4.2, 2.5, 1.8]),
        (0, [4.5, 3.2, 2.1]),
    ]:
        result = call(reopened, "configuration_select", index=index)
        assert (
            result["state"]["calibration"]["calibrant"] == f"detector-reference-{index} (custom)"
        )
        assert reopened.configuration.calibration_model.calibrant.dSpacing == spacings
        assert reopened._calibrant_path().is_file()
