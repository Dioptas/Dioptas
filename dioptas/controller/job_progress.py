# SPDX-License-Identifier: MIT

"""Thread-safe progress and cancellation bridge for background jobs."""

from __future__ import annotations

import threading
import time

from qtpy import QtCore


class JobProgress(QtCore.QObject):
    value_changed = QtCore.Signal(int)
    label_changed = QtCore.Signal(str)

    def __init__(self, parent=None, *, total: int | None = None) -> None:
        super().__init__(parent)
        self.total = total
        self._cancelled = threading.Event()
        self._started_at = time.monotonic()

    @property
    def was_cancelled(self) -> bool:
        return self._cancelled.is_set()

    @QtCore.Slot()
    def cancel(self) -> None:
        self._cancelled.set()

    def update(self, current: int, total: int | None = None) -> bool:
        """Worker-thread callback returning whether work should continue."""
        # Check before emitting Qt signals. During shutdown the dialog (and
        # therefore this QObject's C++ peer) may already be closing while the
        # worker reaches its next progress callback.
        if self.was_cancelled:
            return False
        total = self.total if total is None else total
        total = 0 if total is None else total
        try:
            if total:
                self.value_changed.emit(int(current / total * 100))
            else:
                self.value_changed.emit(int(current))
            elapsed = time.monotonic() - self._started_at
            rate = current / elapsed if elapsed > 0 else 0
            total_label = str(total) if total else "?"
            self.label_changed.emit(
                f"Image {current} of {total_label}\n"
                f"{elapsed:.1f}s elapsed\n"
                f"{rate:.1f} img/s"
            )
        except RuntimeError:
            # The GUI owner was destroyed between the cancellation check and
            # signal delivery. Treat that exactly like cancellation.
            self.cancel()
            return False
        return not self.was_cancelled
