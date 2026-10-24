"""Exercise signing failure paths without certificates, Apple services or macOS."""

import base64
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("signing", Path(__file__).with_name("signing.py"))
signing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(signing)

TEAM = "ABCD123456"
FINGERPRINT = "A" * 40
DETAILS = (f"Authority=Developer ID Application: Example ({TEAM})\n"
           f"TeamIdentifier={TEAM}\nflags=0x10000(runtime)\nTimestamp=Oct 24, 2026\n")


class SigningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.root)
        env = {
            "RUNNER_TEMP": str(self.root), "GITHUB_ENV": str(self.root / "env"),
            "MACOS_CERTIFICATE_P12_BASE64": base64.b64encode(b"test p12").decode(),
            "MACOS_CERTIFICATE_PASSWORD": "test-p12-password",
            "APPLE_ID": "test@example.org", "APPLE_TEAM_ID": TEAM,
            "APPLE_APP_SPECIFIC_PASSWORD": "test-apple-password",
            "DIOPTAS_SIGNING_KEYCHAIN": str(self.root / "signing.keychain-db"),
            "DIOPTAS_CODESIGN_IDENTITY": FINGERPRINT, "DIOPTAS_APPLE_TEAM_ID": TEAM,
        }
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, env, clear=True).start()

    def test_missing_secret_stops_before_import(self):
        del os.environ["APPLE_APP_SPECIFIC_PASSWORD"]
        with patch.object(signing, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "APPLE_APP_SPECIFIC_PASSWORD"):
                signing.setup()
        run.assert_not_called()
        self.assertFalse(signing.signing_dir().exists())

    def setup_with_identity(self, certificate_name):
        def response(*args, **kwargs):
            if args[:2] == ("security", "list-keychains") and "-s" not in args:
                return '"/Users/runner/Library/Keychains/login.keychain-db"\n'
            if args[:2] == ("security", "find-identity"):
                return f'  1) {FINGERPRINT} "{certificate_name}"\n'
            return ""
        return patch.object(signing, "run", side_effect=response)

    def test_setup_selects_matching_developer_id_and_removes_p12(self):
        with self.setup_with_identity(f"Developer ID Application: Example ({TEAM})"):
            signing.setup()
        env = (self.root / "env").read_text()
        self.assertIn(f"DIOPTAS_CODESIGN_IDENTITY={FINGERPRINT}", env)
        self.assertNotIn("password", env)
        self.assertFalse((signing.signing_dir() / "certificate.p12").exists())

    def test_development_or_wrong_team_certificate_is_rejected(self):
        for name in (f"Apple Development: Example ({TEAM})",
                     "Developer ID Application: Example (WRONG12345)"):
            with self.subTest(name=name):
                with self.setup_with_identity(name):
                    with self.assertRaisesRegex(RuntimeError, "Developer ID Application"):
                        signing.setup()
                    self.assertFalse((signing.signing_dir() / "certificate.p12").exists())
                    signing.cleanup()
                self.assertFalse((self.root / "env").exists())

    def test_cleanup_removes_credentials_even_if_search_list_restore_fails(self):
        directory = signing.signing_dir()
        directory.mkdir()
        (directory / "original-keychains.json").write_text('["login.keychain-db"]')
        (directory / "signing.keychain-db").touch()
        with patch.object(signing, "run", side_effect=[RuntimeError("restore failed"), ""]) as run:
            with self.assertRaisesRegex(RuntimeError, "restore failed"):
                signing.cleanup()
        self.assertEqual(run.call_args_list[-1].args[:2], ("security", "delete-keychain"))
        self.assertFalse(directory.exists())

    def test_tool_failure_does_not_include_password_in_error(self):
        with patch.object(signing.subprocess, "run", return_value=subprocess.CompletedProcess(
            [], 1, "", "import failed",
        )):
            with self.assertRaises(RuntimeError) as raised:
                signing.run("security", "import", "certificate.p12", "-P", "private-password",
                            capture=True)
        self.assertNotIn("private-password", str(raised.exception))

    def test_invalid_signatures_are_rejected(self):
        for details in (DETAILS.replace("runtime", "adhoc"),
                        DETAILS.replace(TEAM, "WRONG12345"),
                        DETAILS.replace("Timestamp=", "Signed Time=")):
            with self.subTest(details=details), patch.object(signing, "run"), patch.object(
                signing.subprocess, "run",
                return_value=subprocess.CompletedProcess([], 0, "", details),
            ):
                with self.assertRaisesRegex(RuntimeError, "timestamped Developer ID"):
                    signing.verify_app(Path("Dioptas.app"))

    def test_accepted_app_is_stapled_and_gatekeeper_checked(self):
        signing.signing_dir().mkdir()
        result = subprocess.CompletedProcess([], 0, json.dumps({"id": "test-id", "status": "Accepted"}), "")
        with patch.object(signing, "verify_app") as verify, patch.object(signing, "run") as run, patch.object(
            signing.subprocess, "run", return_value=result,
        ):
            signing.notarize(Path("Dioptas.app"))
        self.assertEqual(verify.call_count, 2)
        calls = [call.args for call in run.call_args_list]
        self.assertIn(("xcrun", "stapler", "staple", "Dioptas.app"), calls)
        self.assertIn(("xcrun", "stapler", "validate", "Dioptas.app"), calls)
        self.assertEqual(calls[-1][0], "spctl")

    def test_accepted_dmg_is_signed_before_submission(self):
        events = []

        def run(*args, **kwargs):
            events.append(args)

        def submit(*args, **kwargs):
            events.append(("submit",))
            return subprocess.CompletedProcess([], 0, '{"id":"test-id","status":"Accepted"}', "")

        with patch.object(signing, "run", side_effect=run), patch.object(
            signing.subprocess, "run", side_effect=submit,
        ):
            signing.notarize(Path("Dioptas.dmg"))
        self.assertEqual(events[0][:3], ("codesign", "--force", "--timestamp"))
        self.assertLess(events.index(("submit",)),
                        events.index(("xcrun", "stapler", "staple", "Dioptas.dmg")))
        self.assertIn("context:primary-signature", events[-1])

    def test_rejection_timeout_and_malformed_response_never_staple(self):
        cases = [(0, '{"id":"test-id","status":"Invalid"}'),
                 (1, '{"id":"test-id","status":"In Progress"}'), (1, "")]
        for code, response in cases:
            with self.subTest(response=response), patch.object(signing, "run") as run, patch.object(
                signing.subprocess, "run",
                return_value=subprocess.CompletedProcess([], code, response, "test stderr"),
            ):
                with self.assertRaises(RuntimeError):
                    signing.notarize(Path("Dioptas.dmg"))
                calls = [call.args for call in run.call_args_list]
                self.assertFalse(any(call[:2] == ("xcrun", "stapler") for call in calls))
                self.assertFalse(any(call[0] == "spctl" for call in calls))
                self.assertEqual(Path("dist/notarization/Dioptas.dmg-submission.json").read_text(), response)


if __name__ == "__main__":
    unittest.main()
