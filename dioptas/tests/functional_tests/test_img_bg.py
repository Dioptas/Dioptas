# -*- coding: utf8 -*-

import os
import gc
import shutil
import numpy as np
from mock import MagicMock

from ..utility import QtTest, click_button, click_checkbox

from qtpy import QtCore, QtWidgets
from qtpy.QtTest import QTest

from ...controller.MainController import MainController

unittest_data_path = os.path.join(os.path.dirname(__file__), '../data')


class ImageBackgroundTests(QtTest):
    def setUp(self):
        self.working_dir = {'image': ''}

        self.controller = MainController(use_settings=False)

    def tearDown(self):
        del self.controller
        gc.collect()

    def test_remove_img_background_in_img_view(self):
        QtWidgets.QFileDialog.getOpenFileNames = MagicMock(
            return_value=[os.path.join(unittest_data_path, 'image_001.tif')])
        QtWidgets.QFileDialog.getOpenFileName = MagicMock(
            return_value=os.path.join(unittest_data_path, 'image_001.tif'))
        click_button(self.controller.widget.integration_widget.load_img_btn)
        data_before_bg = np.copy(self.controller.widget.integration_widget.img_widget.data_img_item.image)

        click_button(self.controller.widget.integration_widget.integration_image_widget.show_background_subtracted_img_btn)
        click_button(self.controller.widget.integration_widget.bkg_image_load_btn)

        data_after_bg = np.copy(self.controller.widget.integration_widget.img_widget.data_img_item.image)
        self.assertFalse(np.array_equal(data_after_bg, data_before_bg))

    def test_remove_img_background_in_img_view_after_loading_bg(self):
        QtWidgets.QFileDialog.getOpenFileNames = MagicMock(
            return_value=[os.path.join(unittest_data_path, 'image_001.tif')])
        QtWidgets.QFileDialog.getOpenFileName = MagicMock(
            return_value=os.path.join(unittest_data_path, 'image_001.tif'))
        click_button(self.controller.widget.integration_widget.load_img_btn)
        data_before_bg = np.copy(self.controller.widget.integration_widget.img_widget.data_img_item.image)

        click_button(self.controller.widget.integration_widget.bkg_image_load_btn)

        click_button(self.controller.widget.integration_widget.integration_image_widget.show_background_subtracted_img_btn)

        data_after_bg = np.copy(self.controller.widget.integration_widget.img_widget.data_img_item.image)
        self.assertFalse(np.array_equal(data_after_bg, data_before_bg))
