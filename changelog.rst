1.4 (development)
-----------------

Bugfixes:
    - auto - creation of spectrum now also works when the folder was inserted by typing it into the line item.
    - loading a new file was always creating an index by time of all the files, which slowed down the loading of new files
      considerably. - this is now done only once when loading a file from a new folder
    - setting the image working directory by typing it into the textfield now works correctly
    - changing the working directory while having enabled autoprocess will not load a file automatically anymore


1.3 (stable 08/05/2014)
-----------------------
    - implemented option to use mask for calibration refinement

Bugfixes:
    - fixed a bug when using phase lines which caused the spectrum plot to flow