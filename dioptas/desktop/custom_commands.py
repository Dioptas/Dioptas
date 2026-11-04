# SPDX-License-Identifier: MIT
"""User-defined external actions, independent of scientific processing.

Arguments are passed directly to a program, never interpolated into a shell.
Only explicit button presses launch processes; projects cannot install actions.
"""

from copy import deepcopy
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import threading
import uuid


FIELDS = {
    "image_path", "image_name", "image_directory", "frame_index", "frame_number",
    "dataset", "calibration_path", "project_path", "wavelength_angstrom",
}
TOKEN = re.compile(r"\{([a-z_][a-z_0-9]*)\}")
ICONS = {
    "terminal", "script", "file-search", "folder", "target", "position",
    "controls", "database", "plot", "camera", "send", "tools",
    "play", "stop", "pause", "restart", "refresh", "lightning",
    "workflow", "calculator", "processor", "scan", "focus", "ruler",
    "gauge", "temperature", "magnet", "microscope", "atom", "flask",
    "layers", "image", "document", "save", "download", "upload", "copy",
    "clipboard", "search", "filter", "globe", "link", "external-link",
    "swap", "compass", "map-pin", "clock", "star",
    "arrow-left", "arrow-right", "arrow-up", "arrow-down", "arrow-up-left",
    "arrow-up-right", "arrow-down-left", "arrow-down-right", "arrow-up-down",
}


def settings_path():
    override = os.environ.get("DIOPTAS_CUSTOM_COMMANDS_FILE")
    return Path(override).expanduser() if override else Path.home() / ".Dioptas" / "desktop-custom-commands.json"


def validate_command(command):
    if not isinstance(command, dict):
        raise ValueError("A custom action must be an object.")
    name, program = command.get("name", "").strip(), command.get("program", "").strip()
    arguments = command.get("arguments", [])
    if not name or len(name) > 80:
        raise ValueError("Give the button a name (up to 80 characters).")
    if not program or "\0" in program:
        raise ValueError("Enter a program or executable script path.")
    if not isinstance(arguments, list) or len(arguments) > 100 or any(
        not isinstance(arg, str) or "\0" in arg for arg in arguments
    ):
        raise ValueError("Provide up to 100 text arguments.")
    for argument in arguments:
        for field in TOKEN.findall(argument):
            if field not in FIELDS:
                raise ValueError(f"Unknown action input: {{{field}}}.")
    enabled = command.get("enabled", True)
    if not isinstance(enabled, bool):
        raise ValueError("Enabled must be a boolean.")
    icon = command.get("icon", "terminal")
    if not isinstance(icon, str) or icon not in ICONS:
        raise ValueError("Choose an available action icon.")
    identifier = command.get("id") or uuid.uuid4().hex
    if not isinstance(identifier, str) or not identifier or len(identifier) > 100:
        raise ValueError("Invalid command ID.")
    return dict(id=identifier, name=name, program=program, arguments=arguments.copy(), enabled=enabled, icon=icon)


def expanded_arguments(command, context):
    def replace(match):
        field = match[1]
        value = context.get(field)
        if value is None or value == "":
            raise ValueError(f"{field.replace('_', ' ').capitalize()} is unavailable for the current image or session.")
        return str(value)
    return [TOKEN.sub(replace, argument) for argument in command["arguments"]]


class CustomCommands:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else settings_path()
        self._runs = {}
        self._lock = threading.Lock()

    def commands(self):
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if payload.get("version") != 1 or not isinstance(payload.get("commands"), list):
                raise ValueError("Unsupported custom-action settings.")
            commands = [validate_command(item) for item in payload["commands"]]
            if len({item["id"] for item in commands}) != len(commands):
                raise ValueError("Duplicate custom-action IDs.")
            return commands
        except (ValueError, TypeError, AttributeError) as error:
            raise ValueError(f"Cannot read custom actions: {error}") from error

    def _write(self, commands):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic replacement preserves the previous settings if writing fails.
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                json.dump({"version": 1, "commands": commands}, stream, indent=2)
                stream.write("\n")
            temporary.replace(self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def save(self, command):
        command = validate_command(command)
        commands = self.commands()
        for index, existing in enumerate(commands):
            if existing["id"] == command["id"]:
                commands[index] = command
                break
        else:
            commands.append(command)
        self._write(commands)

    def delete(self, identifier):
        with self._lock:
            if self._runs.get(identifier, {}).get("running"):
                raise ValueError("Wait for this action to finish before deleting it.")
        self._write([item for item in self.commands() if item["id"] != identifier])

    def run(self, identifier, context):
        command = next((item for item in self.commands() if item["id"] == identifier), None)
        if command is None or not command["enabled"]:
            raise ValueError("Choose an enabled custom action.")
        args = [os.path.expanduser(command["program"]), *expanded_arguments(command, context)]
        with self._lock:
            if self._runs.get(identifier, {}).get("running"):
                raise ValueError("This action is already running.")
            process = subprocess.Popen(
                args, shell=False, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                start_new_session=os.name != "nt",
            )
            run = dict(running=True, exitCode=None, output="", name=command["name"], arguments=args)
            self._runs[identifier] = run

        def collect():
            output = b""
            try:
                with process.stdout:
                    while chunk := os.read(process.stdout.fileno(), 4096):
                        output = (output + chunk)[-16384:]
                        with self._lock:
                            run["output"] = output.decode("utf-8", errors="replace")
            finally:
                code = process.wait()
                with self._lock:
                    run.update(running=False, exitCode=code)

        # Output is drained off the scientific worker and capped at 16 KiB.
        threading.Thread(target=collect, name="dioptas-custom-command", daemon=True).start()

    def snapshot(self):
        with self._lock:
            return deepcopy(self._runs)


class CustomCommandWorkflow:
    def _custom_command_context(self):
        image = self.configuration.img_model
        calibration = self.configuration.calibration_model
        path = str(image.filename) if self._has_image and image.filename else None
        return {
            "image_path": path,
            "image_name": Path(path).name if path else None,
            "image_directory": str(Path(path).parent) if path else None,
            "frame_index": int(image.series_pos) - 1 if path else None,
            "frame_number": int(image.series_pos) if path else None,
            "dataset": image.selected_source if path else None,
            "calibration_path": str(calibration.filename) if calibration.filename else None,
            "project_path": self._project,
            "wavelength_angstrom": float(calibration.pattern_geometry.wavelength) * 1e10
            if calibration.is_calibrated else None,
        }

    def _custom_command(self, operation="list", command=None, identifier=None):
        if operation == "save":
            self._custom_commands.save(command)
        elif operation == "delete":
            self._custom_commands.delete(identifier)
        elif operation == "run":
            self._custom_commands.run(identifier, self._custom_command_context())
        elif operation != "list":
            raise ValueError("Unknown custom-action operation.")
        return {
            "customCommands": self._custom_commands.commands(),
            "customCommandRuns": self._custom_commands.snapshot(),
            "customCommandContext": self._custom_command_context(),
        }
