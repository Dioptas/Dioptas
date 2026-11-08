"""React integration boundary against the same scientific models used by Qt."""

import base64
import json
import shutil
from pathlib import Path

import h5py
import numpy as np
import pytest
from PIL import Image
from xypattern import Pattern

from dioptas.desktop.session import DesktopSession
from dioptas.model.DioptasModel import DioptasModel
from dioptas.model.util.calc import convert_units

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "dioptas/tests/data"


def call(session, command, **payload):
    result = session.invoke(command, payload)
    assert result["ok"], result.get("error")
    json.dumps(result, allow_nan=False)
    return result


@pytest.fixture
def loaded():
    session = DesktopSession()
    call(session, "example")
    call(session, "open_calibration", path=str(DATA / "CeO2_Pilatus1M.poni"))
    call(session, "integration_settings", bins=300, cake_bins=40, trim_zeros=False)
    return session


@pytest.mark.parametrize("supersampling", [1, 2])
def test_linked_detector_contour_passes_through_subpixel_click(loaded, supersampling):
    call(loaded, "integration_settings", supersampling=supersampling)
    geometry = loaded.configuration.calibration_model.pattern_geometry
    for x, y in [(637.2, 564.7), (500.5, 400.5), (350.85, 592.15)]:
        linked = call(loaded, "validation_position", source="image", x=x, y=y)["linked"]
        assert linked["imagePoint"] == {"x": x, "y": y}
        expected = np.rad2deg(geometry.tth(
            np.array([y * supersampling - 0.5]),
            np.array([x * supersampling - 0.5]),
        )[0])
        assert linked["twoTheta"] == pytest.approx(expected)
        # Measure distance to line segments, rather than just vertices: the
        # click may lie between contour samples. A half-pixel shift fails this.
        distances = []
        point = np.array([x, y])
        for contour in linked["contours"]:
            vertices = np.array(contour["points"])
            start, end = vertices[:-1], vertices[1:]
            delta = end - start
            length2 = np.sum(delta * delta, axis=1)
            valid = length2 > 0
            start, delta, length2 = start[valid], delta[valid], length2[valid]
            fraction = np.clip(np.sum((point - start) * delta, axis=1) / length2, 0, 1)
            distances.extend(np.linalg.norm(start + fraction[:, None] * delta - point, axis=1))
        assert min(distances) < 0.005
        back = call(
            loaded, "validation_position", source="cake",
            x=linked["twoTheta"], azimuth=linked["azimuth"],
        )["linked"]
        # Reverse-linked crosses use the same path that is drawn on the image.
        cross = [back["imagePoint"]["x"], back["imagePoint"]["y"]]
        assert any(cross in contour["points"] for contour in back["contours"])


@pytest.mark.parametrize("supersampling", [1, 2])
def test_pixel_readout_uses_original_pixel_centres_for_all_radial_units(loaded, supersampling):
    call(loaded, "integration_settings", supersampling=supersampling)
    pixel = call(loaded, "pixel", x=500, y=400)["pixel"]
    c = loaded.configuration.calibration_model
    expected = np.rad2deg(c.pattern_geometry.tth(
        (np.array([400., 400., 401.]) + 0.5) * supersampling - 0.5,
        (np.array([500., 501., 500.]) + 0.5) * supersampling - 0.5,
    ))
    assert pixel["twoTheta"] == pytest.approx(expected[0])
    assert pixel["twoThetaResolution"] == pytest.approx(np.max(np.abs(expected[1:] - expected[0])))
    raw = call(loaded, "pixel", x=500, y=400, raw=True)["pixel"]
    assert raw["twoTheta"] == pixel["twoTheta"]
    assert raw["twoThetaResolution"] == pixel["twoThetaResolution"]


@pytest.mark.parametrize(
    "unit,sector,cake_sector",
    [
        ("2th_deg", None, [-90, 90]),
        ("q_A^-1", [-60, 70], [-90, 90]),
        ("d_A", [150, -150], [-90, 90]),
        ("2th_deg", None, [150, -150]),
    ],
)
def test_numerical_parity_with_configuration(loaded, unit, sector, cake_sector):
    result = call(
        loaded,
        "integration_settings",
        unit=unit,
        bins=275,
        azimuth_range=sector,
        cake_azimuth_range=cake_sector,
        cake_bins=30,
        solid_angle=False,
        poisson_errors=True,
        polarization=0.8,
    )
    qt = DioptasModel().current_configuration
    qt.auto_integrate_pattern = qt.auto_integrate_cake = False
    qt.img_model.autoprocess = False
    qt.img_model.load(str(DATA / "CeO2_Pilatus1M.tif"))
    qt.calibration_model.load(str(DATA / "CeO2_Pilatus1M.poni"))
    qt.integration_unit = unit
    qt.integration_rad_points = 275
    qt.oned_azimuth_range = sector
    qt.cake_azimuth_range = cake_sector
    qt.cake_azimuth_points = 30
    qt.trim_trailing_zeros = False
    qt.correct_solid_angle = False
    qt.calculate_poisson_errors = True
    qt.calibration_model.polarization_factor = 0.8
    if sector is not None and sector[0] > sector[1]:
        # Explicit discontinuity makes the cross-boundary sector continuous
        # in pyFAI; the Qt controller currently leaves this implicit.
        qt.calibration_model.pattern_geometry.setChiDiscAtZero()
    x, y = qt.integrate_image_1d()
    if cake_sector[0] > cake_sector[1]:
        qt.calibration_model.cake_geometry.setChiDiscAtZero()
    qt.integrate_image_2d()
    np.testing.assert_allclose(result["pattern"]["x"], x, rtol=1e-12)
    np.testing.assert_allclose(result["pattern"]["y"], y, rtol=1e-12)
    cake = np.frombuffer(base64.b64decode(result["cake"]["data"]), dtype="<f4").reshape(
        30, 275
    )
    np.testing.assert_allclose(cake, qt.calibration_model.cake_img, rtol=1e-6)
    assert result["cake"]["unit"] == "2th_deg"
    assert loaded.configuration.pattern_model.errors is not None


def test_automatic_binning_supersampling_and_validation(loaded):
    result = call(loaded, "integration_settings", bins=None, supersampling=2)
    assert result["state"]["bins"] is None
    assert result["state"]["integration"]["actualBins"] == len(result["pattern"]["x"])
    for payload in (
        {"bins": 2.5},
        {"cake_bins": 0},
        {"azimuth_range": [4, 4]},
        {"supersampling": 0},
        {"unit": "invented"},
        {"solid_angle": 1},
    ):
        previous = call(loaded, "state")["state"]["integration"]
        assert not loaded.invoke("integration_settings", payload)["ok"]
        assert call(loaded, "state")["state"]["integration"] == previous


def test_backgrounds_and_flat_field_use_real_image_pipeline(loaded, tmp_path):
    shape = loaded.configuration.img_model.raw_img_data.shape
    raw = loaded.configuration.img_model.raw_img_data.copy()
    bkg = tmp_path / "bkg.tif"
    Image.fromarray(np.full(shape, 2, dtype=np.float32)).save(bkg)
    call(loaded, "integration_image_background", path=str(bkg))
    call(loaded, "integration_image_background", scale=3.0, offset=4.0)
    np.testing.assert_allclose(loaded.configuration.img_model.img_data, raw - 10)
    flat = tmp_path / "flat.tif"
    response = np.broadcast_to(np.linspace(1, 2, shape[1]), shape).astype(np.float32)
    Image.fromarray(response).save(flat)
    call(loaded, "integration_flat_field", path=str(flat))
    np.testing.assert_allclose(
        loaded.configuration.img_model.img_data,
        (raw - 10) / (response / response.mean()),
        rtol=1e-6,
    )
    invalid = tmp_path / "wrong.tif"
    Image.fromarray(np.ones((4, 5), dtype=np.float32)).save(invalid)
    previous = loaded.configuration.img_model.img_data.copy()
    assert not loaded.invoke("integration_image_background", {"path": str(invalid)})[
        "ok"
    ]
    assert not loaded.invoke("integration_flat_field", {"path": str(invalid)})["ok"]
    np.testing.assert_array_equal(loaded.configuration.img_model.img_data, previous)
    call(loaded, "integration_flat_field", reset=True)
    call(loaded, "integration_image_background", reset=True)
    np.testing.assert_array_equal(loaded.configuration.img_model.img_data, raw)


@pytest.mark.parametrize("kind", ["cbn", "oiadac"])
def test_absorption_corrections_and_project_roundtrip(loaded, tmp_path, kind):
    raw = loaded.configuration.img_model.img_data.copy()
    result = call(loaded, "integration_correction", kind=kind, enabled=True)
    assert result["state"]["integration"]["corrections"][kind]["enabled"]
    correction = loaded.configuration.img_model.get_img_correction(kind)
    np.testing.assert_allclose(
        loaded.configuration.img_model.img_data, raw / correction.get_data()
    )
    call(loaded, "save_project", path=str(tmp_path / "test.dio"))
    restored = DesktopSession()
    state = call(restored, "open_project", path=str(tmp_path / "test.dio"))
    assert state["state"]["integration"]["corrections"][kind]["enabled"]
    np.testing.assert_allclose(
        restored.configuration.img_model.img_data,
        loaded.configuration.img_model.img_data,
    )
    call(loaded, "integration_correction", kind=kind, enabled=False)
    np.testing.assert_allclose(loaded.configuration.img_model.img_data, raw)


def test_pattern_background_export_and_unit_range_conversion(loaded, tmp_path):
    call(
        loaded,
        "integration_background",
        enabled=True,
        smoothing=0.2,
        iterations=15,
        order=5,
        range=[2, 10],
    )
    x, y = loaded.configuration.pattern_model.pattern.data
    state = call(loaded, "state")
    np.testing.assert_allclose(state["pattern"]["x"], x)
    np.testing.assert_allclose(state["pattern"]["y"], y)
    output = tmp_path / "subtracted.xy"
    call(loaded, "integration_save_pattern", path=str(output), subtract_background=True)
    saved = Pattern.from_file(str(output))
    np.testing.assert_allclose(saved.data[0], x, rtol=1e-5)
    np.testing.assert_allclose(saved.data[1], y, rtol=1e-5, atol=1e-4)
    call(loaded, "integration_save_background", path=str(tmp_path / "background.xy"))
    call(loaded, "integration_settings", unit="q_A^-1")
    expected = convert_units(
        np.array([2, 10]),
        loaded.configuration.calibration_model.wavelength,
        "2th_deg",
        "q_A^-1",
    )
    np.testing.assert_allclose(
        loaded.configuration.pattern_model.params.auto_bkg_roi, expected
    )
    call(loaded, "integration_background", enabled=False)


def test_background_settings_can_be_edited_while_disabled(loaded):
    result = call(
        loaded, "integration_background", enabled=False, smoothing=0.3,
        iterations=12, order=6, range=[2, 10],
    )
    settings = result["state"]["integration"]["patternBackground"]
    assert not settings["enabled"]
    assert settings["smoothing"] == 0.3
    assert settings["iterations"] == 12
    assert settings["order"] == 6
    assert settings["range"] == [2, 10]
    assert result["pattern"]["backgroundCurves"] == []
    assert loaded.configuration.pattern_model.pattern.auto_bkg is None
    unchanged = call(loaded, "integration_background", enabled=False)
    assert unchanged["state"]["integration"]["patternBackground"] == settings
    enabled = call(
        loaded, "integration_background", enabled=True,
        smoothing=settings["smoothing"], iterations=settings["iterations"],
        order=settings["order"], range=settings["range"],
    )
    assert len(enabled["pattern"]["backgroundCurves"]) == 2


@pytest.mark.parametrize("suffix", [".xy", ".xye", ".chi", ".dat", ".fxye"])
def test_standard_pattern_save_formats(loaded, tmp_path, suffix):
    call(loaded, "integration_settings", poisson_errors=True)
    path = tmp_path / ("pattern" + suffix)
    call(loaded, "integration_save_pattern", path=str(path))
    assert path.stat().st_size > 100
    if suffix == ".xye":
        data = np.loadtxt(path)
        np.testing.assert_allclose(
            data[:, 2], loaded.configuration.pattern_model.errors, rtol=1e-5
        )


def test_overlays_phase_conditions_and_project_persistence(loaded, tmp_path):
    result = call(loaded, "integration_overlay", operation="capture")
    assert len(result["pattern"]["curves"]) == 1
    result = call(
        loaded,
        "integration_overlay",
        operation="update",
        index=0,
        scale=2,
        offset=10,
        color="#ff8800",
    )
    original = loaded.configuration.pattern_model.pattern.data[1]
    np.testing.assert_allclose(result["pattern"]["curves"][0]["y"], original * 2 + 10)
    result = call(
        loaded,
        "integration_phase",
        operation="load",
        path=str(DATA / "jcpds/au_version3.jcpds"),
    )
    assert result["pattern"]["phaseLines"]
    initial = np.array([v["x"] for v in result["pattern"]["phaseLines"]])
    result = call(loaded, "integration_phase", operation="update", index=0, pressure=20)
    expected = loaded._model.phase_model.get_phase_line_positions(
        0, "2th_deg", loaded.configuration.calibration_model.wavelength * 1e10
    )
    np.testing.assert_allclose(
        [v["x"] for v in result["pattern"]["phaseLines"]], expected
    )
    assert not np.allclose(initial, expected)
    call(loaded, "save_project", path=str(tmp_path / "overlays.dio"))
    restored = DesktopSession()
    state = call(restored, "open_project", path=str(tmp_path / "overlays.dio"))
    assert len(state["state"]["integration"]["overlays"]) == 1
    assert state["state"]["integration"]["phases"][0]["pressure"] == 20
    call(loaded, "integration_phase", operation="update", index=0, visible=False)
    assert call(loaded, "state")["pattern"]["phaseLines"] == []


def test_autocreate_and_batch_model_file_roundtrip(loaded, tmp_path):
    inputs = tmp_path / "input"
    output = tmp_path / "output"
    inputs.mkdir()
    output.mkdir()
    for i in range(2):
        shutil.copy(DATA / "CeO2_Pilatus1M.tif", inputs / f"image_{i}.tif")
    call(loaded, "integration_output_directory", path=str(output))
    call(loaded, "integration_settings", auto_save=True, formats=[".xy", ".chi"])
    call(loaded, "open_image", path=str(inputs / "image_0.tif"))
    assert (output / "image_0.xy").exists() and (output / "image_0.chi").exists()
    before = loaded.configuration.img_model.filename
    result = call(loaded, "integration_batch", path=str(inputs))
    assert result["state"]["integration"]["batchFrames"] == 2
    assert loaded.configuration.img_model.filename == before
    batch = tmp_path / "batch.h5"
    call(loaded, "integration_save_batch", path=str(batch))
    with h5py.File(batch) as f:
        np.testing.assert_allclose(
            f["processed/result/data"][0], result["pattern"]["y"]
        )
        assert f["processed/result/data"].shape == (2, 300)
    call(loaded, "integration_save_batch", path=str(tmp_path / "batch.csv"))
    # File handling must never enable signal-driven processing or Qt ownership.
    assert loaded.configuration.auto_integrate_pattern is False
    assert loaded.configuration.auto_integrate_cake is False
    assert loaded.configuration.img_model.autoprocess is False


def test_batch_cancel_bypasses_worker_and_preserves_complete_result(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    import time
    from dioptas.desktop.bridge import DesktopBridge

    folder = tmp_path / "images"
    folder.mkdir()
    for i in range(3):
        shutil.copy(DATA / "CeO2_Pilatus1M.tif", folder / f"image_{i}.tif")
    processor = DesktopBridge()
    entered = threading.Event()
    try:
        call(processor, "example")
        call(processor, "open_calibration", path=str(DATA / "CeO2_Pilatus1M.poni"))
        call(processor, "integration_settings", bins=200, cake_bins=20)
        call(processor, "integration_batch", path=str(folder))
        previous = processor._worker.submit(
            lambda: processor._session.configuration.batch_model.data.copy()
        ).result()

        def install_delay():
            configuration = processor._session.configuration
            calibration = configuration.calibration_model
            if calibration.use_dioptrin:
                integrate_batch = calibration.dioptrin_batch1d_iter

                def slow_batch(*args, **kwargs):
                    for result in integrate_batch(*args, **kwargs):
                        entered.set()
                        time.sleep(0.15)
                        yield result

                calibration.dioptrin_batch1d_iter = slow_batch
                return
            integrate = configuration.integrate_image_1d

            def slow_frame(*args, **kwargs):
                entered.set()
                time.sleep(0.15)
                return integrate(*args, **kwargs)

            configuration.integrate_image_1d = slow_frame

        processor._worker.submit(install_delay).result()
        with ThreadPoolExecutor(max_workers=1) as caller:
            work = caller.submit(
                processor.invoke, "integration_batch", {"path": str(folder)}
            )
            assert entered.wait(5)
            assert call(processor, "progress")["progress"]["running"]
            start = time.monotonic()
            call(processor, "cancel_refinement")
            assert time.monotonic() - start < 0.1
            result = work.result(timeout=15)
        assert result["ok"] and result["cancelled"]
        assert not call(processor, "progress")["progress"]["running"]
        actual = processor._worker.submit(
            lambda: processor._session.configuration.batch_model.data.copy()
        ).result()
        np.testing.assert_array_equal(actual, previous)
    finally:
        processor.close()


def test_standalone_pattern_and_autocreate_settings_preserve_display(tmp_path):
    path = tmp_path / "sample_1.xy"
    np.savetxt(path, np.column_stack((np.linspace(2, 10, 50), np.linspace(10, 40, 50))))
    session = DesktopSession()
    result = call(session, "integration_open_pattern", path=str(path))
    before = result["pattern"]
    result = call(session, "integration_settings", auto_save=False, formats=[".xy"])
    assert result["pattern"] == before
    call(session, "integration_save_pattern", path=str(tmp_path / "saved.xy"))
    result = call(session, "integration_settings", unit="q_A^-1")
    assert result["pattern"]["unit"] == "q_A^-1"


def test_batch_rejects_changed_detector_shape_without_losing_mask(loaded, tmp_path):
    call(loaded, "mask_stroke", points=[[100, 100]], radius=12)
    expected = loaded.configuration.mask_model.get_img().copy()
    geometry = loaded.configuration.calibration_model.get_pyFAI_config()
    original = loaded.configuration.img_model.filename
    Image.fromarray(np.ones((20, 30), dtype=np.float32)).save(tmp_path / "wrong.tif")
    result = loaded.invoke("integration_batch", {"path": str(tmp_path)})
    assert not result["ok"] and "detector shape" in result["error"]
    np.testing.assert_array_equal(loaded.configuration.mask_model.get_img(), expected)
    assert loaded.configuration.img_model.filename == original
    assert loaded.configuration.calibration_model.get_pyFAI_config() == geometry


def test_supersampling_keeps_original_pixel_geometry_and_poni(loaded, tmp_path):
    calibration = loaded.configuration.calibration_model
    original = (calibration.orig_pixel1, calibration.orig_pixel2)
    expected_angle = np.rad2deg(calibration.get_pixel_two_theta_array()[400, 500])
    call(loaded, "integration_settings", supersampling=2)
    linked = call(loaded, "validation_position", source="image", x=500.5, y=400.5)
    assert linked["linked"]["twoTheta"] == pytest.approx(expected_angle, abs=1e-10)
    path = tmp_path / "physical-pixels.poni"
    call(loaded, "save_calibration", path=str(path))
    reopened = DesktopSession()
    call(reopened, "open_calibration", path=str(path))
    actual = reopened.configuration.calibration_model
    assert actual.orig_pixel1 == pytest.approx(original[0])
    assert actual.orig_pixel2 == pytest.approx(original[1])


def test_inspection_curves_preserve_background_subtracted_pattern(loaded):
    result = call(loaded, "integration_background", enabled=True, smoothing=0.2, iterations=10, order=5)
    pattern = loaded.configuration.pattern_model.pattern
    original, background = result["pattern"]["backgroundCurves"]
    np.testing.assert_allclose(original["x"], pattern.original_data[0])
    np.testing.assert_allclose(original["y"], pattern.original_data[1])
    np.testing.assert_allclose(background["x"], pattern.auto_background_pattern.data[0])
    np.testing.assert_allclose(background["y"], pattern.auto_background_pattern.data[1])
    np.testing.assert_allclose(result["pattern"]["y"], pattern.data[1])
    disabled = call(loaded, "integration_background", enabled=False)
    assert disabled["pattern"]["backgroundCurves"] == []


def test_detector_roi_uses_qt_mask_and_rejects_invalid_limits(loaded):
    before = np.array(call(loaded, "state")["pattern"]["y"])
    limits = [100, 800, 150, 700]
    result = call(loaded, "integration_roi", limits=limits)
    assert result["state"]["integration"]["roi"] == limits
    expected_x, expected_y = loaded.configuration.integrate_image_1d()
    np.testing.assert_allclose(result["pattern"]["x"], expected_x)
    np.testing.assert_allclose(result["pattern"]["y"], expected_y)
    assert not np.allclose(result["pattern"]["y"], before)
    for invalid in ([800, 100, 150, 700], [0, 99999, 0, 700], [0, 1, 2], [0.5, 800, 0, 700]):
        assert not loaded.invoke("integration_roi", {"limits": invalid})["ok"]
        assert list(loaded.configuration.roi) == limits
    restored = call(loaded, "integration_roi")
    assert restored["state"]["integration"]["roi"] is None
    np.testing.assert_allclose(restored["pattern"]["y"], before)


def test_raw_image_display_and_readout_do_not_remove_scientific_corrections(loaded, tmp_path):
    raw = loaded.configuration.img_model.raw_img_data.copy()
    bkg = tmp_path / "display-background.tif"
    Image.fromarray(np.ones_like(raw, dtype=np.float32) * 5).save(bkg)
    result = call(loaded, "integration_image_background", path=str(bkg))
    raw_display = np.frombuffer(base64.b64decode(result["rawImage"]["data"]), dtype="<f4").reshape(raw.shape)
    np.testing.assert_allclose(raw_display, raw)
    np.testing.assert_allclose(loaded.configuration.img_model.img_data, raw - 5)
    assert call(loaded, "pixel", x=200, y=300, raw=True)["pixel"]["value"] == float(raw[300, 200])
    assert call(loaded, "pixel", x=200, y=300)["pixel"]["value"] == float(raw[300, 200] - 5)
    np.testing.assert_allclose(loaded.configuration.img_model.img_data, raw - 5)


def test_phase_guides_follow_real_phase_and_detector_geometry(loaded):
    assert call(loaded, "integration_phase_guides")["phaseGuides"] == []
    call(loaded, "integration_phase", operation="load", path=str(DATA / "jcpds/au_version3.jcpds"))
    guides = call(loaded, "integration_phase_guides")["phaseGuides"]
    assert guides and any(len(g["points"]) > 2 for g in guides)
    positions = loaded._model.phase_model.get_phase_line_positions(0, "2th_deg", loaded.configuration.calibration_model.wavelength * 1e10)
    assert all(any(np.isclose(g["twoTheta"], p) for p in positions) for g in guides)
    intensities = loaded._model.phase_model.reflections[0][:, 1]
    assert len({g["lineWidth"] for g in guides}) > 1
    for guide in guides:
        scaling = intensities[guide["reflectionIndex"]] / max(intensities)
        assert guide["phaseIndex"] == 0
        assert guide["lineWidth"] == pytest.approx(1 + 3 * scaling)
        assert guide["opacity"] == pytest.approx(0.3 + 0.4 * scaling)
    # Absolute intensities of another phase must not change relative styling.
    call(loaded, "integration_phase", operation="load", path=str(DATA / "jcpds/au_version3.jcpds"))
    loaded._model.phase_model.reflections[1][:, 1] *= 0.01
    combined = call(loaded, "integration_phase_guides")["phaseGuides"]
    for guide in combined:
        original = next(g for g in guides if g["reflectionIndex"] == guide["reflectionIndex"])
        assert guide["lineWidth"] == pytest.approx(original["lineWidth"])
        assert guide["opacity"] == pytest.approx(original["opacity"])
    call(loaded, "integration_phase", operation="update", index=1, visible=False)
    call(loaded, "integration_phase", operation="update", index=0, visible=False)
    assert call(loaded, "integration_phase_guides")["phaseGuides"] == []


def test_zero_intensity_phase_guides_have_finite_minimum_style(loaded):
    call(loaded, "integration_phase", operation="load", path=str(DATA / "jcpds/au_version3.jcpds"))
    loaded._model.phase_model.reflections[0][:, 1] = 0
    guides = call(loaded, "integration_phase_guides")["phaseGuides"]
    assert guides
    assert all(g["lineWidth"] == 1 and g["opacity"] == 0.3 for g in guides)


def test_capture_as_background_copies_pattern(loaded):
    call(loaded, "integration_overlay", operation="capture_background")
    background = loaded.configuration.pattern_model.background_pattern
    assert background is not loaded.configuration.pattern_model.pattern
    np.testing.assert_allclose(loaded.configuration.pattern_model.pattern.data[1], 0, atol=1e-8)
    call(loaded, "integration_clear_background")
    assert loaded.configuration.pattern_model.background_pattern is None


@pytest.mark.parametrize("background_range", [None, [2, 10]])
def test_quick_unit_toggles_preserve_automatic_background(loaded, background_range):
    call(loaded, "integration_background", enabled=True, smoothing=0.2, iterations=10, order=5, range=background_range)
    for unit in ("q_A^-1", "d_A", "2th_deg"):
        result = call(loaded, "integration_settings", unit=unit)
        assert result["state"]["integration"]["patternBackground"]["enabled"]
        assert result["pattern"]["unit"] == unit
        assert len(result["pattern"]["x"]) > 2
        assert len(result["pattern"]["backgroundCurves"]) == 2
        assert np.all(np.diff(result["pattern"]["x"]) > 0)
