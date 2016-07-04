# -*- coding: utf8 -*-
from tests.utility import QtTest
import os
import gc

import numpy as np
from PyQt4 import QtGui, QtCore
from PyQt4.QtTest import QTest
from mock import MagicMock

from controller.integration import PatternController
from controller.integration import PhaseController
from model.DioptasModel import DioptasModel
from widgets.integration import IntegrationWidget

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')
jcpds_path = os.path.join(data_path, 'jcpds')


class PhaseControllerTest(QtTest):
    @classmethod
    def setUpClass(cls):
        cls.app = QtGui.QApplication.instance()
        if cls.app is None:
            cls.app = QtGui.QApplication([])

    def setUp(self):
        self.model = DioptasModel()
        self.model.calibration_model.is_calibrated = True
        self.model.calibration_model.spectrum_geometry.wavelength = 0.31E-10
        self.model.calibration_model.integrate_1d = MagicMock(return_value=(self.model.calibration_model.tth,
                                                                      self.model.calibration_model.int))
        self.widget = IntegrationWidget()
        self.widget.pattern_widget._auto_range = True
        self.phase_tw = self.widget.phase_tw

        self.spectrum_controller = PatternController({}, self.widget, self.model)
        self.controller = PhaseController({}, self.widget, self.model)
        self.spectrum_controller.load(os.path.join(data_path, 'spectrum_001.xy'))


    def test_manual_deleting_phases(self):
        self.load_phases()
        QtGui.QApplication.processEvents()

        self.assertEqual(self.phase_tw.rowCount(), 6)
        self.assertEqual(len(self.model.phase_model.phases), 6)
        self.assertEqual(len(self.widget.pattern_widget.phases), 6)
        self.assertEqual(self.phase_tw.currentRow(), 5)

        self.controller.remove_btn_click_callback()
        self.assertEqual(self.phase_tw.rowCount(), 5)
        self.assertEqual(len(self.model.phase_model.phases), 5)
        self.assertEqual(len(self.widget.pattern_widget.phases), 5)
        self.assertEqual(self.phase_tw.currentRow(), 4)

        self.widget.select_phase(1)
        self.controller.remove_btn_click_callback()
        self.assertEqual(self.phase_tw.rowCount(), 4)
        self.assertEqual(len(self.model.phase_model.phases), 4)
        self.assertEqual(len(self.widget.pattern_widget.phases), 4)
        self.assertEqual(self.phase_tw.currentRow(), 1)

        self.widget.select_phase(0)
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

    def test_pressure_change(self):
        self.load_phases()
        pressure = 200
        self.widget.phase_pressure_sb.setValue(200)
        for ind, phase in enumerate(self.model.phase_model.phases):
            self.assertEqual(phase.pressure, pressure)
            self.assertEqual(self.widget.get_phase_pressure(ind), pressure)

    def test_temperature_change(self):
        self.load_phases()
        temperature = 1500
        self.widget.phase_temperature_sb.setValue(temperature)
        for ind, phase in enumerate(self.model.phase_model.phases):
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
        for ind, phase in enumerate(self.model.phase_model.phases):
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

        reflections1 = self.model.phase_model.get_lines_d(0)
        reflections2 = self.model.phase_model.get_lines_d(1)
        self.assertTrue(np.array_equal(reflections1, reflections2))

    def test_to_not_show_lines_in_legend(self):
        self.load_phases()
        self.phase_tw.selectRow(1)
        QTest.mouseClick(self.widget.phase_del_btn, QtCore.Qt.LeftButton)
        self.widget.pattern_widget.hide_phase(1)

    def test_auto_scaling_of_lines_in_spectrum_view(self):
        spectrum_view = self.widget.pattern_widget

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
        spectrum_view = self.widget.pattern_widget
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
