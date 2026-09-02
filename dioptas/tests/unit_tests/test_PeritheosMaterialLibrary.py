"""Integration contract for the material library owned by Peritheos."""

from copy import deepcopy

import pytest
from peritheos import (
    Material as PeritheosMaterial,
    get_material_document,
    list_material_documents,
)

from ...model import eos
from ...model.PhaseModel import PhaseModel
from ...model.util.jcpds import EosCalculationError


def test_dioptas_loads_the_complete_peritheos_library():
    materials = eos.load_materials()

    assert {material.identifier for material in materials} == set(
        list_material_documents())
    assert len(materials) == 115
    assert sum(len(material.eos_records) for material in materials) == 147


@pytest.mark.parametrize(
    "material_id,record_id",
    [
        ("gold", "gold_anderson_1989_bm3_1"),
        ("diamond", "diamond_benedict_2014_double_debye_4"),
        ("kcl", "kcl_b2_dewaele_2012_vinet_3"),
    ],
)
def test_new_peritheos_thermal_records_use_the_executable_record(
        material_id, record_id):
    document = get_material_document(material_id)
    record_index = next(
        index for index, record in enumerate(document["eos_records"])
        if record["identifier"] == record_id
    )
    material = eos.Material.from_dict(document)
    phase = eos.build_jcpds(material, record_index=record_index)

    phase.compute_volume(pressure=20.0, temperature=1000.0)
    expected = PeritheosMaterial.from_eosmat(
        document, record_identifiers=[record_id]
    ).eos_records[0].volume(
        20.0, 1000.0, check_validity=False
    )

    assert phase.params["thermal_type"] == (
        document["eos_records"][record_index]["thermal"]["type"])
    assert phase.params["v"] == pytest.approx(expected)


def test_saving_custom_record_in_canonical_material_adds_required_metadata(
        tmp_path):
    material = eos.Material.from_dict(get_material_document("gold"))
    material.eos_records.append({
        "label": "My fit",
        "eos": {
            "type": "BM3",
            "parameters": {"V0": 67.8, "K0": 170.0, "K0_prime": 5.0},
        },
    })
    path = tmp_path / "custom-gold.eosmat"

    eos.save_material_file(str(path), material)
    loaded = eos.load_material_file(str(path))
    custom = loaded.eos_records[-1]

    assert custom["identifier"] == "my_fit"
    assert custom["eos"]["model"] == "birch_murnaghan_3"
    assert custom["reference"] == ""
    assert custom["scientific_validation"]["status"] == "deferred"


def test_duplicated_library_record_exports_as_unvalidated_custom_record(
        tmp_path):
    gold = eos.Material.from_dict(get_material_document("gold"))
    phase = eos.build_jcpds(gold, record_index=0, origin="bundled")
    model = PhaseModel()
    model.add_jcpds_object(phase, filename=phase.filename)

    custom_index = model.duplicate_eos_record(0, 0)
    custom = phase.params["eos_records"][custom_index]
    phase.compute_volume(pressure=20.0, temperature=1000.0)
    path = tmp_path / "custom-gold.eosmat"
    eos.save_material_file(str(path), eos.material_from_jcpds(phase))
    loaded = eos.load_material_file(str(path))

    assert custom["identifier"] != gold.eos_records[0]["identifier"]
    assert custom["scientific_validation"]["status"] == "deferred"
    assert loaded.eos_records[custom_index]["identifier"] == custom["identifier"]


def test_phase_editor_type_changes_keep_canonical_component_models():
    document = get_material_document("gold")
    source_index = next(
        index for index, record in enumerate(document["eos_records"])
        if record.get("thermal", {}).get("type") == "LogVolumeThermalPressure"
    )
    phase = eos.build_jcpds(
        eos.Material.from_dict(document), record_index=source_index,
        origin="bundled",
    )
    model = PhaseModel()
    model.add_jcpds_object(phase, filename=phase.filename)
    custom_index = model.duplicate_eos_record(0, source_index)

    model.set_eos_type(0, "Vinet")
    model.set_param(0, "thermal_parameters", {
        "Tr": 298.15,
        "theta0": 170.0,
        "gamma0": 2.5,
        "q": 1.0,
        "n": 1.0,
    })
    model.set_thermal_type(0, "MieGruneisenDebye")
    custom = phase.params["eos_records"][custom_index]

    assert custom["eos"]["model"] == "vinet"
    assert custom["thermal"]["model"] == "mie_gruneisen_debye"
    phase.compute_volume(pressure=20.0, temperature=300.0)
    cold_volume = phase.params["v"]
    phase.compute_volume(pressure=20.0, temperature=1500.0)
    hot_volume = phase.params["v"]
    portable = eos.material_from_jcpds(phase).to_dict()
    expected = PeritheosMaterial.from_eosmat(
        portable,
        record_identifiers=[custom["identifier"]],
        require_primary_validation=False,
    ).eos_records[0].volume(20.0, 1500.0, check_validity=False)

    assert hot_volume != pytest.approx(cold_volume)
    assert hot_volume == pytest.approx(expected)


def test_save_material_file_does_not_mutate_material(tmp_path):
    material = eos.Material.from_dict(get_material_document("gold"))
    material.eos_records.append({
        "label": "My fit",
        "eos": {
            "type": "BM3",
            "parameters": {"V0": 67.8, "K0": 170.0, "K0_prime": 5.0},
        },
    })
    before = deepcopy(material)

    eos.save_material_file(str(tmp_path / "gold.eosmat"), material)

    assert material == before


@pytest.mark.parametrize("origin,raises", [
    ("bundled", True),
    ("file", False),
    ("custom", False),
])
def test_primary_validation_is_enforced_only_for_bundled_records(
        origin, raises):
    document = deepcopy(get_material_document("gold"))
    record = document["eos_records"][0]
    record["scientific_validation"] = {
        "status": "deferred",
        "note": "Regression fixture: deliberately unaudited.",
    }
    phase = eos.build_jcpds(
        eos.Material.from_dict(document), record_index=0, origin=origin)

    if raises:
        with pytest.raises(EosCalculationError, match="primary-source validation"):
            phase.compute_volume(pressure=20.0, temperature=300.0)
    else:
        phase.compute_volume(pressure=20.0, temperature=300.0)
        assert phase.params["v"] > 0
