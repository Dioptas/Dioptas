# SPDX-License-Identifier: MIT

import os

import pytest

from ...model.PhaseModel import PhaseModel

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')
jcpds_path = os.path.join(data_path, 'jcpds')


@pytest.fixture
def phase_model():
    return PhaseModel()


def load_phase(phase_model, filename):
    phase_model.add_jcpds(os.path.join(jcpds_path, filename))


def test_same_conditions_set_pressure(phase_model):
    load_phase(phase_model, 'ar.jcpds')
    load_phase(phase_model, 'pt.jcpds')

    assert phase_model.phases[0].params['pressure'] == 0
    assert phase_model.phases[1].params['pressure'] == 0
    assert phase_model.same_conditions

    phase_model.set_pressure(0, 10)

    assert phase_model.phases[0].params['pressure'] == 10
    assert phase_model.phases[1].params['pressure'] == 10

    phase_model.same_conditions = False
    phase_model.set_pressure(1, 5)
    assert phase_model.phases[0].params['pressure'] == 10
    assert phase_model.phases[1].params['pressure'] == 5


def test_same_conditions_set_temperature(phase_model: PhaseModel):
    load_phase(phase_model, 'pt.jcpds')
    load_phase(phase_model, 'pt.jcpds')

    assert phase_model.phases[0].params['temperature'] == 298
    assert phase_model.phases[1].params['temperature'] == 298
    assert phase_model.same_conditions

    phase_model.set_temperature(1, 2000)

    assert phase_model.phases[0].params['temperature'] == 2000
    assert phase_model.phases[1].params['temperature'] == 2000

    phase_model.same_conditions = False
    phase_model.set_temperature(1, 1500)
    assert phase_model.phases[0].params['temperature'] == 2000
    assert phase_model.phases[1].params['temperature'] == 1500


def test_set_temperature_with_no_thermal_expansion(phase_model):
    load_phase(phase_model, 'ar.jcpds')

    assert phase_model.phases[0].params['temperature'] == 298
    assert not phase_model.phases[0].has_thermal_expansion()

    phase_model.set_temperature(0, 2000)

    # since there is no thermal expansion defined the temperature should stay at ambient
    assert phase_model.phases[0].params['temperature'] == 298


def test_reload_phase(phase_model: PhaseModel):
    load_phase(phase_model, 'ar.jcpds')
    num_refl = len(phase_model.reflections[0])
    phase_model.delete_reflection(0, 0)
    phase_model.delete_reflection(0, 0)
    phase_model.set_pressure(0, 5)
    old_a0 = phase_model.phases[0].params['a0']
    phase_model.set_param(0, 'a0', 5)

    phase_model.reload(0)

    assert len(phase_model.reflections[0]) == num_refl
    assert phase_model.phases[0].params['a0'] == old_a0
    assert phase_model.phases[0].params['pressure'] == 5
