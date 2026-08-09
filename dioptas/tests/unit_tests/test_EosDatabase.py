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
    assert len(gold.eos_records) >= 3
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
    label = eos.record_label(gold.eos_records[0])
    assert phase.name == f"Au ({label})"
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
    assert phase.params["modified"] is False


def test_build_jcpds_without_records(materials):
    copper = next(m for m in materials if m.formula == "Cu")
    assert copper.eos_records == []
    phase = eos.build_jcpds(copper)
    # loadable anyway: peaks at ambient conditions, V0 from the lattice
    assert phase.name == "Cu"
    assert phase.params["v0"] == pytest.approx(3.615 ** 3, rel=1e-4)
    assert len(phase.reflections) == len(copper.peaks)


def test_reference_switch_updates_parameters_and_name(gold):
    phase = eos.build_jcpds(gold, record_index=0)
    model = PhaseModel()
    model.add_jcpds_object(phase, filename=phase.filename)

    first = gold.eos_records[0]["eos"]["parameters"]
    second = gold.eos_records[1]["eos"]["parameters"]
    second_label = eos.record_label(gold.eos_records[1])

    model.set_eos_reference(0, 1)
    assert model.phases[0].params["k0"] == pytest.approx(second["K0"])
    assert model.phases[0].name == f"Au ({second_label})"
    assert model.phase_files[0] == f"Au ({second_label})"

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
    # and switching still works after the reload
    loaded.phase_model.set_eos_reference(0, 2)
    third = gold.eos_records[2]["eos"]["parameters"]
    assert loaded_phase.params["k0"] == pytest.approx(third["K0"])


def test_eosmat_round_trip(materials, tmp_path):
    # wollastonite is triclinic — angles must survive the round trip
    wollastonite = next(m for m in materials
                        if m.symmetry == "TRICLINIC")
    path = str(tmp_path / "wollastonite.eosmat")
    eos.save_material_file(path, wollastonite)
    loaded = eos.load_material_file(path)

    assert loaded.name == wollastonite.name
    assert loaded.lattice.alpha == pytest.approx(wollastonite.lattice.alpha)
    assert loaded.lattice.beta == pytest.approx(wollastonite.lattice.beta)
    assert loaded.lattice.gamma == pytest.approx(wollastonite.lattice.gamma)
    assert loaded.lattice.alpha != 90.0
    assert loaded.peaks == wollastonite.peaks
    assert loaded.eos_records == wollastonite.eos_records
    assert loaded.formula_units_per_cell == wollastonite.formula_units_per_cell


def test_alias_search_is_case_insensitive():
    assert any(m.formula == "Au" for m in eos.search_materials("GOLD"))
