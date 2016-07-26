# -*- coding: utf8 -*-

import unittest
from mock import MagicMock
import os
import gc

from PyQt4 import QtGui

from controller.MainController import MainController

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, os.pardir, 'data')


class SaveSettingsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtGui.QApplication.instance()
        if cls.app is None:
            cls.app = QtGui.QApplication([])

    def create_controller_and_data(self):
        self.controller = MainController()
        self.controller.model.calibration_model.integrate_1d = MagicMock(
            return_value=(self.controller.model.calibration_model.tth,
                          self.controller.model.calibration_model.int))

    def tearDown(self):
        self.controller.model.clear()
        del self.controller.model
        del self.controller
        gc.collect()

    def test_calibration_data(self):
        self.create_controller_and_data()
        self.controller.model.calibration_model.load(os.path.join(data_path, "LaB6_40keV_MarCCD.poni"))

        center_x = self.controller.model.calibration_model.spectrum_geometry.poni1

        self.controller.save_settings()
        self.tearDown()
        self.create_controller_and_data()

        self.assertEqual(self.controller.model.calibration_model.spectrum_geometry.poni1, center_x)


if __name__ == '__main__':
    unittest.main()
