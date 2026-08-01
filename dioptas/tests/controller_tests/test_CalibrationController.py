# SPDX-License-Identifier: MIT

import unittest
from mock import MagicMock, patch
import os
import gc
from pyFAI import detectors

import numpy as np

from qtpy import QtWidgets, QtCore
from qtpy.QtTest import QTest

from ..utility import (
    QtTest,
    unittest_data_path,
    click_button,
    click_checkbox,
    delete_if_exists,
)
from ...model.DioptasModel import DioptasModel
from ...controller.CalibrationController import (
    CalibrationController,
    get_available_detectors,
)
from ...widgets.CalibrationWidget import CalibrationWidget

class TestCalibrationController(QtTest):
    def setUp(self):
        # Mocking the functions which will block the unittest for some reason...
        # Use patch to ensure proper cleanup
        self.processEvents_patcher = patch.object(QtWidgets.QApplication, 'processEvents', MagicMock())
        self.setValue_patcher = patch.object(QtWidgets.QProgressDialog, 'setValue', MagicMock())
        self.processEvents_patcher.start()
        self.setValue_patcher.start()

        self.model = DioptasModel()

        self.widget = CalibrationWidget()
        self.controller = CalibrationController(
            widget=self.widget, dioptas_model=self.model
        )

    def tearDown(self):
        # Stop the patchers to restore original behavior
        self.processEvents_patcher.stop()
        self.setValue_patcher.stop()

        delete_if_exists(os.path.join(unittest_data_path, "detector_with_spline.h5"))

        # Clean up widgets
        self.widget.close()
        self.widget.deleteLater()
        del self.widget
        del self.controller
        del self.model
        gc.collect()

    def mock_integrate_functions(self):
        self.model.calibration_model.integrate_1d = MagicMock(
            return_value=([np.linspace(0, 100), np.linspace(0, 100)])
        )
        self.model.calibration_model.integrate_2d = MagicMock()

    def test_load_detector(self):
        detector_names, detector_classes = get_available_detectors()
        det_ind = 9
        self.widget.detectors_cb.setCurrentIndex(
            det_ind + 3
        )  # +3 since there is also the custom element at 0
        # and 2 separators
        self.assertIsInstance(
            self.model.calibration_model.detector, detector_classes[det_ind]
        )

        detector_gb = (
            self.widget.calibration_control_widget.calibration_parameters_widget.detector_gb
        )
        self.assertAlmostEqual(
            float(detector_gb.pixel_width_txt.text()) * 1e-6,
            self.model.calibration_model.orig_pixel1,
        )
        self.assertAlmostEqual(
            float(detector_gb.pixel_height_txt.text()) * 1e-6,
            self.model.calibration_model.orig_pixel2,
        )

        self.assertFalse(detector_gb.pixel_width_txt.isEnabled())
        self.assertFalse(detector_gb.pixel_width_txt.isEnabled())

        self.widget.detectors_cb.setCurrentIndex(0)
        self.assertNotIsInstance(
            self.model.calibration_model.detector, detector_classes[det_ind]
        )
        self.assertAlmostEqual(
            float(detector_gb.pixel_width_txt.text()) * 1e-6,
            self.model.calibration_model.orig_pixel1,
        )
        self.assertAlmostEqual(
            float(detector_gb.pixel_height_txt.text()) * 1e-6,
            self.model.calibration_model.orig_pixel2,
        )
        self.assertTrue(detector_gb.pixel_width_txt.isEnabled())
        self.assertTrue(detector_gb.pixel_width_txt.isEnabled())

    def test_load_detector_transform_and_reset(self):
        QtWidgets.QFileDialog.getOpenFileName = MagicMock(
            return_value=os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
        )
        QTest.mouseClick(self.widget.load_calibration_btn, QtCore.Qt.LeftButton)

        detector_gb = (
            self.widget.calibration_control_widget.calibration_parameters_widget.detector_gb
        )
        detector_gb.detector_cb.setCurrentIndex(
            detector_gb.detector_cb.findText("Pilatus CdTe 1M")
        )

        QtWidgets.QFileDialog.getOpenFileName = MagicMock(
            return_value=os.path.join(unittest_data_path, "CeO2_Pilatus1M.tif")
        )
        QTest.mouseClick(self.widget.load_img_btn, QtCore.Qt.LeftButton)

        QTest.mouseClick(self.widget.rotate_m90_btn, QtCore.Qt.LeftButton)
        QTest.mouseClick(self.widget.rotate_m90_btn, QtCore.Qt.LeftButton)

        detector_gb.detector_cb.setCurrentIndex(
            detector_gb.detector_cb.findText("Custom")
        )

        QTest.mouseClick(self.widget.rotate_m90_btn, QtCore.Qt.LeftButton)

    def test_load_detector_from_file(self):
        QtWidgets.QFileDialog.getOpenFileName = MagicMock(
            return_value=os.path.join(unittest_data_path, "detector.h5")
        )
        click_button(self.widget.detector_load_btn)

        self.assertAlmostEqual(self.model.calibration_model.orig_pixel1, 100e-6)

        self.assertTrue(self.widget.detector_reset_btn.isEnabled())
        self.widget.show()  # to check visibility
        self.assertFalse(self.widget.detectors_cb.isVisible())
        self.assertTrue(self.widget.detector_name_lbl.isVisible())
        self.assertEqual(self.widget.detector_name_lbl.text(), "detector.h5")
        detector_gb = (
            self.widget.calibration_control_widget.calibration_parameters_widget.detector_gb
        )
        self.assertFalse(detector_gb.pixel_width_txt.isEnabled())
        self.assertFalse(detector_gb.pixel_height_txt.isEnabled())
        self.assertAlmostEqual(self.widget.get_pixel_size()[0], 100e-6)

        click_button(self.widget.detector_reset_btn)
        self.assertTrue(self.widget.detectors_cb.isVisible())
        self.assertFalse(self.widget.detector_name_lbl.isVisible())
        self.assertEqual(self.widget.detectors_cb.currentIndex(), 0)
        self.assertTrue(detector_gb.pixel_width_txt.isEnabled())
        self.assertTrue(detector_gb.pixel_height_txt.isEnabled())

    def test_load_detector_with_distortion(self):
        # create detector and save it
        spline_detector = detectors.Detector()
        spline_detector.splinefile = os.path.join(
            unittest_data_path, "distortion", "f4mnew.spline"
        )
        spline_detector.save(
            os.path.join(unittest_data_path, "detector_with_spline.h5")
        )

        QtWidgets.QFileDialog.getOpenFileName = MagicMock(
            return_value=os.path.join(unittest_data_path, "detector_with_spline.h5")
        )
        click_button(self.widget.detector_load_btn)

        self.assertEqual(self.widget.spline_filename_txt.text(), "from Detector")

    def test_load_detector_and_image_with_different_dimension(self):
        # set the detector
        self.widget.detectors_cb.setCurrentIndex(
            self.widget.detectors_cb.findText("Pilatus CdTe 1M")
        )

        # load calibration
        QtWidgets.QFileDialog.getOpenFileName = MagicMock(
            return_value=os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
        )
        QTest.mouseClick(self.widget.load_calibration_btn, QtCore.Qt.LeftButton)

        # load image file with different dimension than detector, which should automatically
        # reset the detector to a custom detector
        QtWidgets.QMessageBox.critical = MagicMock()
        QtWidgets.QFileDialog.getOpenFileName = MagicMock(
            return_value=os.path.join(unittest_data_path, "LaB6_40keV_MarCCD.tif")
        )
        click_button(self.widget.load_img_btn)

        QtWidgets.QMessageBox.critical.assert_called_once()
        self.assertEqual(self.widget.detectors_cb.currentText(), "Custom")

    def test_automatic_calibration(self):
        self.mock_integrate_functions()
        QtWidgets.QFileDialog.getOpenFileName = MagicMock(
            return_value=os.path.join(unittest_data_path, "LaB6_40keV_MarCCD.tif")
        )
        QTest.mouseClick(self.widget.load_img_btn, QtCore.Qt.LeftButton)
        self.controller.search_peaks(1179.6, 1129.4)
        self.controller.search_peaks(1268.5, 1119.8)
        self.controller.widget.sv_wavelength_txt.setText("0.31")
        self.controller.widget.sv_distance_txt.setText("200")
        self.controller.widget.set_pixel_size(79e-6, 79e-6)
        calibrant_index = self.widget.calibrant_cb.findText("LaB6")
        self.controller.widget.calibrant_cb.setCurrentIndex(calibrant_index)
        #
        QTest.mouseClick(self.widget.calibrate_btn, QtCore.Qt.LeftButton)
        self.app.processEvents()
        self.model.calibration_model.integrate_1d.assert_called_once()
        self.model.calibration_model.integrate_2d.assert_called_once()
        # Progress dialog should be updated during calibration
        self.assertGreater(QtWidgets.QProgressDialog.setValue.call_count, 0)

        calibration_parameter = (
            self.model.calibration_model.get_calibration_parameter()[0]
        )
        self.assertAlmostEqual(calibration_parameter["dist"], 0.1968, places=3)

    def test_searching_peaks_automatic_increase(self):
        self.mock_integrate_functions()
        QtWidgets.QFileDialog.getOpenFileName = MagicMock(
            return_value=os.path.join(unittest_data_path, "LaB6_40keV_MarCCD.tif")
        )
        QTest.mouseClick(self.widget.load_img_btn, QtCore.Qt.LeftButton)
        self.controller.search_peaks(1179.6, 1129.4)
        self.controller.search_peaks(1268.5, 1119.8)
        self.assertEqual(3, self.widget.peak_num_sb.value())

    def test_searching_peaks_manual_index_assignment(self):
        self.mock_integrate_functions()
        QtWidgets.QFileDialog.getOpenFileName = MagicMock(
            return_value=os.path.join(unittest_data_path, "LaB6_40keV_MarCCD.tif")
        )
        QTest.mouseClick(self.widget.load_img_btn, QtCore.Qt.LeftButton)

        click_checkbox(self.widget.automatic_peak_num_inc_cb)
        self.assertFalse(self.widget.automatic_peak_num_inc_cb.isChecked())

        self.controller.search_peaks(1179.6, 1129.4)
        self.controller.search_peaks(1268.5, 1119.8)
        self.assertEqual(1, self.widget.peak_num_sb.value())

    def test_splines(self):
        self.mock_integrate_functions()
        QtWidgets.QFileDialog.getOpenFileName = MagicMock(
            return_value=os.path.join(unittest_data_path, "distortion", "f4mnew.spline")
        )
        click_button(self.widget.load_spline_btn)

        self.assertIsNotNone(self.model.calibration_model.distortion_spline_filename)
        self.assertEqual(self.widget.spline_filename_txt.text(), "f4mnew.spline")
        self.assertTrue(self.widget.spline_reset_btn.isEnabled())
        #
        click_button(self.widget.spline_reset_btn)
        self.assertIsNone(self.model.calibration_model.distortion_spline_filename)
        self.assertEqual(self.widget.spline_filename_txt.text(), "None")

    def test_loading_and_saving_of_calibration_files(self):
        self.mock_integrate_functions()
        QtWidgets.QFileDialog.getOpenFileName = MagicMock(
            return_value=os.path.join(unittest_data_path, "LaB6_40keV_MarCCD.poni")
        )
        QTest.mouseClick(self.widget.load_calibration_btn, QtCore.Qt.LeftButton)
        QtWidgets.QFileDialog.getSaveFileName = MagicMock(
            return_value=os.path.join(unittest_data_path, "calibration.poni")
        )
        QTest.mouseClick(self.widget.save_calibration_btn, QtCore.Qt.LeftButton)
        self.assertTrue(
            os.path.exists(os.path.join(unittest_data_path, "calibration.poni"))
        )
        os.remove(os.path.join(unittest_data_path, "calibration.poni"))

    def test_selecting_configuration_updates_parameter_display(self):
        self.mock_integrate_functions()
        calibration1 = {
            "dist": 0.2,
            "poni1": 0.08,
            "poni2": 0.081,
            "rot1": 0.0043,
            "rot2": 0.002,
            "rot3": 0.001,
            "pixel1": 7.9e-5,
            "pixel2": 7.9e-5,
            "wavelength": 0.3344,
            "polarization_factor": 0.99,
        }
        calibration2 = {
            "dist": 0.3,
            "poni1": 0.04,
            "poni2": 0.021,
            "rot1": 0.0053,
            "rot2": 0.002,
            "rot3": 0.0013,
            "pixel1": 7.4e-5,
            "pixel2": 7.6e-5,
            "wavelength": 0.31,
            "polarization_factor": 0.98,
        }

        self.model.calibration_model.set_pyFAI(calibration1)
        self.model.add_configuration()
        self.model.calibration_model.set_pyFAI(calibration2)

        self.model.select_configuration(0)

        model_calibration = self.model.configurations[
            0
        ].calibration_model.pattern_geometry.getPyFAI()
        del model_calibration["detector"]
        for key in ("splineFile", "splinefile", "max_shape", "orientation"):
            model_calibration.pop(key, None)

        current_displayed_calibration = self.widget.get_pyFAI_parameter()
        del current_displayed_calibration["polarization_factor"]
        self.assertEqual(model_calibration, current_displayed_calibration)

        self.model.select_configuration(1)
        model_calibration = self.model.configurations[
            1
        ].calibration_model.pattern_geometry.getPyFAI()
        del model_calibration["detector"]
        for key in ("splineFile", "splinefile", "max_shape", "orientation"):
            model_calibration.pop(key, None)
        current_displayed_calibration = self.widget.get_pyFAI_parameter()
        del current_displayed_calibration["polarization_factor"]

        self.assertEqual(model_calibration, current_displayed_calibration)

    @unittest.skip("Does not work for unknown reasons")
    def test_calibrant_with_small_set_of_d_spacings(self):
        self.mock_integrate_functions()
        QtWidgets.QFileDialog.getOpenFileName = MagicMock(
            return_value=os.path.join(unittest_data_path, "LaB6_40keV_MarCCD.tif")
        )
        QTest.mouseClick(self.widget.load_img_btn, QtCore.Qt.LeftButton)
        self.controller.search_peaks(1179.6, 1129.4)
        self.controller.search_peaks(1268.5, 1119.8)
        calibrant_index = self.widget.calibrant_cb.findText("CuO")
        self.controller.widget.calibrant_cb.setCurrentIndex(calibrant_index)
        QtWidgets.QMessageBox.critical = MagicMock()
        click_button(self.widget.calibrate_btn)
        QtWidgets.QMessageBox.critical.assert_called_once()

    def test_loading_calibration_without_an_image_before(self):
        QtWidgets.QFileDialog.getOpenFileName = MagicMock(
            return_value=os.path.join(unittest_data_path, "LaB6_40keV_MarCCD.poni")
        )
        QTest.mouseClick(self.widget.load_calibration_btn, QtCore.Qt.LeftButton)
        self.widget.get_pyFAI_parameter()  # would cause error if GUI not updated
        self.widget.get_fit2d_parameter()  # would cause error if GUI not updated

    def test_detector_rotation_does_not_emit_reset_detector_signal(self):
        QtWidgets.QFileDialog.getOpenFileName = MagicMock(
            return_value=os.path.join(unittest_data_path, "LaB6_40keV_MarCCD.tif")
        )
        click_button(self.widget.load_img_btn)
        self.model.calibration_model.detector_reset.emit = MagicMock()

        click_button(self.widget.rotate_m90_btn)
        self.model.calibration_model.detector_reset.emit.assert_not_called()


def test_calibrate_button_is_gated_until_peaks_are_picked(
    calibration_controller, calibration_model
):
    # the guided workflow disables Calibrate instead of popping an error
    # dialog after the fact
    calibration_model.calibrate = MagicMock()
    widget = calibration_controller.widget
    assert not widget.calibrate_btn.isEnabled()
    assert widget.calibrate_btn.toolTip() != ""

    click_button(widget.calibrate_btn)
    assert not calibration_model.calibrate.called

    calibration_model.params.peak_selections = ((0, ((10.0, 20.0),)),)
    assert widget.calibrate_btn.isEnabled()
    assert widget.calibrate_btn.toolTip() == ""


def test_refine_button_is_gated_until_calibrated(calibration_controller):
    widget = calibration_controller.widget
    assert not widget.refine_btn.isEnabled()
    assert widget.refine_btn.toolTip() != ""


def test_guide_updates_indicator_and_counter(
    calibration_controller, calibration_model, dioptas_model
):
    widget = calibration_controller.widget
    assert widget.step_indicator.step_status(0) == "attention"

    dioptas_model.img_model.load(
        os.path.join(unittest_data_path, "LaB6_40keV_MarCCD.tif")
    )
    assert widget.step_indicator.step_status(0) == "done"
    assert widget.step_indicator.step_status(1) == "attention"

    calibration_model.params.peak_selections = (
        (0, ((10.0, 20.0), (30.0, 40.0))),
        (1, ((50.0, 60.0),)),
    )
    assert widget.step_indicator.step_status(1) == "done"
    assert widget.step_indicator.step_status(2) == "attention"
    assert widget.peak_counter_lbl.text() == "3 peaks on 2 rings"

    calibration_model.params.is_calibrated = True
    assert widget.step_indicator.step_status(2) == "done"
    assert widget.refine_btn.isEnabled()


def test_wizard_shows_one_page_at_a_time(calibration_controller, qtbot):
    widget = calibration_controller.widget
    parameters_widget = (
        widget.calibration_control_widget.calibration_parameters_widget
    )
    widget.show()
    qtbot.addWidget(widget)

    assert parameters_widget.current_step() == 0
    assert widget.step_indicator.isVisible()
    assert widget.load_img_btn.isVisible()
    assert widget.rotate_m90_btn.isVisible()
    assert widget.detectors_cb.isVisible()
    # peak picking, calibrant and the actions belong to later pages
    assert not widget.peak_num_sb.isVisible()
    assert not widget.calibrant_cb.isVisible()
    assert not widget.sv_wavelength_txt.isVisible()
    assert not widget.calibrate_btn.isVisible()
    assert not widget.refine_btn.isVisible()


def test_validation_step_gates_results_and_views(
    calibration_controller, calibration_model, dioptas_model, qtbot
):
    widget = calibration_controller.widget
    widget.show()
    qtbot.addWidget(widget)

    # the cake and pattern views are hidden while working through steps 1-3
    assert not widget.tab_widget.tabBar().isVisible()
    assert not widget.tab_widget.isTabVisible(1)
    assert not widget.tab_widget.isTabVisible(2)

    dioptas_model.img_model.load(
        os.path.join(unittest_data_path, "LaB6_40keV_MarCCD.tif")
    )
    calibration_model.params.peak_selections = ((0, ((10.0, 20.0),)),)
    calibration_controller.go_to_wizard_step(2)
    assert widget.calibrate_btn.isVisible()
    assert widget.calibrate_btn.isEnabled()
    assert not widget.refine_btn.isVisible()
    assert not widget.save_calibration_btn.isVisible()

    # validation is unreachable without a calibration
    calibration_controller.go_to_wizard_step(3)
    assert widget.step_stack.currentIndex() == 2

    calibration_model.params.is_calibrated = True
    calibration_controller.go_to_wizard_step(3)
    assert widget.step_stack.currentIndex() == 3
    assert widget.tab_widget.tabBar().isVisible()
    assert widget.tab_widget.isTabVisible(1)
    assert widget.tab_widget.isTabVisible(2)
    assert widget.parameters_tab_widget.isVisible()
    assert widget.refine_btn.isVisible()
    assert widget.save_calibration_btn.isVisible()

    # going back hides the validation-only views again
    calibration_controller.go_to_wizard_step(1)
    assert not widget.tab_widget.tabBar().isVisible()
    assert not widget.tab_widget.isTabVisible(1)


def test_wizard_navigation_is_gated_by_prerequisites(
    calibration_controller, dioptas_model, calibration_model
):
    widget = calibration_controller.widget
    parameters_widget = (
        widget.calibration_control_widget.calibration_parameters_widget
    )

    # nothing loaded: stuck on page 1
    assert not widget.wizard_next_btn.isEnabled()
    assert not widget.wizard_back_btn.isEnabled()
    assert widget.wizard_next_btn.toolTip() != ""
    calibration_controller.wizard_next()
    assert parameters_widget.current_step() == 0

    dioptas_model.img_model.load(
        os.path.join(unittest_data_path, "LaB6_40keV_MarCCD.tif")
    )
    assert widget.wizard_next_btn.isEnabled()
    click_button(widget.wizard_next_btn)
    assert parameters_widget.current_step() == 1

    # no peaks yet: page 3 unreachable
    assert not widget.wizard_next_btn.isEnabled()
    calibration_controller.wizard_next()
    assert parameters_widget.current_step() == 1

    calibration_model.params.peak_selections = ((0, ((10.0, 20.0),)),)
    assert widget.wizard_next_btn.isEnabled()
    click_button(widget.wizard_next_btn)
    assert parameters_widget.current_step() == 2

    # not calibrated yet: the validation page stays unreachable
    assert not widget.wizard_next_btn.isEnabled()
    calibration_controller.wizard_next()
    assert parameters_widget.current_step() == 2

    calibration_model.params.is_calibrated = True
    assert widget.wizard_next_btn.isEnabled()
    click_button(widget.wizard_next_btn)
    assert parameters_widget.current_step() == 3
    # last page has no next
    assert not widget.wizard_next_btn.isEnabled()

    click_button(widget.wizard_back_btn)
    assert parameters_widget.current_step() == 2


def test_advanced_options_are_collapsed_by_default(calibration_controller):
    widget = calibration_controller.widget
    parameters_widget = (
        widget.calibration_control_widget.calibration_parameters_widget
    )
    assert not parameters_widget.peak_selection_gb.advanced_expander.is_expanded()
    assert not parameters_widget.refinement_options_gb.advanced_expander.is_expanded()
    # the hidden expert controls keep working defaults
    assert widget.automatic_peak_search_rb.isChecked()
    assert widget.options_num_rings_sb.value() == 15

    parameters_widget.peak_selection_gb.advanced_expander.set_expanded(True)
    assert parameters_widget.peak_selection_gb.advanced_expander.is_expanded()


def test_setup_fields_are_flagged_until_edited(calibration_controller):
    widget = calibration_controller.widget
    for field in (
        widget.sv_distance_txt,
        widget.sv_wavelength_txt,
        widget.sv_energy_txt,
        widget.calibrant_cb,
    ):
        assert field.property("unconfirmed")
        assert field.toolTip() != ""

    widget.sv_distance_txt.setText("300")
    widget.sv_distance_txt.textEdited.emit("300")
    assert not widget.sv_distance_txt.property("unconfirmed")
    assert widget.sv_distance_txt.toolTip() == ""
    # the others stay flagged
    assert widget.sv_wavelength_txt.property("unconfirmed")


def test_wavelength_and_energy_stay_in_sync(calibration_controller):
    widget = calibration_controller.widget
    # default 0.3344 A shows its energy equivalent
    assert abs(float(widget.sv_energy_txt.text()) - 37.0766) < 1e-3

    widget.sv_wavelength_txt.setText("0.4")
    widget.sv_wavelength_txt.textEdited.emit("0.4")
    assert abs(float(widget.sv_energy_txt.text()) - 30.9960) < 1e-3
    assert not widget.sv_wavelength_txt.property("unconfirmed")
    assert not widget.sv_energy_txt.property("unconfirmed")

    widget.sv_energy_txt.setText("31")
    widget.sv_energy_txt.textEdited.emit("31")
    assert abs(float(widget.sv_wavelength_txt.text()) - 0.399949) < 1e-5


def test_calibrated_state_confirms_all_setup_fields(
    calibration_controller, calibration_model
):
    widget = calibration_controller.widget
    assert widget.sv_wavelength_txt.property("unconfirmed")

    calibration_model.params.is_calibrated = True
    for field in (
        widget.sv_distance_txt,
        widget.sv_wavelength_txt,
        widget.sv_energy_txt,
        widget.calibrant_cb,
    ):
        assert not field.property("unconfirmed")


def test_loading_detector_confirms_pixel_size(calibration_controller):
    widget = calibration_controller.widget
    detector_gb = (
        widget.calibration_control_widget.calibration_parameters_widget.detector_gb
    )
    assert detector_gb.pixel_width_txt.property("unconfirmed")

    widget.detectors_cb.setCurrentIndex(
        widget.detectors_cb.findText("Pilatus CdTe 1M")
    )
    assert not detector_gb.pixel_width_txt.property("unconfirmed")
    assert not detector_gb.pixel_height_txt.property("unconfirmed")
