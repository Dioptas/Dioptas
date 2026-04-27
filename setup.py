# Setup script for C extensions.
# All other metadata is in pyproject.toml.

import os
import sys

import numpy as np
from setuptools import Extension, setup


def _openmp_flags():
    """Detect OpenMP availability and return (compile_flags, link_flags)."""
    if sys.platform == "darwin":
        # macOS: check for Homebrew libomp
        for prefix in ["/opt/homebrew/opt/libomp", "/usr/local/opt/libomp"]:
            if os.path.isdir(prefix):
                return (
                    ["-Xpreprocessor", "-fopenmp", f"-I{prefix}/include"],
                    ["-L{}/lib".format(prefix), "-lomp"],
                )
        return [], []
    elif sys.platform == "win32":
        return ["/openmp"], []
    else:
        # Linux and others
        return ["-fopenmp"], ["-fopenmp"]


omp_cflags, omp_ldflags = _openmp_flags()

extensions = [
    Extension(
        "dioptas.model.util.mask_plugins._powder_outlier_c",
        sources=["dioptas/model/util/mask_plugins/_powder_outlier_c.c"],
        include_dirs=[np.get_include()],
        extra_compile_args=["-O3"] + omp_cflags,
        extra_link_args=omp_ldflags,
    ),
]

setup(ext_modules=extensions)
