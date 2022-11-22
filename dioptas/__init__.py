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

from __future__ import absolute_import

import sys
from sys import platform as _platform
from qtpy import QtWidgets, QtCore

try:
    from .version import __version__
except ModuleNotFoundError:
    from setuptools_scm import get_version

    __version__ = get_version(root='..', relative_to=__file__)

from .paths import resources_path, calibrants_path, icons_path, data_path, style_path
from .excepthook import excepthook
from ._desktop_shortcuts import make_shortcut
from .controller.MainController import MainController

# Enable scaling for high DPI displays
if _platform != "linux" or _platform != "linux2":  # does not work correctly on linux
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)


def main():
    app = QtWidgets.QApplication([])
    sys.excepthook = excepthook
    print("Dioptas {}".format(__version__))

    if _platform == "linux" or _platform == "linux2" or _platform == "win32" or _platform == 'cygwin':
        app.setStyle('plastique')

    if len(sys.argv) == 1:  # normal start
        controller = MainController()
        controller.show_window()
        app.exec_()
    else:  # with command line arguments
        if sys.argv[1] == 'test':
            controller = MainController(use_settings=False)
            controller.show_window()
        elif sys.argv[1].startswith('makeshortcut'):
            make_shortcut('Dioptas', 'dioptas.py', description='Dioptas 2D XRD {}'.format(__version__),
                          icon_path=icons_path, icon='icon')
    del app

