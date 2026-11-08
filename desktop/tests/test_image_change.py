"""Detector changes must be decided before touching a calibrated session."""

import importlib.util
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from dioptas.desktop.session import DesktopSession

DATA = Path(__file__).resolve().parents[2] / "dioptas/tests/data"


def call(session, action, **arguments):
    result = session.invoke(action, arguments)
    assert result["ok"], result.get("error")
    return result


@pytest.fixture(params=["pyfai", "dioptrin"])
def experiment(request, tmp_path):
    if request.param == "dioptrin" and importlib.util.find_spec("dioptrin") is None:
        pytest.skip("Optional Dioptrin engine not installed")
    for name, shape in [("image_001", (96, 128)), ("image_002", (64, 80)), ("same", (96, 128))]:
        Image.fromarray(np.arange(np.prod(shape), dtype=np.uint16).reshape(shape) + 1).save(tmp_path / f"{name}.tif")
    session = DesktopSession(engine=request.param)
    call(session, "open_calibration", path=str(DATA / "CeO2_Pilatus1M.poni"))
    # Legacy PONIs without dimensions can bind to their first image.
    call(session, "open_image", path=str(tmp_path / "image_001.tif"))
    call(session, "integration_settings", bins=100, cake_bins=20)
    call(session, "mask_stroke", points=[[20, 30]], radius=3)
    call(session, "integration_image_background", path=str(tmp_path / "same.tif"))
    call(session, "integration_image_background", scale=0.1)
    yield session
    session.close()


def test_mismatch_is_readonly_and_can_be_cancelled(experiment, tmp_path):
    session = experiment
    before = call(session, "state")
    c = session.configuration
    pixels = c.img_model.img_data.copy()
    mask = c.mask_model.get_img().copy()
    detector = c.calibration_model.detector
    history = session._model.history.depth
    iterator_path = c.img_model.file_name_iterator.complete_path
    result = call(session, "open_image", path=str(tmp_path / "image_002.tif"))
    assert result["cancelled"]
    assert result["imageChange"]["previousShape"] == [96, 128]
    assert result["imageChange"]["newShape"] == [64, 80]
    assert call(session, "state") == before
    assert session._model.history.depth == history
    assert c.img_model.file_name_iterator.complete_path == iterator_path
    assert c.calibration_model.detector is detector
    np.testing.assert_array_equal(c.img_model.img_data, pixels)
    np.testing.assert_array_equal(c.mask_model.get_img(), mask)


def test_accepting_mismatch_cannot_export_old_result(experiment, tmp_path):
    s = experiment
    call(s, "integration_overlay", operation="capture")
    call(s, "integration_phase", operation="load", path=str(DATA / "jcpds/au_version3.jcpds"))
    call(s, "integration_flat_field", path=str(tmp_path / "same.tif"))
    result = call(s, "open_image", path=str(tmp_path / "image_002.tif"), reset_calibration=True)
    state = result["state"]
    assert result["calibrationReset"]
    assert state["shape"] == [64, 80]
    assert not state["calibrated"] and not state["calibration"]["setupConfirmed"]
    assert state["calibrationName"] is None
    assert state["calibration"]["picks"] == []
    assert not state["calibration"]["saved"]
    assert state["calibration"]["detectorIsCustom"]
    assert state["geometry"]["poni1"] == state["geometry"]["poni2"] == 0
    assert state["geometry"]["rot1"] == state["geometry"]["rot2"] == state["geometry"]["rot3"] == 0
    assert state["maskedPixels"] == 0
    assert result["pattern"] is None and result["cake"] is None
    assert result["rings"] == []
    assert len(state["integration"]["overlays"]) == len(state["integration"]["phases"]) == 1
    image = s.configuration.img_model
    assert not image.has_background() and image.background_filename == ""
    assert image.params.background_filename == ""
    assert not image.has_corrections() and image.params.corrections == {}
    assert s.configuration.calibration_model._dioptrin_integrator is None
    assert not s.invoke("integrate")["ok"]
    assert not s.invoke("save_calibration", {"path": str(tmp_path / "bad.poni")})["ok"]
    assert not s.invoke("integration_save_pattern", {"path": str(tmp_path / "bad.xy")})["ok"]
    call(s, "integration_overlay", operation="update", index=0, visible=False)
    assert s._pattern is None or s._pattern["x"] == []
    assert not s.invoke("integration_save_pattern", {"path": str(tmp_path / "bad.xy")})["ok"]
    assert not (tmp_path / "bad.xy").exists()
    restored = call(s, "open_calibration", path=str(DATA / "CeO2_Pilatus1M.poni"))
    assert restored["state"]["calibrated"] and restored["pattern"] is not None


def test_same_size_preserves_geometry_mask_background_and_orientation(experiment, tmp_path):
    s = experiment
    call(s, "image_transform", operation="rotate_right")
    previous = call(s, "state")["state"]
    result = call(s, "open_image", path=str(tmp_path / "same.tif"))
    assert "imageChange" not in result
    assert result["state"]["calibrated"]
    assert result["state"]["geometry"] == previous["geometry"]
    assert result["state"]["maskedPixels"] == previous["maskedPixels"]
    assert result["state"]["shape"] == [128, 96]
    assert s.configuration.img_model.has_background()


def test_explicit_reset_keeps_raw_image_and_original_orientation(experiment):
    s = experiment
    raw = s.configuration.img_model.untransformed_raw_img_data.copy()
    call(s, "image_transform", operation="rotate_right")
    result = call(s, "reset_calibration")
    assert result["state"]["hasImage"]
    assert result["state"]["shape"] == [96, 128]
    assert not result["state"]["calibrated"]
    assert result["state"]["calibration"]["transformations"] == []
    np.testing.assert_array_equal(s.configuration.img_model.img_data, raw)


def test_next_file_does_not_advance_on_cancel(experiment):
    s = experiment
    before = call(s, "state")
    result = call(s, "next_image")
    assert result["imageChange"]["newShape"] == [64, 80]
    assert call(s, "state") == before
    assert call(s, "next_image")["imageChange"] == result["imageChange"]


def test_unreadable_replacement_does_not_reset(experiment, tmp_path):
    s = experiment
    before = call(s, "state")
    bad = tmp_path / "broken.tif"
    bad.write_text("not an image")
    assert not s.invoke("open_image", {"path": str(bad), "reset_calibration": True})["ok"]
    assert call(s, "state") == before


def test_known_poni_dimensions_in_both_loading_orders(experiment, tmp_path):
    s = experiment
    poni = tmp_path / "known.poni"
    poni.write_text('poni_version: 2.1\nDetector: Detector\nDetector_config: {"pixel1": 0.000172, "pixel2": 0.000172, "max_shape": [200, 300]}\nDistance: 0.2\nPoni1: 0.01\nPoni2: 0.02\nRot1: 0\nRot2: 0\nRot3: 0\nWavelength: 4e-11\n')
    before = call(s, "state")
    rejected = s.invoke("open_calibration", {"path": str(poni)})
    assert not rejected["ok"] and "dimensions" in rejected["error"]
    assert call(s, "state") == before
    fresh = DesktopSession(engine=s._engine.id)
    try:
        call(fresh, "open_calibration", path=str(poni))
        result = call(fresh, "open_image", path=str(tmp_path / "image_001.tif"))
        assert result["imageChange"]["previousShape"] == [200, 300]
        assert not call(fresh, "state")["state"]["hasImage"]
    finally:
        fresh.close()


def test_autoprocess_stops_without_replacing_session(experiment, tmp_path, monkeypatch):
    s = experiment
    call(s, "integration_autoprocess", enabled=True, directory=str(tmp_path))
    before = call(s, "state")["state"]
    monkeypatch.setattr(s._integration_file_watcher, "poll_once", lambda: None)
    s._integration_incoming.append(str(tmp_path / "image_002.tif"))
    result = call(s, "integration_autoprocess_poll")
    state = result["state"]
    assert not state["integration"]["autoProcess"]
    assert "dimensions changed" in state["integration"]["autoProcessError"]
    assert state["imagePath"] == before["imagePath"]
    assert state["geometry"] == before["geometry"]
    assert state["maskedPixels"] == before["maskedPixels"]
