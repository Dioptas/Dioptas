rmdir /s /q dist
rmdir /s /q build

pyinstaller Dioptas.spec

cd dist/Dioptas*

::del mkl_avx512.dll, ^
::    mkl_avx2.dll, ^
::    mkl_avx.dll, ^
::    mkl_mc3.dll, ^
::    mkl_mc.dll, ^
::    mkl_pgi_thread.dll, ^
::    mkl_tbb_thread.dll, ^
::    mkl_sequential.dll, ^
::    mkl_vml_def.dll, ^
::    mkl_vml_cmpt.dll, ^
::    mkl_vml_mc.dll, ^
::    mkl_vml_mc2.dll, ^
::    mkl_vml_mc3.dll, ^
::    mkl_vml_avx.dll, ^
::    mkl_vml_avx2.dll, ^
::    mkl_vml_avx512.dll, ^
::    mkl_scalapack_ilp64.dll, ^
::    mkl_scalapack_lp64.dll, ^
::    Qt5Quick.dll, ^
::    Qt5Qml.dll, ^
::    opengl32sw.dll, ^
::    mfc140u.dll, ^
::    tcl86t.dll, ^
::    tk86t.dll, ^
::    sqlite3.dll, ^
::    win32ui.pyd, ^
::    libxml2.dll, ^
::    Qt5Network.dll, ^
::    unicodedata.pyd, ^
::    ucrtbase.dll, ^
::    iconv.dll 2>NUL
::
::rmdir /s /q bokeh, ^
::    bottleneck, ^
::    certify, ^
::    cryptography, ^
::    Cython, ^
::    cytoolz, ^
::    etc, ^
::    docutils, ^
::    gevent, ^
::    imageio, ^
::    jedi, ^
::    lxml, ^
::    nbconvert, ^
::    nbformat, ^
::    notebook, ^
::    mpl-data, ^
::    matplotlib, ^
::    mkl-fft, ^
::    msgpack, ^
::    pandas, ^
::    share, ^
::    PyQt5\Qt\bin, ^
::    PyQt5\Qt\uic 2>NUL
