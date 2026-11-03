"""Editor parity with Qt entry points, including record and structure ownership."""
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest
from peritheos import get_material_document

from dioptas.desktop.session import DesktopSession
from dioptas.model import eos
from dioptas.model.PhaseModel import PhaseModel
from dioptas.model.util.eos_phase import (
    RT_EOS_TYPES, THERMAL_EOS_TYPES, thermal_parameter_signature,
)

DATA = Path(__file__).resolve().parents[2] / 'dioptas/tests/data'
GOLD = str(DATA / 'jcpds/au_version3.jcpds')


def call(s, command, **args):
    result = s.invoke(command, args)
    assert result['ok'], result.get('error')
    return result


def edit(s, operation, **args):
    return call(s, 'integration_phase', operation=operation, index=0, editor=True, **args)['phaseEditor']


@pytest.fixture
def session():
    s = DesktopSession()
    call(s, 'integration_phase', operation='load', path=GOLD)
    return s


def test_lattice_ratios_and_symmetry_match_qt_model(session):
    reference = PhaseModel()
    reference.add_jcpds(GOLD)
    reference.set_param(0, 'symmetry', 'TETRAGONAL')
    reference.set_param(0, 'c0', reference.phases[0].params['a0'] * 1.3)
    edit(session, 'parameter', parameter='symmetry', value='tetragonal')
    result = edit(session, 'editor_ratio', parameter='c/a', value=1.3)
    assert result['lattice']['c0'] == reference.phases[0].params['c0']
    np.testing.assert_allclose(session._model.phase_model.get_lines_d(0), reference.get_lines_d(0))
    rejected = session.invoke('integration_phase', dict(operation='editor_ratio', index=0, parameter='a/b', value=2))
    assert not rejected['ok']
    assert session._model.phase_model.phases[0].params['a0'] == reference.phases[0].params['a0']
    edit(session, 'parameter', parameter='symmetry', value='rhombohedral')
    result = edit(session, 'parameter', parameter='alpha0', value=87)
    assert result['lattice']['alpha0'] == result['lattice']['beta0'] == result['lattice']['gamma0'] == 87


def test_eos_types_and_complete_thermal_constructor_roundtrip(session, tmp_path):
    result = edit(session, 'editor_eos_type', value='BM2Reference')
    assert [f['key'] for f in result['eosFields']] == ['k0', 'p0']
    result = edit(session, 'editor_parameter', parameter='p0', value=2)
    assert next(f for f in result['eosFields'] if f['key'] == 'p0')['value'] == 2
    edit(session, 'editor_eos_type', value='BM3')
    result = edit(session, 'editor_thermal_type', value='MieGruneisenDebye')
    assert {f['key'] for f in result['thermalFields']} == set(thermal_parameter_signature('MieGruneisenDebye')) - {'n'}
    assert {'n', 'zc'} <= {f['key'] for f in result['eosFields']}
    result = edit(session, 'editor_thermal_parameter', parameter='theta0', value=650)
    reference = PhaseModel()
    reference.add_jcpds_object(deepcopy(session._model.phase_model.phases[0]))
    reference.set_pressure_temperature(0, 10, 800)
    edit(session, 'update', pressure=10, temperature=800)
    np.testing.assert_allclose(session._model.phase_model.get_lines_d(0), reference.get_lines_d(0))
    path = str(tmp_path / 'thermal.eosmat')
    call(session, 'integration_phase_export', index=0, path=path)
    assert eos.load_material_file(path).eos_records[0]['thermal']['parameters']['theta0'] == 650
    edit(session, 'editor_thermal_type', value='none')
    assert not session._model.phase_model.phases[0].has_thermal_expansion()
    assert all(session._model.phase_model.phases[0].params[k] == 0 for k in ('alpha_t0', 'd_alpha_dt', 'dk0dt', 'dk0pdt'))


def test_all_constructor_fields_and_option_restrictions(session):
    from dioptas.desktop.phase_editor import thermal_fields
    params = session._model.phase_model.phases[0].params
    for kind in THERMAL_EOS_TYPES:
        p = dict(params)
        p.update(thermal_type=kind, thermal_parameters={})
        assert {f['key'] for f in thermal_fields(p)} == set(thermal_parameter_signature(kind)) - {'n'}
    result = edit(session, 'editor_eos_type', value='Murnaghan')
    assert {o['value'] for o in result['eosOptions']} == set(RT_EOS_TYPES)
    assert next(o for o in result['thermalOptions'] if o['value'] == 'DoubleDebyeHelmholtz')['error']
    original = deepcopy(session._model.phase_model.phases[0].params['thermal_parameters'])
    result = session.invoke('integration_phase', dict(operation='editor_thermal_type', index=0, value='DoubleDebyeHelmholtz'))
    assert not result['ok']
    assert session._model.phase_model.phases[0].params['thermal_parameters'] == original


def test_published_copy_is_custom_and_retains_source_record(session, tmp_path):
    catalog = call(session, 'integration_phase_catalog', query='Au')['phaseCatalog']
    material = next(m for m in catalog if m['diffraction'] and m['defaultReference'] >= 0 and not m['references'][m['defaultReference']]['loadError'])
    call(session, 'integration_phase', operation='clear')
    call(session, 'integration_phase', operation='load_database', material_id=material['id'], reference=material['defaultReference'])
    model = session._model.phase_model
    source = deepcopy(model.phases[0].params['eos_records'])
    result = edit(session, 'editor_record', action='duplicate')
    assert not result['editable'] and result['eosEditable']
    assert result['recordOrigin'] == 'custom'
    edit(session, 'editor_parameter', parameter='k0', value=180)
    edit(session, 'editor_record', action='rename', value='My diagnostic EOS')
    result = edit(session, 'editor_record', action='default')
    assert result['reference'] == result['defaultReference']
    assert model.phases[0].params['eos_records'][:-1] == source
    path = str(tmp_path / 'custom.eosmat')
    call(session, 'integration_phase_export', index=0, path=path)
    loaded = eos.load_material_file(path)
    assert loaded.eos_records[-1]['label'] == 'My diagnostic EOS'
    assert loaded.eos_records[-1]['scientific_validation']['status'] == 'deferred'
    assert loaded.eos_records[-1]['eos']['parameters']['K0'] == 180
    result = edit(session, 'editor_record', action='delete')
    assert not result['eosEditable']
    assert model.phases[0].params['eos_records'] == source


def gold_copy(session):
    call(session, 'integration_phase', operation='clear')
    material = next(m for m in call(session, 'integration_phase_catalog', query='Gold')['phaseCatalog'] if m['id'] == 'gold')
    reference = next(i for i, r in enumerate(material['references']) if 'Anderson' in r['label'])
    call(session, 'integration_phase', operation='load_database', material_id='gold', reference=reference)
    return edit(session, 'editor_copy')


@pytest.mark.parametrize('identifier', [r['identifier'] for r in get_material_document('gold')['eos_records']])
def test_every_gold_record_delete_save_reload(session, tmp_path, identifier):
    copied = gold_copy(session)
    model = session._model.phase_model
    original = deepcopy(model.phases[0].state)
    before = deepcopy(model.phases[1].params['eos_records'])
    selected = next(i for i, r in enumerate(before) if r['identifier'] == identifier)
    call(session, 'integration_phase', operation='update', index=1, reference=selected)
    depends = any(r.get('derived_from_record') == identifier or r.get('pressure_scale_variant_of') == identifier for r in before)
    result = session.invoke('integration_phase', dict(operation='editor_record', index=1, action='delete', editor=True))
    if depends:
        assert not result['ok']
        assert model.phases[1].params['eos_records'] == before
    else:
        assert result['ok'], result.get('error')
    path = str(tmp_path / 'gold-copy.eosmat')
    call(session, 'integration_phase_export', editor_uid=copied['uid'], path=path)
    loaded = eos.load_material_file(path)
    expected = before if depends else [r for r in before if r['identifier'] != identifier]
    assert [r['identifier'] for r in loaded.eos_records] == [r['identifier'] for r in expected]
    for retained, previous in zip(loaded.eos_records, expected):
        assert retained['eos'] == previous['eos']
        assert retained.get('thermal') == previous.get('thermal')
    document = loaded.to_dict()
    known = {r['identifier'] for r in loaded.eos_records}
    for dataset in document.get('datasets', []):
        assert set(dataset.get('used_by_eos_records', [])) <= known
        assert all(r['eos_record'] in known for r in dataset.get('pressure_reductions', []))
        assert all(set(v['eos_records']) <= known for v in dataset.get('observation_views', []))
    restored = call(session, 'integration_phase', operation='reload', editor_uid=copied['uid'], editor=True)['phaseEditor']
    assert len(restored['references']) == len(expected)
    assert model.phases[0].state == original


def test_clear_all_records_save_structure_and_create_new_eos(session, tmp_path):
    copied = gold_copy(session)
    model = session._model.phase_model
    source = deepcopy(model.phases[0].state)
    sites = deepcopy(copied['structure']['sites'])
    reference = {k: copied['lattice'][k] for k in ('a0', 'b0', 'c0', 'alpha0', 'beta0', 'gamma0')}
    denied = session.invoke('integration_phase', dict(operation='editor_record', index=0, action='clear'))
    assert not denied['ok']
    call(session, 'integration_phase', operation='editor_thermal_type', index=1, value='MieGruneisenDebye')
    call(session, 'integration_phase', operation='editor_thermal_parameter', index=1, parameter='theta0', value=650)
    cleared = call(session, 'integration_phase', operation='editor_record', index=1, action='clear', editor=True)['phaseEditor']
    assert cleared['references'] == [] and cleared['eosEditable']
    assert cleared['structure']['sites'] == sites
    assert {k: cleared['lattice'][k] for k in reference} == reference
    assert not model.phases[1].params['eos_parameter_errors']
    assert not model.phases[1].has_thermal_expansion()
    assert model.phases[1].params['theta_t0'] == 0
    assert model.phases[1].params['gamma_t0'] == 0
    assert model.phases[1].params['q_t0'] == 1
    path = str(tmp_path / 'new-material.eosmat')
    call(session, 'integration_phase_export', index=1, path=path)
    assert eos.load_material_file(path).eos_records == []
    call(session, 'integration_phase', operation='reload', index=1)
    call(session, 'integration_phase', operation='editor_parameter', index=1, parameter='k0', value=180)
    call(session, 'integration_phase', operation='editor_parameter', index=1, parameter='k0p0', value=4)
    call(session, 'integration_phase', operation='editor_record', index=1, action='add')
    call(session, 'integration_phase', operation='editor_record', index=1, action='rename', value='My new EoS')
    call(session, 'integration_phase_export', index=1, save_current=True)
    saved = eos.load_material_file(path)
    assert len(saved.eos_records) == 1
    assert saved.eos_records[0]['label'] == 'My new EoS'
    assert saved.eos_records[0]['eos']['parameters']['K0'] == 180
    assert saved.atom_sites == sites
    assert model.phases[0].state == source


def test_record_dataset_links_preserve_shared_measurements():
    from dioptas.model.eos.record_links import remove_record_links
    document = dict(datasets=[dict(identifier='shared', rows=[[1., 2.]], columns=['P', 'V'],
        used_by_eos_records=['removed', 'kept'],
        pressure_reductions=[dict(eos_record='removed', source='one'), dict(eos_record='kept', source='two')],
        observation_views=[dict(eos_records=['removed'], note='drop'), dict(eos_records=['removed', 'kept'], note='retain')]),
        dict(identifier='only-removed', used_by_eos_records=['removed']),
        dict(identifier='unlinked', used_by_eos_records=[], rows=[[3., 4.]])])
    before = deepcopy(document)
    result = remove_record_links(document, {'removed'})
    assert document == before
    assert [d['identifier'] for d in result['datasets']] == ['shared', 'unlinked']
    shared = result['datasets'][0]
    assert shared['rows'] == before['datasets'][0]['rows']
    assert shared['columns'] == before['datasets'][0]['columns']
    assert shared['used_by_eos_records'] == ['kept']
    assert shared['pressure_reductions'] == [before['datasets'][0]['pressure_reductions'][1]]
    assert shared['observation_views'] == [dict(eos_records=['kept'], note='retain')]


def test_failed_record_deletion_restores_model_without_desktop_wrapper(session, monkeypatch):
    gold_copy(session)
    model = session._model.phase_model
    phase = model.phases[1]
    index = next(i for i, r in enumerate(phase.params['eos_records']) if 'dewaele_2004_mao' in r['identifier'])
    before = deepcopy(phase.state)
    spacings = [r.d for r in phase.reflections]
    def reject(*args):
        raise ValueError('Cannot calculate the next record')
    monkeypatch.setattr(eos, 'apply_eos_record', reject)
    with pytest.raises(ValueError, match='Cannot calculate'):
        model.delete_eos_record(1, index)
    assert phase.state == before
    assert [r.d for r in phase.reflections] == spacings


def test_older_project_with_deleted_record_can_be_exported(session, tmp_path):
    gold_copy(session)
    phase = session._model.phase_model.phases[1]
    old_document = deepcopy(phase.params['material_document'])
    index = next(i for i, r in enumerate(phase.params['eos_records']) if 'dewaele_2004_mao' in r['identifier'])
    deleted_id = phase.params['eos_records'][index]['identifier']
    session._model.phase_model.delete_eos_record(1, index)
    phase.params['material_document'] = old_document  # State written by the earlier editor.
    project = str(tmp_path / 'old-edited-project.dio')
    call(session, 'save_project', path=project)
    restored = DesktopSession()
    call(restored, 'open_project', path=project)
    path = str(tmp_path / 'recovered.eosmat')
    call(restored, 'integration_phase_export', index=1, path=path)
    loaded = eos.load_material_file(path)
    assert deleted_id not in {r['identifier'] for r in loaded.eos_records}
    assert loaded.atom_sites == phase.params['material_document']['atom_sites']
    assert all(r['eos_record'] != deleted_id for dataset in loaded.to_dict().get('datasets', [])
               for r in dataset.get('pressure_reductions', []))


def test_atomic_edits_match_qt_and_preserve_composition_provenance(session, tmp_path):
    path = str(DATA / 'cif/fcc.cif')
    call(session, 'integration_phase', operation='clear')
    call(session, 'integration_phase', operation='load', path=path, minimum_d_spacing=1.5)
    model = session._model.phase_model
    reference = PhaseModel()
    reference.add_jcpds_object(deepcopy(model.phases[0]))
    wavelength = session.configuration.calibration_model.wavelength * 1e10
    reference.set_atom_site_parameter(0, 0, 'occupancy', .75, wavelength_angstrom=wavelength)
    original_z = model.phases[0].params['zc']
    result = edit(session, 'editor_site', action='update', row=0, parameter='occupancy', value=.75)
    np.testing.assert_allclose(model.get_lines_d(0), reference.get_lines_d(0))
    assert result['structure']['modified']
    assert model.phases[0].params['zc'] == original_z
    assert result['structure']['storedZ'] == original_z
    sites = deepcopy(model.phases[0].params['material_document']['atom_sites'])
    rejected = session.invoke('integration_phase', dict(operation='editor_site', index=0, action='update', row=0, parameter='occupancy', value=1.5))
    assert not rejected['ok']
    assert model.phases[0].params['material_document']['atom_sites'] == sites
    reference.set_space_group(0, 'P 1', wavelength_angstrom=wavelength)
    result = edit(session, 'editor_space_group', value='P 1')
    np.testing.assert_allclose(model.get_lines_d(0), reference.get_lines_d(0))
    assert result['structure']['spaceGroupNumber'] == 1
    result = edit(session, 'editor_site', action='add', site=dict(element='Au', x=.2, y=.3, z=.4, occupancy=.5))
    assert len(result['structure']['sites']) == len(sites) + 1
    result = edit(session, 'editor_site', action='remove', rows=[len(sites)])
    assert len(result['structure']['sites']) == len(sites)
    path = str(tmp_path / 'edited.eosmat')
    call(session, 'integration_phase_export', index=0, path=path)
    loaded = eos.load_material_file(path)
    assert loaded.atom_sites[0]['occupancy'] == .75
    assert loaded.source['structure_modified']


def test_export_reflections_and_unique_deletion(session, tmp_path):
    original = call(session, 'integration_phase_editor', index=0)['phaseEditor']
    path = str(tmp_path / 'reflections')
    result = call(session, 'integration_phase_export', index=0, format='txt', path=path)
    text = Path(result['savedPath']).read_text()
    assert text.startswith('h\tk\tl\tIntensity\td0 (Å)\td (Å)\t2θ0 (°)\t2θ (°)\tQ0 (Å⁻¹)\tQ (Å⁻¹)\n')
    assert len(text.splitlines()) == len(original['reflections']) + 1
    result = edit(session, 'reflection', action='remove', rows=[2, 0, 2])
    assert len(result['reflections']) == len(original['reflections']) - 2


def test_constructor_alphakt_survives_legacy_record_selection_and_export(session, tmp_path):
    edit(session, 'editor_thermal_type', value='AlphaKT')
    edit(session, 'editor_thermal_parameter', parameter='alpha1', value=1e-8)
    edit(session, 'editor_thermal_parameter', parameter='thermal_expansion_law', value='linear_temperature')
    edit(session, 'update', pressure=15, temperature=1000)
    model = session._model.phase_model
    expected = model.phases[0].params['v']
    result = edit(session, 'editor_record', action='add')
    assert result['thermalType'] == 'AlphaKT'
    assert model.phases[0].params['v'] == pytest.approx(expected)
    path = str(tmp_path / 'constructor.eosmat')
    call(session, 'integration_phase_export', index=0, path=path)
    restored = eos.build_jcpds(eos.load_material_file(path))
    restored.compute_d(pressure=15, temperature=1000)
    assert restored.params['thermal_type'] == 'AlphaKT'
    assert restored.params['v'] == pytest.approx(expected)
    # Selecting a constructor on an existing v2 record also keeps the marker.
    edit(session, 'editor_thermal_type', value='none')
    result = edit(session, 'editor_thermal_type', value='AlphaKT')
    assert result['recordData']['thermal']['model']
    assert result['thermalType'] == 'AlphaKT'


def test_material_normalization_allows_holzapfel_without_invented_values(session):
    initial = call(session, 'integration_phase_editor', index=0)['phaseEditor']
    assert {f['key'] for f in initial['materialFields']} == {'n', 'z', 'zc'}
    edit(session, 'editor_parameter', parameter='n', value=1)
    edit(session, 'editor_parameter', parameter='z', value=79)
    edit(session, 'editor_parameter', parameter='zc', value=4)
    result = edit(session, 'editor_eos_type', value='Holzapfel')
    assert {'n', 'z', 'zc'} <= {f['key'] for f in result['eosFields']}
    assert result['eosType'] == 'Holzapfel'
    # Inline editor rejections carry the unchanged authoritative data.
    before = result['lattice']
    result = call(session, 'integration_phase', operation='editor_transaction', edit_operation='editor_parameter', index=0, editor=True, parameter='zc', value=1.5)['phaseEditor']
    assert result['editError']
    assert result['lattice'] == before
    assert next(f for f in result['eosFields'] if f['key'] == 'zc')['value'] == 4


def test_jcpds_export_rejects_scientific_loss_before_creating_a_file(session, tmp_path):
    legacy = str(tmp_path / 'legacy.jcpds')
    call(session, 'integration_phase_export', index=0, path=legacy)
    assert Path(legacy).is_file()
    edit(session, 'editor_eos_type', value='Vinet')
    path = tmp_path / 'unsupported.jcpds'
    result = session.invoke('integration_phase_export', dict(index=0, path=str(path)))
    assert not result['ok'] and '.eosmat' in result['error']
    assert not path.exists()
    edit(session, 'editor_eos_type', value='BM3')
    edit(session, 'editor_record', action='add')
    result = session.invoke('integration_phase_export', dict(index=0, path=str(path)))
    assert not result['ok'] and not path.exists()


def test_editable_material_copy_preserves_values_provenance_and_original(session, tmp_path):
    catalog = call(session, 'integration_phase_catalog', query='Au')['phaseCatalog']
    material = next(m for m in catalog if m['diffraction'] and m['defaultReference'] >= 0 and not m['references'][m['defaultReference']]['loadError'])
    call(session, 'integration_phase', operation='clear')
    call(session, 'integration_phase', operation='load_database', material_id=material['id'], reference=material['defaultReference'])
    edit(session, 'update', pressure=12)
    source = call(session, 'integration_phase_editor', index=0)['phaseEditor']
    source_params = deepcopy(session._model.phase_model.phases[0].state)
    result = edit(session, 'editor_copy')
    assert result['index'] == 1 and result['uid'] != source['uid']
    assert result['editable'] and result['eosEditable'] and not result['canReload']
    assert result['lattice'] == source['lattice']
    assert result['reflections'] == source['reflections']
    assert result['pressure'] == 12
    assert result['copiedFrom']
    model = session._model.phase_model
    uid = result['uid']
    call(session, 'integration_phase', operation='parameter', index=1, parameter='a0', value=result['lattice']['a0'] * 1.01)
    call(session, 'integration_phase', operation='editor_parameter', index=1, parameter='k0', value=180)
    assert model.phases[0].state == source_params
    path = str(tmp_path / 'copy.eosmat')
    call(session, 'integration_phase_export', editor_uid=uid, path=path)
    material_copy = eos.load_material_file(path)
    assert material_copy.source['copied_from']['material_identifier'] == material['id']
    assert all(r['scientific_validation']['status'] == 'deferred' for r in material_copy.eos_records)
    restored = eos.build_jcpds(material_copy, result['reference'], origin='file')
    assert restored.params['a0'] == pytest.approx(model.phases[1].params['a0'])
    project = str(tmp_path / 'copies.dio')
    call(session, 'save_project', path=project)
    call(session, 'open_project', path=project)
    assert len(session._model.phase_model.phases) == 2
    assert session._model.phase_model.is_material_editable(1)
    assert not session._model.phase_model.is_material_editable(0)


def test_native_editor_identity_survives_row_removal_and_bounds_payload(session):
    original = call(session, 'integration_phase_editor', index=0)['phaseEditor']
    copy = edit(session, 'editor_copy')
    call(session, 'integration_phase', operation='remove', index=0)
    response = call(session, 'integration_phase', operation='editor_transaction', edit_operation='parameter', index=1,
        editor=True, editor_uid=copy['uid'], editor_only=True, parameter='a0', value=4.3)
    assert set(response) == {'ok', 'phaseEditor', 'phaseRevision'}
    assert response['phaseEditor']['index'] == 0
    assert response['phaseEditor']['lattice']['a0'] == 4.3
    rejected = session.invoke('integration_phase', dict(operation='parameter', editor_uid=original['uid'], parameter='a0', value=5))
    assert not rejected['ok']
    assert session._model.phase_model.phases[0].params['a0'] == 4.3


def test_complete_reflection_positions_match_qt_reference_and_current_lattices(session):
    result = edit(session, 'update', pressure=30)
    from dioptas.widgets.integration.PhaseEditorWidget import ReflectionTableModel
    wavelength = session.configuration.calibration_model.wavelength * 1e10
    qt = ReflectionTableModel()
    qt.update_reflection_data(session._model.phase_model.phases[0].reflections, wavelength)
    rows = [[r[k] for k in ('h', 'k', 'l', 'intensity', 'd0', 'd', 'twoTheta0', 'twoTheta', 'q0', 'q')] for r in result['reflections']]
    np.testing.assert_allclose(rows, qt.reflection_data)


def test_native_phase_refresh_preserves_detector_view_payload(session):
    edit(session, 'parameter', parameter='a0', value=4.2)
    result = call(session, 'integration_phase_state')
    assert result['patternOnly']
    assert not {'image', 'rawImage', 'mask', 'cake', 'rings', 'map'} & result.keys()
    assert result['phaseOnly']
    assert result['state']['integration']['phases'][0]['name'].endswith('*')


def test_native_edit_avoids_building_discarded_workspace_snapshots(session, monkeypatch):
    def no_snapshot(*args, **kwargs):
        raise AssertionError('Phase edit tried to rebuild detector/map state')
    monkeypatch.setattr(session, '_snapshot', no_snapshot)
    result = call(session, 'integration_phase', operation='editor_transaction', edit_operation='parameter',
                  index=0, editor=True, editor_only=True, parameter='a0', value=4.2)
    assert result['phaseRevision'] == session._revision
    assert result['phaseEditor']['lattice']['a0'] == 4.2
    update = call(session, 'integration_phase', operation='update', index=0, pressure=10)
    assert update['phaseOnly']
    assert update['state']['integration']['phases'][0]['pressure'] == 10


def test_material_name_save_as_and_save_keep_file_independent_and_reloadable(session, tmp_path):
    original = call(session, 'integration_phase_editor', index=0)['phaseEditor']
    renamed = edit(session, 'editor_name', value='My measured gold')
    assert renamed['materialName'] == 'My measured gold'
    assert renamed['modified']
    assert renamed['lattice'] == original['lattice']
    path = str(tmp_path / 'anything-I-want.eosmat')
    result = call(session, 'integration_phase_export', index=0, path=path, format='eosmat')
    saved = result['phaseEditor']
    assert saved['filename'] == path and saved['canSaveCurrent'] and saved['canReload']
    assert saved['materialName'] == 'My measured gold' and not saved['modified']
    assert eos.load_material_file(path).name == 'My measured gold'
    edit(session, 'editor_name', value='Second material name')
    edit(session, 'parameter', parameter='a0', value=4.3)
    result = call(session, 'integration_phase_export', index=0, save_current=True, editor_only=True)
    assert result['savedPath'] == path
    assert not result['phaseEditor']['modified']
    assert eos.load_material_file(path).name == 'Second material name'
    assert eos.load_material_file(path).lattice.a == 4.3
    reloaded = edit(session, 'reload')
    assert reloaded['materialName'] == 'Second material name'
    assert reloaded['lattice']['a0'] == 4.3


def test_derived_wyckoff_labels_for_coincident_and_moved_sites(session):
    from dioptas.desktop.phase_sites import site_labels
    document = dict(space_group='F m -3 m', space_group_number=225,
        atom_sites=[dict(element='Au', x=0, y=0, z=0, occupancy=.5),
                    dict(element='Cu', x=0, y=0, z=0, occupancy=.5),
                    dict(element='Au', x=.5, y=.5, z=.5),
                    dict(element='Au', x=.25, y=.25, z=.25),
                    dict(element='Au', x=.123, y=.234, z=.345)])
    labels = site_labels(document)
    assert [site['label'] for site in labels] == ['4a', '4a', '4b', '8c', '192l']
    assert all('wyckoff' not in site for site in document['atom_sites'])
    document['space_group'] = 'R -3 m:R'
    document['space_group_number'] = 166
    assert site_labels(document)[0]['label'] == '1a'
    document['space_group'] = 'R -3 m:H'
    assert site_labels(document)[0]['label'] == '3a'


def test_wyckoff_reference_representatives_across_all_space_group_types():
    from dioptas.desktop.phase_sites import affine_space, classify_site, wyckoff_settings, hall_key
    from dioptas.model.util.phasesmith import resolve_space_group
    tested = 0
    parameters = np.array([.123456789, .271828182, .414213562])
    for number in range(1, 231):
        symbol, info = resolve_space_group(str(number))
        setting = wyckoff_settings()[(hall_key(info.hall_symbol), info.setting)]
        for multiplicity, letter, _symmetry, coordinates in setting['positions']:
            linear, origin, _projection = affine_space(coordinates)
            xyz = tuple((linear @ parameters + origin) % 1)
            label = classify_site(symbol, number, xyz)
            assert label['multiplicity'] == multiplicity, (number, letter, xyz, label)
            assert label['label'] == f'{multiplicity}{letter}', (number, letter, xyz, label)
            tested += 1
    assert tested > 1700


def test_wyckoff_representatives_in_all_hall_settings():
    from types import SimpleNamespace
    from phasesmith.io.space_groups import space_group_from_hall_symbol
    from dioptas.desktop.phase_sites import affine_space, classify_with_info, wyckoff_settings
    tested = 0
    parameters = np.array([.123456789, .271828182, .414213562])
    for setting in wyckoff_settings().values():
        info = SimpleNamespace(number=setting['number'], hall_symbol=setting['hall'], hm_symbol=setting['hall'], setting=setting['setting'],
            space_group=space_group_from_hall_symbol(setting['hall'].replace('=', '"')))
        for multiplicity, letter, _symmetry, coordinates in setting['positions']:
            linear, origin, _projection = affine_space(coordinates)
            xyz = tuple((linear @ parameters + origin) % 1)
            result = classify_with_info(info, xyz)
            assert result['label'] == f'{multiplicity}{letter}', (setting['hall'], coordinates, result)
            tested += 1
    assert tested == 3467
