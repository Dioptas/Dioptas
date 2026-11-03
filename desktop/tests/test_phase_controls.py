"""Phase tab routes preserve PhaseModel science, ownership and Qt phase lists."""
import csv
import json
from pathlib import Path

import numpy as np
import pytest

from dioptas.desktop.session import DesktopSession
from dioptas.model import eos

DATA = Path(__file__).resolve().parents[2] / 'dioptas/tests/data'
GOLD = str(DATA / 'jcpds/au_version3.jcpds')


def call(session, command, **args):
    result = session.invoke(command, args)
    assert result['ok'], result.get('error')
    json.dumps(result, allow_nan=False)
    return result


@pytest.fixture
def session():
    result = DesktopSession()
    call(result, 'example')
    call(result, 'open_calibration', path=str(DATA / 'CeO2_Pilatus1M.poni'))
    call(result, 'integration_settings', bins=120, cake_bins=20)
    return result


def test_multifile_conditions_visibility_and_references(session):
    result = call(session, 'integration_phase', operation='load', paths=[GOLD, GOLD])
    phases = result['state']['integration']['phases']
    assert len(phases) == 2
    assert phases[0]['thermal'] is False
    assert phases[0]['referenceDetails'] == []
    call(session, 'integration_phase', operation='update', index=0, pressure=22)
    assert [p.params['pressure'] for p in session._model.phase_model.phases] == [22, 22]
    call(session, 'integration_phase', operation='same_conditions', enabled=False)
    call(session, 'integration_phase', operation='update', index=1, pressure=35)
    assert [p.params['pressure'] for p in session._model.phase_model.phases] == [22, 35]
    result = call(session, 'integration_phase', operation='visibility_all', visible=False)
    assert result['pattern']['phaseLines'] == []
    result = call(session, 'integration_phase', operation='visibility_all', visible=True)
    assert result['pattern']['phaseLines']


def test_phase_list_roundtrip_appends_and_preserves_false_names_colors_conditions(session, tmp_path):
    call(session, 'integration_phase', operation='load', paths=[GOLD, GOLD])
    call(session, 'integration_phase', operation='same_conditions', enabled=False)
    call(session, 'integration_phase', operation='update', index=0, pressure=20, color='#12ab45', visible=False)
    call(session, 'integration_phase', operation='update', index=1, pressure=50)
    session._model.phase_model.phases[0].name = 'Gold, named with comma'
    path = str(tmp_path / 'phase_list.txt')
    call(session, 'integration_phase_list', save=True, path=path)
    result = call(session, 'integration_phase_list', path=path)
    phases = result['state']['integration']['phases']
    assert len(phases) == 4
    assert phases[:2] == phases[2:]
    assert phases[2]['visible'] is False
    assert phases[2]['name'] == 'Gold, named with comma'
    assert phases[2]['color'] == '#12ab45'
    assert result['state']['integration']['sameConditions'] is False
    call(session, 'integration_phase', operation='clear')
    assert session._model.phase_model.phases == []


def test_phase_list_invalid_row_rolls_back_append(session, tmp_path):
    call(session, 'integration_phase', operation='load', path=GOLD)
    path = tmp_path / 'bad.txt'
    with path.open('w') as stream:
        csv.writer(stream).writerows([[GOLD, 'False', '#123456', 'Gold', '10', '298'], ['invalid']])
    result = session.invoke('integration_phase_list', {'path': str(path)})
    assert not result['ok']
    assert len(session._model.phase_model.phases) == 1
    assert session._model.phase_model.same_conditions


def test_database_load_uses_bundled_ownership_and_primary_assessments(session):
    catalog = call(session, 'integration_phase_catalog', query='Au')['phaseCatalog']
    assert catalog
    material = next(m for m in catalog if m['diffraction'] and m['defaultReference'] >= 0 and not m['references'][m['defaultReference']]['loadError'])
    result = call(session, 'integration_phase', operation='load_database', material_id=material['id'], reference=material['defaultReference'])
    phase = result['state']['integration']['phases'][0]
    assert phase['referenceDetails'][phase['reference']]['detail']
    editor = call(session, 'integration_phase_editor', index=0)['phaseEditor']
    assert not editor['editable']
    assert not editor['eosEditable']
    before = session._model.phase_model.phases[0].params['k0']
    rejected = session.invoke('integration_phase', dict(operation='parameter', index=0, parameter='k0', value=999))
    assert not rejected['ok']
    assert session._model.phase_model.phases[0].params['k0'] == before


def test_eos_only_catalog_cannot_load_as_diffraction_phase(session):
    catalog = call(session, 'integration_phase_catalog')['phaseCatalog']
    material = next(m for m in catalog if not m['diffraction'] and m['defaultReference'] >= 0)
    result = session.invoke('integration_phase', dict(operation='load_database', material_id=material['id'], reference=material['defaultReference']))
    assert not result['ok']
    assert 'diffraction' in result['error']
    assert session._model.phase_model.phases == []


def test_editor_changes_lattice_and_reflections_through_real_model(session, tmp_path):
    call(session, 'integration_phase', operation='load', path=GOLD)
    before = np.array(session._model.phase_model.get_phase_line_positions(0, '2th_deg', 0.406626))
    result = call(session, 'integration_phase', operation='parameter', index=0, parameter='a0', value=4.2, editor=True)
    editor = result['phaseEditor']
    assert editor['lattice']['a0'] == editor['lattice']['b0'] == editor['lattice']['c0'] == 4.2
    assert not np.allclose(before, session._model.phase_model.get_phase_line_positions(0, '2th_deg', 0.406626))
    call(session, 'integration_phase', operation='reflection', index=0, action='update', row=0, parameter='intensity', value=3)
    assert session._model.phase_model.phases[0].reflections[0].intensity == 3
    result = call(session, 'integration_phase', operation='reflection', index=0, action='remove', rows=[0, 2], editor=True)
    assert len(result['phaseEditor']['reflections']) == len(editor['reflections']) - 2
    path = str(tmp_path / 'gold.eosmat')
    call(session, 'integration_phase_export', index=0, path=path)
    restored = eos.load_material_file(path)
    assert restored.lattice.a == 4.2
    call(session, 'integration_phase', operation='parameter', index=0, parameter='a0', value=4.3)
    call(session, 'integration_phase', operation='reload', index=0)
    assert session._model.phase_model.phases[0].params['a0'] == 4.2
    assert session._model.phase_model.phase_files[0] == path


def test_prepare_cif_and_import_use_experimental_cutoff_and_wavelength(session):
    path = str(next((DATA / 'cif').glob('*.cif')))
    prepared = call(session, 'integration_phase_files', paths=[path])['phaseImport']
    assert prepared['paths'] == [path]
    assert prepared['minimumDSpacing'] > 0
    call(session, 'integration_phase', operation='load', paths=[path], minimum_d_spacing=0.8, intensity_cutoff=2)
    phase = session._model.phase_model.phases[0]
    assert phase.state.reflection_wavelength == pytest.approx(session.configuration.calibration_model.wavelength * 1e10)
    assert phase.state.reflection_q_max == pytest.approx(2 * np.pi / 0.8)
    assert phase.state.reflection_intensity_cutoff == 2


def test_phase_list_rejects_non_file_database_sources_without_writing(session, tmp_path):
    catalog = call(session, 'integration_phase_catalog', query='Au')['phaseCatalog']
    material = next(m for m in catalog if m['diffraction'] and m['defaultReference'] >= 0 and not m['references'][m['defaultReference']]['loadError'])
    call(session, 'integration_phase', operation='load_database', material_id=material['id'], reference=material['defaultReference'])
    path = tmp_path / 'database-list.txt'
    result = session.invoke('integration_phase_list', dict(save=True, path=str(path)))
    assert not result['ok']
    assert 'Save a project' in result['error']
    assert not path.exists()


def test_failed_multifile_import_keeps_existing_phases_and_color_sequence(session):
    call(session, 'integration_phase', operation='load', path=GOLD)
    model = session._model.phase_model
    counter = model._color_counter
    result = session.invoke('integration_phase', dict(operation='load', paths=[GOLD, str(DATA / 'missing.jcpds')]))
    assert not result['ok']
    assert len(model.phases) == 1
    assert model._color_counter == counter
