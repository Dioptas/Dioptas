# -*- coding: utf8 -*-


import logging

from copy import copy
from qtpy import QtCore
import numpy as np

from .util.HelperModule import FileNameIterator, get_base_name
from .util import Pattern

logger = logging.getLogger(__name__)


class OverlayModel(QtCore.QObject):
    """
    Main Overlay Pattern Handling Model. (Was previously included in the PatternModel),
    """

    overlay_changed = QtCore.Signal(int)  # changed index
    overlay_added = QtCore.Signal()
    overlay_removed = QtCore.Signal(int)  # removed index

    def __init__(self):
        super(OverlayModel, self).__init__()
        self.overlays = []

    def add_overlay(self, x, y, name=''):
        """
        Adds an overlay to the list of overlays
        :param x: x-values
        :param y: y-values
        :param name: name of overlay to be used for displaying etc.
        """
        self.overlays.append(Pattern(x, y, name))
        self.overlay_added.emit()
        return self.overlays[-1]

    def add_overlay_pattern(self, pattern):
        """
        Adds a pattern as overlay to the list of overlays, does not use its original scaling parameters
        """
        overlay_pattern = Pattern(np.copy(pattern.x),
                                   np.copy(pattern.y),
                                   copy(pattern.name))
        self.overlays.append(overlay_pattern)
        self.overlay_added.emit()

    def add_overlay_file(self, filename):
        """
        Reads a 2-column (x,y) text file and adds it as overlay to the list of overlays
        :param filename: path of the file to be loaded
        """
        self.overlays.append(Pattern())
        self.overlays[-1].load(filename)
        self.overlay_added.emit()

    def remove_overlay(self, ind):
        """
        Removes an overlay from the list of overlays
        :param ind: index of the overlay
        """
        if ind >= 0:
            del self.overlays[ind]
            self.overlay_removed.emit(ind)

    def get_overlay(self, ind):
        """
        :param ind: overlay ind
        :return: returns overlay if existent or None if it does not exist
        """
        try:
            return self.overlays[ind]
        except IndexError:
            return None


    def set_overlay_scaling(self, ind, scaling):
        """
        Sets the scaling of the specified overlay
        :param ind: index of the overlay
        :param scaling: new scaling value
        """
        self.overlays[ind].scaling = scaling
        self.overlay_changed.emit(ind)

    def get_overlay_scaling(self, ind):
        """
        Returns the scaling of the specified overlay
        :param ind: index of the overlay
        :return: scaling value
        """
        return self.overlays[ind].scaling

    def set_overlay_offset(self, ind, offset):
        """
        Sets the offset of the specified overlay
        :param ind: index of the overlay
        :param offset: new offset value
        """
        self.overlays[ind].offset = offset
        self.overlay_changed.emit(ind)

    def get_overlay_offset(self, ind):
        """
        Return the offset of the specified overlay
        :param ind: index of the overlay
        :return: overlay value
        """
        return self.overlays[ind].offset


    def overlay_waterfall(self, separation):
        offset = 0
        for ind in range(len(self.overlays)):
            offset -= separation
            self.overlays[-(ind + 1)].offset = offset
            self.overlay_changed.emit(len(self.overlays) - (ind + 1))


    def reset_overlay_offsets(self):
        for ind, overlay in enumerate(self.overlays):
            overlay.offset = 0
            self.overlay_changed.emit(ind)
