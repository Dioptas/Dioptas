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

import weakref
import pytest
from qtpy import QtCore, QtWidgets
from qtpy.QtTest import QTest

from dioptas.controller.MainController import MainController


@pytest.fixture(scope="session")
def qapp():
    """Fixture ensuring QApplication is instanciated"""
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    try:
        yield app
    finally:
        if app is not None:
            app.closeAllWindows()


@pytest.fixture
def qWidgetFactory(qapp):
    """QWidget factory as fixture

    This fixture provides a function taking a QWidget subclass as argument
    which returns an instance of this QWidget making sure it is shown first
    and destroyed once the test is done.
    """
    widgets = set()

    def createWidget(cls, *args, **kwargs):
        widget = cls(*args, **kwargs)
        widget.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        widget.show()
        QTest.qWaitForWindowExposed(widget)
        widgets.add(widget)
        return weakref.proxy(widget)

    try:
        yield createWidget
    finally:
        for widget in widgets:
            widget.close()
        qapp.processEvents()


@pytest.fixture
def main_controller(qapp):
    """Fixture providing a MainController instance"""
    controller = MainController(use_settings=False)
    controller.show_window()
    controller.widget.setAttribute(QtCore.Qt.WA_DeleteOnClose)
    QTest.qWaitForWindowExposed(controller.widget)
    controller.widget.activateWindow()
    controller.widget.raise_()
    try:
        yield controller
    finally:
        controller.widget.close()