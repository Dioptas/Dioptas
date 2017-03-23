# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2015  Clemens Prescher (clemens.prescher@gmail.com)
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
import time

import numpy as np
from PIL import Image
from qtpy import QtWidgets, QtCore

from ...widgets.UtilityWidgets import open_file_dialog, open_files_dialog, save_file_dialog
from ...model.util.ImgCorrection import CbnCorrection, ObliqueAngleDetectorAbsorptionCorrection
# imports for type hinting in PyCharm -- DO NOT DELETE
from ...widgets.integration import IntegrationWidget
from ...model.DioptasModel import DioptasModel
from ...model.util.HelperModule import get_partial_index, get_partial_value

from .EpicsController import EpicsController


class ImageController(object):
    """
    The IntegrationImageController manages the Image actions in the Integration Window. It connects the file actions, as
    well as interaction with the image_view.
    """

    def __init__(self, working_dir, widget, dioptas_model):
        """
        :param working_dir: dictionary of working directories
        :param widget: Reference to IntegrationView
        :param dioptas_model: Reference to DioptasModel object

        :type widget: IntegrationWidget
        :type dioptas_model: DioptasModel
        """
        self.working_dir = working_dir
        self.widget = widget
        self.model = dioptas_model

        self.epics_controller = EpicsController(self.widget, self.model)

        self.img_mode = 'Image'
        self.img_docked = True
        self.roi_active = False

        self.clicked_tth = None
        self.clicked_azi = None

        self.initialize()
        self.create_signals()
        self.create_mouse_behavior()

    def initialize(self):
        self.update_img(True)
        self.plot_img()
        self.plot_mask()
        self.widget.img_widget.auto_range()

    def plot_img(self, auto_scale=None):
        """
        Plots the current image loaded in self.img_data.
        :param auto_scale:
            Determines if intensities shouldk be auto-scaled. If value is None it will use the parameter saved in the
            Object (self._auto_scale)
        """
        if auto_scale is None:
            auto_scale = self.widget.img_autoscale_btn.isChecked()

        self.widget.img_widget.plot_image(self.model.img_model.raw_img_data, False)

        if auto_scale:
            self.widget.img_widget.auto_range()

    def plot_cake(self, auto_scale=None):
        """
        Plots the cake saved in the calibration data
        :param auto_scale:
            Determines if the intensity should be auto-scaled. If value is None it will use the parameter saved in the
            object (self._auto_scale)
        """
        if auto_scale is None:
            auto_scale = self.widget.img_autoscale_btn.isChecked()

        self.widget.img_widget.plot_image(self.model.cake_data)
        if auto_scale:
            self.widget.img_widget.auto_range()

    def plot_mask(self):
        """
        Plots the mask data.
        """
        if self.model.use_mask and self.img_mode == 'Image':
            self.widget.img_widget.plot_mask(self.model.mask_model.get_img())
        else:
            self.widget.img_widget.plot_mask(np.zeros(self.model.mask_model.get_img().shape))

    def update_mask_transparency(self):
        """
        Changes the colormap of the mask according to the transparency option selection in the GUI. Resulting Mask will
        be either transparent or solid.
        """
        self.model.transparent_mask = self.widget.mask_transparent_cb.isChecked()
        if self.model.transparent_mask:
            self.widget.img_widget.set_color([255, 0, 0, 100])
        else:
            self.widget.img_widget.set_color([255, 0, 0, 255])

    def create_signals(self):
        self.model.configuration_selected.connect(self.update_gui)
        self.model.img_changed.connect(self.update_img)

        self.model.img_changed.connect(self.plot_img)
        self.model.img_changed.connect(self.plot_mask)

        """
        Creates all the connections of the GUI elements.
        """
        self.connect_click_function(self.widget.next_img_btn, self.load_next_img)
        self.connect_click_function(self.widget.prev_img_btn, self.load_previous_img)
        self.connect_click_function(self.widget.load_img_btn, self.load_file)
        self.widget.img_filename_txt.editingFinished.connect(self.filename_txt_changed)
        self.widget.img_directory_txt.editingFinished.connect(self.directory_txt_changed)
        self.connect_click_function(self.widget.img_directory_btn, self.img_directory_btn_click)

        self.connect_click_function(self.widget.file_info_btn, self.show_file_info)

        self.connect_click_function(self.widget.img_browse_by_name_rb, self.set_iteration_mode_number)
        self.connect_click_function(self.widget.img_browse_by_time_rb, self.set_iteration_mode_time)
        self.connect_click_function(self.widget.mask_transparent_cb, self.update_mask_transparency)

        self.connect_click_function(self.widget.img_roi_btn, self.change_roi_mode)
        self.connect_click_function(self.widget.img_mask_btn, self.change_mask_mode)
        self.connect_click_function(self.widget.img_mode_btn, self.change_view_mode)
        self.connect_click_function(self.widget.img_autoscale_btn, self.img_autoscale_btn_clicked)
        self.connect_click_function(self.widget.img_dock_btn, self.img_dock_btn_clicked)

        self.connect_click_function(self.widget.qa_save_img_btn, self.save_img)
        self.connect_click_function(self.widget.load_calibration_btn, self.load_calibration)
        self.connect_click_function(self.widget.set_wavelnegth_btn, self.set_wavelength)

        self.connect_click_function(self.widget.cbn_groupbox, self.cbn_groupbox_changed)
        self.widget.cbn_diamond_thickness_txt.editingFinished.connect(self.cbn_groupbox_changed)
        self.widget.cbn_seat_thickness_txt.editingFinished.connect(self.cbn_groupbox_changed)
        self.widget.cbn_inner_seat_radius_txt.editingFinished.connect(self.cbn_groupbox_changed)
        self.widget.cbn_outer_seat_radius_txt.editingFinished.connect(self.cbn_groupbox_changed)
        self.widget.cbn_cell_tilt_txt.editingFinished.connect(self.cbn_groupbox_changed)
        self.widget.cbn_tilt_rotation_txt.editingFinished.connect(self.cbn_groupbox_changed)
        self.widget.cbn_center_offset_txt.editingFinished.connect(self.cbn_groupbox_changed)
        self.widget.cbn_center_offset_angle_txt.editingFinished.connect(self.cbn_groupbox_changed)
        self.widget.cbn_anvil_al_txt.editingFinished.connect(self.cbn_groupbox_changed)
        self.widget.cbn_seat_al_txt.editingFinished.connect(self.cbn_groupbox_changed)
        self.connect_click_function(self.widget.cbn_plot_correction_btn, self.cbn_plot_correction_btn_clicked)

        self.connect_click_function(self.widget.oiadac_groupbox, self.oiadac_groupbox_changed)
        self.widget.oiadac_thickness_txt.editingFinished.connect(self.oiadac_groupbox_changed)
        self.widget.oiadac_abs_length_txt.editingFinished.connect(self.oiadac_groupbox_changed)
        self.connect_click_function(self.widget.oiadac_plot_btn, self.oiadac_plot_btn_clicked)

        # self.create_auto_process_signal()
        self.widget.autoprocess_cb.toggled.connect(self.auto_process_cb_click)

    def connect_click_function(self, emitter, function):
        """
        Small helper function for the button-click connection.
        """
        emitter.clicked.connect(function)

    def create_mouse_behavior(self):
        """
        Creates the signal connections of mouse interactions
        """
        self.widget.img_widget.mouse_left_clicked.connect(self.img_mouse_click)
        self.widget.img_widget.mouse_moved.connect(self.show_img_mouse_position)

    def load_file(self, *args, **kwargs):
        filename = kwargs.get('filename', None)
        if filename is None:
            filenames = open_files_dialog(self.widget, "Load image data file(s)",
                                          self.working_dir['image'])
        else:
            filenames = [filename]

        if filenames is not None and len(filenames) is not 0:
            self.working_dir['image'] = os.path.dirname(str(filenames[0]))
            if len(filenames) == 1:
                self.model.img_model.load(str(filenames[0]))
            else:
                if self.widget.img_batch_mode_add_rb.isChecked():
                    self.model.img_model.blockSignals(True)
                    self.model.img_model.load(str(filenames[0]))
                    for ind in range(1, len(filenames)):
                        self.model.img_model.add(filenames[ind])
                    self.model.img_model.blockSignals(False)
                    self.model.img_model.img_changed.emit()
                elif self.widget.img_batch_mode_integrate_rb.isChecked():
                    self._load_multiple_files(filenames)
            self._check_absorption_correction_shape()

    def _load_multiple_files(self, filenames):
        if not self.model.calibration_model.is_calibrated:
            self.widget.show_error_msg("Can not integrate multiple images without calibration.")
            return

        working_directory = self._get_spectrum_working_directory()
        if working_directory is '':
            return  # abort file processing if no directory was selected

        progress_dialog = self.widget.get_progress_dialog("Integrating multiple files.", "Abort Integration",
                                                          len(filenames))
        self._set_up_multiple_file_integration()

        for ind in range(len(filenames)):
            filename = str(filenames[ind])
            base_filename = os.path.basename(filename)

            progress_dialog.setValue(ind)
            progress_dialog.setLabelText("Integrating: " + base_filename)

            self.model.img_model.blockSignals(True)
            self.model.img_model.load(filename)
            self.model.img_model.blockSignals(False)

            x, y = self.integrate_spectrum()
            self._save_spectrum(base_filename, working_directory, x, y)

            QtWidgets.QApplication.processEvents()
            if progress_dialog.wasCanceled():
                break

        self._tear_down_multiple_file_integration()
        progress_dialog.close()

    def _get_spectrum_working_directory(self):
        if self.widget.spec_autocreate_cb.isChecked():
            working_directory = self.working_dir['spectrum']
        else:
            # if there is no working directory selected A file dialog opens up to choose a directory...
            working_directory = str(QtWidgets.QFileDialog.getExistingDirectory(
                self.widget, "Please choose the output directory for the integrated spectra.",
                self.working_dir['spectrum']))
        return working_directory

    def _set_up_multiple_file_integration(self):
        self.model.blockSignals(True)

    def _tear_down_multiple_file_integration(self):
        self.model.blockSignals(False)
        self.model.img_changed.emit()

    def _save_spectrum(self, base_filename, working_directory, x, y):
        file_endings = self._get_spectrum_file_endings()
        for file_ending in file_endings:
            filename = os.path.join(working_directory, os.path.splitext(base_filename)[0] + file_ending)
            self.model.pattern_model.set_pattern(x, y, filename, unit=self.get_integration_unit())
            if file_ending == '.xy':
                self.model.pattern_model.save_pattern(filename, header=self._create_spectrum_header())
            else:
                self.model.pattern_model.save_pattern(filename)

            # save the background subtracted filename
            if self.model.pattern.has_background():
                directory = os.path.join(working_directory, 'bkg_subtracted')
                if not os.path.exists(directory):
                    os.mkdir(directory)
                filename = os.path.join(directory, self.model.pattern.name + file_ending)
                if file_ending == '.xy':
                    self.model.pattern_model.save_pattern(filename, header=self._create_spectrum_header(),
                                                          subtract_background=True)
                else:
                    self.model.pattern_model.save_pattern(filename, subtract_background=True)

    def _create_spectrum_header(self):
        header = self.model.calibration_model.create_file_header()
        header = header.replace('\r\n', '\n')
        header += '\n#\n# ' + self.model.pattern_model.unit + '\t I'
        return header

    def _get_spectrum_file_endings(self):
        res = []
        if self.widget.spectrum_header_xy_cb.isChecked():
            res.append('.xy')
        if self.widget.spectrum_header_chi_cb.isChecked():
            res.append('.chi')
        if self.widget.spectrum_header_dat_cb.isChecked():
            res.append('.dat')
        return res

    def show_file_info(self):
        self.widget.file_info_widget.raise_widget()

    def get_integration_unit(self):
        if self.widget.spec_tth_btn.isChecked():
            return '2th_deg'
        elif self.widget.spec_q_btn.isChecked():
            return 'q_A^-1'
        elif self.widget.spec_d_btn.isChecked():
            return 'd_A'

    def integrate_spectrum(self):
        if self.widget.img_mask_btn.isChecked():
            mask = self.model.mask_model.get_mask()
        else:
            mask = None

        if self.widget.img_roi_btn.isChecked():
            roi_mask = self.widget.img_widget.roi.getRoiMask(self.model.img_data.shape)
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

        if self.widget.spec_tth_btn.isChecked():
            integration_unit = '2th_deg'
        elif self.widget.spec_q_btn.isChecked():
            integration_unit = 'q_A^-1'
        elif self.widget.spec_d_btn.isChecked():
            integration_unit = 'd_A'
        else:
            # in case something weird happened
            print('No correct integration unit selected')
            return

        if not self.widget.automatic_binning_cb.isChecked():
            num_points = int(str(self.widget.bin_count_txt.text()))
        else:
            num_points = None
        return self.model.calibration_model.integrate_1d(mask=mask, unit=integration_unit, num_points=num_points)

    def change_mask_mode(self):
        self.model.use_mask = self.widget.integration_image_widget.mask_btn.isChecked()
        self.widget.mask_transparent_cb.setVisible(self.model.use_mask)
        self.plot_mask()
        # print(self.model.mask_model.get_mask().shape)
        self.model.img_model.img_changed.emit()

    def load_next_img(self):
        step = int(str(self.widget.image_browse_step_txt.text()))
        self.model.img_model.load_next_file(step=step)

    def load_previous_img(self):
        step = int(str(self.widget.image_browse_step_txt.text()))
        self.model.img_model.load_previous_file(step=step)

    def filename_txt_changed(self):
        current_filename = os.path.basename(self.model.img_model.filename)
        current_directory = str(self.widget.img_directory_txt.text())
        new_filename = str(self.widget.img_filename_txt.text())
        if os.path.exists(os.path.join(current_directory, new_filename)):
            try:
                self.load_file(filename=os.path.join(current_directory, new_filename).replace('\\', '/'))
            except TypeError:
                self.widget.img_filename_txt.setText(current_filename)
        else:
            self.widget.img_filename_txt.setText(current_filename)

    def directory_txt_changed(self):
        new_directory = str(self.widget.img_directory_txt.text())
        if os.path.exists(new_directory) and new_directory != self.working_dir['image']:
            if self.model.img_model.autoprocess:
                self._files_now = dict([(f, None) for f in os.listdir(self.working_dir['image'])])
            self.working_dir['image'] = os.path.abspath(new_directory)
            old_filename = str(self.widget.img_filename_txt.text())
            self.widget.img_filename_txt.setText(old_filename + '*')
        else:
            self.widget.img_directory_txt.setText(self.working_dir['image'])

    def img_directory_btn_click(self):
        directory = str(QtWidgets.QFileDialog.getExistingDirectory(
            self.widget,
            "Please choose the image working directory.",
            self.working_dir['image']))
        if directory is not '':
            if self.model.img_model.autoprocess:
                self._files_now = dict([(f, None) for f in os.listdir(self.working_dir['image'])])
            self.working_dir['image'] = directory
            self.widget.img_directory_txt.setText(directory)

    def update_img(self, reset_img_levels=None):
        self.widget.img_filename_txt.setText(os.path.basename(self.model.img_model.filename))
        self.widget.img_directory_txt.setText(os.path.dirname(self.model.img_model.filename))
        self.widget.file_info_widget.text_lbl.setText(self.model.img_model.file_info)

        self.widget.cbn_plot_correction_btn.setText('Plot')
        self.widget.oiadac_plot_btn.setText('Plot')

        # update the window due to some errors on mac when using macports
        self._get_master_parent().update()

    def _get_master_parent(self):
        master_widget_parent = self.widget
        while master_widget_parent.parent():
            master_widget_parent = master_widget_parent.parent()
        return master_widget_parent

    def change_roi_mode(self):
        self.roi_active = not self.roi_active
        if self.img_mode == 'Image':
            if self.roi_active:
                self.widget.img_widget.activate_roi()
            else:
                self.widget.img_widget.deactivate_roi()
        if self.roi_active:
            self.widget.img_widget.roi.sigRegionChangeFinished.connect(self.update_roi_in_model)
            self.model.current_configuration.roi = self.widget.img_widget.roi.getRoiLimits()
        else:
            self.widget.img_widget.roi.sigRegionChangeFinished.disconnect(self.update_roi_in_model)
            self.model.current_configuration.roi = None

    def update_roi_in_model(self):
        self.model.current_configuration.roi = self.widget.img_widget.roi.getRoiLimits()

    def change_view_mode(self):
        if str(self.widget.img_mode_btn.text()) == 'Cake':
            self.activate_cake_mode()
        elif str(self.widget.img_mode_btn.text()) == 'Image':
            self.activate_image_mode()

    def activate_cake_mode(self):
        if not self.model.current_configuration.integrate_cake:
            self.model.current_configuration.integrate_cake = True

        self.model.current_configuration.integrate_image_2d()

        self._update_cake_line_pos()
        self._update_cake_mouse_click_pos()
        self.widget.img_widget.activate_vertical_line()
        self.widget.img_widget.deactivate_circle_scatter()

        self.widget.img_widget.img_view_box.setAspectLocked(False)

        if self.roi_active:
            self.widget.img_widget.deactivate_roi()
        self.widget.img_mode_btn.setText('Image')
        self.img_mode = str("Cake")

        self.model.img_changed.disconnect(self.plot_img)
        self.model.img_changed.disconnect(self.plot_mask)

        self.model.cake_changed.connect(self.plot_mask)
        self.model.cake_changed.connect(self.plot_cake)
        self.plot_mask()
        self.plot_cake()

    def activate_image_mode(self):
        if self.model.current_configuration.integrate_cake:
            self.model.current_configuration.integrate_cake = False

        self._update_image_line_pos()
        self._update_image_mouse_click_pos()
        self.widget.img_widget.deactivate_vertical_line()
        self.widget.img_widget.activate_circle_scatter()
        if self.roi_active:
            self.widget.img_widget.activate_roi()
        self.widget.img_widget.img_view_box.setAspectLocked(True)
        self.widget.img_mode_btn.setText('Cake')
        self.img_mode = str("Image")

        self.model.img_changed.connect(self.plot_img)
        self.model.img_changed.connect(self.plot_mask)

        self.model.cake_changed.disconnect(self.plot_mask)
        self.model.cake_changed.disconnect(self.plot_cake)

        self.plot_img()
        self.plot_mask()

    def img_autoscale_btn_clicked(self):
        if self.widget.img_autoscale_btn.isChecked():
            self.widget.img_widget.auto_range()

    def img_dock_btn_clicked(self):
        self.img_docked = not self.img_docked
        self.widget.dock_img(self.img_docked)

    def _update_cake_line_pos(self):
        cur_tth = self.get_current_spectrum_tth()
        if cur_tth < np.min(self.model.cake_tth) or cur_tth > np.max(self.model.cake_tth):
            self.widget.img_widget.vertical_line.hide()
        else:
            new_pos = get_partial_index(self.model.cake_tth, cur_tth) + 0.5
            self.widget.img_widget.vertical_line.setValue(new_pos)
            self.widget.img_widget.vertical_line.show()

    def _update_cake_mouse_click_pos(self):
        if self.clicked_tth is None or not self.model.calibration_model.is_calibrated:
            return
        import time

        tth = self.clicked_tth / np.pi * 180
        azi = self.clicked_azi

        cake_tth = self.model.cake_tth
        cake_azi = self.model.cake_azi

        if tth < np.min(cake_tth) or tth > np.max(cake_tth):
            self.widget.img_widget.mouse_click_item.hide()
        elif azi < np.min(cake_azi) or tth > np.max(cake_azi):
            self.widget.img_widget.mouse_click_item.hide()
        else:
            self.widget.img_widget.mouse_click_item.show()
            x_pos = get_partial_index(cake_tth, tth) + 0.5
            y_pos = get_partial_index(cake_azi, azi) + 0.5
            self.widget.img_widget.set_mouse_click_position(x_pos, y_pos)

    def _update_image_line_pos(self):
        if not self.model.calibration_model.is_calibrated:
            return
        cur_tth = self.get_current_spectrum_tth()
        self.widget.img_widget.set_circle_line(
            self.model.calibration_model.get_two_theta_array(), cur_tth / 180 * np.pi)

    def _update_image_mouse_click_pos(self):
        if self.clicked_tth is None or not self.model.calibration_model.is_calibrated:
            return

        tth = self.clicked_tth
        azi = self.clicked_azi / 180.0 * np.pi

        new_pos = self.model.calibration_model.get_pixel_ind(tth, azi)
        if len(new_pos) == 0:
            self.widget.img_widget.mouse_click_item.hide()
        else:
            x_ind, y_ind = new_pos
            self.widget.img_widget.set_mouse_click_position(y_ind + 0.5, x_ind + 0.5)
            self.widget.img_widget.mouse_click_item.show()

    def get_current_spectrum_tth(self):
        cur_pos = self.widget.pattern_widget.pos_line.getPos()[0]
        if self.widget.spec_q_btn.isChecked():
            cur_tth = self.convert_x_value(cur_pos, 'q_A^-1', '2th_deg')
        elif self.widget.spec_tth_btn.isChecked():
            cur_tth = cur_pos
        elif self.widget.spec_d_btn.isChecked():
            cur_tth = self.convert_x_value(cur_pos, 'd_A', '2th_deg')
        else:
            cur_tth = None
        return cur_tth

    def show_img_mouse_position(self, x, y):
        if self.img_mode == "Image":
            img_shape = self.model.img_data.shape
        elif self.img_mode == "Cake":
            img_shape = (len(self.model.cake_tth), len(self.model.cake_azi))

        if x > 0 and y > 0 and x < img_shape[1] - 1 and y < img_shape[0] - 1:
            x_pos_string = 'X:  %4d' % x
            y_pos_string = 'Y:  %4d' % y
            self.widget.mouse_x_lbl.setText(x_pos_string)
            self.widget.mouse_y_lbl.setText(y_pos_string)

            self.widget.img_widget_mouse_x_lbl.setText(x_pos_string)
            self.widget.img_widget_mouse_y_lbl.setText(y_pos_string)

            int_string = 'I:   %5d' % self.widget.img_widget.img_data[
                int(np.floor(y)), int(np.floor(x))]

            self.widget.mouse_int_lbl.setText(int_string)
            self.widget.img_widget_mouse_int_lbl.setText(int_string)

            if self.model.calibration_model.is_calibrated:
                x_temp = x
                x = np.array([y])
                y = np.array([x_temp])
                if self.img_mode == 'Cake':
                    tth = get_partial_value(self.model.cake_tth, y - 0.5)
                    azi = get_partial_value(self.model.cake_azi, x - 0.5)
                    q_value = self.convert_x_value(tth, '2th_deg', 'q_A^-1')

                else:
                    tth = self.model.calibration_model.get_two_theta_img(x, y)
                    tth = tth / np.pi * 180.0
                    q_value = self.convert_x_value(tth, '2th_deg', 'q_A^-1')
                    azi = self.model.calibration_model.get_azi_img(x, y) / np.pi * 180

                azi = azi + 360 if azi < 0 else azi
                d = self.convert_x_value(tth, '2th_deg', 'd_A')
                tth_str = u"2θ:%9.3f  " % tth
                self.widget.mouse_tth_lbl.setText(tth_str)
                self.widget.mouse_d_lbl.setText('d:%9.3f  ' % d)
                self.widget.mouse_q_lbl.setText('Q:%9.3f  ' % q_value)
                self.widget.mouse_azi_lbl.setText('X:%9.3f  ' % azi)
                self.widget.img_widget_mouse_tth_lbl.setText(tth_str)
                self.widget.img_widget_mouse_d_lbl.setText('d:%9.3f  ' % d)
                self.widget.img_widget_mouse_q_lbl.setText('Q:%9.3f  ' % q_value)
                self.widget.img_widget_mouse_azi_lbl.setText('X:%9.3f  ' % azi)
            else:
                self.widget.mouse_tth_lbl.setText(u'2θ: -')
                self.widget.mouse_d_lbl.setText('d: -')
                self.widget.mouse_q_lbl.setText('Q: -')
                self.widget.mouse_azi_lbl.setText('X: -')
                self.widget.img_widget_mouse_tth_lbl.setText(u'2θ: -')
                self.widget.img_widget_mouse_d_lbl.setText('d: -')
                self.widget.img_widget_mouse_q_lbl.setText('Q: -')
                self.widget.img_widget_mouse_azi_lbl.setText('X: -')

    def img_mouse_click(self, x, y):
        # update click position
        try:
            x_pos_string = 'X:  %4d' % x
            y_pos_string = 'Y:  %4d' % y
            int_string = 'I:   %5d' % self.widget.img_widget.img_data[
                int(np.floor(y)), int(np.floor(x))]

            self.widget.click_x_lbl.setText(x_pos_string)
            self.widget.click_y_lbl.setText(y_pos_string)
            self.widget.click_int_lbl.setText(int_string)

            self.widget.img_widget_click_x_lbl.setText(x_pos_string)
            self.widget.img_widget_click_y_lbl.setText(y_pos_string)
            self.widget.img_widget_click_int_lbl.setText(int_string)
        except IndexError:
            self.widget.click_int_lbl.setText('I: ')

        if self.model.calibration_model.is_calibrated:
            x, y = y, x  # the indices are reversed for the img_array
            if self.img_mode == 'Cake':  # cake mode
                cake_shape = (len(self.model.cake_tth), len(self.model.cake_azi))
                if x < 0 or y < 0 or x > (cake_shape[0] - 1) or y > (cake_shape[1] - 1):
                    return
                y = np.array([y])
                x = np.array([x])
                tth = get_partial_value(self.model.cake_tth, y - 0.5) / 180 * np.pi
                azi = get_partial_value(self.model.cake_azi, x - 0.5)
            elif self.img_mode == 'Image':  # image mode
                img_shape = self.model.img_data.shape
                if x < 0 or y < 0 or x > img_shape[0] - 1 or y > img_shape[1] - 1:
                    return
                tth = self.model.calibration_model.get_two_theta_img(x, y)
                azi = self.model.calibration_model.get_azi_img(np.array([x]), np.array([y])) / np.pi * 180
                self.widget.img_widget.set_circle_line(
                    self.model.calibration_model.get_two_theta_array(), tth)
            else:  # in the case of whatever
                tth = 0
                azi = 0

            self.clicked_tth = tth
            self.clicked_azi = azi

            # calculate right unit for the position line the pattern widget
            if self.widget.spec_q_btn.isChecked():
                pos = 4 * np.pi * \
                      np.sin(tth / 2) / \
                      self.model.calibration_model.wavelength / 1e10
            elif self.widget.spec_tth_btn.isChecked():
                pos = tth / np.pi * 180
            elif self.widget.spec_d_btn.isChecked():
                pos = self.model.calibration_model.wavelength / \
                      (2 * np.sin(tth / 2)) * 1e10
            else:
                pos = 0
            self.widget.pattern_widget.set_pos_line(pos)
        self.widget.click_tth_lbl.setText(self.widget.mouse_tth_lbl.text())
        self.widget.click_d_lbl.setText(self.widget.mouse_d_lbl.text())
        self.widget.click_q_lbl.setText(self.widget.mouse_q_lbl.text())
        self.widget.click_azi_lbl.setText(self.widget.mouse_azi_lbl.text())
        self.widget.img_widget_click_tth_lbl.setText(self.widget.mouse_tth_lbl.text())
        self.widget.img_widget_click_d_lbl.setText(self.widget.mouse_d_lbl.text())
        self.widget.img_widget_click_q_lbl.setText(self.widget.mouse_q_lbl.text())
        self.widget.img_widget_click_azi_lbl.setText(self.widget.mouse_azi_lbl.text())

    def set_iteration_mode_number(self):
        self.model.img_model.set_file_iteration_mode('number')

    def set_iteration_mode_time(self):
        self.model.img_model.set_file_iteration_mode('time')

    def convert_x_value(self, value, previous_unit, new_unit):
        wavelength = self.model.calibration_model.wavelength
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

    def load_calibration(self):
        filename = open_file_dialog(
            self.widget, "Load calibration...",
            self.working_dir[
                'calibration'],
            '*.poni')
        if filename is not '':
            self.working_dir['calibration'] = os.path.dirname(filename)
            self.model.calibration_model.load(filename)
            self.widget.calibration_lbl.setText(
                self.model.calibration_model.calibration_name)
            self.widget.wavelength_lbl.setText('{:.4f}'.format(self.model.calibration_model.wavelength*1e10) + ' A')
            self.model.img_model.img_changed.emit()

    def set_wavelength(self):
        wavelength, ok = QtWidgets.QInputDialog.getText(self.widget, 'Set Wavelength', 'Wavelength in Angstroms:')
        if ok:
            self.model.calibration_model.spectrum_geometry.wavelength = float(wavelength)*1e-10
            self.widget.wavelength_lbl.setText('{:.4f}'.format(self.model.calibration_model.wavelength*1e10) + ' A')
            self.model.img_model.img_changed.emit()

    def auto_process_cb_click(self):
        self.model.img_model.autoprocess = self.widget.autoprocess_cb.isChecked()

    def save_img(self):
        img_filename = os.path.splitext(os.path.basename(self.model.img_model.filename))[0]
        filename = save_file_dialog(self.widget, "Save Image.",
                                    os.path.join(self.working_dir['image'],
                                                 img_filename + '.png'),
                                    ('Image (*.png);;Data (*.tiff)'))
        if filename is not '':
            if filename.endswith('.png'):
                if self.img_mode == 'Cake':
                    self.widget.img_widget.deactivate_vertical_line()
                elif self.img_mode == 'Image':
                    self.widget.img_widget.deactivate_circle_scatter()
                    self.widget.img_widget.deactivate_roi()

                QtWidgets.QApplication.processEvents()
                self.widget.img_widget.save_img(filename)

                if self.img_mode == 'Cake':
                    self.widget.img_widget.activate_vertical_line()
                elif self.img_mode == 'Image':
                    self.widget.img_widget.activate_circle_scatter()
                    if self.roi_active:
                        self.widget.img_widget.activate_roi()
            elif filename.endswith('.tiff'):
                if self.img_mode == 'Image':
                    im_array = np.int32(self.model.img_data)
                elif self.img_mode == 'Cake':
                    im_array = np.int32(self.model.cake_data)
                im_array = np.flipud(im_array)
                im = Image.fromarray(im_array)
                im.save(filename)

    def cbn_groupbox_changed(self):
        if not self.model.calibration_model.is_calibrated:
            self.widget.cbn_groupbox.setChecked(False)
            QtWidgets.QMessageBox.critical(self.widget,
                                           'ERROR',
                                           'Please calibrate the geometry first or load an existent calibration file. ' + \
                                           'The cBN seat correction needs a calibrated geometry.')
            return

        if self.widget.cbn_groupbox.isChecked():
            diamond_thickness = float(str(self.widget.cbn_diamond_thickness_txt.text()))
            seat_thickness = float(str(self.widget.cbn_seat_thickness_txt.text()))
            inner_seat_radius = float(str(self.widget.cbn_inner_seat_radius_txt.text()))
            outer_seat_radius = float(str(self.widget.cbn_outer_seat_radius_txt.text()))
            tilt = float(str(self.widget.cbn_cell_tilt_txt.text()))
            tilt_rotation = float(str(self.widget.cbn_tilt_rotation_txt.text()))
            center_offset = float(str(self.widget.cbn_center_offset_txt.text()))
            center_offset_angle = float(str(self.widget.cbn_center_offset_angle_txt.text()))
            seat_absorption_length = float(str(self.widget.cbn_seat_al_txt.text()))
            anvil_absorption_length = float(str(self.widget.cbn_anvil_al_txt.text()))

            tth_array = 180.0 / np.pi * self.model.calibration_model.spectrum_geometry.ttha
            azi_array = 180.0 / np.pi * self.model.calibration_model.spectrum_geometry.chia

            new_cbn_correction = CbnCorrection(
                tth_array=tth_array,
                azi_array=azi_array,
                diamond_thickness=diamond_thickness,
                seat_thickness=seat_thickness,
                small_cbn_seat_radius=inner_seat_radius,
                large_cbn_seat_radius=outer_seat_radius,
                tilt=tilt,
                tilt_rotation=tilt_rotation,
                center_offset=center_offset,
                center_offset_angle=center_offset_angle,
                cbn_abs_length=seat_absorption_length,
                diamond_abs_length=anvil_absorption_length
            )
            if not new_cbn_correction == self.model.img_model.get_img_correction("cbn"):
                t1 = time.time()
                new_cbn_correction.update()
                print("Time needed for correction calculation: {0}".format(time.time() - t1))
                try:
                    self.model.img_model.delete_img_correction("cbn")
                except KeyError:
                    pass
                self.model.img_model.add_img_correction(new_cbn_correction, "cbn")
        else:
            self.model.img_model.delete_img_correction("cbn")

    def cbn_plot_correction_btn_clicked(self):
        if str(self.widget.cbn_plot_correction_btn.text()) == 'Plot':
            self.widget.img_widget.plot_image(self.model.img_model._img_corrections.get_correction("cbn").get_data(),
                                              True)
            self.widget.cbn_plot_correction_btn.setText('Back')
            self.widget.oiadac_plot_btn.setText('Plot')
        else:
            self.widget.cbn_plot_correction_btn.setText('Plot')
            if self.img_mode == 'Cake':
                self.plot_cake(True)
            elif self.img_mode == 'Image':
                self.plot_img(True)

    def oiadac_groupbox_changed(self):
        if not self.model.calibration_model.is_calibrated:
            self.widget.oiadac_groupbox.setChecked(False)
            QtWidgets.QMessageBox.critical(
                self.widget,
                'ERROR',
                'Please calibrate the geometry first or load an existent calibration file. ' + \
                'The oblique incidence angle detector absorption correction needs a calibrated' + \
                'geometry.'
            )
            return

        if self.widget.oiadac_groupbox.isChecked():
            detector_thickness = float(str(self.widget.oiadac_thickness_txt.text()))
            absorption_length = float(str(self.widget.oiadac_abs_length_txt.text()))

            _, fit2d_parameter = self.model.calibration_model.get_calibration_parameter()
            detector_tilt = fit2d_parameter['tilt']
            detector_tilt_rotation = fit2d_parameter['tiltPlanRotation']

            tth_array = self.model.calibration_model.spectrum_geometry.ttha
            azi_array = self.model.calibration_model.spectrum_geometry.chia
            import time

            t1 = time.time()

            oiadac_correction = ObliqueAngleDetectorAbsorptionCorrection(
                tth_array, azi_array,
                detector_thickness=detector_thickness,
                absorption_length=absorption_length,
                tilt=detector_tilt,
                rotation=detector_tilt_rotation,
            )
            print("Time needed for correction calculation: {0}".format(time.time() - t1))
            try:
                self.model.img_model.delete_img_correction("oiadac")
            except KeyError:
                pass
            self.model.img_model.add_img_correction(oiadac_correction, "oiadac")
        else:
            self.model.img_model.delete_img_correction("oiadac")

    def oiadac_plot_btn_clicked(self):
        if str(self.widget.oiadac_plot_btn.text()) == 'Plot':
            self.widget.img_widget.plot_image(self.model.img_model._img_corrections.get_correction("oiadac").get_data(),
                                              True)
            self.widget.oiadac_plot_btn.setText('Back')
            self.widget.cbn_plot_correction_btn.setText('Plot')
        else:
            self.widget.oiadac_plot_btn.setText('Plot')
            if self.img_mode == 'Cake':
                self.plot_cake(True)
            elif self.img_mode == 'Image':
                self.plot_img(True)

    def _check_absorption_correction_shape(self):
        if self.model.img_model.has_corrections() is None and self.widget.cbn_groupbox.isChecked():
            self.widget.cbn_groupbox.setChecked(False)
            self.widget.oiadac_groupbox.setChecked(False)
            QtWidgets.QMessageBox.critical(self.widget,
                                           'ERROR',
                                           'Due to a change in image dimensions the absorption ' +
                                           'corrections have been removed')

    def update_gui(self):
        self.widget.img_mask_btn.setChecked(self.model.use_mask)
        self.widget.mask_transparent_cb.setChecked(self.model.transparent_mask)
        self.widget.autoprocess_cb.setChecked(self.model.img_model.autoprocess)
        self.widget.calibration_lbl.setText(self.model.calibration_model.calibration_name)

        if self.model.current_configuration.integrate_cake and self.img_mode == 'Image':
            self.activate_cake_mode()
        elif not self.model.current_configuration.integrate_cake and self.img_mode == 'Cake':
            self.activate_image_mode()
        elif self.model.current_configuration.integrate_cake and self.img_mode == 'Cake':
            self._update_cake_line_pos()
            self._update_cake_mouse_click_pos()
        elif not self.model.current_configuration.integrate_cake and self.img_mode == 'Image':
            self._update_image_line_pos()
            self._update_image_mouse_click_pos()
