__author__ = 'Clemens Prescher'

from Data.ImgData import ImgData
from Data.CalibrationData import CalibrationData
from Controller.CalibrationController import CalibrationController
import unittest
from PySide import QtGui
import sys
import numpy as np
import matplotlib.pyplot as plt
import time


class CombinedDataTest(unittest.TestCase):
    def setUp(self):
        self.app = QtGui.QApplication(sys.argv)
        self.image_data = ImgData()
        self.calibration_data = CalibrationData(self.image_data)
        self.calibration_data._calibrants_working_dir = 'Data/Calibrants'

        self.calibration_controller = CalibrationController(img_data=self.image_data, \
                                                            calibration_data=self.calibration_data)

    def test_automatic_calibration1(self):
        self.calibration_controller.load_img('Data/LaB6_p49_40keV_006.tif')
        self.calibration_controller.search_peaks(1179.6, 1129.4)
        self.calibration_controller.search_peaks(1268.5, 1119.8)
        self.calibration_controller.view.sv_wavelength_txt.setText('0.31')
        self.calibration_controller.view.sv_distance_txt.setText('200')
        self.calibration_controller.view.sv_pixel_width_txt.setText('79')
        self.calibration_controller.view.sv_pixel_height_txt.setText('79')
        self.calibration_controller.view.calibrant_cb.setCurrentIndex(7)
        self.calibration_controller.calibrate()
        self.calibration_controller.view.cake_view.set_vertical_line_pos(1419.8, 653.4)

    def test_automatic_calibration2(self):
        self.calibration_controller.load_img('Data/LaB6_WOS_30keV_005.tif')
        self.calibration_controller.search_peaks(1245.2, 1919.3)
        self.calibration_controller.search_peaks(1334.0, 1823.7)
        self.calibration_controller.view.sv_wavelength_txt.setText('0.3344')
        self.calibration_controller.view.sv_distance_txt.setText('500')
        self.calibration_controller.view.sv_pixel_width_txt.setText('200')
        self.calibration_controller.view.sv_pixel_height_txt.setText('200')
        self.calibration_controller.view.calibrant_cb.setCurrentIndex(7)
        self.calibration_controller.calibrate()
        self.calibration_controller.view.cake_view.set_vertical_line_pos(206.5, 171.6)

    def tearDown(self):
        return


