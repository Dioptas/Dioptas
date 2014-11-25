# -*- coding: utf8 -*-
__author__ = 'Clemens Prescher'


import unittest
import sys
import numpy as np
import matplotlib.pyplot as plt
from PyQt4 import QtGui, QtCore
from Controller.MainController import MainController

class SaveSettingsTest(unittest.TestCase):
    def setUp(self):
        self.app = QtGui.QApplication(sys.argv)

    def tearDown(self):
        del self.app

    def create_controller_and_data(self):
        self.controller = MainController()
        self.img_data = self.controller.img_data
        self.mask_data = self.controller.mask_data
        self.calibration_data = self.controller.calibration_data
        self.spectrum_data = self.controller.spectrum_data
        self.phase_data = self.controller.phase_data

    def test_filenames(self):
        self.create_controller_and_data()

        self.img_data.load("../Data/Mg2SiO4_ambient_001.tif")
        self.calibration_data.calibration_name = "test_calibration"
        self.spectrum_data.spectrum_filename = "test_spectrum"
        self.mask_data.filename = "yeah"
        self.controller.save_settings()

        self.create_controller_and_data()
        self.assertEqual(self.img_data.filename, "../Data/Mg2SiO4_ambient_001.tif")
        self.assertEqual(self.calibration_data.calibration_name,  "test_calibration")
        self.assertEqual(self.spectrum_data.spectrum_filename, "test_spectrum")
        self.assertEqual(self.mask_data.filename, "yeah")

    def test_img_data(self):
        self.create_controller_and_data()
        self.img_data.load("../Data/Mg2SiO4_ambient_001.tif")

        img_data_ar = np.copy(self.img_data._img_data)
        self.controller.save_settings()

        self.create_controller_and_data()
        self.assertEqual(np.sum(img_data_ar-self.img_data._img_data), 0)
        self.assertTrue(np.array_equal(img_data_ar, self.img_data._img_data))

    def test_mask_data(self):
        self.create_controller_and_data()
        self.mask_data.mask_ellipse(10,10,100,100)

        mask_data_array = np.copy(self.mask_data.get_mask())

        self.controller.save_settings()
        self.create_controller_and_data()

        self.assertEqual(np.sum(mask_data_array-self.mask_data.get_mask()), 0)
        self.assertTrue(np.array_equal(mask_data_array, self.mask_data.get_mask()))

    def test_calibration_data(self):
        self.create_controller_and_data()
        self.calibration_data.load("../Data/calibration.poni")

        center_x = self.calibration_data.spectrum_geometry.poni1

        self.controller.save_settings()
        self.create_controller_and_data()

        self.assertEqual(self.calibration_data.spectrum_geometry.poni1, center_x)

    def test_spectrum_data(self):
        self.create_controller_and_data()
        self.spectrum_data.load_spectrum("../Data/spec_test.txt")

        x, y = self.spectrum_data.spectrum.data
        x = np.copy(x)
        y = np.copy(y)

        self.controller.save_settings()
        self.create_controller_and_data()

        new_x, new_y = self.spectrum_data.spectrum.data

        self.assertAlmostEqual(np.sum(x-new_x), 0)
        self.assertAlmostEqual(np.sum(y-new_y), 0)



