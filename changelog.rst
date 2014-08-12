0.1.5 (development)
-------------------

Bugfixes:
    - Fixed the header format of xy files in windows
    - .xy header now correctly shows the polarization factor

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