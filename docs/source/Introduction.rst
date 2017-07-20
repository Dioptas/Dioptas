Introduction
============

Dioptas is a  GUI program for fast integration and exploration of 2D X-ray diffraction Images.
It provides the capability of calibrating, integrating, creating masks, showing multiple pattern overlays and display
phases line positions.
The basis of the integration and calibration algorithm is the pyFAI_ library.
The usage of pyFAI_ allows integration times on the order of 80 milliseconds and calibration of every possible detector
geometry.


.. _pyFAI: https:\\github.com\silx-kit\pyFAI


Dioptas has three different modules which can all be accessed by the tab indicators on the left side of the user
interface: **Calibration, Mask, Integration**.

The Calibration module enables you to calibrate the detector geometry.
Within the Mask module you can select regions you want to exclude from the image integration and the Integration module
is the heart for data exploration.
It shows both, the image and integrated spectra.
One can overlay different spectra and show line position of phases.

.. figure:: images/integration_view_modules.png
    :align: center
    :width: 800 px

    Location of module selectors.


Mouse Interaction in Image Views and Pattern Views
--------------------------------------------------

*Left Click:*
    Action depends on the module you are in.
    In the calibration view it will search for peaks.
    In the Mask view it is the primary tool for creating the geometric objects used to build up the mask and in the
    integration view it draws a line at the current two theta value.

*Left Drag:*
    Zooms into the selected area.
    It will try to scale images accordingly, but will not perfectly zoom in to the selected area, because pixels are
    kept as square objects on the screen.

*Right Click (Command+Right Click on Mac):*
    Zoom out.

*Right Double Click (Command + Right Double Click on Mac):*
    Completely zoom out.

*Mouse Wheel:*
    Zoom in and zoom out based on the current cursor position.

Image Color Scale and Contrast
------------------------------

Every image view has a color bar and a histogram either on the side of the image (Mask module and Calibration Module) or
on the top (integration view). The colors of the color bars can be easily adjusted. You can switch to a completely
different color-scale by right clicking the color bar. This creates a pop-up where one of the predefined color scales
can be selected. The position of the individual colors can be adjusted by dragging the triangle of this color. Further
the colors can be changed completely by double clicking (left) it, which will pop up a color chooser. It is in addition
also possible to add a complete new color by double clicking (left) next to the color bar.
The histogram next to the color bar shows the intensity distribution of the loaded image on a log scale. The sliders two
lines define the scaling of the image in the image view. Please feel free to adjust their position by dragging them.

Configurations
--------------
.. _configuration_controls:

.. figure:: images/integration_view_configuration.png
    :align: center
    :width: 800 px

    Location of configuration controls.

Configuration are used to handle experimental setups with multiple detectors in one Dioptas instance. A configuration
contains the calibration information, loaded image, image corrections, mask, integrated pattern and background
corrections. Overlays and phases are not handled in configurations and are global. By default the configuration control
panel (:numref:`configuration_controls`) is hidden and only one configuration is active (single Detector mode).
To enable the panel, please click the **C** button on the upper left corner of Dioptas. In principle, Dioptas can handle
infinite configurations, however, this also means a lot of RAM usage.

A configuration can be added or removed by the **+** and **-** buttons. Each added will be subsequently numbered and
can be selected by the buttons to the left of the **-** button. After adding a a new configuration the configuration
will be empty and needs to be newly calibrated for the wanted detector geometry.

The *File* and *Folder* controls in the middle of the configuration panel enable combined file browsing for all
configurations, whereas the Pos textfield defines the position of the number in the string. By using the "**<**" and
"**>**" buttons the next or previous image in each configuration will be loaded.

This is also true for the similar *Folder* "**<**" and "**>**" buttons.
Here Dioptas supposes that the actual filenames stay the same, but the images are saved in subsequently indexed folders,
like e.g. "run101", "run102".
The MEC checkbox enables a special mode for the matters at extreme conditions beamline at LCLS where both, the folder
and the filenames have the run number included.

The Factor Input is an intensity scaling factor for the image in the configuration, so that different configurations can
be compared where the detector response is not equal.

**Combine Patterns**:Attempts to combine integrated patterns from all configurations, when selected.
    If there is overlap between the different configurations, the intensity will be averaged.

**Combine Cakes**: Attempts to combine integrated cakes from all configurations, when selected.
    If there is overlap between the different configurations (which is in principle not possible in a multi detector
    setup), the intensity will be averaged.




Dioptas Projects
----------------

.. _project_controls:

.. figure:: images/integration_view_project_controls.png
    :align: center
    :width: 800 px

    Location of the project controls

The state of Dioptas including the different configurations with image, mask, image corrections, background corrections
overlays and phases can be open and saved in projects. This is very useful in case you want to continue working on a
project another day. The controls for this are in the upper left of the Dioptas window (see :numref:`project_controls`).
The Dioptas project files have a *.dio extension and are basically HDF5 under the hood. Thus, can the data can be also
opened or edited with any HDF5 viewer.

.. image:: images/open_icon.png
    :align: left

Opens a file browser where you can select a Dioptas project (*.dio) to open.


.. image:: images/save_icon.png
    :align: left

Saves the current state of Dioptas into a Dioptas project (*.dio).


.. image:: images/erase_icon.png
    :align: left

Resets the current state of Dioptas. This means all phases, overlays, and configurations will be deleted and you can
start from a new fresh Dioptas.
