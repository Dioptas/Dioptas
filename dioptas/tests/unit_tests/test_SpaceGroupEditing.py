"""Space-group edits retain settings, geometry and the last valid diffraction state."""

from copy import deepcopy

import numpy as np
import pytest
from peritheos import get_material_document

from ...model import eos
from ...model.PhaseModel import PhaseModel
from ...model.util.jcpds import EosCalculationError, jcpds
from ...model.util.phasesmith import (
    calculate_material_reflections, resolve_space_group, space_group_lattice_symmetry,
)


def material_phase(identifier, origin='file'):
    model = PhaseModel()
    phase = eos.build_jcpds(eos.Material.from_dict(get_material_document(identifier)), origin=origin)
    model.add_jcpds_object(phase)
    return model, phase


def line_data(phase):
    return [(r.h, r.k, r.l, r.d0, r.intensity) for r in phase.reflections]


@pytest.mark.parametrize('value', ['221', 'Pm-3m', 'P m -3 m'])
def test_symbol_and_number_changes_recalculate_systematic_absences(value):
    model, phase = material_phase('gold')
    before_records = deepcopy(phase.params['eos_records'])
    before_lattice = [phase.params[key] for key in ('a0', 'b0', 'c0', 'alpha0', 'beta0', 'gamma0')]
    assert (1, 0, 0) not in {(r.h, r.k, r.l) for r in phase.reflections}

    model.set_space_group(0, value)

    document = phase.params['material_document']
    assert document['space_group_number'] == 221
    assert phase.params['symmetry'] == 'CUBIC'
    assert (1, 0, 0) in {(r.h, r.k, r.l) for r in phase.reflections}
    assert all('wyckoff' not in site for site in document['atom_sites'])
    assert phase.params['eos_records'] == before_records
    assert [phase.params[key] for key in ('a0', 'b0', 'c0', 'alpha0', 'beta0', 'gamma0')] == before_lattice
    np.testing.assert_allclose(line_data(phase), calculate_material_reflections(eos.material_from_jcpds(phase)))
    np.testing.assert_allclose(model.items[0].reflections[:, 1], [r.intensity for r in phase.reflections])


def test_lower_symmetry_preserves_cell_and_coordinates_at_current_conditions():
    model, phase = material_phase('diopside')
    model.set_pressure_temperature(0, 15., 600.)
    before = deepcopy(eos.material_from_jcpds(phase))
    model.set_space_group(0, 'P1')
    after = eos.material_from_jcpds(phase)
    assert phase.params['symmetry'] == after.symmetry == 'TRICLINIC'
    assert after.lattice == before.lattice
    assert [(s['x'], s['y'], s['z']) for s in after.atom_sites] == [
        (s['x'], s['y'], s['z']) for s in before.atom_sites]
    assert phase.params['pressure'] == 15.
    assert phase.params['temperature'] == 600.


def test_equivalent_symbol_or_number_keeps_valid_source_wyckoff_labels():
    model, phase = material_phase('gold')
    sites = deepcopy(phase.params['material_document']['atom_sites'])
    model.set_space_group(0, '225')
    assert phase.params['material_document']['atom_sites'] == sites


@pytest.mark.parametrize('value', ['invalid', '', '0', '231', '225'])
def test_invalid_or_incompatible_group_preserves_complete_phase(value):
    model, phase = material_phase('diopside')
    before = model._condition_snapshot(phase)
    lines = line_data(phase)
    cache = model.items[0].reflections.copy()
    with pytest.raises(ValueError):
        model.set_space_group(0, value)
    assert model._condition_snapshot(phase) == before
    assert line_data(phase) == lines
    np.testing.assert_array_equal(model.items[0].reflections, cache)


def test_non_reference_setting_survives_export_and_recalculation(tmp_path):
    model, phase = material_phase('diopside')
    model.set_space_group(0, 'P21/n')
    document = phase.params['material_document']
    assert document['space_group_number'] == 14
    assert resolve_space_group(document['space_group'])[1].setting == 'b2'
    filename = str(tmp_path / 'setting-b2.eosmat')
    eos.save_material_file(filename, eos.material_from_jcpds(phase))
    loaded = eos.build_jcpds(eos.load_material_file(filename), origin='file')
    assert resolve_space_group(loaded.params['material_document']['space_group'])[1].setting == 'b2'
    np.testing.assert_allclose(line_data(phase), line_data(loaded))


@pytest.mark.parametrize('number', [14, 146, 166, 227])
def test_numeric_lookup_keeps_the_library_reference_setting(number):
    from phasesmith.io.space_groups import space_group_by_number

    symbol, info = resolve_space_group(str(number))
    assert info.hall_symbol == space_group_by_number(number).hall_symbol
    assert resolve_space_group(symbol)[1].hall_symbol == info.hall_symbol


@pytest.mark.parametrize(('symbol', 'lattice', 'symmetry'), [
    ('R -3 m:R', eos.Lattice(a=5., b=5., c=5., alpha=75., beta=75., gamma=75.), 'RHOMBOHEDRAL'),
    ('R -3 m:H', eos.Lattice(a=5., b=5., c=12., gamma=120.), 'TRIGONAL'),
])
def test_rhombohedral_and_hexagonal_settings_use_the_correct_cell_model(symbol, lattice, symmetry):
    _, info = resolve_space_group(symbol)
    assert space_group_lattice_symmetry(info, lattice) == symmetry


def test_non_b_monoclinic_setting_is_not_silently_used_as_unique_b():
    model, phase = material_phase('gold')
    before = model._condition_snapshot(phase)
    with pytest.raises(ValueError, match='unique axis b'):
        model.set_space_group(0, 'P 1 1 21')
    assert model._condition_snapshot(phase) == before


def test_bundled_group_stays_locked_when_eos_is_duplicated():
    model, phase = material_phase('gold', origin='bundled')
    model.duplicate_eos_record(0, phase.params['eos_current_index'])
    before = model._condition_snapshot(phase)
    with pytest.raises(PermissionError):
        model.set_space_group(0, '221')
    assert model._condition_snapshot(phase) == before


def test_failed_condition_calculation_rolls_back_group_and_cell_model(monkeypatch):
    model, phase = material_phase('diopside')
    before = model._condition_snapshot(phase)
    lines = line_data(phase)

    def fail(*_args, **_kwargs):
        raise EosCalculationError('test EOS failure')

    monkeypatch.setattr(jcpds, 'compute_d', fail)
    with pytest.raises(EosCalculationError):
        model.set_space_group(0, 'P1')
    assert model._condition_snapshot(phase) == before
    assert line_data(phase) == lines
