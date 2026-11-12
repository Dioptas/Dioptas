"""Distribution projection, never applied to user-loaded EOS documents.

Keep models, parameters, uncertainty, structure, citations and qualifications.
Drop dataset descriptors/files and embedded observation or audit row tables.
The pinned upstream documents remain identified by their original SHA256s.
"""
import json
from pathlib import Path

POLICY = json.loads(Path(__file__).with_name("peritheos_distribution_policy.json").read_text())


def eos_only(value):
    if isinstance(value, dict):
        return {
            key: eos_only(item)
            for key, item in value.items()
            if key not in POLICY["omitFields"]
            and not (key in POLICY["omitCollections"] and isinstance(item, (list, dict)))
        }
    if isinstance(value, list):
        return [eos_only(item) for item in value]
    return value


def verify_snapshot(source, resources):
    """Check only the distribution projection, without Python scientific packages."""
    import hashlib
    import subprocess

    provenance = json.loads((resources / "SOURCE.json").read_text())
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
    assert revision == provenance["revision"], "Unexpected Peritheos source revision"
    paths = sorted((source / "peritheos/data/materials").glob("*.eosmat"))
    hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    assert hashes == provenance["documents"], "Upstream material documents changed"
    original = [json.loads(path.read_bytes()) for path in paths]
    distributed = json.loads((resources / "materials.json").read_text())
    assert distributed == eos_only(original), "EOS-only catalog differs from upstream projection"
    for before, after in zip(original, distributed):
        assert len(before["eos_records"]) == len(after["eos_records"])
        for old, new in zip(before["eos_records"], after["eos_records"]):
            for key in ("identifier", "model", "parameters", "thermal", "uncertainties", "parameter_covariance", "validity", "reference"):
                assert old.get(key) == new.get(key), (before["identifier"], old["identifier"], key)
    print(f"Verified EOS-only projection of {len(original)} upstream materials and all {sum(len(doc['eos_records']) for doc in original)} EOS records; model parameters and citations unchanged.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--peritheos", type=Path, required=True)
    args = parser.parse_args()
    verify_snapshot(args.peritheos, Path(__file__).resolve().parents[1] / "backend/resources/peritheos")
