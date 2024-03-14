# 0.6.0 (under development)

## New Features
    - Complete GUI overhaul with a Material inspired design
    - Added a new Map Mode for exploring data collected in a 2D grid
    - Multiple files loaded can now be averaged (new batch mode average selection availlable)
    - added the option to add custom "external actions" via providing json file upon start of Dioptas. This allows to
      add custom actions to the main window, which can be used to start external programs or scripts. The commands will
      be executed with two addidtional arguments, the path to the currently loaded image file and the current frame 
      number. The external action buttons are appearing on the lower left of the main window.

## Bug Fixes
    - fixed some issues related to memory when using HDF5 files
    - clicking calibrate without having defined peaks will result in a critical message box and 
      not an error anymore
    - when the automatic refinement will not find any points it will show a critical message 
      box with this information and the program does not show an error
    

# 0.5.9 (stable 13.11.2023)

## New Features
    - Intensity scaling is now persistent across Calibration, Mask and Integration tab
    - Additional configuration available  the scaling of images

## Bug Fixes
    - autoscaling images with detector gaps and large values in them (e.g. ESRF Dectris data) will now automatically ignore
      these gaps 
    - when importing cifs all rhombohedral space groups can now also be in a hexagonal setting (was previously only possible for 167)



# 0.5.8 (stable 29.09.2023)

## New features:
    - scale menu next to the image color scale (Thanks to @t20100)
        - can be opened by clicking the gear wheel
        - allows for manual selection of minimum and maximum values
        - scaling can be set to logarithmic and square root (default is linear)
        - extra button to redo the autoscaling
    - autoscale implementation is now better working with large values (e.g. ESRF Dectris Eiger images)
      (Thanks to @t20100)

## Bug Fixes:
    - fix issues with type of the radial bin number being float instead of int -> this caused issues with the
      integration of cake when setting a manual radial bin number
    - cosmic removal is now working again
    - fixes issue with auto peak number increasing while the checkbox for it was unchecked
    - no more error message when mouse is hovering over the cake image at 0 indices of the image
    - changing the color of an overlay or phase item is now working correctly again
    - the mask is now correctly reset when batch integration is started with images of different shape


# 0.5.7 (stable 24.04.2023)

## New features:
    - saving in batch window will now also save background subtracted patterns, if enabled in the pattern widget
    - upgraded dependency pyqt5 to pyqt6 which should result in improvements for high dpi screens
    - added a new "integrate" button to the batch widget, which will integrate all images in the batch widget
    - now compatible with python 3.11, whenever possible the created executables are compiled with python 3.11
    - dropping support for python 3.6, 3.7 and 3.8 and focussing on compatibility with python 3.9, 3.10 and 3.11


## Bug Fixes:
    - fix numpy float conversion issue due to deprecated numpy.float
    - reading cif files with missing volume tag will now work correctly and the volume will be calculated from cell
      parameters (PR #140, thanks to @ScottNotFound)


# 0.5.6 (stable 23.11.2022)
    - Removed image files from pypi distribution.

# 0.5.5 (stable 22.11.2022)

## New Features:
    - added a normalize button to the batch widget, which will normalize all batch integrated patterns
      to the starting area (i.e. the first 10-30 values of the pattern)
    - batch integration starts immediate after selecting the files
    - added browsing between folders in batch widget


## Bug Fixes:
    - fixed issue with image transformations (rotations and flips)
    - fix issues with font size on some high dpi settings in white text boxes
    - improve resize behavior (dragging the splitter) in the integration view
    - fixed issue with resizing batch widget when filepaths were long


# 0 .5.4 (stable 20.12.2021)

## New Features:
    - made openGL dependency for Batch widget addition optional. --> this means executables are now working properly
      under Mac OS X again
    - Batch waterfall plot is now possible with background subtraction enabled
    - Batch heatmap can now be trimmed along x axis (new T Button) - region of trimming is synchronized with the
      main Dioptas background controls
    - improvements on Batch widget interface - buttons are now only visible when necessary, added more tooltips,
      slightly redesigned gui, improved background calculation with d-spacing as axis unit


## Bug Fixes:
    - fixes issue with mask button toggle when in cake mode
    - fixes the error appearing when clicking into the cake image in the integration window
    - fixes axes not updating when zooming in and out in cake widget and batch widget
    - fixes background subtraction as shown in contour plot of Batch widget (2D view) and in waterfall/overlays 1D
      representation of the main Dioptas window
    - fixes switching between x-axis units (2th, d-spacing, Q) in Batch widget
    - fixes intensity estimation in Batch widget (lower right corner) when background subtraction is activated.
    - fixes issues with representation of phases inside the contour plot of Batch widget, e.g. resetting of the
      "Show Phases" button state upon file information reloading, updating position of the phases upon user input, etc
    - sources selection box is not shown in pattern control widget anymore
    - tth/q/d vertical green line position is now correctly synchronized between image, cake, pattern and batch widget

# 0.5.3a (stable 10/10/2021)

## New Features:
    - pip package has now the correct dependencies

## Bug Fixes:
    - small bug fixes for batch integration (checks whether calibration or mask is loaded)

# 0.5.3 (stable 10/04/2021)

## New Features:
    - added a batch integration view (thanks to hard work of Mikhail Karnevskiy @ DESY). Here you can batch integrate
      your collection series and interact with a contour or 3D plot of the integrated patterns -> this also includes
      visualization of phases lines
    - reading ESRF hdf5 data files is now possible
    - combined patterns from multiple configurations can now be saved as a file (save button on the upper right)

## Bug Fixes:
    - no longer remove integrated intensities below 0, instead now only values with equal to 0 are removed
      (this should fix all the issues with background corrected images)
    - reimplemented the automatic file recognition algorithm of the autoprocess integration function. This should now
      work much more reliable also on network drives and linux systems
    - QT high dpi scaling is now only activated for Windows and Mac OS X -> Disabling it on Linux fixes the display bugs
      encountered here and it is usable with low and high dpi screens (it was not working correctly)

# 0.5.2 (stable 11/26/2020)

## New Features:
    - Added an azimuthal histogram for the cake view, please check the X-Tab in the integration view to change the
      integration bins in 2 theta direction
    - Azimuthal range for 1d integration can now be set in the X-Tab

## Bug Fixes:
    - fix calibration algorithm, which was currently failing most of the time for difficult geometries. It should now
      work correctly again as in 0.5.0
    - fix display bug which was showing horizontal scroll bar in "calibration parameters" on some linux systems
    - disable QT high dpi mode for Linux platforms, which was causing very tiny font sizes. It is working correctly
      without it
    - fixed pixel width/height definition in the detector calibration definition (it was applied interchanged)

# 0.5.1 (stable 05/05/2020)

## New Features:
    - Phase lines can now be shown in the Cake Widget. Intensity is shown as thickness and opacity of the lines.
    - Phase line parameters can now be copied out of the jcpds widget by using ctrl+c and used directly in your
      preferred table/text editor
    - Added a Detector Groupbox in the Calibration Widget. Predefined Detectors can now be loaded as well as Nexus
      Detector files. This enables to load e.g. Nexus detector h5 files which include positions for each pixel.
      (distortion correction and also useful for combined detector modules not adjacent to each other).
    - Added a Continuous Delivery Pipelines, which automatically create executables for all operating systems
      (Thanks to Github Actions)

## Bug Fixes:
    - having parameters fixed during calibration works now correctly
    - the refine button now also works without automatic refinement and with just a calibration loaded from a file
    - reading trigonal rhombic cif files works now correctly
    - setting the dk/dT parameter now changes the Bulk Modulus of a phase. This parameter was previously ignored.
    - entering the range for the automatic background subtraction works now correctly
    - the motor setup widget is now not showing anymore after starting Dioptas on OS X
    - fixed double logarithm for the intensity distribution display histogram
    - (re)loading of a project with image transformations should now work correctly
    - loading cif files with the newer '_space_group_IT_number' representation work now correctly
    - green line in cake widget is now shown correctly upon reloading dioptas

# 0.5.0 (stable 03/05/2019)

## New Features:
    - Added the capability of using detector distortion correction defined by spline files generated from Fit2D (please
      see the calibration parameters)
    - PONI and rotation parameters can now be fixed during the calibration
    - redesigned parts of the GUI: (1) the top controls in the Integration view no adapt to the used width, and split
      into two groups to make use of the space. (2) Overlay and Phase Control Widgets now are mainly controlled by
      buttons and the important parameter can be changed for each item individually in the table. (3) There is now a
      a different view mode for the integration view, where image and integrated pattern are shown on the left, and all
      control panels are on the right. This can be activated by using the change view button on the lower left.
    - the cBN Seat Correction and Detector Incidence Absoprtion Correction Controls have been redesigned
    - Added the option to use a transfer correction for image intensities. Please see the Cor tab in the integration
      view
    - azimuthal bins and azimuthal range for the cake integration can now be adjusted manually in the X tab
    - the cake image can now be exported (press the save button below the image)
    - auto-extracted Pattern background can now be saved as file or later reused as overlay
    - the background subtraction algorithm is now also rewritten in cython, which should make deployment easier
    - a button was added to undo the last peak selection in the calibration tab
    - the jcpds editor now also shows q-values for each line

## Bug Fixes:
    - cosmic removal in the mask panel is now working again
    - changing the radial bins in the X tab in the integration view works now correctly again
    - phases with trigonal symmetry should now work correctly
    - saved background range should now correctly restore after restarting Dioptas
    - browsing files works now correctly from 10 to 9 without leading zeros
    - loading a *.poni file prior to an image will not result in an error message anymore


# 0.4.1 (stable 12/22/2017)

## New Features:
    - easier step selection for pressure, temperature in the phases widget and scaling and offset in the overlay widget,
      the steps are now selected by a spinbox which behaves more or less logarithmically (0.1, 1, 5, 10, 50, 100 etc.)
    - the solid angle correction can now be switched off and on (please see the X-tab in the Integration View)

## Bug Fixes:
    - Overlays overlays are now recovered in order when opening a previously saved project with more than 10 overlays
    - cif and jcpds now als can handle trigonal symmetry (not only hexagonal)
    - auto zoom for cakes works now correctly when browsing through several files
    - entering numbers with a "," as a decimal separator work now correctly
    - loading new files with automatic background subtraction enabled will now correctly keep the x limits constant


# 0.4.0 (stable 07/26/2017)

## New Features:
    - added the possibility to work with multiple detector configurations at the same time (enabled by the C button on  the upper left)
    - all your work (including mutliple configurations) can be saved into project files
    - Dioptas can restore the previous working session on start
    - there is now a Dioptas icon instead of the generic python icon
    - unmasking geometric shapes are now green instead of red, to clarify which mode is selected
    - added the option to use arcs for masking
    - Dioptas is now completely Python 3.5/3.6 compatible
    - Dioptas can now save pattern files as "FXYE" files (GSAS-II format)
    - background subtracted or other modified (absorption correction etc.) Images can now be saved in batch mode
    - lists of phases including their pressure and temperature values can now be saved and loaded
    - the cake mode in the integration window now shows azimuth and tth/q axes
    - the cake image can now be shifted in azimuth, to have a better possibility to view features which where before only at the edges

## Bug Fixes:
    - fixed issues with changing units when having automatic background subtraction enabled
    - strong zooming into pattern view will not cause an error due to rescaling of the phase lines anymore
    - fixed issue with compromised Dioptas settings files, Dioptas will now start even if the settings can't be loaded
    - fixed strange masking artifacts at the edges when using the polygon masking tool
    - fixed undock/dock process, which was not working propoerly (only image was shown without pattern after docking the img widget
    - fixed image view scaling when loading differently sized images or switching between cake and image mode
    - fixed the CeO2 calibration file (there was a (9,0,0) reflection, which does not exist, instead at close position here should be a (8, 4, 0) reflection)


# 0.3.1 (stable 4/21/2016)

## New Features:
    - added compatibility for *.spe files (from Princeton instruments).
    - added capability for beamlines using epics and Image Tags to move to the position where the image was collected
    - added a new error Dialog which will popup on any error and show the error message, which then can be send to
    clemens.prescher@gmail.com, so I can fix it

## Bug Fixes:
    - cif files with errors in atomic coordinates can now be loaded too
    - adding AMCSD cif compatibility
    - fixed an error with file paths on windows causing it to not load any cif files
    - fixed some typos
    - fixing bug with fit2d parameter input
    - fixing bug with background image loading

# 0.3.0 (stable 02/11/2016)

## New Features:
    - It is now possible to load *.cif files in the Phase tab in the integration module. Loading a cif file will
      automatically calculate the intensities of all hkl with a given minimum intensity and minimum d spacing.
    - Dioptas can now load tiff tags and display them in a separate window. This is very practical if the beamline
      setup writes extra information as tags into the tif file such as position or exposure time etc.
    - The overlay tab has a new waterfall feature which automatically creates a waterfall plot with a given offset of
      all loaded overlays, whereby the most recent one is closest to the current integrated pattern.
    - the selected region and image shading is now synchronized between the calibration, mask and image view
    - negative pressures are now allowed for phases, although unphysical, it might give some hint when searching for a
      matching structure. The bulk modulus here is kept constant with pressures below 0. (Since the Birch Murnaghan EOS
      misbehaves at these conditions).
    - There is now a white cross marking the clicked position on the image in the Integration module. This marker will
      move to the corresponding position when switching between 'cake' and 'image' mode. This allows for tracking of
      individual peaks easily.
    - The default filename for the "save mask", "save pattern" and "save image" file dialogs will be the current image
      basename with the appropriate extension.
    - Added a lot more calibrants from pyFAI library. All NIST calibrants should be present with the appropriate
      references in the files.
    - Dioptas has been completely refactored by rewriting almost all of the GUI code, which will make future releases
      much faster, so stay tuned

## Bug Fixes:
    - mar345 files are now correctly loaded
    - autoprocessing of files, i.e. automatically loading newly collected files should now be much more reliable and
      especially the check for new files takes much less network bandwidth
    - jcpds editor content is now properly updated with the values of a newly added phase, which will be the new
      selected one
    - calculation of d-spacings for monoclinic space group jcpds is now correct, there was a sign error in the last term


# 0.2.4 (stable 04/13/2015)

## New Features:
    - Gui reorganization in the integration view: (1) autoscale button and transparent mask button are now shown within
      the image view. (2) the quick action buttons save image, save pattern etc. are now shown in the pattern widget
    - automatic background subtraction under BKG tab in the integration window. can also be accessed from
      the bg button in the pattern widget. By pressing inspect it shows both the original pattern and background
      within the limits for the extraction process. Please adjust the parameters according to your data.
    - File browsing step can now be modified to be different from 1 by entering an integer in the step text field
      below the arrows.
    - The absorption lengths for the diamond and seat corrections can now be adjusted. (They should be chosen according
      to the energy used for the XRD experiment)

# 0.2.3 (stable 12/09/2014)

## New Features:
    - Dioptas now saves the calibration when closing and will automatically open after restarting the program
    - mask files are now saved in a compressed tif format which reduces the file size from before 16 Mb to now less than
      40 kb
    - Added the option to use "Oblique Incidence Angle Detector Absorption correction", which basically corrects for the
      angle dependent path length in the detector scintillator and tries to correct the intensities correspondingly.
      This is especially useful at very high energies.
    - the cBN seat correction has been upgraded to include an Offset and Offset tilt parameter which corrects for
      misalignment of the sample in respect to the cBN seat
    - both, cBN seat correction and Oblique Incidence Angle Detector Absorption correction have been moved to a new tab
      ("Cor") in the Integration window

## Bug Fixes
    - fixed a bug which was causing Dioptas to crash when auto-processing new files and the rate of new files in the folder
      was faster than Dioptas could process them
    - fixed a bug which was causing the first calibration to fail for images with a different pixel size than 79um
    - fixed a bug which was causing the pixel size not to update when loading a calibration "*.poni" file
    - fixed a bug which was producing NAN intensity values in saved spectra when using masks

# 0.2.2 (stable 10/22/2014)

## New Features
    - defining an image as background prior to integration has been implemented. The controls can be found in the Bkg
        tab in the integration widget
    - it is now possible to do an absorption correction for cBN seats based on the geometry and rotation of the cell.
        Further details of the calculation can be found in the manual.
    - the pressure of each phase is now shown next to it in the pattern view and not only in the phase tab.
    - the image window in the integration widget can now be undocked, which creates a separate window for the image
        view whereby the windows are still connected (the green line). This enables the use of Dioptas over 2 Monitors
        for having a better overview.

## Bug Fixes
    - It is now possible to load images with different shapes, after calibration has been done. Although you might wanna
      use a different calibration for different detectors/images.
    - The gui has been updated to look reasonable good also on OS X 10.10 Yosemite.

# 0.2.1 (stable 09/09/2014)

## New Features
    - in the "X"-tab in the integration widget there are now two new options for integration available
    - it is now possible to change the number of bins for integration in the GUI (under X). After each change to the
        number the pattern will be integrated again automatically, to see the effects of different bin numbers easily.
    - the standard number of bin has been increased by a factor of approximately 0.9
    - additionally, the images can now be supersampled, up to a factor of 5. Supersampling divides a pixel into equal
        area subpixel which leads in the end to a smoother pattern. A supersampling factor of 2 will divide each pixel
        into four subpixel, a factor of 3 into 9 and so on. Depending on the initial image size the integration of the
        supersampled image can take very long (especially the first integration where the lookup table/sparse matrix is
        created). To reset the supersampling just type 1 into the spinbox.
    - the available pattern file formats checkboxes have been moved from the X menu to Spec to be more easily visible
    - the speed of the calibration procedure has been improved
    - it is now possible to leave the detector distance constant during calibration (Warning: This is the pyFAI geometry
        detector distance, not the fit2d detector distance. The Fit2D detector distance could still vary a little bit
        during the calibration procedure due to the different geometries of Fit2D and pyFAI)

## Bug Fixes:
    - MAC version - fixed a bug which caused the image to be flipped vertically
    - Polarization correction - fixed a bug which either caused the polarization correction to not be applied or being
                                with the wrong sign. Checked now everything again against Fit2D and should be working
                                correctly
    - Saving the pattern in the vector based .svg format is now working


# 0.2.0 (stable 08/29/2014)
    - Finished the JCPDS editor (pops up when you select a phase and select edit)
    - Fixed several small bugs using jcpds files (triclinic works now)
    - added inverse grey scale to the available image color scales

# 0.1.5 (stable 08/20/2014)

## Bug Fixes:
    - Fixed the header format of xy files in windows
    - .xy header now correctly shows the polarization factor
    - the temperature step in the user interface for phases now correctly changes the step of the temperature spin box
    - erroneous jcpds files will now give an error messagebox and will be handled correctly - no restart needed anymore

# 0.1.4 (stable 08/10/2014)

## New Features:
    - spectra can now be saved in .xy, .chi and dat format
    - they can be selected for automatic creation of pattern files when loading images

## Bug Fixes:
    - auto - creation of pattern now also works when the folder was inserted by typing it into the line item.
    - loading a new file was always creating an index by time of all the files, which slowed down the loading of new files
      considerably. - this is now done only once when loading a file from a new folder
    - setting the image working directory by typing it into the textfield now works correctly
    - changing the working directory while having enabled autoprocess will not load a file automatically anymore
    - the selection color in tables of integration view has been changed to orange, in order to overcome the visibility
      problem of the Checkboxes on Windows
    - browsing in cake mode did reset the integrator everytime which made it very slow. Fixed this bug, browsing in cake
      mode should now be almost as fast as only using integration


# 0.1.3 (stable 08/05/2014)

## New Features
    - implemented option to use mask for calibration refinement

## Bug Fixes:
    - fixed a bug when using phase lines which caused the pattern plot to flow