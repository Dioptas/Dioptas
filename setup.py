# Setup script for C extensions.
# All other metadata is in pyproject.toml.

import os
import sys

import numpy as np
from setuptools import Extension, setup
from setuptools.command.build_ext import build_ext


def _openmp_flags():
    """Detect OpenMP availability and return (compile_flags, link_flags).

    Set DIOPTAS_NO_OPENMP=1 to disable OpenMP (e.g., for PyInstaller builds
    where the OpenMP runtime library would need to be bundled separately).
    """
    if os.environ.get("DIOPTAS_NO_OPENMP", ""):
        return [], []

    if sys.platform == "darwin":
        # macOS: check for Homebrew libomp
        for prefix in ["/opt/homebrew/opt/libomp", "/usr/local/opt/libomp"]:
            if os.path.isdir(prefix):
                return (
                    ["-Xpreprocessor", "-fopenmp", f"-I{prefix}/include"],
                    [f"-L{prefix}/lib", "-lomp"],
                )
        return [], []
    elif sys.platform == "win32":
        return ["/openmp"], []
    else:
        # Linux and others
        return ["-fopenmp"], ["-fopenmp"]


omp_cflags, omp_ldflags = _openmp_flags()

# MSVC already adds /O2 in release builds and rejects "-O3" with a warning,
# so only pass the GCC/Clang optimization flag on non-Windows platforms.
optimize_cflags = [] if sys.platform == "win32" else ["-O3"]

extensions = [
    Extension(
        "dioptas.model.util.mask_plugins._powder_outlier_c",
        sources=["dioptas/model/util/mask_plugins/_powder_outlier_c.c"],
        include_dirs=[np.get_include()],
        extra_compile_args=optimize_cflags + omp_cflags,
        extra_link_args=omp_ldflags,
    ),
]


class OptionalBuildExt(build_ext):
    """Build C extensions, falling back to a pure-Python install on failure.

    The Spot Mask plugin has a NumPy fallback (see
    dioptas/model/util/mask_plugins/powder_outlier.py), so users on
    platforms without a working C toolchain can still ``pip install dioptas``
    and use a slower implementation rather than failing outright.

    Set ``DIOPTAS_REQUIRE_C_EXT=1`` to make a build failure fatal — used by
    CI when producing wheels and PyInstaller bundles that *must* include the
    fast path.
    """

    def run(self):
        try:
            super().run()
        except Exception as exc:
            if os.environ.get("DIOPTAS_REQUIRE_C_EXT"):
                raise
            print(
                f"WARNING: C extension build skipped ({exc}); "
                "the Spot Mask plugin will fall back to a slower NumPy implementation."
            )

    def build_extension(self, ext):
        try:
            super().build_extension(ext)
        except Exception as exc:
            if os.environ.get("DIOPTAS_REQUIRE_C_EXT"):
                raise
            print(f"WARNING: skipping extension {ext.name}: {exc}")


setup(ext_modules=extensions, cmdclass={"build_ext": OptionalBuildExt})
