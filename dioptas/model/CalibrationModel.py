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

import logging
import os
import sys
import time
from enum import Enum
from copy import deepcopy

import numpy as np
from pyFAI.azimuthalIntegrator import AzimuthalIntegrator
from pyFAI.blob_detection import BlobDetection
from pyFAI.calibrant import Calibrant
from pyFAI.detectors import Detector, ALL_DETECTORS, NexusDetector
from pyFAI.geometryRefinement import GeometryRefinement
from pyFAI.massif import Massif
from skimage.measure import find_contours

from .. import calibrants_path
from .ImgModel import ImgModel
from .util import Signal
from .util.HelperModule import (
    get_base_name,
    rotate_matrix_p90,
    rotate_matrix_m90,
    get_partial_index,
)
from .util.calc import supersample_image, trim_trailing_zeros

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class CalibrationModel(object):

    def __init__(self, img_model=None):
        """
        :param img_model:
        :type img_model: ImgModel
        """
        super(CalibrationModel, self).__init__()
        self.img_model = img_model
        self.points = []
        self.points_index = []

        self.detector = Detector(pixel1=79e-6, pixel2=79e-6)
        # self.detector.shape = (2048, 2048)
        self.detector_mode = DetectorModes.CUSTOM
        self._original_detector = (
            None  # used for saving original state before rotating or flipping
        )
        self.pattern_geometry = GeometryRefinement(
            detector=self.detector, wavelength=0.3344e-10, poni1=0, poni2=0
        )  # default params are necessary, otherwise fails...
        self.pattern_geometry_img_shape = None
        self.cake_geometry = None
        self.cake_geometry_img_shape = None
        self.calibrant = Calibrant()

        self.orig_pixel1 = (
            self.detector.pixel1
        )  # needs to be extra stored for applying supersampling
        self.orig_pixel2 = self.detector.pixel2

        self.start_values = {
            "dist": 200e-3,
            "wavelength": 0.3344e-10,
            "polarization_factor": 0.99,
        }
        self.fit_wavelength = False
        self.fixed_values = (
            {}
        )  # dictionary for fixed parameters during calibration (keys can be e.g. rot1, poni1 etc.
        # and values are the values to what the respective parameter will be set
        self.is_calibrated = False
        self.use_mask = False
        self.filename = ""
        self.calibration_name = "None"
        self.polarization_factor = 0.99
        self.supersampling_factor = 1
        self.correct_solid_angle = True
        self._calibrants_working_dir = calibrants_path

        self.distortion_spline_filename = None

        self.tth = np.linspace(0, 25)
        self.int = np.sin(self.tth)
        self.num_points = len(self.int)

        self.cake_img = np.zeros((2048, 2048))
        self.cake_tth = None
        self.cake_azi = None

        self.peak_search_algorithm = None

        self.img_model.img_changed.connect(self._check_detector_and_image_shape)

        self.detector_reset = Signal()

    def find_peaks_automatic(self, x, y, peak_ind):
        """
        Searches peaks by using the Massif algorithm
        :param float x:
            x-coordinate in pixel - should be from original image (not supersampled x-coordinate)
        :param float y:
            y-coordinate in pixel - should be from original image (not supersampled y-coordinate)
        :param peak_ind:
            peak/ring index to which the found points will be added
        :return:
            array of points found
        """
        massif = Massif(self.img_model.img_data, median_prefilter=False)
        cur_peak_points = massif.find_peaks(
            (int(np.round(x)), int(np.round(y))), stdout=DummyStdOut()
        )
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
        left_ind = int(np.round(x - search_size * 0.5))
        if left_ind < 0:
            left_ind = 0
        top_ind = int(np.round(y - search_size * 0.5))
        if top_ind < 0:
            top_ind = 0
        search_array = self.img_model.img_data[
            left_ind : (left_ind + search_size), top_ind : (top_ind + search_size)
        ]
        x_ind, y_ind = np.where(search_array == search_array.max())
        x_ind = x_ind[0] + left_ind
        y_ind = y_ind[0] + top_ind
        self.points.append(np.array([x_ind, y_ind]))
        self.points_index.append(peak_ind)
        return np.array([np.array((x_ind, y_ind))])

    def clear_peaks(self):
        self.points = []
        self.points_index = []

    def remove_last_peak(self):
        if self.points:
            num_points = int(
                self.points[-1].size / 2
            )  # each peak is x, y so length is twice as number of peaks
            self.points.pop(-1)
            self.points_index.pop(-1)
            return num_points

    def create_cake_geometry(self):
        self.cake_geometry = AzimuthalIntegrator(
            splineFile=self.distortion_spline_filename
        )

        pyFAI_parameter = self.pattern_geometry.getPyFAI()
        pyFAI_parameter["wavelength"] = self.pattern_geometry.wavelength

        self.cake_geometry.setPyFAI(
            dist=pyFAI_parameter["dist"],
            poni1=pyFAI_parameter["poni1"],
            poni2=pyFAI_parameter["poni2"],
            rot1=pyFAI_parameter["rot1"],
            rot2=pyFAI_parameter["rot2"],
            rot3=pyFAI_parameter["rot3"],
        )

        self.cake_geometry.detector = self.detector
        self.cake_geometry.wavelength = pyFAI_parameter["wavelength"]

    def setup_peak_search_algorithm(self, algorithm, mask=None):
        """
        Initializes the peak search algorithm on the current image
        :param algorithm:
            peak search algorithm used. Possible algorithms are 'Massif' and 'Blob'
        :param mask:
            if a mask is used during the process this is provided here as a 2d array for the image.
        """

        if algorithm == "Massif":
            self.peak_search_algorithm = Massif(
                self.img_model.img_data, median_prefilter=False
            )
        elif algorithm == "Blob":
            if mask is not None:
                self.peak_search_algorithm = BlobDetection(
                    self.img_model.img_data * mask
                )
            else:
                self.peak_search_algorithm = BlobDetection(self.img_model.img_data)
            self.peak_search_algorithm.process()
        else:
            return

    def search_peaks_on_ring(
        self, ring_index, delta_tth=0.1, min_mean_factor=1, upper_limit=55000, mask=None
    ):
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
        if ring_index >= len(tth_calibrant_list):
            raise NotEnoughSpacingsInCalibrant()
        tth_calibrant = float(tth_calibrant_list[ring_index])

        # get the calculated two theta values for the whole image
        tth_array = self.pattern_geometry.twoThetaArray(self.img_model.img_data.shape)

        # create mask based on two_theta position
        ring_mask = abs(tth_array - tth_calibrant) <= delta_tth

        if mask is not None:
            mask = np.logical_and(ring_mask, np.logical_not(mask))
        else:
            mask = ring_mask

        # calculate the mean and standard deviation of this area
        sub_data = np.array(
            self.img_model.img_data.ravel()[np.where(mask.ravel())], dtype=np.float64
        )
        sub_data[np.where(sub_data > upper_limit)] = np.NaN
        mean = np.nanmean(sub_data)
        std = np.nanstd(sub_data)

        # set the threshold into the mask (don't detect very low intensity peaks)
        threshold = min_mean_factor * mean + std
        mask2 = np.logical_and(self.img_model.img_data > threshold, mask)
        mask2[np.where(self.img_model.img_data > upper_limit)] = False
        size2 = mask2.sum(dtype=int)

        keep = int(np.ceil(np.sqrt(size2)))
        try:
            old_stdout = sys.stdout
            sys.stdout = DummyStdOut
            res = self.peak_search_algorithm.peaks_from_area(
                mask2, Imin=mean - std, keep=keep
            )
            sys.stdout = old_stdout
        except IndexError:
            res = []

        # Store the result
        if len(res):
            self.points.append(np.array(res))
            self.points_index.append(ring_index)

        self.set_supersampling()
        self.pattern_geometry.reset()

    def set_calibrant(self, filename):
        self.calibrant = Calibrant()
        self.calibrant.load_file(filename)
        self.pattern_geometry.calibrant = self.calibrant

    def set_start_values(self, start_values):
        self.start_values = start_values
        self.polarization_factor = start_values["polarization_factor"]

    def set_pixel_size(self, pixel_size):
        """
        :param pixel_size: tuple with pixel_width and pixel height as element
        """
        self.orig_pixel1 = pixel_size[0]
        self.orig_pixel2 = pixel_size[1]

        self.detector.pixel1 = self.orig_pixel1
        self.detector.pixel2 = self.orig_pixel2
        self.set_supersampling()

    def update_detector_shape(self):
        self.detector.shape = self.img_model.img_data.shape
        self.detector.max_shape = self.img_model.img_data.shape

    def set_fixed_values(self, fixed_values):
        """
        Sets the fixed and not fitted values for the geometry refinement
        :param fixed_values: a dictionary with the fixed parameters as key and their corresponding fixed value, possible
                             keys: 'dist', 'rot1', 'rot2', 'rot3', 'poni1', 'poni2'

        """
        self.fixed_values = fixed_values

    def calibrate(self):
        if len(self.points) == 0:
            raise NoPointsError("No starting points for calibration found.")

        self.reset_supersampling()
        self.pattern_geometry = GeometryRefinement(
            self.create_point_array(self.points, self.points_index),
            dist=self.start_values["dist"],
            wavelength=self.start_values["wavelength"],
            detector=self.detector,
            calibrant=self.calibrant,
            splineFile=self.distortion_spline_filename,
        )

        self.refine()
        self.create_cake_geometry()
        self.is_calibrated = True

        self.calibration_name = "current"
        self.set_supersampling()
        # reset the integrator (not the geometric parameters)
        self.pattern_geometry.reset()

    def refine(self):
        if len(self.points) == 0:
            raise NoPointsError("No points for refinement found.")

        self.reset_supersampling()
        self.pattern_geometry.data = self.create_point_array(
            self.points, self.points_index
        )

        fix = ["wavelength"]
        if self.fit_wavelength:
            fix = []

        for key, value in self.fixed_values.items():
            fix.append(key)
            setattr(self.pattern_geometry, key, value)

        self.pattern_geometry.refine2(fix=fix)
        if self.fit_wavelength:
            self.pattern_geometry.refine2_wavelength(fix=fix)

        self.create_cake_geometry()
        self.set_supersampling()
        # reset the integrator (not the geometric parameters)
        self.pattern_geometry.reset()

    def _check_detector_and_image_shape(self):
        if self.detector.shape is not None:
            if self.detector.shape != self.img_model.img_data.shape:
                self.reset_detector()
                self.detector_reset.emit()
        else:
            self.reset_detector()

    def _prepare_integration_mask(self, mask):
        if mask is None:
            return self.detector.mask
        else:
            if self.detector.mask is None:
                return mask
            else:
                if mask.shape == self.detector.mask.shape:
                    return np.logical_or(self.detector.mask, mask)

    def _prepare_integration_super_sampling(self, mask):
        if self.supersampling_factor > 1:
            img_data = supersample_image(
                self.img_model.img_data, self.supersampling_factor
            )
            if mask is not None:
                mask = supersample_image(mask, self.supersampling_factor)
        else:
            img_data = self.img_model.img_data
        return img_data, mask

    def integrate_1d(
        self,
        num_points=None,
        mask=None,
        polarization_factor=None,
        filename=None,
        unit="2th_deg",
        method="csr",
        azi_range=None,
        trim_zeros=True,
    ):
        """
        :param num_points: number of points for the integration
        :param mask: mask for the integration
        :param polarization_factor: polarization factor for the integration
        :param filename: filename for saving the integration
        :param unit: unit for the integration, possible values are '2th_deg', 'q_A^-1', 'r_mm', 'r_m', 'd_A'
        :param method: method for the integration, possible values are 'csr', 'splitbbox', 'lut', 'nosplit_csr',
                          'full_csr', 'numpy', 'cython', 'BBox', 'splitPixel', 'lut_ocl', 'csr_ocl', 'csr_ocl_memsave',
                            'csr_ocl_lut', 'csr_ocl_lut_memsave', 'csr_numpy', 'csr_numpy_memsave'
        :param azi_range: azimuthal range for the integration
        :param trim_zeros: if True, the trailing zeros in the integration will be trimmed
        :return: tth, intensity
        """
        if (
            np.sum(mask)
            == self.img_model.img_data.shape[0] * self.img_model.img_data.shape[1]
        ):
            # do not perform integration if the image is completely masked...
            return self.tth, self.int

        if self.pattern_geometry_img_shape != self.img_model.img_data.shape:
            # if cake geometry was used on differently shaped image before the azimuthal integrator needs to be reset
            self.pattern_geometry.reset()
            self.pattern_geometry_img_shape = self.img_model.img_data.shape

        if polarization_factor is None:
            polarization_factor = self.polarization_factor

        self._check_detector_and_image_shape()
        mask = self._prepare_integration_mask(mask)
        img_data, mask = self._prepare_integration_super_sampling(mask)

        if num_points is None:
            num_points = self.calculate_number_of_pattern_points(img_data.shape, 2)

        self.num_points = num_points

        t1 = time.time()

        if unit == "d_A":
            try:
                self.tth, self.int = self.pattern_geometry.integrate1d(
                    img_data,
                    num_points,
                    method=method,
                    unit="2th_deg",
                    azimuth_range=azi_range,
                    mask=mask,
                    polarization_factor=polarization_factor,
                    correctSolidAngle=self.correct_solid_angle,
                    filename=filename,
                )
            except NameError:
                self.tth, self.int = self.pattern_geometry.integrate1d(
                    img_data,
                    num_points,
                    method="csr",
                    unit="2th_deg",
                    azimuth_range=azi_range,
                    mask=mask,
                    polarization_factor=polarization_factor,
                    correctSolidAngle=self.correct_solid_angle,
                    filename=filename,
                )
            self.tth = (
                self.pattern_geometry.wavelength
                / (2 * np.sin(self.tth / 360 * np.pi))
                * 1e10
            )
            self.int = self.int
        else:
            try:
                self.tth, self.int = self.pattern_geometry.integrate1d(
                    img_data,
                    num_points,
                    method=method,
                    unit=unit,
                    azimuth_range=azi_range,
                    mask=mask,
                    polarization_factor=polarization_factor,
                    correctSolidAngle=self.correct_solid_angle,
                    filename=filename,
                )
            except NameError:
                self.tth, self.int = self.pattern_geometry.integrate1d(
                    img_data,
                    num_points,
                    method="csr",
                    unit=unit,
                    azimuth_range=azi_range,
                    mask=mask,
                    polarization_factor=polarization_factor,
                    correctSolidAngle=self.correct_solid_angle,
                    filename=filename,
                )
        logger.info(
            "1d integration of {0}: {1}s.".format(
                os.path.basename(self.img_model.filename), time.time() - t1
            )
        )

        if (
            np.sum(self.int) != 0 and trim_zeros
        ):  # only trim zeros if not everything is 0 (e.g. bkg-subtraction of the same image)
            self.tth, self.int = trim_trailing_zeros(self.tth, self.int)

        return self.tth, self.int

    def integrate_2d(
        self,
        mask=None,
        polarization_factor=None,
        unit="2th_deg",
        method="csr",
        rad_points=None,
        azimuth_points=360,
        azimuth_range=None,
    ):
        if polarization_factor is None:
            polarization_factor = self.polarization_factor

        if self.cake_geometry_img_shape != self.img_model.img_data.shape:
            # if cake geometry was used on differently shaped image before the azimuthal integrator needs to be reset
            self.cake_geometry.reset()
            self.cake_geometry_img_shape = self.img_model.img_data.shape

        self._check_detector_and_image_shape()
        mask = self._prepare_integration_mask(mask)
        img_data, mask = self._prepare_integration_super_sampling(mask)

        if rad_points is None:
            rad_points = self.calculate_number_of_pattern_points(img_data.shape, 2)
        self.num_points = rad_points

        t1 = time.time()

        res = self.cake_geometry.integrate2d(
            img_data,
            rad_points,
            azimuth_points,
            azimuth_range=azimuth_range,
            method=method,
            mask=mask,
            unit=unit,
            polarization_factor=polarization_factor,
            correctSolidAngle=self.correct_solid_angle,
        )
        logger.info(
            "2d integration of {0}: {1}s.".format(
                os.path.basename(self.img_model.filename), time.time() - t1
            )
        )
        self.cake_img = res[0]
        self.cake_tth = res[1]
        self.cake_azi = res[2]
        return self.cake_img

    def cake_integral(self, tth, bins=1):
        """
        calculates a histogram of the cake in tth direction, thus the result will be pixel vs intensity
        :param tth: tth value in A^-1
        :param bins: number of bins for summing
        :return: cake_azimuth_pixel, intensity
        """
        tth_partial_index = get_partial_index(self.cake_tth, tth)
        if tth_partial_index is None:
            return [], []

        tth_center = tth_partial_index + 0.5
        left = tth_center - 0.5 * bins
        right = tth_center + 0.5 * bins

        y1 = abs(np.ceil(left) - left) * self.cake_img[:, int(np.floor(left))]
        y2 = np.sum(self.cake_img[:, int(np.ceil(left)) : int(np.floor(right))], axis=1)
        y3 = (right - np.floor(right)) * self.cake_img[:, int(np.floor(right))]

        x = np.array(range(len(self.cake_azi))) + 0.5
        y = (y1 + y2 + y3) / bins
        return x, y

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
        pyFAI_parameter = self.pattern_geometry.getPyFAI()
        pyFAI_parameter["polarization_factor"] = self.polarization_factor
        try:
            fit2d_parameter = self.pattern_geometry.getFit2D()
            fit2d_parameter["polarization_factor"] = self.polarization_factor
        except TypeError:
            fit2d_parameter = None

        pyFAI_parameter["wavelength"] = self.pattern_geometry.wavelength
        if fit2d_parameter:
            fit2d_parameter["wavelength"] = self.pattern_geometry.wavelength

        return pyFAI_parameter, fit2d_parameter

    def calculate_number_of_pattern_points(self, img_shape, max_dist_factor=1.5):
        # calculates the number of points for an integrated pattern, based on the distance of the beam center to the the
        # image corners. Maximum value is determined by the shape of the image.
        fit2d_parameter = self.pattern_geometry.getFit2D()
        center_x = fit2d_parameter["centerX"]
        center_y = fit2d_parameter["centerY"]
        width, height = img_shape

        if width > center_x > 0:
            side1 = np.max([abs(width - center_x), center_x])
        else:
            side1 = width

        if center_y < height and center_y > 0:
            side2 = np.max([abs(height - center_y), center_y])
        else:
            side2 = height
        max_dist = np.sqrt(side1**2 + side2**2)
        return int(max_dist * max_dist_factor)

    def load(self, filename):
        """
        Loads a calibration file andsets all the calibration parameter.
        :param filename: filename for a *.poni calibration file
        """
        self.pattern_geometry = GeometryRefinement(
            wavelength=0.3344e-10, detector=self.detector, poni1=0, poni2=0
        )  # default params are necessary, otherwise fails...
        self.pattern_geometry.load(filename)
        self.orig_pixel1 = self.pattern_geometry.pixel1
        self.orig_pixel2 = self.pattern_geometry.pixel2

        if (
            self.pattern_geometry.pixel1 == self.detector.pixel1
            and self.pattern_geometry.pixel2 == self.detector.pixel2
        ):
            self.pattern_geometry.detector = (
                self.detector
            )  # necessary since loading a poni file will reset the detector
        else:
            self.reset_detector()

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

    def load_detector(self, name):
        self.detector_mode = DetectorModes.PREDEFINED
        names, classes = get_available_detectors()
        detector_ind = names.index(name)

        self._load_detector(classes[detector_ind]())

    def load_detector_from_file(self, filename):
        self.detector_mode = DetectorModes.NEXUS
        self._load_detector(NexusDetector(filename))

    def _load_detector(self, detector):
        """Loads a pyFAI detector
        :param detector: an instance of pyFAI Detector
        """
        self.detector = detector
        self.detector.calc_mask()
        self.orig_pixel1 = self.detector.pixel1
        self.orig_pixel2 = self.detector.pixel2

        self.pattern_geometry.detector = self.detector

        if self.cake_geometry:
            self.cake_geometry.detector = self.detector

        self.set_supersampling()
        self._original_detector = None

    def reset_detector(self):
        self.detector_mode = DetectorModes.CUSTOM
        self.detector = Detector(
            pixel1=self.detector.pixel1, pixel2=self.detector.pixel2
        )
        self.update_detector_shape()
        self.pattern_geometry.detector = self.detector
        if self.cake_geometry:
            self.cake_geometry.detector = self.detector
        self.set_supersampling()

    def create_file_header(self):
        try:
            # pyFAI version 0.12.0
            return self.pattern_geometry.makeHeaders(
                polarization_factor=self.polarization_factor
            )
        except AttributeError:
            # pyFAI after version 0.12.0
            from pyFAI.io import DefaultAiWriter

            return DefaultAiWriter(None, self.pattern_geometry).make_headers()

    def set_fit2d(self, fit2d_parameter):
        """
        Reads in a dictionary with fit2d parameters where the fields of the dictionary are:
        'directDist', 'centerX', 'centerY', 'tilt', 'tiltPlanRotation', 'pixelX', pixelY',
        'polarization_factor', 'wavelength'
        """
        self.pattern_geometry.setFit2D(
            directDist=fit2d_parameter["directDist"],
            centerX=fit2d_parameter["centerX"],
            centerY=fit2d_parameter["centerY"],
            tilt=fit2d_parameter["tilt"],
            tiltPlanRotation=fit2d_parameter["tiltPlanRotation"],
            pixelX=fit2d_parameter["pixelX"],
            pixelY=fit2d_parameter["pixelY"],
        )
        # the detector pixel1 and pixel2 values are updated by setPyFAI
        self.orig_pixel1 = self.detector.pixel1
        self.orig_pixel2 = self.detector.pixel2

        self.pattern_geometry.wavelength = fit2d_parameter["wavelength"]
        self.create_cake_geometry()
        self.polarization_factor = fit2d_parameter["polarization_factor"]
        self.orig_pixel1 = fit2d_parameter["pixelX"] * 1e-6
        self.orig_pixel2 = fit2d_parameter["pixelY"] * 1e-6
        self.is_calibrated = True
        self.set_supersampling()

    def set_pyFAI(self, pyFAI_parameter):
        """
        Reads in a dictionary with pyFAI parameters where the fields of dictionary are:
        'dist', 'poni1', 'poni2', 'rot1', 'rot2', 'rot3', 'pixel1', 'pixel2', 'wavelength',
        'polarization_factor'
        """
        self.pattern_geometry.setPyFAI(
            dist=pyFAI_parameter["dist"],
            poni1=pyFAI_parameter["poni1"],
            poni2=pyFAI_parameter["poni2"],
            rot1=pyFAI_parameter["rot1"],
            rot2=pyFAI_parameter["rot2"],
            rot3=pyFAI_parameter["rot3"],
            pixel1=pyFAI_parameter["pixel1"],
            pixel2=pyFAI_parameter["pixel2"],
        )
        self.detector.pixel1 = pyFAI_parameter["pixel1"]
        self.detector.pixel2 = pyFAI_parameter["pixel2"]
        self.orig_pixel1 = self.detector.pixel1
        self.orig_pixel2 = self.detector.pixel2
        self.pattern_geometry.wavelength = pyFAI_parameter["wavelength"]
        self.create_cake_geometry()
        self.polarization_factor = pyFAI_parameter["polarization_factor"]
        self.is_calibrated = True
        self.set_supersampling()

    def load_distortion(self, spline_filename):
        self.distortion_spline_filename = spline_filename
        self.pattern_geometry.set_splineFile(spline_filename)
        if self.cake_geometry:
            self.cake_geometry.set_splineFile(spline_filename)

    def reset_distortion_correction(self):
        self.distortion_spline_filename = None
        self.detector.set_splineFile(None)
        self.pattern_geometry.set_splineFile(None)
        if self.cake_geometry:
            self.cake_geometry.set_splineFile(None)

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

        self.detector.pixel1 = self.orig_pixel1 / float(factor)
        self.detector.pixel2 = self.orig_pixel2 / float(factor)
        self.pattern_geometry.pixel1 = self.orig_pixel1 / float(factor)
        self.pattern_geometry.pixel2 = self.orig_pixel2 / float(factor)

        if factor != self.supersampling_factor:
            self.pattern_geometry.reset()
            self.supersampling_factor = factor

    def reset_supersampling(self):
        self.pattern_geometry.pixel1 = self.orig_pixel1
        self.pattern_geometry.pixel2 = self.orig_pixel2
        self.detector.pixel1 = self.orig_pixel1
        self.detector.pixel2 = self.orig_pixel2

    def get_two_theta_img(self, x, y):
        """
        Gives the two_theta value for the x,y coordinates on the image. Be aware that this function will be incorrect
        for pixel indices, since it does not correct for center of the pixel.
        :param  x: x-coordinate in pixel on the image
        :type   x: ndarray
        :param  y: y-coordinate in pixel on the image
        :type   y: ndarray

        :return  : two theta in radians
        """
        if not isinstance(x, np.ndarray):
            x = np.array([x])
        if not isinstance(y, np.ndarray):
            y = np.array([y])
        x *= self.supersampling_factor
        y *= self.supersampling_factor

        return self.pattern_geometry.tth(x - 0.5, y - 0.5)[
            0
        ]  # deletes 0.5 because tth function uses pixel indices

    def get_azi_img(self, x, y):
        """
        Gives chi for position on image.
        :param  x: x-coordinate in pixel on the image
        :type   x: ndarray
        :param  y: y-coordinate in pixel on the image
        :type   y: ndarray

        :return  : azimuth in radians
        """
        # if float convert to np.array:
        if not isinstance(x, np.ndarray):
            x = np.array([x])
        if not isinstance(y, np.ndarray):
            y = np.array([y])
        x *= self.supersampling_factor
        y *= self.supersampling_factor
        return self.pattern_geometry.chi(x - 0.5, y - 0.5)[0]

    def get_two_theta_array(self):
        return self.pattern_geometry.twoThetaArray(self.img_model.img_data.shape)[
            :: self.supersampling_factor, :: self.supersampling_factor
        ]

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
        tth_ind = find_contours(self.pattern_geometry.ttha, tth)
        if len(tth_ind) == 0:
            return []
        tth_ind = np.vstack(tth_ind)
        azi_values = self.pattern_geometry.chi(tth_ind[:, 0], tth_ind[:, 1])
        min_index = np.argmin(np.abs(azi_values - azi))
        return tth_ind[min_index, 0], tth_ind[min_index, 1]

    @property
    def wavelength(self):
        return self.pattern_geometry.wavelength

    ##########################
    ## Detector rotation stuff
    def swap_detector_shape(self):
        self._swap_detector_shape()
        self._swap_pixel_size()
        self._swap_detector_module_size()

    def rotate_detector_m90(self):
        """
        Rotates the detector stuff by m90 degree. This includes swapping of shape, pixel size and module sizes, as well
        as dx and dy
        """
        self._save_original_detector_definition()

        self.swap_detector_shape()
        self._reset_detector_mask()
        self._transform_pixel_corners(rotate_matrix_m90)

    def rotate_detector_p90(self):
        """ """
        self._save_original_detector_definition()

        self.swap_detector_shape()
        self._reset_detector_mask()
        self._transform_pixel_corners(rotate_matrix_p90)

    def flip_detector_horizontally(self):
        self._save_original_detector_definition()
        self._transform_pixel_corners(np.fliplr)

    def flip_detector_vertically(self):
        self._save_original_detector_definition()
        self._transform_pixel_corners(np.flipud)

    def reset_transformations(self):
        """Restores the detector to it's original state"""
        if self._original_detector is None:  # no transformations done so far
            return

        self.detector = deepcopy(self._original_detector)
        self.orig_pixel1, self.orig_pixel2 = self.detector.pixel1, self.detector.pixel2
        self.pattern_geometry.detector = self.detector
        if self.cake_geometry is not None:
            self.cake_geometry.detector = self.detector
        self.set_supersampling()
        self._original_detector = None

    def load_transformations_string_list(self, transformations):
        """Transforms the detector parameters (shape, pixel size and distortion correction) based on a
        list of transformation actions.
        :param transformations: list of transformations specified as strings, values are "flipud", "fliplr",
                                "rotate_matrix_m90", "rotate_matrix_p90
        """
        for transformation in transformations:
            if transformation == "flipud":
                self.flip_detector_vertically()
            elif transformation == "fliplr":
                self.flip_detector_horizontally()
            elif transformation == "rotate_matrix_m90":
                self.rotate_detector_m90()
            elif transformation == "rotate_matrix_p90":
                self.rotate_detector_p90()

    def _save_original_detector_definition(self):
        """
        Saves the state of the detector to _original_detector if not done yet. Used for restoration upon resetting
        the transformations.
        """
        if self._original_detector is None:
            self._original_detector = deepcopy(self.detector)
            self._original_detector.pixel1 = self.orig_pixel1
            self._original_detector.pixel2 = self.orig_pixel2
            self._mask = False

    def _transform_pixel_corners(self, transform_function):
        """
        :param transform_function: function pointer which will affect the dx, dy and pixel corners of the detector
        """
        if self.detector._pixel_corners is not None:
            self.detector._pixel_corners = np.ascontiguousarray(
                transform_function(self.detector.get_pixel_corners())
            )

    def _swap_pixel_size(self):
        """swaps the pixel sizes"""
        self.orig_pixel1, self.orig_pixel2 = self.orig_pixel2, self.orig_pixel1
        self.set_supersampling()

    def _swap_detector_shape(self):
        """Swaps the detector shape and max_shape values"""
        if self.detector.shape is not None:
            self.detector.shape = (self.detector.shape[1], self.detector.shape[0])
        if self.detector.max_shape is not None:
            self.detector.max_shape = (
                self.detector.max_shape[1],
                self.detector.max_shape[0],
            )

    def _swap_detector_module_size(self):
        """swaps the module size and gap sizes for e.g. Pilatus Detectors"""
        if hasattr(self.detector, "module_size"):
            self.detector.module_size = (
                self.detector.module_size[1],
                self.detector.module_size[0],
            )
        if hasattr(self.detector, "MODULE_GAP"):
            self.detector.MODULE_GAP = (
                self.detector.MODULE_GAP[1],
                self.detector.MODULE_GAP[0],
            )

    def _reset_detector_mask(self):
        """resets and recalculates the mask. Transformations to shape and module size have to be performed before."""
        self.detector._mask = False


class DetectorModes(Enum):
    CUSTOM = 1
    NEXUS = 2
    PREDEFINED = 3


class NotEnoughSpacingsInCalibrant(Exception):
    pass


class DetectorShapeError(Exception):
    pass


class NoPointsError(Exception):
    pass


class DummyStdOut(object):
    @classmethod
    def write(cls, *args, **kwargs):
        pass


def get_available_detectors():
    detector_classes = set()
    detector_names = []

    for key, item in ALL_DETECTORS.items():
        detector_classes.add(item)

    for detector in detector_classes:
        if len(detector.aliases) > 0:
            detector_names.append(detector.aliases[0])
        else:
            detector_names.append(detector().__class__.__name__)

    sorted_indices = sorted(range(len(detector_names)), key=detector_names.__getitem__)

    detector_names_sorted = [detector_names[i] for i in sorted_indices]
    detector_classes_sorted = [list(detector_classes)[i] for i in sorted_indices]

    base_class_index = detector_names_sorted.index("Detector")
    del detector_names_sorted[base_class_index]
    del detector_classes_sorted[base_class_index]

    return detector_names_sorted, detector_classes_sorted
