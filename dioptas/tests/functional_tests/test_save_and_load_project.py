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

import os
import gc
from collections import OrderedDict

import numpy as np

from mock import MagicMock, patch

from qtpy import QtWidgets

import fabio

from ...model.CalibrationModel import CalibrationModel
from ...model.util.HelperModule import rotate_matrix_m90, rotate_matrix_p90
from ...controller.MainController import MainController
from ..utility import (
    QtTest,
    click_button,
    delete_if_exists,
    enter_value_into_text_field,
)

from ... import calibrants_path

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, "../data")
jcpds_path = os.path.join(data_path, "jcpds")

# shared settings for save and load tests
config_file_path = os.path.join(data_path, "test_save_load.hdf5")

working_directories = {
    "image": data_path,
    "calibration": data_path,
    "phase": os.path.join(data_path, "jcpds"),
    "overlay": data_path,
    "mask": data_path,
    "pattern": data_path,
}

integration_unit = "q_A^-1"
use_mask = True
transparent_mask = True
roi = (100, 120, 300, 400)
auto_save_integrated_patterns = True
integrated_patterns_file_formats = [".xy", ".chi"]
img_autoprocess = True
detector_thickness = 30
absorption_length = 175
test_image_file_name = os.path.join(data_path, "CeO2_Pilatus1M.tif")
test_image_file_name_2 = os.path.join(data_path, "a_CeO2_Pilatus1M.tif")
test_calibration_file = os.path.join(data_path, "CeO2_Pilatus1M.poni")
test_calibration_file_2 = os.path.join(data_path, "a_CeO2_Pilatus1M.poni")
poly_order = 55
x_min = 1.0
x_max = 8.0
pyfai_params = OrderedDict(
    {
        "detector": "Detector",
        "pixel1": 7.9e-05,
        "pixel2": 7.9e-05,
        "dist": 0.196711580484,
        "poni1": 0.0813975852141,
        "poni2": 0.0820662115429,
        "rot1": 0.00615439716514,
        "rot2": -0.00156720465515,
        "rot3": 1.68707221612e-06,
        "wavelength": 3.1e-11,
        "polarization_factor": 0.99,
    }
)
pressure = 12.0


class ProjectSaveLoadTest(QtTest):
    def setUp(self):
        self.controller = MainController(use_settings=False)
        self.model = self.controller.model
        self.widget = self.controller.widget
        self.config_widget = self.controller.widget.configuration_widget
        self.config_controller = self.controller.configuration_controller
        self.check_calibration = True

    def tearDown(self):
        delete_if_exists(os.path.join(data_path, "CeO2_Pilatus1M.chi"))
        delete_if_exists(os.path.join(data_path, "CeO2_Pilatus1M.xy"))
        delete_if_exists(config_file_path)
        self.resetState()

    def resetState(self):
        if self.model.calibration_model.cake_geometry is not None:
            self.model.calibration_model.cake_geometry.reset()
        self.model.calibration_model.pattern_geometry.reset()
        self.model.disconnect_models()

        self.config_widget.deleteLater()
        self.widget.integration_widget.deleteLater()
        self.widget.integration_widget.integration_control_widget.deleteLater()
        self.widget.integration_widget.integration_image_widget.deleteLater()
        self.widget.integration_widget.integration_pattern_widget.deleteLater()
        self.widget.integration_widget.integration_status_widget.deleteLater()
        self.widget.mask_widget.deleteLater()
        self.widget.calibration_widget.deleteLater()
        self.widget.deleteLater()

        del self.config_widget
        del self.widget.integration_widget.integration_control_widget
        del self.widget.integration_widget.integration_image_widget
        del self.widget.integration_widget.integration_pattern_widget
        del self.widget.integration_widget.integration_status_widget
        del self.widget.integration_widget
        del self.widget.mask_widget
        del self.widget.calibration_widget
        del self.widget

        del self.config_controller
        del self.controller
        del self.model
        gc.collect()

    def load_image(self, file_name):
        QtWidgets.QFileDialog.getOpenFileNames = MagicMock(return_value=[file_name])
        click_button(
            self.controller.integration_controller.widget.load_img_btn
        )  # load file

        self.model.current_configuration.calibration_model.set_pyFAI(pyfai_params)
        self.model.working_directories = working_directories
        self.model.current_configuration.integration_unit = integration_unit
        self.raw_img_data = self.model.current_configuration.img_model.raw_img_data

    def save_and_load_configuration(
        self, prepare_function, intermediate_function=None, mock_1d_integration=True
    ):
        if mock_1d_integration:
            with patch.object(
                CalibrationModel,
                "integrate_1d",
                return_value=(np.linspace(0, 20, 1001), np.ones((1001,))),
            ):
                self.load_image(test_image_file_name)
                if prepare_function is not None:
                    prepare_function()
                self.save_configuration()
                self.model.reset()
                self.model.working_directories = {
                    "calibration": "",
                    "mask": "",
                    "image": os.path.expanduser("~"),
                    "pattern": "",
                    "overlay": "",
                    "phase": "",
                }
                self.resetState()
                self.setUp()
                if intermediate_function:
                    intermediate_function()

                self.load_configuration()
        else:
            self.load_image(test_image_file_name)
            if prepare_function is not None:
                prepare_function()
            self.save_configuration()
            self.model.reset()
            self.model.working_directories = {
                "calibration": "",
                "mask": "",
                "image": os.path.expanduser("~"),
                "pattern": "",
                "overlay": "",
                "phase": "",
            }
            self.resetState()
            self.setUp()
            if intermediate_function:
                intermediate_function()

            self.load_configuration()

        delete_if_exists(config_file_path)

    def disable_calibration_check(self):
        self.check_calibration = False

    def save_configuration(self):
        QtWidgets.QFileDialog.getSaveFileName = MagicMock(return_value=config_file_path)
        click_button(self.widget.save_btn)
        self.assertTrue(os.path.isfile(config_file_path))

    def load_configuration(self):
        self.model.working_directories = {
            "calibration": "moo",
            "mask": "baa",
            "image": "",
            "pattern": "",
        }
        QtWidgets.QFileDialog.getOpenFileName = MagicMock(return_value=config_file_path)
        click_button(self.widget.load_btn)
        saved_working_directories = self.model.working_directories
        self.assertDictEqual(saved_working_directories, working_directories)
        if self.check_calibration:
            saved_pyfai_params, _ = (
                self.model.calibration_model.get_calibration_parameter()
            )
            if "splineFile" in saved_pyfai_params:
                del saved_pyfai_params["splineFile"]
            if "max_shape" in saved_pyfai_params:
                del saved_pyfai_params["max_shape"]
            self.assertDictEqual(saved_pyfai_params, pyfai_params)

    ####################################################################################################################
    def test_with_auto_processing(self):
        self.save_and_load_configuration(self.auto_process_settings)
        self.assertEqual(
            self.model.current_configuration.auto_save_integrated_pattern,
            auto_save_integrated_patterns,
        )
        self.assertEqual(
            self.model.current_configuration.integrated_patterns_file_formats,
            integrated_patterns_file_formats,
        )
        self.assertEqual(
            self.model.current_configuration.img_model.autoprocess, img_autoprocess
        )

    def auto_process_settings(self):
        self.model.current_configuration.auto_save_integrated_pattern = (
            auto_save_integrated_patterns
        )
        self.model.current_configuration.integrated_patterns_file_formats = (
            integrated_patterns_file_formats
        )
        self.model.current_configuration.img_model.autoprocess = img_autoprocess

    ####################################################################################################################
    def test_with_mask(self):
        self.save_and_load_configuration(self.mask_settings)
        self.assertEqual(self.model.use_mask, use_mask)
        self.assertEqual(self.model.transparent_mask, transparent_mask)
        self.assertTrue(np.array_equal(self.model.mask_model.get_img(), self.mask_data))

    def mask_settings(self):
        self.model.current_configuration.use_mask = True
        self.model.current_configuration.transparent_mask = True
        self.mask_data = np.eye(
            self.raw_img_data.shape[0], self.raw_img_data.shape[1], dtype=bool
        )
        self.model.mask_model.set_mask(self.mask_data)

    ####################################################################################################################
    def test_image_rotation(self):
        img_filename = os.path.join(data_path, "CeO2_Pilatus1M.tif")
        with patch.object(
            CalibrationModel,
            "integrate_1d",
            return_value=(np.linspace(0, 20, 1001), np.ones((1001,))),
        ):
            self.load_image(img_filename)
        self.save_and_load_configuration(self.image_transformations)

        img_data = fabio.open(img_filename).data[::-1]
        img_data = rotate_matrix_m90(img_data)

        self.assertNotEqual(
            img_data.shape, self.model.img_model.untransformed_raw_img_data.shape
        )
        self.assertEqual(np.sum(img_data - self.model.img_model.img_data), 0)

    def rotate_image_p90(self):
        click_button(self.widget.calibration_widget.rotate_p90_btn)

    ####################################################################################################################
    def test_with_image_transformations(self):
        img_filename = os.path.join(data_path, "CeO2_Pilatus1M.tif")
        with patch.object(
            CalibrationModel,
            "integrate_1d",
            return_value=(np.linspace(0, 20, 1001), np.ones((1001,))),
        ):
            self.load_image(img_filename)
        self.save_and_load_configuration(self.image_transformations)

        img_data = fabio.open(img_filename).data[::-1]
        img_data = rotate_matrix_m90(img_data)
        img_data = np.fliplr(img_data)
        img_data = rotate_matrix_p90(img_data)
        img_data = np.flipud(img_data)
        img_data = rotate_matrix_m90(img_data)
        img_data = rotate_matrix_m90(img_data)
        img_data = np.fliplr(img_data)
        img_data = np.flipud(img_data)
        img_data = rotate_matrix_p90(img_data)

        self.assertEqual(np.sum(img_data - self.model.img_data), 0)

    def image_transformations(self):
        click_button(self.widget.calibration_widget.rotate_m90_btn)
        click_button(self.widget.calibration_widget.invert_horizontal_btn)
        click_button(self.widget.calibration_widget.rotate_p90_btn)
        click_button(self.widget.calibration_widget.invert_vertical_btn)
        click_button(self.widget.calibration_widget.rotate_m90_btn)
        click_button(self.widget.calibration_widget.rotate_m90_btn)
        click_button(self.widget.calibration_widget.invert_horizontal_btn)
        click_button(self.widget.calibration_widget.invert_vertical_btn)
        click_button(self.widget.calibration_widget.rotate_p90_btn)

    ####################################################################################################################
    def test_with_phases(self):
        self.save_and_load_configuration(self.phase_settings)
        self.assertEqual(self.model.phase_model.phases[0].params["pressure"], pressure)

    def phase_settings(self):
        self.load_phase("ar.jcpds")
        self.model.phase_model.phases[0].params["pressure"] = pressure

    def load_phase(self, filename):
        QtWidgets.QFileDialog.getOpenFileNames = MagicMock(
            return_value=[os.path.join(jcpds_path, filename)]
        )
        click_button(self.controller.widget.integration_widget.phase_add_btn)

    ####################################################################################################################
    def test_with_overlays(self):
        self.save_and_load_configuration(self.overlay_settings)

    def overlay_settings(self):
        self.controller.integration_controller.widget.qa_set_as_overlay_btn.click()
        self.controller.integration_controller.widget.qa_set_as_overlay_btn.click()
        self.controller.integration_controller.widget.overlay_set_as_bkg_btn.click()
        self.current_pattern_x, self.current_pattern_y = (
            self.model.current_configuration.pattern_model.get_pattern().data
        )

    ####################################################################################################################
    def test_with_roi(self):
        self.save_and_load_configuration(self.roi_settings)
        self.assertTupleEqual(self.model.current_configuration.roi, roi)
        self.assertTrue(
            self.controller.integration_controller.widget.img_roi_btn.isChecked()
        )

    def roi_settings(self):
        self.controller.integration_controller.image_controller.widget.img_roi_btn.click()
        self.model.current_configuration.roi = roi

    ####################################################################################################################
    def test_with_cbn_correction(self):
        self.save_and_load_configuration(
            self.cbn_correction_settings, mock_1d_integration=False
        )
        print(self.model.current_configuration.img_model.img_corrections.corrections)
        self.assertEqual(
            self.model.current_configuration.img_model.img_corrections.corrections[
                "cbn"
            ]._diamond_thickness,
            1.9,
        )

    def cbn_correction_settings(self):
        self.controller.widget.integration_widget.cbn_groupbox.setChecked(True)
        self.controller.widget.integration_widget.cbn_param_tw.cellWidget(0, 1).setText(
            "1.9"
        )
        self.controller.integration_controller.correction_controller.cbn_groupbox_changed()

    ####################################################################################################################
    def test_with_oiadac_correction(self):
        self.save_and_load_configuration(
            self.oiadac_correction_settings, mock_1d_integration=False
        )
        self.assertEqual(
            self.model.current_configuration.img_model.img_corrections.corrections[
                "oiadac"
            ].detector_thickness,
            30,
        )
        self.assertEqual(
            self.model.current_configuration.img_model.img_corrections.corrections[
                "oiadac"
            ].absorption_length,
            450,
        )

    def oiadac_correction_settings(self):
        self.controller.widget.integration_widget.oiadac_groupbox.setChecked(True)
        self.controller.widget.integration_widget.oiadac_param_tw.cellWidget(
            0, 1
        ).setText("30")
        self.controller.widget.integration_widget.oiadac_param_tw.cellWidget(
            1, 1
        ).setText("450")
        self.controller.integration_controller.correction_controller.oiadac_groupbox_changed()

    ####################################################################################################################
    def test_with_transfer_correction(self):
        self.save_and_load_configuration(self.transfer_correction_settings)

        # test model
        self.assertEqual(
            self.model.img_model.transfer_correction.original_filename,
            self.original_filename,
        )
        self.assertEqual(
            self.model.img_model.transfer_correction.response_filename,
            self.response_filename,
        )
        self.assertTrue(self.model.img_model.has_corrections())

        # test widget
        correction_widget = (
            self.widget.integration_widget.integration_control_widget.corrections_control_widget
        )
        self.assertTrue(correction_widget.transfer_gb.isChecked())
        self.assertEqual(
            correction_widget.transfer_original_filename_lbl.text(),
            os.path.basename(self.original_filename),
        )
        self.assertEqual(
            correction_widget.transfer_original_filename_lbl.text(),
            os.path.basename(self.original_filename),
        )

    def transfer_correction_settings(self):
        self.model.calibration_model.detector_reset.emit = MagicMock()
        self.original_filename = os.path.join(
            data_path, "TransferCorrection", "original.tif"
        )
        self.response_filename = os.path.join(
            data_path, "TransferCorrection", "response.tif"
        )
        correction_widget = (
            self.widget.integration_widget.integration_control_widget.corrections_control_widget
        )

        correction_widget.transfer_gb.setChecked(True)
        QtWidgets.QFileDialog.getOpenFileNames = MagicMock(
            return_value=[self.original_filename]
        )
        click_button(self.widget.integration_widget.load_img_btn)
        QtWidgets.QFileDialog.getOpenFileName = MagicMock(
            return_value=self.original_filename
        )
        click_button(correction_widget.transfer_load_original_btn)
        QtWidgets.QFileDialog.getOpenFileName = MagicMock(
            return_value=self.response_filename
        )
        click_button(correction_widget.transfer_load_response_btn)

    ####################################################################################################################
    def test_configuration_in_cake_mode(self):
        self.save_and_load_configuration(self.cake_settings)
        self.assertTrue(self.model.current_configuration.auto_integrate_cake)

    def cake_settings(self):
        self.controller.integration_controller.widget.img_mode_btn.click()

    ####################################################################################################################
    def test_with_fit_bg(self):
        self.save_and_load_configuration(self.fit_bg_settings)
        self.assertEqual(
            self.widget.integration_widget.bkg_pattern_poly_order_sb.value(), poly_order
        )
        self.assertTrue(self.widget.integration_widget.qa_bkg_pattern_btn.isChecked())
        click_button(self.widget.integration_mode_btn)
        self.widget.show()
        self.assertTrue(
            self.widget.integration_widget.qa_bkg_pattern_inspect_btn.isVisible()
        )
        self.widget.close()

    def test_with_q_and_fit_bg(self):
        self.save_and_load_configuration(self.q_and_fit_bg_settings)
        self.assertAlmostEqual(
            float(
                self.controller.integration_controller.widget.bkg_pattern_x_min_txt.text()
            ),
            x_min,
            1,
        )
        self.assertAlmostEqual(
            float(
                self.controller.integration_controller.widget.bkg_pattern_x_max_txt.text()
            ),
            x_max,
            1,
        )

    ####################################################################################################################
    def test_multiple_configurations(self):
        self.save_and_load_configuration(self.add_configuration)
        self.assertEqual(len(self.config_widget.configuration_btns), 2)

    def add_configuration(self):
        click_button(self.widget.configuration_widget.add_configuration_btn)

    def fit_bg_settings(self):
        click_button(self.controller.integration_controller.widget.qa_bkg_pattern_btn)
        self.controller.integration_controller.widget.bkg_pattern_poly_order_sb.setValue(
            poly_order
        )

    def q_and_fit_bg_settings(self):
        self.controller.integration_controller.widget.pattern_q_btn.click()
        self.controller.integration_controller.widget.qa_bkg_pattern_btn.click()
        self.controller.integration_controller.widget.bkg_pattern_poly_order_sb.setValue(
            poly_order
        )

        enter_value_into_text_field(
            self.controller.integration_controller.widget.bkg_pattern_x_min_txt,
            str(x_min),
        )
        enter_value_into_text_field(
            self.controller.integration_controller.widget.bkg_pattern_x_max_txt,
            str(x_max),
        )

    ####################################################################################################################
    def test_with_background_image(self):
        self.save_and_load_configuration(self.add_background_image)
        self.assertTrue(self.model.img_model.has_background())
        self.assertEqual(test_image_file_name, self.model.img_model.background_filename)
        self.assertEqual(
            os.path.split(test_image_file_name)[1],
            self.widget.integration_widget.bkg_image_filename_lbl.text(),
        )

    def add_background_image(self):
        QtWidgets.QFileDialog.getOpenFileName = MagicMock(
            return_value=test_image_file_name
        )
        click_button(self.controller.integration_controller.widget.bkg_image_load_btn)

    ####################################################################################################################
    def test_with_automatic_background_subtraction(self):
        self.save_and_load_configuration(
            self.activate_automatic_background_subtraction, mock_1d_integration=True
        )
        self.assertGreater(self.model.pattern.auto_background_subtraction_roi[0], 9.0)
        self.assertTrue(self.widget.integration_widget.qa_bkg_pattern_btn.isChecked())
        self.assertGreater(
            float(self.widget.integration_widget.bkg_pattern_x_min_txt.text()), 9
        )
        self.assertTrue(self.widget.integration_widget.qa_bkg_pattern_btn.isChecked())

        click_button(self.widget.integration_mode_btn)
        self.widget.show()
        self.assertTrue(
            self.widget.integration_widget.qa_bkg_pattern_inspect_btn.isVisible()
        )
        self.widget.close()

    def activate_automatic_background_subtraction(self):
        self.model.pattern.load(os.path.join(data_path, "pattern_001.xy"))
        click_button(self.widget.integration_widget.qa_bkg_pattern_btn)
        enter_value_into_text_field(
            self.widget.integration_widget.bkg_pattern_x_min_txt, "9"
        )
        self.assertGreater(self.model.pattern.auto_background_subtraction_roi[0], 9)

    ####################################################################################################################
    def test_save_settings_on_closing(self):
        with patch.object(
            CalibrationModel,
            "integrate_1d",
            return_value=(np.linspace(0, 20, 1001), np.ones((1001,))),
        ):
            self.load_image(test_image_file_name)
            self.controller.widget.close()
            self.controller = MainController(
                use_settings=True, settings_directory=data_path
            )
            self.assertEqual(self.model.img_model.filename, test_image_file_name)

    ####################################################################################################################
    def test_file_browsing(self):
        self.save_and_load_configuration(self.prepare_file_browsing)
        with patch.object(
            CalibrationModel,
            "integrate_1d",
            return_value=(np.linspace(0, 20, 1001), np.ones((1001,))),
        ):
            click_button(self.widget.integration_widget.img_step_file_widget.next_btn)
            self.assertEqual(
                str(self.widget.integration_widget.img_filename_txt.text()),
                "image_002.tif",
            )

    def prepare_file_browsing(self):
        self.model.calibration_model.detector_reset.emit = MagicMock()
        self.load_image(os.path.join(data_path, "image_001.tif"))

    ####################################################################################################################
    def test_distortion_correction(self):
        self.check_calibration = False
        self.save_and_load_configuration(
            self.prepare_distortion_correction_test,
            intermediate_function=self.disable_calibration_check,
        )
        self.assertIsNotNone(self.model.calibration_model.distortion_spline_filename)
        self.assertEqual(
            self.widget.calibration_widget.spline_filename_txt.text(), "f4mnew.spline"
        )

    def prepare_distortion_correction_test(self):
        self.model.calibration_model.detector_reset.emit = MagicMock()
        self.model.img_model.load(
            os.path.join(data_path, "distortion", "CeO2_calib.edf")
        )

        self.model.calibration_model.find_peaks_automatic(1025.1, 1226.8, 0)
        self.model.calibration_model.set_calibrant(
            os.path.join(calibrants_path, "CeO2.D")
        )
        self.model.calibration_model.start_values["dist"] = 300e-3
        self.model.calibration_model.start_values["pixel_height"] = 50e-6
        self.model.calibration_model.start_values["pixel_width"] = 50e-6
        self.model.calibration_model.start_values["wavelength"] = 0.1e-10

        self.model.calibration_model.load_distortion(
            os.path.join(data_path, "distortion", "f4mnew.spline")
        )
        self.model.calibration_model.calibrate()

        _, y1 = self.model.calibration_model.integrate_1d()

    ####################################################################################################################
    def test_series_loading(self):
        from dioptas.model.loader.KaraboLoader import extra_data_installed

        if not extra_data_installed:
            return
        self.check_calibration = False
        self.save_and_load_configuration(self.prepare_series_file)
        self.assertTrue(self.model.img_model.series_max > 1)

    def prepare_series_file(self):
        self.model.img_model.load(os.path.join(data_path, "karabo_epix.h5"))
        self.assertTrue(self.model.img_model.series_max > 1)

    ####################################################################################################################
    def test_using_predefined_detector(self):
        self.check_calibration = False
        self.save_and_load_configuration(
            self.prepare_load_predefined_detector_test,
            intermediate_function=self.disable_calibration_check,
        )
        from pyFAI import detectors

        self.assertIsInstance(
            self.model.calibration_model.detector, detectors.PilatusCdTe1M
        )
        self.assertEqual(self.model.calibration_model.orig_pixel1, 172e-6)
        self.assertEqual(self.model.calibration_model.orig_pixel2, 172e-6)

        detector_gb = (
            self.widget.calibration_widget.calibration_control_widget.calibration_parameters_widget.detector_gb
        )
        self.assertEqual(
            self.widget.calibration_widget.detectors_cb.currentText(), "Pilatus CdTe 1M"
        )
        self.assertEqual(float(detector_gb.pixel_width_txt.text()), 172)
        self.assertEqual(float(detector_gb.pixel_height_txt.text()), 172)

        self.assertFalse(detector_gb.pixel_width_txt.isEnabled())
        self.assertFalse(detector_gb.pixel_height_txt.isEnabled())

    def prepare_load_predefined_detector_test(self):
        self.widget.calibration_widget.detectors_cb.setCurrentIndex(
            self.widget.calibration_widget.detectors_cb.findText("Pilatus CdTe 1M")
        )

    ###################################################################################################################
    def test_using_loaded_nexus_detector(self):
        self.check_calibration = False
        self.save_and_load_configuration(
            self.prepare_using_loaded_nexus_detector_test,
            intermediate_function=self.disable_calibration_check,
        )

        from ...model.CalibrationModel import DetectorModes
        from pyFAI import detectors

        self.assertEqual(
            self.model.calibration_model.detector_mode, DetectorModes.NEXUS
        )
        self.assertIsInstance(
            self.model.calibration_model.detector, detectors.NexusDetector
        )

    def prepare_using_loaded_nexus_detector_test(self):
        self.model.img_model._img_data = np.ones((1048, 1032))
        self.model.calibration_model.load_detector_from_file(
            os.path.join(data_path, "detector.h5")
        )

    ###################################################################################################
    def test_using_predefined_detector_and_rotate(self):
        self.check_calibration = False
        self.save_and_load_configuration(
            self.prepare_using_predefined_detector_and_rotate,
            intermediate_function=self.disable_calibration_check,
        )
        self.assertEqual(self.model.calibration_model.detector.shape, (981, 1043))

    def prepare_using_predefined_detector_and_rotate(self):
        self.widget.calibration_widget.detectors_cb.setCurrentIndex(
            self.widget.calibration_widget.detectors_cb.findText("Pilatus CdTe 1M")
        )
        click_button(self.widget.calibration_widget.rotate_p90_btn)
        self.assertEqual(self.model.calibration_model.detector.shape, (981, 1043))

    ###################################################################################################
    def test_using_detector_and_calibration(self):
        self.check_calibration = False
        self.save_and_load_configuration(
            self.prepare_using_detector_and_calibration,
            intermediate_function=self.disable_calibration_check,
        )

        self.assertAlmostEqual(self.model.calibration_model.detector.pixel1, 172e-6)

    def prepare_using_detector_and_calibration(self):
        self.model.calibration_model.detector_reset.emit = MagicMock()
        self.model.calibration_model.load(
            os.path.join(data_path, "CeO2_Pilatus1M.poni")
        )
        self.model.img_model.load(os.path.join(data_path, "image_001.tif"))

        self.assertAlmostEqual(self.model.calibration_model.detector.pixel1, 172e-6)

    ###################################################################################################
    def test_saving_poni_detector_orientation(self):
        self.check_calibration = False
        self.save_and_load_configuration(
            self.prepare_saving_poni_detector_orientation,
            intermediate_function=self.disable_calibration_check,
        )

        assert self.model.calibration_model.polarization_factor == -0.1
        assert self.model.calibration_model.detector.pixel1 == 172e-6
        assert (
            self.model.calibration_model.pattern_geometry.get_config()
            == self.model.calibration_model.cake_geometry.get_config()
        )

    def prepare_saving_poni_detector_orientation(self):
        self.model.calibration_model.load(
            os.path.join(data_path, "CeO2_Pilatus1M.poni")
        )
        self.model.calibration_model.polarization_factor = -0.1
