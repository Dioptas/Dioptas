# -*- coding: utf8 -*-

import os, sys

from ..utility import QtTest, click_button, delete_if_exists
from mock import MagicMock

from qtpy import QtWidgets

import numpy as np

from ...widgets.integration import IntegrationWidget
from ...controller.integration.PatternController import PatternController
from ...model.DioptasModel import DioptasModel

data_path = os.path.join(os.path.dirname(__file__), '../data')
from ..ehook import excepthook


class PatternControllerTest(QtTest):
    def setUp(self):
        self.working_dir = {'image': '', 'pattern': ''}
        sys.excepthook = excepthook

        self.widget = IntegrationWidget()
        self.model = DioptasModel()

        self.controller = PatternController(
            working_dir=self.working_dir,
            widget=self.widget,
            dioptas_model=self.model)

    def tearDown(self):
        delete_if_exists(os.path.join(data_path, "test.xy"))

    def test_configuration_selected_changes_active_unit_btn(self):
        self.model.calibration_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.poni'))
        self.model.img_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.tif'))

        self.model.add_configuration()
        click_button(self.widget.pattern_q_btn)

        self.model.add_configuration()
        click_button(self.widget.pattern_d_btn)

        self.model.select_configuration(0)
        self.assertTrue(self.widget.pattern_tth_btn.isChecked())
        self.assertFalse(self.widget.pattern_q_btn.isChecked())
        self.assertFalse(self.widget.pattern_d_btn.isChecked())

        self.assertEqual(self.widget.pattern_widget.pattern_plot.getAxis('bottom').labelString(),
                         u"<span style='color: #ffffff'>2θ (°)</span>")

        self.model.select_configuration(1)
        self.assertTrue(self.widget.pattern_q_btn.isChecked())

        self.assertEqual(self.widget.pattern_widget.pattern_plot.getAxis('bottom').labelString(),
                         "<span style='color: #ffffff'>Q (A<sup>-1</sup>)</span>")

        self.model.select_configuration(2)
        self.assertTrue(self.widget.pattern_d_btn.isChecked())
        self.assertEqual(self.widget.pattern_widget.pattern_plot.getAxis('bottom').labelString(),
                         u"<span style='color: #ffffff'>d (kA)</span>")

    def test_save_pattern_without_background(self):
        QtWidgets.QFileDialog.getSaveFileName = MagicMock(return_value=os.path.join(data_path, "test.xy"))
        self.model.calibration_model.create_file_header = MagicMock(return_value="None")
        click_button(self.widget.qa_save_pattern_btn)

        self.assertTrue(os.path.exists(os.path.join(data_path, "test.xy")))

    def test_save_and_load_fxye_pattern(self):
        QtWidgets.QFileDialog.getSaveFileName = MagicMock(return_value=os.path.join(data_path, "test.fxye"))
        self.model.calibration_model.create_file_header = MagicMock(return_value="None")
        self.model.current_configuration.integration_unit = '2th_deg'
        self.model.calibration_model.pattern_geometry.wavelength = 0.31E-10
        old_data = self.model.pattern_model.pattern.data

        click_button(self.widget.qa_save_pattern_btn)
        self.assertTrue(os.path.exists(os.path.join(data_path, "test.fxye")))

        QtWidgets.QFileDialog.getOpenFileName = MagicMock(return_value=os.path.join(data_path, "test.fxye"))
        click_button(self.widget.pattern_load_btn)
        new_data = self.model.pattern_model.pattern.data
        self.assertTrue(np.allclose(old_data, new_data, 1e-5))
