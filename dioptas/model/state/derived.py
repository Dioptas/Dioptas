# SPDX-License-Identifier: MIT

"""Derived computations driven by dependency signals.

A :class:`Derived` wraps a computation whose result depends on other state
(e.g. integrating the current image into a pattern). Instead of models and
controllers wiring/unwiring ``connect(compute)`` calls and toggling flags to
suppress recomputation, the policy lives in one object:

- ``active`` gates whether dependency changes trigger the computation at all
  (replaces connect/disconnect cycling of auto-integrate flags). Triggers
  arriving while inactive are discarded, matching a disconnected signal.
- ``hold()`` suppresses and coalesces triggers for the duration of a context:
  at exit the computation runs at most once if anything triggered
  (``flush=True``, the default), or not at all (``flush=False``). This
  replaces the temporary flag-toggling dances around bulk operations.
- ``invalidate()`` is the programmatic equivalent of a dependency firing;
  ``recompute()`` requests the computation regardless of ``active`` (used by
  setters that historically always recomputed).

Explicit direct calls to the underlying computation function intentionally
bypass this object — "compute now" call sites (e.g. a controller forcing an
integration) keep their immediate semantics.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from contextlib import contextmanager
from typing import Any, Iterator

__all__ = ["Derived"]


class Derived:
    def __init__(
        self,
        compute: Callable[[], Any],
        dependencies: Iterable[Any] = (),
        active: bool = True,
    ) -> None:
        self._compute = compute
        self._active = active
        self._hold_depth = 0
        self._hold_flush = True
        self._pending = False
        for dependency in dependencies:
            self.add_dependency(dependency)

    def add_dependency(self, signal: Any) -> None:
        """Registers a signal whose emission triggers this computation."""
        signal.connect(self._on_dependency_changed)

    @property
    def active(self) -> bool:
        return self._active

    @active.setter
    def active(self, value: bool) -> None:
        """En-/disables dependency-triggered recomputation.

        Enabling does not recompute retroactively — triggers received while
        inactive are discarded (matching the disconnected-signal semantics
        this replaces)."""
        self._active = bool(value)

    def invalidate(self) -> None:
        """Signals that a dependency changed; recomputes if active."""
        if not self._active:
            return
        self._trigger()

    def recompute(self) -> None:
        """Requests recomputation regardless of ``active`` (still coalesced
        and discardable while held)."""
        self._trigger()

    def _on_dependency_changed(self, *args: Any) -> None:
        self.invalidate()

    def _trigger(self) -> None:
        if self._hold_depth:
            self._pending = True
        else:
            self._compute()

    @contextmanager
    def hold(self, flush: bool = True) -> Iterator[None]:
        """Suppresses triggers for the duration of the context.

        On exit of the outermost hold the computation runs once if any
        trigger arrived and ``flush`` is True; with ``flush=False`` pending
        triggers are discarded. For nested holds the outermost ``flush``
        wins."""
        if self._hold_depth == 0:
            self._hold_flush = flush
        self._hold_depth += 1
        try:
            yield
        finally:
            self._hold_depth -= 1
            if self._hold_depth == 0:
                pending, self._pending = self._pending, False
                if pending and self._hold_flush:
                    self._compute()
