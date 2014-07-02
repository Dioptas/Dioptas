Dioptas
======

A GUI program for fast analysis of powder X-ray diffraction Images. It provides the capability of calibrating, creating masks, having spectrum overlays and showing phase lines.

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
    * pyfits
    * scikit-image

<b>optional:</b>

    * pyopencl
    * fftw3

It is known to run on Windows, Mac and Linux. For optimal usage on a windows machine it should be run with 64 bit python.

Installation
------------

#### Windows ####

The easiest way to obtain almost all required packages is to install WinPython 64 bit. After this installation you need to install pyFAI, fabio and pyqtgraph. Please refer to the links above for their respective installation instructions. For 64 bit compilation of the c-code in pyFAI and fabio the easiest available compilers are either included in Visual Studio (not the express edition) or the  Windows Software Development Kit version 7.1 (http://msdn.microsoft.com/en-us/windowsserver/bb980924.aspx )

#### OS X ####

Python and the other required packages can be installed by using a package manager like macports. For pyFAI, fabio, and pyqtgraph please refer to their installation instructions.

#### Linux ####

to be filled

