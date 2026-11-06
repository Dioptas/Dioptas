"""Real-model parity, persistence and cancellation for the batch workspace."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import base64
import json
import threading

import h5py
import numpy as np
from PIL import Image
import pytest

from dioptas.desktop.session import DesktopSession
from dioptas.desktop.bridge import DesktopBridge
from dioptas.model.BatchModel import BatchModel
from dioptas.model.worker_configuration import (
    capture_worker_configuration,
    build_worker_configuration,
)

DATA = Path(__file__).resolve().parents[2] / "dioptas/tests/data"


def call(s, command, **args):
    r = s.invoke(command, args)
    assert r["ok"], r
    json.dumps(r, allow_nan=False)
    return r


@pytest.fixture
def prepared(tmp_path):
    s = DesktopSession()
    # A compact detector with smooth positive counts, away from the beam stop.
    yy, xx = np.mgrid[:56, :64]
    values = (
        10 + xx + yy + 30 * np.exp(-((xx - 30) ** 2 + (yy - 20) ** 2) / 70)
    ).astype(np.float32)
    paths = []
    for i, factor in enumerate((1, 2, 3)):
        path = tmp_path / f"frame_{i + 1:03d}.tif"
        Image.fromarray(values * factor).save(path)
        paths.append(str(path))
    call(s, "open_image", path=paths[0])
    call(s, "open_calibration", path=str(DATA / "CeO2_Pilatus1M.poni"))
    call(s, "settings", bins=100)
    return s, paths


@pytest.mark.parametrize(
    "unit,azimuth", [("2th_deg", None), ("q_A^-1", None), ("d_A", [170, 190])]
)
def test_qt_batch_parity_mask_transform_corrections(prepared, unit, azimuth):
    s, paths = prepared
    call(s, "image_transform", operation="flip_horizontal")
    c = s.configuration
    mask = np.zeros(c.img_model.img_data.shape, dtype=bool)
    mask[10:15, 20:26] = True
    c.mask_model.set_mask(mask)
    c.use_mask = True
    c.integration_unit = unit
    c.oned_azimuth_range = azimuth
    worker = build_worker_configuration(capture_worker_configuration(c))
    b = worker.batch_model
    b.set_image_files(paths)
    if azimuth:
        worker.calibration_model.pattern_geometry.reset()
        worker.calibration_model.pattern_geometry.setChiDiscAtZero()
    b.integrate_raw_data(0, 3, 1, use_all=True)
    result = call(s, "open_image", paths=paths, multiple=True)
    assert result["batchOpened"] and result["batch"]["unit"] == unit
    np.testing.assert_allclose(c.batch_model.binning, b.binning, equal_nan=True)
    np.testing.assert_allclose(c.batch_model.data, b.data, equal_nan=True)
    assert result["batch"]["entries"][2]["name"] == "frame_003.tif"
    selected = call(s, "batch_select", index=2)
    assert selected["state"]["imagePath"] == paths[2]
    assert selected["batchSelection"] == 2
    np.testing.assert_allclose(selected["pattern"]["y"], b.data[2], equal_nan=True)
    assert "batch" not in selected  # Browsing does not resend the matrix.


def test_range_stride_and_normalization_restore(prepared):
    s, paths = prepared
    call(s, "batch_load", paths=paths)
    original = s.configuration.batch_model.data.copy()
    call(s, "batch_normalize", start=1, stop=100, reference=2)
    b = s.configuration.batch_model
    assert b.normalization_enabled
    np.testing.assert_allclose(b.data.mean(axis=1), b.data.mean(axis=1)[1])
    call(s, "batch_normalize", enabled=False)
    np.testing.assert_array_equal(b.data, original)
    result = call(s, "batch_load", reintegrate=True, start=1, stop=3, step=2)
    assert len(result["batch"]["entries"]) == 2 and result["batch"]["total"] == 3
    np.testing.assert_allclose(s.configuration.batch_model.data, original[::2])
    previous = s.configuration.batch_model
    assert not s.invoke("batch_load", {"reintegrate": True, "start": 3, "stop": 1})[
        "ok"
    ]
    assert s.configuration.batch_model is previous


@pytest.mark.parametrize("stored_unit", ["2th_deg", "q_A^-1", "d_A"])
@pytest.mark.parametrize("axis_unit", ["2th_deg", "q_A^-1", "d_A"])
def test_physical_normalization_follows_axis_and_recorded_wavelength(prepared, stored_unit, axis_unit):
    s, paths = prepared
    s.configuration.integration_unit = stored_unit
    call(s, "batch_load", paths=paths)
    b = s.configuration.batch_model
    original = b.data.copy()
    wavelength = b._desktop_wavelength * 1e10
    x = b.binning
    # Independent physical conversions, including the descending d mapping.
    q = x if stored_unit == "q_A^-1" else 2 * np.pi / x if stored_unit == "d_A" else 4 * np.pi * np.sin(np.radians(x / 2)) / wavelength
    displayed = q if axis_unit == "q_A^-1" else 2 * np.pi / q if axis_unit == "d_A" else np.degrees(2 * np.arcsin(q * wavelength / (4 * np.pi)))
    ordered = np.sort(displayed)
    minimum, maximum = (ordered[19] + ordered[20]) / 2, (ordered[59] + ordered[60]) / 2
    mask = (displayed >= minimum) & (displayed <= maximum)
    indices = np.flatnonzero(mask)
    # Retain an already chosen reference; changing the region doesn't renumber it.
    call(s, "batch_normalization_settings", start=0, stop=99, reference=1)
    s.configuration.calibration_model.pattern_geometry.wavelength *= 1.2
    r = call(s, "batch_normalization_settings", minimum=minimum, maximum=maximum, unit=axis_unit)
    definition = {"minimum": minimum, "maximum": maximum, "unit": axis_unit}
    assert r["batch"]["normalizationRegion"] == definition
    assert r["batch"]["normalizationReferenceName"] == "frame_002.tif"
    assert b.normalization_range == (indices[0], indices[-1] + 1)
    call(s, "batch_normalize")
    means = original[:, mask].mean(axis=1)
    np.testing.assert_allclose(b.data, original * (means[1] / means)[:, None])
    # Reapplying is always calculated from original counts, not the scaled data.
    call(s, "batch_normalization_settings", **definition)
    np.testing.assert_allclose(b.data, original * (means[1] / means)[:, None])
    normalized = b.data.copy()
    for invalid in ({"minimum": maximum, "maximum": minimum},
                    {"minimum": float("nan"), "maximum": maximum},
                    {"minimum": True, "maximum": maximum},
                    {"minimum": maximum * 10, "maximum": maximum * 11}):
        assert not s.invoke("batch_normalization_settings", {**invalid, "unit": axis_unit})["ok"]
        np.testing.assert_array_equal(b.data, normalized)
        assert call(s, "batch_snapshot")["batch"]["normalizationRegion"] == definition
    call(s, "batch_normalize", enabled=False)
    np.testing.assert_array_equal(b.data, original)


def test_normalization_region_project_and_hdf5_roundtrip(prepared, tmp_path):
    s, paths = prepared
    call(s, "batch_load", paths=paths)
    b = s.configuration.batch_model
    original = b.data.copy()
    region = call(s, "batch_snapshot")["batch"]["normalizationRegion"]
    call(s, "batch_normalization_settings", **region)
    call(s, "batch_normalize")
    project, processed = tmp_path / "region.dio", tmp_path / "region.h5"
    call(s, "save_project", path=str(project))
    call(s, "integration_save_batch", path=str(processed))
    restored = DesktopSession()
    r = call(restored, "open_project", path=str(project))
    assert r["batch"]["normalizationRegion"] == region
    np.testing.assert_array_equal(restored.configuration.batch_model.data, b.data)
    call(restored, "batch_normalize", enabled=False)
    np.testing.assert_array_equal(restored.configuration.batch_model.data, original)
    r = call(restored, "batch_open", path=str(processed))
    assert r["batch"]["normalizationRegion"] == region
    np.testing.assert_array_equal(restored.configuration.batch_model.data, b.data)


def test_normalization_reciprocal_limits_without_recorded_wavelength(tmp_path):
    file = tmp_path / "reciprocal.h5"
    with h5py.File(file, "w") as f:
        g = f.create_group("processed/result")
        g["data"] = np.array([[1., 2., 3., 4.], [3., 6., 9., 12.]])
        g["binning"] = [1., 2., 3., 4.]
        g["binning"].attrs["radial_unit"] = "q_A^-1"
    s = DesktopSession()
    r = call(s, "batch_open", path=str(file))
    assert r["batch"]["normalizationRegion"]["unit"] == "q_A^-1"
    original = s.configuration.batch_model.data.copy()
    call(s, "batch_normalization_settings", minimum=1.8, maximum=3.5, unit="d_A")
    call(s, "batch_normalize")
    np.testing.assert_array_equal(s.configuration.batch_model.data[0], s.configuration.batch_model.data[1])
    assert not s.invoke("batch_normalization_settings", {"minimum": 1, "maximum": 10, "unit": "2th_deg"})["ok"]
    call(s, "batch_normalize", enabled=False)
    np.testing.assert_array_equal(s.configuration.batch_model.data, original)


def test_hdf5_frame_order(prepared, tmp_path):
    s, _ = prepared
    path = tmp_path / "series.h5"
    with h5py.File(path, "w") as f:
        f["entry/data/data"] = np.stack(
            [np.full((56, 64), i + 1, dtype=np.float32) for i in range(3)]
        )
    r = call(s, "batch_load", paths=[str(path)])
    assert [e["frame"] for e in r["batch"]["entries"]] == [1, 2, 3]
    r = call(s, "batch_select", index=2)
    assert r["state"]["integration"]["frame"] == 3
    pixels = np.frombuffer(base64.b64decode(r["image"]["data"]), dtype="<f4")
    np.testing.assert_array_equal(pixels, 3)


def test_failed_file_preserves_batch_live_image_and_geometry(prepared, tmp_path):
    s, paths = prepared
    call(s, "batch_load", paths=paths)
    b = s.configuration.batch_model
    call(s, "batch_select", index=1)
    geometry = call(s, "state")["state"]["geometry"]
    bad = tmp_path / "bad.tif"
    Image.fromarray(np.zeros((6, 8), dtype=np.uint16)).save(bad)
    r = s.invoke("batch_load", {"paths": [paths[0], str(bad)]})
    assert not r["ok"] and "shape" in r["error"]
    assert s.configuration.batch_model is b
    state = call(s, "state")
    assert state["state"]["imagePath"] == paths[1]
    assert state["state"]["geometry"] == geometry
    assert state["batch"]["selected"] == 1


def test_save_reopen_and_project_restore(prepared, tmp_path):
    s, paths = prepared
    call(s, "batch_load", paths=paths)
    original = s.configuration.batch_model.data.copy()
    call(s, "batch_normalize", start=1, stop=100, reference=2)
    call(s, "batch_select", index=2)
    normalized = s.configuration.batch_model.data.copy()
    project = tmp_path / "series.dio"
    call(s, "save_project", path=str(project))
    other = DesktopSession()
    r = call(other, "open_project", path=str(project))
    assert r["batch"]["selected"] == 2 and r["batch"]["normalized"]
    np.testing.assert_array_equal(other.configuration.batch_model.data, normalized)
    call(other, "batch_normalize", enabled=False)
    np.testing.assert_array_equal(other.configuration.batch_model.data, original)
    output = tmp_path / "series.h5"
    call(s, "integration_save_batch", path=str(output))
    call(s, "integration_save_batch", path=str(tmp_path / "series.csv"))
    for p in paths:
        Path(p).unlink()
    # Importing the saved batch keeps current geometry and handles missing raw.
    wavelength = call(s, "state")["batch"]["wavelength"]
    before = call(s, "state")["state"]["geometry"]
    r = call(s, "batch_open", path=str(output))
    assert r["batchOpened"] and not r["state"]["hasImage"]
    assert "unavailable" in r["batchWarning"]
    assert r["clearImage"] and r["cake"] is None
    assert r["state"]["geometry"] == before
    assert r["batch"]["wavelength"] == wavelength
    np.testing.assert_array_equal(s.configuration.batch_model.data, normalized)
    call(s, "integration_save_batch", path=str(tmp_path / "resaved.h5"))
    rows = np.loadtxt(tmp_path / "series.csv", delimiter=",")
    assert rows.shape == (100 * 3, 3)


def test_processed_without_provenance_or_calibration(tmp_path):
    file = tmp_path / "minimal.h5"
    with h5py.File(file, "w") as f:
        g = f.create_group("processed/result")
        g["data"] = np.arange(12).reshape(3, 4)
        g["binning"] = [1.0, 1.5, 3.0, 10.0]
        g["binning"].attrs["radial_unit"] = "d_A"
    s = DesktopSession()
    r = call(s, "batch_open", path=str(file))
    assert r["batch"]["unit"] == "d_A" and not r["state"]["hasImage"]
    assert r["batch"]["wavelength"] is None
    assert r["batch"]["entries"][0]["path"] == ""
    out = tmp_path / "resaved.h5"
    call(s, "integration_save_batch", path=str(out))
    call(s, "batch_open", path=str(out))
    assert call(s, "batch_select", index=1)["pattern"]["y"] == [4, 5, 6, 7]


def test_qt_load_action_and_display_units(prepared, tmp_path):
    s, paths = prepared
    result = call(s, "batch_load_data", paths=paths)
    b = s.configuration.batch_model
    original = b.data.copy()
    theta = b.binning.copy()
    wavelength = b._desktop_wavelength
    for unit, expected in (
        ("q_A^-1", 4 * np.pi * np.sin(np.radians(theta / 2)) / (wavelength * 1e10)),
        ("d_A", wavelength * 1e10 / (2 * np.sin(np.radians(theta / 2)))),
        ("2th_deg", theta),
    ):
        displayed = call(s, "batch_unit", unit=unit)
        assert displayed["batch"]["id"] == result["batch"]["id"]
        assert displayed["pattern"]["unit"] == unit
        np.testing.assert_allclose(displayed["pattern"]["x"], expected)
        np.testing.assert_array_equal(b.data, original)
        np.testing.assert_array_equal(b.binning, theta)
    target = tmp_path / "series.h5"
    call(s, "integration_save_batch", path=str(target))
    imported = call(s, "batch_load_data", paths=[str(target)])
    assert len(imported["batch"]["entries"]) == 3
    np.testing.assert_array_equal(s.configuration.batch_model.data, original)


def test_stored_reciprocal_units_need_no_invented_wavelength(tmp_path):
    file = tmp_path / "stored.h5"
    with h5py.File(file, "w") as f:
        group = f.create_group("processed/result")
        group["data"] = np.arange(12).reshape(3, 4)
        group["binning"] = [1., 2., 4., 8.]
        group["binning"].attrs["radial_unit"] = "q_A^-1"
    s = DesktopSession()
    call(s, "batch_load_data", paths=[str(file)])
    r = call(s, "batch_unit", unit="d_A")
    np.testing.assert_allclose(r["pattern"]["x"], 2 * np.pi / np.array([1., 2., 4., 8.]))
    assert r["batch"]["wavelength"] is None
    assert not s.invoke("batch_unit", {"unit": "2th_deg"})["ok"]
    assert call(s, "batch_snapshot")["batch"]["unit"] == "d_A"


def test_qt_normalization_settings_and_neighboring_folders(prepared, tmp_path):
    s, paths = prepared
    from shutil import copyfile
    folders = []
    for index in (1, 2):
        folder = tmp_path / f"scan_{index:03d}"
        folder.mkdir()
        files = []
        for source in paths:
            target = folder / Path(source).name
            copyfile(source, target)
            files.append(str(target))
        folders.append(files)
    call(s, "batch_load_data", paths=folders[0])
    r = call(s, "batch_folder_step", direction=1)
    assert [e["path"] for e in r["batch"]["entries"]] == folders[1]
    r = call(s, "batch_folder_step", direction=-1)
    assert [e["path"] for e in r["batch"]["entries"]] == folders[0]
    b = s.configuration.batch_model
    original = b.data.copy()
    r = call(s, "batch_normalization_settings", start=0, stop=99, reference=1)
    assert not r["batch"]["normalized"]
    assert r["batch"]["normalizationRange"] == [0, 100]
    assert r["batch"]["normalizationReference"] == 1
    np.testing.assert_array_equal(b.data, original)
    call(s, "batch_normalize", start=1, stop=100, reference=2)
    call(s, "batch_normalization_settings", start=0, stop=99, reference=2)
    np.testing.assert_allclose(b.data.mean(axis=1), original[2].mean())
    call(s, "batch_normalize", enabled=False)
    np.testing.assert_array_equal(b.data, original)


def test_cancellation_bypasses_worker_and_does_not_publish(prepared, monkeypatch):
    s, paths = prepared
    # Exercise the real bridge's progress/cancel fast path with a held worker.
    started, release = threading.Event(), threading.Event()
    original = BatchModel.integrate_raw_data

    def held(self, *args, **kwargs):
        started.set()
        assert release.wait(10)
        return original(self, *args, **kwargs)

    bridge = DesktopBridge()
    try:
        call(bridge, "open_image", path=paths[0])
        call(bridge, "open_calibration", path=str(DATA / "CeO2_Pilatus1M.poni"))
        previous = call(bridge, "batch_load", paths=paths)["batch"]["raster"]["data"]
        monkeypatch.setattr(BatchModel, "integrate_raw_data", held)
        with ThreadPoolExecutor() as pool:
            pending = pool.submit(bridge.invoke, "batch_load", {"paths": paths})
            assert started.wait(10)
            progress = call(bridge, "progress")["progress"]
            assert progress["running"] and progress["label"] == "Integrating batch"
            call(bridge, "cancel_refinement")
            release.set()
            assert pending.result(20)["cancelled"]
        r = call(bridge, "state")
        assert r["batch"]["raster"]["data"] == previous
        assert r["state"]["imagePath"] == paths[0]
    finally:
        release.set()
        bridge.close()


def test_background_and_flat_field_match_live_integration(prepared, tmp_path):
    s, paths = prepared
    background = tmp_path / "background.tif"
    flat = tmp_path / "flat.tif"
    Image.fromarray(np.full((56, 64), 4, dtype=np.float32)).save(background)
    Image.fromarray(np.tile(np.linspace(1, 2, 64, dtype=np.float32), (56, 1))).save(
        flat
    )
    call(s, "integration_image_background", path=str(background))
    call(s, "integration_flat_field", path=str(flat))
    expected = []
    for path in paths:
        call(s, "open_image", path=path)
        expected.append(
            np.array(s.configuration.pattern_model.pattern.data[1], copy=True)
        )
    call(s, "batch_load", paths=paths)
    np.testing.assert_allclose(
        s.configuration.batch_model.data, expected, rtol=1e-12, atol=1e-12
    )
    stored = call(s, "state")["batch"]["pattern"]
    call(s, "settings", bins=200)
    # The batch remains a historical result until explicit reintegration.
    assert call(s, "state")["batch"]["pattern"] == stored


def test_selected_frame_updates_cake_and_keeps_stored_series(prepared):
    s, paths = prepared
    call(s, "batch_load", paths=paths)
    batch = s.configuration.batch_model
    original = np.array(batch.data, copy=True)
    first = call(s, "batch_select", index=0)
    last = call(s, "batch_select", index=2)
    assert first["cake"] and last["cake"]
    assert last["state"]["imagePath"] == paths[2]
    a = np.frombuffer(base64.b64decode(first["cake"]["data"]), dtype="<f4")
    b = np.frombuffer(base64.b64decode(last["cake"]["data"]), dtype="<f4")
    assert np.max(a) > 0
    np.testing.assert_allclose(b, a*3, rtol=1e-6, atol=1e-5)
    np.testing.assert_array_equal(batch.data, original)
    np.testing.assert_allclose(last["pattern"]["y"], original[2])
    call(s, "batch_normalize", start=1, stop=100, reference=2)
    normalized = call(s, "batch_select", index=2)
    assert normalized["cake"]
    np.testing.assert_allclose(normalized["pattern"]["y"], batch.data[2])
    # Normalization changes stored profiles, never the source detector/cake.
    assert normalized["cake"]["data"] == last["cake"]["data"]
    snapshot = call(s, "batch_snapshot")
    assert snapshot["batch"]["selected"] == 2
    assert snapshot["batch"]["id"] == call(s, "batch_snapshot")["batch"]["id"]
    assert "image" not in snapshot and "cake" not in snapshot


@pytest.mark.parametrize("unit", ["2th_deg", "q_A^-1", "d_A"])
def test_batch_click_links_radial_position_and_keeps_matrix(prepared, unit):
    s, paths = prepared
    call(s, "batch_load", paths=paths)
    batch = call(s, "batch_unit", unit=unit)["batch"]
    matrix = s.configuration.batch_model.data.copy()
    x = batch["x"][len(batch["x"]) // 2]
    selected = call(s, "batch_select", index=1, position={"x": x, "unit": unit})
    assert selected["batchPosition"] == {"x": x, "unit": unit}
    assert selected["linked"]["radial"] == pytest.approx(x)
    assert selected["state"]["imagePath"] == paths[1]
    assert selected["cake"]
    snapshot = call(s, "batch_snapshot")["batch"]
    assert snapshot["position"]["unit"] == "2th_deg"
    assert snapshot["position"]["x"] == pytest.approx(selected["linked"]["twoTheta"])
    np.testing.assert_array_equal(s.configuration.batch_model.data, matrix)
    Path(paths[0]).unlink()
    stored = call(s, "batch_select", index=0, position={"x": x, "unit": unit})
    assert stored["clearImage"] and stored["batchPosition"]["x"] == x
    assert stored.get("linked") is None


def test_batch_phase_lines_follow_shared_phase_conditions(prepared):
    s, paths = prepared
    call(s, "batch_load", paths=paths)
    loaded = call(s, "integration_phase", operation="load", path=str(DATA / "jcpds/au_version3.jcpds"))
    original = call(s, "batch_snapshot")["batch"]["phaseLines"]
    assert loaded["batchPhaseLines"] == original
    assert not {"batch", "image", "cake"}.intersection(loaded)
    assert original and all(line["x"] > 0 for line in original)
    expected = s._model.phase_model.get_phase_line_positions(0, "d_A", s.configuration.calibration_model.wavelength * 1e10)
    np.testing.assert_allclose([line["x"] for line in original], expected)
    updated = call(s, "integration_phase", operation="update", index=0, pressure=20)
    changed = call(s, "batch_snapshot")["batch"]["phaseLines"]
    assert updated["batchPhaseLines"] == changed
    assert changed[0]["x"] != original[0]["x"]
    hidden = call(s, "integration_phase", operation="update", index=0, visible=False)
    assert hidden["batchPhaseLines"] == []
    assert not call(s, "batch_snapshot")["batch"]["phaseLines"]
