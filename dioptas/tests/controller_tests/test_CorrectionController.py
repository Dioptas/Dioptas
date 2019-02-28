# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
# Principal author: Clemens Prescher (clemens.prescher@gmail.com)
# Copyright (C) 2014-2019 GSECARS, University of Chicago, USA
# Copyright (C) 2015-2018 Institute for Geology and Mineralogy, University of Cologne, Germany
# Copyright (C) 2019 DESY, Hamburg, Germany
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

from ..utility import QtTest
import os
import gc
import numpy as np

from qtpy import QtWidgets
from mock import MagicMock
import mock

from ..utility import click_button, unittest_data_path

from ...controller.integration.CorrectionController import CorrectionController
from ...model.DioptasModel import DioptasModel
from ...widgets.integration import IntegrationWidget


class CorrectionControllerTest(QtTest):
    def setUp(self):
        self.widget = IntegrationWidget()
        self.correction_widget = self.widget.integration_control_widget.corrections_control_widget
        self.model = DioptasModel()

        self.correction_controller = CorrectionController(self.widget, self.model)

        self.original_filename = os.path.join(unittest_data_path, 'TransferCorrection', 'original.tif')
        self.response_filename = os.path.join(unittest_data_path, 'TransferCorrection', 'response.tif')

    def tearDown(self):
        del self.correction_controller
        del self.widget
        del self.model
        gc.collect()

    def load_original_img(self):
        QtWidgets.QFileDialog.getOpenFileName = MagicMock(return_value=self.original_filename)
        click_button(self.widget.transfer_load_original_btn)

    def load_response_img(self):
        QtWidgets.QFileDialog.getOpenFileName = MagicMock(return_value=self.response_filename)
        click_button(self.widget.transfer_load_response_btn)

    def test_filenames_are_displayed_in_widget(self):
        self.correction_widget.transfer_gb.setChecked(True)

        self.model.img_model.load(self.response_filename)

        self.load_original_img()
        self.assertEqual(self.correction_widget.transfer_original_filename_lbl.text(),
                         os.path.basename(self.original_filename))
        self.load_response_img()
        self.assertEqual(self.correction_widget.transfer_response_filename_lbl.text(),
                         os.path.basename(self.response_filename))

    def test_correction_loaded(self):
        self.correction_widget.transfer_gb.setChecked(True)

        self.model.img_model.load(self.response_filename)

        self.load_original_img()
        self.assertFalse(self.model.img_model.has_corrections())
        self.load_response_img()
        self.assertTrue(self.model.img_model.has_corrections())

    def test_disable_transfer_correction(self):
        self.correction_widget.transfer_gb.setChecked(True)
        self.model.img_model.load(self.response_filename)
        self.load_original_img()
        self.load_response_img()
        self.assertTrue(self.model.img_model.has_corrections())
        self.correction_widget.transfer_gb.setChecked(False)
        self.assertFalse(self.model.img_model.has_corrections())

    def test_load_img_with_different_shape(self):
        QtWidgets.QMessageBox.critical = MagicMock()
        self.correction_widget.transfer_gb.setChecked(True)
        self.model.img_model.load(self.response_filename)
        self.load_original_img()
        self.load_response_img()
        self.assertTrue(self.model.img_model.has_corrections())

        self.model.img_model.load(os.path.join(unittest_data_path, 'image_001.tif'))
        self.assertFalse(self.model.img_model.has_corrections())

        self.assertIsNone(self.model.img_model.transfer_correction.response_filename)
        self.assertFalse(self.widget.transfer_load_original_btn.isVisible())

        self.assertEqual(self.widget.transfer_original_filename_lbl.text(), 'None')
        self.assertEqual(self.widget.transfer_response_filename_lbl.text(), 'None')

    def test_load_img_with_different_shape_and_calibration(self):
        QtWidgets.QMessageBox.critical = MagicMock()
        self.correction_widget.transfer_gb.setChecked(True)
        self.model.img_model.load(self.response_filename)
        self.model.calibration_model.load(os.path.join(unittest_data_path, 'CeO2_Pilatus1M_2.poni'))

        self.load_original_img()
        self.load_response_img()
        self.assertTrue(self.model.img_model.has_corrections())

        self.model.img_model.load(os.path.join(unittest_data_path, 'image_001.tif'))
        self.assertFalse(self.model.img_model.has_corrections())

        self.assertIsNone(self.model.img_model.transfer_correction.response_filename)
        self.assertFalse(self.widget.transfer_load_original_btn.isVisible())

        self.assertEqual(self.widget.transfer_original_filename_lbl.text(), 'None')
        self.assertEqual(self.widget.transfer_response_filename_lbl.text(), 'None')

    def test_image_enable_and_disable(self):
        self.correction_widget.transfer_gb.setChecked(True)
        self.model.img_model.load(self.response_filename)
        before_data = self.model.img_data.copy()
        self.load_original_img()
        self.load_response_img()

        self.assertNotAlmostEqual(np.sum(before_data - self.model.img_data), 0)

        self.correction_widget.transfer_gb.setChecked(False)
        self.assertAlmostEqual(np.sum(before_data - self.model.img_data), 0)

    def test_image_enable_and_disable_with_calibration(self):
        self.correction_widget.transfer_gb.setChecked(True)
        self.model.img_model.load(self.response_filename)
        self.model.calibration_model.load(os.path.join(unittest_data_path, 'CeO2_Pilatus1M_2.poni'))
        before_data = self.model.img_data.copy()
        self.load_original_img()
        self.load_response_img()

        self.assertNotAlmostEqual(np.sum(before_data - self.model.img_data), 0)

        self.correction_widget.transfer_gb.setChecked(False)
        self.assertAlmostEqual(np.sum(before_data - self.model.img_data), 0)

        self.correction_widget.transfer_gb.setChecked(True)
        self.assertNotAlmostEqual(np.sum(before_data - self.model.img_data), 0)

    def test_show_correction_in_img_widget_and_back(self):
        self.correction_widget.transfer_gb.setChecked(True)
        self.model.img_model.load(self.response_filename)
        self.load_original_img()
        self.load_response_img()

        click_button(self.correction_widget.transfer_plot_btn)
        transfer_data = self.model.img_model.transfer_correction.transfer_data
        img_data = self.widget.img_widget.img_data
        self.assertAlmostEqual(np.sum(transfer_data - img_data), 0)
        self.assertTrue(self.correction_widget.transfer_plot_btn.isChecked())
        self.assertEqual(self.correction_widget.transfer_plot_btn.text(), 'Back')

        click_button(self.correction_widget.transfer_plot_btn)

        self.assertFalse(self.correction_widget.transfer_plot_btn.isChecked())
        self.assertEqual(self.correction_widget.transfer_plot_btn.text(), 'Plot')

    def test_transfer_correction_is_applied_correctly(self):
        self.model.calibration_model.load(os.path.join(unittest_data_path, 'TransferCorrection', 'transfer.poni'))
        self.model.img_model.load(self.original_filename)
        y_original = self.model.pattern.y
        self.model.img_model.load(self.response_filename)

        self.correction_widget.transfer_gb.setChecked(True)
        self.load_original_img()
        self.load_response_img()
        y_response_with_transfer = self.model.pattern.y

        self.assertAlmostEqual(np.sum(y_original-y_response_with_transfer), 0)

    def test_changing_transfer_function_several_times(self):
        self.model.img_model.load(self.original_filename)
        self.correction_widget.transfer_gb.setChecked(True)
        self.load_original_img()
        self.load_response_img()

        img_1 = self.model.img_data.copy()

        QtWidgets.QFileDialog.getOpenFileName = MagicMock(return_value=self.original_filename)
        click_button(self.widget.transfer_load_response_btn)

        img_2 = self.model.img_data.copy()

        self.assertFalse(np.array_equal(img_1, img_2))





