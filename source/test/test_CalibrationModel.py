# -*- coding: utf8 -*-
__author__ = 'Clemens Prescher'



import unittest

from model.CalibrationModel import CalibrationModel
from model.ImgModel import ImgModel
import gc

class CalibrationModelTest(unittest.TestCase):
    def setUp(self):
        self.img_model = ImgModel()
        self.calibration_model = CalibrationModel(self.img_model)

    def tearDown(self):
        del self.img_model
        del self.calibration_model.cake_geometry
        del self.calibration_model.spectrum_geometry
        del self.calibration_model
        gc.collect()

    def test_loading_calibration_gives_right_pixel_size(self):
        self.calibration_model.spectrum_geometry.load("Data/calibration_PE.poni")
        self.assertEqual(self.calibration_model.spectrum_geometry.pixel1, 0.0002)


        self.calibration_model.load("Data/calibration_PE.poni")
        self.assertEqual(self.calibration_model.spectrum_geometry.pixel1, 0.0002)