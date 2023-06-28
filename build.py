import shutil
from pathlib import Path


def build_cython_extensions():
    from Cython.Build import build_ext, cythonize  # pyright: ignore [reportMissingImports]
    from setuptools.dist import Distribution

    ext_modules = cythonize('dioptas/model/util/smooth_bruckner_cython.pyx')
    dist = Distribution({"ext_modules": ext_modules})
    cmd = build_ext(dist)
    cmd.ensure_finalized()
    cmd.run()

    for output in cmd.get_outputs():
        output = Path(output)
        relative_extension = output.relative_to(cmd.build_lib)
        shutil.copyfile(output, relative_extension)


build_cython_extensions()
