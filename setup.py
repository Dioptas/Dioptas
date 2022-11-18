# -*- coding: utf-8 -*-
import setuptools
from Cython.Build import cythonize
ext_modules = cythonize('dioptas/model/util/smooth_bruckner_cython.pyx')

if __name__ == "__main__":
    setuptools.setup(ext_modules=ext_modules)
