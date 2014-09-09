# -*- coding: utf-8 -*-
__author__ = 'Clemens Prescher'

import unittest
import sys
import os
import numpy as np
import time

from PyQt4 import QtGui
import matplotlib.pyplot as plt


from Data.ImgData import ImgData
from Data.MaskData import MaskData
from Data.CalibrationData import CalibrationData
from Controller.CalibrationController import CalibrationController
from Views.CalibrationView import CalibrationView


class CalibrationControllerTest(unittest.TestCase):
    def setUp(self):
        self.app = QtGui.QApplication(sys.argv)
        self.img_data = ImgData()
        self.mask_data = MaskData()
        self.calibration_data = CalibrationData(self.img_data)
        self.calibration_data._calibrants_working_dir = 'Data/Calibrants'
        self.calibration_view = CalibrationView()

        self.working_dir = {}

        self.calibration_controller = CalibrationController(working_dir=self.working_dir,
                                                            img_data=self.img_data,
                                                            mask_data=self.mask_data,
                                                            view=self.calibration_view,
                                                            calibration_data=self.calibration_data)

    def tearDown(self):
        del self.app

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

    def test_automatic_calibration_with_supersampling(self):
        self.calibration_controller.load_img('Data/LaB6_p49_40keV_006.tif')
        self.calibration_controller.search_peaks(1179.6, 1129.4)
        self.calibration_controller.search_peaks(1268.5, 1119.8)
        self.calibration_controller.view.sv_wavelength_txt.setText('0.31')
        self.calibration_controller.view.sv_distance_txt.setText('200')
        self.calibration_controller.view.sv_pixel_width_txt.setText('79')
        self.calibration_controller.view.sv_pixel_height_txt.setText('79')
        self.calibration_controller.view.calibrant_cb.setCurrentIndex(7)
        self.img_data.set_supersampling(2)
        self.calibration_data.set_supersampling(2)
        self.calibration_controller.calibrate()

    def test_automatic_calibration_with_supersampling_and_mask(self):
        self.calibration_controller.load_img('Data/LaB6_p49_40keV_006.tif')
        self.calibration_controller.search_peaks(1179.6, 1129.4)
        self.calibration_controller.search_peaks(1268.5, 1119.8)
        self.calibration_controller.view.sv_wavelength_txt.setText('0.31')
        self.calibration_controller.view.sv_distance_txt.setText('200')
        self.calibration_controller.view.sv_pixel_width_txt.setText('79')
        self.calibration_controller.view.sv_pixel_height_txt.setText('79')
        self.calibration_controller.view.calibrant_cb.setCurrentIndex(7)
        self.img_data.set_supersampling(2)
        self.mask_data.mask_below_threshold(self.img_data._img_data, 1)
        self.mask_data.set_supersampling(2)
        self.calibration_data.set_supersampling(2)
        self.calibration_controller.view.use_mask_cb.setChecked(True)
        self.calibration_controller.calibrate()
