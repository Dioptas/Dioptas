# SPDX-License-Identifier: MIT

from __future__ import annotations

import logging
import os
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

        self.file_types: set[str] = set(file_types) if file_types else set()
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
        with self._lock:
            self._path = str(new_path)
            # only files added from now on count, as for the initial path
            self._take_baseline()

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
            entries = self._scan()
            if entries is None:
                return

            # a vanished file may be re-created later; that counts as new again
            self._known &= set(entries)
            for name in list(self._pending):
                if name not in entries:
                    del self._pending[name]

            ready: list[tuple[float, str]] = []
            for name, file_stat in entries.items():
                if name in self._known:
                    continue
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

    def _scan(self) -> dict[str, tuple[int, float]] | None:
        """Lists the matching files with their (size, mtime).

        Opens the directory fresh each time — this is also what defeats the
        NFS attribute cache. Returns None if the directory cannot be read.
        """
        try:
            with os.scandir(self._path) as dir_iterator:
                entries: dict[str, tuple[int, float]] = {}
                for entry in dir_iterator:
                    if not self._matches(entry.name):
                        continue
                    try:
                        if not entry.is_file():
                            continue
                        file_stat = entry.stat()
                    except OSError:
                        continue
                    entries[entry.name] = (file_stat.st_size, file_stat.st_mtime)
                return entries
        except OSError:
            logger.debug("Cannot list watched directory: %s", self._path)
            return None

    def _matches(self, filename: str) -> bool:
        if not self.file_types:
            return True
        lowered = filename.lower()
        return any(
            lowered.endswith("." + file_type.lower().lstrip("."))
            for file_type in self.file_types
        )

    def _take_baseline(self) -> None:
        """Remembers the files already there, which are never announced."""
        entries = self._scan()
        self._known = set(entries) if entries else set()
        self._pending = {}

    def __del__(self) -> None:
        """Stop the poll thread when the object is deleted."""
        try:
            self.deactivate()
            self.file_added.clear()
        except Exception:
            pass
