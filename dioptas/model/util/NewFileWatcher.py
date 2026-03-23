# SPDX-License-Identifier: MIT

from __future__ import annotations

import logging
import os
import time
import threading

import queue

from watchdog.observers import Observer
from watchdog.events import FileSystemEvent, PatternMatchingEventHandler

from . import Signal

logger = logging.getLogger(__name__)


class NewFileInDirectoryWatcher:
    """
    This class watches a given filepath for any new files with a given file extension added to it.

    Typical usage::
        def callback_fcn(path):
            print(path)

        watcher = NewFileInDirectoryWatcher(example_path, file_types = ['.tif', '.tiff'])
        watcher.file_added.connect(callback_fcn)

    """

    def __init__(
        self,
        path: str | None = None,
        file_types: list[str] | None = None,
        activate: bool = False,
    ) -> None:
        """
        :param path: path to folder which will be watched
        :param file_types: list of file types which will be watched for, e.g. ['.tif', '.jpeg']
        :param activate: whether the Watcher will already emit signals
        """

        if path is None:
            path = os.getcwd()
        self._path: str = path

        if file_types is None:
            self.file_types: set[str] = set([])
            self.patterns: str | list[str] = "*"
        else:
            self.file_types = set(file_types)
            self.patterns = ["*." + file_type for file_type in file_types]

        self.event_handler: PatternMatchingEventHandler = PatternMatchingEventHandler(
            patterns=self.patterns
        )
        self.event_handler.on_created = self.on_file_created

        self.active: bool = False
        if activate:
            self.activate()

        self.file_added: Signal = Signal(str)  # to be used signal from outside
        self.filepath_queue: queue.Queue[str] = queue.Queue()

    def on_file_created(self, event: FileSystemEvent) -> None:
        """
        Called when a new file is created in the watched directory. This function will be called by the watchdog
        event handle. We check whether the file is fully written by observing whether the file size changes. If the
        file size is not changing within 10ms, we assume that the file is fully written and emit the file_added signal.
        """
        logger.info("New file detected: %s", event.src_path)
        file_path = os.path.abspath(event.src_path)
        try:
            file_size = os.stat(file_path).st_size
        except FileNotFoundError:
            return
        while True:
            try:
                new_size = os.stat(file_path).st_size
            except FileNotFoundError:
                return
            if new_size == file_size:
                break
            file_size = new_size
            time.sleep(0.01)

        self.filepath_queue.put(os.path.abspath(file_path))

    def activate(self) -> None:
        if not self.active:
            self.active = True
            self.queue_thread: threading.Thread = threading.Thread(
                target=self.process_events, daemon=True
            )
            self.queue_thread.start()
            self._start_observing()

    def deactivate(self) -> None:
        if self.active:
            self.active = False
            self._stop_observing()
            self.queue_thread.join()

    def _start_observing(self) -> None:
        self.observer: Observer = Observer()
        self.observer.schedule(self.event_handler, self.path)
        self.observer.start()

    def _stop_observing(self) -> None:
        if self.observer.is_alive():
            self.observer.stop()
            self.observer.join()

    @property
    def path(self) -> str:
        return self._path

    @path.setter
    def path(self, new_path: str) -> None:
        if self.active:
            self._stop_observing()
        self._path = new_path
        if self.active:
            self._start_observing()

    def process_events(self) -> None:
        """continuously check for new files and emit the file_added signal"""
        while self.active:
            try:
                file_path = self.filepath_queue.get(False)  # doesn't block
            except queue.Empty:  # raised when the queue is empty
                time.sleep(0.05)
                continue

            self.file_added.emit(file_path)

    def __del__(self) -> None:
        """Stop the observer thread when the object is deleted."""
        self.deactivate()
        self.file_added.clear()
