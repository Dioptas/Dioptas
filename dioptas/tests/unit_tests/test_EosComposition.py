"""Peritheos 0.9 composition, editor serialization, and compatibility contracts."""
from copy import deepcopy
import inspect

from peritheos.eos import rt, thermal as thermal_models
from peritheos.errors import ConfigurationError

import pytest
from peritheos import Material as PeritheosMaterial, get_material_document

from ...model import eos
from ...model.PhaseModel import PhaseModel
from ...model.util.eos_phase import EosPhase, RT_EOS_TYPES, thermal_compatibility_error
from .test_EosPhase import GOLD, GOLD_SOKOLOVA


@pytest.mark.parametrize('reference', RT_EOS_TYPES)
@pytest.mark.parametrize('thermal', ['AlphaKT', 'Sokolova2016'])
def test_composable_thermal_models_roundtrip(reference, thermal):
    parameters = ({'Tr': 298.15, 'alpha0': 3e-5, 'dK_dT': -.01}
                  if thermal == 'AlphaKT' else GOLD_SOKOLOVA)
    engine = EosPhase(reference, {**GOLD, 'K0_double_prime': -.04},
                      n=1, z=79, formula_units_per_cell=4,
                      thermal_type=thermal, thermal_parameters=parameters)
    volume = engine.volume(20., 1000.)
    assert engine.pressure(volume, 1000.) == pytest.approx(20., abs=1e-6)


@pytest.mark.parametrize('reference', ['BM2', 'BM3', 'BM4', 'Vinet'])
@pytest.mark.parametrize('thermal', ['DoubleDebyeHelmholtz', 'DoubleDebyeLogMomentHelmholtz'])
@pytest.mark.parametrize('temperature_ref', [None, 300.])
def test_double_debye_compositions_survive_edit_and_save(tmp_path, reference, thermal, temperature_ref):
    document = get_material_document('diamond')
    index = next(i for i, record in enumerate(document['eos_records'])
                 if record.get('thermal', {}).get('type') == thermal)
    phase = eos.build_jcpds(eos.Material.from_dict(document), record_index=index, origin='bundled')
    model = PhaseModel()
    model.add_jcpds_object(phase, filename=phase.filename)
    custom = model.duplicate_eos_record(0, index)
    parameters = {**phase.params['thermal_parameters'], 'Tr': temperature_ref}
    model.set_param(0, 'thermal_parameters', parameters)
    model.set_eos_type(0, reference)
    assert model.set_pressure_temperature(0, 20., 1000.)
    expected_volume = phase.params['v']
    record = phase.params['eos_records'][custom]
    # Also exercise the standalone constructor used for unsaved phases.
    standalone = EosPhase(reference, record['eos']['parameters'], n=phase.params['n'],
                          formula_units_per_cell=phase.params['zc'], thermal_type=thermal,
                          thermal_parameters=parameters)
    assert standalone.volume(20., 1000.) == pytest.approx(expected_volume)
    path = tmp_path / 'diamond.eosmat'
    eos.save_material_file(str(path), eos.material_from_jcpds(phase))
    loaded = eos.load_material_file(str(path))
    restored = PeritheosMaterial.from_eosmat(loaded.to_dict(),
        record_identifiers=[record['identifier']], require_primary_validation=False).eos_records[0]
    assert restored.volume(20., 1000., check_validity=False) == pytest.approx(expected_volume)
    assert restored.pressure(expected_volume, 1000., check_validity=False) == pytest.approx(20., abs=1e-6)
    assert loaded.eos_records[custom]['thermal']['parameters']['Tr'] == temperature_ref


def test_incompatible_alphakt_edit_does_not_mutate_record():
    document = get_material_document('gold')
    index = next(i for i, r in enumerate(document['eos_records'])
                 if r['identifier'] == 'gold_hirose_2008_bm3_fit2')
    phase = eos.build_jcpds(eos.Material.from_dict(document), record_index=index, origin='bundled')
    model = PhaseModel()
    model.add_jcpds_object(phase, filename=phase.filename)
    model.duplicate_eos_record(0, index)
    before = deepcopy(phase.state)
    with pytest.raises(ValueError, match='K′ shift'):
        model.set_eos_type(0, 'BM2')
    assert phase.state == before
    assert phase.params['thermal_parameters']['bulk_modulus_law'] == 'reciprocal_cubic'
    assert phase.params['thermal_parameters']['thermal_expansion_law'] == 'linear_temperature'


@pytest.mark.parametrize('reference', RT_EOS_TYPES)
def test_compatibility_checks_agree_with_peritheos(reference):
    cls = getattr(rt, reference)
    values = {**GOLD, 'K0_double_prime': -.04, 'n': 1., 'Z': 79.}
    base = cls(**{name: values[name] for name in inspect.signature(cls).parameters})
    diamond = get_material_document('diamond')
    double_parameters = next(r['thermal']['parameters'] for r in diamond['eos_records']
                             if r.get('thermal', {}).get('type') == 'DoubleDebyeHelmholtz')
    cases = [
        ('DoubleDebyeHelmholtz', thermal_models.DoubleDebyeHelmholtz, double_parameters),
        ('ThermalModifiedTait', thermal_models.ThermalModifiedTait,
         {'Tr': 300., 'theta': 700., 'alpha0': 3e-5, 'n': 1.}),
        ('AlphaKT', thermal_models.ThermalReferenceStateEOS,
         {'Tr': 300., 'alpha0': 3e-5, 'dK_dT': -.01, 'kprime_log_coefficient': .0003}),
    ]
    for name, constructor, parameters in cases:
        try:
            constructor(rt_eos=base, **parameters)
            supported = True
        except (ValueError, ConfigurationError):
            supported = False
        assert bool(thermal_compatibility_error(reference, name, parameters)) == (not supported)


def test_edit_updates_both_locations_of_thermal_configuration():
    document = get_material_document('gold')
    index = next(i for i, r in enumerate(document['eos_records'])
                 if r['identifier'] == 'gold_hirose_2008_bm3_fit1')
    component = document['eos_records'][index]['thermal']
    component['configuration'] = {'reference_volume_law': 'integrated_expansivity'}
    component['reference_volume_law'] = 'integrated_expansivity'
    phase = eos.build_jcpds(eos.Material.from_dict(document), record_index=index, origin='file')
    model = PhaseModel()
    model.add_jcpds_object(phase, filename=phase.filename)
    parameters = {**phase.params['thermal_parameters'],
                  'thermal_expansion_law': 'constant', 'alpha1': 0.,
                  'reference_volume_law': 'linear_temperature'}
    model.set_param(0, 'thermal_parameters', parameters)
    saved = phase.params['eos_records'][index]['thermal']
    assert saved['reference_volume_law'] == 'linear_temperature'
    assert saved['configuration']['reference_volume_law'] == 'linear_temperature'
    native = EosPhase.from_jcpds(phase, with_thermal=True)
    assert native._eos.reference_volume_law == 'linear_temperature'
