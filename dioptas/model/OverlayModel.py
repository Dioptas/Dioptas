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

from typing import Optional
import logging

from copy import copy
import numpy as np
from .util.HelperModule import calculate_color

from .util import Pattern
from .util import Signal

logger = logging.getLogger(__name__)


class OverlayModel(object):
    """
    Main Overlay Pattern Handling Model. (Was previously included in the PatternModel),
    """

    def __init__(self):
        super(OverlayModel, self).__init__()
        self.overlays = []
        self.overlay_visible = []
        self.overlay_colors = []

        self.overlay_added = Signal()
        self.overlay_changed = Signal(int)  # changed index
        self.overlay_removed = Signal(int)  # removed index

    def add_overlay(self, x: np.ndarray, y: np.ndarray, name: str = ''):
        """
        Adds an overlay to the list of overlays
        :param x: x-values
        :param y: y-values
        :param name: name of overlay to be used for displaying etc.
        """
        self.add_overlay_pattern(Pattern(x, y, name))
        return self.overlays[-1]

    def add_overlay_pattern(self, pattern: Pattern):
        """
        Adds a pattern as overlay to the list of overlays, does not use its original scaling parameters
        """
        overlay_pattern = Pattern(np.copy(pattern.x),
                                  np.copy(pattern.y),
                                  copy(pattern.name))
        self.overlays.append(overlay_pattern)
        self.overlay_visible.append(True)
        self.overlay_colors.append(calculate_color(len(self.overlays)))
        self.overlay_added.emit()

    def add_overlay_file(self, filename: str):
        """
        Reads a 2-column (x,y) text file and adds it as overlay to the list of overlays
        :param filename: path of the file to be loaded
        """
        pattern = Pattern.from_file(filename)
        self.add_overlay_pattern(pattern)

    def remove_overlay(self, ind: int):
        """
        Removes an overlay from the list of overlays
        :param ind: index of the overlay
        """
        if ind >= 0:
            del self.overlays[ind]
            del self.overlay_visible[ind]
            self.overlay_removed.emit(ind)

    def get_overlay(self, ind: int) -> Optional[Pattern]:
        """
        :param ind: overlay ind
        :return: returns overlay if existent or None if it does not exist
        """
        try:
            return self.overlays[ind]
        except IndexError:
            return None

    def move_up_overlay(self, ind: int):
        """
        Moves the overlay up in the list of overlays (i.e. from positon 3 to 2)
        :param ind: index of the overlay
        """
        if ind > 0:
            self.overlays[ind], self.overlays[ind - 1] = \
                self.overlays[ind - 1], self.overlays[ind]
            self.overlay_visible[ind], self.overlay_visible[ind - 1] = \
                self.overlay_visible[ind - 1], self.overlay_visible[ind]
            self.overlay_colors[ind], self.overlay_colors[ind - 1] = \
                self.overlay_colors[ind - 1], self.overlay_colors[ind]
            self.overlay_changed.emit(ind)
            self.overlay_changed.emit(ind - 1)

    def move_down_overlay(self, ind: int):
        """
        Moves the overlay down in the list of overlays (i.e. from position 3 to
        4)
        :param ind: index of the overlay
        """
        if ind < len(self.overlays) - 1:
            self.overlays[ind], self.overlays[ind + 1] = \
                self.overlays[ind + 1], self.overlays[ind]
            self.overlay_visible[ind], self.overlay_visible[ind + 1] = \
                self.overlay_visible[ind + 1], self.overlay_visible[ind]
            self.overlay_colors[ind], self.overlay_colors[ind + 1] = \
                self.overlay_colors[ind + 1], self.overlay_colors[ind]
            self.overlay_changed.emit(ind)
            self.overlay_changed.emit(ind + 1)

    def set_overlay_scaling(self, ind: int, scaling: float):
        """
        Sets the scaling of the specified overlay
        :param ind: index of the overlay
        :param scaling: new scaling value
        """
        self.overlays[ind].scaling = scaling
        self.overlay_changed.emit(ind)

    def get_overlay_scaling(self, ind: int) -> float:
        """
        Returns the scaling of the specified overlay
        :param ind: index of the overlay
        :return: scaling value
        """
        return self.overlays[ind].scaling

    def set_overlay_offset(self, ind: int, offset: float):
        """
        Sets the offset of the specified overlay
        :param ind: index of the overlay
        :param offset: new offset value
        """
        self.overlays[ind].offset = offset
        self.overlay_changed.emit(ind)

    def get_overlay_offset(self, ind: int) -> float:
        """
        Return the offset of the specified overlay
        :param ind: index of the overlay
        :return: overlay value
        """
        return self.overlays[ind].offset

    def set_overlay_visible(self, ind: int, visible: bool):
        """
        Sets the visibility of the specified overlay
        :param ind: index of the overlay
        :param visible: new visibility value (True or False)
        """
        self.overlay_visible[ind] = visible
        self.overlay_changed.emit(ind)

    def set_overlay_color(self, ind: int, color: str):
        """
        Sets the color of the specified overlay
        :param ind: index of the overlay
        :param color: new color value
        """
        self.overlay_colors[ind] = color
        self.overlay_changed.emit(ind)

    def get_overlay_color(self, ind: int) -> tuple[int, int, int]:
        """
        Returns the color of the specified overlay
        :param ind: index of the overlay
        :return: color value
        """
        return self.overlay_colors[ind]

    def overlay_waterfall(self, separation: float):
        offset = 0
        for ind in range(len(self.overlays)):
            offset -= separation
            self.overlays[-(ind + 1)].offset = offset
            self.overlay_changed.emit(len(self.overlays) - (ind + 1))

    def reset_overlay_offsets(self):
        for ind, overlay in enumerate(self.overlays):
            overlay.offset = 0
            self.overlay_changed.emit(ind)

    def reset(self):
        for _ in range(len(self.overlays)):
            self.remove_overlay(0)
