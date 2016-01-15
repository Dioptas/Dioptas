# -*- coding: utf8 -*-

import unittest
import gc
import os
import numpy as np

from model.MaskModel import MaskModel

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')


class MaskModelTest(unittest.TestCase):
    def setUp(self):
        self.mask_model = MaskModel()
        self.img = np.zeros((10, 10))
        self.mask_model.set_dimension(self.img.shape)

    def tearDown(self):
        del self.mask_model
        del self.img
        gc.collect()

    def test_growing_masks(self):
        self.mask_model._mask_data[4, 4] = 1
        self.mask_model._mask_data[0, 0] = 1
        self.mask_model._mask_data[0, 9] = 1
        self.mask_model._mask_data[9, 9] = 1
        self.mask_model._mask_data[9, 0] = 1

        self.mask_model.grow()

        # tests corners
        self.assertEqual(self.mask_model._mask_data[0, 1], 1)
        self.assertEqual(self.mask_model._mask_data[1, 1], 1)
        self.assertEqual(self.mask_model._mask_data[1, 0], 1)

        self.assertEqual(self.mask_model._mask_data[0, 8], 1)
        self.assertEqual(self.mask_model._mask_data[1, 8], 1)
        self.assertEqual(self.mask_model._mask_data[1, 9], 1)

        self.assertEqual(self.mask_model._mask_data[8, 0], 1)
        self.assertEqual(self.mask_model._mask_data[8, 1], 1)
        self.assertEqual(self.mask_model._mask_data[9, 1], 1)

        self.assertEqual(self.mask_model._mask_data[8, 8], 1)
        self.assertEqual(self.mask_model._mask_data[8, 9], 1)
        self.assertEqual(self.mask_model._mask_data[9, 8], 1)

        # tests center
        self.assertEqual(self.mask_model._mask_data[3, 3], 1)
        self.assertEqual(self.mask_model._mask_data[4, 3], 1)
        self.assertEqual(self.mask_model._mask_data[5, 3], 1)

        self.assertEqual(self.mask_model._mask_data[3, 5], 1)
        self.assertEqual(self.mask_model._mask_data[4, 5], 1)
        self.assertEqual(self.mask_model._mask_data[5, 5], 1)

        self.assertEqual(self.mask_model._mask_data[3, 4], 1)
        self.assertEqual(self.mask_model._mask_data[5, 4], 1)

    def test_shrink_mask(self):
        self.mask_model._mask_data[4, 4] = 1
        self.mask_model._mask_data[0, 0] = 1
        self.mask_model._mask_data[0, 9] = 1
        self.mask_model._mask_data[9, 9] = 1
        self.mask_model._mask_data[9, 0] = 1

        self.before_mask = np.copy(self.mask_model._mask_data)
        self.mask_model.grow()
        self.mask_model.shrink()

        self.assertTrue(np.array_equal(self.before_mask, self.mask_model._mask_data))

        self.mask_model.clear_mask()

        self.mask_model._mask_data[4, 4] = 1
        self.mask_model._mask_data[5, 4] = 1
        self.mask_model._mask_data[5, 5] = 1
        self.mask_model._mask_data[4, 5] = 1
        self.mask_model.shrink()

        self.assertEqual(np.sum(self.mask_model._mask_data), 0)

    def test_saving_and_loading(self):
        self.mask_model.mask_ellipse(1024, 1024, 100, 100)
        self.mask_model.set_dimension((2048, 2048))

        mask_array = np.copy(self.mask_model.get_img())

        filename = os.path.join(data_path, 'dummy.mask')

        self.mask_model.save_mask(filename)
        self.mask_model.load_mask(filename)

        self.assertTrue(np.array_equal(mask_array, self.mask_model.get_img()))
        os.remove(filename)


if __name__ == '__main__':
    unittest.main()
