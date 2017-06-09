Dioptas
======

A GUI program for fast analysis of powder X-ray diffraction Images. It provides the capability of calibrating, 
creating masks, having pattern overlays and showing phase lines.

Maintainer
----------

Clemens Prescher (clemens.prescher@gmail.com)

Requirements
------------
    * python 2.7/3.5
    * qtpy with PyQt5/PyQt4/PySide
    * numpy
    * scipy
    * future
    * pyFAI (https://github.com/silx-kit/pyFAI)
    * fabio (https://github.com/silx-kit/fabio)
    * pyqtgraph (https://github.com/pyqtgraph/pyqtgraph
    * scikit-image
    * PyCifRw

<b>optional:</b>

    * pyopencl (increasing pyFAI integration speed)
    * fftw3 (increasing pyFAI instegration speed)

It is known to run on Windows, Mac and Linux. For optimal usage on a windows machine it should be run with 64 bit
python. When used with 32 bit Dioptas occasionally crashes because of limited memory allocation possibilities.

Installation
------------

### Executables

Executable versions for Windows, Mac OsX and Linux (all 64bit) can be downloaded from:

[https://uni-koeln.sciebo.de/index.php/s/rS4RkVjU6guQeRP](https://uni-koeln.sciebo.de/index.php/s/rS4RkVjU6guQeRP)
or
[http://millenia.cars.aps.anl.gov/gsecars/data/Dioptas/](http://millenia.cars.aps.anl.gov/gsecars/data/Dioptas/)

The executable versions are self-contained folders, which do not need any python installation.

### Code

In order to make changes to the source code yourself or always get the latest development versions you need to install
the required python packages on your machine.

The easiest way to install the all the dependencies for Dioptas is to use the Anaconda 64bit Python 2.7 distribution.
Please download it from https://www.continuum.io/downloads. After having the added the scripts to you path (or use the
Anaconda prompt on windows) please run the following commands on the commandline:

```bash
conda install --yes numpy pillow pycifrw scipy pandas matplotlib python-dateutil nose h5py pyqt scikit-image cython future qtpy pyfai fabio lmfit mock -c conda-forge
conda install --yes pyqtgraph -c cprescher
conda install --yes pyepics -c  lightsource2
```


Running the Program
------------------

You can start the program by running the Dioptas.py script in the dioptas folder by:

```bash
python Dioptas.py
```
