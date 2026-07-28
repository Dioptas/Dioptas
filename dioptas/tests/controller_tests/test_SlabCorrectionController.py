# SPDX-License-Identifier: MIT

from ..utility import QtTest
import os
import gc
import numpy as np

from qtpy import QtWidgets
from mock import MagicMock

from ..utility import click_button, unittest_data_path

from ...controller.integration.CorrectionController import CorrectionController
from ...model.DioptasModel import DioptasModel
from ...widgets.integration import IntegrationWidget


class SlabCorrectionControllerTest(QtTest):
    def setUp(self):
        self.widget = IntegrationWidget()
        self.correction_widget = (
            self.widget.integration_control_widget.corrections_control_widget
        )
        self.model = DioptasModel()
        self.correction_controller = CorrectionController(self.widget, self.model)

        self.test_image = os.path.join(unittest_data_path, "CeO2_Pilatus1M.tif")
        self.test_calibration = os.path.join(
            unittest_data_path, "CeO2_Pilatus1M.poni"
        )

    def tearDown(self):
        del self.correction_controller
        del self.widget
        del self.model
        gc.collect()

    def _load_and_calibrate(self):
        self.model.img_model.load(self.test_image)
        self.model.calibration_model.load(self.test_calibration)

    def _enable_slab_correction(self, formula="CeO2", density=7.22):
        self.correction_widget.slab_formula_txt.setText(formula)
        self.correction_widget.slab_param_form.set_value("density", density)
        self.correction_widget.slab_gb.setChecked(True)
        # Trigger the signal manually since setChecked doesn't always emit clicked
        self.correction_controller.slab_groupbox_changed()

    def test_enable_slab_correction(self):
        self._load_and_calibrate()
        self._enable_slab_correction()
        self.assertTrue(self.model.img_model.has_corrections())
        self.assertIsNotNone(
            self.model.img_model.img_corrections.get_correction("slab")
        )

    def test_disable_slab_correction(self):
        self._load_and_calibrate()
        self._enable_slab_correction()
        self.assertTrue(self.model.img_model.has_corrections())

        self.correction_widget.slab_gb.setChecked(False)
        self.correction_controller.slab_groupbox_changed()
        self.assertFalse(self.model.img_model.has_corrections())

    def test_slab_without_calibration_shows_error(self):
        QtWidgets.QMessageBox.critical = MagicMock()
        self.model.img_model.load(self.test_image)

        self.correction_widget.slab_gb.setChecked(True)
        self.correction_controller.slab_groupbox_changed()

        self.assertFalse(self.correction_widget.slab_gb.isChecked())
        QtWidgets.QMessageBox.critical.assert_called_once()

    def test_invalid_formula_shows_error(self):
        QtWidgets.QMessageBox.critical = MagicMock()
        self._load_and_calibrate()

        self._enable_slab_correction(formula="InvalidXYZ123")

        self.assertFalse(self.correction_widget.slab_gb.isChecked())
        QtWidgets.QMessageBox.critical.assert_called_once()

    def test_mu_label_updated_on_enable(self):
        self._load_and_calibrate()
        self._enable_slab_correction()
        mu_text = self.correction_widget.slab_mu_lbl.text()
        self.assertTrue(mu_text.startswith("μ:"))
        self.assertIn("1/mm", mu_text)

    def test_mu_label_reset_on_disable(self):
        self._load_and_calibrate()
        self._enable_slab_correction()

        self.correction_widget.slab_gb.setChecked(False)
        self.correction_controller.slab_groupbox_changed()
        self.assertEqual(self.correction_widget.slab_mu_lbl.text(), "μ:")

    def test_slab_correction_affects_image_data(self):
        self._load_and_calibrate()
        before_data = self.model.img_data.copy()

        self._enable_slab_correction()
        after_data = self.model.img_data.copy()

        self.assertFalse(np.array_equal(before_data, after_data))

    def test_parameter_change_updates_correction(self):
        self._load_and_calibrate()
        self._enable_slab_correction()

        correction_before = (
            self.model.img_model.img_corrections.get_correction("slab").get_data().copy()
        )

        # Change thickness
        self.correction_widget.slab_param_form.set_value("thickness", 0.5)
        self.correction_controller.slab_groupbox_changed()

        correction_after = (
            self.model.img_model.img_corrections.get_correction("slab").get_data()
        )
        self.assertFalse(np.array_equal(correction_before, correction_after))

    def test_plot_btn_shows_correction(self):
        self._load_and_calibrate()
        self._enable_slab_correction()

        click_button(self.correction_widget.slab_plot_btn)
        self.assertEqual(self.correction_widget.slab_plot_btn.text(), "Back")

        click_button(self.correction_widget.slab_plot_btn)
        self.assertEqual(self.correction_widget.slab_plot_btn.text(), "Plot")

    def test_corrections_removed_resets_slab(self):
        QtWidgets.QMessageBox.critical = MagicMock()
        self._load_and_calibrate()
        self._enable_slab_correction()
        self.assertTrue(self.correction_widget.slab_gb.isChecked())

        self.correction_controller.corrections_removed()

        self.assertFalse(self.correction_widget.slab_gb.isChecked())
        self.assertEqual(self.correction_widget.slab_mu_lbl.text(), "μ:")

    def test_update_gui_restores_slab_state(self):
        self._load_and_calibrate()
        self._enable_slab_correction()

        # Simulate config switch by calling update_gui
        self.correction_controller.update_gui()

        self.assertTrue(self.correction_widget.slab_gb.isChecked())
        self.assertIn("1/mm", self.correction_widget.slab_mu_lbl.text())

    def test_slab_plot_resets_other_plot_btns(self):
        self._load_and_calibrate()
        self._enable_slab_correction()

        click_button(self.correction_widget.slab_plot_btn)
        self.assertEqual(self.correction_widget.slab_plot_btn.text(), "Back")
        self.assertEqual(self.correction_widget.cbn_seat_plot_btn.text(), "Plot")
        self.assertEqual(self.correction_widget.oiadac_plot_btn.text(), "Plot")

    def test_empty_formula_does_not_enable(self):
        self._load_and_calibrate()
        self._enable_slab_correction(formula="")
        self.assertFalse(self.correction_widget.slab_gb.isChecked())
        self.assertFalse(self.model.img_model.has_corrections())
