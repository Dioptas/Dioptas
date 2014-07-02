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

from pyFAI.peakPicker import Massif
from pyFAI.blob_detection import BlobDetection
from pyFAI.calibration import Calibration
from pyFAI.geometryRefinement import GeometryRefinement
from pyFAI.azimuthalIntegrator import AzimuthalIntegrator
from pyFAI.calibrant import Calibrant
from Data.HelperModule import get_base_name
import Calibrants
import os
import numpy as np

class CalibrationData(object):
    def __init__(self, img_data=None):
        self.img_data = img_data
        self.points = []
        self.points_index = []
        self.geometry = AzimuthalIntegrator()
        self.calibrant = Calibrant()
        self.start_values = {'dist': 200e-3,
                             'wavelength': 0.3344e-10,
                             'pixel_width': 79e-6,
                             'pixel_height': 79e-6,
                             'polarization_factor': 0.95}
        self.fit_wavelength = False
        self.is_calibrated = False
        self.use_mask = False
        self.calibration_name = 'None'
        self.polarization_factor = 0.95
        self._calibrants_working_dir = os.path.dirname(Calibrants.__file__)
        print self._calibrants_working_dir

    def find_peaks_automatic(self, x, y, peak_ind):
        massif = Massif(self.img_data.img_data)
        cur_peak_points = massif.find_peaks([x, y])
        if len(cur_peak_points):
            self.points.append(np.array(cur_peak_points))
            self.points_index.append(peak_ind)
        return np.array(cur_peak_points)

    def find_peak(self, x, y, search_size, peak_ind):
        left_ind = np.round(x - search_size * 0.5)
        top_ind = np.round(y - search_size * 0.5)
        x_ind, y_ind = np.where(self.img_data.img_data[left_ind:(left_ind + search_size),
                                top_ind:(top_ind + search_size)] == \
                                self.img_data.img_data[left_ind:(left_ind + search_size),
                                top_ind:(top_ind + search_size)].max())
        x_ind = x_ind[0] + left_ind
        y_ind = y_ind[0] + top_ind
        self.points.append(np.array([x_ind, y_ind]))
        self.points_index.append(peak_ind)
        return np.array([np.array((x_ind, y_ind))])

    def clear_peaks(self):
        self.points = []
        self.points_index = []

    def setup_peak_search_algorithm(self, algorithm, mask=None):
        # init the peak search algorithm
        if algorithm == 'Massif':
            self.peak_search_algorithm = Massif(self.img_data.img_data)
        elif algorithm == 'Blob':
            if mask is not None:
                self.peak_search_algorithm = BlobDetection(self.img_data.img_data * mask)
            else:
                self.peak_search_algorithm = BlobDetection(self.img_data.img_data)
            self.peak_search_algorithm.process()
        else:
            return

    def search_peaks_on_ring(self, peak_index, delta_tth=0.1, min_mean_factor=1,
                             upper_limit=55000, mask=None):
        if not self.is_calibrated:
            return

        #transform delta from degree into radians
        delta_tth = delta_tth / 180.0 * np.pi

        # get appropiate two theta value for the ring number
        tth_calibrant_list = self.calibrant.get_2th()
        tth_calibrant = np.float(tth_calibrant_list[peak_index])

        # get the calculated two theta values for the whole image
        if self.geometry._ttha is None:
            tth_array = self.geometry.twoThetaArray(self.img_data.img_data.shape)
        else:
            tth_array = self.geometry._ttha

        # create mask based on two_theta position
        ring_mask = abs(tth_array - tth_calibrant) <= delta_tth

        if mask is not None:
            mask = np.logical_and(ring_mask, np.logical_not(mask))
        else:
            mask = ring_mask

        # calculate the mean and standard deviation of this area
        sub_data = np.array(self.img_data.img_data.ravel()[np.where(mask.ravel())], dtype=np.float64)
        sub_data[np.where(sub_data > upper_limit)] = np.NaN
        mean = np.nanmean(sub_data)
        std = np.nanstd(sub_data)

        # set the threshold into the mask (don't detect very low intensity peaks)
        threshold = min_mean_factor * mean + std
        mask2 = np.logical_and(self.img_data.img_data > threshold, mask)
        mask2[np.where(self.img_data.img_data > upper_limit)] = False
        size2 = mask2.sum(dtype=int)

        keep = int(np.ceil(np.sqrt(size2)))
        try:
            res = self.peak_search_algorithm.peaks_from_area(mask2, Imin=mean - std, keep=keep)
        except IndexError:
            res = []

        # Store the result
        if len(res):
            self.points.append(np.array(res))
            self.points_index.append(peak_index)

    def set_calibrant(self, filename):
        self.calibrant = Calibrant()
        self.calibrant.load_file(filename)
        self.geometry.calibrant = self.calibrant

    def set_start_values(self, start_values):
        self.start_values = start_values
        self.polarization_factor = start_values['polarization_factor']

    def calibrate(self):
        self.geometry = GeometryRefinement(self.create_point_array(self.points, self.points_index),
                                           dist=self.start_values['dist'],
                                           wavelength=self.start_values['wavelength'],
                                           pixel1=self.start_values['pixel_width'],
                                           pixel2=self.start_values['pixel_height'],
                                           calibrant=self.calibrant)
        self.refine()
        self.integrate()
        self.is_calibrated = True
        self.calibration_name = 'current'

    def refine(self):
        self.geometry.data = self.create_point_array(self.points, self.points_index)
        self.geometry.refine2()
        if self.fit_wavelength:
            self.geometry.refine2_wavelength(fix=[])

    def integrate(self):
        self.integrate_1d()
        self.integrate_2d()

    def integrate_1d(self, num_points=1400, mask=None, polarization_factor=None, filename=None, unit='2th_deg'):
        if np.sum(mask) == self.img_data.img_data.shape[0] * self.img_data.img_data.shape[1]:
            #do not perform integration if the image is completelye masked...
            return self.tth, self.int
        if polarization_factor is None:
            polarization_factor = self.polarization_factor
        if unit is 'd_A':
            self.tth, self.int = self.geometry.integrate1d(self.img_data.img_data, num_points, method='lut',
                                                           unit='2th_deg',
                                                           mask=mask, polarization_factor=polarization_factor,
                                                           filename=filename)
            ind = np.where(self.tth > 0)
            self.tth = self.geometry.wavelength / (2 * np.sin(self.tth[ind] / 360 * np.pi)) * 1e10
            self.int = self.int[ind]
        else:
            self.tth, self.int = self.geometry.integrate1d(self.img_data.img_data, num_points, method='lut', unit=unit,
                                                           mask=mask, polarization_factor=polarization_factor,
                                                           filename=filename)
        if self.int.max() > 0:
            ind = np.where(self.int > 0)
            self.tth = self.tth[ind]
            self.int = self.int[ind]
        return self.tth, self.int

    def integrate_2d(self, mask=None, polarization_factor=None, unit='2th_deg'):
        if polarization_factor is None:
            polarization_factor = self.polarization_factor
        res = self.geometry.integrate2d(self.img_data.img_data, 2048, 2048, method='lut', mask=mask, unit=unit,
                                        polarization_factor=polarization_factor)
        self.cake_img = res[0]
        self.cake_tth = res[1]
        self.cake_azi = res[2]
        return self.cake_img

    def create_point_array(self, points, points_ind):
        res = []
        for i, point_list in enumerate(points):
            if point_list.shape == (2,):
                res.append([point_list[0], point_list[1], points_ind[i]])
            else:
                for point in point_list:
                    res.append([point[0], point[1], points_ind[i]])
        return np.array(res)

    def get_point_array(self):
        return self.create_point_array(self.points, self.points_index)

    def get_calibration_parameter(self):
        pyFAI_parameter = self.geometry.getPyFAI()
        pyFAI_parameter['polarization_factor'] = self.polarization_factor
        try:
            fit2d_parameter = self.geometry.getFit2D()
            fit2d_parameter['polarization_factor'] = self.polarization_factor
        except TypeError:
            fit2d_parameter = None
        try:
            pyFAI_parameter['wavelength'] = self.geometry.wavelength
            fit2d_parameter['wavelength'] = self.geometry.wavelength
        except RuntimeWarning:
            pyFAI_parameter['wavelength'] = 0

        return pyFAI_parameter, fit2d_parameter

    def load(self, filename):
        self.geometry = GeometryRefinement(np.zeros((2, 3)),
                                           dist=self.start_values['dist'],
                                           wavelength=self.start_values['wavelength'],
                                           pixel1=self.start_values['pixel_width'],
                                           pixel2=self.start_values['pixel_height'])
        self.geometry.load(filename)
        self.calibration_name = get_base_name(filename)
        self.is_calibrated = True

    def save(self, filename):
        self.geometry.save(filename)
        self.calibration_name = get_base_name(filename)