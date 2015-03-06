# -*- mode: python -*-
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

import os

folder = 'source'

a = Analysis([os.path.join(folder,'Dioptas.py')],
             pathex=['source'],
             hiddenimports=['scipy.special._ufuncs_cxx', 'skimage._shared.geometry'],
             hookspath=None,
             runtime_hooks=None)

import sys
sys.path.append(a.pathex[0])

from controller.MainController import get_version
version = get_version()


##### include mydir in distribution #######
def extra_datas(dest_directory, source_directory):
    def rec_glob(p, files):
        import os
        import glob
        for d in glob.glob(p):
            if os.path.isfile(d):
                files.append(d)
            rec_glob("%s/*" % d, files)
    files = []
    rec_glob("%s/*" % source_directory, files)
    extra_datas = []
    for f in files:
        extra_datas.append((os.path.join(dest_directory, os.path.basename(f)),
                            os.path.join(source_directory, os.path.basename(f)), 'DATA'))
    return extra_datas
###########################################

a.datas += extra_datas('calibrants', 'source/calibrants')
a.datas += [('pyFAI/calibration/__init__.py', 'source/calibrants/__init__.py', 'DATA')]


# remove packages which are not needed Dioptas
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


from sys import platform as _platform
platform = ''

if _platform == "linux" or _platform == "linux2":
    platform = "Linux"
    name = "Dioptas"
elif _platform == "win32" or _platform == "cygwin":
    platform = "Win64"
    name = "Dioptas.exe"
elif _platform == "darwin":
    platform = "Mac64"
    name = "Dioptas"

pyz = PYZ(a.pure)
exe = EXE(pyz,
          a.scripts,
          exclude_binaries=True,
          name=name,
          debug=False,
          strip=None,
          upx=True,
          console=False )


coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=None,
               upx=True,
               name='Dioptas_{}_{}'.format(platform, version))

if _platform == "darwin":
    app = BUNDLE(coll,
                 name='Dioptas_{}.app'.format(version),
                 icon='source/widgets/UiFiles/Icon/icns/icon.icns')
