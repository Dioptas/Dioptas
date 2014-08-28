# -*- coding: utf-8 -*-
# Py2DeX - GUI program for fast processing of 2D X-ray data
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
#     along with this program.  If not, see <http://www.gnu.org/licenses/>.




__author__ = 'Clemens Prescher'

import os
from copy import copy
import numpy as np

from PyQt4 import QtGui, QtCore

from Data.HelperModule import get_base_name
from Data.PhaseData import PhaseLoadError
from .JcpdsEditorController import JcpdsEditorController


class IntegrationPhaseController(object):
    def __init__(self, working_dir, view, calibration_data,
                 spectrum_data, phase_data):
        self.working_dir = working_dir
        self.view = view
        self.calibration_data = calibration_data
        self.spectrum_data = spectrum_data
        self.phase_data = phase_data
        self.jcpds_editor_controller = JcpdsEditorController(self.working_dir, self.calibration_data)
        self.phase_lw_items = []
        self.create_signals()

    def create_signals(self):
        self.connect_click_function(self.view.phase_add_btn, self.add_phase)
        self.connect_click_function(self.view.phase_del_btn, self.del_phase)
        self.connect_click_function(self.view.phase_clear_btn, self.clear_phases)
        self.connect_click_function(self.view.phase_edit_btn, self.edit_phase)

        self.view.phase_pressure_step_txt.editingFinished.connect(self.update_phase_pressure_step)
        self.view.phase_temperature_step_txt.editingFinished.connect(self.update_phase_temperature_step)

        self.view.phase_pressure_sb.valueChanged.connect(self.phase_pressure_sb_changed)
        self.view.phase_temperature_sb.valueChanged.connect(self.phase_temperature_sb_changed)
        #
        # self.view.phase_lw.currentItemChanged.connect(self.phase_item_changed)
        self.view.phase_tw.currentCellChanged.connect(self.phase_selection_changed)
        self.view.phase_color_btn_clicked.connect(self.phase_color_btn_clicked)
        self.view.phase_show_cb_state_changed.connect(self.phase_show_cb_state_changed)

        self.view.spectrum_view.view_box.sigRangeChangedManually.connect(self.update_phase_intensities_slot)
        self.view.spectrum_view.spectrum_plot.autoBtn.clicked.connect(self.spectrum_auto_btn_clicked)
        self.spectrum_data.subscribe(self.spectrum_data_changed)

        self.jcpds_editor_controller.canceled_editor.connect(self.jcpds_editor_reload_phase)

        self.jcpds_editor_controller.lattice_param_changed.connect(self.update_cur_phase_parameters)
        self.jcpds_editor_controller.eos_param_changed.connect(self.update_cur_phase_parameters)

        self.jcpds_editor_controller.reflection_line_added.connect(self.jcpds_editor_reflection_added)
        self.jcpds_editor_controller.reflection_line_removed.connect(self.jcpds_editor_reflection_removed)
        self.jcpds_editor_controller.reflection_line_edited.connect(self.update_cur_phase_parameters)
        self.jcpds_editor_controller.reflection_line_cleared.connect(self.jcpds_editor_reflection_cleared)

        self.jcpds_editor_controller.phase_modified.connect(self.update_cur_phase_name)

    def connect_click_function(self, emitter, function):
        self.view.connect(emitter, QtCore.SIGNAL('clicked()'), function)

    def add_phase(self, filename=None):
        """
        Loads a new phase from jcpds file.
        :param filename: *.jcpds filename. I not set or None it a FileDialog will open.
        :return:
        """
        if filename is None:
            filenames = QtGui.QFileDialog.getOpenFileNames(
                self.view, "Load Phase(s).", self.working_dir['phase'])
            if len(filenames):
                self.working_dir['phase'] = os.path.dirname(str(filenames[0]))
                progress_dialog = QtGui.QProgressDialog("Loading multiple phases.", "Abort Loading", 0, len(filenames),
                                                        self.view)
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
            self.phase_data.add_phase(filename)

            if self.view.phase_apply_to_all_cb.isChecked():
                pressure = np.float(self.view.phase_pressure_sb.value())
                temperature = np.float(self.view.phase_temperature_sb.value())
                self.phase_data.phases[-1].compute_d(pressure=pressure,
                                                     temperature=temperature)
            else:
                pressure = 0
                temperature = 298


            self.phase_data.get_lines_d(-1)
            color = self.add_phase_plot()
            self.view.add_phase(get_base_name(filename), '#%02x%02x%02x' % (color[0], color[1], color[2]))

            self.view.set_phase_tw_pressure(len(self.phase_data.phases)-1, pressure)
            self.update_phase_temperature(len(self.phase_data.phases)-1, temperature)
        except PhaseLoadError as e:
            msg_box = QtGui.QMessageBox(self.view)
            msg_box.setWindowFlags(QtCore.Qt.Tool)
            msg_box.setText('Could not load:\n\n{}.\n\nPlease check if the format of the input file is correct.'.\
                            format(e.filename))
            msg_box.setIcon(QtGui.QMessageBox.Critical)
            msg_box.setWindowTitle('Error')
            msg_box.setStandardButtons(QtGui.QMessageBox.Ok)
            msg_box.setDefaultButton(QtGui.QMessageBox.Ok)
            msg_box.exec_()

    def add_phase_plot(self):
        """
        Adds a phase to the Spectrum view.
        :return:
        """
        axis_range = self.view.spectrum_view.spectrum_plot.viewRange()
        x_range = axis_range[0]
        y_range = axis_range[1]
        positions, intensities, baseline = \
            self.phase_data.get_rescaled_reflections(
                -1, self.spectrum_data.spectrum,
                x_range, y_range,
                self.calibration_data.geometry.wavelength * 1e10,
                self.get_unit())
        color = self.view.spectrum_view.add_phase(self.phase_data.phases[-1].name,
                                                  positions,
                                                  intensities,
                                                  baseline)
        return color

    def edit_phase(self):
        cur_ind = self.view.get_selected_phase_row()
        self.jcpds_editor_controller.show_phase(self.phase_data.phases[cur_ind])

    def del_phase(self):
        """
        Deletes the currently selected Phase
        """
        cur_ind = self.view.get_selected_phase_row()
        if cur_ind >= 0:
            self.view.del_phase(cur_ind)
            self.phase_data.del_phase(cur_ind)
            self.view.spectrum_view.del_phase(cur_ind)
            self.update_temperature_control_visibility()
            if self.jcpds_editor_controller.active:
                cur_ind = self.view.get_selected_phase_row()
                if cur_ind>=0:
                    self.jcpds_editor_controller.show_phase(self.phase_data.phases[cur_ind])
                else:
                    self.jcpds_editor_controller.view.close()


    def clear_phases(self):
        """
        Delets all phases from the GUI and phase data
        """
        while self.view.phase_tw.rowCount() > 0:
            self.del_phase()
            self.jcpds_editor_controller.close_view()

    def update_phase_pressure_step(self):
        value = np.float(self.view.phase_pressure_step_txt.text())
        self.view.phase_pressure_sb.setSingleStep(value)

    def update_phase_temperature_step(self):
        value = np.float(self.view.phase_temperature_step_txt.text())
        self.view.phase_temperature_sb.setSingleStep(value)

    def phase_pressure_sb_changed(self, val):
        """
        Called when pressure spinbox emits a new value. Calculates the appropriate EOS values and updates line
        positions and intensities.
        """
        if self.view.phase_apply_to_all_cb.isChecked():
            for ind in range(len(self.phase_data.phases)):
                self.phase_data.set_pressure(ind, np.float(val))
                self.view.set_phase_tw_pressure(ind, val)
            self.update_phase_intensities()

        else:
            cur_ind = self.view.get_selected_phase_row()
            self.phase_data.set_pressure(cur_ind, np.float(val))
            self.view.set_phase_tw_pressure(cur_ind, val)
            self.update_phase_intensity(cur_ind)

        self.update_jcpds_editor()


    def phase_temperature_sb_changed(self, val):
        """
        Called when temperature spinbox emits a new value. Calculates the appropriate EOS values and updates line
        positions and intensities.
        """
        if self.view.phase_apply_to_all_cb.isChecked():
            for ind in range(len(self.phase_data.phases)):
                self.update_phase_temperature(ind, val)
            self.update_phase_intensities()

        else:
            cur_ind = self.view.get_selected_phase_row()
            self.update_phase_temperature(cur_ind, val)
            self.update_phase_intensity(cur_ind)

        self.update_jcpds_editor()

    def update_phase_temperature(self, ind, val):
        if self.phase_data.phases[ind].has_thermal_expansion():
            self.phase_data.set_temperature(ind, np.float(val))
            self.view.set_phase_tw_temperature(ind, val)
        else:
            self.phase_data.set_temperature(ind, 298)
            self.view.set_phase_tw_temperature(ind, '-')

    def phase_selection_changed(self, row, col, prev_row, prev_col):
        cur_ind = row
        pressure = self.phase_data.phases[cur_ind].pressure
        temperature = self.phase_data.phases[cur_ind].temperature

        self.view.phase_pressure_sb.blockSignals(True)
        self.view.phase_pressure_sb.setValue(pressure)
        self.view.phase_pressure_sb.blockSignals(False)

        self.view.phase_temperature_sb.blockSignals(True)
        self.view.phase_temperature_sb.setValue(temperature)
        self.view.phase_temperature_sb.blockSignals(False)
        self.update_temperature_control_visibility(row)

        if self.jcpds_editor_controller.active:
            self.jcpds_editor_controller.show_phase(self.phase_data.phases[cur_ind])

    def update_temperature_control_visibility(self, row_ind = None):
        if row_ind is None:
            row_ind = self.view.get_selected_phase_row()

        if row_ind == -1:
            return

        if self.phase_data.phases[row_ind].has_thermal_expansion():
            self.view.phase_temperature_sb.setEnabled(True)
            self.view.phase_temperature_step_txt.setEnabled(True)
        else:
            self.view.phase_temperature_sb.setDisabled(True)
            self.view.phase_temperature_step_txt.setDisabled(True)

    def phase_color_btn_clicked(self, ind, button):
        previous_color = button.palette().color(1)
        new_color = QtGui.QColorDialog.getColor(previous_color, self.view)
        if new_color.isValid():
            color = str(new_color.name())
        else:
            color = str(previous_color.name())
        self.view.spectrum_view.set_phase_color(ind, color)
        button.setStyleSheet('background-color:' + color)


    def phase_show_cb_state_changed(self, ind, state):
        if state:
            self.view.spectrum_view.show_phase(ind)
        else:
            self.view.spectrum_view.hide_phase(ind)

    def get_unit(self):
        """
        returns the unit currently selected in the GUI
                possible values: 'tth', 'q', 'd'
        """
        if self.view.spec_tth_btn.isChecked():
            return 'tth'
        elif self.view.spec_q_btn.isChecked():
            return 'q'
        elif self.view.spec_d_btn.isChecked():
            return 'd'


    def spectrum_auto_btn_clicked(self):
        """
        Runs self.update_intensities_slot after 50 ms.
        This is needed because the graph scaling is to slow, to call update_intensities immediately after the autoscale-btn
        was clicked
        """
        QtCore.QTimer.singleShot(50, self.update_phase_intensities_slot)

    def spectrum_data_changed(self):
        """
        Function is called after the spectrum data has changed.
        """
        # QtGui.QApplication.processEvents()
        # self.update_phase_lines_slot()
        QtCore.QTimer.singleShot(50, self.update_phase_lines_slot)


    def update_phase_intensities_slot(self, *args):
        """
        Used as a slot when autoRange of the view is. Tries to prevent a call on autorange while updating intensities of
        phases.
        """
        axis_range = self.view.spectrum_view.spectrum_plot.viewRange()
        auto_range = copy(self.view.spectrum_view.spectrum_plot.vb.state['autoRange'])

        self.view.spectrum_view.spectrum_plot.disableAutoRange()
        self.update_phase_intensities(axis_range)

        if auto_range[0] and auto_range[1]:
            self.view.spectrum_view.spectrum_plot.enableAutoRange()


    def update_phase_lines_slot(self,*args):
        self.update_phase_intensities_slot()
        self.view.spectrum_view.update_phase_line_visibilities()


    def update_phase_intensities(self, axis_range=None):
        """
        Updates all intensities of all phases in the spectrum view. Also checks if phase lines are still visible.
        (within range of spectrum and/or overlays
        :param axis_range: list/tuple of x_range and y_range -- ((x_min, x_max), (y_min, y_max)
        """
        self.view.spectrum_view.view_box.blockSignals(True)
        for ind in range(len(self.phase_data.phases)):
            self.update_phase_intensity(ind, axis_range)
        self.view.spectrum_view.view_box.blockSignals(False)

    def update_phase_intensity(self, ind, axis_range=None):
        """
        Updates the intensities of a specific phase with index ind.
        :param ind: Index of the phase
        :param axis_range: list/tuple of visible x_range and y_range -- ((x_min, x_max), (y_min, y_max))
        """
        if axis_range is None:
            axis_range = self.view.spectrum_view.spectrum_plot.viewRange()
        x_range = axis_range[0]
        y_range = axis_range[1]
        positions, intensities, baseline = \
            self.phase_data.get_rescaled_reflections(
                ind, self.spectrum_data.spectrum,
                x_range, y_range,
                self.calibration_data.geometry.wavelength * 1e10,
                self.get_unit())
        self.view.spectrum_view.update_phase_intensities(
            ind, positions, intensities, baseline)

    def update_cur_phase_name(self):
        cur_ind = self.view.get_selected_phase_row()
        self.view.rename_phase(cur_ind, self.phase_data.phases[cur_ind].name)

    def update_jcpds_editor(self, cur_ind=None):
        if cur_ind is None:
            cur_ind = self.view.get_selected_phase_row()
        if self.jcpds_editor_controller.view.isVisible():
            self.jcpds_editor_controller.update_phase_view(self.phase_data.phases[cur_ind])

    def jcpds_editor_reload_phase(self, jcpds):
        cur_ind = self.view.get_selected_phase_row()
        self.phase_data.phases[cur_ind] = jcpds
        self.view.spectrum_view.phases[cur_ind].clear_lines()
        for dummy_line_ind in self.phase_data.phases[cur_ind].reflections:
            self.view.spectrum_view.phases[cur_ind].add_line()
        self.update_cur_phase_parameters()

    def update_cur_phase_parameters(self):
        cur_ind = self.view.get_selected_phase_row()
        self.phase_data.get_lines_d(cur_ind)
        self.update_phase_intensity(cur_ind)
        self.update_temperature_control_visibility(cur_ind)
        self.view.spectrum_view.update_phase_line_visibility(cur_ind)

    def jcpds_editor_reflection_removed(self, reflection_ind):
        cur_phase_ind = self.view.get_selected_phase_row()
        self.view.spectrum_view.phases[cur_phase_ind].remove_line(reflection_ind)
        self.phase_data.get_lines_d(cur_phase_ind)

    def jcpds_editor_reflection_added(self):
        cur_ind = self.view.get_selected_phase_row()
        self.view.spectrum_view.phases[cur_ind].add_line()
        self.phase_data.get_lines_d(cur_ind)

    def jcpds_editor_reflection_cleared(self):
        cur_phase_ind = self.view.get_selected_phase_row()
        self.view.spectrum_view.phases[cur_phase_ind].clear_lines()





