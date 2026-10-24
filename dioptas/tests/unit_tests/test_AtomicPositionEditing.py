"""Atomic-site edits must update diffraction and portable structure state together."""

from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest
from peritheos import get_material_document

from ...model import eos
from ...model.DioptasModel import DioptasModel
from ...model.PhaseModel import PhaseModel
from ...model.util.jcpds import EosCalculationError, jcpds
from ...model.util.phasesmith import calculate_material_reflections


def add_diopside(model, origin='file'):
    phase = eos.build_jcpds(eos.Material.from_dict(get_material_document('diopside')),
                            origin=origin)
    model.add_jcpds_object(phase)
    return phase


def reflections(phase):
    return np.array([(r.h, r.k, r.l, r.d0, r.intensity, r.d) for r in phase.reflections])


def test_position_edit_recalculates_intensities_at_current_conditions():
    model = PhaseModel()
    phase = add_diopside(model)
    model.set_pressure_temperature(0, 15., 600.)
    records = deepcopy(phase.params['eos_records'])
    old = reflections(phase)
    value = phase.params['material_document']['atom_sites'][3]['x'] + .02

    model.set_atom_site_parameter(0, 3, 'x', value, wavelength_angstrom=.31)

    document = phase.params['material_document']
    assert document['atom_sites'][3]['x'] == value
    assert 'wyckoff' not in document['atom_sites'][3]
    assert phase.state.reflection_source['material']['atom_sites'] == document['atom_sites']
    expected = calculate_material_reflections(eos.material_from_jcpds(phase),
                                              wavelength_angstrom=.31)
    actual = [(r.h, r.k, r.l, r.d0, r.intensity) for r in phase.reflections]
    np.testing.assert_allclose(actual, expected)
    assert old.shape != reflections(phase).shape or not np.allclose(old, reflections(phase))
    assert phase.params['eos_records'] == records
    assert phase.params['pressure'] == 15.
    assert phase.params['temperature'] == 600.
    assert phase.state.modified
    np.testing.assert_allclose(model.items[0].reflections[:, 1], reflections(phase)[:, 4])
    assert model.set_eos_reference(0, phase.params['eos_current_index'])
    assert phase.state.modified
    assert phase.params['material_document']['atom_sites'][3]['x'] == value


@pytest.mark.parametrize(('parameter', 'value'), [
    ('x', 'invalid'), ('y', np.nan), ('z', np.inf),
    ('occupancy', -.01), ('occupancy', 1.01), ('u_iso_angstrom2', -.1),
    ('element', 'Xx'), ('element', ''), ('element', 'Fe3+'),
])
def test_invalid_site_edit_preserves_everything(parameter, value):
    model = PhaseModel()
    phase = add_diopside(model)
    before = model._condition_snapshot(phase)
    lines = reflections(phase)
    with pytest.raises(ValueError):
        model.set_atom_site_parameter(0, 3, parameter, value)
    assert model._condition_snapshot(phase) == before
    np.testing.assert_array_equal(reflections(phase), lines)


def test_failed_calculation_does_not_partly_commit_sites_or_reflections(monkeypatch):
    model = PhaseModel()
    phase = add_diopside(model)
    before = model._condition_snapshot(phase)
    lines = reflections(phase)

    def fail(*_args, **_kwargs):
        raise EosCalculationError('test EOS failure')

    monkeypatch.setattr(jcpds, 'compute_d', fail)
    with pytest.raises(EosCalculationError):
        model.set_atom_site_parameter(0, 3, 'x', .13)
    assert model._condition_snapshot(phase) == before
    np.testing.assert_array_equal(reflections(phase), lines)


def test_custom_eos_copy_does_not_unlock_a_bundled_structure():
    model = PhaseModel()
    phase = add_diopside(model, origin='bundled')
    model.duplicate_eos_record(0, phase.params['eos_current_index'])
    before = model._condition_snapshot(phase)
    with pytest.raises(PermissionError, match='Bundled materials'):
        model.set_atom_site_parameter(0, 3, 'x', .13)
    assert model._condition_snapshot(phase) == before


@pytest.mark.parametrize('operation', ['add', 'remove', 'element'])
def test_site_add_remove_and_element_changes_recalculate_and_round_trip(operation, tmp_path):
    model = PhaseModel()
    phase = add_diopside(model)
    original_sites = deepcopy(phase.params['material_document']['atom_sites'])
    if operation == 'add':
        index = model.add_atom_site(0, 'fe', .12, .23, .34, .5)
        sites = phase.params['material_document']['atom_sites']
        assert index == len(original_sites)
        assert sites[index]['element'] == 'Fe'
        assert sites[index]['occupancy'] == .5
    elif operation == 'remove':
        model.remove_atom_sites(0, [0, 2, 2])
        assert phase.params['material_document']['atom_sites'] == [
            site for i, site in enumerate(original_sites) if i not in (0, 2)]
    else:
        site = phase.params['material_document']['atom_sites'][0]
        site.update({'type_symbol': 'Mg2+', 'charge': 2, 'isotope': 24})
        model.set_atom_site_parameter(0, 0, 'element', 'Fe')
        changed = phase.params['material_document']['atom_sites'][0]
        assert changed['element'] == 'Fe'
        assert not {'type_symbol', 'charge', 'isotope'} & changed.keys()
    expected = calculate_material_reflections(eos.material_from_jcpds(phase))
    np.testing.assert_allclose(reflections(phase)[:, :5], expected)
    path = str(tmp_path / f'{operation}.eosmat')
    eos.save_material_file(path, eos.material_from_jcpds(phase))
    loaded = eos.build_jcpds(eos.load_material_file(path), origin='file')
    assert loaded.params['material_document']['atom_sites'] == phase.params['material_document']['atom_sites']
    np.testing.assert_allclose(reflections(phase), reflections(loaded))


@pytest.mark.parametrize('operation', ['add', 'remove', 'element'])
def test_new_site_operations_reject_bundled_structures(operation):
    model = PhaseModel()
    phase = add_diopside(model, origin='bundled')
    before = model._condition_snapshot(phase)
    with pytest.raises(PermissionError):
        if operation == 'add':
            model.add_atom_site(0, 'Fe')
        elif operation == 'remove':
            model.remove_atom_sites(0, [0])
        else:
            model.set_atom_site_parameter(0, 0, 'element', 'Fe')
    assert model._condition_snapshot(phase) == before


def test_invalid_add_and_removing_every_site_leave_structure_intact():
    model = PhaseModel()
    phase = add_diopside(model)
    before = model._condition_snapshot(phase)
    with pytest.raises(ValueError):
        model.add_atom_site(0, 'Xx')
    with pytest.raises(ValueError, match='finite'):
        model.add_atom_site(0, 'Fe', x=np.nan)
    with pytest.raises(ValueError, match='at least one'):
        model.remove_atom_sites(0, list(range(len(phase.params['material_document']['atom_sites']))))
    assert model._condition_snapshot(phase) == before


def test_edited_cif_positions_survive_eosmat_reload_and_coverage_extension(tmp_path):
    model = PhaseModel()
    model.add_cif(str(Path(__file__).parent / '../data/test.cif'))
    phase = model.phases[0]
    original_cif = phase.params['material_document']['source']['text']
    value = phase.params['material_document']['atom_sites'][0]['x'] + .02
    model.set_atom_site_parameter(0, 0, 'x', value)
    filename = str(tmp_path / 'edited-cif.eosmat')
    eos.save_material_file(filename, eos.material_from_jcpds(phase))

    restored = eos.build_jcpds(eos.load_material_file(filename), origin='file')
    np.testing.assert_allclose(reflections(restored), reflections(phase))
    assert restored.params['material_document']['atom_sites'][0]['x'] == value
    assert restored.params['material_document']['source']['text'] == original_cif
    assert restored.state.reflection_source['kind'] == 'material'
    loaded = PhaseModel()
    loaded.add_jcpds_object(restored)
    loaded.ensure_structure_reflection_coverage(.35, .31)
    assert restored.state.reflection_source['material']['atom_sites'][0]['x'] == value
    expected = calculate_material_reflections(eos.material_from_jcpds(restored),
                                              minimum_d_spacing=.35)
    np.testing.assert_allclose([(r.h, r.k, r.l, r.d0, r.intensity)
                               for r in restored.reflections], expected)


@pytest.mark.parametrize('operation', ['position', 'add', 'remove', 'element', 'space_group'])
def test_atomic_edit_survives_project_and_undo_redo(tmp_path, operation):
    model = DioptasModel()
    restored = DioptasModel()
    try:
        phase = add_diopside(model.phase_model)
        old = deepcopy(phase.params['material_document'])
        model.history.reset()
        if operation == 'position':
            model.phase_model.set_atom_site_parameter(0, 3, 'x', .13)
        elif operation == 'add':
            model.phase_model.add_atom_site(0, 'Fe', .12, .23, .34)
        elif operation == 'remove':
            model.phase_model.remove_atom_sites(0, [0])
        elif operation == 'element':
            model.phase_model.set_atom_site_parameter(0, 0, 'element', 'Fe')
        else:
            model.phase_model.set_space_group(0, 'P21/c')
        changed = deepcopy(phase.params['material_document'])
        lines = reflections(phase)
        assert model.history.depth == 1
        model.history.undo()
        assert model.phase_model.phases[0].params['material_document'] == old
        model.history.redo()
        phase = model.phase_model.phases[0]
        assert phase.params['material_document'] == changed
        np.testing.assert_allclose(reflections(phase), lines)
        filename = str(tmp_path / 'atomic-positions.dio')
        model.save(filename)
        restored.load(filename)
        assert restored.phase_model.phases[0].params['material_document'] == changed
        np.testing.assert_allclose(reflections(restored.phase_model.phases[0]), lines)
    finally:
        model.delete_configurations()
        restored.delete_configurations()
