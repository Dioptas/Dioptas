.. sectnum::
   :start: 6

==========
Map Module
==========

The Map module enables visualization and exploration of 2D diffraction data collected on a spatial grid.
This is useful for experiments where samples are scanned in a grid pattern (e.g., X-Y mapping) and you
want to explore how diffraction patterns vary across the sample.

.. figure:: images/map_view.png
    :align: center
    :width: 600

    The Map module of Dioptas.


Overview
--------

The Map module has a four-panel layout:

- **Map image** (left): Shows a 2D map where each pixel represents an integrated diffraction pattern.
  The pixel value is derived from a selected feature of the pattern (e.g., intensity in a region of interest).
- **Image view** (upper right): Shows the raw diffraction image for the currently selected map position.
- **Control panel** (middle right): Controls for loading data, adjusting visualization, and selecting ROI.
- **Pattern plot** (lower right): Shows the integrated pattern for the currently selected map position.


Loading Map Data
----------------

To create a map, you need a set of integrated diffraction patterns arranged on a grid.
The Map module can integrate multiple image files and arrange them based on their positions.

The map dimensions are calculated automatically from the number of files and the expected grid size.


Visualization Options
---------------------

Several options are available to enhance the map visualization:

- **Smooth**: Apply smoothing to the map image for better visualization. The slider controls
  the smoothing level, which is automatically adjusted based on zoom level.
- **Contours**: Overlay contour lines on the map image using cubic interpolation.
  The slider controls the number of contour levels.
- **AutoScale**: Automatically adjust the image intensity range.
- **Dimension**: Select which dimension to display when the map has more than 2 dimensions.


Interacting with the Map
-------------------------

- **Left click** on the map image to select a position. The corresponding diffraction image and
  integrated pattern are displayed in the other panels.
- The pattern plot supports **Log** and **Sqrt** scaling buttons for the y-axis.
- A region of interest (ROI) can be selected on the pattern to define which feature is used to
  generate the map image values.


Reintegration
-------------

The **Reintegrate** checkbox allows re-running the integration for all map positions when integration
parameters change (e.g., unit, number of bins, mask). This is useful for exploring how different
integration settings affect the map.


Project Persistence
-------------------

The Map module state is saved in Dioptas project files (``.dio``), so maps can be restored
when reopening a project.
