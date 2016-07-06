# -*- coding: utf8 -*-

import os
import gc
import shutil
from tests.utility import QtTest

from PyQt4 import QtCore
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
        self.assertFalse(self.controller._directory_watcher.signalsBlocked())

        self.assertTrue(self.widget.autoprocess_cb.isChecked())
        shutil.copy2(os.path.join(unittest_data_path, 'image_001.tif'),
                     os.path.join(unittest_data_path, 'image_003.tif'))

        self.controller._directory_watcher._file_system_watcher.directoryChanged.emit(unittest_data_path)

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
