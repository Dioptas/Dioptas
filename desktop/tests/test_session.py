"""Numerical and persistence checks for the desktop command boundary."""

import base64
import json
import importlib.util
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from dioptas.desktop.session import DesktopSession, raster

ROOT = Path(__file__).resolve().parents[2]
# Measured CeO2 seed coordinates. These select peaks; no saved geometry is
# loaded into the fit. The PONI reference is used only to check scale below.
SEEDS = [
    (637, 564, 1),
    (671, 511, 2),
    (668, 703, 3),
    (350.5, 592.8, 1),
    (554.3, 367.9, 1),
]


def call(session, action, **payload):
    result = session.invoke(action, payload)
    assert result["ok"], result.get("error")
    json.dumps(result, allow_nan=False)
    return result


@pytest.fixture
def raw():
    session = DesktopSession()
    call(session, "example")
    return session


@pytest.fixture(params=["pyfai", "dioptrin"])
def fitted(raw, request):
    if request.param == "dioptrin" and importlib.util.find_spec("dioptrin") is None:
        pytest.skip("Optional Dioptrin engine not installed")
    call(raw, "calibration_engine", engine=request.param)
    for x, y, ring in SEEDS:
        call(raw, "pick_peak", x=x, y=y, ring=ring)
    call(raw, "calibrate", automatic=False)
    return raw


def test_scientific_entry_does_not_import_dioptas_gui():
    code = """
import sys
class WithoutQt:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'qtpy', 'PyQt6', 'PyQt5', 'PySide6', 'PySide2'}:
            raise ImportError('Qt intentionally unavailable')
sys.meta_path.insert(0, WithoutQt())
from dioptas.desktop.session import DesktopSession
session = DesktopSession()
assert session.invoke('example')['ok']
assert not any(name.startswith(('dioptas.controller', 'dioptas.widgets')) for name in sys.modules)
assert 'dioptrin' not in sys.modules
"""
    subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_example_starts_uncalibrated(raw):
    state = call(raw, "state")["state"]
    assert state["hasImage"] and not state["calibrated"]
    assert state["calibration"]["picks"] == []
    assert state["calibration"]["wavelength"] == pytest.approx(0.406626)
    assert state["bins"] is None
    assert state["integration"]["automaticBinning"] is True
    assert not raw.invoke("calibrate")["ok"]


def test_native_fit_and_independent_angular_residual(fitted):
    result = call(fitted, "state")
    state = result["state"]
    assert state["calibration"]["engine"] in {"pyfai", "dioptrin"}
    assert state["geometry"]["dist"] == pytest.approx(0.20865, abs=0.003)
    assert np.isfinite(state["geometry"]["rot3"])
    assert 0 < state["calibration"]["rmsDegrees"] < 0.03
    calibration = fitted.configuration.calibration_model
    points = calibration.get_point_array()
    # Evaluate native fitted parameters using pyFAI's separate geometry code.
    measured = calibration.pattern_geometry.tth(points[:, 0], points[:, 1])
    expected = np.asarray(calibration.calibrant.get_2th())[points[:, 2].astype(int)]
    rms = np.sqrt(np.mean((measured - expected) ** 2)) * 180 / np.pi
    assert state["calibration"]["rmsDegrees"] == pytest.approx(rms, abs=1e-8)
    assert len(result["rings"]) > 2
    assert result["pattern"]["unit"] == "2th_deg"
    assert fitted.configuration.calibration_model.use_dioptrin == (
        state["calibration"]["engine"] == "dioptrin"
    )


def test_mask_edits_use_original_pixel_coordinates_and_undo(raw):
    result = call(raw, "mask_stroke", points=[[10, 20]], radius=4)
    mask = raw.configuration.mask_model.get_img()
    assert mask[20, 10] and not mask[10, 20]
    assert result["state"]["maskedPixels"] == np.count_nonzero(mask)
    assert result["state"]["useMask"]
    assert call(raw, "undo_mask")["state"]["maskedPixels"] == 0
    assert not raw.invoke("mask_stroke", {"points": [[-1, 20]], "radius": 4})["ok"]
    assert np.count_nonzero(raw.configuration.mask_model.get_img()) == 0


def test_downsampled_mask_preserves_single_excluded_pixel():
    mask = np.zeros((2001, 1500), dtype=bool)
    mask[101, 102] = True
    preview = raster(mask, mask=True)
    values = np.frombuffer(base64.b64decode(preview["data"]), dtype=np.uint8).reshape(
        preview["height"], preview["width"]
    )
    assert preview["step"] == 3
    assert values[101 // 3, 102 // 3] == 1
    assert values.sum() == 1


def test_poni_and_project_round_trip(fitted, tmp_path):
    poni = tmp_path / "calibration.poni"
    project = tmp_path / "experiment.dio"
    pattern = tmp_path / "pattern.xy"
    call(fitted, "save_calibration", path=str(poni))
    call(fitted, "settings", unit="q_A^-1", bins=1000)
    call(fitted, "mask_stroke", points=[[20, 30]], radius=5)
    original = call(fitted, "state")
    call(fitted, "save_project", path=str(project))
    call(fitted, "export_pattern", path=str(pattern))
    saved = np.loadtxt(pattern)
    np.testing.assert_allclose(
        saved[:, 0], original["pattern"]["x"], rtol=1e-6, atol=1e-8
    )
    np.testing.assert_allclose(
        saved[:, 1], original["pattern"]["y"], rtol=1e-6, atol=1e-8
    )
    restored = DesktopSession()
    call(
        restored,
        "calibration_engine",
        engine=original["state"]["calibration"]["engine"],
    )
    result = call(restored, "open_project", path=str(project))
    assert (
        result["state"]["calibration"]["rmsDegrees"]
        == original["state"]["calibration"]["rmsDegrees"]
    )
    assert result["state"]["bins"] == 1000
    assert result["state"]["useMask"]
    assert result["state"]["maskedPixels"] == original["state"]["maskedPixels"]
    # pyFAI returns float32 intensities; rebuilding its lookup cache can
    # change the final rounding by one ULP without changing project inputs.
    np.testing.assert_allclose(
        result["pattern"]["y"],
        original["pattern"]["y"],
        rtol=2 * np.finfo(np.float32).eps,
        atol=1e-7,
    )
    np.testing.assert_array_equal(
        restored.configuration.img_model.img_data,
        fitted.configuration.img_model.img_data,
    )
    # PONI orientation must round-trip through the existing Dioptas reader.
    from dioptas.pipeline import Pipeline

    pipeline = Pipeline()
    pipeline.load_calibration(str(poni))
    assert pipeline.calibration_model.pattern_geometry.dist == pytest.approx(
        original["state"]["geometry"]["dist"]
    )


def test_unit_and_bin_validation_is_explicit(raw):
    original = call(raw, "state")["state"]
    for payload in [
        {"unit": "unknown"},
        {"bins": float("nan")},
        {"bins": 500.5},
        {"unit": "q_A^-1", "use_mask": "invalid"},
    ]:
        assert not raw.invoke("settings", payload)["ok"]
        result = call(raw, "state")["state"]
        assert result["unit"] == original["unit"] and result["bins"] == original["bins"]


def test_histogram_counts_full_resolution_including_zero_and_negative_pixels():
    data = np.arange(63, dtype=float).reshape(7, 9) - 10
    data[1, 1] = 1e8  # Not sampled by the reduced preview.
    data[2, 2] = np.nan
    data[3, 3] = np.inf
    before = data.copy()
    result = raster(data, max_side=2, histogram=True)
    histogram = result["histogram"]
    assert result["step"] > 1
    assert histogram["finitePixels"] == 61
    assert sum(histogram["counts"]) == 61
    assert histogram["edges"][0] <= -10
    assert histogram["edges"][-1] >= 1e8 * (1 - 1e-12)
    assert any(count for edge, count in zip(histogram["edges"], histogram["counts"]) if edge < 0)
    np.testing.assert_array_equal(data, before)


def test_display_and_mask_have_original_spatial_resolution(raw):
    result = call(raw, "state")
    image, mask = result["image"], result["mask"]
    source = raw.configuration.img_model.img_data
    assert image["step"] == mask["step"] == 1
    assert (image["height"], image["width"]) == source.shape
    assert (mask["height"], mask["width"]) == source.shape
    rendered = np.frombuffer(base64.b64decode(image["data"]), dtype="<f4").reshape(source.shape)
    np.testing.assert_array_equal(rendered, source.astype(np.float32))
