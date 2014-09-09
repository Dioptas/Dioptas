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
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <http://www.gnu.org/licenses/>.

__author__ = 'Clemens Prescher'

import os
import numpy as np
import time
import matplotlib.pyplot as plt

import logging

logger = logging.getLogger(__name__)

from pyFAI.massif import Massif
from pyFAI.blob_detection import BlobDetection
from pyFAI.geometryRefinement import GeometryRefinement
from pyFAI.azimuthalIntegrator import AzimuthalIntegrator
from pyFAI.calibrant import Calibrant
from .HelperModule import get_base_name
from copy import copy
import Calibrants


class CalibrationData(object):
    def __init__(self, img_data=None):
        self.img_data = img_data
        self.points = []
        self.points_index = []
        self.geometry = AzimuthalIntegrator()
        self.geometry2 = AzimuthalIntegrator()
        self.calibrant = Calibrant()
        self.start_values = {'dist': 200e-3,
                             'wavelength': 0.3344e-10,
                             'pixel_width': 79e-6,
                             'pixel_height': 79e-6,
                             'polarization_factor': 0.99}
        self.orig_pixel1 = 79e-6
        self.orig_pixel2 = 79e-6
        self.fit_wavelength = False
        self.fit_distance = True
        self.is_calibrated = False
        self.use_mask = False
        self.calibration_name = 'None'
        self.polarization_factor = 0.99
        self.supersampling_factor = 1
        self._calibrants_working_dir = os.path.dirname(Calibrants.__file__)

        self.cake_img = np.zeros((2048, 2048))
        self.tth = np.linspace(0, 25)
        self.int = np.sin(self.tth)

    def find_peaks_automatic(self, x, y, peak_ind):
        """
        Searches peaks by using the Massif algorithm
        :param x:
            x-coordinate in pixel - should be from original image (not supersampled x-coordinate)
        :param y:
            y-coordinate in pixel - should be from original image (not supersampled y-coordinate)
        :param peak_ind:
            peak/ring index to which the found points will be added
        :return:
            array of points found
        """
        massif = Massif(self.img_data._img_data)
        cur_peak_points = massif.find_peaks([x, y])
        if len(cur_peak_points):
            self.points.append(np.array(cur_peak_points))
            self.points_index.append(peak_ind)
        return np.array(cur_peak_points)

    def find_peak(self, x, y, search_size, peak_ind):
        """
        Searches a peak around the x,y position. It just searches for the maximum value in a specific search size.
        :param x:
            x-coordinate in pixel - should be from original image (not supersampled x-coordinate)
        :param y:
            y-coordinate in pixel - should be form original image (not supersampled y-coordinate)
        :param search_size:
            the amount of pixels in all direction in which the algorithm searches for the maximum peak
        :param peak_ind:
            peak/ring index to which the found points will be added
        :return:
            point found (as array)
        """
        left_ind = np.round(x - search_size * 0.5)
        top_ind = np.round(y - search_size * 0.5)
        x_ind, y_ind = np.where(self.img_data._img_data[left_ind:(left_ind + search_size),
                                top_ind:(top_ind + search_size)] == \
                                self.img_data._img_data[left_ind:(left_ind + search_size),
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
        """
        Initializes the peak search algorithm on the current image
        :param algorithm:
            peak search algorithm used. Possible algorithms are 'Massif' and 'Blob'
        :param mask:
            if a mask is used during the process this is provided here as a 2d array for the image.
        """

        if algorithm == 'Massif':
            self.peak_search_algorithm = Massif(self.img_data._img_data)
        elif algorithm == 'Blob':
            if mask is not None:
                self.peak_search_algorithm = BlobDetection(self.img_data._img_data * mask)
            else:
                self.peak_search_algorithm = BlobDetection(self.img_data._img_data)
            self.peak_search_algorithm.process()
        else:
            return


    def search_peaks_on_ring(self, peak_index, delta_tth=0.1, min_mean_factor=1,
                             upper_limit=55000, mask=None):
        self.reset_supersampling()
        if not self.is_calibrated:
            return

        #transform delta from degree into radians
        delta_tth = delta_tth / 180.0 * np.pi

        # get appropriate two theta value for the ring number
        tth_calibrant_list = self.calibrant.get_2th()
        tth_calibrant = np.float(tth_calibrant_list[peak_index])

        # get the calculated two theta values for the whole image
        if self.geometry._ttha is None:
            tth_array = self.geometry.twoThetaArray(self.img_data._img_data.shape)
        else:
            tth_array = self.geometry._ttha

        # create mask based on two_theta position
        ring_mask = abs(tth_array - tth_calibrant) <= delta_tth

        if mask is not None:
            mask = np.logical_and(ring_mask, np.logical_not(mask))
        else:
            mask = ring_mask

        # calculate the mean and standard deviation of this area
        sub_data = np.array(self.img_data._img_data.ravel()[np.where(mask.ravel())], dtype=np.float64)
        sub_data[np.where(sub_data > upper_limit)] = np.NaN
        mean = np.nanmean(sub_data)
        std = np.nanstd(sub_data)

        # set the threshold into the mask (don't detect very low intensity peaks)
        threshold = min_mean_factor * mean + std
        mask2 = np.logical_and(self.img_data._img_data > threshold, mask)
        mask2[np.where(self.img_data._img_data > upper_limit)] = False
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

        self.set_supersampling()
        self.geometry.reset()

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
        self.geometry2 = copy(self.geometry)
        self.is_calibrated = True

        self.orig_pixel1 = self.start_values['pixel_width']
        self.orig_pixel2 = self.start_values['pixel_height']
        self.calibration_name = 'current'
        self.set_supersampling()
        self.geometry.reset()

    def refine(self):
        self.reset_supersampling()
        self.geometry.data = self.create_point_array(self.points, self.points_index)
        # self.geometry.refine2()
        fix = ['wavelength']
        if self.fit_wavelength:
            fix = []
        if not self.fit_distance:
            fix.append('dist')
        if self.fit_wavelength:
            self.geometry.refine2()
        self.geometry.refine2_wavelength(fix=fix)
        self.geometry2 = copy(self.geometry)
        self.set_supersampling()
        self.geometry.reset()

    def integrate_1d(self, num_points=None, mask=None, polarization_factor=None, filename=None,
                     unit='2th_deg', method='csr'):
        if np.sum(mask) == self.img_data.img_data.shape[0] * self.img_data.img_data.shape[1]:
            #do not perform integration if the image is completely masked...
            return self.tth, self.int
        if polarization_factor is None:
            #correct for different orientation definition in pyFAI compared to Fit2D
            polarization_factor = self.polarization_factor

        if num_points is None:
            num_points = self.calculate_number_of_spectrum_points(1.1)
        self.num_points = num_points

        t1 = time.time()
        
        if unit is 'd_A':
            try:
                self.tth, self.int = self.geometry.integrate1d(self.img_data.img_data, num_points, method=method,
                                                               unit='2th_deg',
                                                               mask=mask, polarization_factor=polarization_factor,
                                                               filename=filename)
            except NameError:
                self.tth, self.int = self.geometry.integrate1d(self.img_data.img_data, num_points, method=method,
                                                               unit='2th_deg',
                                                               mask=mask, polarization_factor=polarization_factor,
                                                               filename=filename)
            ind = np.where(self.tth > 0)
            self.tth = self.geometry.wavelength / (2 * np.sin(self.tth[ind] / 360 * np.pi)) * 1e10
            self.int = self.int[ind]
        else:
            try:
                self.tth, self.int = self.geometry.integrate1d(self.img_data.img_data, num_points, method=method,
                                                               unit=unit,
                                                               mask=mask, polarization_factor=polarization_factor,
                                                               filename=filename)
            except NameError:
                self.tth, self.int = self.geometry.integrate1d(self.img_data.img_data, num_points, method='lut',
                                                               unit=unit,
                                                               mask=mask, polarization_factor=polarization_factor,
                                                               filename=filename)
        logger.info('1d integration of {}: {}s.'.format(os.path.basename(self.img_data.filename), time.time() - t1))
        if self.int.max() > 0:
            ind = np.where(self.int > 0)
            self.tth = self.tth[ind]
            self.int = self.int[ind]
        return self.tth, self.int

    def integrate_2d(self, mask=None, polarization_factor=None, unit='2th_deg', method='csr', dimensions=(2048, 2048)):
        if polarization_factor is None:
            polarization_factor = self.polarization_factor

        t1 = time.time()

        res = self.geometry2.integrate2d(self.img_data._img_data, dimensions[0], dimensions[1], method=method, mask=mask,
                                         unit=unit, polarization_factor=polarization_factor)
        logger.info('2d integration of {}: {}s.'.format(os.path.basename(self.img_data.filename), time.time() - t1))
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

    def calculate_number_of_spectrum_points(self, max_dist_factor=1.5):
        #calculates the number of points for an integrated spectrum, based on the distance of the beam center to the the
        #image corners. Maximum value is determined by the shape of the image.
        fit2d_parameter = self.geometry.getFit2D()
        center_x = fit2d_parameter['centerX']
        center_y = fit2d_parameter['centerY']
        width, height = self.img_data.img_data.shape

        if center_x < width and center_x > 0:
            side1 = np.max([abs(width - center_x), center_x])
        else:
            side1 = width

        if center_y < height and center_y > 0:
            side2 = np.max([abs(height - center_y), center_y])
        else:
            side2 = height
        max_dist = np.sqrt(side1 ** 2 + side2 ** 2)
        return int(max_dist * max_dist_factor)

    def load(self, filename):
        self.geometry = GeometryRefinement(np.zeros((2, 3)),
                                           dist=self.start_values['dist'],
                                           wavelength=self.start_values['wavelength'],
                                           pixel1=self.start_values['pixel_width'],
                                           pixel2=self.start_values['pixel_height'])
        self.geometry.load(filename)
        self.calibration_name = get_base_name(filename)
        self.is_calibrated = True
        self.geometry2 = copy(self.geometry)
        self.set_supersampling()

    def save(self, filename):
        self.geometry.save(filename)
        self.calibration_name = get_base_name(filename)

    def set_fit2d(self, fit2d_parameter):
        self.geometry.setFit2D(directDist=fit2d_parameter['directDist'],
                               centerX=fit2d_parameter['centerX'],
                               centerY=fit2d_parameter['centerY'],
                               tilt=fit2d_parameter['tilt'],
                               tiltPlanRotation=fit2d_parameter['tiltPlanRotation'],
                               pixelX=fit2d_parameter['pixelX'],
                               pixelY=fit2d_parameter['pixelY'])
        self.geometry.wavelength = fit2d_parameter['wavelength']
        self.geometry2 = copy(self.geometry)
        self.polarization_factor = fit2d_parameter['polarization_factor']
        self.orig_pixel1 = fit2d_parameter['pixelX']*1e-6
        self.orig_pixel2 = fit2d_parameter['pixelY']*1e-6
        self.is_calibrated = True
        self.set_supersampling()

    def set_pyFAI(self, pyFAI_parameter):
        self.geometry.setPyFAI(dist=pyFAI_parameter['dist'],
                               poni1=pyFAI_parameter['poni1'],
                               poni2=pyFAI_parameter['poni2'],
                               rot1=pyFAI_parameter['rot1'],
                               rot2=pyFAI_parameter['rot2'],
                               rot3=pyFAI_parameter['rot3'],
                               pixel1=pyFAI_parameter['pixel1'],
                               pixel2=pyFAI_parameter['pixel2'])
        self.geometry.wavelength = pyFAI_parameter['wavelength']
        self.geometry2 = copy(self.geometry)
        self.polarization_factor = pyFAI_parameter['polarization_factor']
        self.orig_pixel1 = pyFAI_parameter['pixel1']
        self.orig_pixel2 = pyFAI_parameter['pixel2']
        self.is_calibrated = True
        self.set_supersampling()

    def set_supersampling(self, factor=None):
        if factor is None:
            factor = self.supersampling_factor
        self.geometry.pixel1 = self.orig_pixel1 / float(factor)
        self.geometry.pixel2 = self.orig_pixel2 / float(factor)

        if factor != self.supersampling_factor:
            self.geometry.reset()
            self.supersampling_factor = factor

    def reset_supersampling(self):
        self.geometry.pixel1 = self.orig_pixel1
        self.geometry.pixel2 = self.orig_pixel2
        # self.geometry2.pixel1 = self.orig_pixel1
        # self.geometry2.pixel2 = self.orig_pixel2

    def get_two_theta_img(self, x, y):
        """
        Gives the two_theta value for the x,y coordinates on the image
        :return:
            two theta in radians
        """
        x = np.array([x])*self.supersampling_factor
        y = np.array([y])*self.supersampling_factor

        return self.geometry.tth(x,y)[0]

    def get_azi_img(self, x, y):
        """
        Gives chi for position on image.
        :param x:
            x-coordinate in pixel
        :param y:
            y-coordinate in pixel
        :return:
            azimuth in radians
        """
        x*=self.supersampling_factor
        y*=self.supersampling_factor
        return self.geometry.chi(x,y)[0]

    def get_two_theta_cake(self, y):
        """
        Gives the two_theta value for the x coordinate in the cake
        :param x:
            y-coordinate on image
        :return:
            two theta in degree
        """
        return self.cake_tth[np.round(y[0])]

    def get_azi_cake(self, x):
        """
        Gives the azimuth value for a cake.
        :param x:
            x-coordinate in pixel
        :return:
            azimuth in degree
        """
        return self.cake_azi[np.round(x[0])]

    def get_two_theta_array(self):
        return self.geometry._ttha[::self.supersampling_factor,::self.supersampling_factor]

    @property
    def wavelength(self):
        return self.geometry.wavelength