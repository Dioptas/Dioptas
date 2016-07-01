# -*- coding: utf8 -*-

import os
import unittest

from mock import MagicMock

from PyQt4 import QtGui, QtCore
from PyQt4.QtTest import QTest

from model.ImgConfiguration import ImgConfigurationManager
from widgets.ConfigurationWidget import ConfigurationWidget

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')
jcpds_path = os.path.join(data_path, 'jcpds')


def click_button(widget):
    QTest.mouseClick(widget, QtCore.Qt.LeftButton)

class ConfigurationWidgetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtGui.QApplication.instance()
        if cls.app is None:
            cls.app = QtGui.QApplication([])

    def setUp(self):
        self.config_widget = ConfigurationWidget()
        self.config_manager = ImgConfigurationManager()

    def test_one_configuration(self):
        self.config_widget.update_configurations(self.config_manager.configurations, 0)
        self.assertEqual(len(self.config_widget.configuration_btns), 1)

    def test_multiple_configurations(self):
        self.config_manager.add_configuration()
        self.config_manager.add_configuration()
        self.config_manager.add_configuration()
        self.config_widget.update_configurations(self.config_manager.configurations, 1)

        self.assertEqual(len(self.config_widget.configuration_btns), 4)
        self.assertFalse(self.config_widget.configuration_btns[0].isChecked())
        self.assertFalse(self.config_widget.configuration_btns[2].isChecked())
        self.assertFalse(self.config_widget.configuration_btns[3].isChecked())
        self.assertTrue(self.config_widget.configuration_btns[1].isChecked())

    def test_configuration_selected_signal(self):
        self.config_widget.configuration_selected = MagicMock()
        self.config_manager.add_configuration()
        self.config_manager.add_configuration()
        self.config_manager.add_configuration()
        self.config_widget.update_configurations(self.config_manager.configurations, 0)

        click_button(self.config_widget.configuration_btns[3])
        self.config_widget.configuration_selected.assert_called_once_with(3)

        self.assertFalse(self.config_widget.configuration_btns[0].isChecked())
        self.assertFalse(self.config_widget.configuration_btns[1].isChecked())
        self.assertFalse(self.config_widget.configuration_btns[2].isChecked())
        self.assertTrue(self.config_widget.configuration_btns[3].isChecked())



