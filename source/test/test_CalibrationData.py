# -*- coding: utf8 -*-
__author__ = 'Clemens Prescher'



import unittest

from model.CalibrationData import CalibrationData
from model.ImgData import ImgData
import gc

class MaskUnitTest(unittest.TestCase):
    def setUp(self):
        self.img_data = ImgData()
        self.calibration_data = CalibrationData(self.img_data)

    def tearDown(self):
        del self.img_data
        del self.calibration_data.cake_geometry
        del self.calibration_data.spectrum_geometry
        del self.calibration_data
        gc.collect()

    def test_loading_calibration_gives_right_pixel_size(self):
        self.calibration_data.spectrum_geometry.load("Data/calibration_PE.poni")
        self.assertEqual(self.calibration_data.spectrum_geometry.pixel1, 0.0002)


        self.calibration_data.load("Data/calibration_PE.poni")
        self.assertEqual(self.calibration_data.spectrum_geometry.pixel1, 0.0002)