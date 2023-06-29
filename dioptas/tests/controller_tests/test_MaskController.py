# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
# Principal author: Clemens Prescher (clemens.prescher@gmail.com)
# Copyright (C) 2014-2019 GSECARS, University of Chicago, USA
# Copyright (C) 2015-2018 Institute for Geology and Mineralogy, University of Cologne, Germany
# Copyright (C) 2019-2020 DESY, Hamburg, Germany
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

from ..utility import QtTest, click_button, unittest_data_path, click_checkbox, delete_if_exists
import os
import gc
import numpy as np
from mock import MagicMock

from qtpy import QtWidgets, QtCore, QtGui
from qtpy.QtTest import QTest

from ...model.DioptasModel import DioptasModel
from ...controller.MaskController import MaskController
from ...widgets.MaskWidget import MaskWidget


class MaskControllerTest(QtTest):
    def setUp(self):

        self.model = DioptasModel()
        self.model.working_directories = {'mask': unittest_data_path}

        self.mask_widget = MaskWidget()
        self.mask_controller = MaskController(self.mask_widget, self.model)

    def tearDown(self):
        delete_if_exists(os.path.join(unittest_data_path, 'dummy.mask'))
        del self.model
        self.mask_widget.close()
        del self.mask_widget
        del self.mask_controller
        gc.collect()

    def get_file_size(self, filename):
        stat_info = os.stat(filename)
        return stat_info.st_size

    def test_loading_and_saving_mask_files(self):
        QtWidgets.QFileDialog.getOpenFileName = MagicMock(return_value=(
            os.path.join(unittest_data_path, 'test.mask'),
            MaskController.DEFAULT_MASK_FILTER,
        ))
        click_button(self.mask_widget.load_mask_btn)
        self.model.mask_model.mask_below_threshold(self.model.img_data, 1)

        dialog_results = (
            ('.mask', MaskController.DEFAULT_MASK_FILTER),
            ('.npy', MaskController.FLIPUD_MASK_FILTER),
            ('.edf', MaskController.FLIPUD_MASK_FILTER)

        )
        for extension, selected_filter in dialog_results:
            with self.subTest(extension=extension, selected_filter=selected_filter):
                filename = os.path.join(unittest_data_path, f'dummy{extension}')
                QtWidgets.QFileDialog.getSaveFileName = MagicMock(return_value=(filename, selected_filter))
                click_button(self.mask_widget.save_mask_btn)
                self.assertTrue(os.path.exists(filename))
                delete_if_exists(filename)

    def test_grow_and_shrinking(self):
        self.model.mask_model.mask_ellipse(100, 100, 20, 20)
        previous_mask = np.copy(self.model.mask_model._mask_data)

        QTest.mouseClick(self.mask_widget.grow_btn, QtCore.Qt.LeftButton)
        self.assertFalse(np.array_equal(previous_mask, self.model.mask_model._mask_data))

        QTest.mouseClick(self.mask_widget.shrink_btn, QtCore.Qt.LeftButton)
        self.assertTrue(np.array_equal(previous_mask, self.model.mask_model._mask_data))

    def test_mask_and_unmask(self):
        # test that changing mask mode modifies the model and the color in img_widget
        self.mask_widget.mask_rb.click()
        self.assertEqual(self.model.mask_model.mode, True)
        self.assertEqual(self.mask_widget.img_widget.mask_preview_fill_color, QtGui.QColor(255, 0, 0, 150))
        self.mask_widget.unmask_rb.click()
        self.assertEqual(self.model.mask_model.mode, False)
        self.assertEqual(self.mask_widget.img_widget.mask_preview_fill_color, QtGui.QColor(0, 255, 0, 150))

        # test that masking and unmasking the same area results in the same mask
        previous_mask = np.copy(self.model.mask_model._mask_data)
        self.mask_widget.mask_rb.click()
        self.model.mask_model.mask_ellipse(100, 100, 20, 20)
        self.assertFalse(np.array_equal(previous_mask, self.model.mask_model._mask_data))
        self.mask_widget.unmask_rb.click()
        self.model.mask_model.mask_ellipse(100, 100, 20, 20)
        self.assertTrue(np.array_equal(previous_mask, self.model.mask_model._mask_data))

    def test_select_configuration_updating_mask(self):
        QtWidgets.QFileDialog.getOpenFileName = MagicMock(return_value=os.path.join(unittest_data_path, 'test.mask'))
        click_button(self.mask_widget.load_mask_btn)
        first_mask = self.model.mask_model.get_img()
        self.model.add_configuration()
        self.model.mask_model.mask_below_threshold(self.model.img_data, 1)
        second_mask = self.model.mask_model.get_img()

        self.model.select_configuration(0)
        self.assertEqual(np.sum(self.mask_widget.img_widget.mask_img_item.image-first_mask), 0)
        self.model.select_configuration(1)
        self.assertEqual(np.sum(self.mask_widget.img_widget.mask_img_item.image-second_mask), 0)

    def test_select_configuration_updating_mask_transparency(self):
        QtWidgets.QFileDialog.getOpenFileName = MagicMock(return_value=os.path.join(unittest_data_path, 'test.mask'))
        click_button(self.mask_widget.load_mask_btn)
        self.model.add_configuration()
        self.model.mask_model.mask_below_threshold(self.model.img_data, 1)
        click_checkbox(self.mask_widget.transparent_rb)
        self.assertTrue(self.mask_widget.transparent_rb.isChecked())

        transparent_color = self.mask_widget.img_widget.create_color_map([255, 0, 0, 100])
        filled_color = self.mask_widget.img_widget.create_color_map([255, 0, 0, 255])

        self.assertTrue(self.model.transparent_mask)
        self.model.select_configuration(0)
        self.assertTrue(self.mask_widget.fill_rb.isChecked())
        self.assertTrue(np.array_equal(self.mask_widget.img_widget.mask_img_item.lut, filled_color))
        self.model.select_configuration(1)
        self.assertTrue(self.mask_widget.transparent_rb.isChecked())
        self.assertTrue(np.array_equal(self.mask_widget.img_widget.mask_img_item.lut, transparent_color))

    def test_apply_cosmic_removal(self):
        click_button(self.mask_widget.cosmic_btn)
