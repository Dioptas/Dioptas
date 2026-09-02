# SPDX-License-Identifier: MIT

"""Debounced, latest-only integration scheduling for the Qt application."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import partial

from qtpy import QtCore

from .async_job import DedicatedAsyncJobRunner
from ..model.integration_task import PersistentIntegrationEngine

logger = logging.getLogger(__name__)


@dataclass
class PendingIntegration:
    calculate_pattern: bool = False
    calculate_cake: bool = False
    generation: int = 0


class AsyncIntegrationCoordinator(QtCore.QObject):
    """Coalesce model invalidations and commit only the newest result."""

    completed = QtCore.Signal(object, int)
    failed = QtCore.Signal(object, int, object)
    stale_result_discarded = QtCore.Signal(object, int)

    def __init__(self, model, parent=None, *, debounce_ms: int = 25) -> None:
        super().__init__(parent)
        self.model = model
        self.debounce_ms = debounce_ms
        self._pending = {}
        self._generation = {}
        self._contexts = {}
        self._closed = False
        self._integration_engine = PersistentIntegrationEngine()
        self._runner = DedicatedAsyncJobRunner(
            self,
            finalizer=self._integration_engine.close,
        )
        self._runner.succeeded.connect(self._on_succeeded)
        self._runner.failed.connect(self._on_failed)
        self._timer = QtCore.QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._start_next)

        self.model.configuration_added.connect(self.attach_configurations)
        self.model.configuration_selected.connect(self.attach_configurations)
        self.attach_configurations()

    @property
    def is_busy(self) -> bool:
        return self._runner.is_busy or bool(self._pending)

    def shutdown(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._timer.stop()
        self._pending.clear()
        for configuration in self.model.configurations:
            if configuration.integration_scheduler == self.request:
                configuration.integration_scheduler = None
        self._runner.shutdown(wait=False)

    def attach_configurations(self, *_args) -> None:
        """Install the scheduler on newly created or restored configurations."""
        if self._closed:
            return
        for configuration in self.model.configurations:
            configuration.integration_scheduler = self.request

    def request(
        self,
        configuration,
        *,
        calculate_pattern: bool,
        calculate_cake: bool,
        immediate: bool = False,
    ) -> int:
        if self._closed:
            raise RuntimeError("Cannot schedule integration after shutdown")
        generation = self._generation.get(configuration, 0) + 1
        self._generation[configuration] = generation
        pending = self._pending.setdefault(configuration, PendingIntegration())
        pending.calculate_pattern |= calculate_pattern
        pending.calculate_cake |= calculate_cake
        pending.generation = generation

        if not self._runner.is_busy:
            self._timer.start(0 if immediate else self.debounce_ms)
        return generation

    @QtCore.Slot()
    def _start_next(self) -> None:
        if self._closed or self._runner.is_busy or not self._pending:
            return

        configuration = self._next_configuration()
        pending = self._pending.pop(configuration)

        if configuration not in self.model.configurations:
            self.stale_result_discarded.emit(configuration, pending.generation)
            self._schedule_next()
            return

        try:
            task = configuration.create_integration_task(
                calculate_pattern=pending.calculate_pattern,
                calculate_cake=pending.calculate_cake,
            )
        except Exception as exc:
            logger.exception("Failed to prepare integration task")
            self._emit_failure_or_stale(
                configuration, pending.generation, exc
            )
            self._schedule_next()
            return
        if task is None:
            self.completed.emit(configuration, pending.generation)
            self._schedule_next()
            return

        try:
            job_id = self._runner.submit(
                partial(self._integration_engine.compute, task)
            )
        except Exception as exc:
            logger.exception("Failed to submit integration task")
            self._emit_failure_or_stale(
                configuration, pending.generation, exc
            )
            self._schedule_next()
            return
        self._contexts[job_id] = (configuration, pending.generation)

    def _next_configuration(self):
        current = self.model.current_configuration
        if current in self._pending:
            return current
        return next(iter(self._pending))

    def _schedule_next(self) -> None:
        if not self._closed and self._pending:
            self._timer.start(0)

    def _on_succeeded(self, job_id, result) -> None:
        context = self._contexts.pop(job_id, None)
        if context is None:
            return
        if self._closed:
            return
        configuration, generation = context
        try:
            is_current = configuration in self.model.configurations
            is_latest = self._generation.get(configuration) == generation
            if is_current and is_latest:
                try:
                    applied = configuration.apply_integration_result(result)
                except Exception as exc:
                    logger.exception("Failed to apply integration result")
                    self.failed.emit(configuration, generation, exc)
                else:
                    if applied:
                        self.completed.emit(configuration, generation)
                    else:
                        self.stale_result_discarded.emit(
                            configuration, generation
                        )
            else:
                logger.debug(
                    "Discarded stale integration result for generation %s",
                    generation,
                )
                self.stale_result_discarded.emit(configuration, generation)
        finally:
            self._schedule_next()

    def _on_failed(self, job_id, exc, _traceback_text) -> None:
        context = self._contexts.pop(job_id, None)
        if context is None:
            return
        if self._closed:
            return
        configuration, generation = context
        try:
            self._emit_failure_or_stale(configuration, generation, exc)
        finally:
            self._schedule_next()

    def _emit_failure_or_stale(self, configuration, generation, exc) -> None:
        is_current = configuration in self.model.configurations
        is_latest = self._generation.get(configuration) == generation
        if is_current and is_latest:
            self.failed.emit(configuration, generation, exc)
        else:
            self.stale_result_discarded.emit(configuration, generation)
