# -*- coding: utf8 -*-
__author__ = 'Clemens Prescher'


import unittest
import sys
import time
import numpy as np
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
        self.assertTrue(np.array_equal(img_data_ar, self.img_data._img_data))

