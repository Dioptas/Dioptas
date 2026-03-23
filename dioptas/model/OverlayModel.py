# SPDX-License-Identifier: MIT

from __future__ import annotations

import logging
from copy import copy

import numpy as np
from xypattern import Pattern

from .util.HelperModule import calculate_color, rgb_to_hex
from .util import Signal

logger = logging.getLogger(__name__)


class Overlay(Pattern):
    """Overlay class, inherits from Pattern. It is used to store overlays for the pattern widget."""

    index: int = 0

    def __init__(
        self,
        x: np.ndarray | None = None,
        y: np.ndarray | None = None,
        name: str = "",
    ) -> None:
        super().__init__(x, y, name)
        self.visible: bool = True
        self.color: str = rgb_to_hex(calculate_color(Overlay.index))
        Overlay.index += 1

    @classmethod
    def from_pattern(cls, pattern: Pattern) -> Overlay:
        """Creates an overlay from a pattern, does not use its original scaling parameters."""
        return Overlay(np.copy(pattern.x), np.copy(pattern.y), copy(pattern.name))


class OverlayModel:
    """Main Overlay Pattern Handling Model. (Was previously included in the PatternModel)."""

    def __init__(self) -> None:
        super().__init__()
        self.overlays: list[Overlay] = []

        self.overlay_added: Signal = Signal()
        self.overlay_changed: Signal = Signal(int)  # changed index
        self.overlay_removed: Signal = Signal(int)  # removed index

    def add_overlay(self, x: np.ndarray, y: np.ndarray, name: str = "") -> Overlay:
        """Adds an overlay to the list of overlays."""
        logger.info("Adding overlay: %s", name)
        self.add_overlay_pattern(Overlay(x, y, name))
        return self.overlays[-1]

    def add_overlay_pattern(self, pattern: Pattern) -> None:
        """Adds a pattern as overlay to the list of overlays, does not use its original scaling parameters."""
        overlay_pattern = Overlay.from_pattern(pattern)
        self.overlays.append(overlay_pattern)
        self.overlay_added.emit()

    def add_overlay_file(self, filename: str) -> None:
        """Reads a 2-column (x,y) text file and adds it as overlay to the list of overlays."""
        logger.info("Adding overlay from file: %s", filename)
        pattern = Overlay.from_file(filename)
        self.add_overlay_pattern(pattern)

    def remove_overlay(self, ind: int) -> None:
        """Removes an overlay from the list of overlays."""
        logger.info("Removing overlay %d", ind)
        if ind >= 0:
            del self.overlays[ind]
            self.overlay_removed.emit(ind)

    def get_overlay(self, ind: int) -> Overlay | None:
        """Returns overlay if existent or None if it does not exist."""
        try:
            return self.overlays[ind]
        except IndexError:
            return None

    def move_overlay_up(self, ind: int) -> None:
        """Moves the overlay up in the list of overlays (i.e. from position 3 to 2)."""
        if ind > 0:
            self.overlays[ind], self.overlays[ind - 1] = (
                self.overlays[ind - 1],
                self.overlays[ind],
            )
            self.overlay_changed.emit(ind)
            self.overlay_changed.emit(ind - 1)

    def move_overlay_down(self, ind: int) -> None:
        """Moves the overlay down in the list of overlays (i.e. from position 3 to 4)."""
        if ind < len(self.overlays) - 1:
            self.overlays[ind], self.overlays[ind + 1] = (
                self.overlays[ind + 1],
                self.overlays[ind],
            )
            self.overlay_changed.emit(ind)
            self.overlay_changed.emit(ind + 1)

    def set_overlay_scaling(self, ind: int, scaling: float) -> None:
        """Sets the scaling of the specified overlay."""
        self.overlays[ind].scaling = scaling
        self.overlay_changed.emit(ind)

    def get_overlay_scaling(self, ind: int) -> float:
        """Returns the scaling of the specified overlay."""
        return self.overlays[ind].scaling

    def set_overlay_offset(self, ind: int, offset: float) -> None:
        """Sets the offset of the specified overlay."""
        self.overlays[ind].offset = offset
        self.overlay_changed.emit(ind)

    def get_overlay_offset(self, ind: int) -> float:
        """Returns the offset of the specified overlay."""
        return self.overlays[ind].offset

    def set_overlay_visible(self, ind: int, visible: bool) -> None:
        """Sets the visibility of the specified overlay."""
        self.overlays[ind].visible = visible
        self.overlay_changed.emit(ind)

    def set_overlay_color(self, ind: int, color: str) -> None:
        """Sets the color of the specified overlay (as hex string, e.g. #FF0000)."""
        self.overlays[ind].color = color
        self.overlay_changed.emit(ind)

    def get_overlay_color(self, ind: int) -> str:
        """Returns the color of the specified overlay."""
        return self.overlays[ind].color

    def set_overlay_name(self, ind: int, name: str) -> None:
        """Sets the name of the specified overlay."""
        self.overlays[ind].name = name
        self.overlay_changed.emit(ind)

    def get_overlay_name(self, ind: int) -> str:
        """Returns the name of the specified overlay."""
        return self.overlays[ind].name

    def overlay_waterfall(self, separation: float) -> None:
        offset = 0
        for ind in range(len(self.overlays)):
            offset -= separation
            self.overlays[-(ind + 1)].offset = offset
            self.overlay_changed.emit(len(self.overlays) - (ind + 1))

    def reset_overlay_offsets(self) -> None:
        for ind, overlay in enumerate(self.overlays):
            overlay.offset = 0
            self.overlay_changed.emit(ind)

    def reset(self) -> None:
        for _ in range(len(self.overlays)):
            self.remove_overlay(0)
