"""Qt Image-tab actions use real image models without replacing stored batches."""
from pathlib import Path

import numpy as np
from PIL import Image
import pytest

from dioptas.desktop.session import DesktopSession
from dioptas.model.ImgModel import ImgModel


def call(session, command, **args):
    result = session.invoke(command, args)
    assert result["ok"], result
    return result


@pytest.fixture
def images(tmp_path):
    paths = []
    data = np.arange(120, dtype=np.uint16).reshape(10, 12) + 10
    for i in range(3):
        path = tmp_path / f"source_{i}.tif"
        Image.fromarray(data * (i + 1) + i).save(path)
        paths.append(str(path))
    session = DesktopSession()
    call(session, "open_image", path=paths[0])
    return session, paths


@pytest.mark.parametrize("mode", ["add", "average"])
def test_image_modes_match_qt_model_and_keep_stored_batch(images, mode):
    session, paths = images
    call(session, "image_transform", operation="flip_horizontal")
    before = session.configuration.batch_model
    model = ImgModel()
    model.load(paths[0])
    model.flip_img_horizontally()
    for path in paths[1:]:
        model.add(path)
    if mode == "average":
        model._img_data = model._img_data / len(paths)
        model._calculate_img_data()
    state = call(session, "image_batch_mode", mode=mode)["state"]
    assert state["integration"]["imageBatchMode"] == mode
    result = call(session, "open_image", paths=paths, multiple=True)
    np.testing.assert_array_equal(session.configuration.img_model.raw_img_data, model.raw_img_data)
    np.testing.assert_array_equal(session.configuration.img_model.img_data, model.img_data)
    assert session.configuration.batch_model is before
    assert not result.get("batchOpened")


def test_combining_applies_background_once_and_rejects_mismatched_shape(images, tmp_path):
    session, paths = images
    background = tmp_path / "background.tif"
    Image.fromarray(np.ones((10, 12), dtype=np.uint16)).save(background)
    session.configuration.img_model.load_background(str(background))
    call(session, "open_image", paths=paths, batch_mode="add")
    image = session.configuration.img_model
    np.testing.assert_array_equal(image.img_data, image.raw_img_data - 1)
    previous = image.raw_img_data.copy()
    wrong = tmp_path / "wrong.tif"
    Image.fromarray(np.zeros((8, 8), dtype=np.uint16)).save(wrong)
    result = session.invoke("open_image", {"paths": [paths[0], str(wrong)], "batch_mode": "average"})
    assert not result["ok"]
    np.testing.assert_array_equal(image.raw_img_data, previous)


def test_cancellation_preserves_live_image(images, monkeypatch):
    session, paths = images
    previous = session.configuration.img_model.raw_img_data.copy()
    original = ImgModel.add
    def cancel(model, path):
        original(model, path)
        session._cancel_refinement.set()
    monkeypatch.setattr(ImgModel, "add", cancel)
    assert call(session, "open_image", paths=paths, batch_mode="add")["cancelled"]
    np.testing.assert_array_equal(session.configuration.img_model.raw_img_data, previous)


def test_save_uses_qt_tiff_orientation_and_never_overwrites(images, tmp_path):
    session, paths = images
    output = tmp_path / "output"
    output.mkdir()
    before = session.configuration.img_model.raw_img_data.copy()
    result = call(session, "open_image", paths=paths, batch_mode="save", output_directory=str(output))
    assert len(result["savedPaths"]) == 3
    for source, destination in zip(paths, result["savedPaths"]):
        model = ImgModel(); model.load(source)
        np.testing.assert_array_equal(np.asarray(Image.open(destination)), np.flipud(model.img_data.astype(np.int32)))
        assert Path(destination).name == "batch_" + Path(source).stem + ".tiff"
    np.testing.assert_array_equal(session.configuration.img_model.raw_img_data, before)
    assert not session.invoke("open_image", {"paths": paths, "batch_mode": "save", "output_directory": str(output)})["ok"]


def test_single_image_stays_ordinary_and_invalid_mode_is_rejected(images):
    session, paths = images
    call(session, "image_batch_mode", mode="save")
    assert not call(session, "open_image", paths=[paths[1]], multiple=True).get("savedPaths")
    assert not session.invoke("image_batch_mode", {"mode": "unknown"})["ok"]


def test_cancelled_or_failed_save_publishes_no_partial_outputs(images, tmp_path, monkeypatch):
    from dioptas.desktop import image_batch
    session, paths = images
    output = tmp_path / "outputs"
    output.mkdir()
    before = session.configuration.img_model.raw_img_data.copy()
    save = image_batch.save_tiff_data
    def cancel(path, data):
        save(path, data)
        session._cancel_refinement.set()
    monkeypatch.setattr(image_batch, "save_tiff_data", cancel)
    assert call(session, "open_image", paths=paths, batch_mode="save", output_directory=str(output))["cancelled"]
    assert list(output.iterdir()) == []
    monkeypatch.setattr(image_batch, "save_tiff_data", save)
    broken = tmp_path / "broken.tif"
    broken.write_bytes(b"not a detector image")
    result = session.invoke("open_image", {"paths": [paths[0], str(broken)], "batch_mode": "save", "output_directory": str(output)})
    assert not result["ok"]
    assert list(output.iterdir()) == []
    np.testing.assert_array_equal(session.configuration.img_model.raw_img_data, before)
