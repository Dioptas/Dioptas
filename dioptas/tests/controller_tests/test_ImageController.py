# -*- coding: utf8 -*-

import os
import gc
import shutil
import numpy as np
from mock import MagicMock

from tests.utility import QtTest

from PyQt4 import QtCore, QtGui
from PyQt4.QtTest import QTest

from widgets.integration import IntegrationWidget
from controller.integration.ImageController import ImageController
from model.DioptasModel import DioptasModel

unittest_data_path = os.path.join(os.path.dirname(__file__), '../data')


def click_button(widget):
    QTest.mouseClick(widget, QtCore.Qt.LeftButton)


def click_checkbox(checkbox_widget):
    QTest.mouseClick(checkbox_widget, QtCore.Qt.LeftButton,
                     pos=QtCore.QPoint(2, checkbox_widget.height() / 2.0))


class ImageControllerTest(QtTest):
    def setUp(self):
        self.working_dir = {'image': ''}

        self.widget = IntegrationWidget()
        self.model = DioptasModel()

        self.controller = ImageController(
            working_dir=self.working_dir,
            widget=self.widget,
            dioptas_model=self.model)

    def tearDown(self):
        if os.path.exists(os.path.join(unittest_data_path, 'image_003.tif')):
            os.remove(os.path.join(unittest_data_path, 'image_003.tif'))
        del self.widget
        del self.model
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

        self.assertFalse(self.model.configurations[0].img_model._directory_watcher.signalsBlocked())
        self.assertFalse(
            self.model.configurations[0].img_model._directory_watcher._file_system_watcher.signalsBlocked())

        self.assertTrue(self.widget.autoprocess_cb.isChecked())
        self.assertTrue(self.model.img_model.autoprocess)

        shutil.copy2(os.path.join(unittest_data_path, 'image_001.tif'),
                     os.path.join(unittest_data_path, 'image_003.tif'))

        self.model.configurations[0].img_model._directory_watcher._file_system_watcher.directoryChanged.emit(
            unittest_data_path)

        self.assertEqual('image_003.tif', str(self.widget.img_filename_txt.text()))

    def test_configuration_selected_changes_mask_mode(self):
        self.model.add_configuration()
        click_button(self.widget.img_mask_btn)
        self.assertTrue(self.model.use_mask)

        self.model.select_configuration(0)
        self.assertFalse(self.model.use_mask)
        self.assertFalse(self.widget.img_mask_btn.isChecked())

    def test_configuration_selected_changes_mask_transparency(self):
        click_button(self.widget.img_mask_btn)
        self.model.add_configuration()
        click_button(self.widget.img_mask_btn)
        click_checkbox(self.widget.mask_transparent_cb)
        self.assertTrue(self.model.transparent_mask)

        self.model.select_configuration(0)
        self.assertFalse(self.model.transparent_mask)
        self.assertFalse(self.widget.mask_transparent_cb.isChecked())

    def test_configuration_selected_changed_autoprocessing_of_images(self):
        click_checkbox(self.widget.autoprocess_cb)
        self.model.add_configuration()

        self.assertFalse(self.model.img_model.autoprocess)
        self.assertFalse(self.widget.autoprocess_cb.isChecked())

        self.model.select_configuration(0)
        self.assertTrue(self.model.img_model.autoprocess)
        self.assertTrue(self.widget.autoprocess_cb.isChecked())

    def test_configuration_selected_changes_calibration_name(self):
        self.model.calibration_model.calibration_name = "calib1"
        self.model.add_configuration()
        self.model.calibration_model.calibration_name = "calib2"

        self.model.select_configuration(0)
        self.assertEqual(str(self.widget.calibration_lbl.text()), "calib1")

        self.model.select_configuration(1)
        self.assertEqual(str(self.widget.calibration_lbl.text()), "calib2")

    def test_adding_images(self):
        self.controller.load_file(os.path.join(unittest_data_path, 'image_001.tif'))
        data1 = np.copy(self.widget.img_widget.img_data)
        click_checkbox(self.widget.img_batch_mode_add_rb)
        self.controller.load_file([os.path.join(unittest_data_path, 'image_001.tif'),
                                   os.path.join(unittest_data_path, 'image_001.tif')])
        self.assertTrue(np.array_equal(2*data1, self.widget.img_widget.img_data))



