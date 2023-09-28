def build_cython_extensions():
    from Cython.Build import build_ext, cythonize
    from setuptools.dist import Distribution

    ext_modules = cythonize('dioptas/model/util/smooth_bruckner_cython.pyx')
    dist = Distribution({"ext_modules": ext_modules})
    cmd = build_ext(dist)
    cmd.ensure_finalized()
    cmd.run()


build_cython_extensions()
