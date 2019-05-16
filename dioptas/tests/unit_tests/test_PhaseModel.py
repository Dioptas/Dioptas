# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
# Principal author: Clemens Prescher (clemens.prescher@gmail.com)
# Copyright (C) 2014-2019 GSECARS, University of Chicago, USA
# Copyright (C) 2015-2018 Institute for Geology and Mineralogy, University of Cologne, Germany
# Copyright (C) 2019 DESY, Hamburg, Germany
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

from ...model.PhaseModel import PhaseModel

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')
jcpds_path = os.path.join(data_path, 'jcpds')


class PhaseModelTest(unittest.TestCase):
    def setUp(self):
        self.phase_model = PhaseModel()

    def load_phase(self, filename):
        self.phase_model.add_jcpds(os.path.join(jcpds_path, filename))

    def test_same_conditions_set_pressure(self):
        self.load_phase('ar.jcpds')
        self.load_phase('pt.jcpds')

        self.assertEqual(self.phase_model.phases[0].params['pressure'], 0)
        self.assertEqual(self.phase_model.phases[1].params['pressure'], 0)
        self.assertTrue(self.phase_model.same_conditions)

        self.phase_model.set_pressure(0, 10)

        self.assertEqual(self.phase_model.phases[0].params['pressure'], 10)
        self.assertEqual(self.phase_model.phases[1].params['pressure'], 10)

        self.phase_model.same_conditions = False
        self.phase_model.set_pressure(1, 5)
        self.assertEqual(self.phase_model.phases[0].params['pressure'], 10)
        self.assertEqual(self.phase_model.phases[1].params['pressure'], 5)

    def test_same_conditions_set_temperature(self):
        self.load_phase('pt.jcpds')
        self.load_phase('pt.jcpds')

        self.assertEqual(self.phase_model.phases[0].params['temperature'], 298)
        self.assertEqual(self.phase_model.phases[1].params['temperature'], 298)
        self.assertTrue(self.phase_model.same_conditions)

        self.phase_model.set_temperature(0, 2000)

        self.assertEqual(self.phase_model.phases[1].params['temperature'], 2000)
        self.assertEqual(self.phase_model.phases[0].params['temperature'], 2000)

        self.phase_model.same_conditions = False
        self.phase_model.set_temperature(1, 1500)
        self.assertEqual(self.phase_model.phases[0].params['temperature'], 2000)
        self.assertEqual(self.phase_model.phases[1].params['temperature'], 1500)

    def test_set_temperature_with_no_thermal_expanstion(self):
        self.load_phase('ar.jcpds')

        self.assertEqual(self.phase_model.phases[0].params['temperature'], 298)
        self.assertFalse(self.phase_model.phases[0].has_thermal_expansion())

        self.phase_model.set_temperature(0, 2000)

        # since there is no thermal expansion defined the temperature should stay at ambient
        self.assertEqual(self.phase_model.phases[0].params['temperature'], 298)

