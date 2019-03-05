# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
# Principal author: Clemens Prescher (clemens.prescher@gmail.com)
# Copyright (C) 2014-2019 GSECARS, University of Chicago, USA
# Copyright (C) 2015-2018 Institute for Geology and Mineralogy, University of Cologne, Germany
# Copyright (C) 2019 DESY, Hamburg, Germany
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

import os
import time

from qtpy import QtCore


class NewFileInDirectoryWatcher(QtCore.QObject):
    """
    This class watches a given filepath for any new files with a given file extension added to it.

    Typical usage::
        def callback_fcn(path):
            print(path)

        watcher = NewFileInDirectoryWatcher(example_path, file_types = ['.tif', '.tiff'])
        watcher.file_added.connect(callback_fcn)

    """
    file_added = QtCore.Signal(str)

    def __init__(self, path=None, file_types=None, activate=False):
        """
        :param path: path to folder which will be watched
        :param file_types: list of file types which will be watched for, e.g. ['.tif', '.jpeg]
        :param activate: whether or not the Watcher will already emit signals
        """
        super(NewFileInDirectoryWatcher, self).__init__()

        self._file_system_watcher = QtCore.QFileSystemWatcher()
        if path is None:
            path = os.getcwd()
        self._file_system_watcher.addPath(path)
        self._files_in_path = os.listdir(path)

        self._file_system_watcher.directoryChanged.connect(self._directory_changed)
        self._file_system_watcher.blockSignals(~activate)

        self._file_changed_watcher = QtCore.QFileSystemWatcher()
        self._file_changed_watcher.fileChanged.connect(self._file_changed)

        if file_types is None:
            self.file_types = set([])
        else:
            self.file_types = set(file_types)

    @property
    def path(self):
        return self._file_system_watcher.directories()[0]

    @path.setter
    def path(self, new_path):
        if len(self._file_system_watcher.directories()):
            self._file_system_watcher.removePath(self._file_system_watcher.directories()[0])
        self._file_system_watcher.addPath(new_path)
        self._files_in_path = os.listdir(new_path)

    def activate(self):
        """
        activates the watcher to emit signals when a new file is added
        """
        self._file_system_watcher.blockSignals(False)

    def deactivate(self):
        """
        deactivates the watcher so it will not emit a signal when a new file is added
        """
        self._file_system_watcher.blockSignals(True)

    def _directory_changed(self):
        """
        internal function which determines whether the change in directory is an actual new file. If a new file was
        detected it looks if it has the right extension and checks the file size. When the file is not completely
        written yet it watches it for changes and will call the _file_changed function which wil acctually emit the
        signal.
        """
        files_now = os.listdir(self.path)
        files_added = [f for f in files_now if not f in self._files_in_path]

        if len(files_added) > 0:
            new_file_path = os.path.join(str(self.path), files_added[-1])

            # abort if the new_file added is actually a directory...
            if os.path.isdir(new_file_path):
                self._files_in_path = files_now
                return

            valid_file = False
            for file_type in self.file_types:
                if new_file_path.endswith(file_type):
                    valid_file = True
                    break

            if valid_file:
                if self._file_closed(new_file_path):
                    self.file_added.emit(new_file_path)
                else:
                    self._file_changed_watcher.addPath(new_file_path)
            self._files_in_path = files_now

    def _file_closed(self, path):
        """
        Checks whether a file is used by other processes.
        """
        # since it is hard to ask the operating system for this directly, the change in file size is checked.
        size1 = os.stat(path).st_size
        time.sleep(0.10)
        size2 = os.stat(path).st_size

        return size1 == size2

    def _file_changed(self, path):
        """
        internal function callback for the file_changed_watcher. The watcher is invoked if a new file is detected but
        the file is still below 100 bytes (basically only the file handle created, and no data yet). The _file_changed
        callback function is then invoked when the data is completely written into the file. To ensure that everything
        is correct this function also checks whether the file is above 100 byte after the system sends a file changed
        signal.
        :param path: file path of the watched file
        """
        if self._file_closed(path):
            self.file_added.emit(path)
            self._file_changed_watcher.removePath(path)
