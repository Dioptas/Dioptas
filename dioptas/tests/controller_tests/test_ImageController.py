# -*- coding: utf8 -*-

import gc
import os
import shutil
import unittest

from PyQt4 import QtGui, QtCore
from PyQt4.QtTest import QTest

from controller.integration.ImageController import ImageController
from model.CalibrationModel import CalibrationModel
from model.ImgModel import ImgModel
from model.MaskModel import MaskModel
from model.PatternModel import PatternModel
from widgets.integration import IntegrationWidget

unittest_data_path = os.path.join(os.path.dirname(__file__), '../data')

app = QtGui.QApplication([])


class ImageControllerTest(unittest.TestCase):
    def setUp(self):
        self.working_dir = {'image': ''}

        self.widget = IntegrationWidget()
        self.image_model = ImgModel()
        self.mask_model = MaskModel()
        self.spectrum_model = PatternModel()
        self.calibration_model = CalibrationModel(self.image_model)

        self.controller = ImageController(
                working_dir=self.working_dir,
                widget=self.widget,
                img_model=self.image_model,
                mask_model=self.mask_model,
                spectrum_model=self.spectrum_model,
                calibration_model=self.calibration_model)

    def tearDown(self):
        if os.path.exists(os.path.join(unittest_data_path, 'image_003.tif')):
            os.remove(os.path.join(unittest_data_path, 'image_003.tif'))
        del self.widget
        del self.image_model
        del self.mask_model
        del self.spectrum_model
        del self.calibration_model
        del self.controller
        gc.collect()


    def test_automatic_file_processing(self):
        # get into a specific folder
        self.controller.load_file(os.path.join(unittest_data_path, 'image_001.tif'))
        self.assertEqual(str(self.widget.img_filename_txt.text()), 'image_001.tif')
        self.assertEqual(self.controller.working_dir['image'], unittest_data_path)

        # enable autoprocessing:
        QTest.mouseClick(self.widget.autoprocess_cb, QtCore.Qt.LeftButton,
                         pos=QtCore.QPoint(2, self.widget.autoprocess_cb.height() / 2.0))
        self.assertFalse(self.controller._directory_watcher.signalsBlocked())

        self.assertTrue(self.widget.autoprocess_cb.isChecked())
        shutil.copy2(os.path.join(unittest_data_path, 'image_001.tif'),
                     os.path.join(unittest_data_path, 'image_003.tif'))

        self.controller._directory_watcher._file_system_watcher.directoryChanged.emit(unittest_data_path)

        self.assertEqual('image_003.tif', str(self.widget.img_filename_txt.text()))
