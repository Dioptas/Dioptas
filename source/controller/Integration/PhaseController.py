# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2014  Clemens Prescher (clemens.prescher@gmail.com)
# GSECARS, University of Chicago
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


__author__ = 'Clemens Prescher'

import os

import numpy as np
from PyQt4 import QtGui, QtCore

from model.Helper.HelperModule import get_base_name
from model.PhaseModel import PhaseLoadError
from .JcpdsEditorController import JcpdsEditorController


# imports for type hinting in PyCharm -- DO NOT DELETE
from widgets.IntegrationWidget import IntegrationWidget
from model.CalibrationModel import CalibrationModel
from model.SpectrumModel import SpectrumModel
from model.PhaseModel import PhaseModel

class PhaseController(object):
    """
    IntegrationPhaseController handles all the interaction between the phase controls in the IntegrationView and the
    PhaseData object. It needs the SpectrumData object to properly handle the rescaling of the phase intensities in
    the spectrum plot and it needs the calibration data to have access to the currently used wavelength.
    """
    def __init__(self, working_dir, widget, calibration_model, spectrum_model, phase_model):
        """
        :param working_dir: dictionary with working directories
        :param widget: Reference to an IntegrationWidget
        :param calibration_model: reference to CalibrationModel object
        :param spectrum_model: reference to SpectrumModel object
        :param phase_model: reference to PhaseModel object

        :type widget: IntegrationWidget
        :type calibration_model: CalibrationModel
        :type spectrum_model: SpectrumModel
        :type phase_model: PhaseModel
        """
        self.working_dir = working_dir
        self.widget = widget
        self.calibration_model = calibration_model
        self.spectrum_model = spectrum_model
        self.phase_model = phase_model
        self.jcpds_editor_controller = JcpdsEditorController(self.working_dir, self.calibration_model)
        self.phase_lw_items = []
        self.create_signals()

    def create_signals(self):
        self.connect_click_function(self.widget.phase_add_btn, self.add_btn_click_callback)
        self.connect_click_function(self.widget.phase_del_btn, self.remove_btn_click_callback)
        self.connect_click_function(self.widget.phase_clear_btn, self.clear_phases)
        self.connect_click_function(self.widget.phase_edit_btn, self.edit_btn_click_callback)

        self.widget.phase_pressure_step_txt.editingFinished.connect(self.update_phase_pressure_step)
        self.widget.phase_temperature_step_txt.editingFinished.connect(self.update_phase_temperature_step)

        self.widget.phase_pressure_sb.valueChanged.connect(self.phase_pressure_sb_changed)
        self.widget.phase_temperature_sb.valueChanged.connect(self.phase_temperature_sb_changed)

        self.widget.phase_show_parameter_in_spectrum_cb.stateChanged.connect(self.phase_show_parameter_cb_state_changed)

        self.widget.phase_tw.currentCellChanged.connect(self.phase_selection_changed)
        self.widget.phase_color_btn_clicked.connect(self.phase_color_btn_clicked)
        self.widget.phase_show_cb_state_changed.connect(self.phase_show_cb_state_changed)

        # self.view.spectrum_view.view_box.sigRangeChangedManually.connect(self.update_all_phase_intensities)
        self.widget.spectrum_view.view_box.sigRangeChanged.connect(self.update_all_phase_intensities)
        self.widget.spectrum_view.spectrum_plot.autoBtn.clicked.connect(self.update_all_phase_intensities)
        self.spectrum_model.spectrum_changed.connect(self.spectrum_data_changed)

        self.jcpds_editor_controller.canceled_editor.connect(self.jcpds_editor_reload_phase)

        self.jcpds_editor_controller.lattice_param_changed.connect(self.update_cur_phase_parameters)
        self.jcpds_editor_controller.eos_param_changed.connect(self.update_cur_phase_parameters)

        self.jcpds_editor_controller.reflection_line_added.connect(self.jcpds_editor_reflection_added)
        self.jcpds_editor_controller.reflection_line_removed.connect(self.jcpds_editor_reflection_removed)
        self.jcpds_editor_controller.reflection_line_edited.connect(self.update_cur_phase_parameters)
        self.jcpds_editor_controller.reflection_line_cleared.connect(self.jcpds_editor_reflection_cleared)

        self.jcpds_editor_controller.phase_modified.connect(self.update_cur_phase_name)

    def connect_click_function(self, emitter, function):
        self.widget.connect(emitter, QtCore.SIGNAL('clicked()'), function)

    def add_btn_click_callback(self, filename=None):
        """
        Loads a new phase from jcpds file.
        :param filename: *.jcpds filename. I not set or None it a FileDialog will open.
        :return:
        """
        if not self.calibration_model.is_calibrated:
            self.widget.show_error_msg("Can not load phase without calibration.")

        if filename is None:
            filenames = QtGui.QFileDialog.getOpenFileNames(
                self.widget, "Load Phase(s).", self.working_dir['phase'])
            if len(filenames):
                self.working_dir['phase'] = os.path.dirname(str(filenames[0]))
                progress_dialog = QtGui.QProgressDialog("Loading multiple phases.", "Abort Loading", 0, len(filenames),
                                                        self.widget)
                progress_dialog.setWindowModality(QtCore.Qt.WindowModal)
                progress_dialog.setWindowFlags(QtCore.Qt.FramelessWindowHint)
                progress_dialog.show()
                QtGui.QApplication.processEvents()
                for ind, filename in enumerate(filenames):
                    filename = str(filename)
                    progress_dialog.setValue(ind)
                    progress_dialog.setLabelText("Loading: " + os.path.basename(filename))
                    QtGui.QApplication.processEvents()

                    self._add_phase(filename)

                    if progress_dialog.wasCanceled():
                        break
                progress_dialog.close()
                QtGui.QApplication.processEvents()
                self.update_temperature_control_visibility()
        else:
            self._add_phase(filename)
            self.working_dir['phase'] = os.path.dirname(str(filename))
            self.update_temperature_control_visibility()

    def _add_phase(self, filename):
        try:
            self.phase_model.add_phase(filename)

            if self.widget.phase_apply_to_all_cb.isChecked():
                pressure = np.float(self.widget.phase_pressure_sb.value())
                temperature = np.float(self.widget.phase_temperature_sb.value())
                self.phase_model.phases[-1].compute_d(pressure=pressure,
                                                     temperature=temperature)
            else:
                pressure = 0
                temperature = 298


            self.phase_model.get_lines_d(-1)
            color = self.add_phase_plot()
            self.widget.add_phase(get_base_name(filename), '#%02x%02x%02x' % (color[0], color[1], color[2]))

            self.widget.set_phase_pressure(len(self.phase_model.phases)-1, pressure)
            self.update_phase_temperature(len(self.phase_model.phases)-1, temperature)
        except PhaseLoadError as e:
            self.widget.show_error_msg('Could not load:\n\n{0}.\n\nPlease check if the format of the input file is correct.'.\
                                    format(e.filename))

    def add_phase_plot(self):
        """
        Adds a phase to the Spectrum view.
        :return:
        """
        axis_range = self.widget.spectrum_view.spectrum_plot.viewRange()
        x_range = axis_range[0]
        y_range = axis_range[1]
        positions, intensities, baseline = \
            self.phase_model.get_rescaled_reflections(
                -1, self.spectrum_model.spectrum,
                x_range, y_range,
                self.calibration_model.wavelength * 1e10,
                self.get_unit())
        color = self.widget.spectrum_view.add_phase(self.phase_model.phases[-1].name,
                                                  positions,
                                                  intensities,
                                                  baseline)
        return color

    def edit_btn_click_callback(self):
        cur_ind = self.widget.get_selected_phase_row()
        self.jcpds_editor_controller.show_phase(self.phase_model.phases[cur_ind])
        self.jcpds_editor_controller.show_view()

    def remove_btn_click_callback(self):
        """
        Deletes the currently selected Phase
        """
        cur_ind = self.widget.get_selected_phase_row()
        if cur_ind >= 0:
            self.widget.del_phase(cur_ind)
            self.phase_model.del_phase(cur_ind)
            self.widget.spectrum_view.del_phase(cur_ind)
            self.update_temperature_control_visibility()
            if self.jcpds_editor_controller.active:
                cur_ind = self.widget.get_selected_phase_row()
                if cur_ind>=0:
                    self.jcpds_editor_controller.show_phase(self.phase_model.phases[cur_ind])
                else:
                    self.jcpds_editor_controller.widget.close()


    def clear_phases(self):
        """
        Deletes all phases from the GUI and phase data
        """
        while self.widget.phase_tw.rowCount() > 0:
            self.remove_btn_click_callback()
            self.jcpds_editor_controller.close_view()

    def update_phase_pressure_step(self):
        value = np.float(self.widget.phase_pressure_step_txt.text())
        self.widget.phase_pressure_sb.setSingleStep(value)

    def update_phase_temperature_step(self):
        value = np.float(self.widget.phase_temperature_step_txt.text())
        self.widget.phase_temperature_sb.setSingleStep(value)

    def phase_pressure_sb_changed(self, val):
        """
        Called when pressure spinbox emits a new value. Calculates the appropriate EOS values and updates line
        positions and intensities.
        """
        if self.widget.phase_apply_to_all_cb.isChecked():
            for ind in range(len(self.phase_model.phases)):
                self.phase_model.set_pressure(ind, np.float(val))
                self.widget.set_phase_pressure(ind, val)
            self.update_all_phase_intensities()

        else:
            cur_ind = self.widget.get_selected_phase_row()
            self.phase_model.set_pressure(cur_ind, np.float(val))
            self.widget.set_phase_pressure(cur_ind, val)
            self.update_phase_intensities(cur_ind)

        self.update_jcpds_editor()


    def phase_temperature_sb_changed(self, val):
        """
        Called when temperature spinbox emits a new value. Calculates the appropriate EOS values and updates line
        positions and intensities.
        """
        if self.widget.phase_apply_to_all_cb.isChecked():
            for ind in range(len(self.phase_model.phases)):
                self.update_phase_temperature(ind, val)
            self.update_all_phase_intensities()

        else:
            cur_ind = self.widget.get_selected_phase_row()
            self.update_phase_temperature(cur_ind, val)
            self.update_phase_intensities(cur_ind)

        self.update_jcpds_editor()


    def update_phase_temperature(self, ind, val):
        if self.phase_model.phases[ind].has_thermal_expansion():
            self.phase_model.set_temperature(ind, np.float(val))
            self.widget.set_phase_temperature(ind, val)
        else:
            self.phase_model.set_temperature(ind, 298)
            self.widget.set_phase_temperature(ind, '-')

    def phase_show_parameter_cb_state_changed(self):
        value = self.widget.phase_show_parameter_in_spectrum_cb.isChecked()
        self.widget.show_parameter_in_spectrum = value
        for ind in range(len(self.phase_model.phases)):
            self.widget.update_phase_parameters_in_legend(ind)

    def phase_selection_changed(self, row, col, prev_row, prev_col):
        cur_ind = row
        pressure = self.phase_model.phases[cur_ind].pressure
        temperature = self.phase_model.phases[cur_ind].temperature

        self.widget.phase_pressure_sb.blockSignals(True)
        self.widget.phase_pressure_sb.setValue(pressure)
        self.widget.phase_pressure_sb.blockSignals(False)

        self.widget.phase_temperature_sb.blockSignals(True)
        self.widget.phase_temperature_sb.setValue(temperature)
        self.widget.phase_temperature_sb.blockSignals(False)
        self.update_temperature_control_visibility(row)

        if self.jcpds_editor_controller.active:
            self.jcpds_editor_controller.show_phase(self.phase_model.phases[cur_ind])

    def update_temperature_control_visibility(self, row_ind = None):
        if row_ind is None:
            row_ind = self.widget.get_selected_phase_row()

        if row_ind == -1:
            return

        if self.phase_model.phases[row_ind].has_thermal_expansion():
            self.widget.phase_temperature_sb.setEnabled(True)
            self.widget.phase_temperature_step_txt.setEnabled(True)
        else:
            self.widget.phase_temperature_sb.setDisabled(True)
            self.widget.phase_temperature_step_txt.setDisabled(True)

    def phase_color_btn_clicked(self, ind, button):
        previous_color = button.palette().color(1)
        new_color = QtGui.QColorDialog.getColor(previous_color, self.widget)
        if new_color.isValid():
            color = str(new_color.name())
        else:
            color = str(previous_color.name())
        self.widget.spectrum_view.set_phase_color(ind, color)
        button.setStyleSheet('background-color:' + color)


    def phase_show_cb_state_changed(self, ind, state):
        if state:
            self.widget.spectrum_view.show_phase(ind)
        else:
            self.widget.spectrum_view.hide_phase(ind)

    def get_unit(self):
        """
        returns the unit currently selected in the GUI
                possible values: 'tth', 'q', 'd'
        """
        if self.widget.spec_tth_btn.isChecked():
            return 'tth'
        elif self.widget.spec_q_btn.isChecked():
            return 'q'
        elif self.widget.spec_d_btn.isChecked():
            return 'd'


    def spectrum_data_changed(self):
        """
        Function is called after the spectrum data has changed.
        """
        # QtGui.QApplication.processEvents()
        # self.update_phase_lines_slot()
        self.widget.spectrum_view.update_phase_line_visibilities()


    def update_all_phase_intensities(self):
        """
        Updates all intensities of all phases in the spectrum view. Also checks if phase lines are still visible.
        (within range of spectrum and/or overlays
        :param axis_range: list/tuple of x_range and y_range -- ((x_min, x_max), (y_min, y_max)
        """
        axis_range = self.widget.spectrum_view.view_box.viewRange()

        for ind in range(len(self.phase_model.phases)):
            self.update_phase_intensities(ind, axis_range)

    def update_phase_intensities(self, ind, axis_range=None):
        """
        Updates the intensities of a specific phase with index ind.
        :param ind: Index of the phase
        :param axis_range: list/tuple of visible x_range and y_range -- ((x_min, x_max), (y_min, y_max))
        """
        if axis_range is None:
            axis_range = self.widget.spectrum_view.view_box.viewRange()

        x_range = axis_range[0]
        y_range = axis_range[1]
        positions, intensities, baseline =  self.phase_model.get_rescaled_reflections(
                            ind, self.spectrum_model.spectrum,
                            x_range, y_range,
                            self.calibration_model.wavelength * 1e10,
                            self.get_unit()
        )

        self.widget.spectrum_view.update_phase_intensities(
            ind, positions, intensities, y_range[0])

    def update_cur_phase_name(self):
        cur_ind = self.widget.get_selected_phase_row()
        self.widget.rename_phase(cur_ind, self.phase_model.phases[cur_ind].name)

    ###JCPDS editor callbacks:
    def update_jcpds_editor(self, cur_ind=None):
        if cur_ind is None:
            cur_ind = self.widget.get_selected_phase_row()
        if self.jcpds_editor_controller.widget.isVisible():
            self.jcpds_editor_controller.update_phase_view(self.phase_model.phases[cur_ind])

    def jcpds_editor_reload_phase(self, jcpds):
        cur_ind = self.widget.get_selected_phase_row()
        self.phase_model.phases[cur_ind] = jcpds
        self.widget.spectrum_view.phases[cur_ind].clear_lines()
        for dummy_line_ind in self.phase_model.phases[cur_ind].reflections:
            self.widget.spectrum_view.phases[cur_ind].add_line()
        self.update_cur_phase_parameters()

    def update_cur_phase_parameters(self):
        cur_ind = self.widget.get_selected_phase_row()
        self.phase_model.get_lines_d(cur_ind)
        self.update_phase_intensities(cur_ind)
        self.update_temperature_control_visibility(cur_ind)
        self.widget.spectrum_view.update_phase_line_visibility(cur_ind)

    def jcpds_editor_reflection_removed(self, reflection_ind):
        cur_phase_ind = self.widget.get_selected_phase_row()
        self.widget.spectrum_view.phases[cur_phase_ind].remove_line(reflection_ind)
        self.phase_model.get_lines_d(cur_phase_ind)
        self.update_phase_intensities(cur_phase_ind)

    def jcpds_editor_reflection_added(self):
        cur_ind = self.widget.get_selected_phase_row()
        self.widget.spectrum_view.phases[cur_ind].add_line()
        self.phase_model.get_lines_d(cur_ind)

    def jcpds_editor_reflection_cleared(self):
        cur_phase_ind = self.widget.get_selected_phase_row()
        self.widget.spectrum_view.phases[cur_phase_ind].clear_lines()





