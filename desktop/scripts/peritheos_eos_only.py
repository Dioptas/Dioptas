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
