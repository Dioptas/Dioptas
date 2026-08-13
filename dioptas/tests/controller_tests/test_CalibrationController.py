# SPDX-License-Identifier: MIT

import unittest
from mock import MagicMock, patch
import os
import gc

import pytest
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

    def test_parameters_tab_choice_is_stored_in_view_params(self):
        self.assertEqual(self.model.view.calibration_param_display, "pyFAI")

        tab_widget = self.widget.parameters_tab_widget
        fit2d_index = next(
            i for i in range(tab_widget.count()) if tab_widget.tabText(i) == "Fit2d"
        )
        tab_widget.setCurrentIndex(fit2d_index)
        self.assertEqual(self.model.view.calibration_param_display, "Fit2d")

    def test_parameters_tab_follows_view_params(self):
        # a loaded project or restored session writes the view params; the
        # tab has to follow without the user touching it
        self.model.view.calibration_param_display = "Fit2d"

        tab_widget = self.widget.parameters_tab_widget
        self.assertEqual(tab_widget.tabText(tab_widget.currentIndex()), "Fit2d")

        self.model.view.calibration_param_display = "pyFAI"
        self.assertEqual(tab_widget.tabText(tab_widget.currentIndex()), "pyFAI")

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
        self.controller.go_to_wizard_step(1)
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
        self.controller.go_to_wizard_step(1)
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

        self.controller.go_to_wizard_step(1)
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
        self.controller.go_to_wizard_step(1)
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
    display_widget = widget.calibration_display_widget
    assert widget.img_widget.img_view_box.isVisible()
    assert not display_widget.cake_layout_widget.isVisible()
    assert not display_widget.pattern_layout_widget.isVisible()

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
    assert display_widget.cake_layout_widget.isVisible()
    assert display_widget.pattern_layout_widget.isVisible()
    assert widget.parameters_tab_widget.isVisible()
    assert widget.refine_btn.isVisible()
    assert widget.save_calibration_btn.isVisible()

    # going back hides the validation-only views again
    calibration_controller.go_to_wizard_step(1)
    assert not display_widget.cake_layout_widget.isVisible()
    assert not display_widget.pattern_layout_widget.isVisible()


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


def test_peak_table_lists_and_edits_picks(calibration_controller, calibration_model):
    widget = calibration_controller.widget
    calibration_model.params.peak_selections = (
        (0, ((10.0, 20.0), (30.0, 40.0))),
        (1, ((50.0, 60.0),)),
    )
    table = widget.peak_table
    assert table.rowCount() == 2
    assert table.cellWidget(0, 0).value() == 1
    assert table.item(0, 1).text() == "2"
    assert table.cellWidget(1, 0).value() == 2

    # changing the ring spinbox reassigns the pick to that ring
    table.cellWidget(1, 0).setValue(5)
    assert calibration_model.points_index == [0, 4]
    assert table.cellWidget(1, 0).value() == 5


def test_peak_table_delete_selected(calibration_controller, calibration_model):
    widget = calibration_controller.widget
    calibration_model.params.peak_selections = (
        (0, ((10.0, 20.0),)),
        (1, ((30.0, 40.0),)),
        (2, ((50.0, 60.0),)),
    )
    widget.peak_table.selectRow(1)
    click_button(widget.delete_peak_btn)
    assert calibration_model.points_index == [0, 2]
    assert widget.peak_table.rowCount() == 2


def test_peak_table_selection_highlights_in_image(
    calibration_controller, calibration_model
):
    widget = calibration_controller.widget
    calibration_model.params.peak_selections = (
        (0, ((10.0, 20.0),)),
        (1, ((30.0, 40.0),)),
    )
    widget.peak_table.selectRow(0)
    assert calibration_controller._selected_pick_rows() == [0]

    # the replot with highlighting put both picks on screen
    x_data, y_data = widget.img_widget.img_scatter_plot_item.getData()
    assert len(x_data) == 2


def test_automatic_refinement_parameters_follow_checkbox(
    calibration_controller, calibration_model, dioptas_model, qtbot
):
    widget = calibration_controller.widget
    widget.show()
    qtbot.addWidget(widget)

    dioptas_model.img_model.load(
        os.path.join(unittest_data_path, "LaB6_40keV_MarCCD.tif")
    )
    calibration_model.params.peak_selections = ((0, ((10.0, 20.0),)),)
    calibration_controller.go_to_wizard_step(2)

    # enabled by default: the automatic-refinement parameters are shown
    assert widget.options_automatic_refinement_cb.isChecked()
    assert widget.options_num_rings_sb.isVisible()
    assert widget.options_num_rings_sb.value() == 15

    click_checkbox(widget.options_automatic_refinement_cb)
    assert not widget.options_num_rings_sb.isVisible()
    assert not widget.options_peaksearch_algorithm_cb.isVisible()

    click_checkbox(widget.options_automatic_refinement_cb)
    assert widget.options_num_rings_sb.isVisible()


def test_manual_parameter_entry_without_poni(
    calibration_controller, calibration_model
):
    widget = calibration_controller.widget

    # the validation page is closed without a calibration ...
    calibration_controller.go_to_wizard_step(3)
    assert widget.step_stack.currentIndex() != 3

    # ... but Enter Manually opens it directly
    click_button(widget.enter_parameters_btn)
    assert widget.step_stack.currentIndex() == 3

    pyfai_widget = (
        widget.calibration_control_widget.pyfai_parameters_widget
    )
    for txt_field, value in [
        (pyfai_widget.distance_txt, "200"),
        (pyfai_widget.wavelength_txt, "0.31"),
        (pyfai_widget.polarization_txt, "0.99"),
        (pyfai_widget.poni1_txt, "0.08"),
        (pyfai_widget.poni2_txt, "0.08"),
        (pyfai_widget.rotation1_txt, "0"),
        (pyfai_widget.rotation2_txt, "0"),
        (pyfai_widget.rotation3_txt, "0"),
        (pyfai_widget.pixel_width_txt, "79"),
        (pyfai_widget.pixel_height_txt, "79"),
    ]:
        txt_field.setText(value)

    calibration_controller.update_all = MagicMock()
    click_button(widget.pf_update_btn)
    assert calibration_model.is_calibrated
    assert calibration_controller.update_all.called


def test_manual_parameter_update_with_empty_fields_shows_message(
    calibration_controller, calibration_model
):
    widget = calibration_controller.widget
    click_button(widget.enter_parameters_btn)

    QtWidgets.QMessageBox.critical = MagicMock()
    click_button(widget.pf_update_btn)
    assert QtWidgets.QMessageBox.critical.called
    assert not calibration_model.is_calibrated


def test_image_clicks_only_pick_peaks_on_the_pick_rings_step(
    calibration_controller, calibration_model, dioptas_model
):
    dioptas_model.img_model.load(
        os.path.join(unittest_data_path, "LaB6_40keV_MarCCD.tif")
    )
    # on the image step a click must not add peaks
    assert calibration_controller.widget.step_stack.currentIndex() == 0
    calibration_controller.search_peaks(1179.6, 1129.4)
    assert len(calibration_model.points) == 0

    calibration_controller.go_to_wizard_step(1)
    calibration_controller.search_peaks(1179.6, 1129.4)
    assert len(calibration_model.points) == 1


def test_validation_click_links_position_across_views(
    calibration_controller, calibration_model, dioptas_model
):
    widget = calibration_controller.widget
    dioptas_model.img_model.load(
        os.path.join(unittest_data_path, "LaB6_40keV_MarCCD.tif")
    )
    calibration_model.load(
        os.path.join(unittest_data_path, "LaB6_40keV_MarCCD.poni")
    )
    calibration_controller.go_to_wizard_step(3)

    # off the validation step nothing is published
    calibration_controller.go_to_wizard_step(1)
    calibration_controller.validation_pattern_click(12.0, 0)
    assert dioptas_model.clicked_tth != 12.0

    calibration_controller.go_to_wizard_step(3)
    calibration_controller.validation_pattern_click(12.0, 0)
    assert dioptas_model.clicked_tth == pytest.approx(12.0)
    assert widget.pattern_widget.get_pos_line() == pytest.approx(12.0)

    # a click on the image publishes its 2theta as well
    calibration_controller.validation_img_click(1179.6, 1129.4)
    assert dioptas_model.clicked_tth != pytest.approx(12.0)


def test_only_calibrant_lines_are_drawn_in_validation_views(
    calibration_controller, calibration_model, dioptas_model
):
    widget = calibration_controller.widget
    dioptas_model.img_model.load(
        os.path.join(unittest_data_path, "LaB6_40keV_MarCCD.tif")
    )
    calibration_model.load(
        os.path.join(unittest_data_path, "LaB6_40keV_MarCCD.poni")
    )
    calibration_model.cake_tth = np.linspace(0, 30, 1000)
    calibration_controller.go_to_wizard_step(3)

    # The calibrant is overlaid in every validation view.
    calibrant_ring_count = len(widget.img_widget._phase_ring_items)
    calibrant_cake_line_count = len(widget.cake_widget._phase_line_items)
    assert calibrant_ring_count > 0
    assert calibrant_cake_line_count > 0

    # the calibrant's rings are numbered so they can be matched to the
    # ring spinbox during peak picking; numbering starts at 1
    calibrant_label_count = len(widget.img_widget._phase_ring_label_items)
    assert calibrant_label_count > 0
    assert widget.img_widget._phase_ring_label_items[0].toPlainText() == "1"

    # the numbers follow the zoom: every label anchors inside the current
    # view when its ring crosses it, and hides when the ring is out of view
    widget.img_widget.img_view_box.setRange(
        xRange=(1100, 1600), yRange=(1100, 1600), padding=0
    )
    visible_labels = [
        item
        for item in widget.img_widget._phase_ring_label_items
        if item.isVisible()
    ]
    assert 0 < len(visible_labels) < calibrant_label_count
    # the aspect-locked view box widens the requested range, so compare
    # against what is actually in view
    (x_min, x_max), (y_min, y_max) = widget.img_widget.img_view_box.viewRange()
    for item in visible_labels:
        assert x_min < item.pos().x() < x_max
        assert y_min < item.pos().y() < y_max

    # zoomed inside the innermost ring no label is left in view
    widget.img_widget.img_view_box.setRange(
        xRange=(1000, 1080), yRange=(1000, 1080), padding=0
    )
    assert not any(
        item.isVisible() for item in widget.img_widget._phase_ring_label_items
    )
    widget.img_widget.auto_range()

    dioptas_model.phase_model.add_jcpds(
        os.path.join(unittest_data_path, "jcpds", "au_Anderson.jcpds")
    )
    # Integration phases must not leak into any of the validation plots.
    assert len(widget.img_widget._phase_ring_items) == calibrant_ring_count
    assert len(widget.img_widget._phase_ring_label_items) == calibrant_label_count
    assert len(widget.cake_widget._phase_line_items) == calibrant_cake_line_count
    assert len(widget.pattern_widget.phases) == 0

    dioptas_model.phase_model.del_phase(0)
    assert len(widget.img_widget._phase_ring_items) == calibrant_ring_count
    assert len(widget.cake_widget._phase_line_items) == calibrant_cake_line_count
    assert len(widget.pattern_widget.phases) == 0


def test_calibrant_lines_and_numbers_can_be_hidden(
    calibration_controller, calibration_model, dioptas_model
):
    widget = calibration_controller.widget
    dioptas_model.img_model.load(
        os.path.join(unittest_data_path, "LaB6_40keV_MarCCD.tif")
    )
    calibration_model.load(
        os.path.join(unittest_data_path, "LaB6_40keV_MarCCD.poni")
    )
    calibration_controller.load_calibrant(wavelength_from="pyFAI")
    calibration_controller.go_to_wizard_step(3)
    assert len(widget.img_widget._phase_ring_items) > 0
    assert len(widget.img_widget._phase_ring_label_items) > 0
    assert len(widget.pattern_widget.phases_vlines[0].line_items) > 0

    # numbers off: the lines stay, the labels disappear
    click_checkbox(widget.show_calibrant_numbers_cb)
    assert len(widget.img_widget._phase_ring_items) > 0
    assert len(widget.img_widget._phase_ring_label_items) == 0

    # lines off: everything disappears, in the pattern too; the numbers
    # checkbox is moot without lines
    click_checkbox(widget.show_calibrant_lines_cb)
    assert len(widget.img_widget._phase_ring_items) == 0
    assert len(widget.pattern_widget.phases_vlines[0].line_items) == 0
    assert not widget.show_calibrant_numbers_cb.isEnabled()

    # lines back on: rings and pattern lines return, numbers still off
    click_checkbox(widget.show_calibrant_lines_cb)
    assert len(widget.img_widget._phase_ring_items) > 0
    assert len(widget.pattern_widget.phases_vlines[0].line_items) > 0
    assert len(widget.img_widget._phase_ring_label_items) == 0
    assert widget.show_calibrant_numbers_cb.isEnabled()


def test_project_reset_clears_rings_and_ring_number(
    calibration_controller, calibration_model, dioptas_model
):
    widget = calibration_controller.widget
    dioptas_model.img_model.load(
        os.path.join(unittest_data_path, "LaB6_40keV_MarCCD.tif")
    )
    calibration_model.load(
        os.path.join(unittest_data_path, "LaB6_40keV_MarCCD.poni")
    )
    calibration_controller.go_to_wizard_step(3)
    assert len(widget.img_widget._phase_ring_items) > 0
    widget.peak_num_sb.setValue(5)

    dioptas_model.reset()

    # the old calibration's rings must not survive the reset, no matter
    # which wizard step is shown
    assert len(widget.img_widget._phase_ring_items) == 0
    assert len(widget.img_widget._phase_ring_label_items) == 0
    assert widget.peak_num_sb.value() == 1


def test_ring_number_follows_configuration_switch(
    calibration_controller, calibration_model, dioptas_model
):
    widget = calibration_controller.widget
    dioptas_model.img_model.load(
        os.path.join(unittest_data_path, "LaB6_40keV_MarCCD.tif")
    )
    calibration_model.load(
        os.path.join(unittest_data_path, "LaB6_40keV_MarCCD.poni")
    )
    calibration_model.find_peaks_automatic(1179.6, 1129.4, 0)
    calibration_model.find_peaks_automatic(1268.5, 1119.8, 1)
    widget.peak_num_sb.setValue(3)

    dioptas_model.add_configuration()
    assert widget.peak_num_sb.value() == 1

    dioptas_model.select_configuration(0)
    assert widget.peak_num_sb.value() == 3


def test_fixed_parameters_can_be_set_before_calibration(calibration_controller):
    widget = calibration_controller.widget
    start_values_gb = (
        widget.calibration_control_widget
        .calibration_parameters_widget.start_values_gb
    )
    # everything refined by default
    assert widget.get_fixed_values() == {}

    click_checkbox(start_values_gb.rotation3_cb)
    start_values_gb.rotation3_txt.setText("0.01")
    click_checkbox(start_values_gb.poni1_cb)
    start_values_gb.poni1_txt.setText("0.08")
    assert widget.get_fixed_values() == {"rot3": 0.01, "poni1": 0.08}

    # mirrored onto the pyFAI parameter page and back
    assert not widget.pf_rot3_cb.isChecked()
    assert not widget.pf_poni1_cb.isChecked()
    click_checkbox(widget.pf_rot3_cb)
    assert start_values_gb.rotation3_cb.isChecked()
    assert widget.get_fixed_values() == {"poni1": 0.08}


def test_fitted_values_sync_into_constraint_fields(calibration_controller):
    widget = calibration_controller.widget
    start_values_gb = (
        widget.calibration_control_widget
        .calibration_parameters_widget.start_values_gb
    )
    widget.set_pyFAI_parameter(
        {
            "dist": 0.2,
            "poni1": 0.081,
            "poni2": 0.082,
            "rot1": 0.001,
            "rot2": 0.002,
            "rot3": 0.003,
            "wavelength": 0.31e-10,
            "polarization_factor": 0.99,
            "pixel1": 79e-6,
            "pixel2": 79e-6,
        }
    )
    assert float(start_values_gb.rotation1_txt.text()) == pytest.approx(0.001)
    assert float(start_values_gb.rotation3_txt.text()) == pytest.approx(0.003)
    assert float(start_values_gb.poni1_txt.text()) == pytest.approx(0.081)


def test_project_reset_clears_peak_views(
    calibration_controller, calibration_model, dioptas_model
):
    widget = calibration_controller.widget
    calibration_model.params.peak_selections = ((0, ((10.0, 20.0),)),)
    dioptas_model.use_mask = True
    dioptas_model.mask_changed.emit()
    assert widget.peak_table.rowCount() == 1
    assert widget.use_mask_cb.isChecked()

    dioptas_model.reset()
    assert widget.peak_table.rowCount() == 0
    # the mask state of the fresh configuration is shown, not the old one
    assert not widget.use_mask_cb.isChecked()
    x_data, y_data = widget.img_widget.img_scatter_plot_item.getData()
    assert x_data is None or len(x_data) == 0

    # picking in the fresh configuration updates the views again
    dioptas_model.calibration_model.params.peak_selections = (
        (1, ((30.0, 40.0),)),
    )
    assert widget.peak_table.rowCount() == 1
    assert widget.peak_table.cellWidget(0, 0).value() == 2


def test_current_ring_change_selects_groups_of_that_ring(
    calibration_controller, calibration_model
):
    widget = calibration_controller.widget
    calibration_model.params.peak_selections = (
        (0, ((10.0, 20.0),)),
        (1, ((30.0, 40.0),)),
        (0, ((50.0, 60.0),)),
    )
    widget.peak_num_sb.setValue(2)
    assert calibration_controller._selected_pick_rows() == [1]

    widget.peak_num_sb.setValue(1)
    assert calibration_controller._selected_pick_rows() == [0, 2]


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


def test_automatic_refinement_restores_picks_when_no_peaks_found(
    calibration_controller, calibration_model, dioptas_model
):
    widget = calibration_controller.widget
    dioptas_model.img_model.load(
        os.path.join(unittest_data_path, "LaB6_40keV_MarCCD.tif")
    )
    calibration_controller.go_to_wizard_step(1)
    calibration_controller.search_peaks(1179.6, 1129.4)
    previous_selections = calibration_model.params.peak_selections
    assert len(previous_selections) == 1
    previous_peak_num = widget.peak_num_sb.value()

    # the search finds nothing (e.g. threshold too low) — the manual
    # picks must survive the refinement attempt
    calibration_model.search_peaks_on_ring = MagicMock(return_value=[])
    with patch.object(QtWidgets.QMessageBox, "critical") as critical:
        calibration_controller.automatic_refinement()

    assert critical.called
    assert calibration_model.params.peak_selections == previous_selections
    assert widget.peak_num_sb.value() == previous_peak_num
