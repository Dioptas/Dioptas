# -*- coding: utf8 -*-
#     Py2DeX - GUI program for fast processing of 2D X-ray data
#     Copyright (C) 2014  Clemens Prescher (clemens.prescher@gmail.com)
#     GSECARS, University of Chicago
#
#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.
#
#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <http://www.gnu.org/licenses/>.
__author__ = 'Clemens Prescher'

import os
from PyQt4 import QtGui, QtCore
import pyFAI
import numpy as np


class IntegrationSpectrumController(object):
    def __init__(self, working_dir, view, img_data, mask_data, calibration_data, spectrum_data):
        self.working_dir = working_dir
        self.view = view
        self.img_data = img_data
        self.mask_data = mask_data
        self.calibration_data = calibration_data
        self.spectrum_data = spectrum_data

        self.create_subscriptions()
        self.integration_unit = '2th_deg'
        self.first_plot = True
        self.set_status()

        self.create_signals()

    def create_subscriptions(self):
        self.img_data.subscribe(self.image_changed)
        self.spectrum_data.subscribe(self.plot_spectra)
        self.view.spectrum_view.add_left_click_observer(self.spectrum_left_click)

    def set_status(self):
        self.autocreate = False
        self.unit = pyFAI.units.TTH_DEG

    def create_signals(self):
        self.connect_click_function(self.view.spec_autocreate_cb, self.autocreate_cb_changed)
        self.connect_click_function(self.view.spec_load_btn, self.load)
        self.connect_click_function(self.view.spec_previous_btn, self.load_previous)
        self.connect_click_function(self.view.spec_next_btn, self.load_next)
        self.connect_click_function(self.view.spec_directory_btn, self.spec_directory_btn_click)
        self.connect_click_function(self.view.spec_browse_by_name_rb, self.set_iteration_mode_number)
        self.connect_click_function(self.view.spec_browse_by_time_rb, self.set_iteration_mode_time)
        self.connect_click_function(self.view.spec_unit_tth_rb, self.set_unit_tth)
        self.connect_click_function(self.view.spec_unit_q_rb, self.set_unit_q)
        self.view.connect(self.view.spec_directory_txt, QtCore.SIGNAL('editingFinished()'),
                          self.spec_directory_txt_changed)

    def connect_click_function(self, emitter, function):
        self.view.connect(emitter, QtCore.SIGNAL('clicked()'), function)

    def image_changed(self):
        if self.calibration_data.is_calibrated:
            if self.autocreate:
                filename = self.img_data.filename
                if filename is not '':
                    filename = os.path.join(self.working_dir['spectrum'],
                                            os.path.basename(self.img_data.filename).split('.')[:-1][0] + '.xy')

                self.view.spec_next_btn.setEnabled(True)
                self.view.spec_previous_btn.setEnabled(True)
                self.view.spec_filename_lbl.setText(os.path.basename(filename))
                self.view.spec_directory_txt.setText(os.path.dirname(filename))
            else:
                self.view.spec_next_btn.setEnabled(False)
                self.view.spec_previous_btn.setEnabled(False)
                self.view.spec_filename_lbl.setText('No File saved or selected')
                filename = None

            if self.view.mask_use_cb.isChecked():
                self.mask_data.set_dimension(self.img_data.img_data.shape)
                mask = self.mask_data.get_mask()
            else:
                mask = None

            tth, I = self.calibration_data.integrate_1d(filename=filename, mask=mask, unit=self.integration_unit)
            if filename is not None:
                spectrum_name = filename
            else:
                spectrum_name = self.img_data.filename
            self.spectrum_data.set_spectrum(tth, I, spectrum_name)

    def plot_spectra(self):
        x, y = self.spectrum_data.spectrum.data
        self.view.spectrum_view.plot_data(x, y, self.spectrum_data.spectrum.name)

        if self.first_plot:
            self.view.spectrum_view.spectrum_plot.enableAutoRange()
            self.first_plot = False

        # save the background subtracted file:
        if self.spectrum_data.bkg_ind is not -1:
            if self.autocreate:
                directory = os.path.join(self.working_dir['spectrum'], 'bkg_subtracted')
                if not os.path.exists(directory):
                    os.mkdir(directory)
                header = self.calibration_data.geometry.makeHeaders()
                header += "\n# Background_File: " + self.spectrum_data.overlays[self.spectrum_data.bkg_ind].name
                data = np.dstack((x, y))[0]
                filename = os.path.join(directory, self.spectrum_data.spectrum.name + '_bkg_subtracted.xy')
                np.savetxt(filename, data, header=header)

    def load(self, filename=None):
        if filename is None:
            filename = str(QtGui.QFileDialog.getOpenFileName(self.view, caption="Load Spectrum",
                                                             directory=self.working_dir['spectrum']))
        if filename is not '':
            self.working_dir['spectrum'] = os.path.dirname(filename)
            self.view.spec_filename_lbl.setText(os.path.basename(filename))
            self.spectrum_data.load_spectrum(filename)
            self.view.spec_next_btn.setEnabled(True)
            self.view.spec_previous_btn.setEnabled(True)

    def load_previous(self):
        self.spectrum_data.load_previous()
        self.view.spec_filename_lbl.setText(os.path.basename(self.spectrum_data.spectrum_filename))

    def load_next(self):
        self.spectrum_data.load_next()
        self.view.spec_filename_lbl.setText(os.path.basename(self.spectrum_data.spectrum_filename))

    def autocreate_cb_changed(self):
        self.autocreate = self.view.spec_autocreate_cb.isChecked()

    def spec_directory_btn_click(self):
        directory = QtGui.QFileDialog.getExistingDirectory(self.view,
                                                           "Please choose the default directory for autosaved spectra.",
                                                           self.working_dir['spectrum'])
        if directory is not '':
            self.working_dir['spectrum'] = str(directory)
            self.view.spec_directory_txt.setText(directory)

    def spec_directory_txt_changed(self):
        if os.path.exists(self.view.spec_directory_txt.text()):
            self.working_dir['spectrum'] = self.view.spec_directory_txt.text()
        else:
            self.view.spec_directory_txt.setText(self.working_dir['spectrum'])

    def set_iteration_mode_number(self):
        self.spectrum_data.file_iteration_mode = 'number'

    def set_iteration_mode_time(self):
        self.spectrum_data.file_iteration_mode = 'time'

    def set_unit_tth(self):
        self.integration_unit = '2th_deg'
        self.image_changed()
        self.view.spectrum_view.spectrum_plot.setLabel('bottom', u'2θ', u'°')

        cur_line_pos = self.view.spectrum_view.pos_line.getPos()[0]
        new_line_pos = np.arcsin(cur_line_pos * 1e10 * self.calibration_data.geometry.wavelength / (4 * np.pi)) * 2
        new_line_pos = new_line_pos / np.pi * 180
        self.view.spectrum_view.set_pos_line(new_line_pos)

    def set_unit_q(self):
        self.integration_unit = "q_A^-1"
        self.image_changed()
        self.view.spectrum_view.spectrum_plot.setLabel('bottom', 'Q', 'A<sup>-1</sup>')

        cur_line_pos = self.view.spectrum_view.pos_line.getPos()[0]
        new_line_pos = 4 * np.pi * np.sin(cur_line_pos / 360 * np.pi) / self.calibration_data.geometry.wavelength / 1e10
        self.view.spectrum_view.set_pos_line(new_line_pos)

    def spectrum_left_click(self, x, y):
        self.view.spectrum_view.set_pos_line(x)
        if self.view.spec_unit_q_rb.isChecked():
            x = np.arcsin(x * 1e10 * self.calibration_data.geometry.wavelength / (4 * np.pi)) * 2
            x = x / np.pi * 180

        if self.view.cake_rb.isChecked():  # cake mode
            upper_ind = np.where(self.calibration_data.cake_tth > x)
            lower_ind = np.where(self.calibration_data.cake_tth < x)
            spacing = self.calibration_data.cake_tth[upper_ind[0][0]] - \
                      self.calibration_data.cake_tth[lower_ind[-1][-1]]
            new_pos = lower_ind[-1][-1] + \
                      (x - self.calibration_data.cake_tth[lower_ind[-1][-1]]) / spacing

            self.view.img_view.vertical_line.setValue(new_pos)
        else:  # image mode
            if self.calibration_data.is_calibrated:
                self.view.img_view.set_circle_scatter_tth(self.calibration_data.geometry._ttha, x / 180 * np.pi)