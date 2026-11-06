"""Test deployment-target guards without a macOS host or compiler tools."""

import importlib.util
from pathlib import Path
import plistlib
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("compatibility", Path(__file__).with_name("check_compatibility.py"))
compatibility = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compatibility)


def build_version(minimum):
    return f"Load command 0\n      cmd LC_BUILD_VERSION\n platform 1\n    minos {minimum}\n      sdk 26.0\n"


class CompatibilityTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.app = Path(temp.name) / "Dioptas.app"
        (self.app / "Contents/Frameworks").mkdir(parents=True)
        self.info = self.app / "Contents/Info.plist"
        self.info.write_bytes(plistlib.dumps({"LSMinimumSystemVersion": "14.0"}))
        (self.app / "Contents/Frameworks/libomp.dylib").write_bytes(b"\xcf\xfa\xed\xfe")

    def test_rejects_newer_runtime_even_with_correct_app_metadata(self):
        with patch.object(compatibility.subprocess, "check_output", return_value=build_version("26.0")):
            with self.assertRaisesRegex(RuntimeError, "libomp.dylib requires macOS 26.0"):
                compatibility.check_app(self.app, "14.0")

    def test_accepts_compatible_library(self):
        with patch.object(compatibility.subprocess, "check_output", return_value=build_version("14.0")):
            self.assertEqual(compatibility.check_app(self.app, "14.0"), 1)

    def test_checks_every_architecture(self):
        output = build_version("14.0") + build_version("15.0")
        with patch.object(compatibility.subprocess, "check_output", return_value=output):
            with self.assertRaisesRegex(RuntimeError, "requires macOS 15.0"):
                compatibility.check_app(self.app, "14.0")

    def test_reads_older_macos_load_commands(self):
        output = "Load command 0\n      cmd LC_VERSION_MIN_MACOSX\n  version 11.0\n      sdk 14.0\n"
        self.assertEqual(compatibility.minimum_versions(output), ["11.0"])

    def test_missing_deployment_metadata_cannot_pass(self):
        self.info.write_bytes(plistlib.dumps({}))
        with self.assertRaises(ValueError):
            compatibility.check_app(self.app, "14.0")

    def test_unknown_binary_minimum_cannot_pass(self):
        with patch.object(compatibility.subprocess, "check_output", return_value=""):
            with self.assertRaisesRegex(RuntimeError, "Cannot determine macOS minimum"):
                compatibility.check_app(self.app, "14.0")

    def test_empty_bundle_cannot_pass(self):
        (self.app / "Contents/Frameworks/libomp.dylib").unlink()
        with self.assertRaisesRegex(RuntimeError, "No Mach-O images"):
            compatibility.check_app(self.app, "14.0")
