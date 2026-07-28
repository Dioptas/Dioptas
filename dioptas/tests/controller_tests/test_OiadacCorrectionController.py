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


class OiadacCorrectionControllerTest(QtTest):
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

    def _enable_oiadac_correction(self):
        self.correction_widget.oiadac_gb.setChecked(True)
        self.correction_controller.oiadac_groupbox_changed()

    def test_enable_oiadac_correction(self):
        self._load_and_calibrate()
        self._enable_oiadac_correction()
        self.assertTrue(self.model.img_model.has_corrections())
        self.assertIsNotNone(
            self.model.img_model.img_corrections.get_correction("oiadac")
        )

    def test_disable_oiadac_correction(self):
        self._load_and_calibrate()
        self._enable_oiadac_correction()
        self.assertTrue(self.model.img_model.has_corrections())

        self.correction_widget.oiadac_gb.setChecked(False)
        self.correction_controller.oiadac_groupbox_changed()
        self.assertFalse(self.model.img_model.has_corrections())

    def test_oiadac_without_calibration_shows_error(self):
        QtWidgets.QMessageBox.critical = MagicMock()
        self.model.img_model.load(self.test_image)

        self.correction_widget.oiadac_gb.setChecked(True)
        self.correction_controller.oiadac_groupbox_changed()

        self.assertFalse(self.correction_widget.oiadac_gb.isChecked())
        QtWidgets.QMessageBox.critical.assert_called_once()

    def test_oiadac_correction_affects_image_data(self):
        self._load_and_calibrate()
        before_data = self.model.img_data.copy()

        self._enable_oiadac_correction()
        after_data = self.model.img_data.copy()

        self.assertFalse(np.array_equal(before_data, after_data))

    def test_parameter_change_updates_correction(self):
        self._load_and_calibrate()
        self._enable_oiadac_correction()

        correction_before = (
            self.model.img_model.img_corrections.get_correction("oiadac").get_data().copy()
        )

        # Change detector thickness
        self.correction_widget.oiadac_param_form.set_value("detector_thickness", 80)
        self.correction_controller.oiadac_groupbox_changed()

        correction_after = (
            self.model.img_model.img_corrections.get_correction("oiadac").get_data()
        )
        self.assertFalse(np.array_equal(correction_before, correction_after))

    def test_plot_btn_shows_correction(self):
        self._load_and_calibrate()
        self._enable_oiadac_correction()

        click_button(self.correction_widget.oiadac_plot_btn)
        self.assertEqual(self.correction_widget.oiadac_plot_btn.text(), "Back")

        click_button(self.correction_widget.oiadac_plot_btn)
        self.assertEqual(self.correction_widget.oiadac_plot_btn.text(), "Plot")

    def test_corrections_removed_resets_oiadac(self):
        QtWidgets.QMessageBox.critical = MagicMock()
        self._load_and_calibrate()
        self._enable_oiadac_correction()
        self.assertTrue(self.correction_widget.oiadac_gb.isChecked())

        self.correction_controller.corrections_removed()

        self.assertFalse(self.correction_widget.oiadac_gb.isChecked())

    def test_update_gui_restores_oiadac_state(self):
        self._load_and_calibrate()
        self._enable_oiadac_correction()

        self.correction_controller.update_gui()

        self.assertTrue(self.correction_widget.oiadac_gb.isChecked())

    def test_oiadac_plot_resets_other_plot_btns(self):
        self._load_and_calibrate()
        self._enable_oiadac_correction()

        click_button(self.correction_widget.oiadac_plot_btn)
        self.assertEqual(self.correction_widget.oiadac_plot_btn.text(), "Back")
        self.assertEqual(self.correction_widget.cbn_seat_plot_btn.text(), "Plot")
        self.assertEqual(self.correction_widget.slab_plot_btn.text(), "Plot")
        self.assertEqual(self.correction_widget.cylinder_plot_btn.text(), "Plot")
        self.assertEqual(self.correction_widget.sphere_plot_btn.text(), "Plot")
        self.assertEqual(self.correction_widget.plate_plot_btn.text(), "Plot")
