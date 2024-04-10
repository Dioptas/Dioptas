# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
# Principal author: Clemens Prescher (clemens.prescher@gmail.com)
# Copyright (C) 2014-2019 GSECARS, University of Chicago, USA
# Copyright (C) 2015-2018 Institute for Geology and Mineralogy, University of Cologne, Germany
# Copyright (C) 2019-2020 DESY, Hamburg, Germany
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import inspect
import weakref

__export__ = ["Signal"]


class Signal:
    def __init__(self, *_):
        self.listeners = WeakRefList()
        self.priority_listeners = WeakRefList()
        self.blocked = False

    def connect(self, handle, priority=False):
        """
        Connects a function handle to the Signal.
        :param handle: function handle to be called when the signal is emitted
        :param priority: if set to True, the handle will be added as the first function to be called in the case of
                        the event
        If multiple handles are added with priority, they will obviously be called in the reverse order of adding.
        """
        if priority:
            self.priority_listeners.insert(0, handle)
        else:
            self.listeners.append(handle)

    def disconnect(self, handle):
        """
        Removes a certain function handle from the list of listeners to be called in case of Signal emitted.
        :param handle: function handle to be removed from the listeners
        """
        try:
            self.listeners.remove(handle)
        except ValueError:
            pass

        try:
            self.priority_listeners.remove(handle)
        except ValueError:
            pass

    def emit(self, *args):
        if self.blocked:
            return
        self._serve_listeners(self.priority_listeners, *args)
        self._serve_listeners(self.listeners, *args)

    @staticmethod
    def _serve_listeners(listeners, *args):
        for ref in listeners:
            handle = ref()
            if type(handle) == Signal:
                handle.emit(*args)
            else:
                if len(inspect.signature(handle).parameters) == 0:
                    handle()
                else:
                    handle(*args)

    def clear(self):
        """
        Removes all listeners from the Signal.
        """
        self.listeners = WeakRefList()
        self.priority_listeners = WeakRefList()

    def block(self):
        """
        Blocks the Signal from emitting.
        """
        self.blocked = True

    def unblock(self):
        """
        Unblocks the Signal from emitting.
        """
        self.blocked = False

    def has_listener(self, handle):
        """
        Returns True if the handle is in the list of listeners.
        """
        return handle in self.listeners or handle in self.priority_listeners


class WeakRefList(list):
    """
    A list which holds weak references to its items. If an item is deleted, the reference to it will be removed from
    the list. This is useful for Signals, where we want to hold a list of listeners, but don't want to prevent the
    garbage collector from deleting the listeners.
    It is not a full reimplementation, only the methods which are used in the Signal class are implemented - append,
    remove, insert. This list will work for object methods as well as objects. To retrieve the orginal item, the
    value of the weak reference has to be called. E.g.:
    >>> class A:
    >>>     def method(self):
    >>>         return "lala"
    >>>
    >>> a = A()
    >>> weak_ref_list = WeakRefList()
    >>> weak_ref_list.append(a.method)
    >>> weak_ref_list[0]()() == "lala"
    """

    def append(self, item):
        super(WeakRefList, self).append(self._ref(item))

    def remove(self, item):
        super(WeakRefList, self).remove(self._ref(item))

    def insert(self, index, item):
        super(WeakRefList, self).insert(index, self._ref(item))

    def _remove_ref(self, ref):
        super(WeakRefList, self).remove(ref)

    def _ref(self, item):
        if inspect.ismethod(item):
            return weakref.WeakMethod(item, self._remove_ref)
        else:
            return weakref.ref(item, self._remove_ref)

    def __contains__(self, item):
        for ref in self:
            if ref() == item:
                return True
        return False
