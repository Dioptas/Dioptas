# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
# Principal author: Clemens Prescher (clemens.prescher@gmail.com)
# Copyright (C) 2014-2019 GSECARS, University of Chicago, USA
# Copyright (C) 2015-2018 Institute for Geology and Mineralogy, University of Cologne, Germany
# Copyright (C) 2019-2020 DESY, Hamburg, Germany
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from ..util import Signal
from ..util.NewFileWatcher import NewFileInDirectoryWatcher


class AutoProcessor:
    """
    Handles automatic file processing and directory watching.
    Manages automatic loading of new files and directory monitoring.
    """

    def __init__(self, load_callback=None):
        """
        Initialize AutoProcessor with optional load callback.
        :param load_callback: callback function to call when new file is detected
        """
        self._autoprocess = False
        self._load_callback = load_callback
        
        # TODO: watching a directory should be open to any file type - an extension should be added when a
        # new file is loaded with a previous non-existing file extension
        self._directory_watcher = NewFileInDirectoryWatcher(
            file_types=[
                "img",
                "sfrm",
                "dm3",
                "edf",
                "xml",
                "cbf",
                "kccd",
                "msk",
                "spr",
                "tif",
                "tiff",
                "mccd",
                "mar3450",
                "pnm",
                "spe",
            ]
        )
        
        if load_callback:
            self._directory_watcher.file_added.connect(load_callback)
        
        # Signals
        self.autoprocess_changed = Signal()

    @property
    def autoprocess(self):
        """Get autoprocess state."""
        return self._autoprocess

    @autoprocess.setter
    def autoprocess(self, new_val):
        """Set autoprocess state and activate/deactivate directory watcher."""
        self._autoprocess = new_val
        if new_val:
            self._directory_watcher.activate()
        else:
            self._directory_watcher.deactivate()
        self.autoprocess_changed.emit()

    def set_directory_path(self, path):
        """
        Set the directory path to watch for new files.
        :param path: directory path to watch
        """
        self._directory_watcher.path = path

    def set_load_callback(self, callback):
        """
        Set the callback function to call when a new file is detected.
        :param callback: function to call with filename as parameter
        """
        if self._load_callback:
            self._directory_watcher.file_added.disconnect(self._load_callback)
        
        self._load_callback = callback
        if callback:
            self._directory_watcher.file_added.connect(callback) 