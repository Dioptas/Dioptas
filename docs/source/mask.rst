.. sectnum::
   :start: 3

Mask Creation
=============


In the mask module areas can be defined which will be excluded from integration or calibration. There are several
geometries available to select different kind of areas. Additionally it is possible to mask based on threshold values
and perform automatic cosmic removal. All tools are available on the right control panel in the Mask view. It can be
either chosen to mask a certain region or unmask it (select either on the top of the control panel).

.. figure:: images/mask_view.png
    :align: center
    :width: 700

    The Mask module of Dioptas.


Selection Tools
---------------

To select a specific geometry just click on it and an orange border will show which one is active right now. All
geometric shapes are created by using left clicks:

- *Circle*:
    The first click defines the center of the circle and the second the radius of the circle.

- *Rectangle*:
    The first click defines one corner and the second the corner on the opposite side.

- *Point*:
    A click will mask an area as large as the circle floating around the mouse pointer. The size of the circle can be
    changed by changing the value next the the **Point** button or using just pressing the **q** and **w** keys.

- *Polygon*:
    Subsequent clicks will define edges of the polygon. A double click will close the polygon (and add the position of
    the double click as last point to the polygon)
- *Arc*:
    The first 3 clicks define a circle section and the 4th click defines the thickness of the arc.


Threshold Masking and Cosmic Removal
------------------------------------

In order to do threshold masking, please insert the wanted number next to the desired Thresh button and click the button.

Cosmic removal is an automatic optimization procedure trying to mask cosmic rays from the image. This procedure can take
considerable amount of time, please be patient.

Control Buttons
---------------

*Grow*:
    Grows the current mask by one pixel in all directions.

*Shrink*:
    Shrinks the current mask by one pixel in all directions.

*Invert*:
    This will invert the mask so that unmasked areas become masked and vice versa.

*Clear*:
    This will remove the complete mask.

*Undo/Redo*:
    Enabling to undo the last action or redo them. You can undo up to 50 actions.


File Handling
-------------

*Save Mask*:
    Saves the current mask as a tiff file with intensities being 1 for masked areas and 0 for unmasked areas.

*Load Mask*:
    Loads a previously saved mask. Clears the current mask before.

*Add Mask*:
    Loads a previously saved mask and adds it to the current mask.


