"""DAC confinement is a global experiment setting, separate from material data."""
from copy import deepcopy

import numpy as np
import pytest
from peritheos import Material as PeritheosMaterial, get_material_document

from ...model import eos
from ...model.DioptasModel import DioptasModel
from ...model.PhaseModel import PhaseModel
from ...model.util.eos_phase import EosPhase
from ...model.util.jcpds import EosCalculationError
from ...model.util.phasesmith import material_has_diffraction_data


def gold_phase():
    material = eos.Material.from_dict(get_material_document('gold'))
    return eos.build_jcpds(material, origin='bundled')


def reference_record(phase):
    record = phase.params['eos_records'][phase.params['eos_current_index']]
    return PeritheosMaterial.from_eosmat({
        **phase.params['material_document'],
        'eos_records': phase.params['eos_records'],
    }, record_identifiers=[record['identifier']]).eos_records[0]


@pytest.mark.parametrize('factor', [0.0, 0.25, 0.75])
def test_confinement_matches_peritheos_and_preserves_cold_pressure(factor):
    model = PhaseModel()
    phase = gold_phase()
    model.add_jcpds_object(phase)
    assert model.set_pressure_temperature(0, 40.0, 2000.0)
    isobaric = phase.params['v']
    source = deepcopy(phase.params['eos_records'])
    model.set_dac_thermal_pressure_factor(factor)
    model.set_dac_thermal_pressure_enabled(True)

    record = reference_record(phase)
    expected = record.volume_with_dac_confinement(40.0, 2000.0, f_dac=factor)
    assert phase.params['v'] == pytest.approx(expected)
    assert phase.params['v'] <= isobaric
    assert phase.params['pressure'] == 40.0
    assert phase.params['temperature'] == 2000.0
    assert phase.params['eos_records'] == source
    assert not phase.params['modified']
    assert all(r.d == pytest.approx(r.d0 * (expected / phase.params['v0'])**(1/3))
               for r in phase.reflections)
    model.set_dac_thermal_pressure_enabled(False)
    assert phase.params['v'] == pytest.approx(isobaric)


def test_all_bundled_thermal_phase_records_match_dac_solver():
    checked = 0
    for material in eos.load_materials():
        if not material_has_diffraction_data(material):
            continue
        for index, record in enumerate(material.eos_records):
            if not record.get('thermal'):
                continue
            phase = eos.build_jcpds(material, record_index=index, origin='bundled')
            model = PhaseModel()
            model.add_jcpds_object(phase)
            assert model.set_pressure_temperature(0, 20.0, 1000.0)
            model.set_dac_thermal_pressure_enabled(True)
            assert model.params.dac_thermal_pressure_enabled
            expected = reference_record(phase).volume_with_dac_confinement(
                20.0, 1000.0, f_dac=0.25)
            assert phase.params['v'] == pytest.approx(expected), record['identifier']
            checked += 1
    assert checked > 50


def test_direct_thermal_engine_converts_molar_volume():
    engine = EosPhase('BM3', {'V0': 67.85, 'K0': 167, 'K0_prime': 6},
                      n=1, formula_units_per_cell=4,
                      thermal_type='MieGruneisenDebye',
                      thermal_parameters={'Tr': 300, 'theta0': 170,
                                          'gamma0': 2.5, 'q': 1})
    heated = engine.volume_with_dac_confinement(40, 2000, 0.25)
    assert engine.volume(40, 300) < heated < engine.volume(40, 2000)
    expected_pressure = 40 + engine._eos.dac_thermal_pressure(
        heated * engine._scale, 2000, 0.25)
    assert engine.pressure(heated, 2000) == pytest.approx(expected_pressure)


def test_global_setting_applies_with_individual_conditions_and_new_phases():
    model = PhaseModel()
    model.same_conditions = False
    for pressure, temperature in [(20, 1000), (40, 1500)]:
        model.add_jcpds_object(gold_phase())
        model.set_pressure_temperature(len(model.phases)-1, pressure, temperature)
    old_volumes = [p.params['v'] for p in model.phases]
    model.set_dac_thermal_pressure_enabled(True)
    assert all(p.params['v'] < old for p, old in zip(model.phases, old_volumes))
    model.set_dac_thermal_pressure_factor(0.5)
    newcomer = gold_phase()
    newcomer.compute_d(30, 1200)
    model.add_jcpds_object(newcomer)
    assert newcomer.params['v'] == pytest.approx(
        reference_record(newcomer).volume_with_dac_confinement(30, 1200, f_dac=0.5))
    # Reference changes and later P/T edits retain the global correction.
    alternate = next(i for i, r in enumerate(newcomer.params['eos_records'])
                     if r.get('thermal', {}).get('type') == 'LogVolumeThermalPressure')
    assert model.set_eos_reference(2, alternate)
    assert model.set_temperature(2, 1600)
    assert model.set_pressure(2, 35)
    assert newcomer.params['v'] == pytest.approx(
        reference_record(newcomer).volume_with_dac_confinement(35, 1600, f_dac=0.5))


def test_isothermal_phase_is_unchanged():
    material = eos.Material.from_dict(get_material_document('gold'))
    index = next(i for i, r in enumerate(material.eos_records) if not r.get('thermal'))
    phase = eos.build_jcpds(material, record_index=index, origin='bundled')
    model = PhaseModel()
    model.add_jcpds_object(phase)
    model.set_pressure(0, 40)
    before = phase.params['v']
    model.set_dac_thermal_pressure_enabled(True)
    assert phase.params['v'] == before


@pytest.mark.parametrize('factor', [-0.1, 1.0, float('nan'), float('inf')])
def test_invalid_fraction_does_not_change_setting(factor):
    model = PhaseModel()
    with pytest.raises(ValueError, match='fraction'):
        model.set_dac_thermal_pressure_factor(factor)
    assert model.params.dac_thermal_pressure_factor == 0.25


def test_failed_global_change_rolls_back_all_phases_and_history(monkeypatch):
    model = DioptasModel()
    phases = model.phase_model
    for _ in range(2):
        phases.add_jcpds_object(gold_phase())
    phases.set_pressure_temperature(0, 40, 1500)
    phases.set_pressure_temperature(1, 40, 2000)
    model.history.reset()
    volumes = [p.params['v'] for p in phases.phases]
    reflections = [[r.d for r in p.reflections] for p in phases.phases]
    original = phases.phases[1].compute_d

    def reject_correction(*args, **kwargs):
        if phases.phases[1].params.get('dac_thermal_pressure_factor') is not None:
            raise EosCalculationError('no physical DAC volume')
        return original(*args, **kwargs)

    monkeypatch.setattr(phases.phases[1], 'compute_d', reject_correction)
    phases.set_dac_thermal_pressure_enabled(True)
    assert not phases.params.dac_thermal_pressure_enabled
    assert [p.params['v'] for p in phases.phases] == volumes
    assert [[r.d for r in p.reflections] for p in phases.phases] == reflections
    assert not model.history.can_undo


def test_project_round_trip_and_old_project_defaults(tmp_path):
    import h5py
    import json

    model = DioptasModel()
    model.phase_model.add_jcpds_object(gold_phase())
    model.phase_model.set_pressure_temperature(0, 40, 2000)
    model.phase_model.set_dac_thermal_pressure_factor(0.4)
    model.phase_model.set_dac_thermal_pressure_enabled(True)
    expected = model.phase_model.phases[0].params['v']
    path = str(tmp_path / 'confined.dio')
    model.save(path)
    loaded = DioptasModel()
    loaded.load(path)
    assert loaded.phase_model.params.dac_thermal_pressure_enabled
    assert loaded.phase_model.params.dac_thermal_pressure_factor == 0.4
    assert loaded.phase_model.phases[0].params['v'] == pytest.approx(expected)
    with h5py.File(path, 'r+') as file:
        state = json.loads(file['state'][()])
        state['phase'].pop('dac_thermal_pressure_enabled')
        state['phase'].pop('dac_thermal_pressure_factor')
        del file['state']
        file.create_dataset('state', data=json.dumps(state))
    loaded.load(path)
    assert not loaded.phase_model.params.dac_thermal_pressure_enabled
    assert loaded.phase_model.params.dac_thermal_pressure_factor == 0.25
    phase = loaded.phase_model.phases[0]
    assert phase.params['v'] == pytest.approx(reference_record(phase).volume(40, 2000))


def test_undo_redo_and_restored_phase_keep_global_correction():
    model = DioptasModel()
    phases = model.phase_model
    phases.add_jcpds_object(gold_phase())
    phases.set_pressure_temperature(0, 40, 2000)
    model.history.reset()
    before = phases.phases[0].params['v']
    phases.set_dac_thermal_pressure_enabled(True)
    after = phases.phases[0].params['v']
    model.history.undo()
    assert not phases.params.dac_thermal_pressure_enabled
    assert phases.phases[0].params['v'] == pytest.approx(before)
    model.history.redo()
    assert phases.params.dac_thermal_pressure_enabled
    assert phases.phases[0].params['v'] == pytest.approx(after)
    model.history.reset()
    phases.del_phase(0)
    model.history.undo()
    assert phases.phases[0].params['v'] == pytest.approx(after)
    assert 'dac_thermal_pressure_factor' not in eos.material_from_jcpds(
        phases.phases[0]).to_dict()
