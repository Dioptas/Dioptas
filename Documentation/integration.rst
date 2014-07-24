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


File Browsing
-------------

Images and spectra can be loaded by clicking the **Load** button in the respective modules. Images can be in different
fileformats: *.img*, *.sfrm*, *.dm3*, *.edf*, *.xml*, *.cbf*, *.kccd*, *.msk*, *.spr*, *.tif*, *.mccd*, *.mar3450*,
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

*save Img*:


