# -*- coding: utf-8 -*-
from setuptools import find_packages
from numpy.distutils.core import Extension, setup

import versioneer

with_bruckner_cython = True
with_bruckner_f95 = False

ext_modules = []
if with_bruckner_cython:
    from Cython.Build import cythonize

    ext_modules = cythonize('dioptas/model/util/smooth_bruckner_cython.pyx')

if with_bruckner_f95:
    ext_modules.append(Extension(
        name='dioptas.model.util.smooth_bruckner',
        sources=['dioptas/model/util/smooth_bruckner.f95'])
    )

setup(
    name='dioptas',
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    license='GPLv3',
    author='Clemens Prescher',
    author_email="clemens.prescher@gmail.com",
    url='https://github.com/Dioptas/Dioptas/',
    install_requires=['numpy', 'cython'],
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
                              ]
                  },
    scripts=['scripts/dioptas'],
    ext_modules=ext_modules,
)
