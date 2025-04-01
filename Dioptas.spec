# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
# Principal author: Clemens Prescher (clemens.prescher@gmail.com)
# Copyright (C) 2014-2019 GSECARS, University of Chicago, USA
# Copyright (C) 2015-2018 Institute for Geology and Mineralogy, University of Cologne, Germany
# Copyright (C) 2019-2020 DESY, Hamburg, Germany
# Copyright (C) 2021-2025 University of Freiburg, Freiburg, Germany
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

block_cipher = None

import sys
import os
from sys import platform as _platform
from PyInstaller.utils.hooks import collect_submodules

pristine_sys_module = list(sys.modules.keys())

folder = os.getcwd()

import PyQt6 # needs to be imported before qt_material
import qt_material
import pyFAI

qt_material_path = os.path.dirname(qt_material.__file__)
pyFAI_path = os.path.dirname(pyFAI.__file__)

extra_datas = [
    ("dioptas/resources", "dioptas/resources"),
    (os.path.join(pyFAI_path, "resources"), "pyFAI/resources"),
    (os.path.join(qt_material_path, "fonts", "roboto"), "qt_material/fonts/roboto"),
]

fabio_hiddenimports = collect_submodules("fabio")
pyqtgraph_hiddenimports = collect_submodules("pyqtgraph")
pyFAI_hiddenimports = collect_submodules("pyFAI")

hiddenimports = fabio_hiddenimports + pyqtgraph_hiddenimports + pyFAI_hiddenimports

a = Analysis(
    ["run.py"],
    pathex=[folder],
    binaries=[],
    datas=extra_datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

# remove packages which are not needed by Dioptas
# a.binaries = [x for x in a.binaries if not x[0].startswith("matplotlib")]
a.binaries = [x for x in a.binaries if not x[0].startswith("zmq")]
a.binaries = [x for x in a.binaries if not x[0].startswith("IPython")]
a.binaries = [x for x in a.binaries if not x[0].startswith("docutils")]
a.binaries = [x for x in a.binaries if not x[0].startswith("pytz")]
a.binaries = [x for x in a.binaries if not x[0].startswith("wx")]
a.binaries = [x for x in a.binaries if not x[0].startswith("libQtWebKit")]
a.binaries = [x for x in a.binaries if not x[0].startswith("libQtDesigner")]
a.binaries = [x for x in a.binaries if not x[0].startswith("PySide")]
a.binaries = [x for x in a.binaries if not x[0].startswith("libtk")]

exclude_datas = [
    "PyQt6/Qt6/translations",
    "PyQt6/Qt6/plugins/imageformats",
]

for exclude_data in exclude_datas:
    a.datas = [x for x in a.datas if exclude_data not in x[0]]

platform = ""

if _platform == "linux" or _platform == "linux2":
    platform = "Linux"
    name = "Dioptas"
elif _platform == "win32" or _platform == "cygwin":
    platform = "Win"
    name = "Dioptas.exe"
elif _platform == "darwin":
    platform = "Mac"
    name = "run_dioptas"

# checking whether the platform is 64 or 32 bit
if sys.maxsize > 2**32:
    platform += "64"
else:
    platform += "32"

# getting the current version of Dioptas
try:
    with open(os.path.join("dioptas", "__version__"), "r") as fp:
        __version__ = fp.readline()
except FileNotFoundError:
    from dioptas import __version__

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

print("@@@ Datas @@@")
print(a.datas)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name=name,
    debug=False,
    strip=False,
    upx=True,
    console=False,
    icon="dioptas/resources/icons/icon.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name="Dioptas_{}_{}".format(platform, __version__),
)

if _platform == "darwin":
    app = BUNDLE(
        coll,
        name="Dioptas_{}.app".format(__version__),
        icon="dioptas/resources/icons/icon.icns",
    )
