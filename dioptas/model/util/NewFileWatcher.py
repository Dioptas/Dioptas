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

import os
import time
import threading

import queue

from qtpy import QtCore

from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler

from . import Signal


class NewFileInDirectoryWatcher(QtCore.QObject):
    """
    This class watches a given filepath for any new files with a given file extension added to it.

    Typical usage::
        def callback_fcn(path):
            print(path)

        watcher = NewFileInDirectoryWatcher(example_path, file_types = ['.tif', '.tiff'])
        watcher.file_added.connect(callback_fcn)

    """
    _file_added_qt = QtCore.Signal(str)  # used internally for inside of an qt application to avoid thread problems

    def __init__(self, path=None, file_types=None, activate=False):
        """
        :param path: path to folder which will be watched
        :param file_types: list of file types which will be watched for, e.g. ['.tif', '.jpeg']
        :param activate: whether the Watcher will already emit signals
        """
        super(NewFileInDirectoryWatcher, self).__init__()

        if path is None:
            path = os.getcwd()
        self._path = path

        if file_types is None:
            self.file_types = set([])
            self.patterns = '*'
        else:
            self.file_types = set(file_types)
            self.patterns = ['*.' + file_type for file_type in file_types]

        self.event_handler = PatternMatchingEventHandler(self.patterns)
        self.event_handler.on_created = self.on_file_created

        self.active = False
        if activate:
            self.activate()

        self.file_added = Signal(str)  # to be used signal from outside
        self._file_added_qt.connect(self.file_added.emit)
        self.filepath_queue = queue.Queue()

    def on_file_created(self, event):
        """
        Called when a new file is created in the watched directory. This function will be called by the watchdog
        event handle. We check whether the file is fully written by observing whether the file size changes. If the
        file size is not changing within 10ms, we assume that the file is fully written and emit the file_added signal.
        """
        file_path = os.path.abspath(event.src_path)
        file_size = -1
        while file_size != os.stat(file_path).st_size:
            file_size = os.stat(file_path).st_size
            time.sleep(0.01)

        self.filepath_queue.put(os.path.abspath(file_path))

    def activate(self):
        if not self.active:
            self.active = True
            self.queue_thread = threading.Thread(target=self.process_events, daemon=True)
            self.queue_thread.start()
            self._start_observing()

    def deactivate(self):
        if self.active:
            self.active = False
            self._stop_observing()
            self.queue_thread.join()

    def _start_observing(self):
        self.observer = Observer()
        self.observer.schedule(self.event_handler, self.path)
        self.observer.start()

    def _stop_observing(self):
        if self.observer.is_alive():
            self.observer.stop()
            self.observer.join()

    @property
    def path(self):
        return self._path

    @path.setter
    def path(self, new_path):
        if self.active:
            self._stop_observing()
        self._path = new_path
        if self.active:
            self._start_observing()

    def process_events(self):
        """continuously check for new files and emit the file_added signal"""
        while self.active:
            try:
                file_path = self.filepath_queue.get(False)  # doesn't block
            except queue.Empty:  # raised when the queue is empty
                time.sleep(0.05)
                continue

            if QtCore.QCoreApplication.instance() is not None:
                self._file_added_qt.emit(file_path)
            else:
                self.file_added.emit(file_path)

    def __del__(self):
        """Stop the observer thread when the object is deleted."""
        self.deactivate()
        self.file_added.clear()
