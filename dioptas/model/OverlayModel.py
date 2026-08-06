# SPDX-License-Identifier: MIT

from __future__ import annotations

import logging
from copy import copy

import numpy as np
from xypattern import Pattern

from .util.HelperModule import calculate_color, rgb_to_hex
from .util import Signal
from .state import OverlayItemParams

logger = logging.getLogger(__name__)


class Overlay(Pattern):
    """Overlay class, inherits from Pattern. It is used to store overlays for the pattern widget.

    The user-settable display state lives in the evented ``params``
    dataclass. ``scaling`` and ``offset`` additionally write through to the
    Pattern base class, which applies them in its data computation."""

    index: int = 0

    def __init__(
        self,
        x: np.ndarray | None = None,
        y: np.ndarray | None = None,
        name: str = "",
    ) -> None:
        super().__init__(x, y, name)
        self.params: OverlayItemParams = OverlayItemParams(
            name=self._pre_params_name,
            color=rgb_to_hex(calculate_color(Overlay.index)),
            scaling=Pattern.scaling.fget(self),
            offset=Pattern.offset.fget(self),
        )
        Overlay.index += 1
        # scaling/offset reactions push into the Pattern base class, so a
        # direct params write behaves exactly like the property write
        self.params.events.connect(self._on_params_changed)

    def _on_params_changed(self, info) -> None:
        field = info.signal.name
        if field == "scaling":
            Pattern.scaling.fset(self, info.args[0])
            effective = Pattern.scaling.fget(self)
            if effective != info.args[0]:
                # xypattern clamped the value — record the effective one
                # (this re-emits once with the corrected value)
                self.params.scaling = effective
        elif field == "offset":
            Pattern.offset.fset(self, info.args[0])

    @classmethod
    def from_pattern(cls, pattern: Pattern) -> Overlay:
        """Creates an overlay from a pattern, does not use its original scaling parameters."""
        return Overlay(np.copy(pattern.x), np.copy(pattern.y), copy(pattern.name))

    # name is a plain attribute on Pattern, assigned during super().__init__
    # before the params object exists — hence the _pre_params_name buffer
    @property
    def name(self) -> str:
        if "params" in self.__dict__:
            return self.params.name
        return self._pre_params_name

    @name.setter
    def name(self, value: str) -> None:
        if "params" in self.__dict__:
            self.params.name = value
        else:
            self._pre_params_name = value

    @property
    def visible(self) -> bool:
        return self.params.visible

    @visible.setter
    def visible(self, value: bool) -> None:
        self.params.visible = value

    @property
    def color(self) -> str:
        return self.params.color

    @color.setter
    def color(self, value: str) -> None:
        self.params.color = value

    @property
    def scaling(self) -> float:
        return Pattern.scaling.fget(self)

    @scaling.setter
    def scaling(self, value: float) -> None:
        if "params" in self.__dict__:
            self.params.scaling = value
        else:  # during super().__init__, before params exists
            Pattern.scaling.fset(self, value)

    @property
    def offset(self) -> float:
        return Pattern.offset.fget(self)

    @offset.setter
    def offset(self, value: float) -> None:
        if "params" in self.__dict__:
            self.params.offset = value
        else:
            Pattern.offset.fset(self, value)


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

    def restore(self, overlays: list[Overlay]) -> None:
        """Rebuilds the overlay list to match a saved one (used by undo/redo).

        Emits the ordinary add/remove signals, so views follow without knowing
        the history exists. Only the tail that actually differs is rebuilt:
        overlays sitting at the same index as before are left untouched, so
        undoing a change to one overlay does not disturb the others.
        """
        common = 0
        while (
            common < len(self.overlays)
            and common < len(overlays)
            and self.overlays[common] is overlays[common]
        ):
            common += 1

        for ind in range(len(self.overlays) - 1, common - 1, -1):
            del self.overlays[ind]
            self.overlay_removed.emit(ind)
        for overlay in overlays[common:]:
            self.overlays.append(overlay)
            self.overlay_added.emit()

    def get_overlay_by_uid(self, uid: str) -> Overlay | None:
        """Returns the overlay with the given stable uid, or None."""
        for overlay in self.overlays:
            if overlay.params.uid == uid:
                return overlay
        return None

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
