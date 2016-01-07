# -*- coding: utf8 -*-

import unittest
import os

from model.CalibrationModel import CalibrationModel
from model.ImgModel import ImgModel
import gc


unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, 'data')

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
        self.calibration_model.spectrum_geometry.load(os.path.join(data_path, 'CeO2_Pilatus1M.poni'))
        self.assertEqual(self.calibration_model.spectrum_geometry.pixel1, 0.000172)


        self.calibration_model.load(os.path.join(data_path,'LaB6_40keV_MarCCD.poni'))
        self.assertEqual(self.calibration_model.spectrum_geometry.pixel1, 0.000079)


if __name__ == '__main__':
    unittest.main()