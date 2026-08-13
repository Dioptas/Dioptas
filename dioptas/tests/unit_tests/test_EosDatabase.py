# -*- coding: utf-8 -*-
"""
Tests for the bundled EoS material database: loading, search, the jcpds
phase builder, the per-phase reference switcher, and — crucially — that
all of it survives a project save/load round trip, since the records live
on the phase state.
"""
import os

import pytest

from ...model import eos
from ...model.eos.material import Material, _parse_formula
from ...model.PhaseModel import PhaseModel


@pytest.fixture
def materials():
    return eos.load_materials()


@pytest.fixture
def gold(materials):
    return next(m for m in materials if m.formula == "Au")


def test_bundled_database_loads(materials):
    assert len(materials) >= 20
    names = {m.name for m in materials}
    assert {"Gold", "Platinum", "MgO", "Diamond"} <= names
    # every material parses into a lattice and peaks
    for m in materials:
        assert m.lattice.a > 0
        assert m.peaks


def test_gold_has_multiple_references(gold):
    assert len(gold.eos_records) == 3
    labels = [eos.record_label(r) for r in gold.eos_records]
    assert all(labels), "every record needs a display label"
    assert len(set(labels)) == len(labels), "labels must be unique"


def test_search(materials):
    assert any(m.formula == "Au" for m in eos.search_materials("Au"))
    # alias: common name finds the formula
    assert any(m.formula == "Au" for m in eos.search_materials("gold"))
    assert any(m.formula == "MgO" for m in eos.search_materials("periclase"))
    # empty query returns everything
    assert len(eos.search_materials("")) == len(materials)


def test_formula_parsing():
    assert Material(formula="Au").atoms_per_formula() == 1
    assert Material(formula="Au").electrons_per_formula() == 79
    assert Material(formula="MgO").atoms_per_formula() == 2
    assert Material(formula="MgO").electrons_per_formula() == 20   # 12 + 8
    assert Material(formula="Al2O3").atoms_per_formula() == 5
    # Non-formula strings must not silently parse
    assert Material(formula="diamond").atoms_per_formula() is None
    assert _parse_formula("") == []


def test_build_jcpds_carries_everything(gold):
    phase = eos.build_jcpds(gold, record_index=0)
    # the name is the chemistry alone; the active reference lives in the
    # Ref column and the comments
    assert phase.name == "Au"
    assert phase.params["comments"] == [gold.eos_records[0]["reference"]]
    assert phase.params["k0"] > 0
    assert phase.params["v0"] > 0
    assert len(phase.reflections) == len(gold.peaks)
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


def test_build_jcpds_without_records(materials):
    # some materials carry peak provenance but no published EoS
    material = next(m for m in materials if not m.eos_records)
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
    # the name stays the chemistry; the reference moves to the comments
    assert model.phases[0].name == "Au"
    assert (model.phases[0].params["comments"]
            == [gold.eos_records[1]["reference"]])

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
    assert loaded.peaks == coesite.peaks
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
