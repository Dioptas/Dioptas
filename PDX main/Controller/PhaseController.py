__author__ = 'Clemens Prescher'

import os
from PyQt4 import QtGui, QtCore
import numpy as np
from Data.HelperModule import get_base_name


class IntegrationPhaseController(object):
    def __init__(self, view, calibration_data, spectrum_data, phase_data):
        self.view = view
        self.calibration_data = calibration_data
        self.spectrum_data = spectrum_data
        self.phase_data = phase_data
        self._working_dir = ''
        self.phase_lw_items = []
        self.create_signals()

    def create_signals(self):
        self.connect_click_function(self.view.phase_add_btn, self.add_phase)
        self.connect_click_function(self.view.phase_del_btn, self.del_phase)
        self.connect_click_function(self.view.phase_clear_btn, self.clear_phases)

        self.view.phase_pressure_step_txt.editingFinished.connect(self.update_phase_pressure_step)
        self.view.phase_temperature_step_txt.editingFinished.connect(self.update_phase_pressure_step)

        self.view.phase_pressure_sb.valueChanged.connect(self.phase_pressure_sb_changed)
        self.view.phase_temperature_sb.valueChanged.connect(self.phase_temperature_sb_changed)

        self.view.phase_lw.currentItemChanged.connect(self.phase_item_changed)

        self.spectrum_data.subscribe(self.update_all)

    def connect_click_function(self, emitter, function):
        self.view.connect(emitter, QtCore.SIGNAL('clicked()'), function)

    def add_phase(self, filename=None):
        dialog = QtGui.QFileDialog()
        dialog.setFileMode(QtGui.QFileDialog.ExistingFiles)
        dialog.setWindowTitle("Load Phase(s).")
        dialog.setDirectory(self._working_dir)
        if filename is None:
            if (dialog.exec_()):
                filenames = dialog.selectedFiles()
                for filename in filenames:
                    filename = str(filename)
                    self.phase_data.add_phase(filename)
                    self.phase_lw_items.append(self.view.phase_lw.addItem(get_base_name(filename)))

                    if self.view.phase_apply_to_all_cb.isChecked():
                        self.phase_data.phases[-1].compute_d(pressure=np.float(self.view.phase_pressure_sb.value()),
                                                             temperature=np.float(
                                                                 self.view.phase_temperature_sb.value()))
                    self.view.phase_lw.setCurrentRow(len(self.phase_data.phases) - 1)
                    self.add_phase_plot()
                self._working_dir = os.path.dirname(str(filenames[0]))

        else:
            self.phase_data.add_phase(filename)
            self.phase_lw_items.append(self.view.phase_lw.addItem(get_base_name(filename)))
            if self.view.phase_apply_to_all_cb.isChecked():
                self.phase_data.phases[-1].compute_d(pressure=np.float(self.view.phase_pressure_sb.value()),
                                                     temperature=np.float(self.view.phase_temperature_sb.value()))
            self.view.phase_lw.setCurrentRow(len(self.phase_data.phases) - 1)
            self.add_phase_plot()
            self._working_dir = os.path.dirname(str(filename))

    def add_phase_plot(self):
        reflections = self.phase_data.get_reflections_data(-1, self.calibration_data.geometry.wavelength * 1e10,
                                                           self.spectrum_data.spectrum)
        self.view.spectrum_view.add_phase(self.phase_data.phases[-1].name, reflections[:, 0], reflections[:, 1])


    def del_phase(self):
        cur_ind = self.view.phase_lw.currentRow()
        if cur_ind >= 0:
            self.view.phase_lw.takeItem(cur_ind)
            self.phase_data.del_phase(cur_ind)
            self.view.spectrum_view.del_phase(cur_ind)
            if cur_ind > 1:
                self.view.phase_lw.setCurrentRow(cur_ind - 1)

    def clear_phases(self):
        while self.view.phase_lw.count() > 0:
            self.del_phase()

    def update_phase_pressure_step(self):
        value = np.float(self.view.phase_pressure_step_txt.text())
        self.view.phase_pressure_sb.setSingleStep(value)

    def update_phase_temperature_step(self):
        value = np.float(self.view.phase_temperature_step_txt.text())
        self.view.phase_temperature_sb.setSingleStep(value)

    def phase_pressure_sb_changed(self, val):
        if self.view.phase_apply_to_all_cb.isChecked():
            for ind in xrange(self.view.phase_lw.count()):
                self.phase_data.set_pressure(ind, np.float(val))
                reflections = self.phase_data.get_reflections_data(ind,
                                                                   self.calibration_data.geometry.wavelength * 1e10,
                                                                   self.spectrum_data.spectrum)
                self.view.spectrum_view.update_phase(ind, reflections[:, 0], reflections[:, 1])

        else:
            cur_ind = self.view.phase_lw.currentRow()
            self.phase_data.set_pressure(cur_ind, np.float(val))
            reflections = self.phase_data.get_reflections_data(cur_ind,
                                                               self.calibration_data.geometry.wavelength * 1e10,
                                                               self.spectrum_data.spectrum)
            self.view.spectrum_view.update_phase(cur_ind, reflections[:, 0], reflections[:, 1])
        print val

    def phase_temperature_sb_changed(self, val):
        if self.view.phase_apply_to_all_cb.isChecked():
            for ind in xrange(self.view.phase_lw.count()):
                self.phase_data.set_temperature(ind, np.float(val))
                reflections = self.phase_data.get_reflections_data(ind,
                                                                   self.calibration_data.geometry.wavelength * 1e10,
                                                                   self.spectrum_data.spectrum)
                self.view.spectrum_view.update_phase(ind, reflections[:, 0], reflections[:, 1])

        else:
            cur_ind = self.view.phase_lw.currentRow()
            self.phase_data.set_temperature(cur_ind, np.float(val))
            reflections = self.phase_data.get_reflections_data(cur_ind,
                                                               self.calibration_data.geometry.wavelength * 1e10,
                                                               self.spectrum_data.spectrum)
            self.view.spectrum_view.update_phase(cur_ind, reflections[:, 0], reflections[:, 1])

        print val

    def phase_item_changed(self):
        cur_ind = self.view.phase_lw.currentRow()
        pressure = self.phase_data.phases[cur_ind].pressure
        temperature = self.phase_data.phases[cur_ind].temperature

        self.view.phase_pressure_sb.blockSignals(True)
        self.view.phase_temperature_sb.blockSignals(True)
        self.view.phase_pressure_sb.setValue(pressure)
        self.view.phase_temperature_sb.setValue(temperature)
        self.view.phase_pressure_sb.blockSignals(False)
        self.view.phase_temperature_sb.blockSignals(False)

    def update_all(self):
        for ind in xrange(self.view.phase_lw.count()):
            reflections = self.phase_data.get_reflections_data(ind,
                                                               self.calibration_data.geometry.wavelength * 1e10,
                                                               self.spectrum_data.spectrum)
            self.view.spectrum_view.update_phase(ind, reflections[:, 0], reflections[:, 1])
