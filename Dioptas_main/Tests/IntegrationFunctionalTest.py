# -*- coding: utf8 -*-
__author__ = 'Clemens Prescher'

import unittest
import sys

import numpy as np
from PyQt4 import QtGui, QtCore
from PyQt4.QtTest import QTest

from Controller.MainController import MainController

class IntegrationFunctionalTest(unittest.TestCase):
    def setUp(self):
        self.app = QtGui.QApplication(sys.argv)
        self.main_controller = MainController(self.app)
        self.main_controller.calibration_controller.load_calibration('Data/LaB6_p49_40keV_006.poni', update_all=False)
        self.main_controller.calibration_controller.load_img('Data/LaB6_p49_40keV_006.tif')
        self.main_controller.view.tabWidget.setCurrentIndex(2)
        self.integration_view = self.main_controller.integration_controller.view

    def tearDown(self):
        del self.app

    def enter_value_into_text_field(self, text_field, value):
        text_field.setText('')
        QTest.keyClicks(text_field, str(value))
        QTest.keyPress(text_field, QtCore.Qt.Key_Enter)
        QtGui.QApplication.processEvents()

    def test_changing_number_of_integration_bins(self):
        # Edith wants to change the number of integration bins in order to see the effect of binning onto her line
        # shape. She sees that there is an option in the X tab and deselects automatic and sees that the sbinbox
        # becomes editable.
        self.main_controller.view.integration_widget.tabWidget.setCurrentIndex(4)
        self.assertFalse(self.integration_view.bin_count_txt.isEnabled())
        QTest.mouseClick(self.integration_view.automatic_binning_cb, QtCore.Qt.LeftButton)

        self.assertTrue(self.integration_view.bin_count_txt.isEnabled())

        # she sees that the current value and wants to double it and notices that the spectrum looks a little bit
        # smoother
        self.assertEqual(int(str(self.integration_view.bin_count_txt.text())),1595)
        previous_number_of_points = len(self.main_controller.spectrum_data.spectrum._x)
        self.enter_value_into_text_field(self.integration_view.bin_count_txt, 2*1595)

        self.assertEqual(len(self.main_controller.spectrum_data.spectrum._x), 2*previous_number_of_points)

        # then she decides that having an automatic estimation may probably be better and changes back to automatic.
        # immediately the number is restored and the image looks like when she started
        QTest.mouseClick(self.integration_view.automatic_binning_cb, QtCore.Qt.LeftButton)
        self.assertEqual(int(str(self.integration_view.bin_count_txt.text())), 1595)
        self.assertEqual(len(self.main_controller.spectrum_data.spectrum._x), previous_number_of_points)