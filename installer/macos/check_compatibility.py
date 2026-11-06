"""Verify that every Mach-O image in an app supports its declared macOS floor."""

import argparse
from pathlib import Path
import plistlib
import re
import subprocess


MACHO_MAGICS = {
    b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xce",
    b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca", b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca",
}


def version(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d+(?:\.\d+){0,2}", value):
        raise ValueError(f"Invalid macOS deployment target: {value!r}")
    return tuple((list(map(int, value.split("."))) + [0, 0, 0])[:3])


def minimum_versions(output):
    minima = []
    for block in re.split(r"(?m)^Load command \d+\s*$", output):
        if re.search(r"\bcmd LC_BUILD_VERSION\b", block):
            if not re.search(r"(?im)^\s*platform\s+(?:1|MACOS)\s*$", block):
                continue
            match = re.search(r"(?m)^\s*minos\s+([\d.]+)\s*$", block)
        elif re.search(r"\bcmd LC_VERSION_MIN_MACOSX\b", block):
            match = re.search(r"(?m)^\s*version\s+([\d.]+)\s*$", block)
        else:
            continue
        if match:
            minima.append(match[1])
    return minima


def check_app(app, target):
    app = Path(app)
    target_version = version(target)
    info = plistlib.loads((app / "Contents/Info.plist").read_bytes())
    if version(info.get("LSMinimumSystemVersion")) != target_version:
        raise RuntimeError(f"App minimum macOS must be declared as {target}")

    checked = 0
    seen = set()
    failures = []
    for path in app.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        stat = path.stat()
        identity = stat.st_dev, stat.st_ino
        if identity in seen:
            continue
        seen.add(identity)
        with path.open("rb") as stream:
            if stream.read(4) not in MACHO_MAGICS:
                continue
        output = subprocess.check_output(["otool", "-l", str(path)], text=True)
        minima = minimum_versions(output)
        if not minima:
            raise RuntimeError(f"Cannot determine macOS minimum for {path}")
        checked += len(minima)
        for minimum in minima:
            if version(minimum) > target_version:
                failures.append(f"{path.relative_to(app)} requires macOS {minimum}")
    if not checked:
        raise RuntimeError("No Mach-O images found in the app")
    if failures:
        raise RuntimeError("Bundled libraries exceed the macOS target:\n" + "\n".join(failures))
    return checked


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app", type=Path)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    count = check_app(args.app, args.target)
    print(f"Verified {count} Mach-O architecture records for macOS {args.target}")


if __name__ == "__main__":
    main()
