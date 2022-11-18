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
from mock import MagicMock

from pyFAI import detectors
from pyFAI.detectors import Detector

from ..utility import QtTest, delete_if_exists
from ...model.CalibrationModel import CalibrationModel, get_available_detectors, DetectorModes, DetectorShapeError
from ...model.ImgModel import ImgModel
from ... import calibrants_path
import gc

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')


class CalibrationModelTestWithIntegration(QtTest):
    def setUp(self) -> None:
        self.img_model = ImgModel()
        self.calibration_model = CalibrationModel(self.img_model)

    def tearDown(self):
        delete_if_exists(os.path.join(data_path, 'detector_with_spline.h5'))
        del self.img_model
        if hasattr(self.calibration_model, 'cake_geometry'):
            del self.calibration_model.cake_geometry
        del self.calibration_model.pattern_geometry
        del self.calibration_model
        gc.collect()

    def load_pilatus_1M(self):
        self.img_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.tif'))

    def load_pilatus_1M_with_calibration(self):
        self.calibration_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.poni'))
        self.load_pilatus_1M()

    def load_LaB6_40keV_with_calibration(self):
        self.img_model.load(os.path.join(data_path, 'image_001.tif'))
        self.calibration_model.load(os.path.join(data_path, 'LaB6_40keV_MarCCD.poni'))

    def test_integration_with_supersampling(self):
        self.load_pilatus_1M_with_calibration()
        x1, y1 = self.calibration_model.integrate_1d()

        self.calibration_model.set_supersampling(2)
        x2, y2 = self.calibration_model.integrate_1d()

        self.assertGreater(len(y2), len(y1))
        y1_2_interp = np.interp(x2, x1, y1)

        self.assertAlmostEqual(np.mean((y2 - y1_2_interp)), 0, places=2)

    def test_get_pixel_ind(self):
        self.load_LaB6_40keV_with_calibration()

        self.calibration_model.integrate_1d(1000)

        tth_array = self.calibration_model.pattern_geometry.ttha
        azi_array = self.calibration_model.pattern_geometry.chia

        for i in range(100):
            ind1 = np.random.randint(0, 2024)
            ind2 = np.random.randint(0, 2024)

            tth = tth_array[ind1, ind2]
            azi = azi_array[ind1, ind2]

            result_ind1, result_ind2 = self.calibration_model.get_pixel_ind(tth, azi)

            self.assertAlmostEqual(ind1, result_ind1, places=3)
            self.assertAlmostEqual(ind2, result_ind2, places=3)

    def test_use_different_image_sizes_for_1d_integration(self):
        self.calibration_model.load(os.path.join(data_path, 'LaB6_40keV_MarCCD.poni'))
        self.calibration_model.integrate_1d()
        self.img_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.tif'))
        self.calibration_model.integrate_1d()

    def test_use_different_image_sizes_for_2d_integration(self):
        self.calibration_model.load(os.path.join(data_path, 'LaB6_40keV_MarCCD.poni'))
        self.calibration_model.integrate_2d()
        self.img_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.tif'))
        self.calibration_model.integrate_2d()

    def test_correct_solid_angle(self):
        self.calibration_model.load(os.path.join(data_path, 'LaB6_40keV_MarCCD.poni'))
        self.img_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.tif'))
        _, y1 = self.calibration_model.integrate_1d()
        self.calibration_model.correct_solid_angle = False
        _, y2 = self.calibration_model.integrate_1d()
        self.assertNotEqual(np.sum(y1), np.sum(y2))

    def test_distortion_correction(self):
        self.img_model.load(os.path.join(data_path, 'distortion', 'CeO2_calib.edf'))

        self.calibration_model.find_peaks_automatic(1025.1, 1226.8, 0)
        self.calibration_model.set_calibrant(os.path.join(calibrants_path, 'CeO2.D'))
        self.calibration_model.start_values['dist'] = 300e-3
        self.calibration_model.detector.pixel1 = 50e-6
        self.calibration_model.detector.pixel2 = 50e-6
        self.calibration_model.start_values['wavelength'] = 0.1e-10

        self.calibration_model.calibrate()

        _, y1 = self.calibration_model.integrate_1d()

        self.calibration_model.load_distortion(os.path.join(data_path, 'distortion', 'f4mnew.spline'))
        self.calibration_model.calibrate()

        _, y2 = self.calibration_model.integrate_1d()
        self.assertNotAlmostEqual(y1[100], y2[100])

    def test_cake_integral(self):
        self.load_pilatus_1M_with_calibration()
        self.calibration_model.integrate_2d(azimuth_points=360)

        cake_tth = self.calibration_model.cake_tth
        cake_img = self.calibration_model.cake_img
        cake_step = cake_tth[31] - cake_tth[30]

        # directly selecting value in the tth array
        _, y1 = self.calibration_model.cake_integral(cake_tth[30])
        self.assertTrue(np.array_equal(y1, self.calibration_model.cake_img[:, 30]))

        # selecting exactly in between two points
        cake_partial = 0.5 * cake_img[:, 30] + 0.5 * cake_img[:, 31]
        _, y2 = self.calibration_model.cake_integral(cake_tth[30] + 0.5 * cake_step)
        self.assertTrue(np.array_equal(y2, cake_partial))

        # selecting points somewhere in between
        cake_partial = 0.3 * cake_img[:, 30] + 0.7 * cake_img[:, 31]
        _, y3 = self.calibration_model.cake_integral(cake_tth[30] + 0.7 * cake_step)
        self.assertTrue(np.array_equal(y3, cake_partial))

        # test with larger binsize of 2
        cake_partial = 0.5 * cake_img[:, 30] + 0.5 * cake_img[:, 31]
        _, y4 = self.calibration_model.cake_integral(cake_tth[30] + 0.5 * cake_step, bins=2)
        self.assertTrue(np.array_equal(y4, cake_partial))

        cake_partial = (0.5 * cake_img[:, 29] + cake_img[:, 30] + 0.5 * cake_img[:, 31]) / 2
        _, y5 = self.calibration_model.cake_integral(cake_tth[30], bins=2)
        self.assertTrue(np.array_equal(y5, cake_partial))

    def test_integration_with_predefined_detector(self):
        self.calibration_model.load_detector('Pilatus CdTe 1M')
        self.calibration_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.poni'))
        self.img_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.tif'))
        self.assertTrue(len(self.calibration_model.tth) > 0)

    def test_integration_with_rotated_predefined_detector(self):
        self.load_pilatus_1M_with_calibration()
        self.calibration_model.load_detector('Pilatus CdTe 1M')
        x1, y1 = self.calibration_model.integrate_1d()

        # rotate m90
        self.calibration_model.rotate_detector_m90()
        self.img_model.rotate_img_m90()
        self.calibration_model.integrate_1d()

        # rotate p90
        self.calibration_model.rotate_detector_p90()
        self.img_model.rotate_img_p90()
        x2, y2 = self.calibration_model.integrate_1d()

        self.assertEqual(len(x1), len(x2))
        self.assertAlmostEqual(float(np.sum((y1 - y2) ** 2)), 0)

    def test_integration_with_rotation(self):
        self.load_pilatus_1M_with_calibration()
        self.calibration_model.integrate_1d()

        # rotate m90
        self.calibration_model.rotate_detector_m90()
        self.img_model.rotate_img_m90()
        self.calibration_model.integrate_1d()

    def test_integration_with_rotation_and_reset(self):
        self.load_pilatus_1M_with_calibration()
        self.calibration_model.load_detector('Pilatus CdTe 1M')
        x1, y1 = self.calibration_model.integrate_1d()

        self.calibration_model.rotate_detector_m90()
        self.img_model.rotate_img_m90()
        self.calibration_model.rotate_detector_m90()
        self.img_model.rotate_img_m90()
        self.calibration_model.rotate_detector_p90()
        self.img_model.rotate_img_p90()

        self.calibration_model.reset_transformations()
        self.img_model.reset_transformations()

        x2, y2 = self.calibration_model.integrate_1d()

        self.assertEqual(len(x1), len(x2))
        self.assertAlmostEqual(float(np.sum((y1 - y2) ** 2)), 0)

        self.calibration_model.rotate_detector_p90()
        self.img_model.rotate_img_p90()
        self.calibration_model.integrate_1d()

    def test_integration_with_transformation_and_change_detector_to_custom(self):
        self.load_pilatus_1M_with_calibration()
        self.calibration_model.load_detector('Pilatus CdTe 1M')
        x1, y1 = self.calibration_model.integrate_1d()

        self.calibration_model.rotate_detector_m90()
        self.img_model.rotate_img_m90()

    def test_change_detector_after_loading_image_with_different_shapes_integrate_1d(self):
        self.img_model.load(os.path.join(data_path, 'LaB6_40keV_MarCCD.tif'))
        self.calibration_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.poni'))
        self.calibration_model.integrate_1d()

        callback_function = MagicMock()
        self.calibration_model.detector_reset.connect(callback_function)
        self.calibration_model.load_detector('Pilatus CdTe 1M')
        self.calibration_model.integrate_1d()
        callback_function.assert_called_once()

    def test_change_detector_after_loading_image_with_different_shapes_integrate_2d(self):
        self.img_model.load(os.path.join(data_path, 'LaB6_40keV_MarCCD.tif'))
        self.calibration_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.poni'))
        self.calibration_model.integrate_1d()

        callback_function = MagicMock()
        self.calibration_model.detector_reset.connect(callback_function)
        self.calibration_model.load_detector('Pilatus CdTe 1M')
        self.calibration_model.integrate_2d()
        callback_function.assert_called_once()


class CalibrationModelTest(QtTest):
    def setUp(self):
        self.img_model = ImgModel()
        self.calibration_model = CalibrationModel(self.img_model)

    def tearDown(self):
        delete_if_exists(os.path.join(data_path, 'detector_with_spline.h5'))
        del self.img_model
        if hasattr(self.calibration_model, 'cake_geometry'):
            del self.calibration_model.cake_geometry
        del self.calibration_model.pattern_geometry
        del self.calibration_model
        gc.collect()

    def test_loading_calibration_gives_right_pixel_size(self):
        self.calibration_model.pattern_geometry.load(os.path.join(data_path, 'CeO2_Pilatus1M.poni'))
        self.assertEqual(self.calibration_model.pattern_geometry.pixel1, 0.000172)

        self.calibration_model.load(os.path.join(data_path, 'LaB6_40keV_MarCCD.poni'))
        self.assertEqual(self.calibration_model.pattern_geometry.pixel1, 0.000079)

    def test_find_peaks_automatic(self):
        self.load_pilatus_1M()
        self.find_pilatus_1M_peaks()
        self.assertEqual(len(self.calibration_model.points), 6)
        for points in self.calibration_model.points:
            self.assertGreater(len(points), 0)

    def test_find_peak(self):
        """
        Tests the find_peak function for several maxima and pick points

        """
        points_and_pick_points = [
            [[30, 50], [31, 49]],
            [[30, 50], [34, 46]],
            [[5, 5], [3, 3]],
            [[298, 298], [299, 299]]
        ]

        for data in points_and_pick_points:
            self.img_model._img_data = np.zeros((300, 300))

            point = data[0]
            pick_point = data[1]
            self.img_model._img_data[point[0], point[1]] = 100

            peak_point = self.calibration_model.find_peak(pick_point[0], pick_point[1], 10, 0)
            self.assertEqual(peak_point[0][0], point[0])
            self.assertEqual(peak_point[0][1], point[1])

    def load_pilatus_1M(self):
        self.img_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.tif'))

    def find_pilatus_1M_peaks(self):
        points = [(517.664434674, 646, 0), (667.380513299, 525.252854758, 0),
                  (671.110095329, 473.571503774, 0), (592.788872703, 350.495296791, 0),
                  (387.395462348, 390.987901686, 0), (367.94835605, 554.290314848, 0)]
        for point in points:
            self.calibration_model.find_peaks_automatic(point[0], point[1], 0)

    def test_calibration_with_supersampling1(self):
        self.load_pilatus_1M()
        self.find_pilatus_1M_peaks()
        self.calibration_model.set_calibrant(os.path.join(calibrants_path, 'CeO2.D'))
        self.calibration_model.detector.pixel1 = 172e-6
        self.calibration_model.detector.pixel2 = 172e-6

        self.calibration_model.calibrate()
        normal_poni1 = self.calibration_model.pattern_geometry.poni1
        normal_poni2 = self.calibration_model.pattern_geometry.poni2

        self.calibration_model.set_supersampling(2)

        self.calibration_model.calibrate()
        self.assertAlmostEqual(normal_poni1, self.calibration_model.pattern_geometry.poni1, places=3)
        self.assertAlmostEqual(normal_poni2, self.calibration_model.pattern_geometry.poni2, places=3)

    def test_calibration_with_supersampling2(self):
        self.load_pilatus_1M()
        self.calibration_model.set_calibrant(os.path.join(calibrants_path, 'CeO2.D'))
        self.calibration_model.detector.pixel1 = 172e-6
        self.calibration_model.detector.pixel2 = 172e-6

        self.calibration_model.set_supersampling(2)
        self.find_pilatus_1M_peaks()

        self.calibration_model.calibrate()
        super_poni1 = self.calibration_model.pattern_geometry.poni1
        super_poni2 = self.calibration_model.pattern_geometry.poni2

        self.calibration_model.set_supersampling(1)
        self.find_pilatus_1M_peaks()

        self.calibration_model.calibrate()
        self.assertAlmostEqual(super_poni1, self.calibration_model.pattern_geometry.poni1, places=3)
        self.assertAlmostEqual(super_poni2, self.calibration_model.pattern_geometry.poni2, places=3)

    def test_calibration1(self):
        self.img_model.load(os.path.join(data_path, 'LaB6_40keV_MarCCD.tif'))
        self.calibration_model.find_peaks_automatic(1179.6, 1129.4, 0)
        self.calibration_model.find_peaks_automatic(1268.5, 1119.8, 1)
        self.calibration_model.set_calibrant(os.path.join(calibrants_path, 'LaB6.D'))
        self.calibration_model.calibrate()

        self.assertGreater(self.calibration_model.pattern_geometry.poni1, 0)
        self.assertAlmostEqual(self.calibration_model.pattern_geometry.dist, 0.18, delta=0.01)
        self.assertGreater(self.calibration_model.cake_geometry.poni1, 0)

    def test_calibration2(self):
        self.img_model.load(os.path.join(data_path, 'LaB6_OffCenter_PE.tif'))
        self.calibration_model.find_peaks_automatic(1245.2, 1919.3, 0)
        self.calibration_model.find_peaks_automatic(1334.0, 1823.7, 1)
        self.calibration_model.set_start_values({'dist': 500e-3, 'polarization_factor': 0.99,
                                                 'wavelength': 0.3344e-10})
        self.calibration_model.set_pixel_size((200e-6, 200e-6))
        self.calibration_model.set_calibrant(os.path.join(calibrants_path, 'LaB6.D'))
        self.calibration_model.calibrate()

        print(self.calibration_model.detector.pixel1)

        self.assertGreater(self.calibration_model.pattern_geometry.poni1, 0)
        self.assertAlmostEqual(self.calibration_model.pattern_geometry.dist, 0.500, delta=0.01)
        self.assertGreater(self.calibration_model.cake_geometry.poni1, 0)

    def test_calibration3(self):
        self.load_pilatus_1M()
        self.find_pilatus_1M_peaks()
        self.calibration_model.start_values['wavelength'] = 0.406626e-10
        self.calibration_model.set_start_values({'dist': 200e-3, 'polarization_factor': 0.99,
                                                 'wavelength': 0.406626e-10})
        self.calibration_model.set_pixel_size((172e-6, 172e-6))
        self.calibration_model.set_calibrant(os.path.join(calibrants_path, 'CeO2.D'))
        self.calibration_model.calibrate()

        self.assertGreater(self.calibration_model.pattern_geometry.poni1, 0)
        self.assertAlmostEqual(self.calibration_model.pattern_geometry.dist, 0.208, delta=0.005)
        self.assertGreater(self.calibration_model.cake_geometry.poni1, 0)

    def test_calibration_with_fixed_parameters(self):
        self.load_pilatus_1M()
        self.find_pilatus_1M_peaks()
        self.calibration_model.start_values['wavelength'] = 0.406626e-10
        self.calibration_model.detector.pixel1 = 172e-6
        self.calibration_model.detector.pixel2 = 172e-6
        self.calibration_model.set_calibrant(os.path.join(calibrants_path, 'CeO2.D'))

        fixed_values_dicts = [{'rot1': 0.001},
                              {'rot2': 0.03},
                              {'rot1': 0.01, 'rot2': 0.003},
                              {'poni1': 0.32},
                              {'poni1': 0.2, 'poni2': 0.13},
                              {'dist': 300},
                              {'rot1': 0.001, 'rot2': 0.004, 'poni1': 0.22, 'poni2': 0.34}]
        for fixed_values in fixed_values_dicts:
            self.calibration_model.set_fixed_values(fixed_values)
            self.calibration_model.calibrate()
            for key, value in fixed_values.items():
                self.assertEqual(getattr(self.calibration_model.pattern_geometry, key), value)

    def test_get_two_theta_img_with_distortion(self):
        self.img_model.load(os.path.join(data_path, 'distortion', 'CeO2_calib.edf'))

        self.calibration_model.find_peaks_automatic(1025.1, 1226.8, 0)
        self.calibration_model.set_calibrant(os.path.join(calibrants_path, 'CeO2.D'))
        self.calibration_model.start_values['dist'] = 300e-3
        self.calibration_model.detector.pixel1 = 50e-6
        self.calibration_model.detector.pixel2 = 50e-6
        self.calibration_model.start_values['wavelength'] = 0.1e-10
        self.calibration_model.calibrate()

        x, y = np.array((100,)), np.array((100,))
        self.calibration_model.get_two_theta_img(x, y)
        self.calibration_model.load_distortion(os.path.join(data_path, 'distortion', 'f4mnew.spline'))
        self.calibration_model.get_two_theta_img(x, y)

    def test_cake_integration_with_small_azimuth_range(self):
        self.img_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.tif'))
        self.calibration_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.poni'))

        full_cake = self.calibration_model.integrate_2d()
        small_cake = self.calibration_model.integrate_2d(azimuth_range=(40, 130))
        self.assertFalse(np.array_equal(full_cake, small_cake))

    def test_cake_integration_with_off_azimuth_range(self):
        self.img_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.tif'))
        self.calibration_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.poni'))
        self.calibration_model.integrate_2d(azimuth_range=(150, -130))

        self.assertGreater(np.min(self.calibration_model.cake_azi), 150)
        self.assertLess(np.max(self.calibration_model.cake_azi), 230)

    def test_cake_integration_with_different_num_points(self):
        self.img_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.tif'))
        self.calibration_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.poni'))

        self.calibration_model.integrate_2d(rad_points=200)
        self.assertEqual(len(self.calibration_model.cake_tth), 200)

        self.calibration_model.integrate_2d(azimuth_points=200)
        self.assertEqual(len(self.calibration_model.cake_azi), 200)

    def test_transforms_without_predefined_detector(self):
        self.img_model.load(os.path.join(data_path, 'image_001.tif'))
        self.calibration_model.rotate_detector_p90()
        self.calibration_model.rotate_detector_m90()
        self.calibration_model.flip_detector_horizontally()
        self.calibration_model.img_model.flip_img_horizontally()
        self.calibration_model.flip_detector_horizontally()

    def test_transforms_without_predefined_detector_changing_shape(self):
        self.img_model.load(os.path.join(data_path, 'image_001.tif'))
        self.calibration_model.rotate_detector_p90()
        self.img_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.tif'))
        self.calibration_model.rotate_detector_m90()
        self.calibration_model.flip_detector_horizontally()
        self.calibration_model.img_model.flip_img_horizontally()
        self.calibration_model.flip_detector_horizontally()

    def test_load_detector_list(self):
        names, classes = get_available_detectors()
        for name, cls in zip(names, classes):
            if name.startswith('Quantum'):
                self.assertIn('ADSC_', str(cls))
            elif name.startswith('aca1300'):
                self.assertIn('Basler', str(cls))
            else:
                self.assertIn(name[:2].lower(), str(cls).lower())

        self.assertNotIn('Detector', names)

    def test_load_predefined_detector(self):
        self.calibration_model.load_detector('MAR 345')

        self.assertEqual(self.calibration_model.orig_pixel1, 100e-6)
        self.assertEqual(self.calibration_model.detector.pixel1, 100e-6)

    def test_load_predefined_detector_and_poni_after(self):
        self.calibration_model.load_detector('Pilatus CdTe 1M')
        self.assertIsInstance(self.calibration_model.detector, detectors.PilatusCdTe1M)
        self.assertIsInstance(self.calibration_model.pattern_geometry.detector, detectors.PilatusCdTe1M)

        self.calibration_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.poni'))
        self.assertIsInstance(self.calibration_model.detector, detectors.PilatusCdTe1M)
        self.assertIsInstance(self.calibration_model.pattern_geometry.detector, detectors.PilatusCdTe1M)

    def test_load_predefined_detector_and_poni_with_different_pixel_size(self):
        self.calibration_model.load_detector('Pilatus CdTe 1M')
        self.assertIsInstance(self.calibration_model.detector, detectors.PilatusCdTe1M)
        self.assertIsInstance(self.calibration_model.pattern_geometry.detector, detectors.PilatusCdTe1M)

        self.calibration_model.load(os.path.join(data_path, 'LaB6_40keV_MarCCD.poni'))
        self.assertEqual(self.calibration_model.detector_mode, DetectorModes.CUSTOM)
        self.assertIsInstance(self.calibration_model.detector, detectors.Detector)
        self.assertIsInstance(self.calibration_model.pattern_geometry.detector, detectors.Detector)

    def test_load_detector_from_file(self):
        self.calibration_model.load_detector_from_file(os.path.join(data_path, 'detector.h5'))
        self.assertAlmostEqual(self.calibration_model.orig_pixel1, 100e-6)
        self.assertAlmostEqual(self.calibration_model.orig_pixel2, 100e-6)
        self.assertAlmostEqual(self.calibration_model.detector.pixel1, 100e-6)
        self.assertAlmostEqual(self.calibration_model.detector.pixel2, 100e-6)
        self.assertEqual(self.calibration_model.detector.shape, (1048, 1032))

    def test_load_detector_with_spline_file(self):
        # create detector and save it
        spline_detector = Detector()
        spline_detector.set_splineFile(os.path.join(data_path, 'distortion', 'f4mnew.spline'))
        spline_detector.save(os.path.join(data_path, 'detector_with_spline.h5'))

        # load and check if it is working
        self.calibration_model.load_detector_from_file(os.path.join(data_path, 'detector_with_spline.h5'))
        detector = self.calibration_model.detector
        self.assertAlmostEqual(detector.pixel1, 50e-6)
        self.assertFalse(detector.uniform_pixel)

    def test_load_image_with_different_shape_than_previous_defined_detector(self):
        self.calibration_model.load_detector('Pilatus CdTe 1M')
        self.calibration_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.poni'))
        callback_function = MagicMock()
        self.calibration_model.detector_reset.connect(callback_function)
        self.img_model.load(os.path.join(data_path, 'LaB6_40keV_MarCCD.tif'))
