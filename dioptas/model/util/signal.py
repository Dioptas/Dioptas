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

from inspect import signature


class Signal:
    def __init__(self, *_):
        self.listeners = []
        self.priority_listeners = []
        self.blocked = False

    def connect(self, handle, priority=False):
        """
        Connects a function handle to the Signal.
        :param handle: function handle to be called when signal is emitted
        :param priority: if set to true the handle will be added as first function to be called in the case of the event

        If multiple handles are added with priority, they will obviously be called in the reverse order of adding.
        """
        if priority:
            self.priority_listeners.insert(0, handle)
        else:
            self.listeners.append(handle)

    def disconnect(self, handle):
        """
        Removes a certain function handle from the list of listeners to be called in case of Signal emit.
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
        for handle in listeners:
            if type(handle) == Signal:
                handle.emit(*args)
            else:
                if len(signature(handle).parameters) == 0:
                    handle()
                else:
                    handle(*args)

    def clear(self):
        """
        Removes all listeners from the Signal.
        """
        self.listeners = []
        self.priority_listeners = []
