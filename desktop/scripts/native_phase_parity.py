"""Independent PhaseModel/PhaseSmith/Peritheos comparisons, without child Python."""

import json, tempfile
from pathlib import Path
import numpy as np
from dioptas.model.PhaseModel import PhaseModel
from dioptas.model import eos
from native_reference_client import Native, ROOT


def main():
    receipts = []
    with Native() as n, tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        n.call(
            "manual_geometry",
            convention="pyfai",
            values=dict(
                dist=0.13,
                poni1=0.0024,
                poni2=0.0028,
                rot1=0,
                rot2=0,
                rot3=0,
                pixel1=0.0001,
                pixel2=0.0001,
                wavelength=0.31e-10,
                polarization_factor=0.99,
            ),
        )
        for name in ("au_version3.jcpds", "mo.jcpds"):
            n.call("integration_phase", operation="clear")
            path = ROOT / "dioptas/tests/data/jcpds" / name
            ref = PhaseModel()
            ref.add_jcpds(str(path))
            n.call("integration_phase", operation="load", path=str(path))
            for pressure, temp in ((0, 298), (22, 298), (35, 650), (-2, 298)):
                ref.set_pressure_temperature(0, pressure, temp)
                n.call(
                    "integration_phase",
                    operation="update",
                    index=0,
                    pressure=pressure,
                    temperature=temp,
                )
                e = n.call("integration_phase_editor", index=0)["phaseEditor"]
                np.testing.assert_allclose(
                    [r["d"] for r in e["reflections"]],
                    [r.d for r in ref.phases[0].reflections],
                    rtol=2e-11,
                    atol=1e-12,
                )
            receipts.append({"legacy": name, "conditions": 4})
        n.call("integration_phase", operation="clear")
        path = ROOT / "dioptas/tests/data/cif/fcc.cif"
        ref = PhaseModel()
        ref.add_cif(str(path), 0.5, 0.5, 0.31)
        n.call(
            "integration_phase",
            operation="load",
            path=str(path),
            minimum_d_spacing=0.5,
            intensity_cutoff=0.5,
        )
        rows = n.call("integration_phase_editor", index=0)["phaseEditor"]["reflections"]
        expected = np.array(
            [[r.h, r.k, r.l, r.d0, r.intensity] for r in ref.phases[0].reflections]
        )
        actual = np.array(
            [[r[k] for k in ("h", "k", "l", "d0", "intensity")] for r in rows]
        )
        np.testing.assert_allclose(actual, expected, rtol=2e-11, atol=1e-10)
        receipts.append(
            {
                "cif": "fcc.cif",
                "reflections": len(rows),
                "reference": "independent PhaseSmith Python adapter",
            }
        )
        from dioptas.desktop.phase_sites import site_labels
        from dioptas.model.eos.structure_composition import assess_structure_composition

        # Inspect native-derived Wyckoff labels against the existing Moyo adapter.
        fccdoc = tmp / "fcc.eosmat"
        n.call("integration_phase_export", index=0, path=str(fccdoc))
        fcc = json.loads(fccdoc.read_text())
        structure = n.call("integration_phase_editor", index=0)["phaseEditor"][
            "structure"
        ]
        expected_labels = site_labels(fcc)
        assert [(v["label"], v["multiplicity"]) for v in structure["siteWyckoff"]] == [
            (v["label"], v["multiplicity"]) for v in expected_labels
        ]
        composition = assess_structure_composition(fcc)
        assert structure["compositionStatus"] == composition.status
        if composition.z is not None:
            np.testing.assert_allclose(structure["calculatedZ"], composition.z)
        catalog = n.call("integration_phase_catalog", query="gold")["phaseCatalog"]
        gold = next(m for m in catalog if m["id"] == "gold")
        reference = next(
            i for i, r in enumerate(gold["references"]) if "Anderson" in r["label"]
        )
        doc = tmp / "gold.eosmat"
        n.call("integration_phase_export", material_id="gold", path=str(doc))
        material = eos.load_material_file(str(doc))
        ref = PhaseModel()
        ref.add_jcpds_object(
            eos.build_jcpds(
                material,
                reference,
                minimum_d_spacing=0.5,
                wavelength_angstrom=0.31,
                origin="bundled",
            )
        )
        n.call("integration_phase", operation="clear")
        n.call(
            "integration_phase",
            operation="load_database",
            material_id="gold",
            reference=reference,
        )
        for pressure, temp in ((0, 298), (30, 298), (60, 650), (-2, 650)):
            ref.set_pressure_temperature(0, pressure, temp)
            n.call(
                "integration_phase",
                operation="update",
                index=0,
                pressure=pressure,
                temperature=temp,
            )
            e = n.call("integration_phase_editor", index=0)["phaseEditor"]
            np.testing.assert_allclose(
                [r["d"] for r in e["reflections"]],
                [r.d for r in ref.phases[0].reflections],
                rtol=3e-10,
                atol=1e-12,
            )
            np.testing.assert_allclose(
                e["lattice"]["v"], ref.phases[0].params["v"], rtol=3e-10
            )
        before = n.call("integration_phase_editor", index=0)["phaseEditor"]
        rejected = n.invoke(
            "integration_phase",
            operation="editor_parameter",
            index=0,
            parameter="k0",
            value=170,
        )
        assert not rejected["ok"]
        copy = n.call(
            "integration_phase", operation="editor_copy", index=0, editor=True
        )["phaseEditor"]
        uid = copy["uid"]
        n.call(
            "integration_phase",
            operation="editor_record",
            editor_uid=uid,
            action="duplicate",
        )
        edit = n.call(
            "integration_phase",
            operation="editor_parameter",
            editor_uid=uid,
            parameter="k0",
            value=180,
            editor=True,
        )["phaseEditor"]
        assert edit["recordData"]["scientific_validation"]["status"] == "deferred"
        assert (
            n.call("integration_phase_editor", index=0)["phaseEditor"]["recordData"]
            == before["recordData"]
        )
        custom = tmp / "custom.eosmat"
        n.call("integration_phase_export", editor_uid=uid, path=str(custom))
        saved = eos.load_material_file(str(custom))
        assert saved.eos_records[-1]["eos"]["parameters"]["K0"] == 180
        # Delete/add/duplicate cycles must keep unique record identifiers.
        for action in ("delete", "add", "duplicate", "delete", "add"):
            r = n.call(
                "integration_phase",
                operation="editor_record",
                editor_uid=uid,
                action=action,
                editor=True,
            )
            assert not r["phaseEditor"].get("editError"), r["phaseEditor"].get(
                "editError"
            )
        records = tmp / "records.eosmat"
        n.call("integration_phase_export", editor_uid=uid, path=str(records))
        ids = [r["identifier"] for r in json.loads(records.read_text())["eos_records"]]
        assert len(ids) == len(set(ids))
        # Every editable room-temperature constructor, then representative thermal
        # constructors, is independently evaluated by the Python model adapter.
        from dioptas.model.util.eos_phase import RT_EOS_TYPES

        constructors = []
        n.call(
            "integration_phase",
            operation="editor_thermal_type",
            editor_uid=uid,
            value="none",
        )
        for kind in RT_EOS_TYPES:
            e = n.call(
                "integration_phase",
                operation="editor_eos_type",
                editor_uid=uid,
                value=kind,
                editor=True,
            )["phaseEditor"]
            assert not e.get("editError"), (kind, e.get("editError"))
            exported = tmp / f"{kind}.eosmat"
            n.call("integration_phase_export", editor_uid=uid, path=str(exported))
            material = eos.load_material_file(str(exported))
            ref = PhaseModel()
            ref.add_jcpds_object(
                eos.build_jcpds(
                    material,
                    e["reference"],
                    minimum_d_spacing=0.5,
                    wavelength_angstrom=0.31,
                    origin="custom",
                )
            )
            ref.set_pressure_temperature(0, e["pressure"], e["temperature"])
            np.testing.assert_allclose(
                e["lattice"]["v"], ref.phases[0].params["v"], rtol=3e-9
            )
            constructors.append(kind)
        for kind in ("BM3",):
            n.call(
                "integration_phase",
                operation="editor_eos_type",
                editor_uid=uid,
                value=kind,
            )
        for thermal in (
            "AlphaKT",
            "MieGruneisenDebye",
            "LinearThermalPressure",
            "LogVolumeThermalPressure",
        ):
            e = n.call(
                "integration_phase",
                operation="editor_thermal_type",
                editor_uid=uid,
                value=thermal,
                editor=True,
            )["phaseEditor"]
            assert not e.get("editError"), (thermal, e.get("editError"))
            n.call(
                "integration_phase",
                operation="update",
                editor_uid=uid,
                pressure=35,
                temperature=600,
            )
            target = tmp / f"{thermal}.eosmat"
            n.call("integration_phase_export", editor_uid=uid, path=str(target))
            current = n.call("integration_phase_editor", editor_uid=uid)["phaseEditor"]
            material = eos.load_material_file(str(target))
            ref = PhaseModel()
            ref.add_jcpds_object(
                eos.build_jcpds(
                    material,
                    current["reference"],
                    minimum_d_spacing=0.5,
                    wavelength_angstrom=0.31,
                    origin="custom",
                )
            )
            ref.set_pressure_temperature(0, 35, 600)
            np.testing.assert_allclose(
                current["lattice"]["v"], ref.phases[0].params["v"], rtol=3e-9
            )
        receipts.append(
            {
                "editorConstructors": constructors,
                "thermalComparisons": 4,
                "recordIdentifiers": "unique after deletion/addition",
            }
        )
        n.call("integration_phase", operation="remove", index=0)
        assert (
            n.call("integration_phase_editor", editor_uid=uid)["phaseEditor"]["uid"]
            == uid
        )
        n.call("integration_phase", operation="remove", editor_uid=uid)
        assert not n.invoke("integration_phase_editor", editor_uid=uid)["ok"]
        receipts.append(
            {
                "material": "gold Anderson record",
                "conditions": 4,
                "copy": "retains source record; edited copy deferred; EOSMAT roundtrip; stable UID",
            }
        )
        # Formula search uses the same ranked source material fields.
        from dioptas.model.eos.database import search_materials

        authored = json.loads(
            (ROOT / "desktop/backend/resources/peritheos/materials.json").read_text()
        )
        materials = [eos.Material.from_dict(doc) for doc in authored]
        for query in ("MgFe", "Fe2O3", "gold"):
            actual = [
                m["id"]
                for m in n.call("integration_phase_catalog", query=query)[
                    "phaseCatalog"
                ]
            ]
            expected = [
                m.identifier
                for m in search_materials(
                    query, materials=sorted(materials, key=lambda m: m.name.lower())
                )
            ]
            assert actual == expected, (query, actual, expected)
        n.call("integration_phase", operation="clear")
        assumptions = 0
        for identifier in ("casio3_perovskite_tetragonal", "ca_perovskite_tetragonal"):
            matches = n.call("integration_phase_catalog", query="CaSiO3")[
                "phaseCatalog"
            ]
            entry = next(m for m in matches if m["id"] == identifier)
            assert entry["canAssumeStructure"]
            reference = entry["defaultReference"]
            n.call(
                "integration_phase",
                operation="load_database",
                material_id=identifier,
                reference=reference,
                assume_structure=True,
            )
            current = n.call("integration_phase_editor", index=assumptions)[
                "phaseEditor"
            ]
            assert current["structure"]["assumption"]
            doc = tmp / f"{identifier}.eosmat"
            n.call("integration_phase_export", index=assumptions, path=str(doc))
            material = eos.load_material_file(str(doc))
            ref = PhaseModel()
            ref.add_jcpds_object(
                eos.build_jcpds(
                    material,
                    reference,
                    minimum_d_spacing=0.5,
                    wavelength_angstrom=0.31,
                    origin="bundled",
                )
            )
            np.testing.assert_allclose(
                [r["intensity"] for r in current["reflections"]],
                [r.intensity for r in ref.phases[0].reflections],
                rtol=3e-10,
                atol=1e-9,
            )
            assumptions += 1
        receipts.append(
            {"rankedSearch": 3, "explicitStructureAssumptions": assumptions}
        )
    out = ROOT / "desktop/artifacts/native-integration/phase-parity.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipts, indent=2) + "\n")
    print(json.dumps(receipts, indent=2))


if __name__ == "__main__":
    main()
