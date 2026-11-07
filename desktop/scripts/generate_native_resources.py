"""Reproduce native metadata from pinned authored sources; never a runtime dependency.

Run from the Dioptas root with its test environment. Default compares semantic
JSON; --write refreshes resources. Optional numerical dataset packages are not
read. Keep the Peritheos source revision in sync with backend/Cargo.toml.
"""

import argparse
import hashlib
import inspect
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REVISION = "3c79b1aedf28c348a49cc22d9f24d92895546283"


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--peritheos", type=Path, required=True)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=args.peritheos, text=True
    ).strip()
    assert revision == REVISION, (revision, REVISION)
    sys.path.insert(0, str(args.peritheos.resolve()))
    from dioptas.desktop import custom_commands, phase_sites
    from dioptas.desktop.thermal_field_labels import thermal_field_display
    from dioptas.model import eos
    from dioptas.model.util import eos_phase

    source = args.peritheos / "peritheos/data/materials"
    docs = []
    hashes = {}
    annotations = {}
    for path in sorted(source.glob("*.eosmat")):
        raw = path.read_bytes()
        hashes[path.name] = hashlib.sha256(raw).hexdigest()
        docs.append(json.loads(raw))
        material = eos.load_material_file(str(path))
        for record in material.eos_records:
            reference = record.get("reference")
            assessment, detail = eos.record_reproduction(record)
            annotations[record["identifier"]] = dict(
                assessment=assessment,
                detail=eos.reference_text(reference) + "\n\n" + detail,
                label=eos.record_label(record),
                reportUrl=eos.reconstruction_report_url(record),
                recordUrl=eos.peritheos_record_url(material.identifier, record),
                authors=eos.reference_authors(reference),
                year=eos.reference_year(reference),
                citation=eos.reference_text(reference),
                pressureRange=eos.record_pressure_range(record),
            )
    schema = {
        "eos": {
            kind: eos_phase.eos_parameter_names(kind) for kind in eos_phase.RT_EOS_TYPES
        },
        "thermal": {},
        "eosModels": eos_phase.EOS_MODEL_IDENTIFIERS,
    }
    for kind in eos_phase.THERMAL_EOS_TYPES:
        fields = []
        seeds = eos_phase.thermal_parameter_defaults(kind)
        for name, parameter in eos_phase.thermal_parameter_signature(kind).items():
            required = parameter.default is inspect.Parameter.empty
            label, unit, description = thermal_field_display(kind, name)
            fields.append(
                dict(
                    key=name,
                    label=label,
                    unit=unit,
                    description=description,
                    required=required,
                    default=None if required else parameter.default,
                    choices=list(eos_phase.THERMAL_CONFIGURATION_CHOICES.get(name, ())),
                    initial=seeds[name],
                )
            )
        schema["thermal"][kind] = dict(
            model=eos_phase.THERMAL_MODEL_IDENTIFIERS[kind], fields=fields
        )
    resources = ROOT / "desktop/backend/resources"
    generated = {
        "peritheos/materials.json": docs,
        "peritheos/record-display.json": annotations,
        "phase-editor-schema.json": schema,
        "elements.json": phase_sites.element_choices(),
        "action-icons.json": sorted(custom_commands.ICONS),
    }
    for name, value in generated.items():
        path = resources / name
        if args.write:
            path.write_text(json.dumps(value, separators=(",", ":")) + "\n")
        else:
            expected = json.loads(path.read_text())
            if expected != value:
                if isinstance(value, dict):
                    key = next(k for k in value if expected.get(k) != value[k])
                    print(name, "first differing key:", key)
                raise AssertionError(f"Resource differs: {name}")
    provenance_path = resources / "peritheos/SOURCE.json"
    provenance = json.loads(provenance_path.read_text())
    assert provenance["revision"] == revision and provenance["documents"] == hashes
    helpers = [
        "dioptas/model/eos/material.py",
        "dioptas/model/eos/reproducibility.py",
        "dioptas/model/util/eos_phase.py",
        "dioptas/desktop/thermal_field_labels.py",
        "dioptas/desktop/phase_sites.py",
        "dioptas/desktop/custom_commands.py",
    ]
    derived = dict(
        generator="desktop/scripts/generate_native_resources.py",
        dioptas_revision=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        helper_sha256={
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in helpers
        },
    )
    if args.write:
        provenance["derived_metadata"] = derived
        provenance_path.write_text(json.dumps(provenance, indent=2) + "\n")
    else:
        assert (
            provenance["derived_metadata"]["helper_sha256"] == derived["helper_sha256"]
        )
    print(
        f"Verified {len(docs)} authored materials, {len(annotations)} record annotations and editor metadata."
    )


if __name__ == "__main__":
    main()
