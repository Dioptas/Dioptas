0.2.1 (development)
-------------------
    - it is now possible to change the number of bins for integration in the GUI (under X). After each change to the
        number the spectrum will be integrated again automatically, to see the effects of different bin numbers easily.
    - the available spectrum file formats checkboxes have been moved from the X menu to Spec to be more easily visible

Bugfixes:
    - MAC version - fixed a bug which caused the image to be flipped vertically
    - Polarization correction - fixed a bug which either caused the polarization correction to not be applied or being
                                with the wrong sign. Checked now everything again against fit2d and should be working
                                correctly


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