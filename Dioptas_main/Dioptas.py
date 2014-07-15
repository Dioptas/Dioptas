# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2014  Clemens Prescher (clemens.prescher@gmail.com)
# GSECARS, University of Chicago
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <http://www.gnu.org/licenses/>.

# TODO Browsing images in the calibration window
#TODO quick actions to save spectrum
# TODO having an export fit2d parameters btn
# TODO fix this issue with the calibrant not updating etc. (it should update itself everytime you calibrate etc.)\

__author__ = 'Clemens Prescher'
import sys
from PyQt4 import QtGui
import logging
logging.basicConfig(level=logging.INFO)

from Controller.MainController import MainController

if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    from sys import platform as _platform

    if _platform == "linux" or _platform == "linux2":
        app.setStyle('plastique')
    elif _platform == "win32" or _platform == 'cygwin':
        app.setStyle('plastique')
        # possible values:
        # "windows", "motif", "cde", "plastique", "windowsxp", or "macintosh"
    controller = MainController(app)
    app.exec_()
    del app

