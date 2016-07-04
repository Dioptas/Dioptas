# -*- coding: utf8 -*-

import os
import unittest

from mock import MagicMock

from PyQt4 import QtGui, QtCore
from PyQt4.QtTest import QTest

from controller.ConfigurationController import ConfigurationController
from model.ImgConfiguration import ImgConfigurationManager
from widgets.ConfigurationWidget import ConfigurationWidget

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')
jcpds_path = os.path.join(data_path, 'jcpds')


def click_button(widget):
    QTest.mouseClick(widget, QtCore.Qt.LeftButton)


class ConfigurationControllerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtGui.QApplication.instance()
        if cls.app is None:
            cls.app = QtGui.QApplication([])

    def setUp(self):
        self.config_widget = ConfigurationWidget()
        self.config_manager = ImgConfigurationManager()
        self.config_controller = ConfigurationController(
            configuration_widget=self.config_widget,
            configuration_manager=self.config_manager,
            controllers=[]
        )

    def test_initial_configuration_display(self):
        self.assertEqual(len(self.config_widget.configuration_btns), 1)

    def test_adding_configurations(self):
        click_button(self.config_widget.add_configuration_btn)
        self.assertEqual(len(self.config_manager.configurations), 2)
        self.assertEqual(len(self.config_widget.configuration_btns), 2)
        self.assertTrue(self.config_widget.configuration_btns[1].isChecked())

        click_button(self.config_widget.add_configuration_btn)
        self.assertEqual(len(self.config_manager.configurations), 3)
        self.assertEqual(len(self.config_widget.configuration_btns), 3)
        self.assertTrue(self.config_widget.configuration_btns[2].isChecked())

        self.assertEqual(self.config_widget.configuration_btns[0].text(), "1")
        self.assertEqual(self.config_widget.configuration_btns[1].text(), "2")
        self.assertEqual(self.config_widget.configuration_btns[2].text(), "3")

    def test_selecting_configuration(self):
        click_button(self.config_widget.add_configuration_btn)
        click_button(self.config_widget.add_configuration_btn)
        click_button(self.config_widget.add_configuration_btn)

        self.assertEqual(self.config_manager.current_configuration, 3)
        self.assertTrue(self.config_widget.configuration_btns[-1].isChecked())

        click_button(self.config_widget.configuration_btns[0])
        self.assertEqual(self.config_manager.current_configuration, 0)

    def test_remove_last_configuration(self):
        click_button(self.config_widget.add_configuration_btn)
        click_button(self.config_widget.add_configuration_btn)
        click_button(self.config_widget.add_configuration_btn)

        self.assertEqual(self.config_manager.current_configuration, 3)
        self.assertTrue(self.config_widget.configuration_btns[3].isChecked())

        click_button(self.config_widget.remove_configuration_btn)

        self.assertEqual(self.config_manager.current_configuration, 2)
        self.assertTrue(self.config_widget.configuration_btns[2].isChecked())

    def test_remove_first_configuration(self):
        click_button(self.config_widget.add_configuration_btn)
        click_button(self.config_widget.add_configuration_btn)
        click_button(self.config_widget.add_configuration_btn)

        click_button(self.config_widget.configuration_btns[0])
        click_button(self.config_widget.remove_configuration_btn)

        self.assertEqual(self.config_manager.current_configuration, 0)
        self.assertTrue(self.config_widget.configuration_btns[0].isChecked())
        self.assertEqual(len(self.config_manager.configurations), 3)

        self.assertEqual(self.config_widget.configuration_btns[0].text(), "1")
        self.assertEqual(self.config_widget.configuration_btns[1].text(), "2")
        self.assertEqual(self.config_widget.configuration_btns[2].text(), "3")

    def test_remove_inbetween_configuration(self):
        click_button(self.config_widget.add_configuration_btn)
        click_button(self.config_widget.add_configuration_btn)
        click_button(self.config_widget.add_configuration_btn)

        click_button(self.config_widget.configuration_btns[1])
        click_button(self.config_widget.remove_configuration_btn)

        self.assertEqual(self.config_manager.current_configuration, 1)
        self.assertTrue(self.config_widget.configuration_btns[1].isChecked())
        self.assertEqual(len(self.config_manager.configurations), 3)

        self.assertEqual(self.config_widget.configuration_btns[0].text(), "1")
        self.assertEqual(self.config_widget.configuration_btns[1].text(), "2")
        self.assertEqual(self.config_widget.configuration_btns[2].text(), "3")

    def test_changing_models_for_controller(self):
        controller1 = DummyController()
        controller2 = DummyController()

        self.config_controller = ConfigurationController(
            configuration_widget=self.config_widget,
            configuration_manager=self.config_manager,
            controllers=[controller1, controller2]
        )

        click_button(self.config_widget.add_configuration_btn)

        self.assertIs(controller1.img_model, self.config_manager.img_model)
        self.assertIs(controller2.img_model, self.config_manager.img_model)

        self.assertIs(controller1.mask_model, self.config_manager.mask_model)
        self.assertIs(controller2.mask_model, self.config_manager.mask_model)

        self.assertIs(controller1.calibration_model, self.config_manager.calibration_model)
        self.assertIs(controller2.calibration_model, self.config_manager.calibration_model)

        click_button(self.config_widget.configuration_btns[0])

        self.assertIs(controller1.img_model, self.config_manager.img_model)
        self.assertIs(controller2.img_model, self.config_manager.img_model)

        self.assertIs(controller1.mask_model, self.config_manager.mask_model)
        self.assertIs(controller2.mask_model, self.config_manager.mask_model)

        self.assertIs(controller1.calibration_model, self.config_manager.calibration_model)
        self.assertIs(controller2.calibration_model, self.config_manager.calibration_model)

        click_button(self.config_widget.remove_configuration_btn)

        self.assertIs(controller1.img_model, self.config_manager.img_model)
        self.assertIs(controller2.img_model, self.config_manager.img_model)

        self.assertIs(controller1.mask_model, self.config_manager.mask_model)
        self.assertIs(controller2.mask_model, self.config_manager.mask_model)

        self.assertIs(controller1.calibration_model, self.config_manager.calibration_model)
        self.assertIs(controller2.calibration_model, self.config_manager.calibration_model)


class DummyController(object):
    def __init__(self):
        super(DummyController, self).__init__()
        self.img_model = None
        self.mask_model = None
        self.calibration_model = None
