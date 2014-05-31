# Py2DeX - GUI program for fast processing of 2D X-ray data
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

import sys
import os

import pyqtgraph as pg

from PyQt4 import QtGui, QtCore
from Views.CalibrationView import CalibrationView
from Data.ImgData import ImgData
from Data.CalibrationData import CalibrationData

import numpy as np


class CalibrationController(object):
    def __init__(self, working_dir, view=None, img_data=None, calibration_data=None):
        self.working_dir = working_dir
        if view == None:
            self.view = CalibrationView()
        else:
            self.view = view

        if img_data == None:
            self.data = ImgData()
        else:
            self.data = img_data

        if calibration_data == None:
            self.calibration_data = CalibrationData(self.data)
        else:
            self.calibration_data = calibration_data

        self.data.subscribe(self.plot_image)
        self.calibration_data.set_start_values(self.view.get_start_values())
        self._first_plot = True
        self.create_signals()
        self.load_calibrants_list()

        self.raise_window()

    def raise_window(self):
        self.view.show()
        self.view.setWindowState(self.view.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
        self.view.activateWindow()
        self.view.raise_()

    def create_signals(self):
        self.create_transformation_signals()
        self.create_txt_box_signals()

        self.view.calibrant_cb.currentIndexChanged.connect(self.load_calibrant)

        self.connect_click_function(self.view.load_file_btn, self.load_file)
        self.connect_click_function(self.view.save_calibration_btn, self.save_calibration)
        self.connect_click_function(self.view.load_calibration_btn, self.load_calibration)

        self.connect_click_function(self.view.integrate_btn, self.calibrate)
        self.connect_click_function(self.view.refine_btn, self.refine)

        self.view.img_view.add_left_click_observer(self.search_peaks)
        self.connect_click_function(self.view.clear_peaks_btn, self.clear_peaks_btn_click)


    def create_transformation_signals(self):
        self.connect_click_function(self.view.rotate_m90_btn, self.data.rotate_img_m90)
        self.connect_click_function(self.view.rotate_m90_btn, self.clear_peaks_btn_click)
        self.connect_click_function(self.view.rotate_p90_btn, self.data.rotate_img_p90)
        self.connect_click_function(self.view.rotate_p90_btn, self.clear_peaks_btn_click)
        self.connect_click_function(self.view.invert_horizontal_btn, self.data.flip_img_horizontally)
        self.connect_click_function(self.view.invert_horizontal_btn, self.clear_peaks_btn_click)
        self.connect_click_function(self.view.invert_vertical_btn, self.data.flip_img_vertically)
        self.connect_click_function(self.view.invert_vertical_btn, self.clear_peaks_btn_click)
        self.connect_click_function(self.view.reset_transformations_btn, self.data.reset_img_transformations)
        self.connect_click_function(self.view.reset_transformations_btn, self.clear_peaks_btn_click)
        self.view.connect(self.view.f2_wavelength_cb, QtCore.SIGNAL('clicked()'), self.wavelength_cb_changed)
        self.view.connect(self.view.pf_wavelength_cb, QtCore.SIGNAL('clicked()'), self.wavelength_cb_changed)


    def create_txt_box_signals(self):
        self.connect_click_function(self.view.f2_update_btn, self.update_f2_btn_click)
        self.connect_click_function(self.view.pf_update_btn, self.update_pyFAI_btn_click)

    def update_f2_btn_click(self):
        fit2d_parameter = self.view.get_fit2d_parameter()
        self.calibration_data.geometry.setFit2D(directDist=fit2d_parameter['directDist'],
                                                centerX=fit2d_parameter['centerX'],
                                                centerY=fit2d_parameter['centerY'],
                                                tilt=fit2d_parameter['tilt'],
                                                tiltPlanRotation=fit2d_parameter['tiltPlanRotation'],
                                                pixelX=fit2d_parameter['pixelX'],
                                                pixelY=fit2d_parameter['pixelY'])
        self.calibration_data.geometry.wavelength = fit2d_parameter['wavelength']
        self.calibration_data.polarization_factor = fit2d_parameter['polarization_factor']
        self.update_all()

    def update_pyFAI_btn_click(self):
        pyFAI_parameter = self.view.get_pyFAI_parameter()
        self.calibration_data.geometry.setPyFAI(dist=pyFAI_parameter['dist'],
                                                poni1=pyFAI_parameter['poni1'],
                                                poni2=pyFAI_parameter['poni2'],
                                                rot1=pyFAI_parameter['rot1'],
                                                rot2=pyFAI_parameter['rot2'],
                                                rot3=pyFAI_parameter['rot3'],
                                                pixel1=pyFAI_parameter['pixel1'],
                                                pixel2=pyFAI_parameter['pixel2'])
        self.calibration_data.geometry.wavelength = pyFAI_parameter['wavelength']
        self.calibration_data.polarization_factor = pyFAI_parameter['polarization_factor']
        self.update_all()


    def load_file(self, filename=None):
        if filename is None:
            filename = str(QtGui.QFileDialog.getOpenFileName(self.view, caption="Load Calibration Image",
                                                             directory=self.working_dir['image']))

        if filename is not '':
            self.working_dir['image'] = os.path.dirname(filename)
            self.data.load(filename)

    def load_calibrants_list(self):
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
        self.view.calibrant_cb.setCurrentIndex(0)
        self.load_calibrant()

    def load_calibrant(self, wavelength_from='start_values'):
        current_index = self.view.calibrant_cb.currentIndex()
        filename = os.path.join(self.calibration_data._calibrants_working_dir,
                                self._calibrants_file_list[current_index])
        self.calibration_data.set_calibrant(filename)

        wavelength = 0
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
        self.view.calibrant_cb.setCurrentIndex(index)
        self.load_calibrant()


    def plot_image(self):
        if self._first_plot:
            self.view.img_view.plot_image(self.data.get_img_data(), True)
            self.view.img_view.auto_range()
            self._first_plot = False
        else:
            self.view.img_view.plot_image(self.data.get_img_data(), False)
        self.view.set_img_filename(self.data.filename)


    def connect_click_function(self, emitter, function):
        self.view.connect(emitter, QtCore.SIGNAL('clicked()'), function)

    def search_peaks(self, x, y):
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
        if points == None:
            try:
                points = self.calibration_data.get_point_array()
            except IndexError:
                points = []
        if len(points):
            self.view.img_view.add_scatter_data(points[:, 0] + 0.5, points[:, 1] + 0.5)

    def clear_peaks_btn_click(self):
        self.calibration_data.clear_peaks()
        self.view.img_view.clear_scatter_plot()
        self.view.peak_num_sb.setValue(1)

    def wavelength_cb_changed(self):
        self.calibration_data.fit_wavelength = self.view.f2_wavelength_cb.isChecked()

    def calibrate(self):
        self.load_calibrant()  #load the right calibration file...
        self.calibration_data.set_start_values(self.view.get_start_values())
        self.calibration_data.calibrate()
        self.update_calibration_parameter()

        if self.view.options_automatic_refinement_cb.isChecked():
            self.refine()
        self.update_all()

    def refine(self):
        self.clear_peaks_btn_click()
        self.load_calibrant(wavelength_from='pyFAI')  #load right calibration file

        # get options
        algorithm = str(self.view.options_peaksearch_algorithm_cb.currentText())
        delta_tth = np.float(self.view.options_delta_tth_txt.text())
        intensity_min_factor = np.float(self.view.options_intensity_mean_factor_sb.value())
        intensity_max = np.float(self.view.options_intensity_limit_txt.text())
        num_rings = self.view.options_num_rings_sb.value()

        self.calibration_data.search_peaks_on_ring(0, delta_tth, algorithm, intensity_min_factor, intensity_max)
        self.calibration_data.search_peaks_on_ring(1, delta_tth, algorithm, intensity_min_factor, intensity_max)
        try:
            self.calibration_data.refine()
        except IndexError:
            print 'Did not find any Points with the specified parameters for the first two rings!'
        self.plot_points()

        for i in xrange(num_rings - 2):
            points = self.calibration_data.search_peaks_on_ring(i + 2, delta_tth, algorithm, intensity_min_factor,
                                                                intensity_max)
            self.plot_points(points)
            QtGui.QApplication.processEvents()
            QtGui.QApplication.processEvents()
            try:
                self.calibration_data.refine()
            except IndexError:
                print 'Did not find enough points with the specified parameters!'
        self.calibration_data.integrate()
        self.update_all()

    def load_calibration(self, filename=None):
        if filename is None:
            filename = str(QtGui.QFileDialog.getOpenFileName(self.view, caption="Load calibration...",
                                                             directory=self.working_dir['calibration'],
                                                             filter='*.poni'))
        if filename is not '':
            self.working_dir['calibration'] = os.path.dirname(filename)
            self.calibration_data.load(filename)
            self.update_all()


    def update_all(self):
        if not self._first_plot:
            self.calibration_data.integrate_1d()
            self.calibration_data.integrate_2d()
            self.view.cake_view.plot_image(self.calibration_data.cake_img, True)

            self.view.spectrum_view.plot_data(self.calibration_data.tth, self.calibration_data.int)
            self.view.spectrum_view.plot_vertical_lines(np.array(self.calibration_data.calibrant.get_2th()) /
                                                        np.pi * 180)
            self.view.spectrum_view.img_view_box.autoRange()
            if self.view.tab_widget.currentIndex() == 0:
                self.view.tab_widget.setCurrentIndex(1)

        if self.view.ToolBox.currentIndex() is not 2 or \
                        self.view.ToolBox.currentIndex() is not 3:
            self.view.ToolBox.setCurrentIndex(2)
        self.update_calibration_parameter()

    def update_calibration_parameter(self):
        pyFAI_parameter, fit2d_parameter = self.calibration_data.get_calibration_parameter()
        self.view.set_calibration_parameters(pyFAI_parameter, fit2d_parameter)

    def save_calibration(self, filename=None):
        if filename is None:
            filename = str(QtGui.QFileDialog.getSaveFileName(self.view, "Save calibration...",
                                                             self.working_dir['calibration'], '*.poni'))
        if filename is not '':
            self.working_dir['calibration'] = os.path.dirname(filename)
            self.calibration_data.geometry.save(filename)


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    controller = CalibrationController()
    app.exec_()