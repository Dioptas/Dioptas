# -*- coding: utf8 -*-

from setuptools import setup, find_packages

import versioneer

setup(
    name='glassure',
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    license='GPLv3',
    author='Clemens Prescher',
    author_email="clemens.prescher@gmail.com",
    url='https://github.com/Dioptas/Dioptas/',
    install_requires=['numpy', 'scipy', 'lmfit', 'pyqtgraph', 'future', 'pycifrw', 'fabio', 'pyfai'],
    test_requires=['mock'],
    description='GUI program for reduction and exploration of 2D X-ray diffraction data',
    classifiers=['Intended Audience :: Science/Research',
                 'Operating System :: OS Independent',
                 'Programming Language :: Python',
                 'Topic :: Scientific/Engineering',
                 ],
    packages=find_packages(),
    package_data={'dioptas': ['calibrants/*',
                              'widgets/stylesheet.qss',
                              'model/util/data/*.json']}
)
