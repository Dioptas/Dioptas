"""External actions preserve argument boundaries and leave processing responsive."""

import json
from pathlib import Path
import sys
import time

import pytest

from dioptas.desktop.custom_commands import CustomCommands
from dioptas.desktop.session import DesktopSession


def wait_for_command(commands, identifier):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        result = commands.snapshot()[identifier]
        if not result["running"]:
            return result
        time.sleep(0.01)
    pytest.fail("Custom command did not finish")


def test_program_receives_literal_paths_frame_and_flags_without_shell(tmp_path):
    script = tmp_path / "lookup tool.py"
    script.write_text("import sys,json; print(json.dumps(sys.argv[1:]))")
    commands = CustomCommands(tmp_path / "settings.json")
    commands.save(dict(id="lookup", name="Motor positions", program=sys.executable, icon="microscope",
                       arguments=[str(script), "--image={image_path}", "{frame_index}", "$(touch should-not-exist); & literal"]))
    context = {"image_path": str(tmp_path / 'scan $special; "name".h5'), "frame_index": 0}
    commands.run("lookup", context)
    result = wait_for_command(commands, "lookup")
    assert result["exitCode"] == 0
    assert json.loads(result["output"]) == [f'--image={context["image_path"]}', "0", "$(touch should-not-exist); & literal"]
    assert not (tmp_path / "should-not-exist").exists()
    assert CustomCommands(commands.path).commands()[0]["name"] == "Motor positions"
    assert CustomCommands(commands.path).commands()[0]["icon"] == "microscope"


def test_validation_preserves_saved_commands_and_rejects_unavailable_inputs(tmp_path):
    commands = CustomCommands(tmp_path / "settings.json")
    command = dict(id="lookup", name="Lookup", program=sys.executable, arguments=["{calibration_path}"])
    commands.save(command)
    assert commands.commands()[0]["icon"] == "terminal"
    saved = commands.path.read_bytes()
    with pytest.raises(ValueError, match="available action icon"):
        commands.save({**command, "icon": "unknown"})
    assert commands.path.read_bytes() == saved
    with pytest.raises(ValueError, match="Unknown action input"):
        commands.save({**command, "arguments": ["{missing}"]})
    assert commands.path.read_bytes() == saved
    with pytest.raises(ValueError, match="Calibration path is unavailable"):
        commands.run("lookup", {"calibration_path": None})
    assert commands.snapshot() == {}
    commands.save({**command, "enabled": False})
    with pytest.raises(ValueError, match="enabled"):
        commands.run("lookup", {})
    commands.delete("lookup")
    assert CustomCommands(commands.path).commands() == []


def test_subprocess_is_async_output_is_bounded_and_failure_is_reported(tmp_path):
    commands = CustomCommands(tmp_path / "settings.json")
    commands.save(dict(id="slow", name="Slow lookup", program=sys.executable,
                       arguments=["-c", "import time,sys; print('x'*100000); time.sleep(0.3); print('beamline error',file=sys.stderr); sys.exit(7)"]))
    commands.run("slow", {})
    assert commands.snapshot()["slow"]["running"]
    with pytest.raises(ValueError, match="already running"):
        commands.run("slow", {})
    with pytest.raises(ValueError, match="finish"):
        commands.delete("slow")
    result = wait_for_command(commands, "slow")
    assert result["exitCode"] == 7
    assert len(result["output"]) <= 16384
    assert "beamline error" in result["output"]


def test_session_context_has_real_paths_and_explicit_frame_conventions(tmp_path, monkeypatch):
    monkeypatch.setenv("DIOPTAS_CUSTOM_COMMANDS_FILE", str(tmp_path / "commands.json"))
    session = DesktopSession()
    initial = session.invoke("custom_command")
    assert initial["ok"]
    assert initial["customCommandContext"]["image_path"] is None
    assert initial["customCommandContext"]["wavelength_angstrom"] is None
    assert session.invoke("example")["ok"]
    image = session.configuration.img_model
    image.series_pos = 3
    image.selected_source = "/entry/data"
    result = session.invoke("custom_command")
    context = result["customCommandContext"]
    assert Path(context["image_path"]).is_file()
    assert context["image_name"] == Path(context["image_path"]).name
    assert context["frame_index"] == 2
    assert context["frame_number"] == 3
    assert context["dataset"] == "/entry/data"
    # The example supplies starting values; it has no loaded/fitted geometry.
    assert context["calibration_path"] is None
    calibration_path = session.example_paths()[1]
    assert session.invoke("open_calibration", {"path": str(calibration_path)})["ok"]
    context = session.invoke("custom_command")["customCommandContext"]
    assert context["calibration_path"] == str(calibration_path)
    assert context["wavelength_angstrom"] == pytest.approx(0.4066)
    history_before = (session._model.history.can_undo, session._model.history.undo_label)
    assert session.invoke("custom_command", {"operation": "save", "command": dict(
        id="lookup", name="Lookup", program=sys.executable,
        arguments=["-c", "import time; time.sleep(0.3)"]
    )})["ok"]
    assert session.invoke("custom_command", {"operation": "run", "identifier": "lookup"})["ok"]
    assert session.invoke("state")["ok"]
    wait_for_command(session._custom_commands, "lookup")
    assert (session._model.history.can_undo, session._model.history.undo_label) == history_before


def test_invalid_settings_are_reported_and_never_overwritten(tmp_path):
    path = tmp_path / "commands.json"
    path.write_text('{"version": 27, "commands": []}')
    commands = CustomCommands(path)
    with pytest.raises(ValueError, match="Cannot read"):
        commands.save(dict(name="New", program="echo", arguments=[]))
    assert json.loads(path.read_text())["version"] == 27
