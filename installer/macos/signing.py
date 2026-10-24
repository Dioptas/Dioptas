"""Developer ID setup and notarization for GitHub-hosted macOS builds.

Uses only the standard library so setup can run before installing dependencies.
Secrets are read from the environment, never from CLI arguments or repository files.
"""

import argparse
import base64
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import shutil
import subprocess
import sys


REQUIRED_SECRETS = (
    "MACOS_CERTIFICATE_P12_BASE64",
    "MACOS_CERTIFICATE_PASSWORD",
    "APPLE_ID",
    "APPLE_TEAM_ID",
    "APPLE_APP_SPECIFIC_PASSWORD",
)
PROFILE = "dioptas-notarization"


def run(*args, capture=False):
    result = subprocess.run(args, text=True, capture_output=capture, check=False)
    if result.returncode:
        if capture and result.stderr:
            print(result.stderr, file=sys.stderr)
        # CalledProcessError includes the entire command, potentially passwords.
        raise RuntimeError(f"{args[0]} {args[1]} failed (exit {result.returncode})")
    return result.stdout if capture else ""


def signing_dir():
    return Path(os.environ["RUNNER_TEMP"]) / "dioptas-macos-signing"


def setup():
    missing = [name for name in REQUIRED_SECRETS if not os.environ.get(name)]
    if missing:
        raise RuntimeError("Missing GitHub Actions secrets: " + ", ".join(missing))
    team = os.environ["APPLE_TEAM_ID"]
    if not re.fullmatch(r"[A-Z0-9]{10}", team):
        raise RuntimeError("APPLE_TEAM_ID must be the 10-character Developer team ID")
    directory = signing_dir()
    directory.mkdir(mode=0o700)
    keychain = str(directory / "signing.keychain-db")
    certificate = directory / "certificate.p12"
    password = secrets.token_hex(32)
    original = shlex.split(run("security", "list-keychains", "-d", "user", capture=True))
    (directory / "original-keychains.json").write_text(json.dumps(original))
    try:
        certificate.write_bytes(base64.b64decode(
            "".join(os.environ["MACOS_CERTIFICATE_P12_BASE64"].split()), validate=True,
        ))
        certificate.chmod(0o600)
        run("security", "create-keychain", "-p", password, keychain)
        run("security", "set-keychain-settings", "-lut", "21600", keychain)
        run("security", "unlock-keychain", "-p", password, keychain)
        run("security", "import", str(certificate), "-P",
            os.environ["MACOS_CERTIFICATE_PASSWORD"], "-k", keychain,
            "-T", "/usr/bin/codesign", "-T", "/usr/bin/security")
        run("security", "set-key-partition-list", "-S", "apple-tool:,apple:,codesign:",
            "-s", "-k", password, keychain)
        run("security", "list-keychains", "-d", "user", "-s", keychain, *original)
        identities = run("security", "find-identity", "-v", "-p", "codesigning",
                         keychain, capture=True)
        matches = re.findall(
            r'\b([A-F0-9]{40}) "Developer ID Application: [^"\n]+ \('
            + re.escape(team) + r'\)"', identities,
        )
        if len(matches) != 1:
            raise RuntimeError(
                "The P12 must contain exactly one valid Developer ID Application "
                "certificate and private key matching APPLE_TEAM_ID"
            )
        run("xcrun", "notarytool", "store-credentials", PROFILE, "--keychain", keychain,
            "--apple-id", os.environ["APPLE_ID"], "--team-id", team,
            "--password", os.environ["APPLE_APP_SPECIFIC_PASSWORD"])
        with open(os.environ["GITHUB_ENV"], "a") as env_file:
            env_file.write(f"DIOPTAS_CODESIGN_IDENTITY={matches[0]}\n")
            env_file.write(f"DIOPTAS_SIGNING_KEYCHAIN={keychain}\n")
            env_file.write(f"DIOPTAS_APPLE_TEAM_ID={team}\n")
            env_file.write("PYINSTALLER_STRICT_BUNDLE_CODESIGN_ERROR=1\n")
    finally:
        certificate.unlink(missing_ok=True)


def cleanup():
    directory = signing_dir()
    if not directory.exists():
        return
    original = directory / "original-keychains.json"
    try:
        if original.exists():
            run("security", "list-keychains", "-d", "user", "-s",
                *json.loads(original.read_text()))
    finally:
        try:
            keychain = directory / "signing.keychain-db"
            if keychain.exists():
                run("security", "delete-keychain", str(keychain))
        finally:
            shutil.rmtree(directory)


def verify_app(app):
    run("codesign", "--verify", "--deep", "--strict", "--verbose=2", str(app))
    # codesign writes display information to stderr even on success.
    result = subprocess.run(["codesign", "--display", "--verbose=4", str(app)],
                            capture_output=True, text=True, check=False)
    details = result.stdout + result.stderr
    team = os.environ["DIOPTAS_APPLE_TEAM_ID"]
    if (result.returncode or f"TeamIdentifier={team}\n" not in details
            or "Authority=Developer ID Application:" not in details
            or not re.search(r"flags=.*\bruntime\b", details)
            or "Timestamp=" not in details):
        raise RuntimeError("App must have a timestamped Developer ID signature with "
                           "hardened runtime and the expected team ID")


def notary_response(arguments, log_path):
    result = subprocess.run(
        ["xcrun", "notarytool", *arguments, "--output-format", "json"],
        capture_output=True, text=True, check=False,
    )
    log_path.write_text(result.stdout)
    log_path.with_suffix(".stderr.txt").write_text(result.stderr)
    # notarytool emits timeout JSON on stderr, with an empty stdout.
    for output in (result.stdout, result.stderr):
        try:
            response = json.loads(output)
        except ValueError:
            continue
        if isinstance(response, dict):
            return result.returncode, response
    raise RuntimeError("notarytool returned no JSON; see notarization logs")


def notarize(path, submission_id=None):
    keychain = os.environ["DIOPTAS_SIGNING_KEYCHAIN"]
    auth = ("--keychain-profile", PROFILE, "--keychain", keychain)
    logs = Path("dist/notarization")
    logs.mkdir(parents=True, exist_ok=True)
    archive = path
    if path.suffix == ".app":
        verify_app(path)
        if not submission_id:
            payloads = Path("dist/notarization-payloads")
            payloads.mkdir(parents=True, exist_ok=True)
            archive = payloads / "Dioptas-signed-unnotarized.zip"
            run("ditto", "-c", "-k", "--keepParent", str(path), str(archive))
    elif path.suffix == ".dmg":
        # A resumed submission must use the original bytes and signature.
        if not submission_id:
            run("codesign", "--force", "--timestamp", "--sign",
                os.environ["DIOPTAS_CODESIGN_IDENTITY"], str(path))
        run("codesign", "--verify", "--strict", str(path))
    else:
        raise RuntimeError("Notarization expects a .app or .dmg")

    if not submission_id:
        code, submission = notary_response(
            ("submit", str(archive), *auth), logs / f"{path.name}-submission.json",
        )
        submission_id = submission.get("id")
        if code or not submission_id:
            raise RuntimeError("Apple upload failed; see notarization logs")
    print(f"Apple submission ID: {submission_id}", flush=True)
    # Save the ID before waiting, so a slow Apple response cannot hide it.
    (logs / f"{path.name}-submission-id.txt").write_text(submission_id + "\n")
    code, result = notary_response(
        ("wait", submission_id, *auth, "--timeout", "90m"),
        logs / f"{path.name}-wait.json",
    )
    status = result.get("status")
    print(f"Notarization: {submission_id} — {status or result.get('message')}", flush=True)
    if code or status != "Accepted":
        if status in ("Invalid", "Rejected"):
            run("xcrun", "notarytool", "log", submission_id, *auth,
                str(logs / f"{path.name}-issues.json"))
            raise RuntimeError("Apple rejected this build; see notarization logs")
        raise RuntimeError(
            f"Notarization has not returned Accepted for {submission_id}; "
            "check Apple status before resubmitting. Signed payloads and logs "
            "are retained in the macos-notarization-recovery artifact."
        )
    run("xcrun", "notarytool", "log", submission_id, *auth,
        str(logs / f"{path.name}-issues.json"))
    run("xcrun", "stapler", "staple", str(path))
    run("xcrun", "stapler", "validate", str(path))
    if path.suffix == ".app":
        verify_app(path)
        run("spctl", "--assess", "--type", "execute", "--verbose=2", str(path))
    else:
        run("spctl", "--assess", "--type", "open", "--context",
            "context:primary-signature", "--verbose=2", str(path))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("setup", "cleanup", "notarize", "verify"))
    parser.add_argument("path", type=Path, nargs="?")
    parser.add_argument("--submission-id", help="Resume an existing submission without uploading or re-signing")
    args = parser.parse_args()
    if args.submission_id and args.command != "notarize":
        parser.error("--submission-id is only valid with notarize")
    if args.command in ("verify", "notarize"):
        if args.path is None or not args.path.exists():
            parser.error("provide an existing app bundle or disk image")
    try:
        if args.command == "setup":
            setup()
        elif args.command == "cleanup":
            cleanup()
        elif args.command == "verify":
            verify_app(args.path)
        else:
            notarize(args.path, args.submission_id)
    except (RuntimeError, ValueError, OSError) as error:
        print(f"::error::{error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
