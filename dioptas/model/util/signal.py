# SPDX-License-Identifier: MIT

"""Observer-pattern Signal backed by psygnal.

The public API is the historical Dioptas ``Signal`` (instance-level
construction, ``connect(handle, priority=...)``, writable ``blocked``,
``has_listener``, signal-to-signal chaining), while dispatch, weak-reference
handling and pause/batching come from :class:`psygnal.SignalInstance`.

Semantics inherited from the previous implementation:

- Listeners taking no arguments are called without arguments, all others
  receive every emitted argument.
- Bound-method listeners are held by weak reference and drop out
  automatically when their instance is garbage-collected.
- Exceptions raised by a listener propagate unwrapped to the emitter.
- Connecting a ``Signal`` as listener forwards emissions to it.

New capability: ``paused()`` batches emissions — signals emitted inside the
context are queued and delivered on exit (optionally reduced to a single
emission with ``reducer``).
"""

import inspect
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any, Iterator

from psygnal import EmitLoopError, SignalInstance

__export__ = ["Signal"]


class Signal:
    def __init__(self, *_: type) -> None:
        self._psygnal: SignalInstance = SignalInstance()
        self._blocked: bool = False

    def connect(self, handle: Callable[..., Any], priority: bool = False) -> None:
        """Connects a function handle to the Signal.

        If *priority* is True the handle is called before regular listeners.
        """
        slot = self._as_slot(handle)
        max_args = 0 if _accepts_no_args(slot) else None
        self._psygnal.connect(
            slot,
            check_nargs=False,
            max_args=max_args,
            priority=1 if priority else 0,
            on_ref_error="ignore",  # keep a strong ref when weakref is impossible
        )

    def disconnect(self, handle: Callable[..., Any]) -> None:
        """Removes a function handle from the listeners."""
        self._psygnal.disconnect(self._as_slot(handle), missing_ok=True)

    def emit(self, *args: Any) -> None:
        try:
            self._psygnal.emit(*args)
        except EmitLoopError as e:
            raise _unwrap(e) from None

    def clear(self) -> None:
        """Removes all listeners from the Signal."""
        self._psygnal.disconnect()

    @property
    def blocked(self) -> bool:
        return self._blocked

    @blocked.setter
    def blocked(self, value: bool) -> None:
        self._blocked = bool(value)
        if self._blocked:
            self._psygnal.block()
        else:
            self._psygnal.unblock()

    def block(self) -> None:
        """Blocks the Signal from emitting."""
        self.blocked = True

    def unblock(self) -> None:
        """Unblocks the Signal from emitting."""
        self.blocked = False

    @contextmanager
    def paused(
        self, reducer: Callable[[tuple, tuple], tuple] | None = None
    ) -> Iterator[None]:
        """Context manager batching emissions until exit.

        Without *reducer* every queued emission is delivered on exit; with a
        reducer the queued emission args are folded pairwise into a single
        emission (e.g. ``lambda a, b: b`` keeps only the latest). Listener
        exceptions raised during the flush propagate unwrapped, like emit().
        """
        try:
            with self._psygnal.paused(reducer):
                yield
        except EmitLoopError as e:
            raise _unwrap(e) from None

    def has_listener(self, handle: Callable[..., Any]) -> bool:
        """Returns True if the handle is in the list of listeners."""
        slot = self._as_slot(handle)
        # psygnal has no public containment check; _slots holds WeakCallback
        # objects whose dereference() returns the original callable (or None
        # once garbage-collected). Covered by unit tests against upgrades.
        return any(cb.dereference() == slot for cb in self._psygnal._slots)

    @staticmethod
    def _as_slot(handle: Callable[..., Any]) -> Callable[..., Any]:
        return handle.emit if isinstance(handle, Signal) else handle


def _accepts_no_args(slot: Callable[..., Any]) -> bool:
    try:
        sig = inspect.signature(slot)
    except (ValueError, TypeError):
        return False
    return len(sig.parameters) == 0


def _unwrap(error: EmitLoopError) -> BaseException:
    """Returns the listener's original exception from a psygnal EmitLoopError."""
    cause = error.__cause__
    return cause if cause is not None else error
