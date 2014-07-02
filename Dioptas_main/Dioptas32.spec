# -*- mode: python -*-
a = Analysis(['Dioptas.py'],
             pathex=['C:\\Github\\Dioptas\\Dioptas_main'],
             hiddenimports=['scipy.special._ufuncs_cxx', 'skimage._shared.geometry'],
             hookspath=None,
             runtime_hooks=None)
pyz = PYZ(a.pure)
exe = EXE(pyz,
          a.scripts,
          exclude_binaries=True,
          name='Dioptas.exe',
          debug=False,
          strip=None,
          upx=True,
          console=False)
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=None,
               upx=True,
               name='Dioptas_32')
