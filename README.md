Dioptas
======

A GUI program for fast analysis of powder X-ray diffraction Images. It provides the capability of calibrating, 
creating masks, having pattern overlays and showing phase lines.

Maintainer
----------

Clemens Prescher (clemens.prescher@gmail.com)

Requirements
------------
    * python 2.7
    * PyQt4
    * numpy
    * scipy
    * pyFAI (https://github.com/kif/pyFAI)
    * fabio (https://github.com/kif/fabio)
    * pyqtgraph (http://www.pyqtgraph.org/) - version 0.9.9
    * scikit-image
    * PyCifRw

<b>optional:</b>

    * pyopencl (increasing pyFAI integration speed)
    * fftw3 (increasing pyFAI instegration speed)

It is known to run on Windows, Mac and Linux. For optimal usage on a windows machine it should be run with 64 bit
python. When used with 32 bit Dioptas occasionally crashes because of limited memory allocation possibilities.

Installation
------------

###Executables

Executable versions for Windows, Mac OsX and Linux (all 64bit) can be downloaded from:

[https://uni-koeln.sciebo.de/index.php/s/3feAlsnYZqqIK3N](https://uni-koeln.sciebo.de/index.php/s/3feAlsnYZqqIK3N)
or
[http://millenia.cars.aps.anl.gov/gsecars/data/Dioptas/](http://millenia.cars.aps.anl.gov/gsecars/data/Dioptas/)

###Code

In order to make changes to the source code yourself or always get the latest development versions you need to install
the required python packages on your machine.

The easiest way to install the all the dependencies for Dioptas is to use the Anaconda 64bit Python 2.7 distribution.
Please download it from https://www.continuum.io/downloads. After having the added the scripts to you path (or use the
Anaconda prompt on windows) please run the following commands on the commandline:

```bash
conda update --all
conda install numpy pillow scipy pandas matplotlib dateutil nose h5py pyqt scikit-image cython
pip install lmfit pyqtgraph fabio mock pycifrw
```

The only more advanced dependency is to install pyFAI, since the current release version has some problems with the
newest scipy version, please go to a temporary folder and run:

```bash
git clone https://github.com/kif/pyFAI
cd pyFAI
python setup.py install
cd ..
```

The pyFAI folder can be deleted after this.

Running the Program
------------------

You can start the program by running the Dioptas.py script in the dioptas folder.
