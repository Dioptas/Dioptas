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
site_packages_path = get_python_lib()

extra_datas = [
    (os.path.join(site_packages_path, "pyFAI/calibration"), "pyFAI/calibration"),
    (os.path.join(site_packages_path, "pymatgen/core/*.json"), "pymatgen/core"),
    (os.path.join(site_packages_path, 'pymatgen/symmetry/symm_data.yaml'), "pymatgen/symmetry"),
    (os.path.join(site_packages_path, 'pymatgen/analysis/diffraction/atomic_scattering_params.json'),
     "pymatgen/analysis/diffraction"),
]

a = Analysis(['Dioptas.py'],
             pathex=[folder],
             binaries=None,
             datas=extra_datas,
             hiddenimports=['scipy.special._ufuncs_cxx', 'skimage._shared.geometry'],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)

# remove packages which are not needed by Dioptas
a.binaries = [x for x in a.binaries if not x[0].startswith("matplotlib")]
a.binaries = [x for x in a.binaries if not x[0].startswith("zmq")]
a.binaries = [x for x in a.binaries if not x[0].startswith("IPython")]
a.binaries = [x for x in a.binaries if not x[0].startswith("docutils")]
a.binaries = [x for x in a.binaries if not x[0].startswith("pytz")]
a.binaries = [x for x in a.binaries if not x[0].startswith("wx")]
a.binaries = [x for x in a.binaries if not x[0].startswith("libQtWebKit")]
a.binaries = [x for x in a.binaries if not x[0].startswith("libQtDesigner")]
a.binaries = [x for x in a.binaries if not x[0].startswith("PySide")]
a.binaries = [x for x in a.binaries if not x[0].startswith("libtk")]


a.datas = [x for x in a.datas if not "IPython" in x[0]]
a.datas = [x for x in a.datas if not "matplotlib" in x[0]]
a.datas = [x for x in a.datas if not "mpl-data" in x[0]]
a.datas = [x for x in a.datas if not "_MEI" in x[0]]
a.datas = [x for x in a.datas if not "docutils" in x[0]]
a.datas = [x for x in a.datas if not "pytz" in x[0]]
a.datas = [x for x in a.datas if not "lib{}".format(os.path.sep) in x[0]]
a.datas = [x for x in a.datas if not "include" in x[0]]
a.datas = [x for x in a.datas if not "sphinx" in x[0]]

from sys import platform as _platform
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

# checking wether the platform is 64 or 32 bit
if sys.maxsize > 2**32:
    platform+="64"
else:
    platform+="32"

# getting the current version of Dioptas
from controller.MainController import get_version
version = get_version()


pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          exclude_binaries=True,
          name=name,
          debug=False,
          strip=False,
          upx=True,
          console=False )

coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               name='Dioptas_{}_{}'.format(platform, version))

if _platform == "darwin":
    app = BUNDLE(coll,
                 name='Dioptas_{}.app'.format(version),
                 icon='dioptas/widgets/UiFiles/Icon/icns/icon.icns')
