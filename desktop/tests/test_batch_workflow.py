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
