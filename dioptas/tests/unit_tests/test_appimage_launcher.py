"""Exercise the real AppImage entry point from outside the bundle directory."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.mark.skipif(os.name == "nt", reason="AppImage launcher uses a POSIX shell")
def test_launcher_resolves_bundle_with_spaces_and_preserves_arguments(tmp_path):
    bundle = tmp_path / "Dioptas bundle.AppDir"
    executable = bundle / "usr" / "bin" / "Dioptas"
    executable.parent.mkdir(parents=True)
    executable.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n', encoding="utf-8")
    executable.chmod(0o755)
    launcher = bundle / "AppRun"
    source = Path(__file__).resolve().parents[3] / "installer" / "linux" / "AppRun"
    shutil.copy2(source, launcher)
    result = subprocess.run(
        [str(launcher), "test", "path with spaces"], cwd=tmp_path,
        check=True, capture_output=True, text=True,
    )
    assert result.stdout.splitlines() == ["test", "path with spaces"]
