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

import os

import numpy as np
from qtpy import QtWidgets, QtCore

from ....model.PhaseModel import PhaseLoadError
from ....model.util.HelperModule import get_base_name
from ....controller.integration.phase.JcpdsEditorController import JcpdsEditorController
from ....widgets.UtilityWidgets import save_file_dialog, open_file_dialog, open_files_dialog

from .PhaseInPatternController import PhaseInPatternController
from .PhaseInCakeController import PhaseInCakeController

# imports for type hinting in PyCharm -- DO NOT DELETE
from ....model.DioptasModel import DioptasModel
from ....widgets.integration import IntegrationWidget
from ....widgets.UtilityWidgets import CifConversionParametersDialog


class PhaseController(object):
    """
    PhaseController handles all the interaction between the phase controls in the Integration View and the
    PhaseModel object.
    """

    def __init__(self, integration_widget, dioptas_model):
        """
        :param integration_widget: Reference to an IntegrationWidget
        :param dioptas_model: reference to DioptasModel object

        :type integration_widget: IntegrationWidget
        :type dioptas_model: DioptasModel
        """
        self.integration_widget = integration_widget
        self.phase_widget = self.integration_widget.phase_widget
        self.pattern_widget = self.integration_widget.pattern_widget
        self.model = dioptas_model

        self.cif_conversion_dialog = CifConversionParametersDialog(self.integration_widget)

        self.phase_in_pattern_controller = PhaseInPatternController(self.integration_widget, dioptas_model)
        self.phase_in_cake_controller = PhaseInCakeController(self.integration_widget, dioptas_model)
        self.jcpds_editor_controller = JcpdsEditorController(self.integration_widget, self.model)

        self.phase_lw_items = []
        self.create_signals()
        self.update_temperature_step()
        self.update_pressure_step()

    def create_signals(self):
        # Button Callbacks
        self.phase_widget.add_btn.clicked.connect(self.add_btn_click_callback)
        self.phase_widget.delete_btn.clicked.connect(self.delete_btn_click_callback)
        self.phase_widget.clear_btn.clicked.connect(self.clear_phases)
        self.phase_widget.save_list_btn.clicked.connect(self.save_btn_clicked_callback)
        self.phase_widget.load_list_btn.clicked.connect(self.load_list_btn_clicked_callback)

        # Spinbox Callbacks
        self.phase_widget.pressure_step_msb.valueChanged.connect(self.update_pressure_step)
        self.phase_widget.temperature_step_msb.valueChanged.connect(self.update_temperature_step)

        self.phase_widget.pressure_sb_value_changed.connect(self.model.phase_model.set_pressure)
        self.phase_widget.temperature_sb_value_changed.connect(self.model.phase_model.set_temperature)

        # Color and State
        self.phase_widget.color_btn_clicked.connect(self.color_btn_clicked)
        self.phase_widget.show_cb_state_changed.connect(self.model.phase_model.set_phase_visible)
        self.phase_widget.apply_to_all_cb.stateChanged.connect(self.apply_to_all_callback)

        # TableWidget
        self.phase_widget.phase_tw.horizontalHeader().sectionClicked.connect(self.phase_tw_header_section_clicked)

        # PhaseModel Signals
        self.model.phase_model.phase_added.connect(self.phase_added)
        self.model.phase_model.phase_changed.connect(self.phase_changed)
        self.model.phase_model.phase_removed.connect(self.phase_removed)

    def connect_click_function(self, emitter, function):
        emitter.clicked.connect(function)

    def add_btn_click_callback(self, *args, **kwargs):
        """
        Loads a new phase from jcpds file.
        """
        if not self.model.calibration_model.is_calibrated:
            self.integration_widget.show_error_msg("Can not load phase without calibration.")

        filenames = [kwargs.get('filenames', None)]

        if filenames[0] is None:
            filenames = open_files_dialog(self.integration_widget, "Load Phase(s).",
                                          self.model.working_directories['phase'])

        if len(filenames):
            self.model.working_directories['phase'] = os.path.dirname(str(filenames[0]))
            progress_dialog = QtWidgets.QProgressDialog("Loading multiple phases.", "Abort Loading", 0, len(filenames),
                                                        self.integration_widget)
            progress_dialog.setWindowModality(QtCore.Qt.WindowModal)
            progress_dialog.setWindowFlags(QtCore.Qt.FramelessWindowHint)
            progress_dialog.show()
            QtWidgets.QApplication.processEvents()
            for ind, filename in enumerate(filenames):
                filename = str(filename)
                progress_dialog.setValue(ind)
                progress_dialog.setLabelText("Loading: " + os.path.basename(filename))
                QtWidgets.QApplication.processEvents()

                self._add_phase(filename)

                if progress_dialog.wasCanceled():
                    break
            progress_dialog.close()
            QtWidgets.QApplication.processEvents()

    def _add_phase(self, filename):
        try:
            if filename.endswith("jcpds"):
                self.model.phase_model.add_jcpds(filename)
            elif filename.endswith(".cif"):
                self.cif_conversion_dialog.exec_()
                self.model.phase_model.add_cif(filename,
                                               self.cif_conversion_dialog.int_cutoff,
                                               self.cif_conversion_dialog.min_d_spacing)
        except PhaseLoadError as e:
            self.integration_widget.show_error_msg(
                'Could not load:\n\n{}.\n\nPlease check if the format of the input file is correct.'. \
                    format(e.filename))

    def phase_added(self):
        color = self.model.phase_model.phase_colors[-1]
        self.phase_widget.add_phase(get_base_name(self.model.phase_model.phase_files[-1]),
                                    '#%02x%02x%02x' % (int(color[0]), int(color[1]), int(color[2])))

    def phase_changed(self, ind):
        phase_name = get_base_name(self.model.phase_model.phases[ind].filename)
        if self.model.phase_model.phases[ind].params['modified']:
            phase_name += '*'
        self.phase_widget.rename_phase(ind, phase_name)
        self.phase_widget.set_phase_pressure(ind, self.model.phase_model.phases[ind].params['pressure'])
        self.phase_widget.set_phase_temperature(ind, self.model.phase_model.phases[ind].params['temperature'])
        self.phase_widget.temperature_sbs[ind].setEnabled(self.model.phase_model.phases[ind].has_thermal_expansion())

    def delete_btn_click_callback(self):
        """
        Deletes the currently selected Phase
        """
        cur_ind = self.phase_widget.get_selected_phase_row()
        if cur_ind >= 0:
            self.model.phase_model.del_phase(cur_ind)

    def phase_removed(self, ind):
        self.phase_widget.del_phase(ind)
        # self.img_view_widget.del_cake_phase(ind)

        if self.jcpds_editor_controller.active:
            ind = self.phase_widget.get_selected_phase_row()
            if ind >= 0:
                self.jcpds_editor_controller.show_phase(self.model.phase_model.phases[ind])
            else:
                self.jcpds_editor_controller.jcpds_widget.close()

    def load_list_btn_clicked_callback(self):
        filename = open_file_dialog(self.integration_widget, caption="Load Phase List",
                                    directory=self.model.working_directories['phase'],
                                    filter="*.txt")
        if filename == '':
            return
        with open(filename, 'r') as phase_file:
            if phase_file == '':
                return
            for line in phase_file.readlines():
                line = line.replace('\n', '')
                phase, use_flag, color, name, pressure, temperature = line.split(',')
                self.add_btn_click_callback(filenames=phase)
                row = self.phase_widget.phase_tw.rowCount() - 1
                self.phase_widget.phase_show_cbs[row].setChecked(bool(use_flag))
                self.phase_widget.phase_color_btns[row].setStyleSheet('background-color:' + color)
                self.pattern_widget.set_phase_color(row, color)
                self.phase_widget.phase_tw.item(row, 2).setText(name)
                self.phase_widget.set_phase_pressure(row, float(pressure))
                self.model.phase_model.set_pressure(row, float(pressure))
                temperature = float(temperature)

                if temperature is not '':
                    self.phase_widget.set_phase_temperature(row, temperature)
                    self.model.phase_model.set_temperature(row, temperature)

    def save_btn_clicked_callback(self):
        if len(self.model.phase_model.phase_files) < 1:
            return
        filename = save_file_dialog(self.integration_widget, "Save Phase List.",
                                    os.path.join(self.model.working_directories['phase'], 'phase_list.txt'),
                                    'Text (*.txt)')

        if filename == '':
            return

        with open(filename, 'w') as phase_file:
            for file_name, phase_cb, color_btn, row in zip(self.model.phase_model.phase_files,
                                                           self.phase_widget.phase_show_cbs,
                                                           self.phase_widget.phase_color_btns,
                                                           range(self.phase_widget.phase_tw.rowCount())):
                phase_file.write(file_name + ',' + str(phase_cb.isChecked()) + ',' +
                                 color_btn.styleSheet().replace('background-color:', '').replace(' ', '') + ',' +
                                 self.phase_widget.phase_tw.item(row, 2).text() + ',' +
                                 self.phase_widget.pressure_sbs[row].text() + ',' +
                                 self.phase_widget.temperature_sbs[row].text() + '\n')

    def clear_phases(self):
        """
        Deletes all phases from the GUI and phase data
        """
        while self.phase_widget.phase_tw.rowCount() > 0:
            self.delete_btn_click_callback()
            self.jcpds_editor_controller.close_view()

    def update_pressure_step(self):
        for pressure_sb in self.phase_widget.pressure_sbs:
            pressure_sb.setSingleStep(self.phase_widget.pressure_step_msb.value())

    def update_temperature_step(self):
        for temperature_sb in self.phase_widget.temperature_sbs:
            temperature_sb.setSingleStep(self.phase_widget.temperature_step_msb.value())

    def color_btn_clicked(self, ind, button):
        previous_color = button.palette().color(1)
        new_color = QtWidgets.QColorDialog.getColor(previous_color, self.integration_widget)
        if new_color.isValid():
            color = new_color.toRgb()
        else:
            color = previous_color.toRgb()
        self.model.phase_model.set_color(ind, (color.red(), color.green(), color.blue()))
        button.setStyleSheet('background-color:' + str(color.name()))

    def apply_to_all_callback(self):
        self.model.phase_model.same_conditions = self.phase_widget.apply_to_all_cb.isChecked()

    def phase_tw_header_section_clicked(self, ind):
        if ind != 0:
            return

        current_checkbox_state = False
        # check whether any checkbox is checked, if one is true current_checkbox_state will be True too
        for cb in self.phase_widget.phase_show_cbs:
            current_checkbox_state = current_checkbox_state or cb.isChecked()

        # assign the the opposite to all checkboxes
        for cb in self.phase_widget.phase_show_cbs:
            cb.setChecked(not current_checkbox_state)

    def get_unit(self):
        """
        returns the unit currently selected in the GUI
                possible values: 'tth', 'q', 'd'
        """
        if self.integration_widget.pattern_tth_btn.isChecked():
            return 'tth'
        elif self.integration_widget.pattern_q_btn.isChecked():
            return 'q'
        elif self.integration_widget.pattern_d_btn.isChecked():
            return 'd'
