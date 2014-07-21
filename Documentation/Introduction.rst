Dioptas
=======

Introduction
------------

Dioptas is a  GUI program for fast analysis of powder X-ray diffraction Images.
It provides the capability of calibrating, integrating, creating masks, showing multiple spectrum overlays and display
phases line positions.
The basis of the integration and calibration algorithm is the pyFAI library pyFAI_.
The usage of pyFAI_ allows integration times on the order of 20 milliseconds and calibration of every possible Fit2d.


.. _pyFAI: https:\\github.com\kif\pyFAI


Program structure
-----------------

Dioptas has three different modules which can all be accessed tab indicators on the left side of the interface:
Calibration, Mask, Integration.

The Calibration module enables you to calibrate the detector geometry. Within the mask module you can select regions you
want to exclude from the image integration. The Integration module is the heart for data exploration. It shows both, the
image and integrated spectra. You can overlay different spectra and show line position of phases.


Mouse Interaction with Images and Graph views
---------------------------------------------

Left Click:
    Action depends on the module you are in. In the calibration View it will search for peaks. In the Mask view it is
    the primary tool for creating geometric objects and In the Integration view it draws a line at the current two theta
    and the graph view and img view will be synchronized about this

Left Drag:
    Zooms in to the selected area. For diffraction images it will try to scale because pixels are kept as square objects
    on the screen.

Right Click (Command+Right Click on Mac):
    Zoom out.

Right Double Click (Command + Right Double Click on Mac):
    Completely zoom out.

Mouse Wheel:
    Zoom in and zoom out based on the current cursor position.

Image color scale and Contrast
------------------------------

Every image view has a color bar and a histogram either on the side of the image (Mask module and Calibration Module) or
on the top (integration view). The colors of the color bars can be easily adjusted. You can switch to a completely
different color-scale by right clicking the color bar. This creates a pop-up where one of the predefined color scales
can be selected. The position of the individual colors can be adjusted by dragging the triangle of this color. Further
the colors can be changed completely by double clicking (left) it, which will pop up a color chooser. It is in addition
also possible to add a complete new color by double clicking (left) next to the color bar. The histogram of pixel
intensities is a log scale histogram and the sliders of the range used to scale the image contrast can be adjusted by
mouse dragging until you are satisfied with it.

Calibration procedure
---------------------

Preparation:
    Make sure you are in the calibration module, which should be selected on the left side of the window. Load an the
    calibration image by clicking the "load image" button on the upper right side of the window. This will display the
    image. Now you can insert the starting values for the calibration in the menu on the right. Values should be relatively
    close to the real values although the calibration algorithm is a little bit more permissive than it is implemented in
    Fit2d. after you finished inserting the start values we have to define some initial peak positions.



