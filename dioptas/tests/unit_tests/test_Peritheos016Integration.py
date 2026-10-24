"""Native interchange, scientific holds and project fidelity with Peritheos 0.16."""

from copy import deepcopy
import json

import h5py
import pytest
from peritheos import (
    Material as PeritheosMaterial, convert_eosmat, create_eosmat,
    get_material_document, load_eosmat, save_eosmat,
)

from ...model import eos
from ...model.DioptasModel import DioptasModel
from ...model.util.eos_phase import EosPhase


@pytest.mark.parametrize("identifier", ["gold", "diamond", "diopside", "brucite"])
def test_native_file_calculates_with_full_record_and_preserves_evidence(identifier, tmp_path):
    document = get_material_document(identifier, format_version=4)
    document["private_extension"] = {"source": [1.2345678901234567, None, "µm"]}
    before = deepcopy(document)
    source = tmp_path / "native.eosmat"
    save_eosmat(source, document)
    material = eos.load_material_file(str(source))
    assert material.format_version == 3
    index = next((i for i, r in enumerate(material.eos_records)
                  if r.get("thermal")), 0)
    record = material.eos_records[index]
    phase = eos.build_jcpds(material, record_index=index, origin="file")
    temperature = 1000. if record.get("thermal") else record.get("temperature_ref", 300.)
    engine = EosPhase.from_jcpds(phase, with_thermal=bool(record.get("thermal")))
    expected = PeritheosMaterial.from_eosmat(
        document, record_identifiers=[record["identifier"]],
        require_primary_validation=False,
    ).eos_records[0].volume(20., temperature, check_validity=False)
    phase.compute_d(20., temperature)
    assert engine._record is not None  # canonical dispatch, including thermal configuration
    assert phase.params["v"] == pytest.approx(expected, rel=1e-12)
    output = tmp_path / "export.eosmat"
    eos.save_material_file(str(output), eos.material_from_jcpds(phase))
    exported = load_eosmat(output)
    assert exported["format_version"] == 4
    normalized = convert_eosmat(exported, version=3)
    original = convert_eosmat(document, version=3)
    assert normalized["eos_records"] == original["eos_records"]
    assert normalized.get("datasets") == original.get("datasets")
    assert normalized["private_extension"] == document["private_extension"]
    assert document == before
    eos.save_material_file(str(output), material, format_version=3)
    assert load_eosmat(output)["format_version"] == 3


def test_small_unaudited_native_file_remains_editable_and_executable(tmp_path):
    document = create_eosmat("my_gold", "Au", "BM3",
                            {"V0": 67.8, "K0": 170., "K0_prime": 5.},
                            temperature_ref=300.)
    document.update(symmetry="CUBIC", lattice={"a": 4.078, "alpha": 90., "beta": 90., "gamma": 90.},
                    peaks=[[1, 1, 1, 2.354, 100.]])
    path = tmp_path / "my-gold.eosmat"
    save_eosmat(path, document)
    material = eos.load_material_file(str(path))
    phase = eos.build_jcpds(material, origin="file")
    phase.compute_d(20., 300.)
    assert 0 < phase.params["v"] < 67.8
    assert material.eos_records[0]["scientific_validation"]["status"] != "primary_source_validated"


@pytest.mark.parametrize("identifier", ["palladium", "wadsleyite"])
def test_held_default_needs_selection_and_export_does_not_invent_default(identifier, tmp_path):
    material = eos.Material.from_dict(get_material_document(identifier))
    before = deepcopy(material)
    assert material.default_eos_index == -1
    with pytest.raises(ValueError, match="hold|unresolved"):
        eos.build_jcpds(material, origin="bundled")
    index = next((i for i, r in enumerate(material.eos_records)
                  if r["scientific_validation"]["status"] == "primary_source_validated"), None)
    exported_material = material
    if index is not None:
        phase = eos.build_jcpds(material, record_index=index, origin="bundled")
        phase.compute_d(20., 300.)
        exported_material = eos.material_from_jcpds(phase)
    path = tmp_path / "held.eosmat"
    eos.save_material_file(str(path), exported_material)
    restored = eos.load_material_file(str(path))
    assert restored.recommendation_hold == material.recommendation_hold
    assert restored.default_eos_index == -1
    assert not any(r.get("default") or r.get("default_for") for r in restored.eos_records)
    assert material == before


@pytest.mark.parametrize("embedded_version", [3, 4])
def test_project_embedded_layout_preserves_selected_eos_conditions_and_undo(embedded_version, tmp_path):
    model = DioptasModel()
    material = eos.Material.from_dict(get_material_document("gold"))
    phase = eos.build_jcpds(material, origin="file")
    model.phase_model.add_jcpds_object(phase)
    custom = model.phase_model.duplicate_eos_record(0, phase.params["eos_current_index"])
    model.phase_model.set_param(0, "k0", 171.)
    assert model.phase_model.set_pressure_temperature(0, 20., 900.)
    expected_records = deepcopy(phase.params["eos_records"])
    expected_volume = phase.params["v"]
    path = tmp_path / "project.dio"
    model.save(str(path))
    if embedded_version == 4:
        with h5py.File(path, "r+") as project:
            data = json.loads(project["state"][()])
            crystal = data["phases"][0]["crystal"]
            native = convert_eosmat({**crystal["material_document"],
                                     "eos_records": crystal["eos_records"]}, version=4)
            crystal["eos_records"] = native.pop("eos_records")
            crystal["material_document"] = native
            del project["state"]
            project.create_dataset("state", data=json.dumps(data))
    restored = DioptasModel()
    restored.load(str(path))
    loaded = restored.phase_model.phases[0]
    assert loaded.params["material_document"]["format_version"] == 3
    assert loaded.params["eos_current_index"] == custom
    assert loaded.params["eos_records"] == expected_records
    assert loaded.params["pressure"] == 20.
    assert loaded.params["temperature"] == 900.
    assert loaded.params["v"] == pytest.approx(expected_volume)
    restored.history.reset()
    restored.phase_model.set_param(0, "k0", 180.)
    restored.history.undo()
    loaded = restored.phase_model.phases[0]
    assert loaded.params["k0"] == 171.
    assert loaded.params["eos_records"] == expected_records
    assert loaded.params["v"] == pytest.approx(expected_volume)
    restored.history.redo()
    assert restored.phase_model.phases[0].params["k0"] == 180.
