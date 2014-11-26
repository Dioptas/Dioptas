# -*- coding: utf8 -*-
__author__ = 'Clemens Prescher'


__author__ = 'Clemens Prescher'

import unittest
import time
import numpy as np
import matplotlib.pyplot as plt

from Data.ImgData import ImgData


class ImgDataUnitTest(unittest.TestCase):
    def setUp(self):
        self.img_data = ImgData()
        self.img_data.load('Data/Mg2SiO4_ambient_001.tif')

    def perform_transformations_tests(self):
        self.assertEqual(np.sum(np.absolute(self.img_data.get_img_data())), 0)
        self.img_data.rotate_img_m90()
        self.assertEqual(np.sum(np.absolute(self.img_data.get_img_data())), 0)
        self.img_data.flip_img_horizontally()
        self.assertEqual(np.sum(np.absolute(self.img_data.get_img_data())), 0)
        self.img_data.rotate_img_p90()
        self.assertEqual(np.sum(np.absolute(self.img_data.get_img_data())), 0)
        self.img_data.flip_img_vertically()
        self.assertEqual(np.sum(np.absolute(self.img_data.get_img_data())), 0)
        self.img_data.reset_img_transformations()
        self.assertEqual(np.sum(np.absolute(self.img_data.get_img_data())), 0)

    def test_flipping_images(self):
        original_image = np.copy(self.img_data._img_data)
        self.img_data.flip_img_vertically()
        self.assertTrue(np.array_equal(self.img_data._img_data, np.flipud(original_image)))

    def test_simple_background_subtraction(self):
        self.first_image = np.copy(self.img_data.get_img_data())
        self.img_data.load_next_file()
        self.second_image = np.copy(self.img_data.get_img_data())

        self.img_data.load('Data/Mg2SiO4_ambient_001.tif')
        self.img_data.load_background('Data/Mg2SiO4_ambient_002.tif')

        self.assertFalse(np.array_equal(self.first_image, self.img_data.get_img_data()))

        self.img_data.load_next_file()
        self.assertEqual(np.sum(self.img_data.get_img_data()), 0)

    def test_background_subtraction_with_supersampling(self):
        self.img_data.load_background('Data/Mg2SiO4_ambient_002.tif')

        self.img_data.set_supersampling(2)
        self.img_data.get_img_data()
        self.img_data.set_supersampling(3)
        self.img_data.get_img_data()

        self.img_data.load_next_file()
        self.img_data.get_img_data()

    def test_background_subtraction_with_transformation(self):

        self.img_data.load_background('Data/Mg2SiO4_ambient_002.tif')
        original_img = np.copy(self.img_data._img_data)
        original_background = np.copy(self.img_data._background_data)

        self.assertNotEqual(self.img_data._background_data, None)
        self.assertFalse(np.array_equal(self.img_data.img_data,  self.img_data._img_data))

        original_img_background_subtracted = np.copy(self.img_data.get_img_data())
        self.assertTrue(np.array_equal(original_img_background_subtracted, original_img-original_background))

        ### now comes the main process - flipping the image
        self.img_data.flip_img_vertically()
        flipped_img = np.copy(self.img_data._img_data)
        self.assertTrue(np.array_equal(np.flipud(original_img), flipped_img))

        flipped_background = np.copy(self.img_data._background_data)
        self.assertTrue(np.array_equal(np.flipud(original_background), flipped_background))

        flipped_img_background_subtracted = np.copy(self.img_data.get_img_data())
        self.assertTrue(np.array_equal(flipped_img_background_subtracted, flipped_img-flipped_background))

        self.assertTrue(np.array_equal(np.flipud(original_img_background_subtracted),
                                       flipped_img_background_subtracted))
        self.assertEqual(np.sum(np.flipud(original_img_background_subtracted)-flipped_img_background_subtracted), 0)

        self.img_data.load('Data/Mg2SiO4_ambient_002.tif')
        self.perform_transformations_tests()


    def test_background_subtraction_with_supersampling_and_image_transformation(self):
        self.img_data.load_background('Data/Mg2SiO4_ambient_002.tif')
        self.img_data.load('Data/Mg2SiO4_ambient_002.tif')

        self.img_data.set_supersampling(2)
        self.assertEqual(self.img_data.get_img_data().shape, (4096, 4096))

        self.perform_transformations_tests()

        self.img_data.set_supersampling(3)
        self.assertEqual(self.img_data.get_img_data().shape, (6144, 6144))

        self.perform_transformations_tests()

        self.img_data.load('Data/Mg2SiO4_ambient_002.tif')
        self.assertEqual(self.img_data.get_img_data().shape, (6144, 6144))

        self.perform_transformations_tests()

    def test_background_scaling_and_offset(self):
        self.img_data.load_background('Data/Mg2SiO4_ambient_002.tif')

        #assure that everything is correct before
        self.assertTrue(np.array_equal(self.img_data.get_img_data(),
                                       self.img_data._img_data-self.img_data._background_data))

        #set scaling and see difference
        self.img_data.set_background_scaling(2.4)
        self.assertTrue(np.array_equal(self.img_data.get_img_data(),
                                       self.img_data._img_data-2.4*self.img_data._background_data))

        #set offset and see the difference
        self.img_data.set_background_scaling(1.0)
        self.img_data.set_background_offset(100.0)
        self.assertTrue(np.array_equal(self.img_data.img_data,
                                       self.img_data._img_data-(self.img_data._background_data+100.0)))

        #use offset and scaling combined
        self.img_data.set_background_scaling(2.3)
        self.img_data.set_background_offset(100.0)
        self.assertTrue(np.array_equal(self.img_data.img_data,
                                       self.img_data._img_data-(2.3*self.img_data._background_data+100)))

    def test_background_with_different_shape(self):
        self.img_data.load_background('Data/CeO2_Pilatus1M.tif')
        self.assertEqual(self.img_data._background_data, None)

        self.img_data.load_background('Data/Mg2SiO4_ambient_002.tif')
        self.assertTrue(self.img_data._background_data is not None)

        self.img_data.load('Data/CeO2_Pilatus1M.tif')
        self.assertEqual(self.img_data._background_data, None)

    def test_absorption_correction_with_supersampling(self):
        original_image = np.copy(self.img_data.get_img_data())
        self.img_data.set_absorption_correction(np.ones(original_image.shape)*0.6)

        self.assertAlmostEqual(np.sum(original_image)/0.6, np.sum(self.img_data.get_img_data()), places=4)

        self.img_data.set_supersampling(2)
        self.img_data.get_img_data()

    def test_absorption_correction_with_different_image_sizes(self):
        self.img_data.set_absorption_correction(np.ones(self.img_data._img_data.shape)*0.4)
        self.assertNotEqual(self.img_data._absorption_correction, None)

        self.img_data.load('Data/CeO2_Pilatus1M.tif')
        self.assertEqual(self.img_data._absorption_correction, None)

    def test_saving_data(self):
        self.img_data.load('Data/Mg2SiO4_ambient_001.tif')
        self.img_data.save('Data/TestSaving.tif')
        first_img_array = np.copy(self.img_data._img_data)
        self.img_data.load('Data/TestSaving.tif')
        self.assertTrue(np.array_equal(first_img_array, self.img_data._img_data))

