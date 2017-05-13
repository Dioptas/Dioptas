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
import sys
import time
import logging

import numpy as np

from pyFAI.massif import Massif
from pyFAI.blob_detection import BlobDetection
from pyFAI.geometryRefinement import GeometryRefinement
from pyFAI.azimuthalIntegrator import AzimuthalIntegrator
from pyFAI.calibrant import Calibrant
from skimage.measure import find_contours
from .util.HelperModule import get_base_name
from . import ImgModel
from ..calibrants import calibrants_folder

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class CalibrationModel(object):
    def __init__(self, img_model=None):
        """
        :param img_model:
        :type img_model: ImgModel
        """
        self.img_model = img_model
        self.points = []
        self.points_index = []
        self.spectrum_geometry = AzimuthalIntegrator()
        self.cake_geometry = None
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
        self.filename = ''
        self.calibration_name = 'None'
        self.polarization_factor = 0.99
        self.supersampling_factor = 1
        self._calibrants_working_dir = calibrants_folder

        self.cake_img = np.zeros((2048, 2048))
        self.tth = np.linspace(0, 25)
        self.int = np.sin(self.tth)
        self.num_points = len(self.int)

        self.peak_search_algorithm = None

    def find_peaks_automatic(self, x, y, peak_ind):
        """
        Searches peaks by using the Massif algorithm
        :param int x:
            x-coordinate in pixel - should be from original image (not supersampled x-coordinate)
        :param int y:
            y-coordinate in pixel - should be from original image (not supersampled y-coordinate)
        :param peak_ind:
            peak/ring index to which the found points will be added
        :return:
            array of points found
        """
        massif = Massif(self.img_model._img_data)
        cur_peak_points = massif.find_peaks([x, y], stdout=DummyStdOut())
        if len(cur_peak_points):
            self.points.append(np.array(cur_peak_points))
            self.points_index.append(peak_ind)
        return np.array(cur_peak_points)

    def find_peak(self, x, y, search_size, peak_ind):
        """
        Searches a peak around the x,y position. It just searches for the maximum value in a specific search size.
        :param int x:
            x-coordinate in pixel - should be from original image (not supersampled x-coordinate)
        :param int y:
            y-coordinate in pixel - should be form original image (not supersampled y-coordinate)
        :param search_size:
            the length of the search rectangle in pixels in all direction in which the algorithm searches for
            the maximum peak
        :param peak_ind:
            peak/ring index to which the found points will be added
        :return:
            point found (as array)
        """
        left_ind = np.round(x - search_size * 0.5)
        if left_ind < 0:
            left_ind = 0
        top_ind = np.round(y - search_size * 0.5)
        if top_ind < 0:
            top_ind = 0
        search_array = self.img_model.img_data[left_ind:(left_ind + search_size),
                       top_ind:(top_ind + search_size)]
        x_ind, y_ind = np.where(search_array == search_array.max())
        x_ind = x_ind[0] + left_ind
        y_ind = y_ind[0] + top_ind
        self.points.append(np.array([x_ind, y_ind]))
        self.points_index.append(peak_ind)
        return np.array([np.array((x_ind, y_ind))])

    def clear_peaks(self):
        self.points = []
        self.points_index = []

    def create_cake_geometry(self):
        self.cake_geometry = AzimuthalIntegrator()

        pyFAI_parameter = self.spectrum_geometry.getPyFAI()
        pyFAI_parameter['polarization_factor'] = self.polarization_factor
        pyFAI_parameter['wavelength'] = self.spectrum_geometry.wavelength

        self.cake_geometry.setPyFAI(dist=pyFAI_parameter['dist'],
                                    poni1=pyFAI_parameter['poni1'],
                                    poni2=pyFAI_parameter['poni2'],
                                    rot1=pyFAI_parameter['rot1'],
                                    rot2=pyFAI_parameter['rot2'],
                                    rot3=pyFAI_parameter['rot3'],
                                    pixel1=pyFAI_parameter['pixel1'],
                                    pixel2=pyFAI_parameter['pixel2'])

        self.cake_geometry.wavelength = pyFAI_parameter['wavelength']

    def setup_peak_search_algorithm(self, algorithm, mask=None):
        """
        Initializes the peak search algorithm on the current image
        :param algorithm:
            peak search algorithm used. Possible algorithms are 'Massif' and 'Blob'
        :param mask:
            if a mask is used during the process this is provided here as a 2d array for the image.
        """

        if algorithm == 'Massif':
            self.peak_search_algorithm = Massif(self.img_model.raw_img_data)
        elif algorithm == 'Blob':
            if mask is not None:
                self.peak_search_algorithm = BlobDetection(self.img_model.raw_img_data * mask)
            else:
                self.peak_search_algorithm = BlobDetection(self.img_model.raw_img_data)
            self.peak_search_algorithm.process()
        else:
            return

    def search_peaks_on_ring(self, ring_index, delta_tth=0.1, min_mean_factor=1,
                             upper_limit=55000, mask=None):
        """
        This function is searching for peaks on an expected ring. It needs an initial calibration
        before. Then it will search for the ring within some delta_tth and other parameters to get
        peaks from the calibrant.

        :param ring_index: the index of the ring for the search
        :param delta_tth: search space around the expected position in two theta
        :param min_mean_factor: a factor determining the minimum peak intensity to be picked up. it is based
                                on the mean value of the search area defined by delta_tth. Pick a large value
                                for larger minimum value and lower for lower minimum value. Therefore, a smaller
                                number is more prone to picking up noise. typical values like between 1 and 3.
        :param upper_limit: maximum intensity for the peaks to be picked
        :param mask: in case the image has to be masked from certain areas, it need to be given here. Default is None.
                     The mask should be given as an 2d array with the same dimensions as the image, where 1 denotes a
                     masked pixel and all others should be 0.
        """
        self.reset_supersampling()
        if not self.is_calibrated:
            return

        # transform delta from degree into radians
        delta_tth = delta_tth / 180.0 * np.pi

        # get appropriate two theta value for the ring number
        tth_calibrant_list = self.calibrant.get_2th()
        tth_calibrant = np.float(tth_calibrant_list[ring_index])

        # get the calculated two theta values for the whole image
        tth_array = self.spectrum_geometry.twoThetaArray(self.img_model._img_data.shape)

        # create mask based on two_theta position
        ring_mask = abs(tth_array - tth_calibrant) <= delta_tth

        if mask is not None:
            mask = np.logical_and(ring_mask, np.logical_not(mask))
        else:
            mask = ring_mask

        # calculate the mean and standard deviation of this area
        sub_data = np.array(self.img_model._img_data.ravel()[np.where(mask.ravel())], dtype=np.float64)
        sub_data[np.where(sub_data > upper_limit)] = np.NaN
        mean = np.nanmean(sub_data)
        std = np.nanstd(sub_data)

        # set the threshold into the mask (don't detect very low intensity peaks)
        threshold = min_mean_factor * mean + std
        mask2 = np.logical_and(self.img_model._img_data > threshold, mask)
        mask2[np.where(self.img_model._img_data > upper_limit)] = False
        size2 = mask2.sum(dtype=int)

        keep = int(np.ceil(np.sqrt(size2)))
        try:
            sys.stdout = DummyStdOut
            res = self.peak_search_algorithm.peaks_from_area(mask2, Imin=mean - std, keep=keep)
            sys.stdout = sys.__stdout__
        except IndexError:
            res = []

        # Store the result
        if len(res):
            self.points.append(np.array(res))
            self.points_index.append(ring_index)

        self.set_supersampling()
        self.spectrum_geometry.reset()

    def set_calibrant(self, filename):
        self.calibrant = Calibrant()
        self.calibrant.load_file(filename)
        self.spectrum_geometry.calibrant = self.calibrant

    def set_start_values(self, start_values):
        self.start_values = start_values
        self.polarization_factor = start_values['polarization_factor']

    def calibrate(self):
        self.spectrum_geometry = GeometryRefinement(self.create_point_array(self.points, self.points_index),
                                                    dist=self.start_values['dist'],
                                                    wavelength=self.start_values['wavelength'],
                                                    pixel1=self.start_values['pixel_width'],
                                                    pixel2=self.start_values['pixel_height'],
                                                    calibrant=self.calibrant)
        self.orig_pixel1 = self.start_values['pixel_width']
        self.orig_pixel2 = self.start_values['pixel_height']

        self.refine()
        self.create_cake_geometry()
        self.is_calibrated = True

        self.calibration_name = 'current'
        self.set_supersampling()
        # reset the integrator (not the geometric parameters)
        self.spectrum_geometry.reset()

    def refine(self):
        self.reset_supersampling()
        self.spectrum_geometry.data = self.create_point_array(self.points, self.points_index)

        fix = ['wavelength']
        if self.fit_wavelength:
            fix = []
        if not self.fit_distance:
            fix.append('dist')
        if self.fit_wavelength:
            self.spectrum_geometry.refine2()
        self.spectrum_geometry.refine2_wavelength(fix=fix)

        self.create_cake_geometry()
        self.set_supersampling()
        # reset the integrator (not the geometric parameters)
        self.spectrum_geometry.reset()

    def integrate_1d(self, num_points=None, mask=None, polarization_factor=None, filename=None,
                     unit='2th_deg', method='csr'):
        if np.sum(mask) == self.img_model.img_data.shape[0] * self.img_model.img_data.shape[1]:
            # do not perform integration if the image is completely masked...
            return self.tth, self.int

        if self.spectrum_geometry._polarization is not None:
            if self.img_model.img_data.shape != self.spectrum_geometry._polarization.shape:
                # resetting the integrator if the polarization correction matrix has not the correct shape
                self.spectrum_geometry.reset()

        if polarization_factor is None:
            polarization_factor = self.polarization_factor

        if num_points is None:
            num_points = self.calculate_number_of_spectrum_points(2)
        self.num_points = num_points

        t1 = time.time()

        if unit is 'd_A':
            try:
                self.tth, self.int = self.spectrum_geometry.integrate1d(self.img_model.img_data, num_points,
                                                                        method=method,
                                                                        unit='2th_deg',
                                                                        mask=mask,
                                                                        polarization_factor=polarization_factor,
                                                                        filename=filename)
            except NameError:
                self.tth, self.int = self.spectrum_geometry.integrate1d(self.img_model.img_data, num_points,
                                                                        method='csr',
                                                                        unit='2th_deg',
                                                                        mask=mask,
                                                                        polarization_factor=polarization_factor,
                                                                        filename=filename)
            self.tth = self.spectrum_geometry.wavelength / (2 * np.sin(self.tth / 360 * np.pi)) * 1e10
            self.int = self.int
        else:
            try:
                self.tth, self.int = self.spectrum_geometry.integrate1d(self.img_model.img_data, num_points,
                                                                        method=method,
                                                                        unit=unit,
                                                                        mask=mask,
                                                                        polarization_factor=polarization_factor,
                                                                        filename=filename)
            except NameError:
                self.tth, self.int = self.spectrum_geometry.integrate1d(self.img_model.img_data, num_points,
                                                                        method='csr',
                                                                        unit=unit,
                                                                        mask=mask,
                                                                        polarization_factor=polarization_factor,
                                                                        filename=filename)
        logger.info('1d integration of {0}: {1}s.'.format(os.path.basename(self.img_model.filename), time.time() - t1))

        ind = np.where((self.int > 0) & (~np.isnan(self.int)))
        self.tth = self.tth[ind]
        self.int = self.int[ind]
        return self.tth, self.int

    def integrate_2d(self, mask=None, polarization_factor=None, unit='2th_deg', method='csr', dimensions=(2048, 2048)):
        if polarization_factor is None:
            polarization_factor = self.polarization_factor

        if self.cake_geometry._polarization is not None:
            if self.img_model.img_data.shape != self.cake_geometry._polarization.shape:
                # resetting the integrator if the polarization correction matrix has not the same shape as the image
                self.cake_geometry.reset()

        t1 = time.time()

        res = self.cake_geometry.integrate2d(self.img_model.img_data, dimensions[0], dimensions[1], method=method,
                                             mask=mask,
                                             unit=unit, polarization_factor=polarization_factor)
        logger.info('2d integration of {0}: {1}s.'.format(os.path.basename(self.img_model.filename), time.time() - t1))
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
        pyFAI_parameter = self.spectrum_geometry.getPyFAI()
        pyFAI_parameter['polarization_factor'] = self.polarization_factor
        try:
            fit2d_parameter = self.spectrum_geometry.getFit2D()
            fit2d_parameter['polarization_factor'] = self.polarization_factor
        except TypeError:
            fit2d_parameter = None
        try:
            pyFAI_parameter['wavelength'] = self.spectrum_geometry.wavelength
            fit2d_parameter['wavelength'] = self.spectrum_geometry.wavelength
        except RuntimeWarning:
            pyFAI_parameter['wavelength'] = 0

        return pyFAI_parameter, fit2d_parameter

    def calculate_number_of_spectrum_points(self, max_dist_factor=1.5):
        # calculates the number of points for an integrated spectrum, based on the distance of the beam center to the the
        # image corners. Maximum value is determined by the shape of the image.
        fit2d_parameter = self.spectrum_geometry.getFit2D()
        center_x = fit2d_parameter['centerX']
        center_y = fit2d_parameter['centerY']
        width, height = self.img_model.img_data.shape

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
        """
        Loads a calibration file and and sets all the calibration parameter.
        :param filename: filename for a *.poni calibration file
        """
        self.spectrum_geometry = AzimuthalIntegrator()
        self.spectrum_geometry.load(filename)
        self.orig_pixel1 = self.spectrum_geometry.pixel1
        self.orig_pixel2 = self.spectrum_geometry.pixel2
        self.calibration_name = get_base_name(filename)
        self.filename = filename
        self.is_calibrated = True
        self.create_cake_geometry()
        self.set_supersampling()

    def save(self, filename):
        """
        Saves the current calibration parameters into a a text file. Default extension is
        *.poni
        """
        self.cake_geometry.save(filename)
        self.calibration_name = get_base_name(filename)
        self.filename = filename

    def create_file_header(self):
        try:
            # pyFAI version 0.12.0
            return self.spectrum_geometry.makeHeaders(polarization_factor=self.polarization_factor)
        except AttributeError:
            # pyFAI after version 0.12.0
            from pyFAI.io import DefaultAiWriter
            return DefaultAiWriter(None, self.spectrum_geometry).make_headers()

    def set_fit2d(self, fit2d_parameter):
        """
        Reads in a dictionary with fit2d parameters where the fields of the dictionary are:
        'directDist', 'centerX', 'centerY', 'tilt', 'tiltPlanRotation', 'pixelX', pixelY',
        'polarization_factor', 'wavelength'
        """
        self.spectrum_geometry.setFit2D(directDist=fit2d_parameter['directDist'],
                                        centerX=fit2d_parameter['centerX'],
                                        centerY=fit2d_parameter['centerY'],
                                        tilt=fit2d_parameter['tilt'],
                                        tiltPlanRotation=fit2d_parameter['tiltPlanRotation'],
                                        pixelX=fit2d_parameter['pixelX'],
                                        pixelY=fit2d_parameter['pixelY'])
        self.spectrum_geometry.wavelength = fit2d_parameter['wavelength']
        self.create_cake_geometry()
        self.polarization_factor = fit2d_parameter['polarization_factor']
        self.orig_pixel1 = fit2d_parameter['pixelX'] * 1e-6
        self.orig_pixel2 = fit2d_parameter['pixelY'] * 1e-6
        self.is_calibrated = True
        self.set_supersampling()

    def set_pyFAI(self, pyFAI_parameter):
        """
        Reads in a dictionary with pyFAI parameters where the fields of dictionary are:
        'dist', 'poni1', 'poni2', 'rot1', 'rot2', 'rot3', 'pixel1', 'pixel2', 'wavelength',
        'polarization_factor'
        """
        self.spectrum_geometry.setPyFAI(dist=pyFAI_parameter['dist'],
                                        poni1=pyFAI_parameter['poni1'],
                                        poni2=pyFAI_parameter['poni2'],
                                        rot1=pyFAI_parameter['rot1'],
                                        rot2=pyFAI_parameter['rot2'],
                                        rot3=pyFAI_parameter['rot3'],
                                        pixel1=pyFAI_parameter['pixel1'],
                                        pixel2=pyFAI_parameter['pixel2'])
        self.spectrum_geometry.wavelength = pyFAI_parameter['wavelength']
        self.create_cake_geometry()
        self.polarization_factor = pyFAI_parameter['polarization_factor']
        self.orig_pixel1 = pyFAI_parameter['pixel1']
        self.orig_pixel2 = pyFAI_parameter['pixel2']
        self.is_calibrated = True
        self.set_supersampling()

    def set_supersampling(self, factor=None):
        """
        Sets the supersampling to a specific factor. Whereby the factor determines in how many artificial pixel the
        original pixel is split. (factor^2)

        factor  n_pixel
        1       1
        2       4
        3       9
        4       16
        """
        if factor is None:
            factor = self.supersampling_factor
        self.spectrum_geometry.pixel1 = self.orig_pixel1 / float(factor)
        self.spectrum_geometry.pixel2 = self.orig_pixel2 / float(factor)

        if factor != self.supersampling_factor:
            self.spectrum_geometry.reset()
            self.supersampling_factor = factor

    def reset_supersampling(self):
        self.spectrum_geometry.pixel1 = self.orig_pixel1
        self.spectrum_geometry.pixel2 = self.orig_pixel2

    def get_two_theta_img(self, x, y):
        """
        Gives the two_theta value for the x,y coordinates on the image. Be aware that this function will be incorrect
        for pixel indices, since it does not correct for center of the pixel.
        :return:
            two theta in radians
        """
        x = np.array([x]) * self.supersampling_factor
        y = np.array([y]) * self.supersampling_factor

        return self.spectrum_geometry.tth(x - 0.5, y - 0.5)[0]  # deletes 0.5 because tth function uses pixel indices

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
        x *= self.supersampling_factor
        y *= self.supersampling_factor
        return self.spectrum_geometry.chi(x, y)[0]

        return azi

    def get_two_theta_array(self):
        return self.spectrum_geometry.twoThetaArray(self.img_model.img_data.shape)[::self.supersampling_factor,
               ::self.supersampling_factor]

    def get_pixel_ind(self, tth, azi):
        """
        Calculates pixel index for a specfic two theta and azimutal value.
        :param tth:
            two theta in radians
        :param azi:
            azimuth in radians
        :return:
            tuple of index 1 and 2
        """

        tth_ind = find_contours(self.spectrum_geometry.ttha, tth)
        if len(tth_ind) == 0:
            return []
        tth_ind = np.vstack(tth_ind)
        azi_values = self.spectrum_geometry.chi(tth_ind[:, 0], tth_ind[:, 1])
        min_index = np.argmin(np.abs(azi_values - azi))
        return tth_ind[min_index, 0], tth_ind[min_index, 1]

    @property
    def wavelength(self):
        return self.spectrum_geometry.wavelength


class DummyStdOut(object):
    @classmethod
    def write(cls, *args, **kwargs):
        pass
