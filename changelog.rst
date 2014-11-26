0.2.3 development
-----------------
    - Dioptas now saves the state of the program when closing. Reopening will automatically load the last loaded image,
      calibration, mask and spectrum
    - mask files are now saved in a compressed tif format which reduces the file size from before 16 Mb to now less than
      40 kb

Bugfixes
    - fixed a bug which was causing Dioptas to crash when auto-processing new files and the rate of new files in the folder
      was faster than Dioptas could process them
    - fixed a bug which was causing the first calibration to fail for images with a different pixel size than 79um
    - fixed a bug which was producing NAN intensity values in saved spectra when using masks

0.2.2 (stable 10/22/2014)
-------------------------
    - defining an image as background prior to integration has been implemented. The controls can be found in the Bkg
        tab in the integration widget
    - it is now possible to do an absorption correction for cBN seats based on the geometry and rotation of the cell.
        Further details of the calculation can be found in the manual.
    - the pressure of each phase is now shown next to it in the spectrum view and not only in the phase tab.
    - the image window in the integration widget can now be undocked, which creates a separate window for the image
        view whereby the windows are still connected (the green line). This enables the use of Dioptas over 2 Monitors
        for having a better overview.

Bugfixes
    - It is now possible to load images with different shapes, after calibration has been done. Although you might wanna
      use a different calibration for different detectors/images.
    - The gui has been updated to look reasonable good also on OS X 10.10 Yosemite.

0.2.1 (stable 09/09/2014)
-------------------------
    - in the "X"-tab in the integration widget there are now two new options for integration available
    - it is now possible to change the number of bins for integration in the GUI (under X). After each change to the
        number the spectrum will be integrated again automatically, to see the effects of different bin numbers easily.
    - the standard number of bin has been increased by a factor of approximately 0.9
    - additionally, the images can now be supersampled, up to a factor of 5. Supersampling divides a pixel into equal
        area subpixel which leads in the end to a smoother spectrum. A supersampling factor of 2 will divide each pixel
        into four subpixel, a factor of 3 into 9 and so on. Depending on the initial image size the integration of the
        supersampled image can take very long (especially the first integration where the lookup table/sparse matrix is
        created). To reset the supersampling just type 1 into the spinbox.
    - the available spectrum file formats checkboxes have been moved from the X menu to Spec to be more easily visible
    - the speed of the calibration procedure has been improved
    - it is now possible to leave the detector distance constant during calibration (Warning: This is the pyFAI geometry
        detector distance, not the fit2d detector distance. The Fit2D detector distance could still vary a little bit
        during the calibration procedure due to the different geometries of Fit2D and pyFAI)

Bugfixes:
    - MAC version - fixed a bug which caused the image to be flipped vertically
    - Polarization correction - fixed a bug which either caused the polarization correction to not be applied or being
                                with the wrong sign. Checked now everything again against Fit2D and should be working
                                correctly
    - Saving the spectrum in the vector based .svg format is now working


0.2.0 (stable 08/29/2014)
-------------------------
    - Finished the JCPDS editor (pops up when you select a phase and select edit)
    - Fixed several small bugs using jcpds files (triclinic works now)
    - added inverse grey scale to the available image color scales

0.1.5 (stable 08/20/2014)
-------------------------

Bugfixes:
    - Fixed the header format of xy files in windows
    - .xy header now correctly shows the polarization factor
    - the temperature step in the user interface for phases now correctly changes the step of the temperature spin box
    - erroneous jcpds files will now give an error messagebox and will be handled correctly - no restart needed anymore

0.1.4 (stable 08/10/2014)
-------------------------

- spectra can now be saved in .xy, .chi and dat format
- they can be selected for automatic creation of spectrum files when loading images

Bugfixes:
    - auto - creation of spectrum now also works when the folder was inserted by typing it into the line item.
    - loading a new file was always creating an index by time of all the files, which slowed down the loading of new files
      considerably. - this is now done only once when loading a file from a new folder
    - setting the image working directory by typing it into the textfield now works correctly
    - changing the working directory while having enabled autoprocess will not load a file automatically anymore
    - the selection color in tables of integration view has been changed to orange, in order to overcome the visibility
      problem of the Checkboxes on Windows
    - browsing in cake mode did reset the integrator everytime which made it very slow. Fixed this bug, browsing in cake
      mode should now be almost as fast as only using integration


0.1.3 (stable 08/05/2014)
-------------------------
    - implemented option to use mask for calibration refinement

Bugfixes:
    - fixed a bug when using phase lines which caused the spectrum plot to flow