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

block_cipher = None

import sys
pristine_sys_module = list(sys.modules.keys())
import os

folder = os.getcwd()

from distutils.sysconfig import get_python_lib
from sys import platform as _platform

site_packages_path = get_python_lib()


def get_libs(module_name, pristine=None, sieve=True):
    """Track new modules which were imported
    :param module_name: name of the module
    :param pristine: list of modules previously loaded. By default, use all newly loaded
    :param sieve: set to a string to sieve out on that string, module_name by default
    :return: list of newly loaded modules
    """
    if pristine is None:
        pristine = list(sys.modules.keys())
    __import__(module_name)
    new = [i for i in sys.modules if i not in pristine]
    if sieve:
        if isinstance(sieve, str):
            module = sieve
        else:
            module = module_name
        new = [i for i in new if i.startswith(module)]
    return new


binaries = []

fabio_hiddenimports = get_libs("fabio")
pyFAI_hiddenimports = get_libs("pyFAI.azimuthalIntegrator", sieve="pyFAI")
pyqtgraph_hiddenimports = get_libs("pyqtgraph", sieve="pyqtgraph")

pyqtgraph_hiddenimports += [
    "pyqtgraph.graphicsItems.ViewBox.axisCtrlTemplate_pyqt5",
    "pyqtgraph.graphicsItems.PlotItem.plotConfigTemplate_pyqt5",
    "pyqtgraph.imageview.ImageViewTemplate_pyqt5"
]

import pyFAI
import matplotlib
import lib2to3
import qt_material

pyFAI_path = os.path.dirname(pyFAI.__file__)
matplotlib_path = os.path.dirname(matplotlib.__file__)
lib2to3_path = os.path.dirname(lib2to3.__file__)
qt_material_path = os.path.dirname(qt_material.__file__)

extra_datas = [
    ("dioptas/resources", "dioptas/resources"),
    (os.path.join(pyFAI_path, "resources"), "pyFAI/resources"),
    (os.path.join(pyFAI_path, "utils"), "pyFAI/utils"),
    (os.path.join(lib2to3_path, 'Grammar.txt'), 'lib2to3/'),
    (os.path.join(lib2to3_path, 'PatternGrammar.txt'), 'lib2to3/'),
    (os.path.join(qt_material_path, 'fonts'), os.path.join('qt_material', 'fonts')),
    (os.path.join(site_packages_path, 'hdf5plugin', 'plugins'), os.path.join('hdf5plugin', 'plugins')),
]

a = Analysis(['run.py'],
             pathex=[folder],
             binaries=binaries,
             datas=extra_datas,
             hiddenimports=['scipy.special._ufuncs_cxx', 'scipy._lib.messagestream', 'scipy.special.cython_special',
                            'skimage._shared.geometry', 'h5py.defs', 'h5py.utils', 'h5py.h5ac', 'h5py', 'h5py._proxy',
                            'pywt._extensions._cwt', 'pkg_resources.py2_warn'] +
                           fabio_hiddenimports + pyqtgraph_hiddenimports + pyFAI_hiddenimports,
             hookspath=[],
             runtime_hooks=[],
             excludes=['PyQt4', 'PySide', 'pyepics'],
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
    name = "run_dioptas"

# checking whether the platform is 64 or 32 bit
if sys.maxsize > 2 ** 32:
    platform += "64"
else:
    platform += "32"

# getting the current version of Dioptas
try:
    with open(os.path.join('dioptas', '__version__'), 'r') as fp:
        __version__ = fp.readline()
except FileNotFoundError:
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
          icon="dioptas/resources/icons/icon.ico")

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
                 icon='dioptas/resources/icons/icon.icns')
