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

import os

import numpy as np
from qtpy import QtWidgets, QtCore

from ...model.PhaseModel import PhaseLoadError
from ...model.util.HelperModule import get_base_name
from .JcpdsEditorController import JcpdsEditorController
from ...widgets.UtilityWidgets import save_file_dialog, open_file_dialog, open_files_dialog

# imports for type hinting in PyCharm -- DO NOT DELETE
from ...model.DioptasModel import DioptasModel
from ...widgets.integration import IntegrationWidget
from ...widgets.UtilityWidgets import CifConversionParametersDialog


class PhaseController(object):
    """
    IntegrationPhaseController handles all the interaction between the phase controls in the IntegrationView and the
    PhaseData object. It needs the PatternData object to properly handle the rescaling of the phase intensities in
    the pattern plot and it needs the calibration data to have access to the currently used wavelength.
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
        self.cif_conversion_dialog = CifConversionParametersDialog(self.integration_widget)
        self.model = dioptas_model
        self.jcpds_editor_controller = JcpdsEditorController(self.integration_widget, self.model)
        self.phase_lw_items = []
        self.create_signals()
        self.update_temperature_step()
        self.update_pressure_step()

    def create_signals(self):
        self.connect_click_function(self.phase_widget.add_btn, self.add_btn_click_callback)
        self.connect_click_function(self.phase_widget.delete_btn, self.delete_btn_click_callback)
        self.connect_click_function(self.phase_widget.clear_btn, self.clear_phases)
        self.connect_click_function(self.phase_widget.edit_btn, self.edit_btn_click_callback)
        self.connect_click_function(self.phase_widget.save_list_btn, self.save_btn_clicked_callback)
        self.connect_click_function(self.phase_widget.load_list_btn, self.load_list_btn_clicked_callback)

        self.phase_widget.pressure_step_msb.valueChanged.connect(self.update_pressure_step)
        self.phase_widget.temperature_step_msb.valueChanged.connect(self.update_temperature_step)

        self.phase_widget.pressure_sb_value_changed.connect(self.pressure_sb_changed)
        self.phase_widget.temperature_sb_value_changed.connect(self.temperature_sb_changed)

        self.phase_widget.phase_tw.currentCellChanged.connect(self.phase_selection_changed)
        self.phase_widget.color_btn_clicked.connect(self.color_btn_clicked)
        self.phase_widget.show_cb_state_changed.connect(self.show_cb_state_changed)

        self.pattern_widget.view_box.sigRangeChangedManually.connect(self.update_all_phase_intensities)
        # self.widget.pattern_view.view_box.sigRangeChanged.connect(self.update_all_phase_intensities)
        self.pattern_widget.pattern_plot.autoBtn.clicked.connect(self.update_all_phase_intensities)
        self.model.pattern_changed.connect(self.pattern_data_changed)

        self.jcpds_editor_controller.canceled_editor.connect(self.jcpds_editor_reload_phase)

        self.jcpds_editor_controller.lattice_param_changed.connect(self.update_cur_phase_parameters)
        self.jcpds_editor_controller.eos_param_changed.connect(self.update_cur_phase_parameters)

        self.jcpds_editor_controller.reflection_line_added.connect(self.jcpds_editor_reflection_added)
        self.jcpds_editor_controller.reflection_line_removed.connect(self.jcpds_editor_reflection_removed)
        self.jcpds_editor_controller.reflection_line_edited.connect(self.update_cur_phase_parameters)
        self.jcpds_editor_controller.reflection_line_cleared.connect(self.jcpds_editor_reflection_cleared)

        self.jcpds_editor_controller.phase_modified.connect(self.update_phase_legend)

        # Signals from phase model
        self.model.phase_model.phase_added.connect(self.phase_added)
        self.model.phase_model.phase_removed.connect(self.phase_removed)

    def connect_click_function(self, emitter, function):
        emitter.clicked.connect(function)

    def add_btn_click_callback(self, *args, **kwargs):
        """
        Loads a new phase from jcpds file.
        :return:
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

            if self.phase_widget.apply_to_all_cb.isChecked() and len(self.model.phase_model.phases)>1 :
                pressure = float(self.phase_widget.pressure_sbs[0].value())
                temperature = float(self.phase_widget.temperature_sbs[0].value())
                self.model.phase_model.phases[-1].compute_d(pressure=pressure,
                                                            temperature=temperature)
                assert(True)
            else:
                pressure = 0
                temperature = 298

            self.model.phase_model.get_lines_d(-1)
            color = self.add_phase_plot()
            self.phase_widget.add_phase(get_base_name(filename), '#%02x%02x%02x' % (int(color[0]), int(color[1]),
                                                                                    int(color[2])))

            self.phase_widget.set_phase_pressure(len(self.model.phase_model.phases) - 1, pressure)
            self.update_phase_legend()
            self.update_temperature(len(self.model.phase_model.phases) - 1, temperature)
            if self.jcpds_editor_controller.active:
                self.jcpds_editor_controller.show_phase(self.model.phase_model.phases[-1])
        except PhaseLoadError as e:
            self.integration_widget.show_error_msg(
                'Could not load:\n\n{}.\n\nPlease check if the format of the input file is correct.'. \
                    format(e.filename))

    def phase_added(self):
        self.model.phase_model.get_lines_d(-1)
        color = self.add_phase_plot()

        self.phase_widget.add_phase(self.model.phase_model.phases[-1].name, '#%02x%02x%02x' %
                                    (int(color[0]), int(color[1]), int(color[2])))

        self.phase_widget.set_phase_pressure(len(self.model.phase_model.phases) - 1,
                                             self.model.phase_model.phases[-1].params['pressure'])
        self.update_temperature(len(self.model.phase_model.phases) - 1,
                                self.model.phase_model.phases[-1].params['temperature'])
        self.update_phase_legend()

        if self.jcpds_editor_controller.active:
            self.jcpds_editor_controller.show_phase(self.model.phase_model.phases[-1])

    def add_phase_plot(self):
        """
        Adds a phase to the Pattern view.
        :return:
        """
        axis_range = self.pattern_widget.pattern_plot.viewRange()
        x_range = axis_range[0]
        y_range = axis_range[1]
        positions, intensities, baseline = \
            self.model.phase_model.get_rescaled_reflections(
                -1, self.model.pattern,
                x_range, y_range,
                self.model.calibration_model.wavelength * 1e10,
                self.get_unit())
        color = self.pattern_widget.add_phase(self.model.phase_model.phases[-1].name,
                                              positions,
                                              intensities,
                                              baseline)
        return color

    def edit_btn_click_callback(self):
        cur_ind = self.phase_widget.get_selected_phase_row()
        self.jcpds_editor_controller.show_phase(self.model.phase_model.phases[cur_ind])
        self.jcpds_editor_controller.show_view()

    def delete_btn_click_callback(self):
        """
        Deletes the currently selected Phase
        """
        cur_ind = self.phase_widget.get_selected_phase_row()
        if cur_ind >= 0:
            self.model.phase_model.del_phase(cur_ind)

    def phase_removed(self, ind):
        self.phase_widget.del_phase(ind)
        self.pattern_widget.del_phase(ind)
        if self.jcpds_editor_controller.active:
            ind = self.phase_widget.get_selected_phase_row()
            if ind >= 0:
                self.jcpds_editor_controller.show_phase(self.model.phase_model.phases[ind])
            else:
                self.jcpds_editor_controller.widget.close()

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
                    self.update_phase_intensities(row)
                self.update_phase_legend()

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

    def pressure_sb_changed(self, ind, val):
        """
        Called when pressure spinbox emits a new value. Calculates the appropriate EOS values and updates line
        positions and intensities.
        """
        if self.phase_widget.apply_to_all_cb.isChecked():
            for ind in range(len(self.model.phase_model.phases)):
                self.model.phase_model.set_pressure(ind, np.float(val))
                self.phase_widget.set_phase_pressure(ind, val)
            self.update_all_phase_intensities()

        else:
            self.model.phase_model.set_pressure(ind, np.float(val))
            self.phase_widget.set_phase_pressure(ind, val)
            self.update_phase_intensities(ind)

        self.update_phase_legend()
        self.update_jcpds_editor()

    def temperature_sb_changed(self, ind, val):
        """
        Called when temperature spinbox emits a new value. Calculates the appropriate EOS values and updates line
        positions and intensities.
        """
        if self.phase_widget.apply_to_all_cb.isChecked():
            for ind in range(len(self.model.phase_model.phases)):
                self.update_temperature(ind, val)
            self.update_all_phase_intensities()
        else:
            self.update_temperature(ind, val)
            self.update_phase_intensities(ind)
        self.update_phase_legend()
        self.update_jcpds_editor()

    def update_temperature(self, ind, val):
        if self.model.phase_model.phases[ind].has_thermal_expansion():
            self.model.phase_model.set_temperature(ind, np.float(val))
            self.phase_widget.set_phase_temperature(ind, val)
            self.phase_widget.temperature_sbs[ind].setEnabled(True)
        else:
            self.model.phase_model.set_temperature(ind, 298)
            self.phase_widget.set_phase_temperature(ind, 298)
            self.phase_widget.temperature_sbs[ind].setEnabled(False)
        self.update_phase_legend()

    def update_phase_legend(self):
        for ind in range(len(self.model.phase_model.phases)):
            name = self.model.phase_model.phases[ind].name
            parameter_str = ''
            pressure = self.model.phase_model.phases[ind].params['pressure']
            temperature = self.model.phase_model.phases[ind].params['temperature']
            if pressure != 0:
                parameter_str += '{:0.2f} GPa '.format(pressure)
            if temperature != 0 and temperature != 298 and temperature is not None:
                parameter_str += '{:0.2f} K '.format(temperature)
            self.pattern_widget.rename_phase(ind, parameter_str + name)

    def phase_selection_changed(self, row, col, prev_row, prev_col):
        if self.jcpds_editor_controller.active:
            self.jcpds_editor_controller.show_phase(self.model.phase_model.phases[row])

    def color_btn_clicked(self, ind, button):
        previous_color = button.palette().color(1)
        new_color = QtWidgets.QColorDialog.getColor(previous_color, self.integration_widget)
        if new_color.isValid():
            color = str(new_color.name())
        else:
            color = str(previous_color.name())
        self.pattern_widget.set_phase_color(ind, color)
        button.setStyleSheet('background-color:' + color)

    def show_cb_state_changed(self, ind, state):
        if state:
            self.pattern_widget.show_phase(ind)
        else:
            self.pattern_widget.hide_phase(ind)

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

    def pattern_data_changed(self):
        """
        Function is called after the pattern data has changed.
        """
        # QtWidgets.QApplication.processEvents()
        # self.update_phase_lines_slot()
        self.pattern_widget.update_phase_line_visibilities()

    def update_all_phase_intensities(self):
        """
        Updates all intensities of all phases in the pattern view. Also checks if phase lines are still visible.
        (within range of pattern and/or overlays
        """
        axis_range = self.pattern_widget.view_box.viewRange()

        for ind in range(len(self.model.phase_model.phases)):
            self.update_phase_intensities(ind, axis_range)

    def update_phase_intensities(self, ind, axis_range=None):
        """
        Updates the intensities of a specific phase with index ind.
        :param ind: Index of the phase
        :param axis_range: list/tuple of visible x_range and y_range -- ((x_min, x_max), (y_min, y_max))
        """
        if axis_range is None:
            axis_range = self.pattern_widget.view_box.viewRange()

        x_range = axis_range[0]
        y_range = axis_range[1]
        positions, intensities, baseline = self.model.phase_model.get_rescaled_reflections(
            ind, self.model.pattern,
            x_range, y_range,
            self.model.calibration_model.wavelength * 1e10,
            self.get_unit()
        )

        self.pattern_widget.update_phase_intensities(
            ind, positions, intensities, y_range[0])

    ###JCPDS editor callbacks:
    def update_jcpds_editor(self, cur_ind=None):
        if cur_ind is None:
            cur_ind = self.phase_widget.get_selected_phase_row()
        if self.jcpds_editor_controller.widget.isVisible():
            self.jcpds_editor_controller.update_phase_view(self.model.phase_model.phases[cur_ind])

    def jcpds_editor_reload_phase(self, jcpds):
        cur_ind = self.phase_widget.get_selected_phase_row()
        self.model.phase_model.phases[cur_ind] = jcpds
        self.pattern_widget.phases[cur_ind].clear_lines()
        for dummy_line_ind in self.model.phase_model.phases[cur_ind].reflections:
            self.pattern_widget.phases[cur_ind].add_line()
        self.update_cur_phase_parameters()

    def update_cur_phase_parameters(self):
        cur_ind = self.phase_widget.get_selected_phase_row()
        self.model.phase_model.get_lines_d(cur_ind)
        self.update_phase_intensities(cur_ind)
        self.pattern_widget.update_phase_line_visibility(cur_ind)

    def jcpds_editor_reflection_removed(self, reflection_ind):
        cur_phase_ind = self.phase_widget.get_selected_phase_row()
        self.pattern_widget.phases[cur_phase_ind].remove_line(reflection_ind)
        self.model.phase_model.get_lines_d(cur_phase_ind)
        self.update_phase_intensities(cur_phase_ind)

    def jcpds_editor_reflection_added(self):
        cur_ind = self.phase_widget.get_selected_phase_row()
        self.pattern_widget.phases[cur_ind].add_line()
        self.model.phase_model.get_lines_d(cur_ind)

    def jcpds_editor_reflection_cleared(self):
        cur_phase_ind = self.phase_widget.get_selected_phase_row()
        self.pattern_widget.phases[cur_phase_ind].clear_lines()
