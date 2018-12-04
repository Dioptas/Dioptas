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

from ..utility import QtTest
import os
import gc

from qtpy import QtWidgets
from mock import MagicMock

from ..utility import enter_value_into_text_field, click_button, click_checkbox, unittest_data_path

from ...controller.integration.CorrectionController import CorrectionController
from ...model.DioptasModel import DioptasModel
from ...widgets.integration import IntegrationWidget


class OptionsControllerTest(QtTest):
    def setUp(self):
        self.widget = IntegrationWidget()
        self.correction_widget = self.widget.integration_control_widget.corrections_control_widget
        self.model = DioptasModel()

        self.correction_controller = CorrectionController(self.widget, self.model)

    def tearDown(self):
        del self.correction_controller
        del self.widget
        del self.model
        gc.collect()

    def test_load_correction(self):
        img_filename = os.path.join(unittest_data_path, 'TransferCorrection', 'response.tif')
        self.model.img_model.load(img_filename)

        original_filename = os.path.join(unittest_data_path, 'TransferCorrection', 'original.tif')
        response_filename = img_filename

        click_checkbox(self.correction_widget.transfer_gb)

        QtWidgets.QFileDialog.getOpenFileName = MagicMock(return_value=original_filename)
        click_button(self.widget.transfer_load_original_btn)

        self.assertEqual(self.correction_widget.transfer_original_filename_lbl.text(),
                         os.path.basename(original_filename))

        self.assertFalse(self.model.img_model.has_corrections())

        QtWidgets.QFileDialog.getOpenFileName = MagicMock(return_value=response_filename)
        click_button(self.widget.transfer_load_response_btn)

        self.assertEqual(self.correction_widget.transfer_response_filename_lbl.text(),
                         os.path.basename(response_filename))

        self.assertTrue(self.model.img_model.has_corrections())
