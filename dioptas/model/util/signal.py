# SPDX-License-Identifier: MIT

import inspect
import weakref
from collections.abc import Callable
from typing import Any

__export__ = ["Signal"]


class Signal:
    def __init__(self, *_: type) -> None:
        self.listeners: WeakRefList = WeakRefList()
        self.priority_listeners: WeakRefList = WeakRefList()
        self.blocked: bool = False

    def connect(self, handle: Callable[..., Any], priority: bool = False) -> None:
        """Connects a function handle to the Signal.

        If *priority* is True the handle is prepended and called before
        regular listeners.
        """
        if priority:
            self.priority_listeners.insert(0, handle)
        else:
            self.listeners.append(handle)

    def disconnect(self, handle: Callable[..., Any]) -> None:
        """Removes a function handle from the listeners."""
        try:
            self.listeners.remove(handle)
        except ValueError:
            pass

        try:
            self.priority_listeners.remove(handle)
        except ValueError:
            pass

    def emit(self, *args: Any) -> None:
        if self.blocked:
            return
        self._serve_listeners(self.priority_listeners, *args)
        self._serve_listeners(self.listeners, *args)

    @staticmethod
    def _serve_listeners(listeners: "WeakRefList", *args: Any) -> None:
        for ref in listeners:
            handle = ref()
            if type(handle) == Signal:
                handle.emit(*args)
            else:
                if len(inspect.signature(handle).parameters) == 0:
                    handle()
                else:
                    handle(*args)

    def clear(self) -> None:
        """Removes all listeners from the Signal."""
        self.listeners = WeakRefList()
        self.priority_listeners = WeakRefList()

    def block(self) -> None:
        """Blocks the Signal from emitting."""
        self.blocked = True

    def unblock(self) -> None:
        """Unblocks the Signal from emitting."""
        self.blocked = False

    def has_listener(self, handle: Callable[..., Any]) -> bool:
        """Returns True if the handle is in the list of listeners."""
        return handle in self.listeners or handle in self.priority_listeners


class WeakRefList(list):
    """A list which holds weak references to its items.

    If an item is garbage-collected the reference is automatically removed.
    Only the subset of list methods used by Signal is implemented:
    append, remove, insert.
    """

    def append(self, item: Callable[..., Any]) -> None:
        super().append(self._ref(item))

    def remove(self, item: Callable[..., Any]) -> None:
        super().remove(self._ref(item))

    def insert(self, index: int, item: Callable[..., Any]) -> None:
        super().insert(index, self._ref(item))

    def _remove_ref(self, ref: weakref.ref) -> None:
        super().remove(ref)

    def _ref(self, item: Callable[..., Any]) -> weakref.ref:
        if inspect.ismethod(item):
            return weakref.WeakMethod(item, self._remove_ref)
        else:
            return weakref.ref(item, self._remove_ref)

    def __contains__(self, item: object) -> bool:
        for ref in self:
            if ref() == item:
                return True
        return False
