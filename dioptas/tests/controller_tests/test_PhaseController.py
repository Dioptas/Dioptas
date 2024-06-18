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

from ..utility import QtTest, click_button, click_checkbox
import os
import gc

from qtpy import QtWidgets, QtCore, QtGui
from qtpy.QtTest import QTest
from mock import MagicMock

from ...controller.integration import PatternController
from ...controller.integration import PhaseController
from ...model.DioptasModel import DioptasModel
from ...widgets.integration import IntegrationWidget

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, "../data")
jcpds_path = os.path.join(data_path, "jcpds")


class PhaseControllerTest(QtTest):
    def setUp(self):
        self.model = DioptasModel()
        self.model.calibration_model.is_calibrated = True
        self.model.calibration_model.pattern_geometry.wavelength = 0.31e-10
        self.model.calibration_model.integrate_1d = MagicMock(
            return_value=(
                self.model.calibration_model.tth,
                self.model.calibration_model.int,
            )
        )
        self.widget = IntegrationWidget()
        self.widget.pattern_widget._auto_range = True
        self.phase_tw = self.widget.phase_tw
        self.phase_widget = self.widget.phase_widget

        self.pattern_controller = PatternController(self.widget, self.model)
        self.controller = PhaseController(self.widget, self.model)
        self.model.pattern_model.load_pattern(os.path.join(data_path, "pattern_001.xy"))

    def tearDown(self):
        del self.pattern_controller
        del self.controller
        del self.widget
        self.model.delete_configurations()
        del self.model
        gc.collect()

    def test_manual_deleting_phases(self):
        self.load_phases()

        self.assertEqual(self.phase_tw.rowCount(), 6)
        self.assertEqual(len(self.model.phase_model.phases), 6)
        self.assertEqual(len(self.widget.pattern_widget.phases), 6)
        self.assertEqual(self.phase_tw.currentRow(), 5)

        click_button(self.phase_widget.delete_btn)
        self.assertEqual(self.phase_tw.rowCount(), 5)
        self.assertEqual(len(self.model.phase_model.phases), 5)
        self.assertEqual(len(self.widget.pattern_widget.phases), 5)
        self.assertEqual(self.phase_tw.currentRow(), 4)

        self.phase_widget.select_phase(1)
        click_button(self.phase_widget.delete_btn)
        self.assertEqual(self.phase_tw.rowCount(), 4)
        self.assertEqual(len(self.model.phase_model.phases), 4)
        self.assertEqual(len(self.widget.pattern_widget.phases), 4)
        self.assertEqual(self.phase_tw.currentRow(), 1)

        self.phase_widget.select_phase(0)
        click_button(self.phase_widget.delete_btn)
        self.assertEqual(self.phase_tw.rowCount(), 3)
        self.assertEqual(len(self.model.phase_model.phases), 3)
        self.assertEqual(len(self.widget.pattern_widget.phases), 3)
        self.assertEqual(self.phase_tw.currentRow(), 0)

        click_button(self.phase_widget.delete_btn)
        click_button(self.phase_widget.delete_btn)
        click_button(self.phase_widget.delete_btn)
        self.assertEqual(self.phase_tw.rowCount(), 0)
        self.assertEqual(len(self.model.phase_model.phases), 0)
        self.assertEqual(len(self.widget.pattern_widget.phases), 0)
        self.assertEqual(self.phase_tw.currentRow(), -1)

        click_button(self.phase_widget.delete_btn)
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

        click_button(self.phase_widget.clear_btn)
        self.assertEqual(self.phase_tw.rowCount(), 0)
        self.assertEqual(len(self.model.phase_model.phases), 0)
        self.assertEqual(len(self.widget.pattern_widget.phases), 0)
        self.assertEqual(self.phase_tw.currentRow(), -1)

        multiplier = 1
        for dummy_index in range(multiplier):
            self.load_phases()

        self.assertEqual(self.phase_tw.rowCount(), multiplier * 6)

        click_button(self.phase_widget.clear_btn)
        self.assertEqual(self.phase_tw.rowCount(), 0)
        self.assertEqual(len(self.model.phase_model.phases), 0)
        self.assertEqual(len(self.widget.pattern_widget.phases), 0)
        self.assertEqual(self.phase_tw.currentRow(), -1)

    def test_pressure_step_spinbox_changes_pressure_spinboxes(self):
        self.load_phases()
        for ind in range(6):
            self.assertEqual(self.phase_widget.pressure_sbs[ind].singleStep(), 1)

        new_step = 5
        self.phase_widget.pressure_step_msb.setValue(new_step)
        for ind in range(6):
            self.assertEqual(self.phase_widget.pressure_sbs[ind].singleStep(), new_step)

    def test_temperature_step_spinbox_changes_temperature_spinboxes(self):
        self.load_phases()
        for ind in range(6):
            self.assertEqual(self.phase_widget.temperature_sbs[ind].singleStep(), 100)

        new_step = 5
        self.phase_widget.temperature_step_msb.setValue(new_step)
        for ind in range(6):
            self.assertEqual(
                self.phase_widget.temperature_sbs[ind].singleStep(), new_step
            )

    def test_pressure_change(self):
        self.load_phases()
        click_checkbox(self.phase_widget.apply_to_all_cb)

        pressure = 200
        for ind in [0, 1, 3]:
            self.phase_widget.pressure_sbs[ind].setValue(pressure)
            self.assertEqual(
                self.model.phase_model.phases[ind].params["pressure"], pressure
            )
        self.assertEqual(self.model.phase_model.phases[2].params["pressure"], 0)

    def test_temperature_change(self):
        self.load_phases()
        self.model.phase_model.set_pressure(2, 100)  # otherwise the reflections go none

        temperature = 1500

        for ind in range(len(self.model.phase_model.phases)):
            phase = self.model.phase_model.phases[ind]
            temperature += ind

            self.assertEqual(
                self.phase_widget.temperature_sbs[ind].isEnabled(),
                phase.has_thermal_expansion(),
            )

            if self.phase_widget.temperature_sbs[ind].isEnabled():
                self.phase_widget.temperature_sbs[ind].setValue(temperature)

            if phase.has_thermal_expansion():
                self.assertEqual(phase.params["temperature"], temperature)
                self.assertEqual(
                    self.phase_widget.get_phase_temperature(ind), temperature
                )
            else:
                self.assertEqual(phase.params["temperature"], 298)
                self.assertEqual(self.phase_widget.get_phase_temperature(ind), 298)

    def test_pressure_auto_step_change(self):
        self.load_phases()
        self.widget.phase_pressure_step_msb.setValue(0.5)
        self.widget.phase_pressure_step_msb.stepUp()

        new_pressure_step = self.widget.phase_pressure_step_msb.value()
        self.assertAlmostEqual(new_pressure_step, 1.0, places=5)

        self.widget.phase_pressure_step_msb.stepDown()
        self.widget.phase_pressure_step_msb.stepDown()
        new_pressure_step = self.widget.phase_pressure_step_msb.value()
        self.assertAlmostEqual(new_pressure_step, 0.2, places=5)

    def test_temperature_auto_step_change(self):
        self.load_phases()
        self.widget.phase_temperature_step_msb.setValue(10.0)
        self.widget.phase_temperature_step_msb.stepUp()

        new_pressure_step = self.widget.phase_temperature_step_msb.value()
        self.assertAlmostEqual(new_pressure_step, 20.0, places=5)

        self.widget.phase_temperature_step_msb.stepDown()
        self.widget.phase_temperature_step_msb.stepDown()
        new_pressure_step = self.widget.phase_temperature_step_msb.value()
        self.assertAlmostEqual(new_pressure_step, 5.0, places=5)

    def test_apply_to_all_for_new_added_phase_in_table_widget(self):
        temperature = 1500
        pressure = 200
        self.load_phases()
        self.phase_widget.pressure_sbs[0].setValue(pressure)
        self.phase_widget.temperature_sbs[0].setValue(temperature)
        self.load_phases()

        for ind, phase in enumerate(self.model.phase_model.phases):
            self.assertEqual(phase.params["pressure"], pressure)
            self.assertEqual(self.phase_widget.get_phase_pressure(ind), pressure)

    def test_to_not_show_lines_in_legend(self):
        self.load_phases()
        self.phase_tw.selectRow(1)
        QTest.mouseClick(self.widget.phase_del_btn, QtCore.Qt.LeftButton)
        self.widget.pattern_widget.hide_phase(1)

    def test_save_and_load_phase_lists(self):
        # load some phases
        self.load_phases()
        phase_list_file_name = "phase_list.txt"
        QtWidgets.QFileDialog.getSaveFileName = MagicMock(
            return_value=os.path.join(data_path, phase_list_file_name)
        )
        click_button(self.widget.phase_save_list_btn)
        # make sure that phase list file was saved
        self.assertTrue(os.path.isfile(os.path.join(data_path, phase_list_file_name)))

        old_phase_list_length = self.widget.phase_tw.rowCount()
        old_phase_list_data = [
            [0 for x in range(5)] for y in range(old_phase_list_length)
        ]
        for row in range(self.widget.phase_tw.rowCount()):
            old_phase_list_data[row][2] = self.phase_tw.item(row, 2).text()
            old_phase_list_data[row][3] = self.phase_widget.pressure_sbs[row].text()
            old_phase_list_data[row][4] = self.phase_widget.temperature_sbs[row].text()

        # clear and load the saved list to make sure all phases have been loaded
        click_button(self.widget.phase_clear_btn)
        QtWidgets.QFileDialog.getOpenFileName = MagicMock(
            return_value=os.path.join(data_path, phase_list_file_name)
        )
        click_button(self.widget.phase_load_list_btn)

        self.assertEqual(self.widget.phase_tw.rowCount(), old_phase_list_length)

        for row in range(self.widget.phase_tw.rowCount()):
            self.assertEqual(
                self.phase_tw.item(row, 2).text(), old_phase_list_data[row][2]
            )
            self.assertEqual(
                self.phase_widget.pressure_sbs[row].text(), old_phase_list_data[row][3]
            )
            self.assertEqual(
                self.phase_widget.temperature_sbs[row].text(),
                old_phase_list_data[row][4],
            )

        # delete phase list file
        os.remove(os.path.join(data_path, phase_list_file_name))

    def test_bulk_change_visibility_of_phases(self):
        self.load_phases()
        for cb in self.phase_widget.phase_show_cbs:
            self.assertTrue(cb.isChecked())

        self.controller.phase_tw_header_section_clicked(0)
        for cb in self.phase_widget.phase_show_cbs:
            self.assertFalse(cb.isChecked())

        click_checkbox(self.phase_widget.phase_show_cbs[1])
        self.controller.phase_tw_header_section_clicked(0)
        for ind, cb in enumerate(self.phase_widget.phase_show_cbs):
            self.assertFalse(cb.isChecked())

        self.controller.phase_tw_header_section_clicked(0)
        for ind, cb in enumerate(self.phase_widget.phase_show_cbs):
            self.assertTrue(cb.isChecked())

    def test_change_phase_color(self):
        """
        Test that phase color is changed in phase table widget, phase legend and phase line. We assign the color from
        the second color button to the fourth phase.
        """
        self.load_phases()
        new_color = (
            self.phase_widget.phase_color_btns[1].palette().color(QtGui.QPalette.Button)
        )
        QtWidgets.QColorDialog.getColor = MagicMock(return_value=new_color)
        click_button(self.phase_widget.phase_color_btns[3])

        self.assertEqual(
            self.phase_widget.phase_color_btns[3]
            .palette()
            .color(QtGui.QPalette.Button),
            new_color,
        )

        self.assertEqual(
            self.model.phase_model.phase_colors[3],
            (new_color.red(), new_color.green(), new_color.blue()),
        )

        phase_line_color = self.widget.pattern_widget.phases[3].pen.color()
        phase_legend_color = self.widget.pattern_widget.phases_legend.legendItems[3][
            1
        ].opts["color"]
        self.assertEqual(phase_line_color, new_color)
        self.assertEqual(
            phase_legend_color, (new_color.red(), new_color.green(), new_color.blue())
        )

    def load_phases(self):
        self.load_phase("ar.jcpds")
        self.load_phase("ag.jcpds")
        self.load_phase("au_Anderson.jcpds")
        self.load_phase("mo.jcpds")
        self.load_phase("pt.jcpds")
        self.load_phase("re.jcpds")

    def load_phase(self, filename):
        self.model.phase_model.add_jcpds(os.path.join(jcpds_path, filename))


def test_save_phaselist(qapp, tmp_path):
    integration_widget = IntegrationWidget()
    model = DioptasModel()
    model.calibration_model.is_calibrated = True
    model.calibration_model.pattern_geometry.wavelength = 0.31e-10
    model.calibration_model.integrate_1d = MagicMock(
        return_value=(model.calibration_model.tth, model.calibration_model.int)
    )

    phase_controller = PhaseController(integration_widget, model)

    model.phase_model.add_jcpds(os.path.join(jcpds_path, "ar.jcpds"))
    model.phase_model.add_jcpds(os.path.join(jcpds_path, "ag.jcpds"))

    QtWidgets.QFileDialog.getSaveFileName = MagicMock(
        return_value=tmp_path / "test.txt"
    )
    phase_controller.save_btn_clicked_callback()
    phase_controller.clear_phases()

    assert len(model.phase_model.phases) == 0

    QtWidgets.QFileDialog.getOpenFileName = MagicMock(
        return_value=tmp_path / "test.txt"
    )

    phase_controller.load_list_btn_clicked_callback()

    assert len(model.phase_model.phases) == 2


def test_save_phaselist_with_german_locale(qapp, tmp_path):
    QtCore.QLocale.setDefault(QtCore.QLocale(QtCore.QLocale.German))
    test_save_phaselist(qapp, tmp_path)
