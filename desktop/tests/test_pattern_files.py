"""Qt-style Pattern file navigation uses the existing PatternModel and writers."""
import os
from pathlib import Path

import numpy as np
import pytest

from dioptas.desktop.session import DesktopSession

DATA = Path(__file__).resolve().parents[2] / "dioptas/tests/data"


def call(session, command, **payload):
    result = session.invoke(command, payload)
    assert result["ok"], result.get("error")
    return result


def pattern(folder, number, mtime):
    path = folder / f"scan_{number:03}.xy"
    np.savetxt(path, np.column_stack([np.arange(1, 11), np.arange(1, 11) * number]))
    os.utime(path, (mtime, mtime))
    return path


def test_pattern_filename_directory_and_invalid_entry(tmp_path):
    session = DesktopSession()
    path = pattern(tmp_path, 1, 1000)
    result = call(session, "integration_open_pattern", path=path.name, directory=str(tmp_path))
    assert result["state"]["integration"]["patternPath"] == str(path)
    assert result["state"]["integration"]["outputDirectory"] == str(tmp_path)
    assert result["pattern"]["y"] == list(range(1, 11))
    for command, payload in [
        ("integration_open_pattern", {"path": "absent.xy", "directory": str(tmp_path)}),
        ("integration_output_directory", {"path": str(tmp_path / "absent")}),
    ]:
        assert not session.invoke(command, payload)["ok"]
        after = call(session, "state")
        assert after["pattern"] == result["pattern"]
        assert after["state"]["integration"]["patternPath"] == str(path)


def test_pattern_real_step_and_independent_number_time_order(tmp_path, monkeypatch):
    paths = [pattern(tmp_path, i, mtime) for i, mtime in [(1, 1000), (2, 3000), (3, 2000)]]
    real_ctime = os.path.getctime
    times = {str(paths[0]): 1000, str(paths[1]): 3000, str(paths[2]): 2000}
    monkeypatch.setattr(os.path, "getctime", lambda path: times.get(str(path), real_ctime(path)))
    session = DesktopSession()
    call(session, "integration_open_pattern", path=str(paths[0]))
    result = call(session, "integration_open_pattern", direction=1, step=2)
    assert result["state"]["integration"]["patternPath"] == str(paths[2])
    result = call(session, "integration_open_pattern", direction=-1, step=2)
    assert result["state"]["integration"]["patternPath"] == str(paths[0])
    call(session, "integration_pattern_navigation", mode="time")
    result = call(session, "integration_open_pattern", direction=1)
    assert result["state"]["integration"]["patternPath"] == str(paths[2])
    result = call(session, "integration_open_pattern", direction=1)
    assert result["state"]["integration"]["patternPath"] == str(paths[1])
    assert result["state"]["integration"]["fileIteration"] == "number"
    assert result["state"]["integration"]["patternFileIteration"] == "time"


@pytest.mark.parametrize("payload", [{"direction": 0}, {"direction": 1, "step": 0}, {"direction": 1, "step": 1.5}])
def test_invalid_pattern_navigation_preserves_loaded_curve(tmp_path, payload):
    session = DesktopSession()
    path = pattern(tmp_path, 1, 1000)
    before = call(session, "integration_open_pattern", path=str(path))
    assert not session.invoke("integration_open_pattern", payload)["ok"]
    after = call(session, "state")
    assert after["pattern"] == before["pattern"]
    assert not session.invoke("integration_pattern_navigation", {"mode": "invalid"})["ok"]


def test_autocreate_checkbox_and_formats_preserve_loaded_pattern_and_write_images(tmp_path):
    session = DesktopSession()
    path = pattern(tmp_path, 1, 1000)
    before = call(session, "integration_open_pattern", path=str(path))
    result = call(session, "integration_autocreate", enabled=True, directory=str(tmp_path))
    assert result["state"]["integration"]["autoSave"]
    assert result["pattern"] == before["pattern"]
    result = call(session, "integration_settings", formats=[".xy", ".chi"])
    assert result["pattern"] == before["pattern"]
    call(session, "open_calibration", path=str(DATA / "CeO2_Pilatus1M.poni"))
    result = call(session, "open_image", path=str(DATA / "CeO2_Pilatus1M.tif"))
    assert (tmp_path / "CeO2_Pilatus1M.xy").is_file()
    assert (tmp_path / "CeO2_Pilatus1M.chi").is_file()
    assert result["state"]["integration"]["patternPath"] == ""
    assert not session.invoke("integration_open_pattern", {"direction": 1})["ok"]
    assert not call(session, "integration_autocreate", enabled=False, directory=str(tmp_path / "invalid edit"))["state"]["integration"]["autoSave"]


def test_pattern_folder_chooser_cancel_preserves_directory(tmp_path):
    choices = iter([str(tmp_path), None])
    session = DesktopSession(choose_file=lambda kind, save: next(choices))
    result = call(session, "integration_output_directory")
    assert result["state"]["integration"]["outputDirectory"] == str(tmp_path)
    assert call(session, "integration_output_directory")["cancelled"]
    assert call(session, "state")["state"]["integration"]["outputDirectory"] == str(tmp_path)
