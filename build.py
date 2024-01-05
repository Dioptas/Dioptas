import os
import shutil

from setuptools import Distribution
from setuptools import Extension
from setuptools.command.build_ext import build_ext


extensions = [
    Extension(
        "dioptas.model.util.smooth_bruckner_cython",
        ["dioptas/model/util/smooth_bruckner_cython.pyx"],
    ),
]

def build():
    distribution = Distribution({"name": "dioptas", "ext_modules": extensions})
    distribution.package_dir = {"dioptas": "dioptas"}

    cmd = build_ext(distribution)
    cmd.ensure_finalized()
    cmd.run()

    # Copy built extensions back to the project
    for output in cmd.get_outputs():
        relative_extension = os.path.relpath(output, cmd.build_lib)
        shutil.copyfile(output, relative_extension)
        mode = os.stat(relative_extension).st_mode
        mode |= (mode & 0o444) >> 2
        os.chmod(relative_extension, mode)


if __name__ == "__main__":
    build()
