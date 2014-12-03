# -*- coding: utf8 -*-
__author__ = 'Clemens Prescher'



import unittest
import numpy as np

from Data.ImgCorrection import ImgCorrectionManager, ImgCorrectionInterface


class DummyCorrection(ImgCorrectionInterface):
    def __init__(self, shape, number=1):
        self._data = np.ones(shape)*number
        self._shape = shape

    def get_data(self):
        return self._data

    def shape(self):
        return self._shape

class ImgCorrectionsUnitTest(unittest.TestCase):

    def setUp(self):
        self.corrections = ImgCorrectionManager()

    def tearDown(self):
        pass

    def test_add_first_matrix_and_detect_shape(self):
        cor = DummyCorrection((2048, 2048))

        self.corrections.add(cor)

        self.assertTrue(np.array_equal(cor.get_data(), self.corrections.get_data()))
        self.assertEqual(self.corrections.shape, (2048, 2048))

    def test_add_several_corrections(self):
        cor1 = DummyCorrection((2048, 2048),2)
        cor2 = DummyCorrection((2048, 2048),3)
        cor3 = DummyCorrection((2048, 2048),5)

        self.corrections.add(cor1)
        self.corrections.add(cor2)
        self.corrections.add(cor3)

        self.assertEqual(np.mean(self.corrections.get_data()), 2*3*5)

    def test_delete_corrections_without_names(self):
        self.assertEqual(self.corrections.get_data(), None)

        self.corrections.add(DummyCorrection((2048, 2048), 3))
        self.corrections.delete()
        self.assertEqual(self.corrections.get_data(), None)

        self.corrections.add(DummyCorrection((2048,2048),2))
        self.corrections.add(DummyCorrection((2048,2048),3))

        self.corrections.delete()
        self.assertEqual(np.mean(self.corrections.get_data()),2)
        self.corrections.delete()

    def test_delete_corrections_with_names(self):
        #add two corrections and check if both applied
        self.corrections.add(DummyCorrection((2048, 2048), 3), "cbn Correction")
        self.corrections.add(DummyCorrection((2048, 2048), 5), "oblique angle Correction")
        self.assertEqual(np.mean(self.corrections.get_data()), 3*5)

        #delete the first by name
        self.corrections.delete("cbn Correction")
        self.assertEqual(np.mean(self.corrections.get_data()), 5)

        #trying to delete non existent name will result in KeyError
        self.assertRaises(KeyError, self.corrections.delete, "blub")

        #just deleting something, when all corrections have a name will not change anything
        self.corrections.delete()
        self.assertEqual(np.mean(self.corrections.get_data()), 5)