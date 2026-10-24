"""Scientific and persistence checks for explicitly assumed phase structures."""

from collections import Counter
from copy import deepcopy
from math import sqrt

import pytest
from peritheos import Material as PeritheosMaterial, get_material_document

from ...model import eos
from ...model.eos.assumed_structure import (
    assume_tetragonal_perovskite, can_assume_tetragonal_perovskite)
from ...model.PhaseModel import PhaseModel
from ...model.util.phasesmith import structure_from_material


@pytest.fixture(params=["casio3_perovskite_tetragonal", "ca_perovskite_tetragonal"])
def assumed(request):
    material = eos.Material.from_dict(get_material_document(request.param))
    before = deepcopy(material)
    result = assume_tetragonal_perovskite(material)
    assert material == before
    assert result.eos_records == before.eos_records
    return result


def test_assumed_sites_expand_to_correct_stoichiometry_and_allowed_peaks(assumed):
    structure = structure_from_material(assumed)
    expanded = structure.space_group.expand_sites(
        [site.fractional_xyz for site in structure.sites])
    counts = Counter(structure.sites[i].element_symbol for i in expanded.source_site)
    z = assumed.formula_units_per_cell
    assert counts == {"Ca": z, "Si": z, "O": 3 * z}
    phase = eos.build_jcpds(assumed)
    indices = [(r.h, r.k, r.l) for r in phase.reflections]
    assert indices
    assert not structure.space_group.systematic_absences(indices).any()
    # Tetragonal splitting survives; these axes are not merged as cubic.
    axis_l = 2 if z == 1 else 4
    basal_k = 0 if z == 1 else 2
    basal = next(r for r in phase.reflections
                 if (r.h, r.k, r.l) == (2, basal_k, 0))
    axial = next(r for r in phase.reflections if (r.h, r.k, r.l) == (0, 0, axis_l))
    assert basal.d0 != pytest.approx(axial.d0)
    ratio = phase.params["c0"] / phase.params["a0"]
    if z == 1:
        assert ratio < 1
    else:
        assert ratio > sqrt(2)


def test_all_references_keep_volume_and_fixed_shape_consistent(assumed):
    model = PhaseModel()
    phase = eos.build_jcpds(assumed, origin="bundled")
    model.add_jcpds_object(phase)
    before = deepcopy(phase.params["eos_records"])
    ratio = phase.params["c0"] / phase.params["a0"]
    for index, record in enumerate(assumed.eos_records):
        assert model.set_eos_reference(0, index)
        phase.compute_d(40., 300.)
        assert phase.params["a0"] ** 2 * phase.params["c0"] == pytest.approx(
            record["eos"]["parameters"]["V0"])
        expected = PeritheosMaterial.from_eosmat(
            get_material_document(assumed.identifier),
            record_identifiers=[record["identifier"]],
        ).eos_records[0].volume(40., record["temperature_ref"], check_validity=False)
        assert phase.params["v"] == pytest.approx(expected)
        assert phase.params["a"] ** 2 * phase.params["c"] == pytest.approx(expected)
        assert phase.params["c"] / phase.params["a"] == pytest.approx(ratio)
        for r in phase.reflections:
            expected_d = 1 / sqrt(
                (r.h ** 2 + r.k ** 2) / phase.params["a"] ** 2
                + r.l ** 2 / phase.params["c"] ** 2)
            assert r.d == pytest.approx(expected_d)
        assert "Assumed diffraction structure" in phase.params["comments"][-1]
    assert phase.params["eos_records"] == before


def test_assumption_survives_export_and_project_save(assumed, tmp_path):
    from ...model.DioptasModel import DioptasModel

    phase = eos.build_jcpds(assumed, origin="bundled")
    path = str(tmp_path / "assumed.eosmat")
    eos.save_material_file(path, eos.material_from_jcpds(phase))
    loaded = eos.load_material_file(path)
    assert loaded.source == assumed.source
    assert loaded.atom_sites == assumed.atom_sites
    assert "assumed structure" in loaded.name
    model = DioptasModel()
    model.phase_model.add_jcpds_object(phase)
    project = str(tmp_path / "assumed.dio")
    model.save(project)
    restored = DioptasModel()
    restored.load(project)
    restored_phase = restored.phase_model.phases[0]
    assert restored_phase.params["material_document"]["source"] == assumed.source
    assert "assumed structure" in restored_phase.name
    assert restored.phase_model.set_eos_reference(0, len(assumed.eos_records) - 1)
    assert restored.phase_model.ensure_structure_reflection_coverage(.3, .31) == [0]
    restored_phase.compute_d(40., 300.)
    assert restored_phase.params["a"] ** 2 * restored_phase.params["c"] == pytest.approx(
        restored_phase.params["v"])


def test_assumptions_do_not_replace_existing_or_unrelated_structures():
    for identifier in ("gold", "ca_perovskite", "breyite"):
        material = eos.Material.from_dict(get_material_document(identifier))
        assert not can_assume_tetragonal_perovskite(material)
    material = assume_tetragonal_perovskite(eos.Material.from_dict(
        get_material_document("ca_perovskite_tetragonal")))
    assert not can_assume_tetragonal_perovskite(material)
    material.lattice.a = 0
    assert not can_assume_tetragonal_perovskite(material)
