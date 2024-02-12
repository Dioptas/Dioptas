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

import os
import sys
from sys import platform as _platform

# If QT_API is not set, use PyQt6 by default
if "QT_API" not in os.environ:
    try:
        import PyQt6.QtCore
    except ImportError:
        pass

from qtpy import QtWidgets
from qt_material import apply_stylesheet

__version__ = "0.5.9"

from .paths import resources_path, calibrants_path, icons_path, data_path, style_path
from .excepthook import excepthook
from ._desktop_shortcuts import make_shortcut
from .controller.MainController import MainController


theme_path = os.path.join(style_path, "dark_orange.xml")
qss_path = os.path.join(style_path, "qt_material.css")

def main():
    app = QtWidgets.QApplication([])

    apply_stylesheet(
        app,
        theme=theme_path,
        css_file=qss_path,
        extra={"density_scale": -2},
    )
    # sys.excepthook = excepthook
    print("Dioptas {}".format(__version__))

    if len(sys.argv) == 1:  # normal start
        controller = MainController()
        controller.show_window()
        app.exec_()
    else:  # with command line arguments
        if sys.argv[1] == "test":
            controller = MainController(use_settings=False)
            controller.show_window()
        elif sys.argv[1].startswith("makeshortcut"):
            make_shortcut(
                "Dioptas",
                "dioptas.py",
                description="Dioptas 2D XRD {}".format(__version__),
                icon_path=icons_path,
                icon="icon",
            )
    del app
