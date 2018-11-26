# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2017  Clemens Prescher (clemens.prescher@gmail.com)
# Institute for Geology and Mineralogy, University of Cologne
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

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
