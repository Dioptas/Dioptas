# SPDX-License-Identifier: MIT

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


class FlatFieldCorrectionControllerTest(QtTest):
    def setUp(self):
        self.widget = IntegrationWidget()
        self.correction_widget = (
            self.widget.integration_control_widget.corrections_control_widget
        )
        self.model = DioptasModel()
        self.correction_controller = CorrectionController(self.widget, self.model)

        self.flat_field_filename = os.path.join(
            unittest_data_path, "TransferCorrection", "original.tif"
        )

    def tearDown(self):
        del self.correction_controller
        del self.widget
        del self.model
        gc.collect()

    def load_flat_field(self):
        with mock.patch(
            "dioptas.controller.integration.CorrectionController.open_file_dialog",
            return_value=self.flat_field_filename,
        ):
            self.correction_controller.flat_field_load_btn_clicked()

    def test_filename_is_displayed_in_widget(self):
        self.model.img_model.load(self.flat_field_filename)
        self.load_flat_field()
        self.assertEqual(
            self.correction_widget.flat_field_filename_lbl.text(),
            os.path.basename(self.flat_field_filename),
        )

    def test_correction_loaded(self):
        self.model.img_model.load(self.flat_field_filename)
        self.assertFalse(self.model.img_model.has_corrections())
        self.load_flat_field()
        self.assertTrue(self.model.img_model.has_corrections())

    def test_disable_flat_field_correction(self):
        self.model.img_model.load(self.flat_field_filename)
        self.load_flat_field()
        self.assertTrue(self.model.img_model.has_corrections())
        self.correction_widget.flat_field_gb.setChecked(False)
        self.assertFalse(self.model.img_model.has_corrections())

    def test_enable_and_disable(self):
        # Use a different image than the flat field so the correction has a visible effect
        response_filename = os.path.join(
            unittest_data_path, "TransferCorrection", "response.tif"
        )
        self.model.img_model.load(response_filename)
        before_data = self.model.img_data.copy()
        self.load_flat_field()

        self.assertFalse(np.array_equal(before_data, self.model.img_data))

        self.correction_widget.flat_field_gb.setChecked(False)
        self.assertTrue(np.array_equal(before_data, self.model.img_data))

    def test_load_img_with_different_shape(self):
        QtWidgets.QMessageBox.critical = MagicMock()
        self.model.img_model.load(self.flat_field_filename)
        self.load_flat_field()
        self.assertTrue(self.model.img_model.has_corrections())

        self.model.img_model.load(
            os.path.join(unittest_data_path, "image_001.tif")
        )
        self.assertFalse(self.model.img_model.has_corrections())
        self.assertIsNone(self.model.img_model.flat_field_correction.filename)
        self.assertEqual(
            self.widget.flat_field_filename_lbl.text(), "None"
        )

    def test_corrections_removed_resets_flat_field(self):
        QtWidgets.QMessageBox.critical = MagicMock()
        self.model.img_model.load(self.flat_field_filename)
        self.load_flat_field()
        self.assertTrue(self.model.img_model.has_corrections())
        self.assertTrue(self.correction_widget.flat_field_gb.isChecked())

        # Trigger shape mismatch
        self.model.img_model.load(
            os.path.join(unittest_data_path, "image_001.tif")
        )
        self.assertFalse(self.correction_widget.flat_field_gb.isChecked())
        self.assertEqual(self.correction_widget.flat_field_filename_lbl.text(), "None")
