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

import unittest
import gc

import numpy as np
import pytest

from ...model.util.ImgCorrection import ImgCorrectionManager, ImgCorrectionInterface, \
    ObliqueAngleDetectorAbsorptionCorrection
from ...model.util.ImgCorrection import TransferFunctionCorrection, load_image
from ..utility import unittest_data_path

from pyFAI.azimuthalIntegrator import AzimuthalIntegrator
from ...model.util.ImgCorrection import CbnCorrection


class DummyCorrection(ImgCorrectionInterface):
    def __init__(self, shape, number=1):
        self._data = np.ones(shape) * number
        self._shape = shape

    def get_data(self):
        return self._data

    def shape(self):
        return self._shape


@pytest.fixture
def corrections():
    return ImgCorrectionManager()


def test_add_first_matrix_and_detect_shape(corrections):
    cor = DummyCorrection((2048, 2048))

    corrections.add(cor)

    assert np.array_equal(cor.get_data(), corrections.get_data())
    assert corrections.shape == (2048, 2048)


def test_add_several_corrections(corrections):
    cor1 = DummyCorrection((2048, 2048), 2)
    cor2 = DummyCorrection((2048, 2048), 3)
    cor3 = DummyCorrection((2048, 2048), 5)

    corrections.add(cor1)
    corrections.add(cor2)
    corrections.add(cor3)

    assert np.mean(corrections.get_data()) == 2 * 3 * 5


def test_delete_corrections_without_names(corrections):
    assert corrections.get_data() is None

    corrections.add(DummyCorrection((2048, 2048), 3))
    corrections.delete()
    assert corrections.get_data() is None

    corrections.add(DummyCorrection((2048, 2048), 2))
    corrections.add(DummyCorrection((2048, 2048), 3))

    corrections.delete()
    assert np.mean(corrections.get_data()) == 2
    corrections.delete()


def test_delete_corrections_with_names(corrections):
    # add two corrections and check if both applied
    corrections.add(DummyCorrection((2048, 2048), 3), "cbn Correction")
    corrections.add(DummyCorrection((2048, 2048), 5), "oblique angle Correction")
    assert np.mean(corrections.get_data()) == 3 * 5

    # delete the first by name
    corrections.delete("cbn Correction")
    assert np.mean(corrections.get_data()) == 5

    # trying to delete non-existent name will result in KeyError
    with pytest.raises(KeyError):
        corrections.delete("blub")

    # just deleting something, when all corrections have a name will not change anything
    corrections.delete()
    assert np.mean(corrections.get_data()) == 5


class CbnCorrectionTest(unittest.TestCase):
    def setUp(self):
        # defining geometry
        image_shape = [2048, 2048]  # pixel
        detector_distance = 200  # mm
        wavelength = 0.31  # angstrom
        center_x = 1024  # pixel
        center_y = 1024  # pixel
        tilt = 0  # degree
        rotation = 0  # degree
        pixel_size = 79  # um
        dummy_tth = np.linspace(0, 35, 2000)
        dummy_int = np.ones(dummy_tth.shape)
        self.geometry = AzimuthalIntegrator()
        self.geometry.setFit2D(directDist=detector_distance,
                               centerX=center_x,
                               centerY=center_y,
                               tilt=tilt,
                               tiltPlanRotation=rotation,
                               pixelX=pixel_size,
                               pixelY=pixel_size)
        self.geometry.wavelength = wavelength / 1e10
        self.dummy_img = self.geometry.calcfrom1d(dummy_tth, dummy_int, shape=image_shape, correctSolidAngle=True)

        self.tth_array = self.geometry.twoThetaArray(image_shape)
        self.azi_array = self.geometry.chiArray(image_shape)

    def tearDown(self):
        del self.tth_array
        del self.azi_array
        del self.dummy_img
        del self.geometry
        gc.collect()

    def test_that_it_is_calculating_correctly(self):
        cbn_correction = CbnCorrection(self.tth_array, self.azi_array,
                                       diamond_thickness=2.2,
                                       seat_thickness=5.3,
                                       small_cbn_seat_radius=0.4,
                                       large_cbn_seat_radius=1.95,
                                       tilt=0,
                                       tilt_rotation=0)
        cbn_correction.update()
        cbn_correction_data = cbn_correction.get_data()
        self.assertGreater(np.sum(cbn_correction_data), 0)
        self.assertEqual(cbn_correction_data.shape, self.dummy_img.shape)


from ...model.CalibrationModel import CalibrationModel
from ...model.ImgModel import ImgModel
from ...model.MaskModel import MaskModel
from lmfit import Parameters, minimize, report_fit
from scipy.ndimage import gaussian_filter1d
import os
import matplotlib.pyplot as plt


@unittest.skip("Optimization takes forever...")
class CbnAbsorptionCorrectionOptimizationTest(unittest.TestCase):
    def setUp(self):
        # creating Data objects
        self.img_data = ImgModel()
        self.img_data.load("Data/CbnCorrectionOptimization/Mg2SiO4_091.tif")
        self.calibration_data = CalibrationModel(self.img_data)
        self.calibration_data.load("Data/CbnCorrectionOptimization/LaB6_40keV side.poni")
        self.mask_data = MaskModel()
        self.mask_data.load_mask("Data/CbnCorrectionOptimization/Mg2SiO4_91_combined.mask")

        # creating the ObliqueAngleDetectorAbsorptionCorrection
        _, fit2d_parameter = self.calibration_data.get_calibration_parameter()
        detector_tilt = fit2d_parameter['tilt']
        detector_tilt_rotation = fit2d_parameter['tiltPlanRotation']

        self.tth_array = self.calibration_data.pattern_geometry.twoThetaArray((2048, 2048))
        self.azi_array = self.calibration_data.pattern_geometry.chiArray((2048, 2048))

        self.oiadac_correction = ObliqueAngleDetectorAbsorptionCorrection(
            self.tth_array, self.azi_array,
            detector_thickness=40,
            absorption_length=465.5,
            tilt=detector_tilt,
            rotation=detector_tilt_rotation,
        )
        self.img_data.add_img_correction(self.oiadac_correction, "oiadac")

    def tearDown(self):
        del self.calibration_data.cake_geometry
        del self.calibration_data.pattern_geometry

    def test_the_world(self):
        params = Parameters()
        params.add("diamond_thickness", value=2, min=1.9, max=2.3)
        params.add("seat_thickness", value=5.3, min=4.0, max=6.6, vary=False)
        params.add("small_cbn_seat_radius", value=0.2, min=0.10, max=0.5, vary=True)
        params.add("large_cbn_seat_radius", value=1.95, min=1.85, max=2.05, vary=False)
        params.add("tilt", value=3.3, min=0, max=8)
        params.add("tilt_rotation", value=0, min=-15, max=+15)
        params.add("cbn_abs_length", value=14.05, min=12, max=16)

        region = [8, 26]

        self.tth_array = 180.0 / np.pi * self.tth_array
        self.azi_array = 180.0 / np.pi * self.azi_array

        def fcn2min(params):
            cbn_correction = CbnCorrection(
                tth_array=self.tth_array,
                azi_array=self.azi_array,
                diamond_thickness=params['diamond_thickness'].value,
                seat_thickness=params['seat_thickness'].value,
                small_cbn_seat_radius=params['small_cbn_seat_radius'].value,
                large_cbn_seat_radius=params['large_cbn_seat_radius'].value,
                tilt=params['tilt'].value,
                tilt_rotation=params['tilt_rotation'].value,
                cbn_abs_length=params["cbn_abs_length"].value
            )
            self.img_data.add_img_correction(cbn_correction, "cbn")
            tth, int = self.calibration_data.integrate_1d(mask=self.mask_data.get_mask())
            self.img_data.delete_img_correction("cbn")
            ind = np.where((tth > region[0]) & (tth < region[1]))
            int = gaussian_filter1d(int, 20)
            return (np.diff(int[ind])) ** 2

        def output_values(param1, iteration, residual):
            report_fit(param1)

        result = minimize(fcn2min, params, iter_cb=output_values)
        report_fit(params)

        # plotting result:
        cbn_correction = CbnCorrection(
            tth_array=self.tth_array,
            azi_array=self.azi_array,
            diamond_thickness=params['diamond_thickness'].value,
            seat_thickness=params['seat_thickness'].value,
            small_cbn_seat_radius=params['small_cbn_seat_radius'].value,
            large_cbn_seat_radius=params['large_cbn_seat_radius'].value,
            tilt=params['tilt'].value,
            tilt_rotation=params['tilt_rotation'].value,
            cbn_abs_length=params['cbn_abs_length'].value
        )
        self.img_data.add_img_correction(cbn_correction, "cbn")
        tth, int = self.calibration_data.integrate_1d(mask=self.mask_data.get_mask())
        ind = np.where((tth > region[0]) & (tth < region[1]))
        tth = tth[ind]
        int = int[ind]
        int_smooth = gaussian_filter1d(int, 10)

        int_diff1 = np.diff(int)
        int_diff1_smooth = np.diff(int_smooth)
        int_diff2 = np.diff(int_diff1)
        int_diff2_smooth = np.diff(int_diff1_smooth)

        plt.figure()
        plt.subplot(3, 1, 1)
        plt.plot(tth, int)
        plt.plot(tth, int_smooth)
        plt.subplot(3, 1, 2)
        plt.plot(int_diff1)
        plt.plot(int_diff1_smooth)
        plt.subplot(3, 1, 3)
        plt.plot(int_diff2)
        plt.plot(int_diff2_smooth)
        plt.savefig("Results/optimize_cbn_absorption.png", dpi=300)

        os.system("open " + "Results/optimize_cbn_absorption.png")


class ObliqueAngleDetectorAbsorptionCorrectionTest(unittest.TestCase):
    def setUp(self):
        # defining geometry
        image_shape = [2048, 2048]  # pixel
        detector_distance = 200  # mm
        wavelength = 0.31  # angstrom
        center_x = 1024  # pixel
        center_y = 1024  # pixel
        self.tilt = 0  # degree
        self.rotation = 0  # degree
        pixel_size = 79  # um
        dummy_tth = np.linspace(0, 35, 2000)
        dummy_int = np.ones(dummy_tth.shape)
        self.geometry = AzimuthalIntegrator()
        self.geometry.setFit2D(directDist=detector_distance,
                               centerX=center_x,
                               centerY=center_y,
                               tilt=self.tilt,
                               tiltPlanRotation=self.rotation,
                               pixelX=pixel_size,
                               pixelY=pixel_size)
        self.geometry.wavelength = wavelength / 1e10
        self.dummy_img = self.geometry.calcfrom1d(dummy_tth, dummy_int, shape=image_shape, correctSolidAngle=True)

        self.tth_array = self.geometry.twoThetaArray(image_shape)
        self.azi_array = self.geometry.chiArray(image_shape)

    def tearDown(self):
        del self.azi_array
        del self.tth_array
        del self.dummy_img
        del self.geometry
        gc.collect()

    def test_that_it_is_correctly_calculating(self):
        oblique_correction = ObliqueAngleDetectorAbsorptionCorrection(
            tth_array=self.tth_array,
            azi_array=self.azi_array,
            detector_thickness=40,
            absorption_length=465.5,
            tilt=self.tilt,
            rotation=self.rotation
        )
        oblique_correction_data = oblique_correction.get_data()
        self.assertGreater(np.sum(oblique_correction_data), 0)
        self.assertEqual(oblique_correction_data.shape, self.dummy_img.shape)
        del oblique_correction


class TransferFunctionCorrectionTest(unittest.TestCase):
    def setUp(self):
        self.original_image_filename = os.path.join(unittest_data_path, 'TransferCorrection', 'original.tif')
        self.response_image_filename = os.path.join(unittest_data_path, 'TransferCorrection', 'response.tif')
        self.original_data = load_image(self.original_image_filename)
        self.response_data = load_image(self.response_image_filename)

        self.transfer_correction = TransferFunctionCorrection(self.original_image_filename,
                                                              self.response_image_filename)

    def test_general_behavior(self):
        transfer_data = self.transfer_correction.get_data()
        self.assertEqual(transfer_data.shape, self.original_data.shape)
        self.assertEqual(transfer_data.shape, self.response_data.shape)
        self.assertAlmostEqual(np.sum(transfer_data - self.response_data / self.original_data), 0)

    def test_apply_img_transformations(self):
        from ...model.util.HelperModule import rotate_matrix_m90
        img_transformations = [np.fliplr, rotate_matrix_m90]
        self.transfer_correction.set_img_transformations(img_transformations)

        transfer_data = self.transfer_correction.get_data()
        self.assertNotEqual(transfer_data, self.original_data)
        self.assertNotEqual(transfer_data, self.response_data)
