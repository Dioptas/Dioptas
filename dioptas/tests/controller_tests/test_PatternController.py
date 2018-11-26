# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2017  Clemens Prescher (clemens.prescher@gmail.com)
# Institute for Geology and Mineralogy, University of Cologne
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

import numpy as np

from ...widgets.integration import IntegrationWidget
from ...controller.integration.PatternController import PatternController
from ...model.DioptasModel import DioptasModel

data_path = os.path.join(os.path.dirname(__file__), '../data')
from ..ehook import excepthook


class PatternControllerTest(QtTest):
    def setUp(self):
        self.working_dir = {'image': '', 'pattern': ''}
        sys.excepthook = excepthook

        self.widget = IntegrationWidget()
        self.model = DioptasModel()

        self.controller = PatternController(
            widget=self.widget,
            dioptas_model=self.model)

    def tearDown(self):
        delete_if_exists(os.path.join(data_path, "test.xy"))

    def test_configuration_selected_changes_active_unit_btn(self):
        self.model.calibration_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.poni'))
        self.model.img_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.tif'))

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
        QtWidgets.QFileDialog.getSaveFileName = MagicMock(return_value=os.path.join(data_path, "test.xy"))
        self.model.calibration_model.create_file_header = MagicMock(return_value="None")
        click_button(self.widget.qa_save_pattern_btn)

        self.assertTrue(os.path.exists(os.path.join(data_path, "test.xy")))
