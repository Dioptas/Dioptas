# -*- coding: utf8 -*-

import unittest
import os
import numpy as np

from PyQt4 import QtGui

from model.CalibrationModel import CalibrationModel
from model.ImgModel import ImgModel
from model.util.HelperModule import reverse_interpolate_two_array, reverse_interpolate_two_array2

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')


class HelperModuleTest(unittest.TestCase):
    app = QtGui.QApplication([])

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_get_xy_from_tth_and_azi_array_with_calibration(self):
        self.img_model = ImgModel()
        self.calibration_model = CalibrationModel(self.img_model)
        self.img_model.load(os.path.join(data_path, 'image_001.tif'))
        self.calibration_model.load(os.path.join(data_path, 'LaB6_40keV_MarCCD.poni'))

        self.calibration_model.integrate_1d(1000)

        tth_array = self.calibration_model.spectrum_geometry.ttha
        azi_array = self.calibration_model.spectrum_geometry.chia

        for i in range(100):
            ind1 = np.random.random_integers(0, 2023)
            ind2 = np.random.random_integers(0, 2023)

            tth = tth_array[ind1, ind2]
            azi = azi_array[ind1, ind2]

            result_ind1, result_ind2 = self.calibration_model.get_pixel_ind(tth, azi)

            self.assertAlmostEqual(ind1, result_ind1, places=3)
            self.assertAlmostEqual(ind2, result_ind2, places=3)
