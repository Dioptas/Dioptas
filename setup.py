# -*- coding: utf-8 -*-
from setuptools import find_packages, setup
from Cython.Build import cythonize
import versioneer

ext_modules = cythonize('dioptas/model/util/smooth_bruckner_cython.pyx')

version = versioneer.get_version()

if version == "0+unknown":
    version = "0.5.3a"

setup(
    name='dioptas',
    version=version,
    cmdclass=versioneer.get_cmdclass(),
    license='GPLv3',
    author='Clemens Prescher',
    author_email="clemens.prescher@gmail.com",
    url='https://github.com/Dioptas/Dioptas/',
    install_requires=['cython', 'extra_data', 'future', 'h5py', 'hdf5plugin', 'lmfit', 'pandas', 'pycifrw',
                      'python-dateutil', 'pyinstaller', 'pyqt5', 'pyfai', 'pyepics', 'pyopengl', 'pyopengl-accelerate',
                      'pyqtgraph', 'qtpy', 'scikit-image', 'sharedmem', 'watchdog', ],
    description='GUI program for reduction and exploration of 2D X-ray diffraction data',
    classifiers=['Intended Audience :: Science/Research',
                 'Operating System :: OS Independent',
                 'Programming Language :: Python',
                 'Topic :: Scientific/Engineering',
                 ],
    packages=find_packages(),
    package_data={'dioptas': ['resources/style/*',
                              'resources/calibrants/*',
                              'resources/data/*',
                              'resources/icons/*',
                              '__version__'
                              ]
                  },
    scripts=['scripts/dioptas', 'scripts/dioptas_batch'],
    ext_modules=ext_modules,
)
