# SPDX-License-Identifier: MIT

"""Derived guidance state for the stepwise calibration workflow.

The guide watches the store-level signals of a :class:`DioptasModel` and
reduces the current configuration's image and calibration state to a small
:class:`GuideState` snapshot: which workflow steps are done and what the
suggested next user action is. Everything is derived — the guide holds no
state of its own beyond the last snapshot, so it needs no persistence and
follows configuration switching for free (the store signals always describe
the current configuration).

The states are semantic only; mapping them to labels, colors and tooltips is
the view layer's job.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import TYPE_CHECKING, Mapping

from .util.signal import Signal

if TYPE_CHECKING:
    from .DioptasModel import DioptasModel


class NextAction(enum.Enum):
    """The single suggested next user action in the calibration workflow."""

    LOAD_IMAGE = enum.auto()
    PICK_PEAKS = enum.auto()
    CALIBRATE = enum.auto()
    SAVE = enum.auto()
    #: nothing left to suggest — a saved (or loaded) calibration exists
    NONE = enum.auto()


class Step(enum.Enum):
    """The four pages of the calibration wizard: image & detector,
    peak picking, calibrant & calibration, validation of the result."""

    IMAGE = enum.auto()
    PEAKS = enum.auto()
    CALIBRATE = enum.auto()
    VALIDATE = enum.auto()


class StepStatus(enum.Enum):
    PENDING = enum.auto()
    #: the step the user should act on next
    ATTENTION = enum.auto()
    #: not performed, but made unnecessary (e.g. peak picking after a
    #: calibration was loaded from file or entered manually)
    SKIPPED = enum.auto()
    DONE = enum.auto()


@dataclass(frozen=True)
class GuideState:
    image_loaded: bool
    num_peaks: int
    num_rings: int
    is_calibrated: bool
    #: a calibration exists and is backed by a .poni file (saved or loaded)
    is_saved: bool
    next_action: NextAction
    step_status: Mapping[Step, StepStatus]


def compute_guide_state(model: "DioptasModel") -> GuideState:
    """Reduces the current configuration's state to a GuideState."""
    calibration_params = model.calibration_model.params

    image_loaded = model.img_model.filename != ""
    peak_selections = calibration_params.peak_selections
    num_peaks = sum(len(positions) for _, positions in peak_selections)
    num_rings = len(
        {ring for ring, positions in peak_selections if len(positions) > 0}
    )
    is_calibrated = calibration_params.is_calibrated
    is_saved = is_calibrated and calibration_params.poni_filename != ""

    if not image_loaded:
        next_action = NextAction.LOAD_IMAGE
    elif num_peaks == 0 and not is_calibrated:
        next_action = NextAction.PICK_PEAKS
    elif not is_calibrated:
        next_action = NextAction.CALIBRATE
    elif not is_saved:
        next_action = NextAction.SAVE
    else:
        next_action = NextAction.NONE

    step_status = {
        Step.IMAGE: StepStatus.DONE if image_loaded else StepStatus.ATTENTION,
        Step.PEAKS: (
            StepStatus.DONE
            if num_peaks > 0
            else StepStatus.SKIPPED
            if is_calibrated
            else StepStatus.ATTENTION
            if next_action == NextAction.PICK_PEAKS
            else StepStatus.PENDING
        ),
        Step.CALIBRATE: (
            StepStatus.DONE
            if is_calibrated
            else StepStatus.ATTENTION
            if next_action == NextAction.CALIBRATE
            else StepStatus.PENDING
        ),
        Step.VALIDATE: (
            StepStatus.DONE
            if is_saved
            else StepStatus.ATTENTION
            if next_action == NextAction.SAVE
            else StepStatus.PENDING
        ),
    }

    return GuideState(
        image_loaded=image_loaded,
        num_peaks=num_peaks,
        num_rings=num_rings,
        is_calibrated=is_calibrated,
        is_saved=is_saved,
        next_action=next_action,
        step_status=step_status,
    )


#: configuration_params_changed fields that can change the GuideState
_RELEVANT_FIELDS = frozenset(
    {
        "img.filename",
        "calibration.peak_selections",
        "calibration.is_calibrated",
        "calibration.poni_filename",
    }
)


class CalibrationGuide:
    """Keeps a GuideState snapshot in sync with the store and signals changes.

    ``changed`` emits the new :class:`GuideState` whenever the derived state
    actually differs from the previous snapshot.
    """

    def __init__(self, dioptas_model: "DioptasModel") -> None:
        self.model = dioptas_model
        self.changed: Signal = Signal(object)
        self._state = compute_guide_state(dioptas_model)

        dioptas_model.configuration_params_changed.connect(self._on_params_changed)
        dioptas_model.configuration_selected.connect(self._on_configuration_selected)

    @property
    def state(self) -> GuideState:
        return self._state

    def _on_params_changed(self, field: str, _new, _old) -> None:
        if field in _RELEVANT_FIELDS:
            self._refresh()

    def _on_configuration_selected(self, _ind: int) -> None:
        self._refresh()

    def _refresh(self) -> None:
        new_state = compute_guide_state(self.model)
        if new_state != self._state:
            self._state = new_state
            self.changed.emit(new_state)
