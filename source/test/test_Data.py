__author__ = 'Clemens Prescher'

import unittest
import gc

from model.ImgModel import *
import numpy as np


class ImgModelTest(unittest.TestCase):
    def setUp(self):
        self.img_model = ImgModel()
        self.img_model.load('Data/test_001.tif')

    def tearDown(self):
        del self.img_model
        gc.collect()

    def test_rotation(self):
        pre_transformed_data = self.img_model.get_img_data()
        self.img_model.rotate_img_m90()
        self.img_model.rotate_img_m90()
        self.img_model.rotate_img_m90()
        self.img_model.rotate_img_m90()
        self.assertTrue(np.array_equal(self.img_model.get_img_data(), pre_transformed_data))
        self.img_model.reset_img_transformations()

        pre_transformed_data = self.img_model.get_img_data()
        self.img_model.rotate_img_m90()
        self.img_model.rotate_img_p90()
        self.assertTrue(np.array_equal(self.img_model.get_img_data(), pre_transformed_data))
        self.img_model.reset_img_transformations()

        pre_transformed_data = self.img_model.get_img_data()
        self.img_model.flip_img_horizontally()
        self.img_model.flip_img_horizontally()
        self.assertTrue(np.array_equal(self.img_model.get_img_data(), pre_transformed_data))
        self.img_model.reset_img_transformations()

        pre_transformed_data = self.img_model.get_img_data()
        self.img_model.flip_img_vertically()
        self.img_model.flip_img_vertically()
        self.assertTrue(np.array_equal(self.img_model.get_img_data(), pre_transformed_data))
        self.img_model.reset_img_transformations()

        self.img_model.flip_img_vertically()
        self.img_model.flip_img_horizontally()
        self.img_model.rotate_img_m90()
        self.img_model.rotate_img_p90()
        self.img_model.rotate_img_m90()
        self.img_model.rotate_img_m90()
        self.img_model.flip_img_horizontally()
        transformed_data = self.img_model.get_img_data()
        self.img_model.load('Data/test_001.tif')
        self.assertTrue(np.array_equal(self.img_model.get_img_data(), transformed_data))
        self.img_model.reset_img_transformations()

        pre_transformed_data = self.img_model.get_img_data()
        self.img_model.rotate_img_m90()
        self.img_model.reset_img_transformations()
        self.assertTrue(np.array_equal(self.img_model.get_img_data(), pre_transformed_data))

        pre_transformed_data = self.img_model.get_img_data()
        self.img_model.rotate_img_p90()
        self.img_model.reset_img_transformations()
        self.assertTrue(np.array_equal(self.img_model.get_img_data(), pre_transformed_data))

        pre_transformed_data = self.img_model.get_img_data()
        self.img_model.flip_img_horizontally()
        self.img_model.reset_img_transformations()
        self.assertTrue(np.array_equal(self.img_model.get_img_data(), pre_transformed_data))

        pre_transformed_data = self.img_model.get_img_data()
        self.img_model.flip_img_vertically()
        self.img_model.reset_img_transformations()
        self.assertTrue(np.array_equal(self.img_model.get_img_data(), pre_transformed_data))

        pre_transformed_data = self.img_model.get_img_data()
        self.img_model.flip_img_vertically()
        self.img_model.flip_img_horizontally()
        self.img_model.rotate_img_m90()
        self.img_model.rotate_img_p90()
        self.img_model.rotate_img_m90()
        self.img_model.rotate_img_m90()
        self.img_model.flip_img_horizontally()
        self.img_model.reset_img_transformations()
        self.assertTrue(np.array_equal(self.img_model.get_img_data(), pre_transformed_data))





