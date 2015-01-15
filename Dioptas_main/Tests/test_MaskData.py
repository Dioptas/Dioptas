# -*- coding: utf8 -*-
__author__ = 'Clemens Prescher'

import unittest
import gc
import sys
import os
import numpy as np

from Data.MaskData import MaskData


class MaskUnitTest(unittest.TestCase):
    def setUp(self):
        self.mask_data = MaskData()
        self.img = np.zeros((10, 10))
        self.mask_data.set_dimension(self.img.shape)

    def tearDown(self):
        del self.mask_data
        gc.collect()

    def test_growing_masks(self):
        self.mask_data._mask_data[4, 4] = 1
        self.mask_data._mask_data[0, 0] = 1
        self.mask_data._mask_data[0, 9] = 1
        self.mask_data._mask_data[9, 9] = 1
        self.mask_data._mask_data[9, 0] = 1

        self.mask_data.grow()

        # test corners
        self.assertEqual(self.mask_data._mask_data[0, 1], 1)
        self.assertEqual(self.mask_data._mask_data[1, 1], 1)
        self.assertEqual(self.mask_data._mask_data[1, 0], 1)

        self.assertEqual(self.mask_data._mask_data[0, 8], 1)
        self.assertEqual(self.mask_data._mask_data[1, 8], 1)
        self.assertEqual(self.mask_data._mask_data[1, 9], 1)

        self.assertEqual(self.mask_data._mask_data[8, 0], 1)
        self.assertEqual(self.mask_data._mask_data[8, 1], 1)
        self.assertEqual(self.mask_data._mask_data[9, 1], 1)

        self.assertEqual(self.mask_data._mask_data[8, 8], 1)
        self.assertEqual(self.mask_data._mask_data[8, 9], 1)
        self.assertEqual(self.mask_data._mask_data[9, 8], 1)

        # test center
        self.assertEqual(self.mask_data._mask_data[3, 3], 1)
        self.assertEqual(self.mask_data._mask_data[4, 3], 1)
        self.assertEqual(self.mask_data._mask_data[5, 3], 1)

        self.assertEqual(self.mask_data._mask_data[3, 5], 1)
        self.assertEqual(self.mask_data._mask_data[4, 5], 1)
        self.assertEqual(self.mask_data._mask_data[5, 5], 1)

        self.assertEqual(self.mask_data._mask_data[3, 4], 1)
        self.assertEqual(self.mask_data._mask_data[5, 4], 1)

    def test_shrink_mask(self):
        self.mask_data._mask_data[4, 4] = 1
        self.mask_data._mask_data[0, 0] = 1
        self.mask_data._mask_data[0, 9] = 1
        self.mask_data._mask_data[9, 9] = 1
        self.mask_data._mask_data[9, 0] = 1

        self.before_mask = np.copy(self.mask_data._mask_data)
        self.mask_data.grow()
        self.mask_data.shrink()

        self.assertTrue(np.array_equal(self.before_mask, self.mask_data._mask_data))

        self.mask_data.clear_mask()

        self.mask_data._mask_data[4,4] = 1
        self.mask_data._mask_data[5,4] = 1
        self.mask_data._mask_data[5,5] = 1
        self.mask_data._mask_data[4,5] = 1
        self.mask_data.shrink()

        self.assertEqual(np.sum(self.mask_data._mask_data), 0)

    def test_saving_and_loading(self):
        self.mask_data.mask_ellipse(1024, 1024, 100, 100)
        self.mask_data.set_dimension((2048, 2048))

        mask_array = np.copy(self.mask_data.get_img())

        self.mask_data.save_mask("Data/test.mask")
        self.mask_data.load_mask("Data/test.mask")

        self.assertTrue(np.array_equal(mask_array, self.mask_data.get_img()))


        #loading an old style mask (text file with zeros and ones...)
        self.mask_data.load_mask("Data/test1.mask")






