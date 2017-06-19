# Dioptas - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2015  Clemens Prescher (clemens.prescher@gmail.com)
# University of Cologne, Institute for Geology and Mineralogy
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


folder = os.getcwd()

from distutils.sysconfig import get_python_lib
from sys import platform as _platform

site_packages_path = get_python_lib()
import pyFAI
import matplotlib
import lib2to3

pyFAI_path = os.path.dirname(pyFAI.__file__)
matplotlib_path = os.path.dirname(matplotlib.__file__)
lib2to3_path = os.path.dirname(lib2to3.__file__)

extra_datas = [
    ("dioptas/calibrants", "dioptas/calibrants"),
    (os.path.join(pyFAI_path, "resources"), "pyFAI/resources"),
    (os.path.join(pyFAI_path, "utils"), "pyFAI/utils"),
    ("dioptas/widgets/stylesheet.qss", "dioptas/widgets"),
    ("dioptas/widgets/icns/icon.svg", "dioptas/widgets/icns"),
    (os.path.join(lib2to3_path, 'Grammar.txt'), 'lib2to3/'),
    (os.path.join(lib2to3_path, 'PatternGrammar.txt'), 'lib2to3/'),
    ("dioptas/model/util/data/*.json", "dioptas/model/util/data"),
]

binaries = []

if _platform == "darwin":
    extra_datas.extend((
        (os.path.join(os.path.expanduser('~'), '//anaconda/lib/libQtCore.4.dylib'), '.'),
        (os.path.join(os.path.expanduser('~'), '//anaconda/lib/libQtWidgets.4.dylib'), '.'),
        (os.path.join(os.path.expanduser('~'), '//anaconda/lib/libpng16.16.dylib'), '.'),
        (os.path.join(os.path.expanduser('~'), '//anaconda/lib/libQtSvg.4.dylib'), '.'),
        (os.path.join(os.path.expanduser('~'), '//anaconda/lib/libhdf5.10.dylib'), '.'),
        (os.path.join(os.path.expanduser('~'), '//anaconda/lib/libhdf5_hl.10.dylib'), '.'),
    ))
elif _platform == "linux":
    extra_datas.extend((
        (os.path.join(os.path.expanduser('~'), 'anaconda3/lib/libgomp.so.1'), '.'),
    ))

a = Analysis(['Dioptas.py'],
             pathex=[folder],
             binaries=binaries,
             datas=extra_datas,
             hiddenimports=['scipy.special._ufuncs_cxx', 'skimage._shared.geometry'],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)

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
    "IPython",
#   "matplotlib",
#   "mpl-data", #needs to be included
#   "_MEI",
#   "docutils",
#   "pytz",
#   "lib",
   "include",
   "sphinx",
#   ".py",
   "tests",
   "skimage",
   "alabaster",
   "boto",
   "jsonschema",
   "babel",
   "idlelib",
   "requests",
   "qt4_plugins",
   "qt5_plugins"
]

for exclude_data in exclude_datas:
    a.datas = [x for x in a.datas if exclude_data not in x[0]]


platform = ''

if _platform == "linux" or _platform == "linux2":
    platform = "Linux"
    name = "Dioptas"
elif _platform == "win32" or _platform == "cygwin":
    platform = "Win"
    name = "Dioptas.exe"
elif _platform == "darwin":
    platform = "Mac"
    name = "Dioptas"

# checking whether the platform is 64 or 32 bit
if sys.maxsize > 2 ** 32:
    platform += "64"
else:
    platform += "32"

# getting the current version of Dioptas
from dioptas import __version__

pyz = PYZ(a.pure, a.zipped_data,
          cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          exclude_binaries=True,
          name=name,
          debug=False,
          strip=False,
          upx=True,
          console=False,
          icon="dioptas/widgets/icns/icon.ico")

coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               name='Dioptas_{}_{}'.format(platform, __version__))

if _platform == "darwin":
    app = BUNDLE(coll,
                 name='Dioptas_{}.app'.format(__version__),
                 icon='widgets/icns/icon.icns')
