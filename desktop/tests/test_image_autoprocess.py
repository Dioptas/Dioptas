"""Integration file entry and incoming acquisition use the desktop worker/models."""
import os
from pathlib import Path
import shutil

import numpy as np
import pytest

from dioptas.desktop.session import DesktopSession

DATA = Path(__file__).resolve().parents[2] / "dioptas/tests/data"


def call(session, command, **payload):
    result = session.invoke(command, payload)
    assert result["ok"], result.get("error")
    return result


def incoming(folder, name):
    path = folder / name
    shutil.copyfile(DATA / "CeO2_Pilatus1M.tif", path)
    os.utime(path, (1000, 1000))
    return path


@pytest.fixture
def loaded():
    session = DesktopSession()
    call(session, "example")
    call(session, "open_calibration", path=str(DATA / "CeO2_Pilatus1M.poni"))
    call(session, "integration_settings", bins=120, cake_bins=20)
    return session


def test_entered_filename_loads_relative_to_selected_folder(loaded, tmp_path):
    path = incoming(tmp_path, "measurement.tif")
    geometry = call(loaded, "state")["state"]["geometry"]
    call(loaded, "integration_image_directory", path=str(tmp_path))
    result = call(loaded, "open_image", path=path.name, directory=str(tmp_path))
    assert result["state"]["imagePath"] == str(path)
    assert result["state"]["integration"]["imageDirectory"] == str(tmp_path)
    assert result["state"]["geometry"] == geometry
    assert len(result["pattern"]["x"]) > 10
    assert not loaded.invoke("open_image", {"path": "missing.tif", "directory": str(tmp_path)})["ok"]
    assert call(loaded, "state")["state"]["imagePath"] == str(path)
    assert not loaded.invoke("integration_image_directory", {"path": str(tmp_path / "missing")})["ok"]
    assert call(loaded, "state")["state"]["integration"]["imageDirectory"] == str(tmp_path)


def test_directory_chooser_and_cancel_leave_image_in_place(tmp_path):
    choices = iter([str(tmp_path), None])
    session = DesktopSession(choose_file=lambda kind, save: next(choices))
    first = call(session, "integration_image_directory")
    assert first["state"]["integration"]["imageDirectory"] == str(tmp_path)
    assert not first["state"]["hasImage"]
    assert call(session, "integration_image_directory")["cancelled"]
    assert call(session, "state")["state"]["integration"]["imageDirectory"] == str(tmp_path)


def test_autoprocess_waits_for_stable_files_and_integrates_every_new_image(loaded, tmp_path):
    incoming(tmp_path, "already_here.tif")
    original = call(loaded, "state")
    call(loaded, "integration_image_directory", path=str(tmp_path))
    call(loaded, "integration_autoprocess", enabled=True)
    assert not loaded._integration_file_watcher.active  # No extra processing thread.
    assert call(loaded, "integration_autoprocess_poll") == {"ok": True}
    placeholder = tmp_path / "a_new.tif"
    placeholder.touch()
    for _ in range(2):
        assert call(loaded, "integration_autoprocess_poll") == {"ok": True}
    incoming(tmp_path, placeholder.name)
    incoming(tmp_path, "b_new.tif")
    (tmp_path / "notes.txt").write_text("Not a detector image")
    assert call(loaded, "integration_autoprocess_poll") == {"ok": True}
    first = call(loaded, "integration_autoprocess_poll")
    second = call(loaded, "integration_autoprocess_poll")
    assert [first["state"]["imageName"], second["state"]["imageName"]] == ["a_new.tif", "b_new.tif"]
    assert first["state"]["geometry"] == original["state"]["geometry"]
    np.testing.assert_allclose(first["pattern"]["y"], original["pattern"]["y"])
    assert call(loaded, "integration_autoprocess_poll") == {"ok": True}
    call(loaded, "integration_autoprocess", enabled=False)
    incoming(tmp_path, "after_disable.tif")
    for _ in range(3):
        assert call(loaded, "integration_autoprocess_poll") == {"ok": True}
    assert call(loaded, "state")["state"]["imageName"] == "b_new.tif"


def test_growing_and_bad_files_do_not_block_following_images(loaded, tmp_path):
    call(loaded, "integration_image_directory", path=str(tmp_path))
    call(loaded, "integration_autoprocess", enabled=True)
    bad = tmp_path / "a_bad.tif"
    bad.write_bytes(b"partial")
    call(loaded, "integration_autoprocess_poll")
    bad.write_bytes(b"growing partial")
    os.utime(bad, (1000, 1000))
    assert call(loaded, "integration_autoprocess_poll") == {"ok": True}
    incoming(tmp_path, "b_good.tif")
    failure = call(loaded, "integration_autoprocess_poll")
    assert "a_bad.tif" in failure["state"]["integration"]["autoProcessError"]
    assert failure["state"]["integration"]["autoProcess"]
    result = call(loaded, "integration_autoprocess_poll")
    assert result["state"]["imageName"] == "b_good.tif"
    assert not result["state"]["integration"]["autoProcessError"]


def test_switching_folders_drops_old_queue_and_baselines_existing_files(loaded, tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir(); second.mkdir()
    call(loaded, "integration_image_directory", path=str(first))
    call(loaded, "integration_autoprocess", enabled=True)
    incoming(first, "a.tif"); incoming(first, "b.tif")
    call(loaded, "integration_autoprocess_poll")
    assert call(loaded, "integration_autoprocess_poll")["state"]["imageName"] == "a.tif"
    incoming(second, "existing.tif")
    call(loaded, "integration_image_directory", path=str(second))
    for _ in range(2):
        assert call(loaded, "integration_autoprocess_poll") == {"ok": True}
    incoming(second, "new.tif")
    call(loaded, "integration_autoprocess_poll")
    assert call(loaded, "integration_autoprocess_poll")["state"]["imagePath"] == str(second / "new.tif")


def test_autoprocess_uses_autocreate_and_stays_off_after_project_reload(loaded, tmp_path):
    output = tmp_path / "patterns"
    output.mkdir()
    call(loaded, "integration_output_directory", path=str(output))
    call(loaded, "integration_settings", auto_save=True, formats=[".xy"])
    call(loaded, "integration_image_directory", path=str(tmp_path))
    call(loaded, "integration_autoprocess", enabled=True)
    incoming(tmp_path, "acquisition.tif")
    call(loaded, "integration_autoprocess_poll")
    call(loaded, "integration_autoprocess_poll")
    assert (output / "acquisition.xy").is_file()
    project = tmp_path / "acquisition.dio"
    call(loaded, "save_project", path=str(project))
    reloaded = call(loaded, "open_project", path=str(project))
    assert not reloaded["state"]["integration"]["autoProcess"]
    assert call(loaded, "integration_autoprocess_poll") == {"ok": True}
    call(loaded, "integration_autoprocess", enabled=True)
    assert not call(loaded, "example")["state"]["integration"]["autoProcess"]


def test_folder_can_be_watched_before_loading_first_image(tmp_path):
    session = DesktopSession()
    call(session, "integration_autoprocess", enabled=True, directory=str(tmp_path))
    incoming(tmp_path, "first.tif")
    call(session, "integration_autoprocess_poll")
    result = call(session, "integration_autoprocess_poll")
    assert result["state"]["imageName"] == "first.tif"
    assert result["state"]["hasImage"]
