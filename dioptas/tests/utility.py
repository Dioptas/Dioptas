# -*- coding: utf8 -*-

import unittest
from qtpy import QtWidgets, QtCore
from qtpy.QtTest import QTest
import os


class QtTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance()
        if cls.app is None:
            cls.app = QtWidgets.QApplication([])


def delete_if_exists(data_path):
    if os.path.exists(data_path):
        os.remove(data_path)


def click_button(widget):
    QTest.mouseClick(widget, QtCore.Qt.LeftButton)


def click_checkbox(checkbox_widget):
    QTest.mouseClick(checkbox_widget, QtCore.Qt.LeftButton,
                     pos=QtCore.QPoint(2, checkbox_widget.height() / 2.0))
