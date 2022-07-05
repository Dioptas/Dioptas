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

import os, sys

from ..utility import QtTest, click_button, delete_if_exists
from mock import MagicMock

from qtpy import QtWidgets

from ...model.util.calc import convert_units
import numpy as np

from ...widgets.integration import IntegrationWidget
from ...controller.integration.PatternController import PatternController
from ...model.DioptasModel import DioptasModel

unittest_data_path = os.path.join(os.path.dirname(__file__), '../data')

class PatternControllerTest(QtTest):
    def setUp(self):
        self.widget = IntegrationWidget()
        self.model = DioptasModel()

        self.controller = PatternController(
            widget=self.widget,
            dioptas_model=self.model)

    def tearDown(self):
        delete_if_exists(os.path.join(unittest_data_path, "test.xy"))

    def test_configuration_selected_changes_active_unit_btn(self):
        self.model.calibration_model.load(os.path.join(unittest_data_path, 'CeO2_Pilatus1M.poni'))
        self.model.img_model.load(os.path.join(unittest_data_path, 'CeO2_Pilatus1M.tif'))

        self.model.add_configuration()
        click_button(self.widget.pattern_q_btn)

        self.model.add_configuration()
        click_button(self.widget.pattern_d_btn)

        self.model.select_configuration(0)
        self.assertTrue(self.widget.pattern_tth_btn.isChecked())
        self.assertFalse(self.widget.pattern_q_btn.isChecked())
        self.assertFalse(self.widget.pattern_d_btn.isChecked())

        self.assertEqual(self.widget.pattern_widget.pattern_plot.getAxis('bottom').labelString(),
                         u"<span style='color: #ffffff'>2θ (°)</span>")

        self.model.select_configuration(1)
        self.assertTrue(self.widget.pattern_q_btn.isChecked())

        self.assertEqual(self.widget.pattern_widget.pattern_plot.getAxis('bottom').labelString(),
                         "<span style='color: #ffffff'>Q (A<sup>-1</sup>)</span>")

        self.model.select_configuration(2)
        self.assertTrue(self.widget.pattern_d_btn.isChecked())
        self.assertEqual(self.widget.pattern_widget.pattern_plot.getAxis('bottom').labelString(),
                         u"<span style='color: #ffffff'>d (kA)</span>")

    def test_save_pattern_without_background(self):
        QtWidgets.QFileDialog.getSaveFileName = MagicMock(return_value=os.path.join(unittest_data_path, "test.xy"))
        self.model.calibration_model.create_file_header = MagicMock(return_value="None")
        click_button(self.widget.qa_save_pattern_btn)

        self.assertTrue(os.path.exists(os.path.join(unittest_data_path, "test.xy")))

    def test_click_pattern_sends_tth_changed_signal(self):
        self.model.clicked_tth_changed.emit = MagicMock()
        self.widget.integration_pattern_widget.pattern_view.mouse_left_clicked.emit(10, 300)
        self.model.clicked_tth_changed.emit.assert_called_once_with(10)

    def test_click_pattern_changes_position_line(self):
        self.widget.integration_pattern_widget.pattern_view.mouse_left_clicked.emit(10, 300)
        prior_pos = self.widget.integration_pattern_widget.pattern_view.pos_line.getPos()
        self.widget.integration_pattern_widget.pattern_view.mouse_left_clicked.emit(12, 300)
        new_pos = self.widget.integration_pattern_widget.pattern_view.pos_line.getPos()[0]
        self.assertEqual(new_pos, 12)

    def test_pos_line_updates_on_integration_unit_change(self):
        self.load_pilatus1M_image_and_calibration()
        self.widget.integration_pattern_widget.pattern_view.mouse_left_clicked.emit(10, 300)

        click_button(self.widget.integration_pattern_widget.q_btn)
        new_pos = self.widget.integration_pattern_widget.pattern_view.pos_line.getPos()[0]
        self.assertEqual(new_pos, convert_units(10, self.model.calibration_model.wavelength, '2th_deg', 'q_A^-1'))

        click_button(self.widget.integration_pattern_widget.d_btn)
        new_pos = self.widget.integration_pattern_widget.pattern_view.pos_line.getPos()[0]
        self.assertAlmostEqual(new_pos, convert_units(10, self.model.calibration_model.wavelength, '2th_deg', 'd_A'))

        click_button(self.widget.integration_pattern_widget.tth_btn)
        new_pos = self.widget.integration_pattern_widget.pattern_view.pos_line.getPos()[0]
        self.assertAlmostEqual(new_pos, 10)

    def test_pos_line_updates_on_tth_clicked_signal(self):
        self.load_pilatus1M_image_and_calibration()
        self.model.clicked_tth_changed.emit(5)
        new_pos = self.widget.integration_pattern_widget.pattern_view.pos_line.getPos()[0]
        self.assertEqual(new_pos, 5)

        click_button(self.widget.integration_pattern_widget.q_btn)
        self.model.clicked_tth_changed.emit(3)
        new_pos = self.widget.integration_pattern_widget.pattern_view.pos_line.getPos()[0]
        self.assertAlmostEqual(new_pos, convert_units(3, self.model.calibration_model.wavelength, '2th_deg', 'q_A^-1'))

    def load_pilatus1M_image_and_calibration(self):
        file_name = os.path.join(unittest_data_path, 'CeO2_Pilatus1M.tif')
        self.model.img_model.load(file_name)
        calibration_file_name = os.path.join(unittest_data_path, 'CeO2_Pilatus1M.poni')
        self.model.calibration_model.load(calibration_file_name)
