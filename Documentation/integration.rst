Integration Module
==================

The integration module is the heart of Dioptas. Here you can automatically integrate multiple of spectra, browse between
images and integrated spectra, compare multiple spectra to each other, perform background subtraction and compare
spectrum peak positions to the ones of known phases.

.. figure:: images/integration_view.png
    :align: center
    :width: 700

    The integration module of Dioptas.

In the integration module the current image is displayed on the left side with the integrated spectrum shown on the
lower right. The control panel has several tabs for different functions.

The "**Img**" and "**Spec**" tabs are primarily for loading and browsing images and spectra, respectively.
In the "**Overlay**" tab integrated spectra can be loaded for comparing them to the currently loaded shown active spectrum.
The "**Phase**" tab enables opening/editing jcpds files and changing the equation of state parameters of the loaded phases.
Several display are based in the "**X**" tab.


File Handling
-------------

Images and spectra can be loaded by clicking the **Load** button in the respective modules. Images can be in different
file formats: *.img*, *.sfrm*, *.dm3*, *.edf*, *.xml*, *.cbf*, *.kccd*, *.msk*, *.spr*, *.tif*, *.mccd*, *.mar3450*,
*.pnm*, or any other common image formats. Spectrum files should be 2 column files. If there is a header present it should be
commented by '#' signs.

Images loaded will be automatically integrated if a calibration is available (either by performing it in the calibration
window or by loading a previously saved calibration file (* \*.poni*) file).
There are too modes for file browsing (clicking the "**<**" and "**>**" buttons:

*By Name*:
    the next and previous filenames will be searched based on the last digits in the filename. For example the next file from
    *test_002.tif* will be *test_003.tif* and the previous will be *test_001.tif*

*By Time*:
    The next and previous files loaded will be search based on creation time of the files. This filemode does not need
    any numbers in the filenames it will just sort the files based on creation time and go forward and backwards in this
    list.

Any newly added file to the current img working directory can be opened by checking the **autoprocess** checkbox in the
Image module.

By default the integrated spectra are not saved. If you want the spectra to be saved please choose an output folder in the
**Spec** tab by clicking the "**...**" button and then check the **autoprocess** checkbox. All new integrated spectra will
then be automatically saved in this folder with name being the same as the image but *.xy* as file extension. All spectrum
files contain a header showing the calibration used for their respective integration.

In addition to file browsing and the "**load**" button, files can also be loaded by inserting their name folder in the
respective text fields. The upper one is the filename and the lower one is the containing folder. If the file does not
exist it the text field will revert to its previous state.

Quick Actions
~~~~~~~~~~~~~

The "**Img**" and the "**Spec**" tab exhibit several quick actions, which are basically shortcuts to some
functions:

*Save Image*:
    Saves the currently shown image as either a \*.png file for presentation or \*.tiff file as data.

*Save Spectrum*:
    Saves the current spectrum either in a two-column format (\*.xy) or the complete spectrum content in a \*.png or
    vectorized \*.svg format.

*As Overlay*:
    Adds the currently active spectrum (white) to overlays.

*As Bkg*:
    Adds the currently active spectrum (white) to overlays and sets it as background.

*Load Calibration*:
    Opens a dialog to open a *.poni calibration file and sets this as the new calibration parameters.


Overlays
--------

.. figure:: images/overlay_control.png
    :align: center
    :width: 700

    Overlay controls in Dioptas.

In the overlay control panel you can add, delete or clear overlays and adjust their scaling and offset.

*Add*:
    Loads a spectrum file (2-column file) as overlay. It is possible to select multiple spectra and load them all at once.

*Delete*:
    Deletes the currently selected overlay in the overlay list.

*Clear*:
    Deletes all currently loaded overlays.

The list of overlays shows several widgets representing the state of each individual overlay.
The first checkbox controls if the overlay is visible
in the graph. The colored button shows the overlay color. Clicking on it will pop-up a color-chooser dialog where the color
for this overlay can be changed. The name of an overlay is by default its filename, but it can also be changed by
double-clicking the name in the overlay list.

On the right side you can adjust the scale and offset of the overlays by either entering a specific number or using the
spin-box controls. The **step** text fields control the steps of the spin-box.

An overlay can be used as a background for the spectrum. In order to to so, you have to activate the
"**Set as Background**" button. This button set the currently selected overlay as background for the spectrum file.
It can be seen that an overlay is set as background by the **Set as Background** button being activated for a
specific overlay and by the background overlay name being shown in the lower right of the graphical user interface
(right below the graph). The overlay/background can still be adjusted by using the scale and offset spin boxes. The
background overlay remains active until you deactivate it, therefore the background will be automatically subtracted from
each newly integrated image or newly loaded spectrum. If autosave for spectra is set, Dioptas will created a
*bkg_subtracted* folder in the autosave folder and automatically save all subtracted spectra.


Phases
------

.. figure:: images/phase_control.png
    :align: center
    :width: 700

    Phase controls for Dioptas

The basic controls for phases are similar to the ones in overlay:

*Add*:
    Loads a *.jcpds file, calculates the line positions in the range of the current spectrum and shows the phase lines in
    the graph. You can select multiple spectra in the file dialog.

*Edit*:
    Not yet implemented

*Delete*:
    Deletes the currently selected phase in the phase list.

*Clear*:
    Deletes all phases.

The list of phases shows several widgets representing the state of each individual phase overlay.
The first checkbox controls if the phase lines are visible in the graph.
The colored button shows the color of the phase lines. Clicking on it will pop-up a color-chooser dialog where the color
for this phase can be changed. The name of an phase is by default its filename, but can be changed by
double-clicking the name in the phase list. Additionally the pressure and temperature for each phase is shown in the phase
list. If for a particular phase thermal expansion is not in the jcpds file it will always display '- K'.

On the right side the pressure and temperatures of the loaded phases can be adjusted. If *Apply to all phases* is checked
the pressure and temperature will be set for all loaded phases.

Background subtraction
----------------------

Not yet Implemented

Options (X-Tab)
---------------

.. figure:: images/integration_options.png
    :align: center
    :width: 700

    Integration window option in Dioptas.

The currently available options:

*Mask - Transparent*:
    If a mask is used for integration it will be shown as transparent red over the image, compared to the usual solid red.
    This makes it possible to still be able to see what exactly is masked

*Levels - Autoscale, Absolute, Percentage*:
    These 3 choices are different modes for intensity scaling when loading new files or browsing files. *Autoscale* will
    always perform autoscaling for each newly loaded image. When using *Absolute* the maximum and minimum levels remain
    the same and are independent of the img intensities and when using *Percentage* the levels are always scaled as
    percentage of the maximum intensity of the newly loaded image.