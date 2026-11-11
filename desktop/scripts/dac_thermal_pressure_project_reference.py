"""Explicit Qt format-2 project writer/reader for native interoperability QA."""
import json
import sys
from pathlib import Path
from peritheos import get_material_document
from dioptas.model import eos
from dioptas.model.DioptasModel import DioptasModel

mode, directory = sys.argv[1:]
directory = Path(directory)
if mode == 'write':
    model = DioptasModel()
    phase = eos.build_jcpds(eos.Material.from_dict(get_material_document('gold')), record_index=4, origin='bundled')
    model.phase_model.add_jcpds_object(phase)
    model.phase_model.set_pressure_temperature(0, 40, 2000)
    model.phase_model.set_dac_thermal_pressure_factor(.4)
    model.phase_model.set_dac_thermal_pressure_enabled(True)
    model.add_configuration()
    model.save(str(directory / 'qt-factor.dio'))
    (directory / 'expected.json').write_text(json.dumps(dict(volume=phase.params['v'],factor=.4,pressure=40,temperature=2000)))
else:
    model = DioptasModel();model.load(str(directory / 'native-factor.dio'))
    expected=json.loads((directory / 'expected.json').read_text())
    assert model.phase_model.params.dac_thermal_pressure_enabled
    assert model.phase_model.params.dac_thermal_pressure_factor == expected['factor']
    assert len(model.configurations)==2
    phase=model.phase_model.phases[0]
    assert phase.params['pressure']==40 and phase.params['temperature']==2000
    assert abs(phase.params['v']-expected['volume'])<2e-7*expected['volume']
    print(json.dumps(dict(qtReopenedNative=True,volume=phase.params['v'],factor=expected['factor'])))
