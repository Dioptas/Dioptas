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


    def test_calibration_data(self):
        self.create_controller_and_data()
        self.calibration_data.load("Data/calibration.poni")

        center_x = self.calibration_data.spectrum_geometry.poni1

        self.controller.save_settings()
        self.create_controller_and_data()

        self.assertEqual(self.calibration_data.spectrum_geometry.poni1, center_x)




