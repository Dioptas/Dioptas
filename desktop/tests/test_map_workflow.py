"""Real scientific model and transport coverage for the desktop Map adapter."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import time

import h5py
import numpy as np
from PIL import Image
import pytest

from dioptas.desktop.session import DesktopSession
from dioptas.desktop.bridge import DesktopBridge
from dioptas.model.MapModel import MapPointInfo

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "dioptas/tests/data"


def call(session, action, **payload):
    response = session.invoke(action, payload)
    assert response["ok"], response
    json.dumps(response, allow_nan=False)
    return response


@pytest.fixture
def stored():
    s = DesktopSession()
    # Analytic patterns: a triangular peak on an exactly linear background.
    # Testing independently known reductions catches unit/ROI wiring errors.
    x = np.arange(11, dtype=float)
    peak = np.array([0, 0, 0, 1, 2, 3, 2, 1, 0, 0, 0], dtype=float)
    y = np.array([10+x+peak*k for k in (1, 2, 3, 4, 5)])
    s.configuration.map_model.set_integration_results(x, y,
        [MapPointInfo(str(DATA / f"missing_{i:03d}.tif"), i) for i in range(5)],
        [str(DATA / "missing.tif")], pattern_unit="q_A^-1")
    call(s, "map_roi", name="A", minimum=0, maximum=10)
    return s


@pytest.mark.parametrize("reduction,background,expected", [
    ("sum", False, 135+9*np.arange(1, 6)),
    ("sum", True, 9*np.arange(1, 6)),
    ("mean", False, 15+np.arange(1, 6)),
    ("max", False, np.array([19, 21, 24, 27, 30])),
    ("area", False, 9*np.arange(1, 6)),
    ("center", False, np.full(5, 5)),
    ("width", False, np.full(5, 3)),
])
def test_roi_values_from_independently_known_profiles(stored, reduction, background, expected):
    result = call(stored, "map_roi", name="A", reduction=reduction, background=background)
    np.testing.assert_allclose(stored.configuration.map_model.window_intensities, expected)
    assert result["map"]["unit"] == "q_A^-1"
    assert "image" not in result  # ROI updates do not resend detector arrays.


def test_grid_transforms_blanks_and_selection(stored):
    call(stored, "map_grid", rows=2, columns=3, snake=True)
    m = stored.configuration.map_model
    np.testing.assert_array_equal(m.index_map, [[0, 1, 2], [-1, 4, 3]])
    result = call(stored, "map_select", row=1, column=2)
    assert result["map"]["selected"] == 3
    np.testing.assert_allclose(result["pattern"]["y"], m.pattern_intensities[3])
    assert not result["state"]["hasImage"]
    assert "unavailable" in result["mapWarning"]
    blank = call(stored, "map_select", row=1, column=0)
    assert blank["pattern"] is None and blank["map"]["selected"] is None
    call(stored, "map_grid", transpose=True, flip_horizontal=True)
    np.testing.assert_array_equal(m.index_map, [[-1, 0], [4, 1], [3, 2]])
    call(stored, "map_arrange", op="insert", slot=1)
    assert m.get_slots()[1] is None
    call(stored, "map_arrange", op="remove", slot=1)
    call(stored, "map_arrange", op="exclude", index=2)
    assert 2 not in m.index_map
    assert 2 in m.excluded_points
    call(stored, "map_arrange", op="exclude", index=2)
    assert 2 in m.index_map
    assert not stored.invoke("map_grid", {"rows": 1, "columns": 2})["ok"]


def test_expression_rename_invalid_and_nonfinite(stored):
    call(stored, "map_roi", op="add")
    call(stored, "map_roi", name="B", minimum=0, maximum=10, reduction="sum")
    call(stored, "map_expression", name="Ratio", expression="A/B")
    np.testing.assert_allclose(stored.configuration.map_model.window_intensities, 1)
    call(stored, "map_roi", name="A", new_name="Peak")
    assert stored.configuration.map_model.expressions["Ratio"].replace(" ", "") == "Peak/B"
    assert not stored.invoke("map_expression", {"name": "Bad", "expression": "unknown/2"})["ok"]
    assert stored.configuration.map_model.active_layer == "Ratio"
    result = call(stored, "map_roi", name="Peak", minimum=100, maximum=200)
    assert all(v is None for row in result["map"]["values"] for v in row)
    json.dumps(result, allow_nan=False)


def test_normalization_project_round_trip_and_exports(stored, tmp_path):
    m = stored.configuration.map_model
    original = m.pattern_intensities.copy()
    batch = stored.configuration.batch_model
    batch.data = np.arange(24, dtype=float).reshape(3, 8) + 1
    batch.normalize((1, 7), 0)
    other_batch_data = batch.data
    call(stored, "map_normalize", start=1, stop=10, reference=2)
    expected = original * (original[2, 1:10].mean()/original[:, 1:10].mean(axis=1))[:, None]
    assert batch.data is other_batch_data and batch.normalization_enabled
    np.testing.assert_allclose(m.pattern_intensities, expected)
    call(stored, "map_grid", rows=2, columns=3, snake=True)
    call(stored, "save_project", path=str(tmp_path / "map.dio"))
    reopened = DesktopSession()
    result = call(reopened, "open_project", path=str(tmp_path / "map.dio"))
    assert result["map"]["normalized"] and result["map"]["snake"]
    np.testing.assert_allclose(reopened.configuration.map_model.pattern_intensities, expected)
    call(reopened, "map_normalize", enabled=False)
    np.testing.assert_allclose(reopened.configuration.map_model.pattern_intensities, original)
    path = tmp_path / "map.txt"
    call(stored, "map_export", path=str(path))
    np.testing.assert_allclose(np.loadtxt(path), m.map, rtol=1e-5, equal_nan=True)
    call(stored, "map_export", path=str(tmp_path / "map.tiff"))
    tif = np.asarray(Image.open(tmp_path / "map.tiff"))
    assert tif.shape == (2, 3) and tif[1, 0] == 0


def test_batch_import_unit_and_missing_sources(tmp_path):
    path = tmp_path / "batch.h5"
    with h5py.File(path, "w") as f:
        g = f.create_group("processed/result")
        g["data"] = np.arange(24, dtype=float).reshape(3, 8)
        g["binning"] = np.arange(8, dtype=float)[::-1] + 1
        g["binning"].attrs["radial_unit"] = "d_A"
    s = DesktopSession()
    result = call(s, "map_batch", path=str(path))
    assert result["map"]["points"] == 3 and result["pattern"]["unit"] == "d_A"
    assert not result["state"]["hasImage"]
    np.testing.assert_array_equal(result["pattern"]["x"], np.arange(8)[::-1]+1)
    assert s.configuration.calibration_model.is_calibrated is False


def test_measured_image_integration_linked_selection_and_failed_load(tmp_path):
    s = DesktopSession()
    call(s, "example")
    call(s, "open_calibration", path=str(DATA / "CeO2_Pilatus1M.poni"))
    result = call(s, "map_load", paths=[str(DATA / "CeO2_Pilatus1M.tif")]*3)
    m = s.configuration.map_model
    assert result["map"]["points"] == 3
    assert result["image"]["step"] == 1 and result["image"]["width"] == 981
    x, expected = s.configuration.integrate_image_1d(update_pattern_model=False)
    # Map disables zero trimming, so compare the full existing engine output.
    np.testing.assert_allclose(m.pattern_intensities[0][:len(expected)], expected)
    result = call(s, "map_select", index=2)
    assert result["map"]["selected"] == 2 and result["state"]["hasImage"]
    original = m.pattern_intensities.copy()
    broken = tmp_path / "bad.tif"
    broken.write_text("not a detector image")
    assert not s.invoke("map_load", {"paths": [str(broken)]})["ok"]
    np.testing.assert_array_equal(m.pattern_intensities, original)


def test_cancel_real_map_preserves_previous_map_and_bypasses_worker():
    with ThreadPoolExecutor(1) as executor:
        bridge = DesktopBridge()
        try:
            call(bridge, "example")
            call(bridge, "open_calibration", path=str(DATA / "CeO2_Pilatus1M.poni"))
            call(bridge, "map_load", paths=[str(DATA / "CeO2_Pilatus1M.tif")])
            task = executor.submit(bridge.invoke, "map_load", {"paths": [str(DATA / "CeO2_Pilatus1M.tif")]*60})
            deadline = time.monotonic()+5
            while time.monotonic() < deadline:
                progress = call(bridge, "progress")["progress"]
                if progress["running"]:
                    break
                time.sleep(0.01)
            assert progress["running"]
            start = time.monotonic()
            call(bridge, "cancel_refinement")
            assert time.monotonic()-start < 0.5
            assert task.result(timeout=10)["cancelled"]
            assert call(bridge, "state")["map"]["points"] == 1
        finally:
            bridge.close()


def test_map_display_retains_blank_footprint_and_never_mutates_values(stored):
    import base64
    call(stored, "map_grid", rows=2, columns=3)
    m = stored.configuration.map_model
    original = m.map.copy()
    result = call(stored, "map_display", smooth=5, contours=5)
    raster = result["mapPreview"]
    assert raster["width"] == 15 and raster["height"] == 10
    assert raster["fullWidth"] == 3 and raster["fullHeight"] == 2
    data = np.frombuffer(base64.b64decode(raster["data"]), dtype="<f4").reshape(10, 15)
    assert np.isnan(data).any() and np.isfinite(data).any()
    assert result["mapContours"]
    np.testing.assert_array_equal(m.map, original)


def test_folder_order_and_multiframe_identity(tmp_path):
    from fabio.edfimage import EdfImage
    folder = tmp_path / "scan"
    folder.mkdir()
    for name, value in [("scan10.edf", 10), ("scan2.edf", 2)]:
        image = EdfImage(data=np.full((40, 50), value, dtype=np.uint16))
        image.append_frame(data=np.full((40, 50), value+1, dtype=np.uint16))
        image.write(str(folder / name))
    s = DesktopSession()
    call(s, "manual_geometry", convention="pyfai", values={
        "dist": 200, "poni1": 1, "poni2": 1, "rot1": 0, "rot2": 0, "rot3": 0,
        "wavelength": 0.4, "pixel1": 100, "pixel2": 100, "polarization_factor": 0.99,
    })
    result = call(s, "map_folder", path=str(folder))
    m = s.configuration.map_model
    assert result["map"]["points"] == 4
    assert [(Path(p.filepath).name, p.frame_index) for p in m.point_infos] == [
        ("scan2.edf", 0), ("scan2.edf", 1), ("scan10.edf", 0), ("scan10.edf", 1)]
    call(s, "map_select", index=3)
    np.testing.assert_array_equal(s.configuration.img_model.img_data, 11)
    assert s.configuration.img_model.series_pos == 2
