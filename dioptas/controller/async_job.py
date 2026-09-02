# SPDX-License-Identifier: MIT

"""Small Qt thread-pool adapter with GUI-thread result delivery."""

from __future__ import annotations

import logging
import traceback
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from qtpy import QtCore

logger = logging.getLogger(__name__)

# A runner is normally the owner of its jobs. Keep an additional process-wide
# reference while run() is active so closing a window cannot destroy the Python
# signal wrapper out from under a still-running QRunnable.
_RUNNING_JOBS: set[FunctionJob] = set()


class JobSignals(QtCore.QObject):
    succeeded = QtCore.Signal(int, object)
    failed = QtCore.Signal(int, object, str)


class FunctionJob(QtCore.QRunnable):
    """Run a no-argument callable and report its value or exception."""

    def __init__(self, job_id: int, fn: Callable[[], Any]) -> None:
        super().__init__()
        self.job_id = job_id
        self.fn = fn
        self.signals = JobSignals()
        self.setAutoDelete(False)

    @QtCore.Slot()
    def run(self) -> None:
        try:
            result = self.fn()
        except Exception as exc:
            try:
                self.signals.failed.emit(self.job_id, exc, traceback.format_exc())
            except RuntimeError:
                logger.debug("Job receiver was destroyed before failure delivery")
        else:
            try:
                self.signals.succeeded.emit(self.job_id, result)
            except RuntimeError:
                logger.debug("Job receiver was destroyed before result delivery")
        finally:
            _RUNNING_JOBS.discard(self)


class AsyncJobRunner(QtCore.QObject):
    """Submit functions to a Qt thread pool and marshal results to Qt.

    ``succeeded`` and ``failed`` are delivered on the runner's thread (the GUI
    thread in application use).  Jobs are retained until their terminal
    signal is handled, avoiding the common QRunnable/Signal garbage-collection
    race in Python Qt bindings.
    """

    succeeded = QtCore.Signal(int, object)
    failed = QtCore.Signal(int, object, str)
    busy_changed = QtCore.Signal(bool)

    def __init__(
        self,
        parent: QtCore.QObject | None = None,
        *,
        thread_pool: QtCore.QThreadPool | None = None,
        run_inline: bool = False,
    ) -> None:
        super().__init__(parent)
        self._thread_pool = thread_pool or QtCore.QThreadPool.globalInstance()
        self._run_inline = run_inline
        self._next_job_id = 0
        self._jobs: dict[int, FunctionJob] = {}

    @property
    def is_busy(self) -> bool:
        return bool(self._jobs)

    def submit(self, fn: Callable[[], Any]) -> int:
        self._next_job_id += 1
        job_id = self._next_job_id
        job = FunctionJob(job_id, fn)
        job.signals.succeeded.connect(self._on_succeeded)
        job.signals.failed.connect(self._on_failed)
        was_busy = self.is_busy
        self._jobs[job_id] = job
        _RUNNING_JOBS.add(job)
        if not was_busy:
            self.busy_changed.emit(True)

        if self._run_inline:
            job.run()
        else:
            self._thread_pool.start(job)
        return job_id

    @QtCore.Slot(int, object)
    def _on_succeeded(self, job_id: int, result: object) -> None:
        self._finish(job_id)
        self.succeeded.emit(job_id, result)

    @QtCore.Slot(int, object, str)
    def _on_failed(self, job_id: int, exc: object, traceback_text: str) -> None:
        self._finish(job_id)
        logger.error("Background job %s failed\n%s", job_id, traceback_text)
        self.failed.emit(job_id, exc, traceback_text)

    def _finish(self, job_id: int) -> None:
        self._jobs.pop(job_id, None)
        if not self._jobs:
            self.busy_changed.emit(False)


class DedicatedAsyncJobRunner(QtCore.QObject):
    """Run jobs serially on one persistent native thread.

    This is required for native objects such as Dioptrin's PyO3 integrator,
    which must be used and destroyed on the thread that created them. The
    optional finalizer is queued after all work and runs on that same thread.
    """

    succeeded = QtCore.Signal(int, object)
    failed = QtCore.Signal(int, object, str)
    busy_changed = QtCore.Signal(bool)

    def __init__(
        self,
        parent: QtCore.QObject | None = None,
        *,
        finalizer: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="dioptas-integration",
        )
        self._finalizer = finalizer
        self._next_job_id = 0
        self._jobs: dict[int, FunctionJob] = {}
        self._closed = False

    @property
    def is_busy(self) -> bool:
        return bool(self._jobs)

    def submit(self, fn: Callable[[], Any]) -> int:
        if self._closed:
            raise RuntimeError("Cannot submit to a closed job runner")
        self._next_job_id += 1
        job_id = self._next_job_id
        job = FunctionJob(job_id, fn)
        job.signals.succeeded.connect(self._on_succeeded)
        job.signals.failed.connect(self._on_failed)
        was_busy = self.is_busy
        self._jobs[job_id] = job
        _RUNNING_JOBS.add(job)
        if not was_busy:
            self.busy_changed.emit(True)
        self._executor.submit(job.run)
        return job_id

    @QtCore.Slot(int, object)
    def _on_succeeded(self, job_id: int, result: object) -> None:
        self._finish(job_id)
        self.succeeded.emit(job_id, result)

    @QtCore.Slot(int, object, str)
    def _on_failed(self, job_id: int, exc: object, traceback_text: str) -> None:
        self._finish(job_id)
        logger.error("Background job %s failed\n%s", job_id, traceback_text)
        self.failed.emit(job_id, exc, traceback_text)

    def _finish(self, job_id: int) -> None:
        self._jobs.pop(job_id, None)
        if not self._jobs:
            self.busy_changed.emit(False)

    def shutdown(self, *, wait: bool = True) -> None:
        """Stop accepting work and retire the worker.

        With ``wait=False`` queued work and the native-backend finalizer still
        run in FIFO order on the owning thread, but the caller is not blocked.
        GUI teardown uses this mode so a long integration cannot hold the Qt
        event loop hostage while the window is closing.
        """
        if getattr(self, "_closed", True):
            return
        self._closed = True
        finalizer_future = None
        if self._finalizer is not None:
            # The single-worker executor is FIFO: this runs after submitted
            # integrations, on the exact thread that owns their backend.
            finalizer_future = self._executor.submit(self._finalizer)
        self._executor.shutdown(wait=wait)
        if finalizer_future is not None and wait:
            finalizer_future.result()
        self._jobs.clear()

    def __del__(self):
        try:
            self.shutdown(wait=False)
        except Exception:
            # Interpreter shutdown can dismantle concurrent.futures first.
            pass
