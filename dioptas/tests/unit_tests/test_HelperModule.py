# -*- coding: utf8 -*-

import unittest
import os
import numpy as np

from PyQt4 import QtGui

from model.CalibrationModel import CalibrationModel
from model.ImgModel import ImgModel
from model.util.HelperModule import reverse_interpolate_two_array

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')


class PatternTest(unittest.TestCase):
    app = QtGui.QApplication([])

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_reverse_interpolate_two_arrays_simple(self):
        array1 = np.array([range(0, 100)] * 100) * 0.05
        array2 = array1.T

        pos1 = 2.3
        pos2 = 3.6

        ind1, ind2 = reverse_interpolate_two_array(pos1, array1, pos2, array2, 0.5, 0.5)

        self.assertAlmostEqual(pos1, array1[ind1, ind2])
        self.assertAlmostEqual(pos2, array2[ind1, ind2])

    def test_get_xy_from_tth_and_azi_array_with_calibration(self):
        self.img_model = ImgModel()
        self.calibration_model = CalibrationModel(self.img_model)
        self.img_model.load(os.path.join(data_path, 'image_001.tif'))
        self.calibration_model.load(os.path.join(data_path, 'LaB6_40keV_MarCCD.poni'))

        self.calibration_model.integrate_1d(1000)

        start_ind1 = 1033
        start_ind2 = 230

        tth_array = self.calibration_model.spectrum_geometry.ttha
        azi_array = self.calibration_model.spectrum_geometry.chia

        tth_step = np.max(np.diff(tth_array)) * 0.5
        azi_step = np.max(np.diff(azi_array)) * 0.5

        tth = tth_array[start_ind1, start_ind2]
        azi = azi_array[start_ind1, start_ind2]

        result_ind1, result_ind2 = reverse_interpolate_two_array(tth, tth_array, azi, azi_array, tth_step, azi_step)

        print result_ind1
        print result_ind2

        self.assertEqual(start_ind1, result_ind1)
        self.assertEqual(start_ind2, result_ind2)
