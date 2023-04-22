# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
# Principal author: Clemens Prescher (clemens.prescher@gmail.com)
# Copyright (C) 2014-2019 GSECARS, University of Chicago, USA
# Copyright (C) 2015-2018 Institute for Geology and Mineralogy, University of Cologne, Germany
# Copyright (C) 2019-2020 DESY, Hamburg, Germany
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import unittest
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
