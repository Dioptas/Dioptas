# -*- coding: utf-8 -*-

import unittest
from mock import MagicMock
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
data_path = os.path.join(unittest_path, '../data')

if QtGui.QApplication.instance() is None:
    app = QtGui.QApplication([])
else:
    app = QtGui.QApplication.instance()

class TestCalibrationController(unittest.TestCase):

    def setUp(self):
        self.img_model = ImgModel()
        self.mask_model = MaskModel()
        self.calibration_model = CalibrationModel(self.img_model)
        self.calibration_model._calibrants_working_dir = os.path.join(data_path, 'calibrants')
        self.calibration_model.integrate_1d = MagicMock()
        self.calibration_model.integrate_2d = MagicMock()

        self.calibration_widget = CalibrationWidget()
        self.working_dir = {}
        self.calibration_controller = CalibrationController(working_dir=self.working_dir,
                                                            img_model=self.img_model,
                                                            mask_model=self.mask_model,
                                                            widget=self.calibration_widget,
                                                            calibration_model=self.calibration_model)

    def tearDown(self):
        del self.img_model
        del self.calibration_model.cake_geometry
        del self.calibration_model.spectrum_geometry
        del self.calibration_model
        gc.collect()

    def test_automatic_calibration(self):
        self.calibration_controller.load_img(os.path.join(data_path, 'LaB6_40keV_MarCCD.tif'))
        self.calibration_controller.search_peaks(1179.6, 1129.4)
        self.calibration_controller.search_peaks(1268.5, 1119.8)
        self.calibration_controller.widget.sv_wavelength_txt.setText('0.31')
        self.calibration_controller.widget.sv_distance_txt.setText('200')
        self.calibration_controller.widget.sv_pixel_width_txt.setText('79')
        self.calibration_controller.widget.sv_pixel_height_txt.setText('79')
        calibrant_index = self.calibration_widget.calibrant_cb.findText('LaB6')
        self.calibration_controller.widget.calibrant_cb.setCurrentIndex(calibrant_index)

        QTest.mouseClick(self.calibration_widget.integrate_btn, QtCore.Qt.LeftButton)
        self.calibration_model.integrate_1d.assert_called_once_with()
        self.calibration_model.integrate_2d.assert_called_once_with()

        calibration_parameter = self.calibration_model.get_calibration_parameter()[0]
        self.assertAlmostEqual(calibration_parameter['dist'], .1967, places=4)

    @unittest.skip('')
    def test_loading_and_saving_of_calibration_files(self):
        self.calibration_controller.load_calibration(os.path.join(data_path, 'LaB6_40keV_MarCCD.poni'))
        self.calibration_controller.save_calibration(os.path.join(data_path, 'calibration.poni'))
        self.assertTrue(os.path.exists(os.path.join(data_path, 'calibration.poni')))
        os.remove(os.path.join(data_path, 'calibration.poni'))


if __name__ == '__main__':
    unittest.main()
