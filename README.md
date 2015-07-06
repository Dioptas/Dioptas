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

<b>optional:</b>

    * pyopencl (increasing pyFAI integration speed)
    * fftw3 (increasing pyFAI instegration speed)
    * pymatgen (enables to import cif files as phases)

It is known to run on Windows, Mac and Linux. For optimal usage on a windows machine it should be run with 64 bit
python. When used with 32 bit Dioptas occasionally crashes because of limited memory allocation possibilities.

Installation
------------

###Executables

Executable versions for Windows, Mac OsX and Linux (all 64bit) can be downloaded from:

[http://millenia.cars.aps.anl.gov/gsecars/data/Dioptas/](http://millenia.cars.aps.anl.gov/gsecars/data/Dioptas/)

###Code

In order to make changes to the source code yourself or always get the latest development versions you need to install
the required python packages on your machine.

#### Windows ####

The easiest way to obtain almost all required packages is to install WinPython 64 bit or the Anaconda 64 bit python
distribution. After the installation you need to install pyFAI, fabio and pyqtgraph. Please refer to the links above for 
their respective installation instructions. 
For 64 bit compilation of the c-code in pyFAI and fabio the easiest available compilers are either included in 
Visual Studio (not the express edition), the Windows Software Development Kit version 7.1 
(http://msdn.microsoft.com/en-us/windowsserver/bb980924.aspx) or the Microsoft Visual C++ Compiler for Python 2.7 
(http://www.microsoft.com/en-us/download/details.aspx?id=44266).

#### OS X ####

Python and the other required packages can be installed by using a package manager like macports or also use a 
 distribution like anaconda or enthought. All required libraries can be installed using pip package manager.

#### Linux ####

All packages can be installed using the normal package manager (e.g. apt-get or pip). The .travis.yml file gives a 
list of detailed instructions to install a small anaconda distribution specifically for usage with Dioptas.

Running the Program
------------------

You can start the program by running the Dioptas.py script in the Dioptas_main folder.
