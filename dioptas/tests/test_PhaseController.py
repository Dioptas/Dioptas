# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2014  Clemens Prescher (clemens.prescher@gmail.com)
# GSECARS, University of Chicago
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.
#
#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <http://www.gnu.org/licenses/>.

import unittest
import os

from PyQt4 import QtGui, QtCore
import numpy as np
from PyQt4.QtTest import QTest

from model.ImgModel import ImgModel
from model.CalibrationModel import CalibrationModel
from model.PatternModel import PatternModel
from model.PhaseModel import PhaseModel
from widgets.IntegrationWidget import IntegrationWidget
from controller.integration import PhaseController
from controller.integration import PatternController

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, 'data')
jcpds_path = os.path.join(data_path, 'jcpds')


class PhaseControllerTest(unittest.TestCase):

    app = QtGui.QApplication([])

    def setUp(self):
        self.image_model = ImgModel()
        self.calibration_model = CalibrationModel()
        self.calibration_model.is_calibrated = True
        self.calibration_model.spectrum_geometry.wavelength = 0.31E-10
        self.spectrum_model = PatternModel()
        self.phase_model = PhaseModel()
        self.widget = IntegrationWidget()
        self.widget.spectrum_view._auto_range = True
        self.phase_tw = self.widget.phase_tw

        self.spectrum_controller = PatternController({}, self.widget, self.image_model, None,
                                                     self.calibration_model, self.spectrum_model)
        self.controller = PhaseController({}, self.widget, self.calibration_model, self.spectrum_model,
                                          self.phase_model)
        self.spectrum_controller.load(os.path.join(data_path, 'spectrum_001.xy'))

    def test_manual_deleting_phases(self):
        self.load_phases()
        QtGui.QApplication.processEvents()

        self.assertEqual(self.phase_tw.rowCount(), 6)
        self.assertEqual(len(self.phase_model.phases), 6)
        self.assertEqual(len(self.widget.spectrum_view.phases), 6)
        self.assertEqual(self.phase_tw.currentRow(), 5)

        self.controller.remove_btn_click_callback()
        self.assertEqual(self.phase_tw.rowCount(), 5)
        self.assertEqual(len(self.phase_model.phases), 5)
        self.assertEqual(len(self.widget.spectrum_view.phases), 5)
        self.assertEqual(self.phase_tw.currentRow(), 4)

        self.widget.select_phase(1)
        self.controller.remove_btn_click_callback()
        self.assertEqual(self.phase_tw.rowCount(), 4)
        self.assertEqual(len(self.phase_model.phases), 4)
        self.assertEqual(len(self.widget.spectrum_view.phases), 4)
        self.assertEqual(self.phase_tw.currentRow(), 1)

        self.widget.select_phase(0)
        self.controller.remove_btn_click_callback()
        self.assertEqual(self.phase_tw.rowCount(), 3)
        self.assertEqual(len(self.phase_model.phases), 3)
        self.assertEqual(len(self.widget.spectrum_view.phases), 3)
        self.assertEqual(self.phase_tw.currentRow(), 0)

        self.controller.remove_btn_click_callback()
        self.controller.remove_btn_click_callback()
        self.controller.remove_btn_click_callback()
        self.assertEqual(self.phase_tw.rowCount(), 0)
        self.assertEqual(len(self.phase_model.phases), 0)
        self.assertEqual(len(self.widget.spectrum_view.phases), 0)
        self.assertEqual(self.phase_tw.currentRow(), -1)

        self.controller.remove_btn_click_callback()
        self.assertEqual(self.phase_tw.rowCount(), 0)
        self.assertEqual(len(self.phase_model.phases), 0)
        self.assertEqual(len(self.widget.spectrum_view.phases), 0)
        self.assertEqual(self.phase_tw.currentRow(), -1)

    def test_automatic_deleting_phases(self):
        self.load_phases()
        self.load_phases()
        self.assertEqual(self.phase_tw.rowCount(), 12)
        self.assertEqual(len(self.phase_model.phases), 12)
        self.assertEqual(len(self.widget.spectrum_view.phases), 12)
        self.controller.clear_phases()
        self.assertEqual(self.phase_tw.rowCount(), 0)
        self.assertEqual(len(self.phase_model.phases), 0)
        self.assertEqual(len(self.widget.spectrum_view.phases), 0)
        self.assertEqual(self.phase_tw.currentRow(), -1)

        multiplier = 1
        for dummy_index in range(multiplier):
            self.load_phases()

        self.assertEqual(self.phase_tw.rowCount(), multiplier * 6)
        self.controller.clear_phases()
        self.assertEqual(self.phase_tw.rowCount(), 0)
        self.assertEqual(len(self.phase_model.phases), 0)
        self.assertEqual(len(self.widget.spectrum_view.phases), 0)
        self.assertEqual(self.phase_tw.currentRow(), -1)

    def test_pressure_change(self):
        self.load_phases()
        pressure = 200
        self.widget.phase_pressure_sb.setValue(200)
        for ind, phase in enumerate(self.phase_model.phases):
            self.assertEqual(phase.pressure, pressure)
            self.assertEqual(self.widget.get_phase_pressure(ind), pressure)

    def test_temperature_change(self):
        self.load_phases()
        temperature = 1500
        self.widget.phase_temperature_sb.setValue(temperature)
        for ind, phase in enumerate(self.phase_model.phases):
            if phase.has_thermal_expansion():
                self.assertEqual(phase.temperature, temperature)
                self.assertEqual(self.widget.get_phase_temperature(ind), temperature)
            else:
                self.assertEqual(phase.temperature, 298)
                self.assertEqual(self.widget.get_phase_temperature(ind), None)

    def test_apply_to_all_for_new_added_phase_in_table_widget(self):
        temperature = 1500
        pressure = 200
        self.widget.phase_temperature_sb.setValue(temperature)
        self.widget.phase_pressure_sb.setValue(pressure)
        self.load_phases()
        for ind, phase in enumerate(self.phase_model.phases):
            self.assertEqual(phase.pressure, pressure)
            self.assertEqual(self.widget.get_phase_pressure(ind), pressure)
            if phase.has_thermal_expansion():
                self.assertEqual(phase.temperature, temperature)
                self.assertEqual(self.widget.get_phase_temperature(ind), temperature)
            else:
                self.assertEqual(phase.temperature, 298)
                self.assertEqual(self.widget.get_phase_temperature(ind), None)

    def test_apply_to_all_for_new_added_phase_d_positions(self):
        pressure = 50
        self.load_phase('au_Anderson.jcpds')
        self.widget.phase_pressure_sb.setValue(pressure)
        self.load_phase('au_Anderson.jcpds')

        reflections1 = self.phase_model.get_lines_d(0)
        reflections2 = self.phase_model.get_lines_d(1)
        self.assertTrue(np.array_equal(reflections1, reflections2))

    def test_to_not_show_lines_in_legend(self):
        self.load_phases()
        self.phase_tw.selectRow(1)
        QTest.mouseClick(self.widget.phase_del_btn, QtCore.Qt.LeftButton)
        self.widget.spectrum_view.hide_phase(1)

    def test_auto_scaling_of_lines_in_spectrum_view(self):
        spectrum_view = self.widget.spectrum_view

        spectrum_view_range = spectrum_view.view_box.viewRange()
        spectrum_y = spectrum_view.plot_item.getData()[1]
        expected_maximum_height = np.max(spectrum_y) - spectrum_view_range[1][0]

        self.load_phase('au_Anderson.jcpds')
        phase_plot = spectrum_view.phases[0]
        line_heights = []
        for line in phase_plot.line_items:
            line_data = line.getData()
            height = line_data[1][1] - line_data[1][0]
            line_heights.append(height)

        self.assertAlmostEqual(expected_maximum_height, np.max(line_heights))

        spectrum_view_range = spectrum_view.view_box.viewRange()
        spectrum_y = spectrum_view.plot_item.getData()[1]
        expected_maximum_height = np.max(spectrum_y) - spectrum_view_range[1][0]

        self.assertAlmostEqual(expected_maximum_height, np.max(line_heights))

    def test_line_height_in_spectrum_view_after_zooming(self):
        spectrum_view = self.widget.spectrum_view
        self.load_phase('au_Anderson.jcpds')

        spectrum_view.view_box.setRange(xRange=[17, 30])
        spectrum_view.emit_sig_range_changed()

        phase_plot = spectrum_view.phases[0]
        line_heights = []
        for line in phase_plot.line_items:
            line_data = line.getData()
            if (line_data[0][0] > 17) and (line_data[0][1] < 30):
                height = line_data[1][1] - line_data[1][0]
                line_heights.append(height)

        spectrum_view_range = spectrum_view.view_box.viewRange()
        spectrum_x, spectrum_y = spectrum_view.plot_item.getData()
        spectrum_y_max_in_range = np.max(spectrum_y[(spectrum_x > spectrum_view_range[0][0]) & \
                                                    (spectrum_x < spectrum_view_range[0][1])])
        expected_maximum_height = spectrum_y_max_in_range - spectrum_view_range[1][0]

        self.assertAlmostEqual(expected_maximum_height, np.max(line_heights))

    def load_phases(self):
        self.load_phase('ar.jcpds')
        self.load_phase('ag.jcpds')
        self.load_phase('au_Anderson.jcpds')
        self.load_phase('mo.jcpds')
        self.load_phase('pt.jcpds')
        self.load_phase('re.jcpds')

    def load_phase(self, filename):
        self.controller.add_btn_click_callback(os.path.join(jcpds_path, filename))


if __name__ == '__main__':
    unittest.main()
