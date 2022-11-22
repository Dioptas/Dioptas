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
import unittest

import numpy as np
from mock import MagicMock

from ..utility import delete_if_exists
from ...model.DioptasModel import DioptasModel
from ...model.util import Pattern

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')


class DioptasModelTest(unittest.TestCase):
    def setUp(self):
        self.model = DioptasModel()

    def tearDown(self):
        self.calibration_model.pattern_geometry.reset()
        self.calibration_model.cake_geometry.reset()
        delete_if_exists(os.path.join(data_path, 'empty.dio'))
        delete_if_exists(os.path.join(data_path, 'combined_pattern.xy'))

    def test_add_configuration(self):
        self.model.img_model.load(os.path.join(data_path, "image_001.tif"))

        prev_sum = np.sum(self.model.img_data)
        self.assertTrue(np.array_equal(self.model.img_data,
                                       self.model.configurations[0].img_model.img_data))

        self.model.add_configuration()
        new_sum = np.sum(self.model.img_data)
        self.assertTrue(np.array_equal(self.model.img_data,
                                       self.model.configurations[1].img_model.img_data))

        self.assertEqual(prev_sum, new_sum)

    def test_remove_configuration(self):
        self.model.add_configuration()
        self.model.img_model.load(os.path.join(data_path, "image_001.tif"))
        old_img = self.model.img_data

        self.model.remove_configuration()
        self.assertFalse(np.array_equal(self.model.img_data,
                                        old_img))

    def test_select_configuration(self):
        img_1 = self.model.img_data

        self.model.add_configuration()
        self.model.img_model.load(os.path.join(data_path, "image_001.tif"))
        img_2 = self.model.img_data

        self.model.add_configuration()
        self.model.img_model.load(os.path.join(data_path, "image_002.tif"))
        img_3 = self.model.img_data

        self.model.select_configuration(0)
        self.assertTrue(np.array_equal(self.model.img_data,
                                       img_1))

        self.model.select_configuration(2)
        self.assertTrue(np.array_equal(self.model.img_data,
                                       img_3))

        self.model.select_configuration(1)
        self.assertTrue(np.array_equal(self.model.img_data,
                                       img_2))

    def test_signals_are_raised(self):
        self.model.configuration_added = MagicMock()
        self.model.configuration_selected = MagicMock()
        self.model.configuration_removed = MagicMock()

        self.model.add_configuration()
        self.model.add_configuration()
        self.model.configuration_added.emit.assert_called()

        self.model.select_configuration(0)
        self.model.configuration_selected.emit.assert_called_with(0)

        self.model.remove_configuration()
        self.model.configuration_removed.emit.assert_called_with(0)

    def test_integrate_cakes(self):
        self.model.calibration_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.poni'))
        self.model.current_configuration.auto_integrate_cake = True
        self.model.img_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.tif'))
        self.assertFalse(np.array_equal(self.model.current_configuration.cake_img,
                                        np.zeros((2048, 2048))))

    def test_integrate_cake_with_mask(self):
        self.model.calibration_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.poni'))
        self.model.current_configuration.auto_integrate_cake = True
        self.model.img_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.tif'))
        cake_img1 = self.model.current_configuration.cake_img

        self.model.use_mask = True
        self.model.mask_model.mask_below_threshold(self.model.img_data, 1)
        self.model.img_model.img_changed.emit()
        cake_img2 = self.model.current_configuration.cake_img
        self.assertFalse(np.array_equal(cake_img1, cake_img2))

    def test_integrate_cake_with_different_azimuth_points(self):
        self.model.calibration_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.poni'))
        self.model.current_configuration.auto_integrate_cake = True
        self.model.img_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.tif'))

        self.assertEqual(self.model.current_configuration.cake_img.shape[0], 360)
        self.model.current_configuration.cake_azimuth_points = 720
        self.assertEqual(self.model.current_configuration.cake_img.shape[0], 720)

    def test_integrate_cake_with_different_rad_points(self):
        self.model.calibration_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.poni'))
        self.model.current_configuration.auto_integrate_cake = True
        self.model.img_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.tif'))

        self.assertGreater(self.model.current_configuration.cake_img.shape[1], 360)
        self.model.current_configuration.integration_rad_points = 720
        self.assertEqual(self.model.current_configuration.cake_img.shape[1], 720)

    def test_change_cake_azimuth_range(self):
        self.model.calibration_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.poni'))
        self.model.current_configuration.auto_integrate_cake = True
        self.model.img_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.tif'))

        self.model.current_configuration.cake_azimuth_range = [-180, 180]

        self.assertAlmostEqual(self.model.current_configuration.calibration_model.cake_azi[0], -179.5, places=4)
        self.assertAlmostEqual(self.model.current_configuration.calibration_model.cake_azi[-1], 179.5, places=4)

        self.model.current_configuration.cake_azimuth_range = [-100, 100]
        self.assertGreater(self.model.current_configuration.calibration_model.cake_azi[0], -100)
        self.assertLess(self.model.current_configuration.calibration_model.cake_azi[-1], 100)

    def prepare_combined_patterns(self):
        x1 = np.linspace(0, 10)
        y1 = np.ones(x1.shape)
        pattern1 = Pattern(x1, y1)

        x2 = np.linspace(7, 15)
        y2 = np.ones(x2.shape) * 2
        pattern2 = Pattern(x2, y2)

        self.model.pattern_model.pattern = pattern1
        self.model.add_configuration()
        self.model.pattern_model.pattern = pattern2

        self.model.combine_patterns = True

    def test_combine_patterns(self):
        self.prepare_combined_patterns()
        x3, y3 = self.model.pattern.data
        self.assertLess(np.min(x3), 7)
        self.assertGreater(np.max(x3), 10)

    def test_save_combine_patterns(self):
        self.prepare_combined_patterns()
        file_path = os.path.join(data_path, 'combined_pattern.xy')
        self.model.pattern.save(file_path)
        saved_pattern = Pattern().load(file_path)
        x3, y3 = saved_pattern.data
        self.assertLess(np.min(x3), 7)
        self.assertGreater(np.max(x3), 10)

    def test_combine_cakes(self):
        self.model.calibration_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.poni'))
        self.model.current_configuration.auto_integrate_cake = True
        self.model.img_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.tif'))

        cake1 = self.model.cake_data
        self.model.add_configuration()

        self.model.calibration_model.load(os.path.join(data_path, 'CeO2_Pilatus1M_2.poni'))
        self.model.current_configuration.auto_integrate_cake = True
        self.model.img_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.tif'))

        self.model.combine_cakes = True
        self.assertFalse(np.array_equal(self.model.cake_data, cake1))

    def test_setting_factors(self):
        self.model.img_model.load(os.path.join(data_path, "image_001.tif"))
        data1 = np.copy(self.model.img_data)
        self.model.img_model.factor = 2
        self.assertTrue(np.array_equal(2 * data1, self.model.img_data))

    def test_iterate_next_image(self):
        self.model.img_model.load(os.path.join(data_path, "image_001.tif"))
        self.model.add_configuration()
        self.model.img_model.load(os.path.join(data_path, "image_001.tif"))

        self.model.next_image()

        self.assertEqual(self.model.configurations[0].img_model.filename,
                         os.path.abspath(os.path.join(data_path, "image_002.tif")))
        self.assertEqual(self.model.configurations[1].img_model.filename,
                         os.path.abspath(os.path.join(data_path, "image_002.tif")))

    def test_iterate_previous_image(self):
        self.model.img_model.load(os.path.join(data_path, "image_002.tif"))
        self.model.add_configuration()
        self.model.img_model.load(os.path.join(data_path, "image_002.tif"))

        self.model.previous_image()

        self.assertEqual(self.model.configurations[0].img_model.filename,
                         os.path.abspath(os.path.join(data_path, "image_001.tif")))
        self.assertEqual(self.model.configurations[1].img_model.filename,
                         os.path.abspath(os.path.join(data_path, "image_001.tif")))

    def test_unit_change_with_auto_background_subtraction(self):
        # load calibration and image
        self.model.calibration_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.poni'))
        self.model.img_model.load(os.path.join(data_path, "image_001.tif"))

        # check that background subtraction works
        x, y = self.model.pattern_model.pattern.data
        x_max_2th = np.max(x)
        roi = (0, np.max(x) + 1)
        self.model.pattern_model.set_auto_background_subtraction((0.1, 50, 50), roi)
        new_y = self.model.pattern_model.pattern.y
        self.assertNotEqual(np.sum(y - new_y), 0)

        x_bkg, y_bkg = self.model.pattern_model.pattern.auto_background_pattern.data

        # change the unit to q
        self.model.integration_unit = 'q_A^-1'

        # check that the pattern is integrated with different unit
        x, y = self.model.pattern_model.pattern.data
        x_max_q = np.max(x)
        self.assertLess(x_max_q, x_max_2th)

        self.assertLess(self.model.pattern_model.pattern.auto_background_subtraction_parameters[0], 0.1)

        # check that the background roi has changed
        self.assertNotEqual(self.model.pattern_model.pattern.auto_background_subtraction_roi, roi)
        self.assertTrue(self.model.pattern_model.pattern.auto_background_subtraction)

        # check that the background pattern has changed:
        x_bkg_2, y_bkg_2 = self.model.pattern_model.pattern.auto_background_pattern.data
        self.assertNotEqual(np.max(x_bkg), np.max(x_bkg_2))

    def test_save_empty_configuration(self):
        self.model.save(os.path.join(data_path, 'empty.dio'))

    def test_clear_model(self):
        self.model.calibration_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.poni'))
        self.model.img_model.load(os.path.join(data_path, "image_001.tif"))

        self.model.add_configuration()
        self.model.add_configuration()

        self.model.reset()
