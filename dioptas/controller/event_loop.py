# SPDX-License-Identifier: MIT

"""Lightweight Qt event-loop responsiveness instrumentation."""

from __future__ import annotations

import logging
import time
from collections import deque
from collections.abc import Callable

from qtpy import QtCore

logger = logging.getLogger(__name__)


class RecentLogHandler(logging.Handler):
    """Retain recent existing Dioptas logs without emitting more output."""

    def __init__(self, capacity: int = 2) -> None:
        super().__init__(level=logging.NOTSET)
        self._records: deque[str] = deque(maxlen=capacity)

    def emit(self, record: logging.LogRecord) -> None:
        # A previous stall warning is not useful evidence for the next one.
        if record.name == __name__:
            return
        message = " ".join(record.getMessage().split())[:240]
        if message:
            self._records.append(f"[{record.name}] {message}")

    def snapshot(self) -> tuple[str, ...]:
        self.acquire()
        try:
            return tuple(self._records)
        finally:
            self.release()


class EventLoopLagMonitor(QtCore.QObject):
    """Measure delays between Qt timer callbacks.

    The monitor does not make scheduling decisions.  It records enough state
    to make responsiveness regressions visible in logs and to support focused
    performance tests without adding a profiler to normal application runs.
    """

    stalled = QtCore.Signal(float)

    def __init__(
        self,
        parent: QtCore.QObject | None = None,
        *,
        interval_ms: int = 50,
        warning_threshold_ms: int = 250,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        super().__init__(parent)
        if interval_ms <= 0:
            raise ValueError("interval_ms must be positive")
        if warning_threshold_ms < 0:
            raise ValueError("warning_threshold_ms cannot be negative")

        self.interval_ms = interval_ms
        self.warning_threshold_ms = warning_threshold_ms
        self.last_lag_ms = 0.0
        self.max_lag_ms = 0.0
        self._clock = clock
        self._expected_at: float | None = None
        self._recent_logs = RecentLogHandler(capacity=2)
        self._log_handler_installed = False

        self._timer = QtCore.QTimer(self)
        self._timer.setTimerType(QtCore.Qt.PreciseTimer)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._sample)

    @property
    def is_active(self) -> bool:
        return self._timer.isActive()

    def start(self) -> None:
        """Start monitoring and reset the sampling deadline."""
        now = self._clock()
        self._expected_at = now + self.interval_ms / 1000.0
        if not self._log_handler_installed:
            logging.getLogger("dioptas").addHandler(self._recent_logs)
            self._log_handler_installed = True
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()
        self._expected_at = None
        if self._log_handler_installed:
            logging.getLogger("dioptas").removeHandler(self._recent_logs)
            self._log_handler_installed = False

    @QtCore.Slot()
    def _sample(self) -> None:
        now = self._clock()
        if self._expected_at is None:
            self._expected_at = now + self.interval_ms / 1000.0
            return

        lag_ms = max(0.0, (now - self._expected_at) * 1000.0)
        self.last_lag_ms = lag_ms
        self.max_lag_ms = max(self.max_lag_ms, lag_ms)
        # Reset relative to the actual callback time.  Otherwise one long
        # stall would be reported repeatedly while the timer catches up.
        self._expected_at = now + self.interval_ms / 1000.0

        if lag_ms >= self.warning_threshold_ms:
            recent_logs = self._recent_logs.snapshot()
            if recent_logs:
                logger.warning(
                    "Qt event loop stalled for %.0f ms; preceding logs: %s",
                    lag_ms,
                    " | ".join(recent_logs),
                )
            else:
                logger.warning("Qt event loop stalled for %.0f ms", lag_ms)
            self.stalled.emit(lag_ms)
