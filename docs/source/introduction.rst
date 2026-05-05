.. sectnum::

Introduction
============

Dioptas is a GUI program for fast integration and exploration of 2D X-ray diffraction images.
It provides the capability of calibrating, integrating, creating masks, showing multiple pattern overlays, and
displaying phase line positions.
The basis of the integration and calibration algorithm is the pyFAI_ library.
The usage of pyFAI_ allows integration times on the order of milliseconds and calibration of any detector geometry.

.. _pyFAI: https://github.com/silx-kit/pyFAI

Dioptas has four different modules which can all be accessed by the mode selector buttons on the left side of the user
interface: **Calibration**, **Mask**, **Integration**, and **Map**.

The **Calibration** module enables you to calibrate the detector geometry.
Within the **Mask** module you can select regions to exclude from image integration.
The **Integration** module is the heart of Dioptas, where you will spend most time for data exploration.
It shows both the image and integrated pattern, and you can overlay different patterns and show line positions of phases.
The **Map** module allows you to visualize and explore 2D maps of diffraction data collected on a grid.

.. figure:: images/integration_view_modules.png
    :align: center
    :width: 600 px

    Location of module selectors.

In addition to the GUI, Dioptas provides a :doc:`scripting API <scripting_api>` for headless integration
from Python scripts and Jupyter notebooks.


Mouse Interaction in the Image and Pattern Widgets
--------------------------------------------------

The image and pattern widgets available in all modules support the following mouse interactions:

- *Left Click:*
    Action depends on the current module.
    In the Calibration view it searches for peaks.
    In the Mask view it is the primary tool for creating geometric mask shapes.
    In the Integration view it draws a line at the current two-theta value.

- *Left Drag:*
    Zooms into the selected area.

- *Right Click:*
    Zoom out.

- *Right Double Click:*
    Completely zoom out (reset view).

- *Mouse Wheel:*
    Zoom in and zoom out centered on the current cursor position.


Image Color Scale and Contrast
------------------------------

Every image widget has a color bar and a histogram either on the side of the image (Mask and Calibration modules)
or on the top (Integration module).
The colors of the color bar can be adjusted in several ways:

- **Change color scale**: Right-click the color bar to select from predefined color scales.
- **Adjust individual colors**: Drag the triangle markers to reposition colors.
- **Change a color**: Double-click (left) a triangle to open a color chooser.
- **Add a new color**: Double-click (left) next to the color bar.

The histogram shows the intensity distribution of the loaded image on a log scale.
The two slider lines define the intensity range displayed in the image view — drag them to adjust contrast.

The **AutoScale** button (available in integration mode) automatically adjusts the intensity range for each
newly loaded image using percentile-based scaling.


Keyboard Shortcuts
------------------

Several keyboard shortcuts are available throughout the application:

- *Ctrl/Cmd + Left/Right Arrow Keys:* Load the previous/next image. Available in all modules.
- *Alt + Left/Right Arrow Keys (Integration module):* Move the position line on the pattern
  by one data point. Hold **Shift** as well to step by 10 points; hold **Ctrl/Cmd** as well
  to take a fractional (1/20th) step.
- *Q/W Keys (Mask module):* Decrease/increase point mask size.
- *Ctrl/Cmd + Z (Mask module):* Undo last mask action.
- *Ctrl/Cmd + Y (Mask module):* Redo last mask action.
