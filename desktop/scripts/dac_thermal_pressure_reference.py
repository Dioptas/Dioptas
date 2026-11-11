"""Explicit independent Qt/Peritheos reference; never imported by the native app.
Run with .venv/bin/python desktop/scripts/dac_thermal_pressure_reference.py.
"""
from copy import deepcopy
import json
from pathlib import Path
from peritheos import get_material_document
from dioptas.model import eos
from dioptas.model.PhaseModel import PhaseModel
from dioptas.model.util.jcpds import jcpds

root = Path(__file__).resolve().parents[2]
# Cover every thermal family represented in the bundled diffraction catalog,
# plus isothermal and legacy coefficient behavior. No source records are edited.
selections = [
    ('gold', 0), ('gold', 3), ('gold', 4), ('gold', 6), ('gold', 14),
    ('gold', 15), ('gold', 21), ('aragonite', 0), ('argon_fcc', 0),
    ('argon_fcc', 2), ('diamond', 3), ('diamond', 4), ('iridium', 0),
    ('iron', 11), ('mgo', 1), ('mgo', 3), ('mgo', 8), ('platinum', 1),
    ('platinum', 3), ('platinum', 16), ('mg075fe025o', 0),
]
fixtures = []
for identifier, index in selections:
    doc = get_material_document(identifier)
    record = doc['eos_records'][index]
    # Use a small reference reflection table to keep this numerical qualification
    # independent of the separate full structure/intensity implementation.
    lattice = doc['lattice']
    doc['atom_sites'] = []
    doc['peaks'] = [[1, 0, 0, lattice['a'], 100.0]]
    material = eos.Material.from_dict(doc)
    phase = eos.build_jcpds(material, record_index=index, origin='bundled')
    model = PhaseModel()
    model.add_jcpds_object(phase)
    inputs = [(0., 298.), (20., 1000.), (40., 2000.)]
    if identifier == 'argon_fcc':
        inputs = [(5., 298.), (10., 500.), (20., 1000.)]
    samples = []
    for pressure, temperature in inputs:
        model.set_dac_thermal_pressure_enabled(False)
        assert model.set_pressure_temperature(0, pressure, temperature), (identifier, index, pressure, temperature)
        for enabled, fraction in [(False, .25), (True, 0.), (True, .25), (True, .4), (True, .75), (False, .75)]:
            model.set_dac_thermal_pressure_factor(fraction)
            model.set_dac_thermal_pressure_enabled(enabled)
            assert model.params.dac_thermal_pressure_enabled == enabled, (identifier, index, enabled)
            samples.append(dict(pressure=pressure, temperature=temperature, enabled=enabled,
                                factor=fraction, volume=phase.params['v'], a=phase.params['a'],
                                d=phase.reflections[0].d))
    doc['eos_records'] = [record]
    # Keep linked dataset provenance while restricting links to this selected
    # reference fixture. Numerical parameters and selected source data are intact.
    selected = record['identifier']
    for dataset in doc.get('datasets', []):
        if 'used_by_eos_records' in dataset:
            dataset['used_by_eos_records'] = [r for r in dataset['used_by_eos_records'] if r == selected]
        if 'pressure_reductions' in dataset:
            dataset['pressure_reductions'] = [r for r in dataset['pressure_reductions'] if r.get('eos_record') == selected]
        for view in dataset.get('observation_views', []):
            if 'eos_records' in view:
                view['eos_records'] = [r for r in view['eos_records'] if r == selected]

    fixtures.append(dict(id=f'{identifier}:{index}', document=doc, samples=samples))
    print(identifier, index, record['eos']['type'], (record.get('thermal') or {}).get('type'), flush=True)
# Legacy JCPDS input is consumed by its original coefficient path, including
# negative pressure and temperature=0's established 298 K interpretation.
phase = jcpds()
phase.load_file(str(root / 'dioptas/tests/data/jcpds/au_version3.jcpds'))
model = PhaseModel(); model.add_jcpds_object(phase)
samples=[]
for pressure, temperature in [(0., 0.), (20., 1000.), (40., 2000.), (-1., 500.)]:
    assert model.set_pressure_temperature(0, pressure, temperature)
    for enabled, fraction in [(False,.25),(True,0.),(True,.25),(True,.4),(True,.75)]:
        model.set_dac_thermal_pressure_factor(fraction);model.set_dac_thermal_pressure_enabled(enabled)
        samples.append(dict(pressure=pressure,temperature=temperature,enabled=enabled,factor=fraction,
                            volume=phase.params['v'],a=phase.params['a'],d=phase.reflections[0].d))
fixtures.append(dict(id='legacy-au',path='dioptas/tests/data/jcpds/au_version3.jcpds',samples=samples))
out = root / 'desktop/backend/tests/fixtures/dac-qt-reference.json'
out.write_text(json.dumps(dict(reference='Qt PhaseModel + installed Peritheos 0.17.0; explicit reference only', cases=fixtures), indent=2)+'\n')
print(out, sum(len(f['samples']) for f in fixtures), 'states')
