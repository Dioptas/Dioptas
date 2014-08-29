# -*- coding: utf-8 -*-
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
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <http://www.gnu.org/licenses/>.


__author__ = 'Clemens Prescher'
import os
from PyQt4 import QtGui, QtCore
import numpy as np
from PIL import Image


class IntegrationImageController(object):
    """
    The IntegrationImageController manages the Image actions in the Integration Window. It connects the file actions, as
    well as interaction with the image_view.
    """

    def __init__(self, working_dir, view, img_data, mask_data, spectrum_data,
                 calibration_data):
        self.working_dir = working_dir
        self.view = view
        self.img_data = img_data
        self.mask_data = mask_data
        self.spectrum_data = spectrum_data
        self.calibration_data = calibration_data
        self._auto_scale = True
        self.img_mode = 'Image'
        self.use_mask = False
        self.roi_active = False

        self.autoprocess_timer = QtCore.QTimer(self.view)

        self.view.show()
        self.initialize()
        self.img_data.subscribe(self.update_img)
        self.create_signals()
        self.create_mouse_behavior()

    def initialize(self):
        self.update_img(True)
        self.plot_mask()
        self.view.img_view.auto_range()

    def plot_img(self, auto_scale=None):
        """
        Plots the current image loaded in self.img_data.
        :param auto_scale:
            Determines if intensities should be auto-scaled. If value is None it will use the parameter saved in the
            Object (self._auto_scale)
        """
        if auto_scale is None:
            auto_scale = self._auto_scale

        self.view.img_view.plot_image(self.img_data.get_img_data(),
                                      False)

        if auto_scale:
            self.view.img_view.auto_range()

    def plot_cake(self, auto_scale=None):
        """
        Plots the cake saved in the calibration data
        :param auto_scale:
            Determines if the intensity should be auto-scaled. If value is None it will use the parameter saved in the
            object (self._auto_scale)
        """
        if auto_scale is None:
            auto_scale = self._auto_scale
        self.view.img_view.plot_image(self.calibration_data.cake_img)
        if auto_scale:
            self.view.img_view.auto_range()

    def plot_mask(self):
        """
        Plots the mask data.
        """
        if self.use_mask and \
                        self.img_mode == 'Image':
            self.view.img_view.plot_mask(self.mask_data.get_img())
        else:
            self.view.img_view.plot_mask(
                np.zeros(self.mask_data.get_img().shape))

    def change_mask_colormap(self):
        """
        Changes the colormap of the mask according to the transparency option selection in the GUI. Resulting Mask will
        be either transparent or solid.
        """
        if self.view.mask_transparent_cb.isChecked():
            self.view.img_view.set_color([255, 0, 0, 100])
        else:
            self.view.img_view.set_color([255, 0, 0, 255])

    def change_img_levels_mode(self):
        """
        Sets the img intensity scaling mode according to the option selection in the GUI.
        """
        self.view.img_view.img_histogram_LUT.percentageLevel = self.view.img_levels_percentage_rb.isChecked()
        self.view.img_view.img_histogram_LUT.old_hist_x_range = self.view.img_view.img_histogram_LUT.hist_x_range
        if self.view.img_levels_autoscale_rb.isChecked():
            self._auto_scale = True
        else:
            self._auto_scale = False

    def create_signals(self):
        """
        Creates all the connections of the GUI elements.
        """
        self.connect_click_function(self.view.next_img_btn, self.load_next_img)
        self.connect_click_function(self.view.prev_img_btn, self.load_previous_img)
        self.connect_click_function(self.view.load_img_btn, self.load_file)
        self.view.img_filename_txt.editingFinished.connect(self.filename_txt_changed)
        self.view.img_directory_txt.editingFinished.connect(self.directory_txt_changed)
        self.connect_click_function(self.view.img_directory_btn, self.img_directory_btn_click)

        self.connect_click_function(self.view.img_browse_by_name_rb, self.set_iteration_mode_number)
        self.connect_click_function(self.view.img_browse_by_time_rb, self.set_iteration_mode_time)
        self.connect_click_function(self.view.mask_transparent_cb, self.change_mask_colormap)
        self.connect_click_function(self.view.img_levels_autoscale_rb, self.change_img_levels_mode)
        self.connect_click_function(self.view.img_levels_absolute_rb, self.change_img_levels_mode)
        self.connect_click_function(self.view.img_levels_percentage_rb, self.change_img_levels_mode)

        self.connect_click_function(self.view.img_roi_btn, self.change_roi_mode)
        self.connect_click_function(self.view.img_mask_btn, self.change_mask_mode)
        self.connect_click_function(self.view.img_mode_btn, self.change_view_mode)
        self.connect_click_function(self.view.img_autoscale_btn, self.view.img_view.auto_range)

        self.connect_click_function(self.view.qa_img_save_img_btn, self.save_img)

        self.connect_click_function(self.view.img_load_calibration_btn, self.load_calibration)
        self.create_auto_process_signal()

    def connect_click_function(self, emitter, function):
        """
        Small helper function for the button-click connection.
        """
        self.view.connect(emitter, QtCore.SIGNAL('clicked()'), function)

    def create_mouse_behavior(self):
        """
        Creates the signal connections of mouse interactions
        """
        self.view.img_view.mouse_left_clicked.connect(self.img_mouse_click)
        self.view.img_view.mouse_moved.connect(self.show_img_mouse_position)

    def load_file(self, filenames=None):
        if filenames is None:
            filenames = list(QtGui.QFileDialog.getOpenFileNames(
                self.view, "Load image data file(s)",
                self.working_dir['image']))

        else:
            if isinstance(filenames, str):
                filenames = [filenames]

        if filenames is not None and len(filenames) is not 0:
            self.working_dir['image'] = os.path.dirname(str(filenames[0]))
            if len(filenames) == 1:
                self.img_data.load(str(filenames[0]))
            else:
                if self.view.spec_autocreate_cb.isChecked():
                    working_directory = self.working_dir['spectrum']
                else:
                    working_directory = str(QtGui.QFileDialog.getExistingDirectory(self.view,
                                                                                   "Please choose the output directory for the integrated spectra.",
                                                                                   self.working_dir['spectrum']))
                if working_directory is '':
                    return

                progress_dialog = QtGui.QProgressDialog("Integrating multiple files.", "Abort Integration", 0,
                                                        len(filenames),
                                                        self.view)
                progress_dialog.setWindowModality(QtCore.Qt.WindowModal)
                progress_dialog.setWindowFlags(QtCore.Qt.FramelessWindowHint)
                progress_dialog.move(self.view.spectrum_view.pg_layout.x() + self.view.spectrum_view.pg_layout.size().width() / 2.0 - \
                                     progress_dialog.size().width() / 2.0,
                                     self.view.spectrum_view.pg_layout.y() + self.view.spectrum_view.pg_layout.size().height() / 2.0 -
                                     progress_dialog.size().height() / 2.0)
                progress_dialog.show()
                for ind in range(len(filenames)):
                    filename = str(filenames[ind])
                    base_filename = os.path.basename(filename)
                    progress_dialog.setValue(ind)
                    progress_dialog.setLabelText("Integrating: " + base_filename)
                    QtGui.QApplication.processEvents()
                    self.img_data.turn_off_notification()
                    self.img_data.load(filename)
                    x, y = self.integrate_spectrum()
                    file_endings = self.get_spectrum_file_endings()
                    for file_ending in file_endings:
                        filename = os.path.join(working_directory, os.path.splitext(base_filename)[0] + file_ending)
                        print filename
                        self.spectrum_data.set_spectrum(x, y, filename, unit=self.get_integration_unit())
                        if file_ending == '.xy':
                            self.spectrum_data.save_spectrum(filename, header=self.create_header())
                        else:
                            self.spectrum_data.save_spectrum(filename)
                    QtGui.QApplication.processEvents()
                    QtGui.QApplication.processEvents()
                    if progress_dialog.wasCanceled():
                        break
                self.img_data.turn_on_notification()
                self.img_data.notify()
                progress_dialog.close()

    def create_header(self):
        header = self.calibration_data.geometry.makeHeaders(polarization_factor=self.calibration_data.polarization_factor)
        header = header.replace('\r\n', '\n')
        header += '\n#\n# ' + self.spectrum_data.unit + '\t I'
        return header

    def get_spectrum_file_endings(self):
        res = []
        if self.view.spectrum_header_xy_cb.isChecked():
            res.append('.xy')
        if self.view.spectrum_header_chi_cb.isChecked():
            res.append('.chi')
        if self.view.spectrum_header_dat_cb.isChecked():
            res.append('.dat')
        return res

    def get_integration_unit(self):
        if self.view.spec_tth_btn.isChecked():
            return '2th_deg'
        elif self.view.spec_q_btn.isChecked():
            return 'q_A^-1'
        elif self.view.spec_d_btn.isChecked():
            return 'd_A'

    def integrate_spectrum(self):
        if self.view.img_mask_btn.isChecked():
            self.mask_data.set_dimension(self.img_data.img_data.shape)
            mask = self.mask_data.get_mask()
        else:
            mask = None

        if self.view.img_roi_btn.isChecked():
            roi_mask = self.view.img_view.roi.getRoiMask(self.img_data.img_data.shape)
        else:
            roi_mask = None

        if roi_mask is None and mask is None:
            mask = None
        elif roi_mask is None and mask is not None:
            mask = mask
        elif roi_mask is not None and mask is None:
            mask = roi_mask
        elif roi_mask is not None and mask is not None:
            mask = np.logical_or(mask, roi_mask)

        if self.view.spec_tth_btn.isChecked():
            integration_unit = '2th_deg'
        elif self.view.spec_q_btn.isChecked():
            integration_unit = 'q_A^-1'
        elif self.view.spec_d_btn.isChecked():
            integration_unit = 'd_A'
        else:
            # in case something weird happened
            print('No correct integration unit selected')
            return

        return self.calibration_data.integrate_1d(mask=mask, unit=integration_unit)

    def change_mask_mode(self):
        self.use_mask = not self.use_mask
        self.plot_mask()
        auto_scale_save = self._auto_scale
        self._auto_scale = False
        self.img_data.notify()
        self._auto_scale = auto_scale_save

    def load_next_img(self):
        self.img_data.load_next_file()

    def load_previous_img(self):
        self.img_data.load_previous_file()

    def filename_txt_changed(self):
        current_filename = os.path.basename(self.img_data.filename)
        current_directory = str(self.view.img_directory_txt.text())
        new_filename = str(self.view.img_filename_txt.text())
        if os.path.exists(os.path.join(current_directory, new_filename)):
            try:
                self.load_file(os.path.join(current_directory, new_filename))
            except TypeError:
                self.view.img_filename_txt.setText(current_filename)
        else:
            self.view.img_filename_txt.setText(current_filename)

    def directory_txt_changed(self):
        new_directory = str(self.view.img_directory_txt.text())
        if os.path.exists(new_directory) and new_directory != self.working_dir['image']:
            if self.view.autoprocess_cb.isChecked():
                self._files_now = dict([(f, None) for f in os.listdir(self.working_dir['image'])])
            self.working_dir['image'] = os.path.abspath(new_directory)
            old_filename = str(self.view.img_filename_txt.text())
            self.view.img_filename_txt.setText(old_filename + '*')
            #update for autoprocessing of images
        else:
            self.view.img_directory_txt.setText(self.working_dir['image'])

    def img_directory_btn_click(self):
        directory = str(QtGui.QFileDialog.getExistingDirectory(
            self.view,
            "Please choose the image working directory.",
            self.working_dir['image']))
        if directory is not '':
            if self.view.autoprocess_cb.isChecked():
                self._files_now = dict([(f, None) for f in os.listdir(self.working_dir['image'])])
            self.working_dir['image'] = directory
            self.view.img_directory_txt.setText(directory)

    def update_img(self, reset_img_levels=None):
        self.view.img_filename_txt.setText(os.path.basename(self.img_data.filename))
        self.view.img_directory_txt.setText(os.path.dirname(self.img_data.filename))
        if self.img_mode == 'Cake' and \
                self.calibration_data.is_calibrated:
            if self.use_mask:
                mask = self.mask_data.get_mask()
            else:
                mask = np.zeros(self.img_data.img_data.shape)

            if self.roi_active:
                roi_mask = np.ones(self.img_data.img_data.shape)
                x1, x2, y1, y2 = self.view.img_view.roi.getIndexLimits(self.img_data.img_data.shape)
                roi_mask[x1:x2, y1:y2] = 0
            else:
                roi_mask = np.zeros(self.img_data.img_data.shape)

            if self.use_mask or self.roi_active:
                mask = np.logical_or(mask, roi_mask)
            else:
                mask = None

            self.calibration_data.integrate_2d(mask)
            self.plot_cake()
            self.view.img_view.plot_mask(
                np.zeros(self.mask_data.get_img().shape))
            self.view.img_view.activate_vertical_line()
            self.view.img_view.img_view_box.setAspectLocked(False)
        elif self.img_mode == 'Image':
            self.plot_mask()
            self.plot_img(reset_img_levels)
            self.view.img_view.deactivate_vertical_line()
            self.view.img_view.img_view_box.setAspectLocked(True)

    def change_roi_mode(self):
        self.roi_active = not self.roi_active
        if self.img_mode == 'Image':
            if self.roi_active:
                self.view.img_view.activate_roi()
            else:
                self.view.img_view.deactivate_roi()

        auto_scale_save = self._auto_scale
        self._auto_scale = False
        self.img_data.notify()
        self._auto_scale = auto_scale_save

    def change_view_mode(self):
        self.img_mode = self.view.img_mode_btn.text()
        if not self.calibration_data.is_calibrated:
            return
        else:
            self.update_img()
            if self.img_mode == 'Cake':
                self.view.img_view.deactivate_circle_scatter()
                self.view.img_view.deactivate_roi()
                self._update_cake_line_pos()
                self.view.img_mode_btn.setText('Image')
            elif self.img_mode == 'Image':
                self.view.img_view.activate_circle_scatter()
                if self.roi_active:
                    self.view.img_view.activate_roi()
                self._update_image_scatter_pos()
                self.view.img_mode_btn.setText('Cake')

    def _update_cake_line_pos(self):
        cur_tth = self.get_current_spectrum_tth()
        if cur_tth < np.min(self.calibration_data.cake_tth):
            new_pos = np.min(self.calibration_data.cake_tth)
        else:
            upper_ind = np.where(self.calibration_data.cake_tth > cur_tth)
            lower_ind = np.where(self.calibration_data.cake_tth < cur_tth)

            spacing = self.calibration_data.cake_tth[upper_ind[0][0]] - \
                      self.calibration_data.cake_tth[lower_ind[-1][-1]]
            new_pos = lower_ind[-1][-1] + \
                      (cur_tth -
                       self.calibration_data.cake_tth[lower_ind[-1][-1]]) / spacing
        self.view.img_view.vertical_line.setValue(new_pos)

    def _update_image_scatter_pos(self):
        cur_tth = self.get_current_spectrum_tth()
        self.view.img_view.set_circle_scatter_tth(
            self.calibration_data.geometry._ttha, cur_tth / 180 * np.pi)

    def get_current_spectrum_tth(self):
        cur_pos = self.view.spectrum_view.pos_line.getPos()[0]
        if self.view.spec_q_btn.isChecked():
            cur_tth = self.convert_x_value(cur_pos, 'q_A^-1', '2th_deg')
        elif self.view.spec_tth_btn.isChecked():
            cur_tth = cur_pos
        elif self.view.spec_d_btn.isChecked():
            cur_tth = self.convert_x_value(cur_pos, 'd_A', '2th_deg')
        else:
            cur_tth = None
        return cur_tth

    def show_img_mouse_position(self, x, y):
        img_shape = self.img_data.get_img_data().shape
        if x > 0 and y > 0 and x < img_shape[0] and y < img_shape[1]:
            x_pos_string = 'X:  %4d' % x
            y_pos_string = 'Y:  %4d' % y
            self.view.mouse_x_lbl.setText(x_pos_string)
            self.view.mouse_y_lbl.setText(y_pos_string)

            int_string = 'I:   %5d' % self.view.img_view.img_data[
                np.floor(y), np.floor(x)]
            self.view.mouse_int_lbl.setText(int_string)
            if self.calibration_data.is_calibrated:
                x_temp = x
                x = np.array([y])
                y = np.array([x_temp])
                if self.img_mode == 'Cake':
                    tth = self.calibration_data.cake_tth[np.round(y[0])]
                    azi = self.calibration_data.cake_azi[np.round(x[0])]
                    q_value = self.convert_x_value(tth, '2th_deg', 'q_A^-1')

                else:
                    tth = self.calibration_data.geometry.tth(np.array([x]), np.array([y]))[0]
                    tth = tth / np.pi * 180.0
                    q_value = self.convert_x_value(tth, '2th_deg', 'q_A^-1')
                    azi = self.calibration_data.geometry.chi(
                        x, y)[0] / np.pi * 180

                azi = azi + 360 if azi < 0 else azi
                d = self.convert_x_value(tth, '2th_deg', 'd_A')
                tth_str = u"2θ:%9.3f  " % tth
                self.view.mouse_tth_lbl.setText(unicode(tth_str))
                self.view.mouse_d_lbl.setText('d:%9.3f  ' % d)
                self.view.mouse_q_lbl.setText('Q:%9.3f  ' % q_value)
                self.view.mouse_azi_lbl.setText('X:%9.3f  ' % azi)
            else:
                self.view.mouse_tth_lbl.setText(u'2θ: -')
                self.view.mouse_d_lbl.setText('d: -')
                self.view.mouse_q_lbl.setText('Q: -')
                self.view.mouse_azi_lbl.setText('X: -')

    def img_mouse_click(self, x, y):
        #update click position
        try:
            x_pos_string = 'X:  %4d' % y
            y_pos_string = 'Y:  %4d' % x
            int_string = 'I:   %5d' % self.view.img_view.img_data[
                np.floor(x), np.floor(y)]
            self.view.click_x_lbl.setText(x_pos_string)
            self.view.click_y_lbl.setText(y_pos_string)
            self.view.click_int_lbl.setText(int_string)
        except IndexError:
            self.view.click_int_lbl.setText('I: ')

        if self.calibration_data.is_calibrated:
            if self.img_mode == 'Cake':  # cake mode
                y = np.array([y])
                tth = self.calibration_data.cake_tth[np.round(y[0])] / 180 * np.pi
            elif self.img_mode == 'Image':  # image mode
                x = np.array([x])
                y = np.array([y])
                tth = self.calibration_data.geometry.tth(np.array([x]), np.array([y]))[0]
                self.view.img_view.set_circle_scatter_tth(
                    self.calibration_data.geometry._ttha, tth)
            else:  # in the cas of whatever
                tth = 0

            # calculate right unit
            if self.view.spec_q_btn.isChecked():
                pos = 4 * np.pi * \
                      np.sin(tth / 2) / \
                      self.calibration_data.geometry.get_wavelength() / 1e10
            elif self.view.spec_tth_btn.isChecked():
                pos = tth / np.pi * 180
            elif self.view.spec_d_btn.isChecked():
                pos = self.calibration_data.geometry.get_wavelength() / \
                      (2 * np.sin(tth / 2)) * 1e10
            else:
                pos = 0
            self.view.spectrum_view.set_pos_line(pos)
        self.view.click_tth_lbl.setText(self.view.mouse_tth_lbl.text())
        self.view.click_d_lbl.setText(self.view.mouse_d_lbl.text())
        self.view.click_q_lbl.setText(self.view.mouse_q_lbl.text())
        self.view.click_azi_lbl.setText(self.view.mouse_azi_lbl.text())

    def set_iteration_mode_number(self):
        self.img_data.set_file_iteration_mode('number')

    def set_iteration_mode_time(self):
        self.img_data.set_file_iteration_mode('time')

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

    def load_calibration(self, filename=None):
        if filename is None:
            filename = str(QtGui.QFileDialog.getOpenFileName(
                self.view, "Load calibration...",
                self.working_dir[
                    'calibration'],
                '*.poni'))
        if filename is not '':
            self.working_dir['calibration'] = os.path.dirname(filename)
            self.calibration_data.load(filename)
            self.view.calibration_lbl.setText(
                self.calibration_data.calibration_name)
            self.img_data.notify()

    def create_auto_process_signal(self):
        self.view.autoprocess_cb.clicked.connect(self.auto_process_cb_click)
        self.autoprocess_timer.setInterval(50)
        self.view.connect(self.autoprocess_timer,
                          QtCore.SIGNAL('timeout()'),
                          self.check_files)

    def auto_process_cb_click(self):
        if self.view.autoprocess_cb.isChecked():
            self._files_before = dict(
                [(f, None) for f in os.listdir(self.working_dir['image'])])
            self.autoprocess_timer.start()
        else:
            self.autoprocess_timer.stop()

    def check_files(self):
        self._files_now = dict(
            [(f, None) for f in os.listdir(self.working_dir['image'])])
        self._files_added = [
            f for f in self._files_now if not f in self._files_before]
        self._files_removed = [
            f for f in self._files_before if not f in self._files_now]
        if len(self._files_added) > 0:
            new_file_str = self._files_added[-1]
            path = os.path.join(self.working_dir['image'], new_file_str)
            acceptable_file_endings = ['.img', '.sfrm', '.dm3', '.edf', '.xml',
                                       '.cbf', '.kccd', '.msk', '.spr', '.tif',
                                       '.mccd', '.mar3450', '.pnm']
            read_file = False
            for ending in acceptable_file_endings:
                if path.endswith(ending):
                    read_file = True
                    break
            file_info = os.stat(path)
            if file_info.st_size > 100:
                if read_file:
                    self.load_file(path)
                self._files_before = self._files_now

    def save_img(self, filename=None):
        if filename is None:
            filename = str(QtGui.QFileDialog.getSaveFileName(self.view, "Save Image.",
                                                             self.working_dir['image'],
                                                             ('Image (*.png);;Data (*.tiff)')))
        if filename is not '':
            if filename.endswith('.png'):
                if self.img_mode == 'Cake':
                    self.view.img_view.deactivate_vertical_line()
                elif self.img_mode == 'Image':
                    self.view.img_view.deactivate_circle_scatter()
                    self.view.img_view.deactivate_roi()

                QtGui.QApplication.processEvents()
                self.view.img_view.save_img(filename)

                if self.img_mode == 'Cake':
                    self.view.img_view.activate_vertical_line()
                elif self.img_mode == 'Image':
                    self.view.img_view.activate_circle_scatter()
                    if self.roi_active:
                        self.view.img_view.activate_roi()
            elif filename.endswith('.tiff'):
                if self.img_mode == 'Image':
                    im_array = np.int32(self.img_data.img_data)
                elif self.img_mode == 'Cake':
                    im_array = np.int32(self.calibration_data.cake_img)
                im_array = np.flipud(im_array)
                im = Image.fromarray(im_array)
                im.save(filename)

