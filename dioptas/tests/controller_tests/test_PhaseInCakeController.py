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
import pytest

from ..utility import QtTest
import os
import gc

from mock import MagicMock

from ...controller.integration import PhaseInCakeController
from ...model.DioptasModel import DioptasModel
from ...widgets.integration import IntegrationWidget

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')
jcpds_path = os.path.join(data_path, 'jcpds')


@pytest.fixture
def phase_in_cake_controller(integration_widget, dioptas_model):
    return PhaseInCakeController(integration_widget, dioptas_model)


@pytest.fixture
def load_phase(phase_in_cake_controller):
    def _load_phase(filename):
        phase_in_cake_controller.model.phase_model.add_jcpds(os.path.join(jcpds_path, filename))

    return _load_phase


@pytest.fixture
def load_phases(load_phase):
    load_phase('ar.jcpds')
    load_phase('ag.jcpds')
    load_phase('au_Anderson.jcpds')
    load_phase('mo.jcpds')
    load_phase('pt.jcpds')
    load_phase('re.jcpds')


def test_loading_a_phase(load_phase, integration_widget):
    assert len(integration_widget.cake_widget.phases) == 0
    load_phase('ar.jcpds')
    assert len(integration_widget.cake_widget.phases) == 1
    load_phase('ar.jcpds')


def test_loading_many_phases(load_phases, integration_widget):
    assert len(integration_widget.cake_widget.phases) == 6


class PhaseInCakeControllerTest(QtTest):
    # SETUP
    #######################
    def setUp(self) -> None:
        self.model = DioptasModel()
        self.model.calibration_model.is_calibrated = True
        self.model.calibration_model.pattern_geometry.wavelength = 0.31E-10
        self.model.calibration_model.integrate_1d = MagicMock(return_value=(self.model.calibration_model.tth,
                                                                            self.model.calibration_model.int))
        self.widget = IntegrationWidget()
        self.controller = PhaseInCakeController(self.widget, self.model)

    def tearDown(self) -> None:
        del self.controller
        del self.widget
        self.model.delete_configurations()
        del self.model
        gc.collect()

    # Utility Functions
    #######################
    def load_phase(self, filename):
        self.model.phase_model.add_jcpds(os.path.join(jcpds_path, filename))

    def load_phases(self):
        self.load_phase('ar.jcpds')
        self.load_phase('ag.jcpds')
        self.load_phase('au_Anderson.jcpds')
        self.load_phase('mo.jcpds')
        self.load_phase('pt.jcpds')
        self.load_phase('re.jcpds')

    # Tests
    #######################

    def test_remove_phase(self):
        self.load_phases()
        self.assertEqual(len(self.widget.cake_widget.phases), 6)
        self.model.phase_model.del_phase(3)
        self.assertEqual(len(self.widget.cake_widget.phases), 5)

    def test_changing_pressure(self):
        self.load_phase('ar.jcpds')
        first_line_position = self.widget.cake_widget.phases[0].line_items[0].getPos()
        self.model.phase_model.set_pressure(0, 4)
        self.assertNotEqual(first_line_position,
                            self.widget.cake_widget.phases[0].line_items[0].getPos())

    def test_changing_temperature_and_pressure(self):
        self.load_phase('pt.jcpds')
        self.model.phase_model.set_pressure(0, 100)
        first_line_position = self.widget.cake_widget.phases[0].line_items[0].getPos()
        self.model.phase_model.set_temperature(0, 3000)
        self.assertNotEqual(first_line_position,
                            self.widget.cake_widget.phases[0].line_items[0].getPos())

    def test_changing_color(self):
        self.load_phase('pt.jcpds')
        green_value = self.widget.cake_widget.phases[0].line_items[0].pen.color().green()
        self.model.phase_model.set_color(0, (230, 22, 0))
        self.assertNotEqual(green_value,
                            self.widget.cake_widget.phases[0].line_items[0].pen.color().green())

    def test_reflection_added(self):
        self.load_phase("pt.jcpds")
        num_line_items = len(self.widget.cake_widget.phases[0].line_items)

        self.model.phase_model.add_reflection(0)
        self.assertEqual(len(self.widget.cake_widget.phases[0].line_items),
                         num_line_items + 1)

    def test_delete_reflection(self):
        self.load_phase("pt.jcpds")
        num_line_items = len(self.widget.cake_widget.phases[0].line_items)
        self.model.phase_model.delete_reflection(0, 0)
        self.assertEqual(len(self.widget.cake_widget.phases[0].line_items),
                         num_line_items - 1)

    def test_reload_phase(self):
        self.load_phase('au_Anderson.jcpds')
        self.model.phase_model.reload(0)

    def test_phases_are_not_shown_in_img_mode(self):
        self.load_phase('au_Anderson.jcpds')
        cake_phase = self.widget.cake_widget.phases[0]
        self.assertFalse(cake_phase.visible)
