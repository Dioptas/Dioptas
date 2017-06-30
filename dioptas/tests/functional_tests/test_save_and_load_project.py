# -*- coding: utf8 -*-

import os
import gc

import numpy as np

from mock import MagicMock, patch

from qtpy import QtWidgets

import fabio

from ...model.CalibrationModel import CalibrationModel
from ...model.util.HelperModule import rotate_matrix_m90, rotate_matrix_p90
from ...controller.MainController import MainController
from ..utility import QtTest, click_button

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')
jcpds_path = os.path.join(data_path, 'jcpds')

# shared settings for save and load tests
config_file_path = os.path.join(data_path, 'test_save_load.hdf5')

working_directories = {'image': data_path,
                       'calibration': data_path,
                       'phase': os.path.join(data_path, 'jcpds'),
                       'overlay': data_path,
                       'mask': data_path,
                       'pattern': data_path}

integration_unit = 'q_A^-1'
use_mask = True
transparent_mask = True
roi = (100, 120, 300, 400)
auto_save_integrated_patterns = True
integrated_patterns_file_formats = ['.xy', '.chi']
img_autoprocess = True
detector_thickness = 30
absorption_length = 175
test_image_file_name = os.path.join(data_path, 'CeO2_Pilatus1M.tif')
test_image_file_name_2 = os.path.join(data_path, 'a_CeO2_Pilatus1M.tif')
test_calibration_file = os.path.join(data_path, 'CeO2_Pilatus1M.poni')
test_calibration_file_2 = os.path.join(data_path, 'a_CeO2_Pilatus1M.poni')
poly_order = 55
pyfai_params = {'detector': 'Detector',
                'dist': 0.196711580484,
                'poni1': 0.0813975852141,
                'poni2': 0.0820662115429,
                'rot1': 0.00615439716514,
                'rot2': -0.00156720465515,
                'rot3': 1.68707221612e-06,
                'pixel1': 7.9e-05,
                'pixel2': 7.9e-05,
                'wavelength': 3.1e-11,
                'polarization_factor': 0.99,
                'splineFile': None}
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
        del self.model
        del self.config_widget
        del self.config_controller
        del self.controller
        del self.widget
        gc.collect()

    def load_image(self, file_name):
        QtWidgets.QFileDialog.getOpenFileNames = MagicMock(return_value=[file_name])
        click_button(self.controller.integration_controller.widget.load_img_btn)  # load file

        self.model.current_configuration.calibration_model.set_pyFAI(pyfai_params)
        self.model.working_directories = working_directories
        self.model.current_configuration.integration_unit = integration_unit
        self.raw_img_data = self.model.current_configuration.img_model.raw_img_data

    def save_and_load_configuration(self, prepare_function, intermediate_function=None, mock_1d_integration=True):

        if mock_1d_integration:
            with patch.object(CalibrationModel, 'integrate_1d', return_value=(np.linspace(0, 20, 1001),
                                                                              np.ones((1001,)))):
                self.load_image(test_image_file_name)
                if prepare_function is not None:
                    prepare_function()
                self.save_configuration()
                self.tearDown()
                self.setUp()

                if intermediate_function:
                    intermediate_function()

                self.load_configuration()
        else:
            self.load_image(test_image_file_name)
            if prepare_function is not None:
                prepare_function()
            self.save_configuration()
            self.tearDown()
            self.setUp()

            if intermediate_function:
                intermediate_function()

            self.load_configuration()

    def existing_files_intermediate_settings(self):
        self.check_calibration = False

    def save_configuration(self):
        QtWidgets.QFileDialog.getSaveFileName = MagicMock(return_value=config_file_path)
        click_button(self.widget.save_btn)
        self.assertTrue(os.path.isfile(config_file_path))

    def load_configuration(self):
        self.model.working_directories = {'calibration': 'moo', 'mask': 'baa', 'image': '', 'pattern': ''}
        QtWidgets.QFileDialog.getOpenFileName = MagicMock(return_value=config_file_path)
        click_button(self.widget.load_btn)
        saved_working_directories = self.model.working_directories
        self.assertDictEqual(saved_working_directories, working_directories)
        if self.check_calibration:
            saved_pyfai_params, _ = self.model.calibration_model.get_calibration_parameter()
            self.assertDictEqual(saved_pyfai_params, pyfai_params)

    ####################################################################################################################
    def test_save_and_load_configuration_basic(self):
        self.save_and_load_configuration(None)

    def test_with_auto_processing(self):
        self.save_and_load_configuration(self.auto_process_settings)
        self.assertEqual(self.model.current_configuration.auto_save_integrated_pattern, auto_save_integrated_patterns)
        self.assertEqual(self.model.current_configuration.integrated_patterns_file_formats,
                         integrated_patterns_file_formats)
        self.assertEqual(self.model.current_configuration.img_model.autoprocess, img_autoprocess)

    def auto_process_settings(self):
        self.model.current_configuration.auto_save_integrated_pattern = auto_save_integrated_patterns
        self.model.current_configuration.integrated_patterns_file_formats = integrated_patterns_file_formats
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
        self.mask_data = np.eye(self.raw_img_data.shape[0], self.raw_img_data.shape[1], dtype=bool)
        self.model.mask_model.set_mask(self.mask_data)

    ####################################################################################################################
    def test_with_image_transformations(self):
        img_filename = os.path.join(data_path, 'CeO2_Pilatus1M.tif')
        with patch.object(CalibrationModel, 'integrate_1d', return_value=(np.linspace(0, 20, 1001),
                                                                          np.ones((1001,)))):
            self.load_image(img_filename)
        self.save_and_load_configuration(self.image_transformations)

        img_data = fabio.open(img_filename).data[::-1]
        img_data = rotate_matrix_m90(img_data)
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
        self.assertEqual(self.model.phase_model.phases[0].params['pressure'], pressure)

    def phase_settings(self):
        self.load_phase('ar.jcpds')
        self.model.phase_model.phases[0].params['pressure'] = pressure

    def load_phase(self, filename):
        QtWidgets.QFileDialog.getOpenFileNames = MagicMock(return_value=[os.path.join(jcpds_path, filename)])
        click_button(self.controller.widget.integration_widget.phase_add_btn)

    ####################################################################################################################
    def test_with_overlays(self):
        self.save_and_load_configuration(self.overlay_settings)

    def overlay_settings(self):
        self.controller.integration_controller.widget.qa_set_as_overlay_btn.click()
        self.controller.integration_controller.widget.qa_set_as_overlay_btn.click()
        self.controller.integration_controller.widget.overlay_set_as_bkg_btn.click()
        self.current_pattern_x, self.current_pattern_y = \
            self.model.current_configuration.pattern_model.get_pattern().data

    ####################################################################################################################
    def test_with_roi(self):
        self.save_and_load_configuration(self.roi_settings)
        self.assertTupleEqual(self.model.current_configuration.roi, roi)
        self.assertTrue(self.controller.integration_controller.widget.img_roi_btn.isChecked())

    def roi_settings(self):
        self.controller.integration_controller.image_controller.widget.img_roi_btn.click()
        self.model.current_configuration.roi = roi

    ####################################################################################################################
    def test_with_cbn_correction(self):
        self.save_and_load_configuration(self.cbn_correction_settings, mock_1d_integration=False)
        self.assertEqual(self.model.current_configuration.img_model.img_corrections.
                         corrections["cbn"]._diamond_thickness, 1.9)

    def cbn_correction_settings(self):
        self.controller.widget.integration_widget.cbn_groupbox.setChecked(True)
        self.controller.widget.integration_widget.cbn_diamond_thickness_txt.setText('1.9')
        self.controller.integration_controller.image_controller.cbn_groupbox_changed()

    ####################################################################################################################
    def test_with_oiadac_correction(self):
        self.save_and_load_configuration(self.oiadac_correction_settings, mock_1d_integration=False)
        self.assertEqual(self.model.current_configuration.img_model.img_corrections.
                         corrections["oiadac"].detector_thickness, 30)
        self.assertEqual(self.model.current_configuration.img_model.img_corrections.
                         corrections["oiadac"].absorption_length, 450)

    def oiadac_correction_settings(self):
        self.controller.widget.integration_widget.oiadac_groupbox.setChecked(True)
        self.controller.widget.integration_widget.oiadac_thickness_txt.setText('30')
        self.controller.widget.integration_widget.oiadac_abs_length_txt.setText('450')
        self.controller.integration_controller.image_controller.oiadac_groupbox_changed()

    ####################################################################################################################
    def test_configuration_in_cake_mode(self):
        self.save_and_load_configuration(self.cake_settings)
        self.assertTrue(self.model.current_configuration.auto_integrate_cake)

    def cake_settings(self):
        self.controller.integration_controller.widget.img_mode_btn.click()

    ####################################################################################################################
    def test_with_fit_bg(self):
        self.save_and_load_configuration(self.fit_bg_settings)
        self.assertEqual(self.widget.integration_widget.bkg_pattern_poly_order_sb.value(), poly_order)

    ####################################################################################################################
    def test_multiple_configurations(self):
        self.save_and_load_configuration(self.add_configuration)
        self.assertEqual(len(self.config_widget.configuration_btns), 2)

    def add_configuration(self):
        click_button(self.widget.configuration_widget.add_configuration_btn)

    def fit_bg_settings(self):
        self.controller.integration_controller.widget.qa_bkg_pattern_btn.click()
        self.controller.integration_controller.widget.bkg_pattern_poly_order_sb.setValue(poly_order)

    ####################################################################################################################
    def test_with_background_image(self):
        self.save_and_load_configuration(self.add_background_image)
        self.assertTrue(self.model.img_model.has_background())
        self.assertEqual(test_image_file_name, self.model.img_model.background_filename)
        self.assertEqual(os.path.split(test_image_file_name)[1],
                         self.widget.integration_widget.bkg_image_filename_lbl.text())

    def add_background_image(self):
        QtWidgets.QFileDialog.getOpenFileName = MagicMock(return_value=test_image_file_name)
        click_button(self.controller.integration_controller.widget.bkg_image_load_btn)

    ####################################################################################################################
    def test_save_settings_on_closing(self):
        with patch.object(CalibrationModel, 'integrate_1d', return_value=(np.linspace(0, 20, 1001),
                                                                          np.ones((1001,)))):
            self.load_image(test_image_file_name)
            self.controller.widget.close()
            self.controller=MainController(use_settings=True)
            self.assertEqual(self.model.img_model.filename, test_image_file_name)