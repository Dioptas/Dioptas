# SPDX-License-Identifier: MIT

"""Undo/redo over snapshots of the state.

The alternative to this is the command pattern: every action carries its own
``undo()``. That fits applications whose actions are few and well-fenced. Here
the settings live in evented params dataclasses behind a single change surface
(see params.py), so *every* write is already observable in one place — and a
whole snapshot of the settings is about 1.5 kB, cheap enough to keep one per
step. Capturing state is therefore both less code and harder to get wrong than
describing changes: an action that forgets to register an undo cannot exist.

The stack is a list of states with a cursor, not the more common pair of
undo/redo stacks. ``undo`` moves the cursor back and applies whatever it lands
on; the states either side of it are untouched. Push/pop designs have to move
the current state across to the opposite stack on every step, and any
bookkeeping running alongside them (a parallel deque, say) has to be moved in
exact lockstep or the two silently drift apart.

What a snapshot contains is up to the *capture* callable; this class never
inspects it. It only requires that states are comparable with ``==`` (to drop
no-op records) and cheap to hold. Large payloads are expected to be shared
between snapshots by reference rather than copied — see the mask blobs in
DioptasModel.

Recording happens *after* a change has been applied, so ``states[cursor]``
always mirrors the live state. Three mechanisms keep the granularity useful:

- ``key`` coalescing merges consecutive records of the same key within a short
  window into one step, so dragging a spinbox is one undo, not forty.
- ``transaction()`` collapses everything inside it into a single step, for
  compound operations whose intermediate states are not meaningful.
- ``suspended()`` records nothing at all, for loading a project or resetting,
  where the new state is a starting point rather than an edit.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

from ..util.signal import Signal

__all__ = ["History"]


@dataclass(frozen=True)
class _Step:
    state: Any
    label: str
    key: Any
    at: float


class History:
    def __init__(
        self,
        capture: Callable[[], Any],
        restore: Callable[[Any], None],
        max_steps: int = 100,
        coalesce_seconds: float = 0.6,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._capture = capture
        self._restore = restore
        self._max_steps = max(1, int(max_steps))
        self._coalesce_seconds = coalesce_seconds
        self._clock = clock

        self._suspend_depth = 0
        self._txn_depth = 0
        self._txn_dirty = False
        self._txn_label = ""
        self._restoring = False

        #: emitted whenever the available undo/redo steps change, so views can
        #: re-render their enabled state and labels
        self.changed: Signal = Signal()

        self._steps: list[_Step] = [_Step(capture(), "", None, clock())]
        self._cursor = 0

    # -- state ------------------------------------------------------------

    @property
    def can_undo(self) -> bool:
        return self._cursor > 0

    @property
    def can_redo(self) -> bool:
        return self._cursor < len(self._steps) - 1

    @property
    def undo_label(self) -> str:
        """Label of the action ``undo()`` would reverse."""
        return self._steps[self._cursor].label if self.can_undo else ""

    @property
    def redo_label(self) -> str:
        """Label of the action ``redo()`` would reapply."""
        return self._steps[self._cursor + 1].label if self.can_redo else ""

    @property
    def depth(self) -> int:
        """Number of undoable steps currently held."""
        return len(self._steps) - 1

    def states(self) -> tuple:
        """Every state currently held (baseline included, oldest first).

        Exists for resource accounting: the payload store sweeps against the
        ids reachable from these, so anything a held snapshot references
        stays alive exactly as long as the snapshot does.
        """
        return tuple(step.state for step in self._steps)

    # -- recording --------------------------------------------------------

    def record(self, label: str = "", key: Any = None) -> None:
        """Records the current state as a new step.

        Call after the change has been applied. Recording is skipped while
        suspended or restoring; inside a transaction it only marks the
        transaction dirty, so the whole block becomes a single step.
        """
        if self._suspend_depth or self._restoring:
            return
        if self._txn_depth:
            self._txn_dirty = True
            if not self._txn_label:
                self._txn_label = label
            return
        self._push(label, key)

    def _push(self, label: str, key: Any = None) -> None:
        state = self._capture()
        current = self._steps[self._cursor]
        if _same(state, current.state):
            # a write that did not change anything we track (or a reaction
            # firing twice) must not consume an undo step
            return

        now = self._clock()
        del self._steps[self._cursor + 1 :]  # a new edit invalidates the redo tail

        # Merges a run of writes to the same field — a spinbox being dragged.
        # Deliberately keyed rather than purely time-based: coalescing
        # everything that lands close together also swallows genuinely
        # separate actions performed in quick succession, which is worse than
        # the occasional extra step.
        coalescing = (
            key is not None
            and key == current.key
            # once the stack has been trimmed, steps[0] is the oldest state
            # still reachable rather than a pristine baseline; overwriting it
            # would edit history the user can still undo into
            and self._cursor > 0
            and now - current.at <= self._coalesce_seconds
        )
        if coalescing:
            # the first record names the action; anything merged into it is a
            # consequence of that action ("mask" for a rotation resizing it),
            # so the original label is the one worth showing
            self._steps[self._cursor] = _Step(
                state, current.label or label, current.key or key, now
            )
        else:
            self._steps.append(_Step(state, label, key, now))
            self._cursor += 1
            self._trim()
        self.changed.emit()

    def _trim(self) -> None:
        excess = len(self._steps) - (self._max_steps + 1)  # +1 for the baseline
        if excess > 0:
            del self._steps[:excess]
            self._cursor -= excess

    def reset(self) -> None:
        """Drops all history and re-baselines on the current state.

        Used when the state is replaced wholesale (loading a project, reset),
        where undoing back into the previous session would be surprising.

        Ignored while restoring: applying a step can legitimately look like a
        wholesale replacement to a listener (restoring an image of a different
        size resizes the mask, for one), and honouring that would throw away
        the very stack being navigated.
        """
        if self._restoring:
            return
        self._steps = [_Step(self._capture(), "", None, self._clock())]
        self._cursor = 0
        self.changed.emit()

    # -- navigation -------------------------------------------------------

    def undo(self) -> bool:
        if not self.can_undo:
            return False
        self._cursor -= 1
        self._apply(self._steps[self._cursor].state)
        return True

    def redo(self) -> bool:
        if not self.can_redo:
            return False
        self._cursor += 1
        self._apply(self._steps[self._cursor].state)
        return True

    def _apply(self, state: Any) -> None:
        # restoring writes the params back, which emits change events and so
        # would otherwise record the undo itself as a new step
        self._restoring = True
        try:
            self._restore(state)
        finally:
            self._restoring = False

        # Re-capture what was actually achieved. A restore can legitimately
        # fall short — a file that has moved cannot be re-read — and the
        # invariant that states[cursor] mirrors the live state has to hold
        # regardless: _push compares against it to decide whether anything
        # changed, and a step that quietly disagrees with reality gets
        # discarded by the next edit while still being on screen.
        step = self._steps[self._cursor]
        self._steps[self._cursor] = _Step(
            self._capture(), step.label, step.key, step.at
        )
        self.changed.emit()

    # -- control ----------------------------------------------------------

    @contextmanager
    def suspended(self) -> Iterator[None]:
        """Records nothing for the duration of the context."""
        self._suspend_depth += 1
        try:
            yield
        finally:
            self._suspend_depth -= 1

    @contextmanager
    def transaction(self, label: str = "") -> Iterator[None]:
        """Collapses every record inside the context into one step.

        Nested transactions join the outermost one. If nothing was recorded,
        no step is created.
        """
        if self._suspend_depth or self._restoring:
            yield  # suspension wins: record nothing at all
            return
        if self._txn_depth == 0:
            self._txn_label = label
        self._txn_depth += 1
        try:
            yield
        finally:
            self._txn_depth -= 1
            if self._txn_depth == 0:
                dirty, self._txn_dirty = self._txn_dirty, False
                label, self._txn_label = self._txn_label, ""
                if dirty:
                    self._push(label)


def _same(a: Any, b: Any) -> bool:
    """Equality that never raises, whatever the snapshot holds.

    Snapshots are plain dicts/tuples/bytes, but a numpy array reaching one
    would make ``==`` return an array and blow up in a boolean context. Such a
    comparison is treated as "not equal", which records a redundant step at
    worst — never a lost one.
    """
    try:
        return bool(a == b)
    except Exception:
        return False
