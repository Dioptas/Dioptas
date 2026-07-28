# SPDX-License-Identifier: MIT

"""Evented parameter dataclasses — the serializable settings layer.

Params classes hold everything the user can set, as opposed to loaded data
(images, patterns) or derived results (integrated patterns, cakes). They are
plain dataclasses, so the whole tree can be serialized generically (see
hdf5.py), and evented via psygnal: assigning a new value to a field emits
``instance.events.<field>(new_value, old_value)`` as well as the aggregated
``instance.events`` group signal. Assigning an equal value emits nothing.

In-place mutation of mutable fields (``params.working_directories["mask"] =
...``) does not emit — assign a new object to the field when listeners need
to know.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import ClassVar

from psygnal import SignalGroupDescriptor

__all__ = [
    "ConfigurationParams",
    "ImgParams",
    "PatternParams",
    "ViewParams",
    "default_working_directories",
]


def default_working_directories() -> dict[str, str]:
    return {
        "calibration": "",
        "mask": "",
        "image": os.path.expanduser("~"),
        "pattern": "",
        "overlay": "",
        "phase": "",
        "batch": os.path.expanduser("~"),
    }


@dataclass
class ViewParams:
    """View state of the GUI that is not derivable from the data models.

    Owned by DioptasModel (a single, stable instance — load applies fields
    onto it instead of replacing it, so event subscriptions stay valid).
    Controllers write it and react to its change events; keeping it in the
    model makes it persistable and testable without widgets.
    """

    events: ClassVar[SignalGroupDescriptor] = SignalGroupDescriptor()

    #: what the integration image panel shows: "Image" or "Cake"
    img_mode: str = "Image"


@dataclass
class ImgParams:
    """User-settable parameters of an ImgModel.

    Owned by :class:`dioptas.model.ImgModel.ImgModel`, which exposes them
    through delegating properties that add side effects (image
    recalculation, directory-watcher activation). Writing the fields here
    directly bypasses those side effects but still emits change events.
    """

    events: ClassVar[SignalGroupDescriptor] = SignalGroupDescriptor()

    autoprocess: bool = False
    #: int default is deliberate: it keeps pristine img_data in the image's
    #: native dtype (uint16 * 1 stays uint16); any user-set factor is
    #: coerced to float by ImgModel.factor so integer multiplication can
    #: never wrap the pixel values
    factor: float = 1

    background_scaling: float = 1.0
    background_offset: float = 0.0

    #: how prev/next iterate through files: "number" or "time"
    file_iteration_mode: str = "number"


@dataclass
class PatternParams:
    """User-settable parameters of a PatternModel.

    Owned by :class:`dioptas.model.PatternModel.PatternModel`; the model's
    properties delegate here. Writing fields directly bypasses model side
    effects but still emits change events.
    """

    events: ClassVar[SignalGroupDescriptor] = SignalGroupDescriptor()

    #: unit of the current pattern's x-axis ("", "2th_deg", "q_A^-1", "d_A")
    unit: str = ""

    #: how prev/next iterate through pattern files: "number" or "time"
    file_iteration_mode: str = "number"


@dataclass
class ConfigurationParams:
    """User-settable parameters of a single Configuration.

    Owned by :class:`dioptas.model.Configuration.Configuration`, which
    exposes them through delegating properties that add side effects
    (re-integration, signal re-wiring). Reading/writing the fields here
    directly bypasses those side effects but still emits change events.
    """

    events: ClassVar[SignalGroupDescriptor] = SignalGroupDescriptor()

    working_directories: dict[str, str] = field(
        default_factory=default_working_directories
    )

    use_mask: bool = False
    transparent_mask: bool = False

    integration_rad_points: int | None = None
    integration_unit: str = "2th_deg"
    oned_azimuth_range: list[float] | None = None
    trim_trailing_zeros: bool = True

    cake_azimuth_points: int = 360
    cake_azimuth_range: list[float] | None = None

    auto_integrate_pattern: bool = True
    auto_integrate_cake: bool = False

    auto_save_integrated_pattern: bool = False
    integrated_patterns_file_formats: list[str] = field(
        default_factory=lambda: [".xy"]
    )
