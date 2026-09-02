# SPDX-License-Identifier: MIT

from __future__ import annotations

import logging
import os
import stat
import threading

from . import Signal

logger = logging.getLogger(__name__)


class NewFileInDirectoryWatcher:
    """
    This class watches a given filepath for any new files with a given file
    extension added to it.

    It polls the directory instead of subscribing to OS file events on
    purpose: inotify (Linux) and FSEvents (macOS) only report changes made
    through the local kernel. At a beamline the detector server writes to
    network storage and Dioptas reads a client mount, where such events never
    arrive at all — while a fresh directory listing sees the new file on any
    filesystem.

    A new file is announced only once its size and modification time have
    stayed the same over two consecutive polls and it is not empty, so a file
    still being written — network filesystems flush in bursts — is left alone
    until the writer is done.

    Typical usage::
        def callback_fcn(path):
            print(path)

        watcher = NewFileInDirectoryWatcher(example_path, file_types = ['.tif', '.tiff'])
        watcher.file_added.connect(callback_fcn)

    """

    def __init__(
        self,
        path: str | os.PathLike | None = None,
        file_types: list[str] | None = None,
        activate: bool = False,
        poll_interval: float = 1.0,
    ) -> None:
        """
        :param path: path to folder which will be watched
        :param file_types: list of file types which will be watched for, e.g. ['.tif', '.jpeg']
        :param activate: whether the Watcher will already emit signals
        :param poll_interval: seconds between two looks at the directory
        """
        if path is None:
            path = os.getcwd()
        self._path: str = str(path)

        self._file_types: set[str] = set()
        self._suffixes: tuple[str, ...] = ()
        self.file_types = file_types or []
        self.poll_interval: float = poll_interval

        self.file_added: Signal = Signal(str)  # to be used signal from outside

        self.active: bool = False
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        # files already announced (or present before watching started) and
        # files seen once but not yet stable, with their (size, mtime)
        self._known: set[str] = set()
        self._pending: dict[str, tuple[int, float]] = {}

        if activate:
            self.activate()

    def activate(self) -> None:
        if self.active:
            return
        self.active = True
        self._stop_event.clear()
        with self._lock:
            self._take_baseline()
        self._poll_thread: threading.Thread = threading.Thread(
            target=self._poll_loop, daemon=True
        )
        self._poll_thread.start()

    def deactivate(self) -> None:
        if not self.active:
            return
        self.active = False
        self._stop_event.set()
        # file_added handlers run on the poll thread; one of them turning
        # the watcher off must not join the very thread it runs on
        if threading.current_thread() is not self._poll_thread:
            self._poll_thread.join()

    @property
    def path(self) -> str:
        return self._path

    @path.setter
    def path(self, new_path: str | os.PathLike) -> None:
        new_path = str(new_path)
        with self._lock:
            if os.path.abspath(new_path) == os.path.abspath(self._path):
                return
            self._path = new_path
            # only files added from now on count, as for the initial path
            self._take_baseline()

    @property
    def file_types(self) -> set[str]:
        return self._file_types

    @file_types.setter
    def file_types(self, values) -> None:
        self._file_types = set(values) if values else set()
        self._suffixes = tuple(
            "." + value.lower().lstrip(".")
            for value in sorted(self._file_types)
        )

    def _poll_loop(self) -> None:
        # Event.wait doubles as an interruptible sleep, so deactivate() never
        # has to wait out a full interval
        while not self._stop_event.wait(self.poll_interval):
            self.poll_once()

    def poll_once(self) -> None:
        """One look at the directory; called repeatedly by the poll thread.

        Emits file_added for every file that appeared since watching started
        and has finished being written (stats unchanged since the last look).
        """
        with self._lock:
            scan = self._scan()
            if scan is None:
                return
            current_names, candidate_stats = scan

            # a vanished file may be re-created later; that counts as new again
            self._known &= current_names
            for name in list(self._pending):
                if name not in current_names:
                    del self._pending[name]

            ready: list[tuple[float, str]] = []
            for name, file_stat in candidate_stats.items():
                if self._pending.get(name) == file_stat and file_stat[0] > 0:
                    ready.append((file_stat[1], name))
                    self._known.add(name)
                    del self._pending[name]
                else:
                    self._pending[name] = file_stat

            new_file_paths = [
                os.path.abspath(os.path.join(self._path, name))
                for _, name in sorted(ready)
            ]

        # emitted outside the lock so a handler may touch the watcher
        for file_path in new_file_paths:
            logger.info("New file detected: %s", file_path)
            self.file_added.emit(file_path)

    def _scan(
        self,
    ) -> tuple[set[str], dict[str, tuple[int, float]]] | None:
        """List matching names and stat only not-yet-announced files.

        Opens the directory fresh each time — this is also what defeats the
        NFS attribute cache. Avoiding ``stat`` calls for every known image is
        important for large beamline directories and network mounts. Returns
        None if the directory cannot be read.
        """
        current_names = self._matching_names()
        if current_names is None:
            return None

        candidate_stats: dict[str, tuple[int, float]] = {}
        for name in current_names - self._known:
            try:
                file_stat = os.stat(os.path.join(self._path, name))
            except OSError:
                continue
            if stat.S_ISREG(file_stat.st_mode):
                candidate_stats[name] = (
                    file_stat.st_size,
                    file_stat.st_mtime,
                )
        return current_names, candidate_stats

    def _matching_names(self) -> set[str] | None:
        try:
            # listdir performs the directory walk in C. This matters for
            # directories containing tens of thousands of detector images:
            # iterating DirEntry objects in Python once per second can contend
            # with the Qt thread even before any stat calls are made.
            return {
                name for name in os.listdir(self._path) if self._matches(name)
            }
        except OSError:
            logger.debug("Cannot list watched directory: %s", self._path)
            return None

    def _matches(self, filename: str) -> bool:
        if not self._suffixes:
            return True
        return filename.lower().endswith(self._suffixes)

    def _take_baseline(self) -> None:
        """Remembers the files already there, which are never announced."""
        names = self._matching_names()
        self._known = names if names else set()
        self._pending = {}

    def __del__(self) -> None:
        """Stop the poll thread when the object is deleted."""
        try:
            self.deactivate()
            self.file_added.clear()
        except Exception:
            pass
