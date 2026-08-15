# -*- coding: utf-8 -*-
"""
Tests for the bundled EoS material database: loading, search, the jcpds
phase builder, the per-phase reference switcher, and — crucially — that
all of it survives a project save/load round trip, since the records live
on the phase state.
"""
import os
import math

import pytest

from ...model import eos
from ...model.eos.material import Material, _parse_formula
from ...model.PhaseModel import PhaseModel
from ...model.util.jcpds import EosCalculationError
from ...model.util.phasesmith import material_has_complete_structure
from ...model.util.eos_phase import EosPhase


@pytest.fixture
def materials():
    return eos.load_materials()


@pytest.fixture
def gold(materials):
    return next(m for m in materials if m.formula == "Au")


def test_bundled_database_loads(materials):
    assert len(materials) >= 20
    names = {m.name for m in materials}
    assert {
        "Gold", "Platinum", "MgO", "Diamond",
        "Zinc oxide (wurtzite B4)", "Zinc oxide (rocksalt B1)",
        "Zirconium (alpha)", "Zirconium (omega)", "Zirconium (beta)",
        "Nickel oxide (rhombohedral B1)", "Cementite",
        "Iron carbide (orthorhombic Fe7C3)",
        "Calcium carbonate (post-aragonite Pmmn)",
    } <= names
    # Complete structures are calculated by PhaseSmith; legacy records keep
    # a stored peak table only when they cannot be calculated.
    for m in materials:
        assert m.lattice.a > 0
        if material_has_complete_structure(m):
            assert not m.peaks
        else:
            assert m.peaks


def test_every_bundled_eos_record_constructs_and_evaluates(materials):
    """Database curation must never rely on the silent BM3 fallback."""
    evaluated = 0
    for material in materials:
        for index, record in enumerate(material.eos_records):
            phase = eos.build_jcpds(material, record_index=index)
            thermal_type = phase.params.get("thermal_type") or ""
            try:
                engine = EosPhase.from_jcpds(
                    phase, with_thermal=bool(thermal_type)
                )
                volume = engine.volume(20.0, 1000.0)
            except Exception as error:
                pytest.fail(
                    f"{material.name} record {index} "
                    f"({record.get('label')}) is not constructible: {error}"
                )
            assert math.isfinite(volume) and volume > 0
            evaluated += 1
    assert evaluated == 147


@pytest.mark.parametrize(
    "name",
    [
        "Zinc oxide (wurtzite B4)",
        "Zinc oxide (rocksalt B1)",
        "Zirconium (alpha)",
        "Zirconium (omega)",
        "Zirconium (beta)",
        "Nickel oxide (rhombohedral B1)",
        "Cementite",
        "Iron carbide (orthorhombic Fe7C3)",
        "Calcium carbonate (post-aragonite Pmmn)",
    ],
)
def test_phase_expansion_materials_build_structure_reflections(
        materials, name):
    material = next(material for material in materials
                    if material.name == name)
    for index in range(len(material.eos_records)):
        phase = eos.build_jcpds(material, record_index=index)
        assert phase.reflections


def test_gold_has_multiple_references(gold):
    assert len(gold.eos_records) == 4
    labels = [eos.record_label(r) for r in gold.eos_records]
    assert all(labels), "every record needs a display label"
    assert len(set(labels)) == len(labels), "labels must be unique"


def test_unreachable_gold_temperature_retains_last_valid_state(gold):
    """A Peritheos inversion limit is user input feedback, not a traceback."""
    model = PhaseModel()
    model.same_conditions = False
    phase = eos.build_jcpds(gold)  # Fei et al. MGD record
    model.add_jcpds_object(phase)
    assert model.set_pressure(0, 10.0)
    previous_temperature = phase.params["temperature"]
    previous_volume = phase.params["v"]
    previous_d = [reflection.d for reflection in phase.reflections]

    assert not model.set_temperature(0, 100000.0)
    assert phase.params["temperature"] == previous_temperature
    assert phase.params["v"] == previous_volume
    assert [reflection.d for reflection in phase.reflections] == previous_d


def test_unreachable_gold_reference_switch_is_rolled_back(gold, monkeypatch):
    model = PhaseModel()
    model.same_conditions = False
    phase = eos.build_jcpds(gold)
    model.add_jcpds_object(phase)
    previous_index = phase.params["eos_current_index"]
    previous_type = phase.params["eos_type"]

    def fail_at_current_conditions(*args, **kwargs):
        raise EosCalculationError("outside invertible range")

    monkeypatch.setattr(phase, "compute_d", fail_at_current_conditions)

    assert not model.set_eos_reference(0, 3)
    assert phase.params["eos_current_index"] == previous_index
    assert phase.params["eos_type"] == previous_type


def test_search(materials):
    assert any(m.formula == "Au" for m in eos.search_materials("Au"))
    # Names and material-owned aliases find the corresponding formula.
    assert any(m.formula == "Au" for m in eos.search_materials("gold"))
    assert any(m.formula == "MgO" for m in eos.search_materials("periclase"))
    assert any(m.formula == "Mg2Fe3O5"
               for m in eos.search_materials("ferropericlase"))
    # Every bundled water-ice phase is discoverable by its chemistry.
    water_ice_names = {m.name for m in eos.search_materials("H2O")}
    assert {"Ice VI", "Ice VII", "Ice VIII"} <= water_ice_names
    assert any(m.name == "Zinc oxide (wurtzite B4)"
               for m in eos.search_materials("zincite"))
    assert any(m.name == "Calcium carbonate (post-aragonite Pmmn)"
               for m in eos.search_materials("CaCO3-Pmmn"))
    # empty query returns everything
    assert len(eos.search_materials("")) == len(materials)


def test_search_matches_formula_family_and_ranks_exact_formula_first():
    materials = [
        Material(name="Mixed oxide", formula="Mg2Fe3O5"),
        Material(name="Exact", formula="MgFeO"),
        Material(name="Different family", formula="Mg2SiO4"),
    ]

    results = eos.search_materials("MgFeO", materials)

    assert [material.name for material in results] == ["Exact", "Mixed oxide"]


def test_search_matches_multi_element_formula_subset_in_any_order():
    materials = [
        Material(name="Ferropericlase", formula="Mg2Fe3O5"),
        Material(name="Magnesium silicate", formula="Mg2SiO4"),
    ]

    assert eos.search_materials("MgFe", materials) == [materials[0]]
    assert eos.search_materials("FeMg", materials) == [materials[0]]


def test_search_recognizes_equivalent_decimal_and_unicode_formulas():
    materials = [
        Material(name="Ferropericlase", formula="Mg2Fe3O5"),
        Material(name="Different ratio", formula="MgFeO"),
    ]

    ascii_results = eos.search_materials("Mg0.4Fe0.6O", materials)
    unicode_results = eos.search_materials("Mg₀.₄Fe₀.₆O", materials)

    assert ascii_results[0].name == "Ferropericlase"
    assert unicode_results[0].name == "Ferropericlase"


def test_search_uses_material_owned_aliases_and_partial_aliases():
    materials = [
        Material(name="MgO", formula="MgO",
                 aliases=["Magnesia", "Periclase"]),
        Material(name="Unrelated", formula="CaO"),
    ]

    assert eos.search_materials("periclase", materials) == [materials[0]]
    assert eos.search_materials("peri", materials) == [materials[0]]


def test_material_aliases_survive_serialization():
    material = Material(name="Alumina", formula="Al2O3",
                        aliases=["Corundum"])

    loaded = Material.from_dict(material.to_dict())

    assert loaded.aliases == ["Corundum"]


def test_formula_parsing():
    assert Material(formula="Au").atoms_per_formula() == 1
    assert Material(formula="Au").electrons_per_formula() == 79
    assert Material(formula="MgO").atoms_per_formula() == 2
    assert Material(formula="MgO").electrons_per_formula() == 20   # 12 + 8
    assert Material(formula="Al2O3").atoms_per_formula() == 5
    # Non-formula strings must not silently parse
    assert Material(formula="diamond").atoms_per_formula() is None
    assert _parse_formula("") == []


def test_experimental_pressure_range_display():
    record = {
        "label": "Angel et al. (1997)",
        "experimental_pressure_range_gpa": [0.0, 8.9]
    }
    assert eos.record_pressure_range(record) == "0–8.9 GPa"
    assert eos.record_label(record) == "Angel et al. (1997) [0–8.9 GPa]"
    assert eos.record_pressure_range({}) == ""


def test_structured_reference_display_and_legacy_compatibility():
    reference = {
        "authors": ["Dewaele", "Torrent", "Loubeyre", "Mezouar"],
        "year": 2008,
        "source": "Phys. Rev. B",
        "volume": "78",
        "locator": "104102",
        "doi": "10.1103/PhysRevB.78.104102",
    }
    assert eos.reference_authors(reference) == "Dewaele et al."
    assert eos.reference_year(reference) == "2008"
    assert eos.reference_short(reference) == "Dewaele et al. (2008)"
    assert eos.reference_text(reference) == (
        "Dewaele, Torrent, Loubeyre, and Mezouar, Phys. Rev. B 78, "
        "104102 (2008), doi:10.1103/PhysRevB.78.104102"
    )

    legacy = "Dewaele et al., Phys. Rev. B 91, 134108 (2015)"
    assert eos.reference_authors(legacy) == "Dewaele et al."
    assert eos.reference_year(legacy) == "2015"
    assert eos.reference_text(legacy) == legacy


@pytest.mark.parametrize(
    "authors, expected",
    [
        (["Ross"], "Ross"),
        (["Redfern", "Angel"], "Redfern and Angel"),
        (["Martinez", "Zhang", "Reeder"], "Martinez et al."),
    ],
)
def test_reference_authors_compacts_complete_author_lists(authors, expected):
    assert eos.reference_authors({"authors": authors}) == expected


def test_non_numeric_pressure_domain_status_display():
    assert eos.record_pressure_range({
        "pressure_range_status": "reference_parameterization"
    }) == "reference model"
    assert eos.record_pressure_range({
        "pressure_range_status": "theoretical"
    }) == "theoretical"
    assert eos.record_pressure_range({
        "pressure_range_status": "reported_qualitatively"
    }) == "qualitative limit"


def test_build_jcpds_carries_everything(gold):
    phase = eos.build_jcpds(gold, record_index=0)
    # The mineral/material and chemistry identify the phase; the active
    # literature record remains separate in the Ref column and comments.
    assert phase.name == "Gold (Au)"
    assert phase.params["comments"] == [
        eos.reference_text(gold.eos_records[0]["reference"])
    ]
    assert phase.params["k0"] > 0
    assert phase.params["v0"] > 0
    assert not gold.peaks
    assert len(phase.reflections) > 0
    assert phase.reflections[0].d0 == pytest.approx(2.35917, abs=1e-5)
    # Holzapfel data (Au -> n=1, Z=79, fcc -> Zc=4)
    assert phase.params["n"] == 1
    assert phase.params["z"] == 79
    assert phase.params["zc"] == 4
    # the reference switcher state
    assert phase.params["chemistry"] == "Au"
    assert len(phase.params["eos_records"]) == len(gold.eos_records)
    assert phase.params["eos_current_index"] == 0
    assert (phase.params["eos_parameter_errors"]
            == gold.eos_records[0]["parameter_errors"])
    assert (phase.params["eos_fixed_parameters"]
            == gold.eos_records[0]["fixed_parameters"])
    assert phase.params["modified"] is False


def test_build_jcpds_uses_explicit_material_default(gold):
    phase = eos.build_jcpds(gold)

    assert gold.default_eos_index == 1
    assert phase.params["eos_current_index"] == 1
    assert phase.params["comments"] == [
        eos.reference_text(gold.eos_records[1]["reference"])
    ]


def test_build_jcpds_distinguishes_polymorph_name_from_formula(materials):
    akimotoite = next(material for material in materials
                      if material.name == "Akimotoite")

    phase = eos.build_jcpds(akimotoite, origin="bundled")

    assert phase.name == "Akimotoite (MgSiO3)"
    assert "Siersch" not in phase.name


def test_build_jcpds_without_records(materials):
    # some materials carry peak provenance but no published EoS
    material = next(
        m for m in materials
        if not m.eos_records and not material_has_complete_structure(m)
    )
    phase = eos.build_jcpds(material)
    # loadable anyway: peaks at ambient conditions, V0 from the lattice
    assert phase.params["v0"] > 0
    assert len(phase.reflections) == len(material.peaks)
    assert phase.params["k0"] == 0.0


def test_reference_switch_updates_parameters_and_comments(gold):
    phase = eos.build_jcpds(gold, record_index=0)
    model = PhaseModel()
    model.add_jcpds_object(phase, filename=phase.filename)

    first = gold.eos_records[0]["eos"]["parameters"]
    second = gold.eos_records[1]["eos"]["parameters"]

    model.set_eos_reference(0, 1)
    assert model.phases[0].params["k0"] == pytest.approx(second["K0"])
    # the material name stays stable; the reference moves to the comments
    assert model.phases[0].name == "Gold (Au)"
    assert (model.phases[0].params["comments"]
            == [eos.reference_text(gold.eos_records[1]["reference"])])

    model.set_eos_reference(0, 0)   # and back
    assert model.phases[0].params["k0"] == pytest.approx(first["K0"])

    # out-of-range indices are ignored
    model.set_eos_reference(0, 99)
    assert model.phases[0].params["k0"] == pytest.approx(first["K0"])


def test_reference_switch_is_noop_for_legacy_jcpds():
    unittest_path = os.path.dirname(__file__)
    model = PhaseModel()
    model.add_jcpds(os.path.join(unittest_path, "../data/jcpds",
                                 "au_Anderson.jcpds"))
    assert model.get_eos_reference_labels(0) == []
    k0 = model.phases[0].params["k0"]
    model.set_eos_reference(0, 0)
    assert model.phases[0].params["k0"] == k0


def test_bundled_records_are_immutable_but_custom_copies_are_editable(gold):
    phase = eos.build_jcpds(gold, record_index=0, origin="bundled")
    model = PhaseModel()
    model.add_jcpds_object(phase, filename=phase.filename)

    assert model.eos_record_origin(0) == "bundled"
    assert not model.is_eos_record_editable(0)
    with pytest.raises(PermissionError, match="read-only"):
        model.set_eos_type(0, "Vinet")
    with pytest.raises(PermissionError, match="read-only"):
        model.delete_eos_record(0, 0)
    with pytest.raises(PermissionError, match="read-only"):
        model.set_param(0, "a0", 4.1)
    with pytest.raises(PermissionError, match="read-only"):
        model.delete_reflection(0, 0)

    custom_index = model.duplicate_eos_record(0, 0)
    assert model.eos_record_origin(0, custom_index) == "custom"
    assert model.is_eos_record_editable(0, custom_index)
    model.set_eos_type(0, "Vinet")
    assert phase.params["eos_records"][custom_index]["eos"]["type"] == "Vinet"
    model.set_eos_reference(0, 0)
    assert phase.params["modified"] is True

    model.delete_eos_record(0, custom_index)
    assert len(phase.params["eos_records"]) == len(gold.eos_records)
    assert all(origin == "bundled"
               for origin in phase.params["eos_record_origins"])


def test_custom_record_lifecycle_and_last_delete(gold):
    structure_only = Material.from_dict(gold.to_dict())
    structure_only.eos_records = []
    phase = eos.build_jcpds(structure_only, origin="cif")
    model = PhaseModel()
    model.add_jcpds_object(phase, filename=phase.filename)
    phase.params["k0"] = 150.0
    phase.params["k0p0"] = 4.2
    record = model.eos_record_from_phase(0)
    record["label"] = "My fit"

    index = model.add_eos_record(0, record)
    assert index == 0
    assert model.get_eos_reference_labels(0) == ["My fit"]
    model.set_eos_default(0, 0)
    model.delete_eos_record(0, 0)

    assert phase.params["eos_records"] == []
    assert phase.params["k0"] == 0.0
    assert phase.params["eos_type"] == "BM3"


def test_live_phase_exports_complete_user_material(gold):
    phase = eos.build_jcpds(gold, record_index=0, origin="bundled")
    model = PhaseModel()
    model.add_jcpds_object(phase, filename=phase.filename)
    custom_index = model.duplicate_eos_record(0, 0)
    model.set_eos_type(0, "Vinet")
    model.set_eos_default(0, custom_index)

    exported = eos.material_from_jcpds(phase)

    assert exported.atom_sites == gold.atom_sites
    assert len(exported.eos_records) == len(gold.eos_records) + 1
    assert exported.default_eos_index == custom_index
    assert exported.eos_records[custom_index]["eos"]["type"] == "Vinet"
    assert "eos_record_origins" not in exported.to_dict()


def test_records_survive_project_round_trip(gold, tmp_path):
    from ...model.DioptasModel import DioptasModel

    model = DioptasModel()
    phase = eos.build_jcpds(gold, record_index=0)
    model.phase_model.add_jcpds_object(phase, filename=phase.filename)
    model.phase_model.set_eos_reference(0, 1)
    model.phase_model.set_eos_type(0, "Vinet")
    filename = str(tmp_path / "project.dio")
    model.save(filename)

    loaded = DioptasModel()
    loaded.load(filename)
    loaded_phase = loaded.phase_model.phases[0]
    # the full switcher state is back: records, labels, selection, name
    assert loaded.phase_model.get_eos_type(0) == "Vinet"
    assert (loaded.phase_model.get_eos_reference_labels(0)
            == [eos.record_label(r) for r in gold.eos_records])
    assert loaded_phase.params["eos_current_index"] == 1
    assert loaded_phase.name == phase.name
    assert (loaded_phase.params["eos_parameter_errors"]
            == gold.eos_records[1]["parameter_errors"])
    assert (loaded_phase.params["eos_fixed_parameters"]
            == gold.eos_records[1]["fixed_parameters"])
    # and switching still works after the reload
    loaded.phase_model.set_eos_reference(0, 0)
    first = gold.eos_records[0]["eos"]["parameters"]
    assert loaded_phase.params["k0"] == pytest.approx(first["K0"])


def test_record_ownership_and_material_survive_project_round_trip(
        gold, tmp_path):
    from ...model.DioptasModel import DioptasModel

    model = DioptasModel()
    phase = eos.build_jcpds(gold, record_index=0, origin="bundled")
    model.phase_model.add_jcpds_object(phase, filename=phase.filename)
    custom_index = model.phase_model.duplicate_eos_record(0, 0)
    filename = str(tmp_path / "ownership.dio")
    model.save(filename)

    loaded = DioptasModel()
    loaded.load(filename)
    loaded_phase = loaded.phase_model.phases[0]

    assert loaded_phase.params["material_origin"] == "bundled"
    assert loaded_phase.params["material_document"]["formula"] == "Au"
    assert loaded_phase.params["eos_record_origins"][:-1] == [
        "bundled" for _ in gold.eos_records]
    assert loaded_phase.params["eos_record_origins"][custom_index] == "custom"
    assert loaded.phase_model.is_eos_record_editable(0, custom_index)
    assert not loaded.phase_model.is_eos_record_editable(0, 0)


def test_structure_source_survives_project_and_can_extend_lines(gold, tmp_path):
    from math import pi

    from ...model.DioptasModel import DioptasModel

    model = DioptasModel()
    phase = eos.build_jcpds(gold)
    model.phase_model.add_jcpds_object(phase, filename=phase.filename)
    filename = str(tmp_path / "structure-source.dio")
    model.save(filename)

    loaded = DioptasModel()
    loaded.load(filename)
    loaded_phase = loaded.phase_model.phases[0]
    initial_count = len(loaded_phase.reflections)

    changed = loaded.phase_model.ensure_structure_reflection_coverage(
        2.0 * pi / 21.0,
        0.31,
    )

    assert loaded_phase.state.reflection_source["kind"] == "material"
    assert changed == [0]
    assert len(loaded_phase.reflections) > initial_count


def test_eosmat_round_trip(materials, tmp_path):
    # Coesite is monoclinic — its non-orthogonal angle must survive the round trip.
    coesite = next(m for m in materials if m.name == "Coesite")
    path = str(tmp_path / "coesite.eosmat")
    eos.save_material_file(path, coesite)
    loaded = eos.load_material_file(path)

    assert loaded.name == coesite.name
    assert loaded.lattice.alpha == pytest.approx(coesite.lattice.alpha)
    assert loaded.lattice.beta == pytest.approx(coesite.lattice.beta)
    assert loaded.lattice.gamma == pytest.approx(coesite.lattice.gamma)
    assert loaded.lattice.beta != 90.0
    assert loaded.peaks == coesite.peaks == []
    assert loaded.eos_records == coesite.eos_records
    assert loaded.formula_units_per_cell == coesite.formula_units_per_cell
    assert loaded.space_group == coesite.space_group
    assert loaded.space_group_number == coesite.space_group_number
    assert loaded.atom_sites == coesite.atom_sites

    rendered = open(path, encoding="utf-8").read()
    peak_lines = [line for line in rendered.splitlines()
                  if line.startswith("  [")]
    assert len(peak_lines) == len(coesite.peaks)


def test_eosmat_keeps_each_atom_site_on_one_line(tmp_path):
    material = next(m for m in eos.load_materials() if m.formula == "MgO")
    path = str(tmp_path / "MgO.eosmat")
    eos.save_material_file(path, material)
    rendered = open(path, encoding="utf-8").read()
    site_lines = [line for line in rendered.splitlines()
                  if line.startswith('  {"element"')]
    assert len(site_lines) == len(material.atom_sites)


def test_alias_search_is_case_insensitive():
    assert any(m.formula == "Au" for m in eos.search_materials("GOLD"))


def test_mgd_record_applies_thermal_state(gold):
    mgd_index = next(i for i, r in enumerate(gold.eos_records)
                     if (r.get("thermal") or {}).get("type")
                     == "MieGruneisenDebye")
    phase = eos.build_jcpds(gold, record_index=mgd_index)
    assert phase.params["thermal_type"] == "MieGruneisenDebye"
    assert phase.params["theta_t0"] == pytest.approx(170.0)
    assert phase.params["gamma_t0"] == pytest.approx(2.97)
    assert phase.has_thermal_expansion()

    # temperature genuinely moves the volume through the engine
    phase.compute_volume(pressure=10.0, temperature=300.0)
    v300 = phase.params["v"]
    phase.compute_volume(pressure=10.0, temperature=1500.0)
    assert phase.params["v"] > v300

    # switching away from MGD clears the engine's MGD thermal state
    model = PhaseModel()
    model.add_jcpds_object(phase, filename=phase.filename)
    other = next(i for i, r in enumerate(gold.eos_records)
                 if (r.get("thermal") or {}).get("type") == "AlphaKT")
    model.set_eos_reference(0, other)
    assert model.get_thermal_type(0) == ""


def test_custom_mgd_record_applies_thermal_atom_count():
    record = {
        "label": "Custom thermal fit",
        "eos": {
            "type": "Vinet",
            "parameters": {"V0": 64.0, "K0": 150.0, "K0_prime": 4.0},
        },
        "thermal": {
            "type": "MieGruneisenDebye",
            "parameters": {
                "Tr": 300.0,
                "theta0": 500.0,
                "gamma0": 1.5,
                "q": 1.0,
                "n": 1.0,
            },
        },
    }
    material = eos.Material(
        name="Custom phase",
        symmetry="CUBIC",
        lattice=eos.Lattice(a=4.0),
        formula_units_per_cell=1,
        peaks=[[1, 0, 0, 4.0, 100.0]],
        eos_records=[record],
    )

    phase = eos.build_jcpds(material)

    assert phase.params["n"] == pytest.approx(1.0)
    phase.compute_volume(pressure=10.0, temperature=300.0)
    volume_at_300 = phase.params["v"]
    phase.compute_volume(pressure=10.0, temperature=1000.0)
    assert phase.params["v"] > volume_at_300

    model = PhaseModel()
    model.add_jcpds_object(phase, filename=phase.filename)
    saved_record = model.eos_record_from_phase(0, record)
    assert saved_record["thermal"]["parameters"]["n"] == pytest.approx(1.0)


def test_thermal_state_survives_project_round_trip(gold, tmp_path):
    from ...model.DioptasModel import DioptasModel

    mgd_index = next(i for i, r in enumerate(gold.eos_records)
                     if (r.get("thermal") or {}).get("type")
                     == "MieGruneisenDebye")
    model = DioptasModel()
    phase = eos.build_jcpds(gold, record_index=mgd_index)
    model.phase_model.add_jcpds_object(phase, filename=phase.filename)
    filename = str(tmp_path / "thermal.dio")
    model.save(filename)

    loaded = DioptasModel()
    loaded.load(filename)
    p = loaded.phase_model.phases[0].params
    assert p["thermal_type"] == "MieGruneisenDebye"
    assert p["theta_t0"] == pytest.approx(170.0)
    assert p["gamma_t0"] == pytest.approx(2.97)
    assert p["q_t0"] == pytest.approx(0.6)
    loaded.phase_model.phases[0].compute_volume(pressure=10.0,
                                                temperature=1500.0)
    phase.compute_volume(pressure=10.0, temperature=1500.0)
    assert (loaded.phase_model.phases[0].params["v"]
            == pytest.approx(phase.params["v"], rel=1e-9))


def test_sokolova_record_and_full_parameters_survive_project_round_trip(
        gold, tmp_path):
    from ...model.DioptasModel import DioptasModel

    index = next(i for i, record in enumerate(gold.eos_records)
                 if (record.get("thermal") or {}).get("type")
                 == "Sokolova2016")
    source = gold.eos_records[index]["thermal"]
    phase = eos.build_jcpds(gold, record_index=index)
    assert phase.params["thermal_type"] == "Sokolova2016"
    assert phase.params["thermal_parameters"] == source["parameters"]
    assert (phase.params["thermal_parameter_errors"]
            == source["parameter_errors"])

    model = DioptasModel()
    model.phase_model.add_jcpds_object(phase, filename=phase.filename)
    filename = str(tmp_path / "sokolova.dio")
    model.save(filename)
    loaded = DioptasModel()
    loaded.load(filename)
    loaded_phase = loaded.phase_model.phases[0]
    assert loaded_phase.params["thermal_parameters"] == source["parameters"]
    loaded_phase.compute_volume(pressure=100.0, temperature=1000.0)
    assert loaded_phase.params["v"] < loaded_phase.params["v0"]
