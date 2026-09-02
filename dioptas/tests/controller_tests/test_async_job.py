# SPDX-License-Identifier: MIT

from __future__ import annotations

import threading

from qtpy import QtCore

from dioptas.controller.async_job import (
    AsyncJobRunner,
    DedicatedAsyncJobRunner,
    _RUNNING_JOBS,
)


def test_async_job_runs_off_thread_and_delivers_on_gui_thread(qtbot):
    runner = AsyncJobRunner()
    gui_thread = threading.get_ident()
    completed = []
    busy = []
    runner.busy_changed.connect(busy.append)
    runner.succeeded.connect(
        lambda job_id, result: completed.append(
            (job_id, result, threading.get_ident())
        )
    )

    job_id = runner.submit(lambda: ("done", threading.get_ident()))

    qtbot.waitUntil(lambda: bool(completed))
    assert completed == [(job_id, ("done", completed[0][1][1]), gui_thread)]
    assert completed[0][1][1] != gui_thread
    assert busy == [True, False]
    assert not runner.is_busy


def test_async_job_reports_exceptions(qtbot):
    runner = AsyncJobRunner()
    failures = []
    runner.failed.connect(
        lambda job_id, exc, traceback_text: failures.append(
            (job_id, exc, traceback_text)
        )
    )

    def fail():
        raise ValueError("bad job")

    job_id = runner.submit(fail)

    qtbot.waitUntil(lambda: bool(failures))
    assert failures[0][0] == job_id
    assert isinstance(failures[0][1], ValueError)
    assert "ValueError: bad job" in failures[0][2]


def test_inline_mode_is_deterministic_for_controller_tests(qapp):
    runner = AsyncJobRunner(run_inline=True)
    completed = []
    runner.succeeded.connect(lambda job_id, result: completed.append(result))

    runner.submit(lambda: 42)

    assert completed == [42]
    assert not runner.is_busy


def test_running_job_survives_destroyed_qt_owner(qapp, qtbot):
    parent = QtCore.QObject()
    runner = AsyncJobRunner(parent)
    started = threading.Event()
    release = threading.Event()

    def controlled_job():
        started.set()
        assert release.wait(timeout=5)
        return 42

    runner.submit(controlled_job)
    assert started.wait(timeout=2)

    parent.deleteLater()
    qapp.processEvents()
    release.set()

    qtbot.waitUntil(lambda: not _RUNNING_JOBS, timeout=5000)


def test_dedicated_runner_reuses_thread_and_finalizes_there(qtbot):
    job_threads = []
    finalized_on = []
    completed = []
    runner = DedicatedAsyncJobRunner(
        finalizer=lambda: finalized_on.append(threading.get_ident())
    )
    runner.succeeded.connect(
        lambda _job_id, result: completed.append(result)
    )

    runner.submit(lambda: job_threads.append(threading.get_ident()) or 1)
    runner.submit(lambda: job_threads.append(threading.get_ident()) or 2)
    qtbot.waitUntil(lambda: completed == [1, 2], timeout=5000)
    runner.shutdown()

    assert len(set(job_threads)) == 1
    assert finalized_on == [job_threads[0]]


def test_dedicated_runner_can_shutdown_without_blocking_active_job(qtbot):
    started = threading.Event()
    release = threading.Event()
    finalized = threading.Event()
    runner = DedicatedAsyncJobRunner(finalizer=finalized.set)

    def controlled_job():
        started.set()
        assert release.wait(timeout=5)

    runner.submit(controlled_job)
    assert started.wait(timeout=2)

    # Application close must return even though native work cannot be
    # interrupted safely. Its finalizer is still queued on the same thread.
    runner.shutdown(wait=False)
    assert not finalized.is_set()

    release.set()
    assert finalized.wait(timeout=2)
    qtbot.waitUntil(lambda: not _RUNNING_JOBS, timeout=5000)
