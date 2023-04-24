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

import unittest
from qtpy import QtWidgets, QtCore
from qtpy.QtTest import QTest
import os
import shutil

unittest_data_path = os.path.join(os.path.dirname(__file__), 'data')


class QtTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance()
        if cls.app is None:
            cls.app = QtWidgets.QApplication([])


def delete_if_exists(data_path):
    if os.path.exists(data_path):
        os.remove(data_path)


def delete_folder_if_exists(data_path):
    if os.path.exists(data_path):
        shutil.rmtree(data_path)


def click_button(widget):
    QTest.mouseClick(widget, QtCore.Qt.LeftButton)


def click_checkbox(checkbox_widget):
    QTest.mouseClick(checkbox_widget, QtCore.Qt.LeftButton,
                     pos=QtCore.QPoint(2, int(checkbox_widget.height() / 2.0)))


def enter_value_into_text_field(text_field, value):
    text_field.setText('')
    QTest.keyClicks(text_field, str(value))
    QTest.keyPress(text_field, QtCore.Qt.Key_Enter)
    QtWidgets.QApplication.processEvents()


class MockMouseEvent:
    def __init__(self, key=None, diff=None):
        self.key_value = key
        self.diff = diff

        class TestCoord:
            def x(self):
                return 100

            def y(self):
                return 100

        self.coord = TestCoord()

    def key(self):
        return self.key_value

    def x(self):
        return self.diff

    def angleDelta(self):
        return self.coord

    def modifiers(self):
        return QtCore.Qt.CoverWindow

    def button(self):
        return QtCore.Qt.CoverWindow
