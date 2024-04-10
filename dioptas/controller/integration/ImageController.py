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

import os

import numpy as np
from PIL import Image
from qtpy import QtWidgets, QtCore
import pyqtgraph as pg
from xypattern import Pattern

from ...widgets.UtilityWidgets import open_file_dialog, open_files_dialog, save_file_dialog
# imports for type hinting in PyCharm -- DO NOT DELETE
from ...widgets.integration import IntegrationWidget
from ...model.DioptasModel import DioptasModel
from ...model.util.HelperModule import get_partial_index, get_partial_value

from .EpicsController import EpicsController


class ImageController(object):
    """
    The ImageController manages the Image actions in the Integration Window. It connects the file actions, as
    well as interaction with the image_view.
    """

    def __init__(self, widget: IntegrationWidget, dioptas_model: DioptasModel):
        """
        :param widget: Reference to IntegrationWidget
        :param dioptas_model: Reference to DioptasModel object
        """
        self.widget = widget
        self.model = dioptas_model

        self.epics_controller = EpicsController(self.widget, self.model)

        self.img_docked = True
        self.view_mode = 'normal'  # modes available: normal, alternative
        self.roi_active = False

        self.vertical_splitter_alternative_state = None
        self.vertical_splitter_normal_state = None
        self.horizontal_splitter_alternative_state = None
        self.horizontal_splitter_normal_state = None

        self.create_signals()
        self.create_mouse_behavior()

    def plot_img(self, auto_scale=None):
        """
        Plots the current image loaded in self.img_data.
        :param auto_scale:
            Determines if intensities should be auto-scaled. If value is None it will use the parameter saved in the
            Object (self._auto_scale)
        """
        if auto_scale is None:
            auto_scale = self.widget.img_autoscale_btn.isChecked()

        if self.widget.integration_image_widget.show_background_subtracted_img_btn.isChecked():
            self.widget.img_widget.plot_image(self.model.img_model.img_data, False)
        else:
            self.widget.img_widget.plot_image(self.model.img_model.raw_img_data, False)

        if auto_scale:
            self.widget.img_widget.auto_level()

    def plot_cake(self, auto_scale=None):
        """
        Plots the cake saved in the calibration data
        :param auto_scale:
            Determines if the intensity should be auto-scaled. If value is None it will use the parameter saved in the
            object (self._auto_scale)
        """
        if auto_scale is None:
            auto_scale = self.widget.img_autoscale_btn.isChecked()

        shift_amount = self.widget.cake_shift_azimuth_sl.value()
        self.widget.cake_widget.plot_image(np.roll(self.model.cake_data, shift_amount, axis=0))
        self.plot_cake_integral()
        self.update_cake_axes_range()
        if auto_scale:
            self.widget.cake_widget.auto_level()

    def plot_cake_integral(self, tth=None):
        if not self.widget.cake_widget.cake_integral_plot.isVisible():
            return

        if tth is None:
            tth = self.model.clicked_tth

        x, y = self.model.calibration_model.cake_integral(
            tth,
            self.widget.integration_control_widget.integration_options_widget.cake_integral_width_sb.value()
        )
        shift_amount = self.widget.cake_shift_azimuth_sl.value()
        self.widget.cake_widget.plot_cake_integral(x, np.roll(y, shift_amount))

    def _update_cake_integral(self):
        self.plot_cake_integral()

    def save_cake_integral(self):
        img_filename, _ = os.path.splitext(os.path.basename(self.model.img_model.filename))
        filename = save_file_dialog(
            self.widget, "Save Cake Integral Data.",
            os.path.join(self.model.working_directories['pattern'],
                         img_filename + '.xy'))

        if filename != '':
            integral_pattern = Pattern(*self.widget.cake_widget.cake_integral_item.getData())
            integral_pattern.save(filename)

    def plot_mask(self):
        """
        Plots the mask data.
        """
        if self.model.use_mask and self.widget.img_mode == 'Image':
            self.widget.img_widget.activate_mask()
            self.widget.img_widget.plot_mask(self.model.mask_model.get_img())
        else:
            self.widget.img_widget.deactivate_mask()

    def update_mask_transparency(self):
        """
        Changes the colormap of the mask according to the transparency option selection in the GUI. Resulting Mask will
        be either transparent or solid.
        """
        self.model.transparent_mask = self.widget.mask_transparent_cb.isChecked()
        if self.model.transparent_mask:
            self.widget.img_widget.set_mask_color([255, 0, 0, 100])
        else:
            self.widget.img_widget.set_mask_color([255, 0, 0, 255])

    def create_signals(self):
        self.model.configuration_selected.connect(self.update_gui_from_configuration)
        self.model.img_changed.connect(self.update_img_control_widget)

        self.model.img_changed.connect(self.plot_img)
        self.model.img_changed.connect(self.plot_mask)

        """
        Creates all the connections of the GUI elements.
        """
        self.widget.img_step_file_widget.next_btn.clicked.connect(self.load_next_img)
        self.widget.img_step_file_widget.previous_btn.clicked.connect(self.load_previous_img)
        self.widget.load_img_btn.clicked.connect(self.load_file)
        self.widget.img_filename_txt.editingFinished.connect(self.filename_txt_changed)
        self.widget.img_directory_txt.editingFinished.connect(self.directory_txt_changed)
        self.widget.img_directory_btn.clicked.connect(self.img_directory_btn_click)

        self.widget.img_step_series_widget.next_btn.clicked.connect(self.load_next_series_img)
        self.widget.img_step_series_widget.previous_btn.clicked.connect(self.load_prev_series_img)
        self.widget.img_step_series_widget.pos_txt.editingFinished.connect(self.load_series_img)

        self.widget.file_info_btn.clicked.connect(self.show_file_info)

        self.widget.img_step_file_widget.browse_by_name_rb.clicked.connect(self.set_iteration_mode_number)
        self.widget.img_step_file_widget.browse_by_time_rb.clicked.connect(self.set_iteration_mode_time)

        self.widget.image_control_widget.sources_cb.currentTextChanged.connect(self.select_source)

        ###
        # Image widget image specific controls
        self.widget.img_roi_btn.clicked.connect(self.click_roi_btn)
        self.widget.img_mask_btn.clicked.connect(self.change_mask_mode)
        self.widget.mask_transparent_cb.clicked.connect(self.update_mask_transparency)

        ###
        # Image Widget cake specific controls
        self.widget.img_phases_btn.clicked.connect(self.toggle_show_phases)
        self.widget.cake_shift_azimuth_sl.valueChanged.connect(self.cake_shift_changed)
        self.widget.integration_image_widget.cake_view.img_view_box.sigRangeChanged.connect(self.update_cake_axes_range)
        self.widget.pattern_q_btn.clicked.connect(self.set_cake_axis_to_q)
        self.widget.pattern_tth_btn.clicked.connect(self.set_cake_axis_to_2th)
        self.widget.integration_control_widget.integration_options_widget.cake_integral_width_sb.valueChanged. \
            connect(self._update_cake_integral)
        self.widget.integration_control_widget.integration_options_widget.cake_integral_width_sb.editingFinished. \
            connect(self._update_cake_integral)
        self.widget.integration_control_widget.integration_options_widget.cake_save_integral_btn.clicked. \
            connect(self.save_cake_integral)

        ###
        # General Image Widget controls
        self.widget.img_dock_btn.clicked.connect(self.img_dock_btn_clicked)
        self.widget.img_autoscale_btn.clicked.connect(self.img_autoscale_btn_clicked)
        self.widget.img_mode_btn.clicked.connect(self.change_view_mode)

        self.widget.integration_image_widget.show_background_subtracted_img_btn.clicked.connect(
            self.show_background_subtracted_img_btn_clicked)

        self.widget.qa_save_img_btn.clicked.connect(self.save_img)
        self.widget.load_calibration_btn.clicked.connect(self.load_calibration)
        self.widget.set_wavelnegth_btn.clicked.connect(self.set_wavelength)

        # signals
        self.widget.change_view_btn.clicked.connect(self.change_view_btn_clicked)
        self.widget.autoprocess_cb.toggled.connect(self.auto_process_cb_click)

    def activate(self):
        if self.widget.img_mode == 'Image':
            if not self.model.img_changed.has_listener(self.plot_img):
                self.model.img_changed.connect(self.plot_img)
            if not self.model.img_changed.has_listener(self.plot_mask):
                self.model.img_changed.connect(self.plot_mask)
        elif self.widget.img_mode == 'Cake':
            if not self.model.cake_changed.has_listener(self.plot_cake):
                self.model.cake_changed.connect(self.plot_cake)
        self.widget.calibration_lbl.setText(
            self.model.calibration_model.calibration_name
        )
        self.widget.wavelength_lbl.setText(
            "{:.4f}".format(self.model.calibration_model.wavelength * 1e10) + " A"
        )

    def update_image(self):
        if self.widget.img_mode == 'Image':
            self.plot_mask()
            self.plot_img()
        elif self.widget.img_mode == 'Cake':
            self.plot_cake()

    def deactivate(self):
        if self.model.img_changed.has_listener(self.plot_img):
            self.model.img_changed.disconnect(self.plot_img)
        if self.plot_mask in self.model.img_changed.listeners:
            self.model.img_changed.disconnect(self.plot_mask)
        if self.plot_cake in self.model.cake_changed.listeners:
            self.model.cake_changed.disconnect(self.plot_cake)

    def create_mouse_behavior(self):
        """
        Creates the signal connections of mouse interactions
        """
        self.widget.img_widget.mouse_left_clicked.connect(self.img_mouse_click)
        self.widget.img_widget.mouse_moved.connect(self.show_img_mouse_position)
        self.widget.cake_widget.mouse_left_clicked.connect(self.img_mouse_click)
        self.widget.cake_widget.mouse_moved.connect(self.show_img_mouse_position)

        self.model.clicked_tth_changed.connect(self.set_cake_line_position)
        self.model.clicked_tth_changed.connect(self.set_image_line_position)

    def load_file(self, *args, **kwargs):
        filename = kwargs.get('filename', None)
        if filename is None:
            filenames = open_files_dialog(self.widget, "Load image data file(s)",
                                          self.model.working_directories['image'])
        else:
            filenames = [filename]

        if filenames is not None and len(filenames) != 0:
            self.model.working_directories['image'] = os.path.dirname(str(filenames[0]))
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
                if self.widget.img_batch_mode_average_rb.isChecked():
                    self.model.img_model.blockSignals(True)
                    self.model.img_model.load(str(filenames[0]))
                    for ind in range(1, len(filenames)):
                        self.model.img_model.add(filenames[ind])
                    self.model.img_model._img_data = self.model.img_model._img_data / len(filenames)
                    self.model.img_model._calculate_img_data()
                    self.model.img_model.blockSignals(False)
                    self.model.img_model.img_changed.emit()
                elif self.widget.img_batch_mode_integrate_rb.isChecked():
                    self._load_multiple_files(filenames)
                elif self.widget.img_batch_mode_image_save_rb.isChecked():
                    self._save_multiple_image_files(filenames)

    def _load_multiple_files(self, filenames):
        if not self.model.calibration_model.is_calibrated:
            self.widget.show_error_msg("Can not integrate multiple images without calibration.")
            return

        working_directory = self._get_pattern_working_directory()
        if working_directory == '':
            return  # abort file processing if no directory was selected

        progress_dialog = self.widget.get_progress_dialog("Integrating multiple files.", "Abort Integration",
                                                          len(filenames))
        self._set_up_batch_processing()

        for ind in range(len(filenames)):
            filename = str(filenames[ind])
            base_filename = os.path.basename(filename)

            progress_dialog.setValue(ind)
            progress_dialog.setLabelText("Integrating: " + base_filename)

            self.model.img_model.blockSignals(True)
            self.model.img_model.load(filename)
            self.model.img_model.blockSignals(False)

            x, y = self.integrate_pattern()
            self._save_pattern(base_filename, working_directory, x, y)

            QtWidgets.QApplication.processEvents()
            if progress_dialog.wasCanceled():
                break

        progress_dialog.close()
        self._tear_down_batch_processing()

    def _get_pattern_working_directory(self):
        if self.widget.pattern_autocreate_cb.isChecked():
            working_directory = self.model.working_directories['pattern']
        else:
            # if there is no working directory selected A file dialog opens up to choose a directory...
            working_directory = str(QtWidgets.QFileDialog.getExistingDirectory(
                self.widget, "Please choose the output directory for the integrated Patterns.",
                self.model.working_directories['pattern']))
        return working_directory

    def _set_up_batch_processing(self):
        self.model.blockSignals(True)

    def _tear_down_batch_processing(self):
        self.model.blockSignals(False)
        self.model.img_changed.emit()
        self.model.pattern_changed.emit()

    def _save_multiple_image_files(self, filenames):
        working_directory = str(QtWidgets.QFileDialog.getExistingDirectory(
            self.widget, "Please choose the output directory for the Images.",
            self.model.working_directories['image']))

        if working_directory == '':
            return

        self._set_up_batch_processing()
        progress_dialog = self.widget.get_progress_dialog("Saving multiple image files.", "Abort",
                                                          len(filenames))
        QtWidgets.QApplication.processEvents()

        self.model.current_configuration.auto_integrate_pattern = False

        for ind, filename in enumerate(filenames):
            base_filename = os.path.basename(filename)

            progress_dialog.setValue(ind)
            progress_dialog.setLabelText("Saving: " + base_filename)

            self.model.img_model.load(str(filename))
            self.save_img(os.path.join(working_directory, 'batch_' + base_filename))

            QtWidgets.QApplication.processEvents()
            if progress_dialog.wasCanceled():
                break

        self.model.current_configuration.auto_integrate_pattern = True

        progress_dialog.close()
        self._tear_down_batch_processing()

    def _save_pattern(self, base_filename, working_directory, x, y):
        file_endings = self._get_pattern_file_endings()
        for file_ending in file_endings:
            filename = os.path.join(working_directory, os.path.splitext(base_filename)[0] + file_ending)
            self.model.pattern_model.set_pattern(x, y, filename, unit=self.get_integration_unit())
            if file_ending == '.xy':
                self.model.pattern_model.save_pattern(filename, header=self._create_pattern_header())
            else:
                self.model.pattern_model.save_pattern(filename)

            # save the background subtracted filename
            if self.model.pattern.auto_bkg is not None:
                directory = os.path.join(working_directory, 'bkg_subtracted')
                if not os.path.exists(directory):
                    os.mkdir(directory)
                filename = os.path.join(directory, self.model.pattern.name + file_ending)
                if file_ending == '.xy':
                    self.model.pattern_model.save_pattern(filename, header=self._create_pattern_header(),
                                                          subtract_background=True)
                else:
                    self.model.pattern_model.save_pattern(filename, subtract_background=True)

    def _create_pattern_header(self):
        header = self.model.calibration_model.create_file_header()
        header = header.replace('\r\n', '\n')
        header += '\n#\n# ' + self.model.pattern_model.unit + '\t I'
        return header

    def _get_pattern_file_endings(self):
        res = []
        if self.widget.pattern_header_xy_cb.isChecked():
            res.append('.xy')
        if self.widget.pattern_header_chi_cb.isChecked():
            res.append('.chi')
        if self.widget.pattern_header_dat_cb.isChecked():
            res.append('.dat')
        return res

    def show_file_info(self):
        self.widget.file_info_widget.raise_widget()

    def get_integration_unit(self):
        if self.widget.pattern_tth_btn.isChecked():
            return '2th_deg'
        elif self.widget.pattern_q_btn.isChecked():
            return 'q_A^-1'
        elif self.widget.pattern_d_btn.isChecked():
            return 'd_A'

    def integrate_pattern(self):
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

        if self.widget.pattern_tth_btn.isChecked():
            integration_unit = '2th_deg'
        elif self.widget.pattern_q_btn.isChecked():
            integration_unit = 'q_A^-1'
        elif self.widget.pattern_d_btn.isChecked():
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
        self.model.img_model.img_changed.emit()

    def update_mask_mode(self):
        self.widget.integration_image_widget.mask_btn.setChecked(bool(self.model.use_mask))
        self.widget.mask_transparent_cb.setVisible(bool(self.model.use_mask))
        self.widget.mask_transparent_cb.setChecked(bool(self.model.transparent_mask))

    def update_img_mode(self):
        self.widget.img_mode_btn.click()

    def load_series_img(self):
        pos = int(str(self.widget.img_step_series_widget.pos_txt.text()))
        self.model.img_model.load_series_img(pos)

    def load_prev_series_img(self):
        step = int(str(self.widget.img_step_series_widget.step_txt.text()))
        pos = int(str(self.widget.img_step_series_widget.pos_txt.text()))
        self.model.img_model.load_series_img(pos - step)

    def load_next_series_img(self):
        step = int(str(self.widget.img_step_series_widget.step_txt.text()))
        pos = int(str(self.widget.img_step_series_widget.pos_txt.text()))
        self.model.img_model.load_series_img(pos + step)

    def load_next_img(self):
        step = int(str(self.widget.img_step_file_widget.step_txt.text()))
        self.model.img_model.load_next_file(step=step)

    def load_previous_img(self):
        step = int(str(self.widget.img_step_file_widget.step_txt.text()))
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
        if os.path.exists(new_directory) and new_directory != self.model.working_directories['image']:
            if self.model.img_model.autoprocess:
                self._files_now = dict([(f, None) for f in os.listdir(self.model.working_directories['image'])])
            self.model.working_directories['image'] = os.path.abspath(new_directory)
            old_filename = str(self.widget.img_filename_txt.text())
            self.widget.img_filename_txt.setText(old_filename + '*')
        else:
            self.widget.img_directory_txt.setText(self.model.working_directories['image'])

    def img_directory_btn_click(self):
        directory = str(QtWidgets.QFileDialog.getExistingDirectory(
            self.widget,
            "Please choose the image working directory.",
            self.model.working_directories['image']))
        if directory != '':
            if self.model.img_model.autoprocess:
                self._files_now = dict([(f, None) for f in os.listdir(self.model.working_directories['image'])])
            self.model.working_directories['image'] = directory
            self.widget.img_directory_txt.setText(directory)

    def update_img_control_widget(self):
        self.widget.img_step_series_widget.setVisible(int(self.model.img_model.series_max > 1))
        self.widget.img_step_series_widget.pos_validator.setTop(self.model.img_model.series_max)
        self.widget.img_step_series_widget.pos_txt.setText(str(self.model.img_model.series_pos))

        self.widget.file_info_btn.setVisible(self.model.img_model.file_info != "")
        self.widget.move_btn.setVisible(len(self.model.img_model.motors_info) > 0)

        self.widget.img_filename_txt.setText(os.path.basename(self.model.img_model.filename))
        self.widget.img_directory_txt.setText(os.path.dirname(self.model.img_model.filename))
        self.widget.file_info_widget.text_lbl.setText(self.model.img_model.file_info)

        self.widget.image_control_widget.sources_widget.setVisible(not (self.model.img_model.sources is None))
        if self.model.img_model.sources is not None:
            sources_cb = self.widget.image_control_widget.sources_cb
            sources_cb.blockSignals(True)
            # remove all previous items:
            for _ in range(sources_cb.count()):
                sources_cb.removeItem(0)

            sources_cb.addItems(self.model.img_model.sources)
            sources_cb.setCurrentText(self.model.img_model.selected_source)
            sources_cb.blockSignals(False)

        self.widget.cbn_plot_btn.setText('Plot')
        self.widget.oiadac_plot_btn.setText('Plot')

        # update the window due to some errors on mac when using macports
        self._get_master_parent().update()

    def _get_master_parent(self):
        master_widget_parent = self.widget
        while master_widget_parent.parent():
            master_widget_parent = master_widget_parent.parent()
        return master_widget_parent

    def click_roi_btn(self):
        if self.model.current_configuration.roi is None:
            self.model.current_configuration.roi = self.widget.img_widget.roi.getRoiLimits()
        else:
            self.model.current_configuration.roi = None
        self.update_roi_in_gui()

    def update_roi_in_gui(self):
        roi = self.model.mask_model.roi
        if roi is None:
            self.widget.img_widget.deactivate_roi()
            self.widget.img_roi_btn.setChecked(False)
            if self.roi_active:
                self.widget.img_widget.roi.sigRegionChangeFinished.disconnect(self.update_roi_in_model)
                self.roi_active = False
            return

        if not self.model.current_configuration.auto_integrate_cake:
            self.widget.img_roi_btn.setChecked(True)
            self.widget.img_widget.activate_roi()
            self.widget.img_widget.update_roi_shade_limits(self.model.img_data.shape)

            pos = QtCore.QPoint(int(roi[2]), int(roi[0]))
            size = QtCore.QPoint(int(roi[3] - roi[2]), int(roi[1] - roi[0]))
            self.widget.img_widget.roi.setRoiLimits(pos, size)

            if not self.roi_active:
                self.widget.img_widget.roi.sigRegionChangeFinished.connect(self.update_roi_in_model)
                self.roi_active = True

    def update_roi_in_model(self):
        self.model.current_configuration.roi = self.widget.img_widget.roi.getRoiLimits()

    def change_view_mode(self):
        if str(self.widget.img_mode_btn.text()) == 'Cake':
            self.activate_cake_mode()
        elif str(self.widget.img_mode_btn.text()) == 'Image':
            self.activate_image_mode()

    def toggle_show_phases(self):
        if str(self.widget.img_phases_btn.text()) == 'Show Phases':
            self.widget.integration_image_widget.cake_view.show_all_visible_cake_phases(
                self.widget.phase_widget.phase_show_cbs)
            self.widget.img_phases_btn.setText('Hide Phases')
            self.model.enabled_phases_in_cake.emit()
        elif str(self.widget.img_phases_btn.text()) == 'Hide Phases':
            self.widget.integration_image_widget.cake_view.hide_all_cake_phases()
            self.widget.img_phases_btn.setText('Show Phases')

    def cake_shift_changed(self):
        self.plot_cake()
        self._update_cake_mouse_click_pos()
        self.update_cake_azimuth_axis()
        self.plot_cake_integral(None)

    def activate_cake_mode(self):
        if self.model.calibration_model.cake_geometry is None:
            self.widget.show_error_msg("Can not switch to the cake mode without calibration.")
            return

        if not self.model.current_configuration.auto_integrate_cake:
            self.model.current_configuration.auto_integrate_cake = True

        self.model.current_configuration.integrate_image_2d()

        self.set_cake_line_position(self.model.clicked_tth)
        self._update_cake_mouse_click_pos()

        self.widget.img_mode_btn.setText('Image')
        self.widget.img_mode = str("Cake")

        self.model.img_changed.disconnect(self.plot_img)
        self.model.img_changed.disconnect(self.plot_mask)

        self.model.cake_changed.connect(self.plot_cake)
        self.plot_cake()

        self.widget.cake_shift_azimuth_sl.setVisible(True)
        self.widget.cake_shift_azimuth_sl.setMinimum(int(-len(self.model.cake_azi) / 2))
        self.widget.cake_shift_azimuth_sl.setMaximum(int(len(self.model.cake_azi) / 2))
        self.widget.cake_shift_azimuth_sl.setSingleStep(1)
        self.widget.img_phases_btn.setVisible(True)

        self.widget.integration_image_widget.img_pg_layout.hide()
        self.widget.integration_image_widget.cake_pg_layout.show()

    def activate_image_mode(self):
        if self.model.current_configuration.auto_integrate_cake:
            self.model.current_configuration.auto_integrate_cake = False

        self.widget.cake_shift_azimuth_sl.setVisible(False)
        self.widget.img_phases_btn.setVisible(False)

        self._update_image_line_pos()
        self._update_image_mouse_click_pos()

        self.widget.img_mode_btn.setText('Cake')
        self.widget.img_mode = str("Image")
        self.model.img_changed.connect(self.plot_img)
        self.model.img_changed.connect(self.plot_mask)
        self.model.cake_changed.disconnect(self.plot_cake)
        self.plot_img()
        self.plot_mask()

        self.widget.integration_image_widget.img_pg_layout.show()
        self.widget.integration_image_widget.cake_pg_layout.hide()

    def img_autoscale_btn_clicked(self):
        if self.widget.img_autoscale_btn.isChecked():
            self.widget.img_widget.auto_level()

    def img_dock_btn_clicked(self):
        self.img_docked = not self.img_docked
        self.widget.dock_img(self.img_docked)

    def show_background_subtracted_img_btn_clicked(self):
        if self.widget.img_mode_btn.text() == 'Cake':
            self.plot_img()
        else:
            self.widget.integration_image_widget.show_background_subtracted_img_btn.setChecked(False)

    def _update_cake_mouse_click_pos(self):
        if not self.model.calibration_model.is_calibrated:
            return

        tth = self.model.clicked_tth
        azi = self.model.clicked_azi

        cake_tth = self.model.cake_tth

        x_pos = get_partial_index(cake_tth, tth)
        if x_pos is None:
            return

        x_pos = x_pos + 0.5
        shift_amount = self.widget.cake_shift_azimuth_sl.value()
        y_pos = (get_partial_index(self.model.cake_azi, azi) + 0.5 + shift_amount) % len(self.model.cake_azi)
        self.widget.cake_widget.set_mouse_click_position(x_pos, y_pos)

    def _update_image_line_pos(self):
        if not self.model.calibration_model.is_calibrated:
            return
        self.set_image_line_position(self.model.clicked_tth)

    def _update_image_mouse_click_pos(self):
        if not self.model.calibration_model.is_calibrated:
            return

        tth = np.deg2rad(self.model.clicked_tth)
        azi = np.deg2rad(self.model.clicked_azi)

        new_pos = self.model.calibration_model.get_pixel_ind(tth, azi)
        if len(new_pos) == 0:
            self.widget.img_widget.mouse_click_item.hide()
        else:
            x_ind, y_ind = new_pos
            self.widget.img_widget.set_mouse_click_position(y_ind + 0.5, x_ind + 0.5)
            self.widget.img_widget.mouse_click_item.show()

    def update_cake_axes_range(self):
        if self.model.current_configuration.auto_integrate_cake:
            self.update_cake_azimuth_axis()
            self.update_cake_x_axis()

    def update_cake_azimuth_axis(self):
        img_view_rect = self.widget.integration_image_widget.cake_view.img_view_rect()
        img_bounding_rect = self.widget.integration_image_widget.cake_view.img_bounding_rect()
        shift_amount = self.widget.cake_shift_azimuth_sl.value()
        cake_azi = self.model.cake_azi - shift_amount * np.mean(np.diff(self.model.cake_azi))
        if img_bounding_rect.height() == 0:
            return

        height = img_view_rect.height()
        bottom = img_view_rect.top()
        v_scale = (cake_azi[-1] - cake_azi[0]) / img_bounding_rect.height()
        v_shift = np.min(cake_azi[0])
        min_azi = v_scale * bottom + v_shift
        max_azi = v_scale * (bottom + height) + v_shift

        self.widget.integration_image_widget.cake_view.left_axis_cake.setRange(min_azi, max_azi)

    def update_cake_x_axis(self):
        if self.model.cake_tth is None:
            return

        img_view_rect = self.widget.integration_image_widget.cake_view.img_view_rect()
        img_bounding_rect = self.widget.integration_image_widget.cake_view.img_bounding_rect()

        cake_tth = self.model.cake_tth
        if img_bounding_rect.width() == 0:
            return

        width = img_view_rect.width()
        left = img_view_rect.left()
        h_scale = (np.max(cake_tth) - np.min(cake_tth)) / img_bounding_rect.width()
        h_shift = np.min(cake_tth)
        min_tth = h_scale * left + h_shift
        max_tth = h_scale * (left + width) + h_shift

        if self.model.current_configuration.integration_unit == '2th_deg':
            self.widget.integration_image_widget.cake_view.bottom_axis_cake.setRange(min_tth, max_tth)
        elif self.model.current_configuration.integration_unit == 'q_A^-1':
            self.widget.integration_image_widget.cake_view.bottom_axis_cake.setRange(
                self.convert_x_value(min_tth, '2th_deg', 'q_A^-1'),
                self.convert_x_value(max_tth, '2th_deg', 'q_A^-1'))

    def set_cake_axis_to_2th(self):
        self.widget.integration_image_widget.cake_view.bottom_axis_cake.setLabel(u'2θ', u'°')
        self.update_cake_x_axis()

    def set_cake_axis_to_q(self):
        self.widget.integration_image_widget.cake_view.bottom_axis_cake.setLabel('Q', 'A<sup>-1</sup>')
        self.update_cake_x_axis()

    def show_img_mouse_position(self, x, y):
        if self.widget.img_mode == 'Cake':
            img_data = self.widget.cake_widget.img_data
        else:
            img_data = self.widget.img_widget.img_data
        img_shape = img_data.shape

        if 0 < x < img_shape[1] - 1 and 0 < y < img_shape[0] - 1:
            self.update_mouse_position_labels(x, y, img_data[int(np.floor(y)), int(np.floor(x))])
        else:
            self.update_mouse_position_labels(x, y, None)

        if 0.5 < x < img_shape[1] - 0.5 and 0.5 < y < img_shape[0] - 0.5:
            if self.model.calibration_model.is_calibrated:
                x_temp = x
                x = np.array([y])
                y = np.array([x_temp])
                if self.widget.img_mode == 'Cake':
                    tth = get_partial_value(self.model.cake_tth, y - 0.5)
                    shift_amount = self.widget.cake_shift_azimuth_sl.value()
                    cake_azi = self.model.cake_azi - shift_amount * np.mean(np.diff(self.model.cake_azi))
                    azi = get_partial_value(cake_azi, x - 0.5)
                    q_value = self.convert_x_value(tth, '2th_deg', 'q_A^-1')
                else:
                    tth = self.model.calibration_model.get_two_theta_img(x, y)
                    tth = tth / np.pi * 180.0
                    q_value = self.convert_x_value(tth, '2th_deg', 'q_A^-1')
                    azi = self.model.calibration_model.get_azi_img(x, y) / np.pi * 180

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
        if self.widget.img_mode == 'Cake':
            img_data = self.widget.cake_widget.img_data
        else:
            img_data = self.widget.img_widget.img_data

        if 0 < x < img_data.shape[1] - 1 and 0 < y < img_data.shape[0] - 1:
            intensity = img_data[int(np.floor(y)), int(np.floor(x))]
        else:
            intensity = None
        self.update_mouse_click_position_labels(x, y, intensity)

        if self.model.calibration_model.is_calibrated:
            x, y = y, x  # the indices are reversed for the img_array
            if self.widget.img_mode == 'Cake':  # cake mode
                # get clicked tth and azimuth
                cake_shape = self.model.cake_data.shape
                if x < 0 or y < 0 or x > cake_shape[0] - 1 or y > cake_shape[1] - 1:
                    return
                tth = get_partial_value(self.model.cake_tth, y - 0.5)
                shift_amount = self.widget.cake_shift_azimuth_sl.value()
                azi = get_partial_value(np.roll(self.model.cake_azi, shift_amount), x - 0.5)
                self.widget.cake_widget.activate_vertical_line()

            elif self.widget.img_mode == 'Image':  # image mode
                img_shape = self.model.img_data.shape
                if x < 0 or y < 0 or x > img_shape[0] - 1 or y > img_shape[1] - 1:
                    return
                x = np.array([x])
                y = np.array([y])
                tth = np.rad2deg(self.model.calibration_model.get_two_theta_img(x, y))
                azi = np.rad2deg(self.model.calibration_model.get_azi_img(x, y))
            else:  # in the case of whatever
                tth = 0
                azi = 0

            self.clicked_tth = tth  # in degree
            self.clicked_azi = azi  # in degree

            if self.widget.img_mode == 'Cake':
                self.plot_cake_integral()

            self.model.clicked_tth_changed.emit(tth)
            self.model.clicked_azi_changed.emit(azi)

        self.widget.click_tth_lbl.setText(self.widget.mouse_tth_lbl.text())
        self.widget.click_d_lbl.setText(self.widget.mouse_d_lbl.text())
        self.widget.click_q_lbl.setText(self.widget.mouse_q_lbl.text())
        self.widget.click_azi_lbl.setText(self.widget.mouse_azi_lbl.text())
        self.widget.img_widget_click_tth_lbl.setText(self.widget.mouse_tth_lbl.text())
        self.widget.img_widget_click_d_lbl.setText(self.widget.mouse_d_lbl.text())
        self.widget.img_widget_click_q_lbl.setText(self.widget.mouse_q_lbl.text())
        self.widget.img_widget_click_azi_lbl.setText(self.widget.mouse_azi_lbl.text())

    def update_mouse_position_labels(self, x, y, intensity):
        x_pos_string = 'X:  %4d' % x
        y_pos_string = 'Y:  %4d' % y

        try:
            int_string = 'I:   %5d' % intensity
        except (ValueError, TypeError, OverflowError):
            int_string = 'I:'

        self.widget.mouse_x_lbl.setText(x_pos_string)
        self.widget.mouse_y_lbl.setText(y_pos_string)
        self.widget.mouse_int_lbl.setText(int_string)

    def update_mouse_click_position_labels(self, x, y, intensity):
        self.update_mouse_position_labels(x, y, intensity)

        self.widget.click_x_lbl.setText(self.widget.mouse_x_lbl.text())
        self.widget.click_y_lbl.setText(self.widget.mouse_y_lbl.text())
        self.widget.click_int_lbl.setText(self.widget.mouse_int_lbl.text())

    def set_cake_line_position(self, tth):
        if self.model.cake_tth is None:
            return

        pos = get_partial_index(self.model.cake_tth, tth)
        if pos is None:
            self.widget.cake_widget.plot_cake_integral(np.array([]), np.array([]))
            self.widget.cake_widget.deactivate_vertical_line()
            return

        self.widget.cake_widget.vertical_line.setValue(pos + 0.5)
        self.widget.cake_widget.activate_vertical_line()
        self.plot_cake_integral(tth)

    def set_image_line_position(self, tth):
        if not self.model.calibration_model.is_calibrated:
            self.widget.img_widget.deactivate_circle_scatter()
            return
        self.widget.img_widget.activate_circle_scatter()
        self.widget.img_widget.set_circle_line(self.model.calibration_model.get_two_theta_array(), np.deg2rad(tth))

    def set_iteration_mode_number(self):
        self.model.img_model.set_file_iteration_mode('number')

    def set_iteration_mode_time(self):
        self.model.img_model.set_file_iteration_mode('time')

    def select_source(self, source):
        self.model.img_model.select_source(source)

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
            self.model.working_directories['calibration'],
            '*.poni')
        if filename != '':
            self.model.working_directories['calibration'] = os.path.dirname(filename)
            self.model.calibration_model.load(filename)
            self.widget.calibration_lbl.setText(
                self.model.calibration_model.calibration_name)
            self.widget.wavelength_lbl.setText('{:.4f}'.format(self.model.calibration_model.wavelength * 1e10) + ' A')
            self.model.img_model.img_changed.emit()

    def set_wavelength(self):
        wavelength, ok = QtWidgets.QInputDialog.getText(self.widget, 'Set Wavelength', 'Wavelength in Angstroms:')
        if ok:
            self.model.calibration_model.pattern_geometry.wavelength = float(wavelength) * 1e-10
            self.widget.wavelength_lbl.setText('{:.4f}'.format(self.model.calibration_model.wavelength * 1e10) + ' A')
            self.model.img_model.img_changed.emit()

    def auto_process_cb_click(self):
        self.model.img_model.autoprocess = self.widget.autoprocess_cb.isChecked()

    def save_img(self, filename=None):
        if not filename:
            img_filename = os.path.splitext(os.path.basename(self.model.img_model.filename))[0]
            filename = save_file_dialog(self.widget, "Save Image.",
                                        os.path.join(self.model.working_directories['image'],
                                                     img_filename + '.png'),
                                        ('Image (*.png);;Data (*.tiff);;Text (*.txt)'))

        if filename != '':
            if filename.endswith('.png'):
                if self.widget.img_mode == 'Cake':
                    self.widget.cake_widget.deactivate_vertical_line()
                    self.widget.cake_widget.deactivate_mouse_click_item()
                    QtWidgets.QApplication.processEvents()
                    self.widget.cake_widget.save_img(filename)
                    self.widget.cake_widget.activate_vertical_line()
                    self.widget.cake_widget.activate_mouse_click_item()
                elif self.widget.img_mode == 'Image':
                    self.widget.img_widget.deactivate_circle_scatter()
                    self.widget.img_widget.deactivate_roi()
                    QtWidgets.QApplication.processEvents()
                    self.widget.img_widget.save_img(filename)
                    self.widget.img_widget.activate_circle_scatter()
                    if self.roi_active:
                        self.widget.img_widget.activate_roi()

            elif filename.endswith('.tiff') or filename.endswith('.tif'):
                if self.widget.img_mode == 'Image':
                    im_array = np.int32(self.model.img_data)
                elif self.widget.img_mode == 'Cake':
                    im_array = np.int32(self.model.cake_data)
                im_array = np.flipud(im_array)
                im = Image.fromarray(im_array)
                im.save(filename)
            elif filename.endswith('.txt') or filename.endswith('.csv'):
                if self.widget.img_mode == 'Image':
                    return
                elif self.widget.img_mode == 'Cake':  # saving cake data as a text file for export.
                    with open(filename, 'w') as out_file:  # this is done in an odd and slow way because the headers
                        # should be floats and the data itself int.
                        cake_tth = np.insert(self.model.cake_tth, 0, 0)
                        np.savetxt(out_file, cake_tth[None], fmt='%6.3f')
                        for azi, row in zip(self.model.cake_azi, self.model.cake_data):
                            row_str = " ".join(["{:6.0f}".format(el) for el in row])
                            out_file.write("{:6.2f}".format(azi) + row_str + '\n')

    def update_gui_from_configuration(self):
        self.widget.img_mask_btn.setChecked(int(self.model.use_mask))
        self.widget.mask_transparent_cb.setChecked(bool(self.model.transparent_mask))
        self.widget.autoprocess_cb.setChecked(bool(self.model.img_model.autoprocess))
        self.widget.calibration_lbl.setText(self.model.calibration_model.calibration_name)

        self.update_img_control_widget()
        self.update_mask_mode()
        self.update_roi_in_gui()

        if self.model.current_configuration.auto_integrate_cake and self.widget.img_mode == 'Image':
            self.activate_cake_mode()
        elif not self.model.current_configuration.auto_integrate_cake and self.widget.img_mode == 'Cake':
            self.activate_image_mode()
        elif self.model.current_configuration.auto_integrate_cake and self.widget.img_mode == 'Cake':
            self.set_cake_line_position(self.model.clicked_tth)
            self._update_cake_mouse_click_pos()
        elif not self.model.current_configuration.auto_integrate_cake and self.widget.img_mode == 'Image':
            self._update_image_line_pos()
            self._update_image_mouse_click_pos()

    def change_view_btn_clicked(self):
        if self.view_mode == 'alternative':
            self.change_view_to_normal()
        elif self.view_mode == 'normal':
            self.change_view_to_alternative()

    def change_view_to_normal(self):
        if self.view_mode == 'normal':
            return
        self.vertical_splitter_alternative_state = self.widget.vertical_splitter.saveState()
        self.horizontal_splitter_alternative_state = self.widget.horizontal_splitter.saveState()
        self.widget.vertical_splitter.addWidget(self.widget.integration_pattern_widget)

        self.widget.integration_control_widget.setOrientation(QtCore.Qt.Horizontal)

        if self.vertical_splitter_normal_state:
            self.widget.vertical_splitter.restoreState(self.vertical_splitter_normal_state)
        if self.horizontal_splitter_normal_state:
            self.widget.horizontal_splitter.restoreState(self.horizontal_splitter_normal_state)

        self.widget.img_widget.set_orientation("horizontal")
        self.view_mode = 'normal'

    def change_view_to_alternative(self):
        if self.view_mode == 'alternative':
            return

        self.vertical_splitter_normal_state = self.widget.vertical_splitter.saveState()
        self.horizontal_splitter_normal_state = self.widget.horizontal_splitter.saveState()

        self.widget.vertical_splitter_left.insertWidget(0, self.widget.integration_pattern_widget)

        self.widget.integration_control_widget.setOrientation(QtCore.Qt.Vertical)

        if self.vertical_splitter_alternative_state:
            self.widget.vertical_splitter.restoreState(self.vertical_splitter_alternative_state)
        if self.horizontal_splitter_alternative_state:
            self.widget.horizontal_splitter.restoreState(self.horizontal_splitter_alternative_state)

        self.widget.img_widget.set_orientation("vertical")
        self.view_mode = 'alternative'
