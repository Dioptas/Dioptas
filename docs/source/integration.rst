.. sectnum::
   :start: 4

==================
Integration Module
==================


The Integration module is the heart of Dioptas.
Here you can automatically integrate images to patterns, browse between images, compare multiple patterns,
perform background subtraction, apply intensity corrections, and compare peak positions to known phases.

.. figure:: images/integration_view.png
    :align: center
    :width: 600

    The Integration module of Dioptas.

The current image is displayed on the left with the integrated pattern shown on the lower right.
The control panel on the upper right has several tabs:

- **Image** — Loading, browsing, and batch processing images
- **Pattern** — Pattern file handling and auto-save settings
- **Overlay** — Loading and comparing multiple patterns
- **Phase** — Loading crystallographic phases and adjusting conditions
- **Cor** — Intensity corrections (cBN seat, detector absorption, transfer function)
- **Bkg** — Image and pattern background subtraction
- **X** — Integration options (binning, azimuth range, supersampling)


File Handling
-------------

Images and patterns can be loaded by clicking the **Load** button in the respective tabs.
Supported image formats include: *.tif*, *.tiff*, *.cbf*, *.edf*, *.img*, *.sfrm*, *.dm3*, *.xml*,
*.kccd*, *.mccd*, *.mar3450*, *.pnm*, *.spr*, *.spe*, HDF5 files, and other formats supported by fabio.
Pattern files should be 2-column files, optionally with a '#'-commented header.

Images loaded will be automatically integrated if a calibration is available (either from performing it in the
Calibration module or by loading a ``.poni`` file).

There are two modes for file browsing (using the **<** and **>** buttons):

*By Name*:
    Files are found based on the last digits in the filename.
    For example, the next file from *test_002.tif* is *test_003.tif*.

*By Time*:
    Files are sorted by creation time. This mode does not require numbers in filenames.

The **step** value controls how many files to skip when browsing.
The **autoprocess** checkbox monitors the current directory and automatically loads any newly added file.

For multi-frame files (e.g., HDF5), a frame slider and position indicator allow navigation within the file.


Pattern Auto-Save
~~~~~~~~~~~~~~~~~

To automatically save integrated patterns, select an output folder in the **Pattern** tab by clicking "**...**"
and check the **autocreate** checkbox.
Patterns can be saved in four formats simultaneously:

- *.xy*: Two-column format with calibration header (default)
- *.chi*: Two-column Fit2D format
- *.dat*: Two-column format without header
- *.fxye*: Three-column GSAS/GSAS-II format (includes intensity errors)


Batch Processing
~~~~~~~~~~~~~~~~

In the **Image** tab, batch operations allow processing multiple images at once:

- **Integrate**: Integrate all files in a directory
- **Add**: Sum multiple images
- **Average**: Average multiple images
- **Save**: Save the current image

A progress dialog shows the integration status.


Overlays
--------

.. figure:: images/overlay_control.png
    :align: center
    :width: 500

    Overlay controls in the integration window.

The Overlay tab allows loading and comparing multiple patterns:

- *Add*: Load one or more pattern files as overlays.
- *Delete*: Remove the selected overlay.
- *Clear*: Remove all overlays.

Each overlay in the list has:

- A **visibility checkbox** to show/hide it
- A **color button** to change its display color (click to open color chooser)
- An **editable name** (double-click to rename)

Adjust the **Scale** and **Offset** of overlays using the spin boxes on the right.
The **Step** fields control the spin box increment.

Right-clicking on an overlay provides a context menu with **Match intensity** to automatically scale the
overlay to match the active pattern's intensity range.


Set as Background
~~~~~~~~~~~~~~~~~

The **Set as Background** button uses the selected overlay as a background for pattern subtraction.
The background remains active for all subsequently integrated or loaded patterns.
If auto-save is enabled, background-subtracted patterns are saved in a ``bkg_subtracted`` subfolder.

Waterfall
~~~~~~~~~

The **Waterfall** button automatically offsets all overlays by multiples of the specified value,
creating a waterfall plot. The **Reset** button sets all overlay offsets to zero.


Phases
------

.. figure:: images/phase_control.png
    :align: center
    :width: 500

    Phase controls in the integration window.

Phase controls are similar to overlay controls:

- *Add*: Load a ``.jcpds`` or ``.cif`` file. CIF files are internally converted to JCPDS format;
  a dialog asks for the **Intensity Cutoff** and **Minimum d-spacing** for reflections.
  Multiple files can be selected at once.
- *Edit*: Open the JCPDS editor dialog.
- *Delete*: Remove the selected phase.
- *Clear*: Remove all phases.
- *Save List / Load List*: Save or restore a list of loaded phases.

Each phase shows its name, pressure, and temperature.
The **P** and **T** spin boxes adjust pressure and temperature.
Check **Apply to all phases** to change all phases simultaneously.
**Show in Pattern** controls whether P/T values appear in the phase legend.


JCPDS Editor
~~~~~~~~~~~~

.. figure:: images/jcpds_editor.png
    :align: center
    :height: 500

    Graphical JCPDS editor.

The JCPDS Editor allows modifying phase parameters interactively.
All changes are immediately reflected in the pattern line positions.
You can edit:

- Comment and symmetry
- Lattice parameters
- Equation of state parameters
- Individual reflections (h, k, l, intensity) by double-clicking in the table

A "0" suffix indicates ambient-condition values; values without "0" correspond to the current P/T conditions.

- *Save As*: Save modifications to a new file
- *Reload File*: Revert all changes
- *OK*: Accept changes and close
- *Cancel*: Revert changes made since opening and close


Corrections
-----------

.. figure:: images/cor_control.png
    :align: center
    :width: 600

    Correction controls in the integration window.

The **Cor** tab provides three types of intensity corrections:


cBN Seat Correction
~~~~~~~~~~~~~~~~~~~

Calculates the theoretical transmitted intensity through a diamond and cBN seat assembly
(for diamond anvil cell experiments). Parameters:

- *Anvil d*: Diamond anvil thickness (mm)
- *Seat d*: cBN seat thickness (mm)
- *Inner Seat r*: Small opening radius of the cBN seat (mm)
- *Outer Seat r*: Large opening radius (mm)
- *Cell Tilt*: Cell tilt relative to the beam (degrees)
- *Tilt Rot*: Direction of the cell tilt (degrees)
- *Offset*: Sample offset from the center of the diamond–seat assembly (mm)
- *Offs. Rot*: Rotation of the center offset (degrees)
- *Anvil AL*: Diamond absorption length (μm)
- *Seat AL*: cBN seat absorption length (μm)

Click **Plot** to visualize the calculated absorption correction in the image view.


Oblique Incidence Angle Detector Absorption Correction
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Corrects for the detector's intensity response at large angles, where the path length through the
scintillator increases. Parameters:

- *Det. Thickness*: Scintillator thickness (mm)
- *Abs. Length*: Scintillator absorption length (μm)

Click **Plot** to visualize the correction.

.. note::
    This correction assumes all intensity comes from the calibrated sample position.
    It is not valid for air scattering or other diffuse background contributions.
    Remove such backgrounds before applying this correction.


Transfer Function Correction
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Corrects for non-uniform detector response using a pair of images: an **original** flat-field image
and the detector's **response** image. The correction is the ratio of original to response.


Background Subtraction
----------------------

.. figure:: images/background_control.png
    :align: center
    :width: 600

    Background controls in the integration window.

The **Bkg** tab provides two types of background subtraction:

Image Background
~~~~~~~~~~~~~~~~

Subtract a background image (e.g., dark frame or empty cell) from the raw image before integration.

- *Load*: Load an image as background.
- *Remove*: Remove the background image.
- *Scale*: Multiply the background intensity by this factor.
- *Offset*: Add this value to the background intensity.

The formula is: ``corrected = image - (scale × background + offset)``

After any change, the image is automatically reintegrated.


Pattern Background
~~~~~~~~~~~~~~~~~~

Automatically estimate and subtract the background from the integrated pattern using a moving-average
(Smooth Bruckner) method:

- *Smooth Width*: Width of the smoothing window (in pattern x-units).
- *Iterations*: Number of smoothing passes.
- *Poly Order*: Chebyshev polynomial order for the background fit.
- *X-Range*: Min and max x-values for background estimation.
  **Note**: The subtracted pattern is only displayed within this range.
- *Inspect*: Show the original pattern and estimated background (red dashed line)
  side by side for parameter tuning. The x-range can be adjusted by dragging the yellow ROI lines.

.. _background_inspect_figure:

.. figure:: images/background_inspect.png
    :align: center
    :width: 600

    Inspect mode in the pattern widget for background subtraction.

The **bg** and **I** buttons on the right side of the pattern widget provide quick access to
enable background subtraction and inspection mode, respectively.


Options (X Tab)
---------------

.. figure:: images/integration_options.png
    :align: center
    :width: 500

    Integration options.

1D Integration
~~~~~~~~~~~~~~

- *Number of Bins*: Manually set the number of integration bins, or check **auto** to let pyFAI decide.
- *Azimuth Range*: Restrict the azimuthal range for integration (in degrees).
- *Solid Angle Correction*: Enable/disable solid angle correction during integration.
- *Supersampling*: Split each pixel into n² sub-pixels for finer integration.
  Can reduce peak widths for large pixels but may produce artifacts. Use with caution.

2D Cake Integration
~~~~~~~~~~~~~~~~~~~

- *Azimuth Bins*: Number of azimuthal bins for the cake image.
- *Azimuth Range*: Restrict the azimuthal range of the cake.
- *Integral Width*: Width of the azimuthal integration range when clicking on the cake.


Quick Actions
-------------

The Image and Pattern widgets have quick-action buttons for common operations.


Image Quick Actions
~~~~~~~~~~~~~~~~~~~

.. figure:: images/image_widget_qa.png
    :align: center
    :width: 400

    Quick actions in the image widget.

Located at the bottom/top of the image widget:

- *ROI*: Show a draggable region of interest — only the area inside the ROI is integrated.
- *Cake*: Switch to cake (2D-integrated) view showing intensity vs. azimuth.
- *Image*: Switch back to the raw image view.
- *Mask*: Toggle the mask for integration (mask must be defined in the Mask module first).
- *trans*: Toggle transparent mask display.
- *bg*: Show the background-subtracted image (requires a loaded background).
- *AutoScale*: Automatically adjust the intensity range for each new image.
- *Undock/Dock*: Detach the image widget into a separate window (useful for multi-monitor setups).


Pattern Quick Actions
~~~~~~~~~~~~~~~~~~~~~

Located at the top and right side of the pattern widget:

**Top buttons:**

- *Save Image*: Save the current view as PNG or TIFF.
- *Save Pattern*: Save the pattern as .xy, .png, or .svg.
- *As Overlay*: Add the active pattern to overlays.
- *As Bkg*: Add the active pattern as a background overlay.
- *Load Calibration*: Load a .poni calibration file.

**Right-side buttons:**

- :math:`2\theta`, :math:`Q`, :math:`d` — Select the integration unit.
- *Log*, *Sqrt* — Toggle logarithmic or square-root y-axis scaling.
- *bg*, *I* — Enable background subtraction and inspection mode.
- *AA* — Toggle anti-aliasing (disable for better performance with many overlays).
- *A* — Auto-range: automatically scale to show the full pattern when new data is loaded.
