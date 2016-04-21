# -*- coding: utf8 -*-

import gc
import os
import unittest

import mock
import numpy as np
from PyQt4 import QtGui, QtCore
from PyQt4.QtTest import QTest

from controller.integration import IntegrationController
from model import ImgModel, CalibrationModel, MaskModel, PatternModel, PhaseModel
from widgets.integration import IntegrationWidget

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')


class IntegrationControllerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtGui.QApplication([])

    @classmethod
    def tearDownClass(cls):
        cls.app.quit()
        cls.app.deleteLater()

    def setUp(self):
        self.img_model = ImgModel()
        self.mask_model = MaskModel()
        self.spectrum_model = PatternModel()

        # setting up the calibration model but mocking the integration for speed
        self.calibration_model = CalibrationModel(self.img_model)
        self.calibration_model.num_points = 1000
        dummy_x = np.linspace(0, 25, 1000)
        dummy_y = np.sin(dummy_x)
        self.calibration_model.integrate_1d = mock.Mock(return_value=(dummy_x, dummy_y))

        self.phase_model = PhaseModel()
        self.widget = IntegrationWidget()
        self.integration_controller = IntegrationController({'spectrum': data_path},
                                                            widget=self.widget,
                                                            img_model=self.img_model,
                                                            mask_model=self.mask_model,
                                                            calibration_model=self.calibration_model,
                                                            spectrum_model=self.spectrum_model,
                                                            phase_model=self.phase_model)
        self.image_controller = self.integration_controller.image_controller
        self.calibration_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.poni'))
        self.img_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.tif'))

    def tearDown(self):
        del self.calibration_model
        del self.img_model
        del self.phase_model
        del self.widget
        del self.integration_controller
        del self.image_controller
        gc.collect()

    def _setup_batch_integration(self):
        # setting up filenames and working directories
        filenames = ['image_001.tif', 'image_002.tif']
        input_filenames = [os.path.join(data_path, f) for f in filenames]
        working_dir = os.path.join(data_path, 'out')
        if not os.path.exists(working_dir):
            os.mkdir(working_dir)
        self.image_controller.working_dir['spectrum'] = os.path.join(working_dir)
        self.widget.spec_autocreate_cb.setChecked(True)

        return filenames, input_filenames, working_dir

    def test_batch_integration_of_multiple_files(self):
        filenames, input_filenames, working_dir = self._setup_batch_integration()
        self.image_controller.load_file(input_filenames)

        for filename in filenames:
            filename = filename.split('.')[0] + '.xy'
            filepath = os.path.join(working_dir, filename)
            self.assertTrue(os.path.exists(filepath))
            os.remove(filepath)
        # cleaning up
        os.rmdir(working_dir)

    def test_batch_integration_with_automatic_background_subtraction(self):
        filenames, input_filenames, working_dir = self._setup_batch_integration()
        self.widget.bkg_spectrum_gb.setChecked(True)
        self.image_controller.load_file(input_filenames)

        self.assertTrue(os.path.exists(os.path.join(working_dir, 'bkg_subtracted')))

        # check if two kind of files have been saved
        for filename in filenames:
            filename = filename.split('.')[0] + '.xy'

            orig_filepath = os.path.join(working_dir, filename)
            self.assertTrue(os.path.exists(orig_filepath))
            os.remove(orig_filepath)

            bkg_subtracted_filepath = os.path.join(working_dir, 'bkg_subtracted', filename)
            self.assertTrue(os.path.exists(bkg_subtracted_filepath))
            os.remove(bkg_subtracted_filepath)

        os.rmdir(os.path.join(working_dir, 'bkg_subtracted'))
        os.rmdir(working_dir)


    def test_switching_to_cake_mode_without_having_clicked_the_image_before(self):
        QTest.mouseClick(self.widget.img_mode_btn, QtCore.Qt.LeftButton)
        QTest.mouseClick(self.widget.img_mode_btn, QtCore.Qt.LeftButton)
