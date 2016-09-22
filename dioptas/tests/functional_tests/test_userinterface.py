import unittest
from mock import MagicMock
import os
import gc

import numpy as np

from PyQt5 import QtWidgets, QtCore

from ...controller import MainController

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, os.pardir, 'data')


class UserInterFaceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance()
        if cls.app is None:
            cls.app = QtWidgets.QApplication([])

    @classmethod
    def tearDownClass(cls):
        del cls.app
        gc.collect()

    def setUp(self):
        self.controller = MainController(use_settings=False)
        self.model = self.controller.model
        self.model.calibration_model.integrate_1d = MagicMock(
            return_value=(self.model.calibration_model.tth,
                          self.model.calibration_model.int))
        self.phase_model = self.model.phase_model

        self.calibration_widget = self.controller.widget.calibration_widget
        self.mask_widget = self.controller.widget.mask_widget
        self.integration_widget = self.controller.widget.integration_widget

        self.integration_controller = self.controller.integration_controller
        self.model.calibration_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.poni'))
        self.model.img_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.tif'))

        self.integration_spectrum_controller = self.integration_controller.spectrum_controller
        self.integration_image_controller = self.integration_controller.image_controller

    def tearDown(self):
        del self.integration_spectrum_controller
        self.model.clear()
        del self.integration_widget
        del self.integration_controller
        del self.model
        gc.collect()

    def test_synchronization_of_view_range(self):
        # calibration and mask view
        self.calibration_widget.img_widget.img_view_box.setRange(QtCore.QRectF(-10, -10, 20, 20))
        self.controller.widget.tabWidget.setCurrentIndex(1)

        self.assertAlmostEqual(np.sum(np.array(self.calibration_widget.img_widget.img_view_box.targetRange()) - \
                                      np.array(self.mask_widget.img_widget.img_view_box.targetRange())), 0)

        self.mask_widget.img_widget.img_view_box.setRange(QtCore.QRectF(100, 100, 300, 300))
        self.controller.widget.tabWidget.setCurrentIndex(0)

        self.assertAlmostEqual(np.sum(np.array(self.calibration_widget.img_widget.img_view_box.targetRange()) - \
                                      np.array(self.mask_widget.img_widget.img_view_box.targetRange())), 0)
