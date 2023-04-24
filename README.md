Dioptas
======

A GUI program for fast analysis of powder X-ray diffraction Images. It provides the capability of calibrating, 
creating masks, having pattern overlays and showing phase lines.

Maintainer
----------

Clemens Prescher (clemens.prescher@gmail.com)

Requirements
------------
    * python 3.9+

It is known to run on Windows, Mac and Linux. For optimal usage on a Windows machine it should be run with 64 bit
python. When used with 32 bit Dioptas occasionally crashes because of limited memory allocation possibilities.

Installation
------------

### Executables

Executable versions for Windows, Mac OsX and Linux (all 64bit) can be downloaded from:

https://github.com/Dioptas/Dioptas/releases

The executable versions are self-contained folders, which do not need any python installation. Under Windows and Linux 
the program can be started by running the executable (e.g. Dioptas.exe or Dioptas). Under MacOS X the folder will 
contain an app folder which can be double-clicked for starting. Please accept the security prompts.

### Code

In order to make changes to the source code yourself or always get the latest development versions you need to install
the required python packages on your machine.

The easiest way to install the all the dependencies for Dioptas is to use the pip package manager with python 
version newer than 3.7.

```bash
pip install dioptas
```

and then run Dioptas by typing:
```bash
dioptas
```
in the commandline.


Running the Program from source
-------------------------------

You can start the program by running the Dioptas.py script in the dioptas folder:

```bash
python Dioptas.py
```
