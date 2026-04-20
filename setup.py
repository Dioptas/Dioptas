# Setup script for C extensions.
# All other metadata is in pyproject.toml.

import numpy as np
from setuptools import Extension, setup

extensions = [
    Extension(
        "dioptas.model.util.mask_plugins._powder_outlier_c",
        sources=["dioptas/model/util/mask_plugins/_powder_outlier_c.c"],
        include_dirs=[np.get_include()],
    ),
]

setup(ext_modules=extensions)
