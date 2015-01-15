__author__ = 'Clemens Prescher'

import unittest
import gc

from Data.ImgData import *
import numpy as np


class ImgDataTest(unittest.TestCase):
    def setUp(self):
        self.data = ImgData()
        self.data.load('Data/test_001.tif')

    def tearDown(self):
        del self.data
        gc.collect()

    def test_rotation(self):
        pre_transformed_data = self.data.get_img_data()
        self.data.rotate_img_m90()
        self.data.rotate_img_m90()
        self.data.rotate_img_m90()
        self.data.rotate_img_m90()
        self.assertTrue(np.array_equal(self.data.get_img_data(), pre_transformed_data))
        self.data.reset_img_transformations()

        pre_transformed_data = self.data.get_img_data()
        self.data.rotate_img_m90()
        self.data.rotate_img_p90()
        self.assertTrue(np.array_equal(self.data.get_img_data(), pre_transformed_data))
        self.data.reset_img_transformations()

        pre_transformed_data = self.data.get_img_data()
        self.data.flip_img_horizontally()
        self.data.flip_img_horizontally()
        self.assertTrue(np.array_equal(self.data.get_img_data(), pre_transformed_data))
        self.data.reset_img_transformations()

        pre_transformed_data = self.data.get_img_data()
        self.data.flip_img_vertically()
        self.data.flip_img_vertically()
        self.assertTrue(np.array_equal(self.data.get_img_data(), pre_transformed_data))
        self.data.reset_img_transformations()

        self.data.flip_img_vertically()
        self.data.flip_img_horizontally()
        self.data.rotate_img_m90()
        self.data.rotate_img_p90()
        self.data.rotate_img_m90()
        self.data.rotate_img_m90()
        self.data.flip_img_horizontally()
        transformed_data = self.data.get_img_data()
        self.data.load('Data/test_001.tif')
        self.assertTrue(np.array_equal(self.data.get_img_data(), transformed_data))
        self.data.reset_img_transformations()

        pre_transformed_data = self.data.get_img_data()
        self.data.rotate_img_m90()
        self.data.reset_img_transformations()
        self.assertTrue(np.array_equal(self.data.get_img_data(), pre_transformed_data))

        pre_transformed_data = self.data.get_img_data()
        self.data.rotate_img_p90()
        self.data.reset_img_transformations()
        self.assertTrue(np.array_equal(self.data.get_img_data(), pre_transformed_data))

        pre_transformed_data = self.data.get_img_data()
        self.data.flip_img_horizontally()
        self.data.reset_img_transformations()
        self.assertTrue(np.array_equal(self.data.get_img_data(), pre_transformed_data))

        pre_transformed_data = self.data.get_img_data()
        self.data.flip_img_vertically()
        self.data.reset_img_transformations()
        self.assertTrue(np.array_equal(self.data.get_img_data(), pre_transformed_data))

        pre_transformed_data = self.data.get_img_data()
        self.data.flip_img_vertically()
        self.data.flip_img_horizontally()
        self.data.rotate_img_m90()
        self.data.rotate_img_p90()
        self.data.rotate_img_m90()
        self.data.rotate_img_m90()
        self.data.flip_img_horizontally()
        self.data.reset_img_transformations()
        self.assertTrue(np.array_equal(self.data.get_img_data(), pre_transformed_data))





