# -*- coding: utf8 -*-

import os

from ..utility import QtTest
from mock import MagicMock

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtTest import QTest

from ...widgets.integration import IntegrationWidget
from ...controller.integration.PatternController import PatternController
from ...model.DioptasModel import DioptasModel

unittest_data_path = os.path.join(os.path.dirname(__file__), '../data')


def click_button(widget):
    QTest.mouseClick(widget, QtCore.Qt.LeftButton)


def click_checkbox(checkbox_widget):
    QTest.mouseClick(checkbox_widget, QtCore.Qt.LeftButton,
                     pos=QtCore.QPoint(2, checkbox_widget.height() / 2.0))


class PatternControllerTest(QtTest):
    def setUp(self):
        self.working_dir = {'image': '', 'spectrum': ''}

        self.widget = IntegrationWidget()
        self.model = DioptasModel()

        self.controller = PatternController(
            working_dir=self.working_dir,
            widget=self.widget,
            dioptas_model=self.model)

    def tearDown(self):
        if os.path.exists(os.path.join(unittest_data_path, "test.xy")):
            os.remove(os.path.join(unittest_data_path, "test.xy"))

    def test_configuration_selected_changes_active_unit_btn(self):
        self.model.add_configuration()
        click_button(self.widget.spec_q_btn)
        self.model.add_configuration()
        click_button(self.widget.spec_d_btn)

        self.model.select_configuration(0)
        self.assertTrue(self.widget.spec_tth_btn.isChecked())
        self.assertFalse(self.widget.spec_q_btn.isChecked())
        self.assertFalse(self.widget.spec_d_btn.isChecked())

        self.assertEqual(self.widget.pattern_widget.spectrum_plot.getAxis('bottom').labelString(),
                         u"<span style='color: #ffffff'>2θ (°)</span>")

        self.model.select_configuration(1)
        self.assertTrue(self.widget.spec_q_btn.isChecked())

        self.assertEqual(self.widget.pattern_widget.spectrum_plot.getAxis('bottom').labelString(),
                         "<span style='color: #ffffff'>Q (A<sup>-1</sup>)</span>")

        self.model.select_configuration(2)
        self.assertTrue(self.widget.spec_d_btn.isChecked())
        self.assertEqual(self.widget.pattern_widget.spectrum_plot.getAxis('bottom').labelString(),
                         u"<span style='color: #ffffff'>d (A)</span>")

    def test_save_pattern_without_background(self):
        QtWidgets.QFileDialog.getSaveFileName = MagicMock(return_value=os.path.join(unittest_data_path, "test.xy"))
        self.model.calibration_model.create_file_header = MagicMock(return_value="None")
        click_button(self.widget.qa_save_spectrum_btn)

        self.assertTrue(os.path.exists(os.path.join(unittest_data_path, "test.xy")))
