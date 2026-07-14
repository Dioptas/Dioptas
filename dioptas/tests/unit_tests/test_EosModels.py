# SPDX-License-Identifier: MIT
"""
Tests for the pydantic material models and the .eosmat round trip.
"""
import pytest

from ...eos_models import Material, EosParameters, Peak, Lattice
from ...eos_formats import build_jcpds, write_eosmat, read_eosmat


@pytest.fixture
def gold_material():
    return Material(
        name="Gold",
        formula="Au",
        lattice=Lattice(symmetry="CUBIC", a=4.0786),
        peaks=[
            Peak(h=1, k=1, l=1, d_spacing=2.3550, intensity=100.0),
            Peak(h=2, k=0, l=0, d_spacing=2.0390, intensity=52.0),
        ],
        formula_units_per_cell=4,
    )


@pytest.fixture
def gold_eos():
    return EosParameters(
        eos_type="Birch-Murnaghan", eos_order=3,
        reference="Anderson et al 1989",
        v0=67.847, k0=166.65, k0_prime=5.4823,
    )


def test_from_api_maps_flat_dict_to_nested_model():
    material = Material.from_api({
        "id": "abc", "name": "Gold", "formula": "Au", "symmetry": "CUBIC",
        "a": 4.0786, "b": None, "c": None,
        "alpha": 90.0, "beta": 90.0, "gamma": 90.0,
        "diffraction_peaks": [
            {"h": 1, "k": 1, "l": 1, "d_spacing": 2.355, "intensity": 100.0}],
    })
    assert material.lattice.symmetry == "CUBIC"
    assert material.lattice.a == 4.0786
    assert material.peaks[0].d_spacing == 2.355
    assert material.display_name == "Gold (Au)"


def test_formula_parsing():
    assert Material(formula="Au").atoms_per_formula() == 1
    assert Material(formula="Au").electrons_per_formula() == 79
    assert Material(formula="MgO").atoms_per_formula() == 2
    assert Material(formula="MgO").electrons_per_formula() == 20   # 12 + 8
    assert Material(formula="Al2O3").atoms_per_formula() == 5
    # Non-formula strings must not silently parse
    assert Material(formula="diamond").atoms_per_formula() is None


def test_engine_type_mapping():
    assert EosParameters(eos_type="Birch-Murnaghan", eos_order=3).engine_type == "BM3"
    assert EosParameters(eos_type="Birch-Murnaghan", eos_order=2).engine_type == "BM2"
    assert EosParameters(eos_type="Vinet", eos_order=None).engine_type == "VINET"
    assert EosParameters(eos_type="Holzapfel", eos_order=None).engine_type == "HOLZAPFEL"


def test_build_jcpds_names_phase_with_chemistry_and_reference(gold_material, gold_eos):
    phase = build_jcpds(gold_material, gold_eos)
    assert phase._name == "Au (Anderson et al 1989)"
    assert phase.params["k0"] == 166.65
    assert phase.params["eos_type"] == "BM3"
    # Holzapfel data carried on the phase (from formula + cell count)
    assert phase.params["n"] == 1
    assert phase.params["z"] == 79
    assert phase.params["zc"] == 4
    assert len(phase.reflections) == 2


def test_eosmat_round_trip(tmp_path, gold_material, gold_eos):
    path = str(tmp_path / "gold.eosmat")
    write_eosmat(path, gold_material, gold_eos)
    material, eos = read_eosmat(path)

    assert material.name == "Gold"
    assert material.formula == "Au"
    assert material.lattice.symmetry == "CUBIC"
    assert material.lattice.a == pytest.approx(4.0786)
    assert material.formula_units_per_cell == 4
    assert len(material.peaks) == 2
    assert material.peaks[0].d_spacing == pytest.approx(2.3550)

    assert eos.eos_type == "Birch-Murnaghan"
    assert eos.eos_order == 3
    assert eos.k0 == pytest.approx(166.65)
    assert eos.engine_type == "BM3"
