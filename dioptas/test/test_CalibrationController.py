# -*- coding: utf-8 -*-

import unittest
import sys
import os
import gc

from PyQt4 import QtGui, QtCore
from PyQt4.QtTest import QTest

from model.ImgModel import ImgModel
from model.MaskModel import MaskModel
from model.CalibrationModel import CalibrationModel
from controller.CalibrationController import CalibrationController
from widgets.CalibrationWidget import CalibrationWidget

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, 'data')


class CalibrationControllerTest(unittest.TestCase):

    app = QtGui.QApplication(sys.argv)

    def setUp(self):
        self.img_model = ImgModel()
        self.mask_model = MaskModel()
        self.calibration_model = CalibrationModel(self.img_model)
        self.calibration_model._calibrants_working_dir = os.path.join(data_path, 'calibrants')
        self.calibration_widget = CalibrationWidget()
        self.working_dir = {}
        self.calibration_controller = CalibrationController(working_dir=self.working_dir,
                                                            img_model=self.img_model,
                                                            mask_model=self.mask_model,
                                                            widget=self.calibration_widget,
                                                            calibration_model=self.calibration_model)
        print 'lets go'

    def tearDown(self):
        del self.img_model
        del self.calibration_model.cake_geometry
        del self.calibration_model.spectrum_geometry
        del self.calibration_model
        gc.collect()

    def load_pilatus_1M_and_pick_peaks(self):
        self.calibration_controller.load_img(os.path.join(data_path, 'CeO2_Pilatus1M.tif'))
        QTest.mouseClick(self.calibration_widget.automatic_peak_num_inc_cb, QtCore.Qt.LeftButton)

        self.assertFalse(self.calibration_widget.automatic_peak_num_inc_cb.isChecked())
        self.calibration_controller.search_peaks(517.664434674, 647.529865592)
        self.calibration_controller.search_peaks(667.380513299, 525.252854758)
        self.calibration_controller.search_peaks(671.110095329, 473.571503774)
        self.calibration_controller.search_peaks(592.788872703, 350.495296791)
        self.calibration_controller.search_peaks(387.395462348, 390.987901686)
        self.calibration_controller.search_peaks(367.94835605, 554.290314848)

        self.calibration_widget.sv_wavelength_txt.setText('0.406626')
        self.calibration_widget.sv_distance_txt.setText('200')
        self.calibration_widget.sv_pixel_width_txt.setText('172')
        self.calibration_widget.sv_pixel_height_txt.setText('172')
        calibrant_index = self.calibration_widget.calibrant_cb.findText('CeO2')
        self.calibration_widget.calibrant_cb.setCurrentIndex(calibrant_index)

        self.mask_model.set_dimension(self.img_model.img_data.shape)

    def test_automatic_calibration1(self):
        self.calibration_controller.load_img(os.path.join(data_path, 'LaB6_40keV_MarCCD.tif'))
        self.calibration_controller.search_peaks(1179.6, 1129.4)
        self.calibration_controller.search_peaks(1268.5, 1119.8)
        self.calibration_controller.widget.sv_wavelength_txt.setText('0.31')
        self.calibration_controller.widget.sv_distance_txt.setText('200')
        self.calibration_controller.widget.sv_pixel_width_txt.setText('79')
        self.calibration_controller.widget.sv_pixel_height_txt.setText('79')
        calibrant_index = self.calibration_widget.calibrant_cb.findText('LaB6')
        self.calibration_controller.widget.calibrant_cb.setCurrentIndex(calibrant_index)
        self.calibration_controller.calibrate()
        self.calibration_controller.widget.cake_view.set_vertical_line_pos(1419.8, 653.4)

    def test_automatic_calibration2(self):
        self.calibration_controller.load_img(os.path.join(data_path, 'LaB6_OffCenter_PE.tif'))
        self.calibration_controller.search_peaks(1245.2, 1919.3)
        self.calibration_controller.search_peaks(1334.0, 1823.7)
        self.calibration_controller.widget.sv_wavelength_txt.setText('0.3344')
        self.calibration_controller.widget.sv_distance_txt.setText('500')
        self.calibration_controller.widget.sv_pixel_width_txt.setText('200')
        self.calibration_controller.widget.sv_pixel_height_txt.setText('200')
        calibrant_index = self.calibration_widget.calibrant_cb.findText('LaB6')
        self.calibration_controller.widget.calibrant_cb.setCurrentIndex(calibrant_index)
        self.calibration_controller.calibrate()
        self.calibration_controller.widget.cake_view.set_vertical_line_pos(206.5, 171.6)

    def test_automatic_calibration3(self):
        self.load_pilatus_1M_and_pick_peaks()

        start_values = self.calibration_widget.get_start_values()
        self.assertAlmostEqual(start_values['wavelength'], 0.406626e-10)
        self.assertAlmostEqual(start_values['pixel_height'], 172e-6)
        self.assertAlmostEqual(start_values['pixel_width'], 172e-6)
        self.calibration_controller.load_calibrant()
        self.assertAlmostEqual(self.calibration_model.calibrant.wavelength, 0.406626e-10)

        QTest.mouseClick(self.calibration_widget.integrate_btn, QtCore.Qt.LeftButton)
        calibration_parameter = self.calibration_model.get_calibration_parameter()[0]

        self.assertAlmostEqual(calibration_parameter['dist'], .2086, places=4)

    def test_automatic_calibration_with_supersampling(self):
        self.load_pilatus_1M_and_pick_peaks()
        self.img_model.set_supersampling(2)
        self.calibration_model.set_supersampling(2)
        self.calibration_controller.calibrate()

    def test_automatic_calibration_with_supersampling_and_mask(self):
        self.load_pilatus_1M_and_pick_peaks()
        self.img_model.set_supersampling(2)
        self.mask_model.mask_below_threshold(self.img_model._img_data, 1)
        self.mask_model.set_supersampling(2)
        self.calibration_model.set_supersampling(2)
        self.calibration_controller.widget.use_mask_cb.setChecked(True)
        self.calibration_controller.calibrate()

    def test_calibrating_one_image_size_and_loading_different_image_size(self):
        self.load_pilatus_1M_and_pick_peaks()
        self.calibration_controller.calibrate()
        self.calibration_model.integrate_1d()
        self.calibration_model.integrate_2d()
        self.calibration_controller.load_img(os.path.join(data_path, 'CeO2_Pilatus1M.tif'))
        self.calibration_model.integrate_1d()
        self.calibration_model.integrate_2d()

    def test_loading_and_saving_of_calibration_files(self):
        self.calibration_controller.load_calibration(os.path.join(data_path, 'LaB6_40keV_MarCCD.poni'))
        self.calibration_controller.save_calibration(os.path.join(data_path, 'calibration.poni'))
        self.assertTrue(os.path.exists(os.path.join(data_path, 'calibration.poni')))
        os.remove(os.path.join(data_path, 'calibration.poni'))


if __name__ == '__main__':
    unittest.main()
