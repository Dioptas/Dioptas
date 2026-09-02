# SPDX-License-Identifier: MIT

from __future__ import annotations

import logging

import pytest

from dioptas.controller.event_loop import EventLoopLagMonitor


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_monitor_records_and_emits_only_threshold_crossings(qapp):
    clock = Clock()
    monitor = EventLoopLagMonitor(
        interval_ms=50,
        warning_threshold_ms=100,
        clock=clock,
    )
    stalls = []
    monitor.stalled.connect(stalls.append)

    monitor.start()
    assert monitor.is_active

    clock.now = 0.10
    monitor._sample()
    assert monitor.last_lag_ms == 50
    assert stalls == []

    clock.now = 0.30
    monitor._sample()
    assert monitor.last_lag_ms == pytest.approx(150)
    assert monitor.max_lag_ms == pytest.approx(150)
    assert stalls == pytest.approx([150])

    monitor.stop()
    assert not monitor.is_active


def test_monitor_validates_intervals(qapp):
    try:
        EventLoopLagMonitor(interval_ms=0)
    except ValueError as exc:
        assert "positive" in str(exc)
    else:
        raise AssertionError("zero interval should fail")

    try:
        EventLoopLagMonitor(warning_threshold_ms=-1)
    except ValueError as exc:
        assert "cannot be negative" in str(exc)
    else:
        raise AssertionError("negative warning threshold should fail")


def test_stall_warning_includes_only_two_most_recent_logs(qapp, caplog):
    clock = Clock()
    monitor = EventLoopLagMonitor(
        interval_ms=50,
        warning_threshold_ms=100,
        clock=clock,
    )
    with caplog.at_level(logging.DEBUG, logger="dioptas"):
        monitor.start()
        activity_logger = logging.getLogger("dioptas.test.activity")
        activity_logger.info("old activity")
        activity_logger.debug("Loading detector image")
        activity_logger.info("Integrating image 1D")
        clock.now = 0.20
        monitor._sample()
        monitor.stop()

    message = caplog.messages[-1]
    assert "old activity" not in message
    assert "[dioptas.test.activity] Loading detector image" in message
    assert "[dioptas.test.activity] Integrating image 1D" in message
