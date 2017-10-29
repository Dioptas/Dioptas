# -*- coding: utf8 -*-
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

from ..utility import QtTest, click_button
import os
import gc

import numpy as np
from qtpy import QtWidgets, QtCore
from qtpy.QtTest import QTest
from mock import MagicMock

from ...controller.integration import PatternController
from ...controller.integration import PhaseController
from ...model.DioptasModel import DioptasModel
from ...widgets.integration import IntegrationWidget

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')
jcpds_path = os.path.join(data_path, 'jcpds')


class PhaseControllerTest(QtTest):
    def setUp(self):
        self.model = DioptasModel()
        self.model.calibration_model.is_calibrated = True
        self.model.calibration_model.pattern_geometry.wavelength = 0.31E-10
        self.model.calibration_model.integrate_1d = MagicMock(return_value=(self.model.calibration_model.tth,
                                                                      self.model.calibration_model.int))
        self.widget = IntegrationWidget()
        self.widget.pattern_widget._auto_range = True
        self.phase_tw = self.widget.phase_tw
        self.phase_widget = self.widget.phase_widget

        self.pattern_controller = PatternController(self.widget, self.model)
        self.controller = PhaseController(self.widget, self.model)
        self.model.pattern_model.load_pattern(os.path.join(data_path, 'pattern_001.xy'))

    def tearDown(self):
        del self.pattern_controller
        del self.controller
        del self.widget
        self.model.delete_configurations()
        del self.model
        gc.collect()

    def test_manual_deleting_phases(self):
        self.load_phases()
        QtWidgets.QApplication.processEvents()

        self.assertEqual(self.phase_tw.rowCount(), 6)
        self.assertEqual(len(self.model.phase_model.phases), 6)
        self.assertEqual(len(self.widget.pattern_widget.phases), 6)
        self.assertEqual(self.phase_tw.currentRow(), 5)

        self.controller.remove_btn_click_callback()
        self.assertEqual(self.phase_tw.rowCount(), 5)
        self.assertEqual(len(self.model.phase_model.phases), 5)
        self.assertEqual(len(self.widget.pattern_widget.phases), 5)
        self.assertEqual(self.phase_tw.currentRow(), 4)

        self.phase_widget.select_phase(1)
        self.controller.remove_btn_click_callback()
        self.assertEqual(self.phase_tw.rowCount(), 4)
        self.assertEqual(len(self.model.phase_model.phases), 4)
        self.assertEqual(len(self.widget.pattern_widget.phases), 4)
        self.assertEqual(self.phase_tw.currentRow(), 1)

        self.phase_widget.select_phase(0)
        self.controller.remove_btn_click_callback()
        self.assertEqual(self.phase_tw.rowCount(), 3)
        self.assertEqual(len(self.model.phase_model.phases), 3)
        self.assertEqual(len(self.widget.pattern_widget.phases), 3)
        self.assertEqual(self.phase_tw.currentRow(), 0)

        self.controller.remove_btn_click_callback()
        self.controller.remove_btn_click_callback()
        self.controller.remove_btn_click_callback()
        self.assertEqual(self.phase_tw.rowCount(), 0)
        self.assertEqual(len(self.model.phase_model.phases), 0)
        self.assertEqual(len(self.widget.pattern_widget.phases), 0)
        self.assertEqual(self.phase_tw.currentRow(), -1)

        self.controller.remove_btn_click_callback()
        self.assertEqual(self.phase_tw.rowCount(), 0)
        self.assertEqual(len(self.model.phase_model.phases), 0)
        self.assertEqual(len(self.widget.pattern_widget.phases), 0)
        self.assertEqual(self.phase_tw.currentRow(), -1)

    def test_automatic_deleting_phases(self):
        self.load_phases()
        self.load_phases()
        self.assertEqual(self.phase_tw.rowCount(), 12)
        self.assertEqual(len(self.model.phase_model.phases), 12)
        self.assertEqual(len(self.widget.pattern_widget.phases), 12)
        self.controller.clear_phases()
        self.assertEqual(self.phase_tw.rowCount(), 0)
        self.assertEqual(len(self.model.phase_model.phases), 0)
        self.assertEqual(len(self.widget.pattern_widget.phases), 0)
        self.assertEqual(self.phase_tw.currentRow(), -1)

        multiplier = 1
        for dummy_index in range(multiplier):
            self.load_phases()

        self.assertEqual(self.phase_tw.rowCount(), multiplier * 6)
        self.controller.clear_phases()
        self.assertEqual(self.phase_tw.rowCount(), 0)
        self.assertEqual(len(self.model.phase_model.phases), 0)
        self.assertEqual(len(self.widget.pattern_widget.phases), 0)
        self.assertEqual(self.phase_tw.currentRow(), -1)

    def test_pressure_step_change(self):
        self.load_phases()
        old_pressure = float(self.widget.phase_pressure_sb.text())
        self.widget.phase_pressure_sb.stepUp()
        step = float(self.widget.phase_pressure_step_msb.text())
        self.assertAlmostEqual(float(self.widget.phase_pressure_sb.text()), old_pressure + step, places=5)

    def test_temperature_step_change(self):
        self.load_phases()
        old_temperature = float(self.widget.phase_temperature_sb.text())
        self.widget.phase_temperature_sb.stepUp()
        step = float(self.widget.phase_temperature_step_msb.text())
        self.assertAlmostEqual(float(self.widget.phase_temperature_sb.text()), old_temperature + step, places=5)

    def test_pressure_change(self):
        self.load_phases()
        pressure = 200
        self.widget.phase_pressure_sb.setValue(200)
        for ind, phase in enumerate(self.model.phase_model.phases):
            self.assertEqual(phase.params['pressure'], pressure)
            self.assertEqual(self.phase_widget.get_phase_pressure(ind), pressure)

    def test_temperature_change(self):
        self.load_phases()
        temperature = 1500
        self.widget.phase_temperature_sb.setValue(temperature)
        for ind, phase in enumerate(self.model.phase_model.phases):
            if phase.has_thermal_expansion():
                self.assertEqual(phase.params['temperature'], temperature)
                self.assertEqual(self.phase_widget.get_phase_temperature(ind), temperature)
            else:
                self.assertEqual(phase.params['temperature'], 298)
                self.assertEqual(self.phase_widget.get_phase_temperature(ind), None)

    def test_pressure_auto_step_change(self):
        self.load_phases()
        self.widget.phase_pressure_step_msb.setValue(0.5)
        self.widget.phase_pressure_step_msb.stepUp()

        new_pressure_step = float(self.widget.phase_pressure_step_msb.text())
        self.assertAlmostEqual(new_pressure_step, 1.0, places=5)

        self.widget.phase_pressure_step_msb.stepDown()
        self.widget.phase_pressure_step_msb.stepDown()
        new_pressure_step = float(self.widget.phase_pressure_step_msb.text())
        self.assertAlmostEqual(new_pressure_step, 0.2, places=5)

    def test_temperature_auto_step_change(self):
        self.load_phases()
        self.widget.phase_temperature_step_msb.setValue(10.0)
        self.widget.phase_temperature_step_msb.stepUp()

        new_pressure_step = float(self.widget.phase_temperature_step_msb.text())
        self.assertAlmostEqual(new_pressure_step, 20.0, places=5)

        self.widget.phase_temperature_step_msb.stepDown()
        self.widget.phase_temperature_step_msb.stepDown()
        new_pressure_step = float(self.widget.phase_temperature_step_msb.text())
        self.assertAlmostEqual(new_pressure_step, 5.0, places=5)

    def test_apply_to_all_for_new_added_phase_in_table_widget(self):
        temperature = 1500
        pressure = 200
        self.phase_widget.temperature_sb.setValue(temperature)
        self.phase_widget.pressure_sb.setValue(pressure)
        self.load_phases()
        for ind, phase in enumerate(self.model.phase_model.phases):
            self.assertEqual(phase.params['pressure'], pressure)
            self.assertEqual(self.phase_widget.get_phase_pressure(ind), pressure)
            if phase.has_thermal_expansion():
                self.assertEqual(phase.params['temperature'], temperature)
                self.assertEqual(self.phase_widget.get_phase_temperature(ind), temperature)
            else:
                self.assertEqual(phase.params['temperature'], 298)
                self.assertEqual(self.phase_widget.get_phase_temperature(ind), None)

    def test_apply_to_all_for_new_added_phase_d_positions(self):
        pressure = 50
        self.load_phase('au_Anderson.jcpds')
        self.widget.phase_pressure_sb.setValue(pressure)
        self.load_phase('au_Anderson.jcpds')

        reflections1 = self.model.phase_model.get_lines_d(0)
        reflections2 = self.model.phase_model.get_lines_d(1)
        self.assertTrue(np.array_equal(reflections1, reflections2))

    def test_to_not_show_lines_in_legend(self):
        self.load_phases()
        self.phase_tw.selectRow(1)
        QTest.mouseClick(self.widget.phase_del_btn, QtCore.Qt.LeftButton)
        self.widget.pattern_widget.hide_phase(1)

    def test_auto_scaling_of_lines_in_pattern_view(self):
        pattern_view = self.widget.pattern_widget

        pattern_view_range = pattern_view.view_box.viewRange()
        pattern_y = pattern_view.plot_item.getData()[1]
        expected_maximum_height = np.max(pattern_y) - pattern_view_range[1][0]

        self.load_phase('au_Anderson.jcpds')
        phase_plot = pattern_view.phases[0]
        line_heights = []
        for line in phase_plot.line_items:
            line_data = line.getData()
            height = line_data[1][1] - line_data[1][0]
            line_heights.append(height)

        self.assertAlmostEqual(expected_maximum_height, np.max(line_heights))

        pattern_view_range = pattern_view.view_box.viewRange()
        pattern_y = pattern_view.plot_item.getData()[1]
        expected_maximum_height = np.max(pattern_y) - pattern_view_range[1][0]

        self.assertAlmostEqual(expected_maximum_height, np.max(line_heights))

    def test_line_height_in_pattern_view_after_zooming(self):
        pattern_view = self.widget.pattern_widget
        self.load_phase('au_Anderson.jcpds')

        pattern_view.view_box.setRange(xRange=[17, 30])
        pattern_view.emit_sig_range_changed()

        phase_plot = pattern_view.phases[0]
        line_heights = []
        for line in phase_plot.line_items:
            line_data = line.getData()
            if (line_data[0][0] > 17) and (line_data[0][1] < 30):
                height = line_data[1][1] - line_data[1][0]
                line_heights.append(height)

        pattern_view_range = pattern_view.view_box.viewRange()
        pattern_x, pattern_y = pattern_view.plot_item.getData()
        pattern_y_max_in_range = np.max(pattern_y[(pattern_x > pattern_view_range[0][0]) & \
                                                    (pattern_x < pattern_view_range[0][1])])
        expected_maximum_height = pattern_y_max_in_range - pattern_view_range[1][0]

        self.assertAlmostEqual(expected_maximum_height, np.max(line_heights))

    def test_save_and_load_phase_lists(self):
        # load some phases
        self.load_phases()
        phase_list_file_name = 'phase_list.txt'
        QtWidgets.QFileDialog.getSaveFileName = MagicMock(return_value=os.path.join(data_path, phase_list_file_name))
        click_button(self.widget.phase_save_list_btn)
        # make sure that phase list file was saved
        self.assertTrue(os.path.isfile(os.path.join(data_path, phase_list_file_name)))

        old_phase_list_length = self.widget.phase_tw.rowCount()
        old_phase_list_data = [[0 for x in range(5)] for y in range(old_phase_list_length)]
        for row in range(self.widget.phase_tw.rowCount()):
            old_phase_list_data[row][2] = self.phase_tw.item(row, 2).text()
            old_phase_list_data[row][3] = self.phase_tw.item(row, 3).text()
            old_phase_list_data[row][4] = self.phase_tw.item(row, 4).text()

        # clear and load the saved list to make sure all phases have been loaded
        click_button(self.widget.phase_clear_btn)
        QtWidgets.QFileDialog.getOpenFileName = MagicMock(return_value=os.path.join(data_path, phase_list_file_name))
        click_button(self.widget.phase_load_list_btn)

        self.assertEqual(self.widget.phase_tw.rowCount(), old_phase_list_length)

        for row in range(self.widget.phase_tw.rowCount()):
            self.assertEqual(self.phase_tw.item(row, 2).text(), old_phase_list_data[row][2])
            self.assertEqual(self.phase_tw.item(row, 3).text(), old_phase_list_data[row][3])
            self.assertEqual(self.phase_tw.item(row, 4).text(), old_phase_list_data[row][4])

        # delete phase list file
        os.remove(os.path.join(data_path, phase_list_file_name))

    def load_phases(self):
        self.load_phase('ar.jcpds')
        self.load_phase('ag.jcpds')
        self.load_phase('au_Anderson.jcpds')
        self.load_phase('mo.jcpds')
        self.load_phase('pt.jcpds')
        self.load_phase('re.jcpds')

    def load_phase(self, filename):
        QtWidgets.QFileDialog.getOpenFileNames = MagicMock(return_value=[os.path.join(jcpds_path, filename)])
        click_button(self.widget.phase_add_btn)
