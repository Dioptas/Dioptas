# -*- coding: utf8 -*-

import unittest
import os

from model.CalibrationModel import CalibrationModel
from model.ImgModel import ImgModel
import gc

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')
calibrant_path = os.path.join(unittest_path, '../../calibrants')


class CalibrationModelTest(unittest.TestCase):
    def setUp(self):
        self.img_model = ImgModel()
        self.calibration_model = CalibrationModel(self.img_model)

    def tearDown(self):
        del self.img_model
        if hasattr(self.calibration_model, 'cake_geometry'):
            del self.calibration_model.cake_geometry
        del self.calibration_model.spectrum_geometry
        del self.calibration_model
        gc.collect()

    def test_loading_calibration_gives_right_pixel_size(self):
        self.calibration_model.spectrum_geometry.load(os.path.join(data_path, 'CeO2_Pilatus1M.poni'))
        self.assertEqual(self.calibration_model.spectrum_geometry.pixel1, 0.000172)

        self.calibration_model.load(os.path.join(data_path, 'LaB6_40keV_MarCCD.poni'))
        self.assertEqual(self.calibration_model.spectrum_geometry.pixel1, 0.000079)

    def test_find_peaks_automatic(self):
        self.load_pilatus_1M_and_find_peaks()
        self.assertEqual(len(self.calibration_model.points), 6)
        for points in self.calibration_model.points:
            self.assertGreater(len(points), 0)

    def test_calibration_with_supersampling(self):
        self.load_pilatus_1M_and_find_peaks()
        self.calibration_model.set_calibrant(os.path.join(calibrant_path, 'LaB6.D'))
        self.calibration_model.calibrate()
        normal_poni1 = self.calibration_model.spectrum_geometry.poni1
        self.img_model.set_supersampling(2)
        self.calibration_model.set_supersampling(2)
        self.calibration_model.calibrate()
        self.assertAlmostEqual(normal_poni1, self.calibration_model.spectrum_geometry.poni1)

    def load_pilatus_1M_and_find_peaks(self):
        self.img_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.tif'))
        self.calibration_model.find_peaks_automatic(517.664434674, 647.529865592, 0)
        self.calibration_model.find_peaks_automatic(667.380513299, 525.252854758, 1)
        self.calibration_model.find_peaks_automatic(671.110095329, 473.571503774, 2)
        self.calibration_model.find_peaks_automatic(592.788872703, 350.495296791, 3)
        self.calibration_model.find_peaks_automatic(387.395462348, 390.987901686, 4)
        self.calibration_model.find_peaks_automatic(367.94835605, 554.290314848, 5)

    def test_calibration1(self):
        self.img_model.load(os.path.join(data_path, 'LaB6_40keV_MarCCD.tif'))
        self.calibration_model.find_peaks_automatic(1179.6, 1129.4, 0)
        self.calibration_model.find_peaks_automatic(1268.5, 1119.8, 1)
        self.calibration_model.set_calibrant(os.path.join(calibrant_path, 'LaB6.D'))
        self.calibration_model.calibrate()

        self.assertGreater(self.calibration_model.spectrum_geometry.poni1, 0)
        self.assertAlmostEqual(self.calibration_model.spectrum_geometry.dist, 0.18, delta=0.01)
        self.assertGreater(self.calibration_model.cake_geometry.poni1, 0)

    def test_calibration2(self):
        self.img_model.load(os.path.join(data_path, 'LaB6_OffCenter_PE.tif'))
        self.calibration_model.find_peaks_automatic(1245.2, 1919.3, 0)
        self.calibration_model.find_peaks_automatic(1334.0, 1823.7, 1)
        self.calibration_model.start_values['dist'] = 500e-3
        self.calibration_model.start_values['pixel_height'] = 200e-6
        self.calibration_model.start_values['pixel_width'] = 200e-6
        self.calibration_model.set_calibrant(os.path.join(calibrant_path, 'LaB6.D'))
        self.calibration_model.calibrate()

        self.assertGreater(self.calibration_model.spectrum_geometry.poni1, 0)
        self.assertAlmostEqual(self.calibration_model.spectrum_geometry.dist, 0.500, delta=0.01)
        self.assertGreater(self.calibration_model.cake_geometry.poni1, 0)

    def test_calibration3(self):
        self.load_pilatus_1M_and_find_peaks()
        self.calibration_model.start_values['wavelength'] = 0.406626e-10
        self.calibration_model.start_values['pixel_height'] = 172e-6
        self.calibration_model.start_values['pixel_width'] = 172e-6
        self.calibration_model.set_calibrant(os.path.join(calibrant_path, 'LaB6.D'))
        self.calibration_model.calibrate()

        self.assertGreater(self.calibration_model.spectrum_geometry.poni1, 0)
        self.assertAlmostEqual(self.calibration_model.spectrum_geometry.dist, 0.100, delta=0.02)
        self.assertGreater(self.calibration_model.cake_geometry.poni1, 0)


if __name__ == '__main__':
    unittest.main()
