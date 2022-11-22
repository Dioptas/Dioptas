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
from mock import MagicMock
import os

import numpy as np

from ...model.ImgModel import ImgModel, BackgroundDimensionWrongException
from ...model.util.ImgCorrection import DummyCorrection

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')
spe_path = os.path.join(data_path, 'spe')


class ImgModelTest(unittest.TestCase):
    def setUp(self):
        self.img_model = ImgModel()
        self.img_model.load(os.path.join(data_path, 'image_001.tif'))

    def tearDown(self):
        del self.img_model

    def test_load_karabo_nexus_file(self):
        self.img_model.load(os.path.join(data_path, 'karabo_epix.h5'))

    def perform_transformations_tests(self):
        self.assertEqual(np.sum(np.absolute(self.img_model.img_data)), 0)
        self.img_model.rotate_img_m90()
        self.assertEqual(np.sum(np.absolute(self.img_model.img_data)), 0)
        self.img_model.flip_img_horizontally()
        self.assertEqual(np.sum(np.absolute(self.img_model.img_data)), 0)
        self.img_model.rotate_img_p90()
        self.assertEqual(np.sum(np.absolute(self.img_model.img_data)), 0)
        self.img_model.flip_img_vertically()
        self.assertEqual(np.sum(np.absolute(self.img_model.img_data)), 0)
        self.img_model.reset_transformations()
        self.assertEqual(np.sum(np.absolute(self.img_model.img_data)), 0)

    def test_load_emits_signal(self):
        callback_fcn = MagicMock()
        self.img_model.img_changed.connect(callback_fcn)
        self.img_model.load(os.path.join(data_path, 'image_001.tif'))
        callback_fcn.assert_called_once_with()

    def test_flipping_images(self):
        original_image = np.copy(self.img_model._img_data)
        self.img_model.flip_img_vertically()
        self.assertTrue(np.array_equal(self.img_model._img_data, np.flipud(original_image)))

    def test_simple_background_subtraction(self):
        self.first_image = np.copy(self.img_model.img_data)
        self.img_model.load_next_file()
        self.second_image = np.copy(self.img_model.img_data)

        self.img_model.load(os.path.join(data_path, 'image_001.tif'))
        self.img_model.load_background(os.path.join(data_path, 'image_002.tif'))

        self.assertFalse(np.array_equal(self.first_image, self.img_model.img_data))

        self.img_model.load_next_file()
        self.assertEqual(np.sum(self.img_model.img_data), 0)

    def test_background_subtraction_with_transformation(self):
        self.img_model.load_background(os.path.join(data_path, 'image_002.tif'))
        original_img = np.copy(self.img_model._img_data)
        original_background = np.copy(self.img_model._background_data)

        self.assertIsNotNone(self.img_model._background_data)
        self.assertFalse(np.array_equal(self.img_model.img_data, self.img_model._img_data))

        original_img_background_subtracted = np.copy(self.img_model.img_data)
        self.assertTrue(np.array_equal(original_img_background_subtracted, original_img - original_background))

        ### now comes the main process - flipping the image
        self.img_model.flip_img_vertically()
        flipped_img = np.copy(self.img_model._img_data)
        self.assertTrue(np.array_equal(np.flipud(original_img), flipped_img))

        flipped_background = np.copy(self.img_model._background_data)
        self.assertTrue(np.array_equal(np.flipud(original_background), flipped_background))

        flipped_img_background_subtracted = np.copy(self.img_model.img_data)
        self.assertTrue(np.array_equal(flipped_img_background_subtracted, flipped_img - flipped_background))

        self.assertTrue(np.array_equal(np.flipud(original_img_background_subtracted),
                                       flipped_img_background_subtracted))
        self.assertEqual(np.sum(np.flipud(original_img_background_subtracted) - flipped_img_background_subtracted), 0)

        self.img_model.load(os.path.join(data_path, 'image_002.tif'))
        self.perform_transformations_tests()

    def test_background_scaling_and_offset(self):
        self.img_model.load_background(os.path.join(data_path, 'image_002.tif'))

        # assure that everything is correct before
        self.assertTrue(np.array_equal(self.img_model.img_data,
                                       self.img_model._img_data - self.img_model._background_data))

        # set scaling and see difference
        self.img_model.background_scaling = 2.4
        self.assertTrue(np.array_equal(self.img_model.img_data,
                                       self.img_model._img_data - 2.4 * self.img_model._background_data))

        # set offset and see the difference
        self.img_model.background_scaling = 1.0
        self.img_model.background_offset = 100.0
        self.assertTrue(np.array_equal(self.img_model.img_data,
                                       self.img_model._img_data - (self.img_model._background_data + 100.0)))

        # use offset and scaling combined
        self.img_model.background_scaling = 2.3
        self.img_model.background_offset = 100.0
        self.assertTrue(np.array_equal(self.img_model.img_data,
                                       self.img_model._img_data - (2.3 * self.img_model._background_data + 100)))

    def test_background_with_different_shape(self):
        with self.assertRaises(BackgroundDimensionWrongException):
            self.img_model.load_background(os.path.join(data_path, 'CeO2_Pilatus1M.tif'))
        self.assertEqual(self.img_model._background_data, None)

        self.img_model.load_background(os.path.join(data_path, 'image_002.tif'))
        self.assertTrue(self.img_model._background_data is not None)

        self.img_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.tif'))
        self.assertEqual(self.img_model._background_data, None)

    def test_absorption_correction_with_different_image_sizes(self):
        dummy_correction = DummyCorrection(self.img_model.img_data.shape, 0.4)
        # self.img_data.set_absorption_correction(np.ones(self.img_data._img_data.shape)*0.4)
        self.img_model.add_img_correction(dummy_correction, "Dummy 1")
        self.assertTrue(self.img_model._img_corrections.has_items())

        self.img_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.tif'))
        self.assertFalse(self.img_model.has_corrections())

    def test_adding_several_absorption_corrections(self):
        original_image = np.copy(self.img_model.img_data)
        img_shape = original_image.shape
        self.img_model.add_img_correction(DummyCorrection(img_shape, 0.4))
        self.img_model.add_img_correction(DummyCorrection(img_shape, 3))
        self.img_model.add_img_correction(DummyCorrection(img_shape, 5))

        self.assertTrue(np.sum(original_image) / (0.5 * 3 * 5), np.sum(self.img_model.img_data))

        self.img_model.delete_img_correction(1)
        self.assertTrue(np.sum(original_image) / (0.5 * 5), np.sum(self.img_model.img_data))

    def test_saving_data(self):
        self.img_model.load(os.path.join(data_path, 'image_001.tif'))
        filename = os.path.join(data_path, 'test.tif')
        self.img_model.save(filename)
        first_img_array = np.copy(self.img_model._img_data)
        self.img_model.load(filename)
        self.assertTrue(np.array_equal(first_img_array, self.img_model._img_data))
        self.assertTrue(os.path.exists(filename))
        os.remove(filename)

    def test_negative_rotation(self):
        pre_transformed_data = self.img_model.img_data
        self.img_model.rotate_img_m90()
        self.img_model.rotate_img_m90()
        self.img_model.rotate_img_m90()
        self.img_model.rotate_img_m90()
        self.assertTrue(np.array_equal(self.img_model.img_data, pre_transformed_data))

    def test_combined_rotation(self):
        pre_transformed_data = self.img_model.img_data
        self.img_model.rotate_img_m90()
        self.img_model.rotate_img_p90()
        self.assertTrue(np.array_equal(self.img_model.img_data, pre_transformed_data))

    def test_flip_img_horizontally(self):
        pre_transformed_data = self.img_model.img_data
        self.img_model.flip_img_horizontally()
        self.img_model.flip_img_horizontally()
        self.assertTrue(np.array_equal(self.img_model.img_data, pre_transformed_data))

    def test_flip_img_vertically(self):
        pre_transformed_data = self.img_model.img_data
        self.img_model.flip_img_vertically()
        self.img_model.flip_img_vertically()
        self.assertTrue(np.array_equal(self.img_model.img_data, pre_transformed_data))

    def test_combined_rotation_and_flipping(self):
        self.img_model.flip_img_vertically()
        self.img_model.flip_img_horizontally()
        self.img_model.rotate_img_m90()
        self.img_model.rotate_img_p90()
        self.img_model.rotate_img_m90()
        self.img_model.rotate_img_m90()
        self.img_model.flip_img_horizontally()
        transformed_data = self.img_model.img_data
        self.img_model.load(os.path.join(data_path, 'image_001.tif'))
        self.assertTrue(np.array_equal(self.img_model.img_data, transformed_data))

    def test_reset_img_transformation(self):
        pre_transformed_data = self.img_model.img_data
        self.img_model.rotate_img_m90()
        self.img_model.reset_transformations()
        self.assertTrue(np.array_equal(self.img_model.img_data, pre_transformed_data))

        pre_transformed_data = self.img_model.img_data
        self.img_model.rotate_img_p90()
        self.img_model.reset_transformations()
        self.assertTrue(np.array_equal(self.img_model.img_data, pre_transformed_data))

        pre_transformed_data = self.img_model.img_data
        self.img_model.flip_img_horizontally()
        self.img_model.reset_transformations()
        self.assertTrue(np.array_equal(self.img_model.img_data, pre_transformed_data))

        pre_transformed_data = self.img_model.img_data
        self.img_model.flip_img_vertically()
        self.img_model.reset_transformations()
        self.assertTrue(np.array_equal(self.img_model.img_data, pre_transformed_data))

        pre_transformed_data = self.img_model.img_data
        self.img_model.flip_img_vertically()
        self.img_model.flip_img_horizontally()
        self.img_model.rotate_img_m90()
        self.img_model.rotate_img_p90()
        self.img_model.rotate_img_m90()
        self.img_model.rotate_img_m90()
        self.img_model.flip_img_horizontally()
        self.img_model.reset_transformations()
        self.assertTrue(np.array_equal(self.img_model.img_data, pre_transformed_data))

    def test_loading_a_tagged_tif_file_and_retrieving_info_string(self):
        self.img_model.load(os.path.join(data_path, "attrib.tif"))
        self.assertIn("areaDetector", self.img_model.file_info)

    def test_loading_spe_file(self):
        self.img_model.load(os.path.join(spe_path, 'CeO2_PI_CCD_Mo.SPE'))
        self.assertEqual(self.img_model.img_data.shape, (1042, 1042))

    def test_loading_ESRF_hdf5_file(self):
        self.img_model.load(os.path.join(data_path, 'hdf5_dataset', 'ma4500_demoh5.h5'))
        self.assertEqual(self.img_model.img_data.shape, (2048, 2048))

        img1 = self.img_model.img_data
        self.img_model.select_source(self.img_model.sources[2])
        img2 = self.img_model.img_data
        self.assertNotEqual(np.sum(img1-img2), 0)

    def test_summing_files(self):
        data1 = np.copy(self.img_model._img_data).astype(np.uint32)
        self.img_model.add(os.path.join(data_path, 'image_001.tif'))
        self.assertTrue(np.array_equal(2 * data1, self.img_model._img_data))

    def test_summing_rotated(self):
        self.img_model.rotate_img_m90()
        data1 = np.copy(self.img_model._img_data).astype(np.uint32)
        self.img_model.add(os.path.join(data_path, 'image_001.tif'))
        self.assertTrue(np.array_equal(2 * data1, self.img_model._img_data))


if __name__ == '__main__':
    unittest.main()
