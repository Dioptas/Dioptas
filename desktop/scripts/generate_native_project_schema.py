"""Reproduce format-2 params defaults for the Rust project adapter (test-time only)."""

import dataclasses
import hashlib
import json
from pathlib import Path
from dioptas.model.state import params
from dioptas.model.util.jcpds import CrystalState

ROOT = Path(__file__).resolve().parents[2]
NAMES = {
    "params": params.ConfigurationParams,
    "img": params.ImgParams,
    "calibration": params.CalibrationParams,
    "mask": params.MaskParams,
    "pattern": params.PatternParams,
    "map": params.MapParams,
    "view": params.ViewParams,
    "phase": params.PhaseParams,
    "crystal": CrystalState,
}


def main():
    import argparse

    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    data = {key: dataclasses.asdict(kind()) for key, kind in NAMES.items()}
    data["params"]["working_directories"] = {
        key: "" for key in data["params"]["working_directories"]
    }
    files = [
        "dioptas/model/state/params.py",
        "dioptas/model/state/project.py",
        "dioptas/model/util/jcpds.py",
    ]
    data["source_sha256"] = {
        p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in files
    }
    path = ROOT / "desktop/backend/resources/project-defaults.json"
    if args.write:
        path.write_text(json.dumps(data, indent=2) + "\n")
    else:
        assert json.loads(path.read_text()) == json.loads(json.dumps(data))
    print("Verified format-2 params defaults and source hashes.")


if __name__ == "__main__":
    main()
