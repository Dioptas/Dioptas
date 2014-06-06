# -*- coding: utf8 -*-
# Py2DeX - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2014  Clemens Prescher (clemens.prescher@gmail.com)
# GSECARS, University of Chicago
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
from Data.HelperModule import SignalFrequencyLimiter


class IntegrationSpectrumController(object):
    def __init__(self, working_dir, view, img_data,
                 mask_data, calibration_data, spectrum_data):
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
        self.view.spectrum_view.add_left_click_observer(
            self.spectrum_left_click)

        self.mouse_move_timer = SignalFrequencyLimiter(self.view.spectrum_view.add_mouse_move_observer,
                                                       self.show_spectrum_mouse_position)

    def set_status(self):
        self.autocreate = False
        self.unit = pyFAI.units.TTH_DEG

    def create_signals(self):
        self.connect_click_function(
            self.view.spec_autocreate_cb, self.autocreate_cb_changed)
        self.connect_click_function(self.view.spec_load_btn, self.load)
        self.connect_click_function(
            self.view.spec_previous_btn, self.load_previous)
        self.connect_click_function(self.view.spec_next_btn, self.load_next)
        self.connect_click_function(
            self.view.spec_directory_btn, self.spec_directory_btn_click)
        self.connect_click_function(
            self.view.spec_browse_by_name_rb, self.set_iteration_mode_number)
        self.connect_click_function(
            self.view.spec_browse_by_time_rb, self.set_iteration_mode_time)

        self.connect_click_function(self.view.spec_tth_btn, self.set_unit_tth)
        self.connect_click_function(self.view.spec_q_btn, self.set_unit_q)
        self.connect_click_function(self.view.spec_d_btn, self.set_unit_d)

        self.view.connect(self.view.spec_directory_txt,
                          QtCore.SIGNAL('editingFinished()'),
                          self.spec_directory_txt_changed)

    def connect_click_function(self, emitter, function):
        self.view.connect(emitter, QtCore.SIGNAL('clicked()'), function)

    def image_changed(self):
        if self.calibration_data.is_calibrated:
            if self.autocreate:
                filename = self.img_data.filename
                if filename is not '':
                    filename = os.path.join(
                        self.working_dir['spectrum'],
                        os.path.basename(
                            self.img_data.filename).split('.')[:-1][0] + '.xy')

                self.view.spec_next_btn.setEnabled(True)
                self.view.spec_previous_btn.setEnabled(True)
                self.view.spec_filename_lbl.setText(os.path.basename(filename))
                self.view.spec_directory_txt.setText(os.path.dirname(filename))
            else:
                self.view.spec_next_btn.setEnabled(False)
                self.view.spec_previous_btn.setEnabled(False)
                self.view.spec_filename_lbl.setText(
                    'No File saved or selected')
                filename = None

            if self.view.mask_use_cb.isChecked():
                self.mask_data.set_dimension(self.img_data.img_data.shape)
                mask = self.mask_data.get_mask()
            else:
                mask = None

            tth, I = self.calibration_data.integrate_1d(
                filename=filename, mask=mask, unit=self.integration_unit)
            if filename is not None:
                spectrum_name = filename
            else:
                spectrum_name = self.img_data.filename
            self.spectrum_data.set_spectrum(tth, I, spectrum_name)

    def plot_spectra(self):
        x, y = self.spectrum_data.spectrum.data
        self.view.spectrum_view.plot_data(
            x, y, self.spectrum_data.spectrum.name)

        if self.first_plot:
            self.view.spectrum_view.spectrum_plot.enableAutoRange()
            self.first_plot = False

        # save the background subtracted file:
        if self.spectrum_data.bkg_ind is not -1:
            # create background subtracted spectrum
            if self.autocreate:
                directory = os.path.join(
                    self.working_dir['spectrum'], 'bkg_subtracted')
                if not os.path.exists(directory):
                    os.mkdir(directory)
                header = self.calibration_data.geometry.makeHeaders()
                header += "\n# Background_File: " + \
                          self.spectrum_data.overlays[
                              self.spectrum_data.bkg_ind].name
                data = np.dstack((x, y))[0]
                filename = os.path.join(
                    directory,
                    self.spectrum_data.spectrum.name + '_bkg_subtracted.xy')
                np.savetxt(filename, data, header=header)
            # update the bkg_name
            self.view.bkg_name_lbl.setText('Bkg: ' + self.spectrum_data.overlays[self.spectrum_data.bkg_ind].name)
        else:
            self.view.bkg_name_lbl.setText('')


    def load(self, filename=None):
        if filename is None:
            filename = str(QtGui.QFileDialog.getOpenFileName(
                self.view, caption="Load Spectrum",
                directory=self.working_dir['spectrum']))
        if filename is not '':
            self.working_dir['spectrum'] = os.path.dirname(filename)
            self.view.spec_filename_lbl.setText(os.path.basename(filename))
            self.spectrum_data.load_spectrum(filename)
            self.view.spec_next_btn.setEnabled(True)
            self.view.spec_previous_btn.setEnabled(True)

    def load_previous(self):
        self.spectrum_data.load_previous()
        self.view.spec_filename_lbl.setText(
            os.path.basename(self.spectrum_data.spectrum_filename))

    def load_next(self):
        self.spectrum_data.load_next()
        self.view.spec_filename_lbl.setText(
            os.path.basename(self.spectrum_data.spectrum_filename))

    def autocreate_cb_changed(self):
        self.autocreate = self.view.spec_autocreate_cb.isChecked()

    def spec_directory_btn_click(self):
        directory = QtGui.QFileDialog.getExistingDirectory(
            self.view,
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
        previous_unit = self.integration_unit
        self.integration_unit = '2th_deg'
        self.image_changed()
        self.view.spectrum_view.spectrum_plot.setLabel('bottom', u'2θ', u'°')
        self.update_line_position(previous_unit, self.integration_unit)
        self.view.spec_q_btn.setChecked(False)
        self.view.spec_d_btn.setChecked(False)

    def set_unit_q(self):
        previous_unit = self.integration_unit
        self.integration_unit = "q_A^-1"
        self.image_changed()
        self.view.spectrum_view.spectrum_plot.setLabel(
            'bottom', 'Q', 'A<sup>-1</sup>')

        self.update_line_position(previous_unit, self.integration_unit)

        self.view.spec_tth_btn.setChecked(False)
        self.view.spec_d_btn.setChecked(False)

    def set_unit_d(self):
        previous_unit = self.integration_unit
        self.integration_unit = 'd_A'
        self.image_changed()
        self.view.spectrum_view.spectrum_plot.setLabel(
            'bottom', 'd', 'A'
        )
        self.update_line_position(previous_unit, self.integration_unit)

        self.view.spec_tth_btn.setChecked(False)
        self.view.spec_q_btn.setChecked(False)

    def update_line_position(self, previous_unit, new_unit):
        cur_line_pos = self.view.spectrum_view.pos_line.getPos()[0]
        if cur_line_pos == 0 and new_unit == 'd_A':
            cur_line_pos = 0.01
        try:
            new_line_pos = self.convert_x_value(cur_line_pos, previous_unit, new_unit)
        except RuntimeWarning:  # no calibration available
            new_line_pos = cur_line_pos
        self.view.spectrum_view.set_pos_line(new_line_pos)

    def convert_x_value(self, value, previous_unit, new_unit):
        wavelength = self.calibration_data.geometry.wavelength
        if previous_unit == '2th_deg':
            tth = value
        elif previous_unit == 'q_A^-1':
            tth = np.arcsin(
                value * 1e10 * wavelength / (4 * np.pi)) * 360 / np.pi
        elif previous_unit == 'd_A':
            tth = 2 * np.arcsin(wavelength / (2 * value * 1e-10)) * 180 / np.pi
        else:
            tth = 0

        if new_unit == '2th_deg':
            res = tth
        elif new_unit == 'q_A^-1':
            res = 4 * np.pi * \
                  np.sin(tth / 360 * np.pi) / \
                  wavelength / 1e10
        elif new_unit == 'd_A':
            res = wavelength / (2 * np.sin(tth / 360 * np.pi)) * 1e10
        else:
            res = 0
        return res

    def spectrum_left_click(self, x, y):
        self.view.spectrum_view.set_pos_line(x)
        if self.calibration_data.is_calibrated:
            if self.integration_unit == 'q_A^-1':
                x = self.convert_x_value(x, 'q_A^-1', '2th_deg')
            elif self.integration_unit == 'd_A':
                x = self.convert_x_value(x, 'd_A', '2th_deg')

            if self.view.cake_rb.isChecked():  # cake mode
                upper_ind = np.where(self.calibration_data.cake_tth > x)
                lower_ind = np.where(self.calibration_data.cake_tth < x)
                spacing = self.calibration_data.cake_tth[upper_ind[0][0]] - \
                          self.calibration_data.cake_tth[lower_ind[-1][-1]]
                new_pos = lower_ind[-1][-1] + \
                          (x -
                           self.calibration_data.cake_tth[lower_ind[-1][-1]]) / spacing

                self.view.img_view.vertical_line.setValue(new_pos)
            else:  # image mode
                if self.calibration_data.is_calibrated:
                    self.view.img_view.set_circle_scatter_tth(
                        self.calibration_data.geometry._ttha, x / 180 * np.pi)

        self.view.click_tth_lbl.setText(self.view.mouse_tth_lbl.text())
        self.view.click_d_lbl.setText(self.view.mouse_d_lbl.text())
        self.view.click_q_lbl.setText(self.view.mouse_q_lbl.text())
        self.view.click_azi_lbl.setText(self.view.mouse_azi_lbl.text())

    def show_spectrum_mouse_position(self, x, y):
        if self.calibration_data.is_calibrated:
            if self.integration_unit == '2th_deg':
                tth = x
                q_value = self.convert_x_value(tth, '2th_deg', 'q_A^-1')
                d_value = self.convert_x_value(tth, '2th_deg', 'd_A')
            elif self.integration_unit == 'q_A^-1':
                q_value = x
                tth = self.convert_x_value(q_value, 'q_A^-1', '2th_deg')
                d_value = self.convert_x_value(q_value, 'q_A^-1', 'd_A')
            elif self.integration_unit == 'd_A':
                d_value = x
                q_value = self.convert_x_value(d_value, 'd_A', 'q_A^-1')
                tth = self.convert_x_value(d_value, 'd_A', '2th_deg')

            tth_str = u'2θ:%9.2f  ' % tth
            d_str = u'd:%9.2f  ' % d_value
            q_str = u'Q:%9.2f  ' % q_value
        else:
            tth_str = u'2θ: -'
            d_str = u'd: -'
            q_str = u'Q: -'
            if self.integration_unit == '2th_deg':
                tth_str = u'2θ:%9.2f  ' % x
            elif self.integration_unit == 'q_A^-1':
                q_str = u'Q:%9.2f  ' % x
            elif self.integration_unit == 'd_A':
                d_str = u'd:%9.2f  ' % x
        self.view.mouse_tth_lbl.setText(tth_str)
        self.view.mouse_d_lbl.setText(d_str)
        self.view.mouse_q_lbl.setText(q_str)
        self.view.mouse_azi_lbl.setText(u'X: -')
