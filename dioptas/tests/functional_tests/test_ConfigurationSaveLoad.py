# -*- coding: utf8 -*-

import os, sys
import unittest
import gc

import numpy as np

from mock import MagicMock
import h5py

from qtpy import QtWidgets, QtCore
from qtpy.QtTest import QTest

from ...controller.MainController import MainController
from ...controller.ConfigurationController import ConfigurationController
from ...model.DioptasModel import DioptasModel
from ...widgets.ConfigurationWidget import ConfigurationWidget
from ..ehook import excepthook


unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')
jcpds_path = os.path.join(data_path, 'jcpds')


def click_button(widget):
    QTest.mouseClick(widget, QtCore.Qt.LeftButton)


def enter_value_into_text_field(text_field, value):
    text_field.setText('')
    QTest.keyClicks(text_field, str(value))
    QTest.keyPress(text_field, QtCore.Qt.Key_Enter)
    QtWidgets.QApplication.processEvents()


class ConfigurationSaveLoadTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance()
        if cls.app is None:
            cls.app = QtWidgets.QApplication([])

    def setUp(self):
        self.controller = MainController()
        self.model = self.controller.model
        self.config_widget = self.controller.widget.configuration_widget
        self.config_controller = self.controller.configuration_controller

    def tearDown(self):
        del self.model
        del self.config_widget
        del self.config_controller
        del self.controller
        gc.collect()

    def test_save_and_load_configuration(self):
        self.test_save_configuration()
        self.tearDown()
        self.setUp()
        self.test_load_configuration()

    def test_save_configuration(self):
        # sys.excepthook = excepthook

        self.model.img_model.load(test_image_file_name)
        self.model.calibration_model.set_pyFAI(pyfai_params)
        self.model.working_directories = working_directories
        self.model.current_configuration.integration_unit = integration_unit
        self.model.use_mask = True
        self.model.transparent_mask = True
        self.model.current_configuration.autosave_integrated_pattern = autosave_integrated_patterns
        self.model.current_configuration.integrated_patterns_file_formats = integrated_patterns_file_formats
        self.model.current_configuration.img_model.autoprocess = img_autoprocess
        self.load_phase('ar.jcpds')
        self.model.phase_model.phases[0].params['pressure'] = pressure

        self.raw_img_data = self.model.current_configuration.img_model.raw_img_data
        self.mask_data = np.eye(self.raw_img_data.shape[0], self.raw_img_data.shape[1], dtype=bool)
        self.model.mask_model.set_mask(self.mask_data)
        self.current_pattern_x, self.current_pattern_y = \
            self.model.current_configuration.pattern_model.get_pattern().data
        self.controller.widget.integration_widget.cbn_groupbox.setChecked(True)
        # self.controller.integration_controller.image_controller.cbn_groupbox_changed()
        # self.model.current_configuration.pattern_model.get_pattern().recalculate_pattern()
        # self.assertTrue(np.array_equal(self.current_pattern_x,
        #                                self.model.current_configuration.pattern_model.get_pattern()._spectrum_x))
        # self.assertFalse(np.array_equal(self.current_pattern_y,
        #                                 self.model.current_configuration.pattern_model.get_pattern()._spectrum_y))

        QtWidgets.QFileDialog.getSaveFileName = MagicMock(return_value=config_file_path)

        click_button(self.config_widget.save_configuration_btn)
        self.assertTrue(os.path.isfile(config_file_path))

        # self.fail()

    def test_load_configuration(self):
        # sys.excepthook = excepthook
        self.model.working_directories = {'calibration': 'moo', 'mask': 'baa', 'image': '', 'spectrum': ''}
        QtWidgets.QFileDialog.getOpenFileName = MagicMock(return_value=config_file_path)
        click_button(self.config_widget.load_configuration_button)
        saved_working_directories = self.model.working_directories
        saved_working_directories.pop('temp', None)

        self.assertDictEqual(saved_working_directories, working_directories)
        self.assertEqual(self.model.current_configuration.integration_unit, integration_unit)
        self.assertEqual(self.model.use_mask, use_mask)
        self.assertEqual(self.model.transparent_mask, transparent_mask)
        self.assertTrue(np.array_equal(self.model.img_model.raw_img_data, self.raw_img_data))
        self.assertEqual(self.model.current_configuration.autosave_integrated_pattern, autosave_integrated_patterns)
        self.assertEqual(self.model.current_configuration.integrated_patterns_file_formats,
                         integrated_patterns_file_formats)
        self.assertEqual(self.model.current_configuration.img_model.autoprocess, img_autoprocess)
        self.assertTrue(np.array_equal(self.model.mask_model.get_mask(), self.mask_data))
        saved_pyfai_params, _ = self.model.calibration_model.get_calibration_parameter()
        self.assertDictEqual(saved_pyfai_params, pyfai_params)
        self.assertEqual(self.model.phase_model.phases[0].params['pressure'], pressure)
        # self.fail()

    def print_name(self, name):
        print(name)

    def load_phase(self, filename):
        QtWidgets.QFileDialog.getOpenFileNames = MagicMock(return_value=[os.path.join(jcpds_path, filename)])
        click_button(self.controller.widget.integration_widget.phase_add_btn)

# shared settings for save and load tests

config_file_path = os.path.join(data_path, 'test_save_load.hdf5')

working_directories = {'image': data_path,
                       'calibration': data_path,
                       'phase': os.path.join(data_path, 'jcpds'),
                       'overlay': data_path,
                       'mask': data_path,
                       'spectrum': data_path}

integration_unit = 'q_A^-1'
use_mask = True
transparent_mask = True
autosave_integrated_patterns = True
integrated_patterns_file_formats = ['.xy', '.chi']
img_autoprocess = True
test_image_file_name = os.path.join(data_path, 'CeO2_Pilatus1M.tif')
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
