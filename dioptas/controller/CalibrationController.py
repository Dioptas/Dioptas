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
from qtpy import QtWidgets, QtCore

import numpy as np

from ..widgets.UtilityWidgets import open_file_dialog, save_file_dialog
from .. import calibrants_path

# imports for type hinting in PyCharm -- DO NOT DELETE
from ..widgets.CalibrationWidget import CalibrationWidget
from ..widgets.UtilityWidgets import open_file_dialog
from ..model.DioptasModel import DioptasModel
from ..model.CalibrationModel import NotEnoughSpacingsInCalibrant, get_available_detectors, DetectorModes


class CalibrationController(object):
    """
    CalibrationController handles all the interaction between the CalibrationView and the CalibrationData class
    """

    def __init__(self, widget, dioptas_model):
        """Manages the connection between the calibration GUI and data

        :param widget: Gives the Calibration Widget
        :type widget: CalibrationWidget

        :param dioptas_model: Reference to DioptasModel Object
        :type dioptas_model: DioptasModel

        """
        self.widget = widget
        self.model = dioptas_model

        self.widget.set_start_values(self.model.calibration_model.start_values)
        self._first_plot = True
        self.create_signals()
        self.plot_image()
        self.load_detectors_list()
        self.load_calibrants_list()

    def create_signals(self):
        """
        Connects the GUI signals to the appropriate Controller methods.
        """
        self.model.img_changed.connect(self.plot_image)
        self.model.configuration_selected.connect(self.update_calibration_parameter_in_view)
        self.model.configuration_selected.connect(self.update_detector_parameters_in_view)
        self.model.calibration_model.detector_reset.connect(self.update_detector_parameters_in_view)
        self.model.calibration_model.detector_reset.connect(self.show_detector_reset_message_box)

        self.create_transformation_signals()
        self.create_update_signals()
        self.create_mouse_signals()

        self.widget.detectors_cb.currentIndexChanged.connect(self.load_detector)
        self.widget.detector_load_btn.clicked.connect(self.load_detector_from_file)
        self.widget.detector_reset_btn.clicked.connect(self.reset_detector_from_file)

        self.widget.calibrant_cb.currentIndexChanged.connect(self.load_calibrant)
        self.widget.load_img_btn.clicked.connect(self.load_img)
        self.widget.load_next_img_btn.clicked.connect(self.load_next_img)
        self.widget.load_previous_img_btn.clicked.connect(self.load_previous_img)
        self.widget.filename_txt.editingFinished.connect(self.update_filename_txt)

        self.widget.save_calibration_btn.clicked.connect(self.save_calibration)
        self.widget.load_calibration_btn.clicked.connect(self.load_calibration)
        self.widget.calibrate_btn.clicked.connect(self.calibrate)
        self.widget.refine_btn.clicked.connect(self.refine)

        self.widget.clear_peaks_btn.clicked.connect(self.clear_peaks)
        self.widget.undo_peaks_btn.clicked.connect(self.undo_peaks_btn_clicked)

        self.widget.load_spline_btn.clicked.connect(self.load_spline_btn_click)
        self.widget.spline_reset_btn.clicked.connect(self.reset_spline_btn_click)

        self.widget.f2_wavelength_cb.stateChanged.connect(self.wavelength_cb_changed)
        self.widget.pf_wavelength_cb.stateChanged.connect(self.wavelength_cb_changed)
        self.widget.sv_wavelength_cb.stateChanged.connect(self.wavelength_cb_changed)

        self.widget.f2_distance_cb.stateChanged.connect(self.distance_cb_changed)
        self.widget.pf_distance_cb.stateChanged.connect(self.distance_cb_changed)
        self.widget.sv_distance_cb.stateChanged.connect(self.distance_cb_changed)

        self.widget.use_mask_cb.stateChanged.connect(self.plot_mask)
        self.widget.mask_transparent_cb.stateChanged.connect(self.mask_transparent_status_changed)

    def create_transformation_signals(self):
        """
        Connects all the rotation GUI controls.
        """
        self.widget.rotate_m90_btn.clicked.connect(self.rotate_m90_btn_clicked)
        self.widget.rotate_p90_btn.clicked.connect(self.rotate_p90_btn_clicked)
        self.widget.invert_horizontal_btn.clicked.connect(self.invert_horizontal_btn_clicked)
        self.widget.invert_vertical_btn.clicked.connect(self.invert_vertical_btn_clicked)
        self.widget.reset_transformations_btn.clicked.connect(self.reset_transformations_btn_clicked)

    def rotate_m90_btn_clicked(self):
        self.model.calibration_model.rotate_detector_m90()
        self.model.img_model.rotate_img_m90()
        self.clear_peaks()

    def rotate_p90_btn_clicked(self):
        self.model.calibration_model.rotate_detector_p90()
        self.model.img_model.rotate_img_p90()
        self.clear_peaks()

    def invert_horizontal_btn_clicked(self):
        self.model.calibration_model.flip_detector_horizontally()
        self.model.img_model.flip_img_horizontally()
        self.clear_peaks()

    def invert_vertical_btn_clicked(self):
        self.model.calibration_model.flip_detector_vertically()
        self.model.img_model.flip_img_vertically()
        self.clear_peaks()

    def reset_transformations_btn_clicked(self):
        self.model.calibration_model.reset_transformations()
        self.model.img_model.reset_transformations()
        self.clear_peaks()

    def create_update_signals(self):
        """
        Connects all the txt box signals. Which specifically are the update buttons here.
        """
        self.widget.f2_update_btn.clicked.connect(self.update_f2_btn_click)
        self.widget.pf_update_btn.clicked.connect(self.update_pyFAI_btn_click)

    def create_mouse_signals(self):
        """
        Creates the mouse_move connections to show the current position of the mouse pointer.
        """
        self.widget.img_widget.mouse_moved.connect(self.update_img_mouse_position_lbl)
        self.widget.cake_widget.mouse_moved.connect(self.update_cake_mouse_position_lbl)
        self.widget.pattern_widget.mouse_moved.connect(self.update_pattern_mouse_position_lbl)
        self.widget.img_widget.mouse_left_clicked.connect(self.search_peaks)

    def update_f2_btn_click(self):
        """
        Takes all parameters inserted into the fit2d txt-fields and updates the current calibration accordingly.
        """
        fit2d_parameter = self.widget.get_fit2d_parameter()
        self.model.calibration_model.set_fit2d(fit2d_parameter)
        self.update_all()

    def update_pyFAI_btn_click(self):
        """
        Takes all parameters inserted into the fit2d txt-fields and updates the current calibration accordingly.
        """
        pyFAI_parameter = self.widget.get_pyFAI_parameter()
        self.model.calibration_model.set_pyFAI(pyFAI_parameter)
        self.update_all()

    def load_img(self):
        """
        Loads an image file.
        """
        filename = open_file_dialog(self.widget, caption="Load Calibration Image",
                                    directory=self.model.working_directories['image'],
                                    )

        if filename != '':
            self.model.working_directories['image'] = os.path.dirname(filename)
            self.model.img_model.load(filename)

    def load_next_img(self):
        self.model.img_model.load_next_file()

    def load_previous_img(self):
        self.model.img_model.load_previous_file()

    def update_filename_txt(self):
        """
        Updates the filename in the GUI corresponding to the filename in img_data
        """
        current_filename = os.path.basename(self.model.img_model.filename)
        current_directory = os.path.dirname(self.model.img_model.filename)
        new_filename = str(self.widget.filename_txt.text())
        if current_filename == new_filename:
            return
        if os.path.exists(os.path.join(current_directory, new_filename)):
            try:
                self.load_img(os.path.join(current_directory, new_filename))
            except TypeError:
                self.widget.filename_txt.setText(current_filename)
        else:
            self.widget.filename_txt.setText(current_filename)

    def load_detectors_list(self):
        self._detectors_list, _ = get_available_detectors()
        self._detectors_list.insert(0, 'Custom')
        self.widget.detectors_cb.blockSignals(True)
        self.widget.detectors_cb.clear()
        self.widget.detectors_cb.addItems(self._detectors_list)
        self.widget.detectors_cb.insertSeparator(1)
        self.widget.detectors_cb.insertSeparator(1)
        self.widget.detectors_cb.blockSignals(False)

    def load_detector(self, ind):
        """
        Loads the selected Detector from the Detector combobox into the calibration model. This blackout disable the
        controls for pixel widths, unless "custom" (the first element) is selected.
        """
        if ind != 0:
            self.model.calibration_model.load_detector(self.widget.detectors_cb.currentText())
            emit_img_changed = self.model.calibration_model.detector.shape == self.model.img_model.img_data.shape
            # makes no sense to have transformations when loading a detector, however only emitting that the img changed
            # if detector and image have same size, otherwise the user should have the possibility to load an image
            # without error
            self.model.img_model.reset_transformations(emit_img_changed)
        else:
            self.model.calibration_model.reset_detector()
        self.update_detector_parameters_in_view()

    def load_detector_from_file(self):
        filename = open_file_dialog(self.widget, caption="Load Nexus Detector",
                                    directory=self.model.working_directories['image'],
                                    filter='*.h5')

        if filename != '':
            self.model.calibration_model.load_detector_from_file(filename)
            self.update_detector_parameters_in_view()

    def reset_detector_from_file(self):
        self.model.calibration_model.reset_detector()
        self.model.img_model.reset_transformations()
        self.update_detector_parameters_in_view()

    def _update_pixel_size_in_gui(self):
        self.widget.set_pixel_size(self.model.calibration_model.orig_pixel2,
                                   self.model.calibration_model.orig_pixel1)

    def _update_spline_in_gui(self):
        if self.model.calibration_model.detector.splineFile is not None:
            self.widget.spline_filename_txt.setText(os.path.basename(self.model.calibration_model.detector.splineFile))
        elif not self.model.calibration_model.detector.uniform_pixel:
            self.widget.spline_filename_txt.setText('from Detector')
        else:
            self.widget.spline_filename_txt.setText('None')

    def load_calibrants_list(self):
        """
        Loads all calibrants from the ExampleData/calibrants directory into the calibrants combobox. And loads number 7.
        """
        self._calibrants_file_list = []
        self._calibrants_file_names_list = []
        for file in os.listdir(calibrants_path):
            if file.endswith('.D'):
                self._calibrants_file_list.append(file)
                self._calibrants_file_names_list.append(file.split('.')[:-1][0])
        self._calibrants_file_list.sort()
        self._calibrants_file_names_list.sort()
        self.widget.calibrant_cb.blockSignals(True)
        self.widget.calibrant_cb.clear()
        self.widget.calibrant_cb.addItems(self._calibrants_file_names_list)
        self.widget.calibrant_cb.blockSignals(False)
        self.widget.calibrant_cb.setCurrentIndex(self._calibrants_file_names_list.index('LaB6'))  # to LaB6
        self.load_calibrant()

    def load_calibrant(self, wavelength_from='start_values'):
        """
        Loads the selected calibrant in the calibrant combobox into the calibration data.
        :param wavelength_from: determines which wavelength to use possible values: "start_values", "pyFAI"
        """
        current_index = self.widget.calibrant_cb.currentIndex()
        filename = os.path.join(self.model.calibration_model._calibrants_working_dir,
                                self._calibrants_file_list[current_index])
        self.model.calibration_model.set_calibrant(filename)

        if wavelength_from == 'start_values':
            start_values = self.widget.get_start_values()
            wavelength = start_values['wavelength']
        elif wavelength_from == 'pyFAI':
            pyFAI_parameter, _ = self.model.calibration_model.get_calibration_parameter()
            if pyFAI_parameter['wavelength'] != 0:
                wavelength = pyFAI_parameter['wavelength']
            else:
                start_values = self.widget.get_start_values()
                wavelength = start_values['wavelength']
        else:
            start_values = self.widget.get_start_values()
            wavelength = start_values['wavelength']

        self.model.calibration_model.calibrant.setWavelength_change2th(wavelength)
        try:
            integration_unit = self.model.current_configuration.integration_unit
        except:
            integration_unit = '2th_deg'

        calibrant_line_positions = self.convert_x_value(
            np.array(self.model.calibration_model.calibrant.get_2th()) / np.pi * 180, '2th_deg', integration_unit,
            wavelength)
        # filter them to only show the ones visible with the current pattern
        if len(self.model.pattern.x) > 0:
            pattern_min = np.min(self.model.pattern.x)
            pattern_max = np.max(self.model.pattern.x)
            calibrant_line_positions = calibrant_line_positions[calibrant_line_positions > pattern_min]
            calibrant_line_positions = calibrant_line_positions[calibrant_line_positions < pattern_max]
            self.widget.pattern_widget.plot_vertical_lines(positions=calibrant_line_positions,
                                                           name=self._calibrants_file_names_list[current_index])

    def set_calibrant(self, index):
        """
        :param index:
            index of a specific calibrant in the calibrant combobox
        """
        self.widget.calibrant_cb.setCurrentIndex(index)
        self.load_calibrant()

    def plot_image(self):
        """
        Plots the current image loaded in img_data and autoscales the intensity.
        :return:
        """
        self.widget.img_widget.plot_image(self.model.img_data, True)
        self.widget.set_img_filename(self.model.img_model.filename)

    def search_peaks(self, x, y):
        """
        Searches peaks around a specific points (x,y) in the current image file. The algorithm for searching
        (either automatic or single peaksearch) is set in the GUI.
        :param x:
            x-Position for the search.
        :param y:
            y-Position for the search
        """
        x, y = y, x  # indeces for the img array are transposed compared to the mouse position

        # convert pixel coord into pixel index
        x, y = int(x), int(y)

        # filter events outside the image
        shape = self.model.img_model.img_data.shape
        if not (0 <= x < shape[0]):
            return
        if not (0 <= y < shape[1]):
            return

        peak_ind = self.widget.peak_num_sb.value()
        if self.widget.automatic_peak_search_rb.isChecked():
            points = self.model.calibration_model.find_peaks_automatic(x, y, peak_ind - 1)
        else:
            search_size = int(self.widget.search_size_sb.value())
            points = self.model.calibration_model.find_peak(x, y, search_size, peak_ind - 1)
        if len(points):
            self.plot_points(points)
            if self.widget.automatic_peak_num_inc_cb.checkState():
                self.widget.peak_num_sb.setValue(peak_ind + 1)

    def plot_points(self, points=None):
        """
        Plots points into the image view.
        :param points:
            list of points, whereby a point is a [x,y] element. If it is none it will plot the points stored in the
            calibration_data
        """
        if points is None:
            try:
                points = self.model.calibration_model.get_point_array()
            except IndexError:
                points = []
        if len(points):
            self.widget.img_widget.add_scatter_data(points[:, 0] + 0.5, points[:, 1] + 0.5)

    def clear_peaks(self):
        """
        Deletes all points/peaks in the calibration_data and in the GUI.
        """
        self.model.calibration_model.clear_peaks()
        self.widget.img_widget.clear_scatter_plot()
        self.widget.peak_num_sb.setValue(1)

    def undo_peaks_btn_clicked(self):
        """
        undoes clicked peaks
        """
        num_points = self.model.calibration_model.remove_last_peak()
        self.widget.img_widget.remove_last_scatter_points(num_points)
        if self.widget.automatic_peak_num_inc_cb.isChecked():
            self.widget.peak_num_sb.setValue(self.widget.peak_num_sb.value() - 1)

    def load_spline_btn_click(self):
        filename = open_file_dialog(self.widget, caption="Load Distortion Spline File",
                                    directory=self.model.working_directories['image'],
                                    filter='*.spline')

        if filename != '':
            self.model.calibration_model.load_distortion(filename)
            self._update_spline_in_gui()
            self.widget.spline_reset_btn.setEnabled(True)

    def reset_spline_btn_click(self):
        self.model.calibration_model.reset_distortion_correction()
        self.widget.spline_filename_txt.setText('None')
        self.widget.spline_reset_btn.setEnabled(False)

    def wavelength_cb_changed(self, value):
        """
        Sets the fit_wavelength parameter in the calibration data according to the GUI state.
        """
        self.widget.f2_wavelength_cb.blockSignals(True)
        self.widget.pf_wavelength_cb.blockSignals(True)
        self.widget.sv_wavelength_cb.blockSignals(True)

        self.widget.f2_wavelength_cb.setChecked(value)
        self.widget.pf_wavelength_cb.setChecked(value)
        self.widget.sv_wavelength_cb.setChecked(value)

        self.widget.f2_wavelength_cb.blockSignals(False)
        self.widget.pf_wavelength_cb.blockSignals(False)
        self.widget.sv_wavelength_cb.blockSignals(False)

        self.model.calibration_model.fit_wavelength = value

    def distance_cb_changed(self, value):
        """
        Sets the fit_distance parameter int he calibration model according to the GUI state
        """
        self.widget.f2_distance_cb.blockSignals(True)
        self.widget.pf_distance_cb.blockSignals(True)
        self.widget.sv_distance_cb.blockSignals(True)

        self.widget.f2_distance_cb.setChecked(value)
        self.widget.pf_distance_cb.setChecked(value)
        self.widget.sv_distance_cb.setChecked(value)

        self.widget.f2_distance_cb.blockSignals(False)
        self.widget.pf_distance_cb.blockSignals(False)
        self.widget.sv_distance_cb.blockSignals(False)

        self.model.calibration_model.fit_distance = value

    def update_fixed_values(self):
        self.model.calibration_model.set_fixed_values(self.widget.get_fixed_values())

    def calibrate(self):
        """
        Performs calibration based on the previously inputted/searched peaks and start values.
        """
        self.load_calibrant()  # load the right calibration file...
        self.model.calibration_model.set_start_values(self.widget.get_start_values())
        self.model.calibration_model.set_pixel_size(self.widget.get_pixel_size())
        self.model.calibration_model.set_fixed_values(self.widget.get_fixed_values())
        progress_dialog = self.create_progress_dialog('Calibrating.', '', 0, show_cancel_btn=False)
        self.model.calibration_model.calibrate()

        progress_dialog.close()

        if self.widget.options_automatic_refinement_cb.isChecked():
            self.automatic_refinement()
        else:
            self.update_all()
        self.update_calibration_parameter_in_view()

    def refine(self):
        self.model.calibration_model.set_fixed_values(self.widget.get_fixed_values())

        if self.widget.options_automatic_refinement_cb.isChecked():
            self.automatic_refinement()
        else:
            progress_dialog = self.create_progress_dialog('Refining.', '', 0, show_cancel_btn=False)
            self.model.calibration_model.refine()
            progress_dialog.close()
            self.update_all()

        self.update_calibration_parameter_in_view()

    def create_progress_dialog(self, text_str, abort_str, end_value, show_cancel_btn=True):
        """ Creates a Progress Bar Dialog.
        :param text_str:  Main message string
        :param abort_str:  Text on the abort button
        :param end_value:  Number of steps for which the progressbar is being used
        :param show_cancel_btn: Whether the cancel button should be shown.
        :return: ProgressDialog reference which is already shown in the interface
        :rtype: QtWidgets.ProgressDialog
        """
        progress_dialog = QtWidgets.QProgressDialog(text_str, abort_str, 0, end_value,
                                                    self.widget)

        progress_dialog.move(int(self.widget.tab_widget.x() + self.widget.tab_widget.size().width() / 2.0 - \
                                 progress_dialog.size().width() / 2.0),
                             int(self.widget.tab_widget.y() + self.widget.tab_widget.size().height() / 2.0 -
                                 progress_dialog.size().height() / 2.0))

        progress_dialog.setWindowTitle('   ')
        progress_dialog.setWindowModality(QtCore.Qt.WindowModal)
        progress_dialog.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        if not show_cancel_btn:
            progress_dialog.setCancelButton(None)
        progress_dialog.show()
        QtWidgets.QApplication.processEvents()
        return progress_dialog

    def automatic_refinement(self):
        """
        Refines the current calibration parameters by searching peaks in the approximate positions and subsequent
        refinement. Parameters for this search are set in the GUI.
        """

        # Basic Algorithm:
        # search peaks on first and second ring
        #   calibrate based on those two rings
        #   repeat until ring_ind = max_ind:
        #       search next ring
        #       calibrate based on all previous found points

        num_rings = self.widget.options_num_rings_sb.value()

        progress_dialog = self.create_progress_dialog("Refining Calibration.", 'Abort', num_rings)
        self.clear_peaks()
        self.load_calibrant(wavelength_from='pyFAI')  # load right calibration file

        # get options
        algorithm = str(self.widget.options_peaksearch_algorithm_cb.currentText())
        delta_tth = float(self.widget.options_delta_tth_txt.text())
        intensity_min_factor = float(self.widget.options_intensity_mean_factor_sb.value())
        intensity_max = float(self.widget.options_intensity_limit_txt.text())

        self.model.calibration_model.setup_peak_search_algorithm(algorithm)

        if self.widget.use_mask_cb.isChecked():
            mask = self.model.mask_model.get_img()
        else:
            mask = None

        self.model.calibration_model.search_peaks_on_ring(0, delta_tth, intensity_min_factor, intensity_max, mask)
        self.widget.peak_num_sb.setValue(2)
        progress_dialog.setValue(1)
        self.model.calibration_model.search_peaks_on_ring(1, delta_tth, intensity_min_factor, intensity_max, mask)
        self.widget.peak_num_sb.setValue(3)
        if len(self.model.calibration_model.points):
            self.model.calibration_model.refine()
            self.plot_points()
        else:
            print('Did not find any Points with the specified parameters for the first two rings!')

        progress_dialog.setValue(2)

        refinement_canceled = False
        for i in range(num_rings - 2):
            try:
                points = self.model.calibration_model.search_peaks_on_ring(i + 2, delta_tth, intensity_min_factor,
                                                                           intensity_max, mask)
            except NotEnoughSpacingsInCalibrant:
                QtWidgets.QMessageBox.critical(self.widget,
                                               'Not enough d-spacings!.',
                                               'The calibrant file does not contain enough d-spacings.',
                                               QtWidgets.QMessageBox.Ok)
                break
            self.widget.peak_num_sb.setValue(i + 4)
            if len(self.model.calibration_model.points):
                self.plot_points(points)
                QtWidgets.QApplication.processEvents()
                QtWidgets.QApplication.processEvents()
                self.model.calibration_model.refine()
            else:
                print('Did not find enough points with the specified parameters!')
            progress_dialog.setLabelText("Refining Calibration. \n"
                                         "Finding peaks on Ring {0}.".format(i + 3))
            progress_dialog.setValue(i + 3)
            if progress_dialog.wasCanceled():
                refinement_canceled = True
                break
        progress_dialog.close()
        del progress_dialog

        QtWidgets.QApplication.processEvents()
        if not refinement_canceled:
            self.update_all()

    def load_calibration(self):
        """
        Loads a '*.poni' file and updates the calibration data class
        """
        filename = open_file_dialog(self.widget, caption="Load calibration...",
                                    directory=self.model.working_directories['calibration'],
                                    filter='*.poni')
        if filename != '':
            self.model.working_directories['calibration'] = os.path.dirname(filename)
            self.model.calibration_model.load(filename)
            self.update_all(integrate=self.model.img_model.filename != '')

    def plot_mask(self):
        """
        Plots the mask
        """
        state = self.widget.use_mask_cb.isChecked()
        if state:
            self.widget.img_widget.plot_mask(self.model.mask_model.get_img())
        else:
            self.widget.img_widget.plot_mask(np.zeros(self.model.mask_model.get_img().shape))

    def mask_transparent_status_changed(self, state):
        """
        :param state: Boolean value whether the mask is being transparent
        :type state: bool
        """
        if state:
            self.widget.img_widget.set_mask_color([255, 0, 0, 100])
        else:
            self.widget.img_widget.set_mask_color([255, 0, 0, 255])

    def update_all(self, integrate=True):
        """
        Performs 1d and 2d integration based on the current calibration parameter set. Updates the GUI interface
        accordingly with the new diffraction pattern and cake image.
        """
        if integrate:
            progress_dialog = self.create_progress_dialog('Integrating to cake.', '',
                                                          0, show_cancel_btn=False)
            QtWidgets.QApplication.processEvents()
            self.model.current_configuration.integrate_image_2d()
            progress_dialog.setLabelText('Integrating to pattern.')
            QtWidgets.QApplication.processEvents()
            QtWidgets.QApplication.processEvents()
            self.model.current_configuration.integrate_image_1d()
            progress_dialog.close()
        self.widget.cake_widget.plot_image(self.model.cake_data, False)
        self.widget.cake_widget.auto_level()

        self.widget.pattern_widget.plot_data(*self.model.pattern.data)
        self.widget.pattern_widget.plot_vertical_lines(self.convert_x_value(np.array(
            self.model.calibration_model.calibrant.get_2th()) / np.pi * 180, '2th_deg',
                                                                            self.model.current_configuration.integration_unit,
                                                                            None))

        if self.model.current_configuration.integration_unit == '2th_deg':
            self.widget.pattern_widget.pattern_plot.setLabel('bottom', u'2θ', '°')
        elif self.model.current_configuration.integration_unit == 'q_A^-1':
            self.widget.pattern_widget.pattern_plot.setLabel('bottom', 'Q', 'A<sup>-1</sup>')
        elif self.model.current_configuration.integration_unit == 'd_A':
            self.widget.pattern_widget.pattern_plot.setLabel('bottom', 'd', 'A')

        self.widget.pattern_widget.view_box.autoRange()
        if self.widget.tab_widget.currentIndex() == 0:
            self.widget.tab_widget.setCurrentIndex(1)

        if self.widget.ToolBox.currentIndex() != 2 or \
                self.widget.ToolBox.currentIndex() != 3:
            self.widget.ToolBox.setCurrentIndex(2)
        self.update_calibration_parameter_in_view()
        self.load_calibrant('pyFAI')

    def update_calibration_parameter_in_view(self):
        """
        Reads the calibration parameter from the calibration_data object and displays them in the GUI.
        :return:
        """
        pyFAI_parameter, fit2d_parameter = self.model.calibration_model.get_calibration_parameter()
        self.widget.set_calibration_parameters(pyFAI_parameter, fit2d_parameter)
        self._update_spline_in_gui()

    def update_detector_parameters_in_view(self):
        detector_mode = self.model.calibration_model.detector_mode

        self.widget.enable_pixel_size_txt(detector_mode == DetectorModes.CUSTOM)
        self.widget.detectors_cb.setVisible(detector_mode in (DetectorModes.CUSTOM, DetectorModes.PREDEFINED))
        self.widget.detector_name_lbl.setVisible(detector_mode == DetectorModes.NEXUS)
        self.widget.detector_reset_btn.setEnabled(detector_mode == DetectorModes.NEXUS)

        if detector_mode == DetectorModes.CUSTOM:
            self.widget.detectors_cb.blockSignals(True)
            self.widget.detectors_cb.setCurrentText('Custom')
            self.widget.detectors_cb.blockSignals(False)

        if detector_mode == DetectorModes.PREDEFINED:
            self.widget.detectors_cb.blockSignals(True)
            self.widget.detectors_cb.setCurrentText(self.model.calibration_model.detector.name)
            self.widget.detectors_cb.blockSignals(False)

        if detector_mode == DetectorModes.NEXUS:
            self.widget.detector_name_lbl.setText(
                os.path.basename(self.model.calibration_model.detector.filename))

        self._update_pixel_size_in_gui()
        self._update_spline_in_gui()

    def show_detector_reset_message_box(self):
        QtWidgets.QMessageBox.critical(self.widget,
                                       'Shape mismatch.',
                                       'Image and detector definition do not have the same shape!\n' + \
                                       'The Detector has been reset.',
                                       QtWidgets.QMessageBox.Ok)

    def save_calibration(self):
        """
        Saves the current calibration in a file.
        :return:
        """

        filename = save_file_dialog(self.widget, "Save calibration...",
                                    self.model.working_directories['calibration'], '*.poni')
        if filename != '':
            self.model.working_directories['calibration'] = os.path.dirname(filename)
            if not filename.rsplit('.', 1)[-1] == 'poni':
                filename = filename + '.poni'
            self.model.calibration_model.save(filename)

    def update_img_mouse_position_lbl(self, x, y):
        """
        Displays the values of x, y (usually mouse -position) and their image intensity in the GUI.
        """
        # x, y = pos
        try:
            if x > 0 and y > 0:
                str = "x: %.1f y: %.1f I: %.0f" % (x, y, self.widget.img_widget.img_data.T[int(np.round(x)),
                                                                                           int(np.round(y))])
            else:
                str = "x: %.1f y: %.1f" % (x, y)
        except (IndexError, AttributeError):
            str = "x: %.1f y: %.1f" % (x, y)
        self.widget.pos_lbl.setText(str)

    def update_cake_mouse_position_lbl(self, x, y):
        """
        Displays the values of x, y (usually mouse -position) and their cake intensity in the GUI.
        """
        # x, y = pos
        try:
            if x > 0 and y > 0:
                str = "x: %.1f y: %.1f I: %.0f" % (x, y, self.widget.cake_widget.img_data.T[int(np.round(x)),
                                                                                            int(np.round(y))])
            else:
                str = "x: %.1f y: %.1f" % (x, y)
        except (IndexError, AttributeError):
            str = "x: %.1f y: %.1f" % (x, y)
        self.widget.pos_lbl.setText(str)

    def update_pattern_mouse_position_lbl(self, x, y):
        """
        Displays the values of x, y (pattern mouse-position) in the GUI.
        """
        # x, y = pos
        str = "x: %.1f y: %.1f" % (x, y)
        self.widget.pos_lbl.setText(str)

    def convert_x_value(self, value, previous_unit, new_unit, wavelength):
        if wavelength is None:
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
