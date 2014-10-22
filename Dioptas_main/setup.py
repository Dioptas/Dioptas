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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

__author__ = "Clemens Prescher"

import sys
from cx_Freeze import setup, Executable

# Dependencies are automatically detected, but it might need fine tuning.
build_exe_options = {"excludes": ["tcl", "Tcl", "Tk", "ttk", "tkinter", "pyopencl",
                                  "cvxopt", "_gtkagg", "_tkagg", "bsddb", "curses", "email", "pywin.debugger",
                                  "pywin.debugger.dbgcon", "pywin.dialogs", "tcl", "tables",
                                  "Tkconstants", "Tkinter", "zmq", "PySide", "pysideuic", "PyQt4.uic.port_v3"],
                     "includes": ["re", "scipy.sparse.csgraph._validation", "scipy.integrate.vode", "scipy.special",
                                  "scipy.special._ufuncs", "scipy.special._ufuncs_cxx", "scipy.integrate.lsoda",
                                  "skimage._shared.geometry", "matplotlib.backends.backend_macosx"],
                     "include_files": ("Calibrants","Views/UiFiles/images", "Views/UiFiles/Icon"),
                     "create_shared_zip": True,
                     "compressed": False,
                     "icon":"Views/UiFiles/Icon/Icon1_128x128.ico",
}

bdist_mac_options = {}
# GUI applications require a different base on Windows (the default is for a
# console application).
base = None
if sys.platform == "win32":
    base = "Win32GUI"

setup(name="Dioptas",
      version="0.2.2",
      description="Analysis of 2 dimensional X-ray diffraction patterns.",
      options={"build_exe": build_exe_options,
               "bdist_mac": bdist_mac_options},
      executables=[Executable("Dioptas.py",
                              base=base,
                              icon="Views/UiFiles/Icon/Icon1_128x128.ico")])
