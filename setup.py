# -*- coding: utf8 -*-
from setuptools import find_packages
from numpy.distutils.core import Extension, setup

import versioneer

smooth_bruckner = Extension(
    name='dioptas.model.util.smooth_bruckner',
    sources= ['dioptas/model/util/smooth_bruckner.f95']
)

setup(
    name='dioptas',
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    license='GPLv3',
    author='Clemens Prescher',
    author_email="clemens.prescher@gmail.com",
    url='https://github.com/Dioptas/Dioptas/',
    install_requires=['numpy'],
    description='GUI program for reduction and exploration of 2D X-ray diffraction data',
    classifiers=['Intended Audience :: Science/Research',
                 'Operating System :: OS Independent',
                 'Programming Language :: Python',
                 'Topic :: Scientific/Engineering',
                 ],
    packages=find_packages(),
    package_data={'dioptas': ['calibrants/*',
                              'widgets/stylesheet.qss',
                              'widgets/icns/icon*',
                              'model/util/data/*.json',
                              'model/util/smooth_bruckner.f95']},
    scripts=['scripts/dioptas'],
    ext_modules=[smooth_bruckner]
)
