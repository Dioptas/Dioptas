#!/usr/bin/env python
"""
Create desktop shortcuts to run Python scripts.
More specifically, this creates a desktop shortcut
for Windows or Linux, or a small App for MacOSX.

"""

from __future__ import print_function
import os
import sys
import shutil


def unixpath(d):
    "unix path"
    return d.replace('\\', '/')

def winpath(d):
    "ensure path uses windows delimiters"
    if d.startswith('//'):
        d = d[1:]
    d = d.replace('/', '\\')
    return d

nativepath = unixpath
if os.name == 'nt':
    nativepath = winpath

def fix_anacondapy_pythonw(script):
    """fix shebang line for scripts using anaconda python
    to use 'pythonw' instead of 'python'
    """
    # print(" fix anaconda py (%s) for %s" % (sys.prefix, script))
    fname = os.path.join(sys.prefix, 'bin', script)
    with open(fname, 'r') as fh:
        try:
            lines = fh.readlines()
        except IOError:
            lines = ['-']
    firstline = lines[0][:-1].strip()
    if firstline.startswith('#!') and 'python' in firstline:
        firstline = '#!/usr/bin/env pythonw'
        fh = open(fname, 'w')
        fh.write('%s\n' % firstline)
        fh.write("".join(lines[1:]))
        fh.close()

HAS_PWD = True
try:
    import pwd
except ImportError:
    HAS_PWD = False

def get_homedir():
    "determine home directory"
    home = None
    def check(method, s):
        "check that os.path.expanduser / expandvars gives a useful result"
        try:
            if method(s) not in (None, s):
                return method(s)
        except:
            pass
        return None

    # for Unixes, allow for sudo case
    susername = os.environ.get("SUDO_USER", None)
    if HAS_PWD and susername is not None and home is None:
        home = pwd.getpwnam(susername).pw_dir

    # try expanding '~' -- should work on most Unixes
    if home is None:
        home = check(os.path.expanduser, '~')

    # try the common environmental variables
    if home is  None:
        for var in ('$HOME', '$HOMEPATH', '$USERPROFILE', '$ALLUSERSPROFILE'):
            home = check(os.path.expandvars, var)
            if home is not None:
                break

    # For Windows, ask for parent of Roaming 'Application Data' directory
    if home is None and os.name == 'nt':
        try:
            from win32com.shell import shellcon, shell
            home = shell.SHGetFolderPath(0, shellcon.CSIDL_APPDATA, 0, 0)
        except ImportError:
            pass

    # finally, use current folder
    if home is None:
        home = os.path.abspath('.')
    return nativepath(home)

##  Desktop/Larch folder
homedir = get_homedir()
desktop = os.path.join(homedir, 'Desktop')


def make_shortcut_macosx(name, script, description='',
                         icon_path='.', icon=None, in_terminal=False):
    """create minimal Mac App to run script"""
    pyexe = sys.executable
    if 'Anaconda' in sys.version:
        pyexe = "{prefix:s}/python.app/Contents/MacOS/python".format(prefix=sys.prefix)
        fix_anacondapy_pythonw(script)
    dest = os.path.join(desktop, name + '.app')
    if os.path.exists(dest):
        shutil.rmtree(dest)
    os.mkdir(dest)
    os.mkdir(os.path.join(dest, 'Contents'))
    os.mkdir(os.path.join(dest, 'Contents', 'MacOS'))
    os.mkdir(os.path.join(dest, 'Contents', 'Resources'))
    opts = dict(name=name, desc=description, script=script,
                prefix=sys.prefix, pyexe=pyexe)

    info = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple Computer//DTD PLIST 1.0//EN"
"http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
  <key>CFBundleGetInfoString</key> <string>{desc:s}</string>
  <key>CFBundleName</key> <string>{name:s}</string>
  <key>CFBundleExecutable</key> <string>{name:s}</string>
  <key>CFBundleIconFile</key> <string>{name:s}</string>
  <key>CFBundlePackageType</key> <string>APPL</string>
  </dict>
</plist>
"""

    header = """#!/bin/bash
## Run script with Python that created this script
export PYTHONEXECUTABLE={prefix:s}/bin/python
export PY={pyexe:s}
export SCRIPT={prefix:s}/bin/{script:s}
"""
    ## {pyexe:s} {prefix:s}/bin/{script:s}
    text = "$PY $SCRIPT"
    if in_terminal:
        text = """
osascript -e 'tell application "Terminal" to do script "'${{PY}}\ ${{SCRIPT}}'"'
"""

    with open(os.path.join(dest, 'Contents', 'Info.plist'), 'w') as fout:
        fout.write(info.format(**opts))

    script_name = os.path.join(dest, 'Contents', 'MacOS', name)
    with open(script_name, 'w') as fout:
        fout.write(header.format(**opts))
        fout.write(text.format(**opts))
        fout.write("\n")

    os.chmod(script_name, 493) ## = octal 755 / rwxr-xr-x
    if icon is not None:
        icon_dest = os.path.join(dest, 'Contents', 'Resources', name + '.icns')
        icon_src = os.path.join(icon_path, icon + '.icns')
        shutil.copy(icon_src, icon_dest)

def make_shortcut_windows(name, script, description='',
                          icon_path='.', icon=None, in_terminal=False):
    """create windows shortcut"""
    from win32com.client import Dispatch

    pyexe = os.path.join(sys.prefix, 'python.exe')  # could be pythonw?
    if in_terminal:
        pyexe = os.path.join(sys.prefix, 'python.exe')
    target = os.path.join(sys.prefix, 'Scripts', script)

    # add several checks for valid ways to run each script, including
    # accounting for Anaconda's automagic renaming and creation of exes.
    target_exe = '%s.exe' % target
    target_bat = '%s.bat' % target
    target_spy = '%s-script.py' % target

    if os.path.exists(target_exe):
        target = target_exe
    elif os.path.exists(target_spy):
        target = "%s %s" % (pyexe, target_spy)
    elif os.path.exists(target):
        fbat = open(target_bat, 'w')
        fbat.write("""@echo off

%s %%~dp0%%~n0 %%1 %%2 %%3 %%4 %%5

        """ % (pyexe))
        fbat.close()
        target = target_bat

    shortcut = Dispatch('WScript.Shell').CreateShortCut(
        os.path.join(desktop, name) +  '.lnk')
    shortcut.Targetpath = target
    shortcut.WorkingDirectory = homedir
    shortcut.WindowStyle = 0
    shortcut.Description = description
    if icon is not None:
        shortcut.IconLocation = os.path.join(icon_path, icon + '.ico')
    shortcut.save()


def make_shortcut_linux(name, script, description='',
                        icon_path='.', icon=None, in_terminal=False):
    """create linux desktop app"""
    buff = ['[Desktop Entry]']
    buff.append('Name=%s' % name)
    buff.append('Type=Application')
    buff.append('Comment=%s' % description)
    if in_terminal:
        buff.append('Terminal=true')
    else:
        buff.append('Terminal=false')
    if icon:
        buff.append('Icon=%s' % os.path.join(icon_path, '%s.ico' % icon))

    buff.append('Exec=%s' % os.path.join(sys.prefix, 'bin', script))
    buff.append('')

    with open(os.path.join(desktop, '%s.desktop' % name), 'w') as fout:
        fout.write("\n".join(buff))


make_shortcut = None

if sys.platform.startswith('win') or os.name == 'nt':
    make_shortcut = make_shortcut_windows
elif sys.platform == 'darwin':
    make_shortcut = make_shortcut_macosx
elif sys.platform == 'linux':
    make_shortcut = make_shortcut_linux

# def make_desktop_shortcuts():
#     """make desktop shortcuts with icons for current OS
#     using definitions in APPS
#     """
#
#     if maker is not None:
#         for (name, script, description, iconfile, in_terminal) in APPS:
#             maker(name, script, description=description,
#                   icon=iconfile, in_terminal=in_terminal)
