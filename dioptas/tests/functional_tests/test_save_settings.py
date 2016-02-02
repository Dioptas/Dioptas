# -*- coding: utf8 -*-

import unittest
from mock import MagicMock
import os
import gc

import numpy as np

from PyQt4 import QtGui

from controller.MainController import MainController

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, os.pardir, 'data')


class SaveSettingsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtGui.QApplication([])

    @classmethod
    def tearDownClass(cls):
        cls.app.quit()

    def create_controller_and_data(self):
        self.controller = MainController()
        self.img_model = self.controller.img_model
        self.mask_model = self.controller.mask_model
        self.calibration_model = self.controller.calibration_model
        self.calibration_model.integrate_1d = MagicMock(return_value=(self.calibration_model.tth,
                                                                      self.calibration_model.int))
        self.spectrum_model = self.controller.spectrum_model
        self.phase_model = self.controller.phase_model

    def tearDown(self):
        del self.calibration_model.cake_geometry
        del self.calibration_model.spectrum_geometry
        del self.calibration_model
        del self.img_model
        del self.mask_model
        del self.controller
        gc.collect()

    def test_calibration_data(self):
        self.create_controller_and_data()
        self.calibration_model.load(os.path.join(data_path, "LaB6_40keV_MarCCD.poni"))

        center_x = self.calibration_model.spectrum_geometry.poni1

        self.controller.save_settings()
        self.tearDown()
        self.create_controller_and_data()

        self.assertEqual(self.calibration_model.spectrum_geometry.poni1, center_x)


if __name__ == '__main__':
    unittest.main()
