"""Database browser contract, original Qt parity, and explicit loading safeguards."""
from copy import deepcopy
import json
from unittest.mock import patch

import pytest

from dioptas.desktop.phases import load_error
from dioptas.desktop.phase_database import catalog_payload, database_material, open_documentation
from dioptas.desktop.session import DesktopSession
from dioptas.model import eos
from dioptas.controller.integration.phase.EosDatabaseController import _diffraction_status, _record_row
from dioptas.model.eos.assumed_structure import can_assume_tetragonal_perovskite


@pytest.fixture(scope='module')
def catalog():
    result = catalog_payload('', load_error)['phaseCatalog']
    json.dumps(result, allow_nan=False)
    return result


def test_catalog_matches_qt_for_every_bundled_record(catalog):
    materials = eos.load_materials()
    assert [m['id'] for m in catalog] == [m.identifier for m in materials]
    for entry, material in zip(catalog, materials):
        assert entry['diffractionStatus'] == _diffraction_status(material)[0]
        assert entry['defaultReference'] == material.default_eos_index
        assert entry['hold'] == (material.recommendation_hold or '')
        assert len(entry['references']) == len(material.eos_records)
        for data, record in zip(entry['references'], material.eos_records):
            qt = _record_row(record)
            assert (data['eos'], data['authors'], data['year'], data['pressureRange'], data['assessment']) == (qt[0], qt[2], qt[3], qt[4], qt[8])
            assert data['sourceRecord'] == record
            assert data['parameters'] == record['eos']['parameters']
            assert data['errors'] == (record.get('parameter_errors') or {})
            assert data['fixed'] == (record.get('fixed_parameters') or [])
            assert data['recordUrl'] == eos.peritheos_record_url(material.identifier, record)
            assert data['reportUrl'] == eos.reconstruction_report_url(record)


def test_ranked_formula_search_and_no_hits():
    for query in ['Au', 'MgFe', 'Mg₀.₂Fe₀.₈O', 'periclase', 'no such material xyz']:
        assert [m['id'] for m in catalog_payload(query, load_error)['phaseCatalog']] == [m.identifier for m in eos.search_materials(query)]


def test_held_and_source_only_records_remain_distinct(catalog):
    palladium = next(m for m in catalog if m['id'] == 'palladium')
    assert palladium['defaultReference'] == -1
    assert palladium['hold']
    assert any(not r['loadError'] for r in palladium['references'])
    assert any(r['loadError'] for m in catalog for r in m['references'])
    assert any(not m['diffraction'] for m in catalog)


def test_assumed_structure_is_opt_in_and_keeps_original_catalog(catalog, tmp_path):
    session = DesktopSession()
    for material in filter(can_assume_tetragonal_perovskite, eos.load_materials()):
        original = deepcopy(material.to_dict())
        entry = next(m for m in catalog if m['id'] == material.identifier)
        assert entry['canAssumeStructure'] and entry['assumptionNote']
        assert load_error(material, material.default_eos_index)
        assumed = database_material(material, True)
        assert not load_error(assumed, assumed.default_eos_index)
        assert material.to_dict() == original
        path = tmp_path / f'{material.identifier}.eosmat'
        result = session.invoke('integration_phase_export', dict(material_id=material.identifier, path=str(path), assume_structure=True))
        assert result['ok'], result.get('error')
        loaded = eos.load_material_file(path)
        assert loaded.source['assumed_structure']['status'] == 'assumed'
        assert loaded.eos_records == material.eos_records
        loaded_phase = session.invoke('integration_phase', dict(operation='load_database', material_id=material.identifier, reference=material.default_eos_index, assume_structure=True))
        assert loaded_phase['ok'], loaded_phase.get('error')
        phase = session._model.phase_model.phases[-1]
        assert phase.reflections and 'assumed structure' in phase.name
        assert material.to_dict() == original
    with pytest.raises(ValueError):
        database_material(eos.load_materials()[0], True)
    with pytest.raises(ValueError):
        database_material(eos.load_materials()[0], 'true')


def test_open_documentation_resolves_only_the_selected_source_record():
    material = next(m for m in eos.load_materials() if m.identifier == 'gold')
    with patch('webbrowser.open', return_value=True) as opened:
        for i, record in enumerate(material.eos_records):
            open_documentation(material, i, 'record')
            assert opened.call_args.args[0] == eos.peritheos_record_url(material.identifier, record)
        with pytest.raises(ValueError):
            open_documentation(material, -1, 'record')
        with pytest.raises(ValueError):
            open_documentation(material, 0, 'https://example.org')
    with patch('webbrowser.open', return_value=False), pytest.raises(ValueError, match='system browser'):
        open_documentation(material, 0, 'record')
