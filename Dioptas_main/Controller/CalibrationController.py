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
from copy import copy

from PyQt4 import QtGui, QtCore

import numpy as np


class CalibrationController(object):
    """
    CalibrationController handles all the interaction between the CalibrationView and the CalibrationData class
    """

    def __init__(self, working_dir, view, img_data, mask_data, calibration_data):
        self.working_dir = working_dir
        self.view = view
        self.img_data = img_data
        self.mask_data = mask_data
        self.calibration_data = calibration_data

        self.img_data.subscribe(self.plot_image)
        self.view.set_start_values(self.calibration_data.start_values)
        self._first_plot = True
        self.create_signals()
        self.plot_image()
        self.load_calibrants_list()


    def create_signals(self):
        """
        Connects the GUI signals to the appropriate Controller methods.
        """
        self.create_transformation_signals()
        self.create_update_signals()
        self.create_mouse_signals()

        self.view.calibrant_cb.currentIndexChanged.connect(self.load_calibrant)
        self.connect_click_function(self.view.load_img_btn, self.load_img)
        self.connect_click_function(self.view.load_next_img_btn, self.load_next_img)
        self.connect_click_function(self.view.load_previous_img_btn, self.load_previous_img)
        self.view.filename_txt.editingFinished.connect(self.filename_txt_changed)

        self.connect_click_function(self.view.save_calibration_btn, self.save_calibration)
        self.connect_click_function(self.view.load_calibration_btn, self.load_calibration)
        self.connect_click_function(self.view.integrate_btn, self.calibrate)
        self.connect_click_function(self.view.refine_btn, self.refine)

        self.view.img_view.mouse_left_clicked.connect(self.search_peaks)
        self.connect_click_function(self.view.clear_peaks_btn, self.clear_peaks_btn_click)

        self.view.f2_wavelength_cb.stateChanged.connect(self.wavelength_cb_changed)
        self.view.pf_wavelength_cb.stateChanged.connect(self.wavelength_cb_changed)
        self.view.sv_wavelength_cb.stateChanged.connect(self.wavelength_cb_changed)

        self.view.f2_distance_cb.stateChanged.connect(self.distance_cb_changed)
        self.view.pf_distance_cb.stateChanged.connect(self.distance_cb_changed)
        self.view.sv_distance_cb.stateChanged.connect(self.distance_cb_changed)

        self.view.use_mask_cb.stateChanged.connect(self.use_mask_status_changed)
        self.view.mask_transparent_cb.stateChanged.connect(self.mask_transparent_status_changed)


    def create_transformation_signals(self):
        """
        Connects all the rotation GUI controls.
        """
        self.connect_click_function(self.view.rotate_m90_btn, self.img_data.rotate_img_m90)
        self.connect_click_function(self.view.rotate_m90_btn, self.clear_peaks_btn_click)
        self.connect_click_function(self.view.rotate_p90_btn, self.img_data.rotate_img_p90)
        self.connect_click_function(self.view.rotate_p90_btn, self.clear_peaks_btn_click)
        self.connect_click_function(self.view.invert_horizontal_btn, self.img_data.flip_img_horizontally)
        self.connect_click_function(self.view.invert_horizontal_btn, self.clear_peaks_btn_click)
        self.connect_click_function(self.view.invert_vertical_btn, self.img_data.flip_img_vertically)
        self.connect_click_function(self.view.invert_vertical_btn, self.clear_peaks_btn_click)
        self.connect_click_function(self.view.reset_transformations_btn, self.img_data.reset_img_transformations)
        self.connect_click_function(self.view.reset_transformations_btn, self.clear_peaks_btn_click)

    def create_update_signals(self):
        """
        Connects all the txt box signals. Which specifically are the update buttons here.
        """
        self.connect_click_function(self.view.f2_update_btn, self.update_f2_btn_click)
        self.connect_click_function(self.view.pf_update_btn, self.update_pyFAI_btn_click)

    def create_mouse_signals(self):
        """
        Creates the mouse_move connections to show the current position of the mouse pointer.
        """
        self.view.img_view.mouse_moved.connect(self.show_img_mouse_position)
        self.view.cake_view.mouse_moved.connect(self.show_cake_mouse_position)
        self.view.spectrum_view.mouse_moved.connect(self.show_spectrum_mouse_position)

    def connect_click_function(self, emitter, function):
        self.view.connect(emitter, QtCore.SIGNAL('clicked()'), function)

    def update_f2_btn_click(self):
        """
        Takes all parameters inserted into the fit2d txt-fields and updates the current calibration accordingly.
        """
        fit2d_parameter = self.view.get_fit2d_parameter()
        self.calibration_data.set_fit2d(fit2d_parameter)
        self.update_all()

    def update_pyFAI_btn_click(self):
        """
        Takes all parameters inserted into the fit2d txt-fields and updates the current calibration accordingly.
        """
        pyFAI_parameter = self.view.get_pyFAI_parameter()
        self.calibration_data.set_pyFAI(pyFAI_parameter)
        self.update_all()

    def load_img(self, filename=None):
        """
        Loads an image file.
        :param filename:
            filename of image file. If not set it will pop up a QFileDialog where the file can be chosen.
        """
        if filename is None:
            filename = str(QtGui.QFileDialog.getOpenFileName(self.view, caption="Load Calibration Image",
                                                             directory=self.working_dir['image']))

        if filename is not '':
            self.working_dir['image'] = os.path.dirname(filename)
            self.img_data.load(filename)

    def load_next_img(self):
        self.img_data.load_next_file()

    def load_previous_img(self):
        self.img_data.load_previous_file()

    def filename_txt_changed(self):
        current_filename = os.path.basename(self.img_data.filename)
        current_directory = os.path.dirname(self.img_data.filename)
        new_filename = str(self.view.filename_txt.text())
        if current_filename == new_filename:
            return
        if os.path.exists(os.path.join(current_directory, new_filename)):
            try:
                self.load_img(os.path.join(current_directory, new_filename))
            except TypeError:
                self.view.filename_txt.setText(current_filename)
        else:
            self.view.filename_txt.setText(current_filename)

    def load_calibrants_list(self):
        """
        Loads all calibrants from the ExampleData/calibrants directory into the calibrants combobox. And loads number 7.
        """
        self._calibrants_file_list = []
        self._calibrants_file_names_list = []
        for file in os.listdir(self.calibration_data._calibrants_working_dir):
            if file.endswith('.D'):
                self._calibrants_file_list.append(file)
                self._calibrants_file_names_list.append(file.split('.')[:-1][0])
        self.view.calibrant_cb.blockSignals(True)
        self.view.calibrant_cb.clear()
        self.view.calibrant_cb.addItems(self._calibrants_file_names_list)
        self.view.calibrant_cb.blockSignals(False)
        self.view.calibrant_cb.setCurrentIndex(7)  # to LaB6
        self.load_calibrant()

    def load_calibrant(self, wavelength_from='start_values'):
        """
        Loads the selected calibrant in the calibrant combobox into the calibration data.
        :param wavelength_from: determines which wavelength to use possible values: "start_values", "pyFAI"
        """
        current_index = self.view.calibrant_cb.currentIndex()
        filename = os.path.join(self.calibration_data._calibrants_working_dir,
                                self._calibrants_file_list[current_index])
        self.calibration_data.set_calibrant(filename)

        if wavelength_from == 'start_values':
            start_values = self.view.get_start_values()
            wavelength = start_values['wavelength']
        elif wavelength_from == 'pyFAI':
            pyFAI_parameter, _ = self.calibration_data.get_calibration_parameter()
            if pyFAI_parameter['wavelength'] is not 0:
                wavelength = pyFAI_parameter['wavelength']
            else:
                start_values = self.view.get_start_values()
                wavelength = start_values['wavelength']
        else:
            start_values = self.view.get_start_values()
            wavelength = start_values['wavelength']

        self.calibration_data.calibrant.setWavelength_change2th(wavelength)
        self.view.spectrum_view.plot_vertical_lines(np.array(self.calibration_data.calibrant.get_2th()) / np.pi * 180,
                                                    name=self._calibrants_file_names_list[current_index])

    def set_calibrant(self, index):
        """
        :param index:
            index of a specific calibrant in the calibrant combobox
        """
        self.view.calibrant_cb.setCurrentIndex(index)
        self.load_calibrant()

    def plot_image(self):
        """
        Plots the current image loaded in img_data and autoscales the intensity.
        :return:
        """
        self.view.img_view.plot_image(self.img_data.get_img(), True)
        self.view.img_view.auto_range()
        self.view.set_img_filename(self.img_data.filename)

    def search_peaks(self, x, y):
        """
        Searches peaks around a specific points (x,y) in the current image file. The algorithm for searching
        (either automatic or single peaksearch) is set in the GUI.
        :param x:
            x-Position for the search.
        :param y:
            y-Position for the search
        """
        peak_ind = self.view.peak_num_sb.value()
        if self.view.automatic_peak_search_rb.isChecked():
            points = self.calibration_data.find_peaks_automatic(x, y, peak_ind - 1)
        else:
            search_size = np.int(self.view.search_size_sb.value())
            points = self.calibration_data.find_peak(x, y, search_size, peak_ind - 1)
        if len(points):
            self.plot_points(points)
            if self.view.automatic_peak_num_inc_cb.checkState():
                self.view.peak_num_sb.setValue(peak_ind + 1)

    def plot_points(self, points=None):
        """
        Plots points into the image view.
        :param points:
            list of points, whereby a point is a [x,y] element. If it is none it will plot the points stored in the
            calibration_data
        """
        if points is None:
            try:
                points = self.calibration_data.get_point_array()
            except IndexError:
                points = []
        if len(points):
            self.view.img_view.add_scatter_data(points[:, 0] + 0.5, points[:, 1] + 0.5)

    def clear_peaks_btn_click(self):
        """
        Deletes all points/peaks in the calibration_data and in the gui.
        :return:
        """
        self.calibration_data.clear_peaks()
        self.view.img_view.clear_scatter_plot()
        self.view.peak_num_sb.setValue(1)

    def wavelength_cb_changed(self, value):
        """
        Sets the fit_wavelength parameter in the calibration data according to the GUI state.
        """
        self.view.f2_wavelength_cb.blockSignals(True)
        self.view.pf_wavelength_cb.blockSignals(True)
        self.view.sv_wavelength_cb.blockSignals(True)

        self.view.f2_wavelength_cb.setChecked(value)
        self.view.pf_wavelength_cb.setChecked(value)
        self.view.sv_wavelength_cb.setChecked(value)

        self.view.f2_wavelength_cb.blockSignals(False)
        self.view.pf_wavelength_cb.blockSignals(False)
        self.view.sv_wavelength_cb.blockSignals(False)

        self.calibration_data.fit_wavelength = value

    def distance_cb_changed(self, value):
        """
        Sets the fit_distance parameter int he calibration model according to the GUI state
        """
        self.view.f2_distance_cb.blockSignals(True)
        self.view.pf_distance_cb.blockSignals(True)
        self.view.sv_distance_cb.blockSignals(True)

        self.view.f2_distance_cb.setChecked(value)
        self.view.pf_distance_cb.setChecked(value)
        self.view.sv_distance_cb.setChecked(value)

        self.view.f2_distance_cb.blockSignals(False)
        self.view.pf_distance_cb.blockSignals(False)
        self.view.sv_distance_cb.blockSignals(False)

        self.calibration_data.fit_distance = value


    def calibrate(self):
        """
        Performs calibration based on the previously inputted/searched peaks and start values.
        """
        self.load_calibrant()  # load the right calibration file...
        self.calibration_data.set_start_values(self.view.get_start_values())
        progress_dialog = self.create_progress_dialog('Calibrating.', '', 0, show_cancel_btn=False)
        self.calibration_data.calibrate()

        progress_dialog.close()

        if self.view.options_automatic_refinement_cb.isChecked():
            self.refine()
        else:
            self.update_all()
        self.update_calibration_parameter_in_view()

    def create_progress_dialog(self, text_str, abort_str, end_value, show_cancel_btn=True):
        progress_dialog = QtGui.QProgressDialog(text_str, abort_str, 0, end_value,
                                                self.view)

        progress_dialog.move(self.view.tab_widget.x() + self.view.tab_widget.size().width() / 2.0 - \
                             progress_dialog.size().width() / 2.0,
                             self.view.tab_widget.y() + self.view.tab_widget.size().height() / 2.0 -
                             progress_dialog.size().height() / 2.0)

        progress_dialog.setWindowTitle('   ')
        progress_dialog.setWindowModality(QtCore.Qt.WindowModal)
        progress_dialog.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        if not show_cancel_btn:
            progress_dialog.setCancelButton(None)
        progress_dialog.show()
        QtGui.QApplication.processEvents()
        return progress_dialog

    def refine(self):
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

        num_rings = self.view.options_num_rings_sb.value()

        progress_dialog = self.create_progress_dialog("Refining Calibration.", 'Abort', num_rings)
        self.clear_peaks_btn_click()
        self.load_calibrant(wavelength_from='pyFAI')  #load right calibration file

        # get options
        algorithm = str(self.view.options_peaksearch_algorithm_cb.currentText())
        delta_tth = np.float(self.view.options_delta_tth_txt.text())
        intensity_min_factor = np.float(self.view.options_intensity_mean_factor_sb.value())
        intensity_max = np.float(self.view.options_intensity_limit_txt.text())

        self.calibration_data.setup_peak_search_algorithm(algorithm)

        if self.view.use_mask_cb.isChecked():
            mask = self.mask_data.get_img()
        else:
            mask = None

        self.calibration_data.search_peaks_on_ring(0, delta_tth, intensity_min_factor, intensity_max, mask)
        self.view.peak_num_sb.setValue(2)
        progress_dialog.setValue(1)
        self.calibration_data.search_peaks_on_ring(1, delta_tth, intensity_min_factor, intensity_max, mask)
        self.view.peak_num_sb.setValue(3)
        if len(self.calibration_data.points):
            self.calibration_data.refine()
            self.plot_points()
        else:
            print('Did not find any Points with the specified parameters for the first two rings!')

        progress_dialog.setValue(2)

        refinement_canceled = False
        for i in range(num_rings - 2):
            points = self.calibration_data.search_peaks_on_ring(i + 2, delta_tth, intensity_min_factor,
                                                                intensity_max, mask)
            self.view.peak_num_sb.setValue(i + 4)
            if len(self.calibration_data.points):
                self.plot_points(points)
                QtGui.QApplication.processEvents()
                QtGui.QApplication.processEvents()
                self.calibration_data.refine()
            else:
                print('Did not find enough points with the specified parameters!')
            progress_dialog.setLabelText("Refining Calibration. \n"
                                         "Finding peaks on Ring {}.".format(i + 3))
            progress_dialog.setValue(i + 3)
            if progress_dialog.wasCanceled():
                refinement_canceled = True
                break
        progress_dialog.close()
        del progress_dialog

        QtGui.QApplication.processEvents()
        if not refinement_canceled:
            self.update_all()

    def load_calibration(self, filename=None, update_all = True):
        """
        Loads a '*.poni' file and updates the calibration data class
        :param filename:
            filename of the calibration file
        """
        if filename is None:
            filename = str(QtGui.QFileDialog.getOpenFileName(self.view, caption="Load calibration...",
                                                             directory=self.working_dir['calibration'],
                                                             filter='*.poni'))
        if filename is not '':
            self.working_dir['calibration'] = os.path.dirname(filename)
            self.calibration_data.load(filename)
            if update_all:
                self.update_all()

    def use_mask_status_changed(self):
        self.plot_mask()

    def plot_mask(self):
        state = self.view.use_mask_cb.isChecked()
        if state:
            self.view.img_view.plot_mask(self.mask_data.get_img())
        else:
            self.view.img_view.plot_mask(np.zeros(self.mask_data.get_img().shape))

    def mask_transparent_status_changed(self, state):
        if state:
            self.view.img_view.set_color([255, 0, 0, 100])
        else:
            self.view.img_view.set_color([255, 0, 0, 255])

    def update_all(self, integrate=True):
        """
        Performs 1d and 2d integration based on the current calibration parameter set. Updates the GUI interface
        accordingly with the new diffraction pattern and cake image.
        :return:
        """
        if integrate:
            progress_dialog = self.create_progress_dialog('Integrating to cake.', '',
                                                          0, show_cancel_btn=False)
            QtGui.QApplication.processEvents()
            self.calibration_data.integrate_2d()
            progress_dialog.setLabelText('Integrating to spectrum.')
            QtGui.QApplication.processEvents()
            QtGui.QApplication.processEvents()
            self.calibration_data.integrate_1d()
            progress_dialog.close()
        self.view.cake_view.plot_image(self.calibration_data.cake_img, False)
        self.view.cake_view.auto_range()

        self.view.spectrum_view.plot_data(self.calibration_data.tth, self.calibration_data.int)
        self.view.spectrum_view.plot_vertical_lines(np.array(self.calibration_data.calibrant.get_2th()) /
                                                    np.pi * 180)
        self.view.spectrum_view.view_box.autoRange()
        if self.view.tab_widget.currentIndex() == 0:
            self.view.tab_widget.setCurrentIndex(1)

        if self.view.ToolBox.currentIndex() is not 2 or \
                        self.view.ToolBox.currentIndex() is not 3:
            self.view.ToolBox.setCurrentIndex(2)
        self.update_calibration_parameter_in_view()
        self.load_calibrant('pyFAI')

    def update_calibration_parameter_in_view(self):
        """
        Reads the calibration parameter from the calibration_data object and displays them in the GUI.
        :return:
        """
        pyFAI_parameter, fit2d_parameter = self.calibration_data.get_calibration_parameter()
        self.view.set_calibration_parameters(pyFAI_parameter, fit2d_parameter)

    def save_calibration(self, filename=None):
        """
        Saves the current calibration in a file.
        :param filename:
            Filename of the saved calibration. If 'None' a QFileDialog will open and the file will be saved with the
            *.poni ending.
        :return:
        """
        if filename is None:
            filename = str(QtGui.QFileDialog.getSaveFileName(self.view, "Save calibration...",
                                                             self.working_dir['calibration'], '*.poni'))
        if filename is not '':
            self.working_dir['calibration'] = os.path.dirname(filename)
            self.calibration_data.save(filename)

    def show_img_mouse_position(self, x, y):
        """
        Displays the values of x, y (usually mouse -position) and their image intensity in the GUI.
        """
        # x, y = pos
        try:
            if x > 0 and y > 0:
                str = "x: %.1f y: %.1f I: %.0f" % (x, y, self.view.img_view.img_data.T[np.round(x), np.round(y)])
            else:
                str = "x: %.1f y: %.1f" % (x, y)
        except (IndexError, AttributeError):
            str = "x: %.1f y: %.1f" % (x, y)
        self.view.pos_lbl.setText(str)

    def show_cake_mouse_position(self, x, y):
        """
        Displays the values of x, y (usually mouse -position) and their cake intensity in the GUI.
        """
        # x, y = pos
        try:
            if x > 0 and y > 0:
                str = "x: %.1f y: %.1f I: %.0f" % (x, y, self.view.cake_view.img_data.T[np.round(x), np.round(y)])
            else:
                str = "x: %.1f y: %.1f" % (x, y)
        except (IndexError, AttributeError):
            str = "x: %.1f y: %.1f" % (x, y)
        self.view.pos_lbl.setText(str)

    def show_spectrum_mouse_position(self, x, y):
        """
        Displays the values of x, y (spectrum mouse-position) in the GUI.
        """
        # x, y = pos
        str = "x: %.1f y: %.1f" % (x, y)
        self.view.pos_lbl.setText(str)
