# SPDX-License-Identifier: MIT

"""Unified, serializable application state.

This package is the foundation of the ongoing state refactor: user-settable
parameters move out of the individual models into plain evented dataclasses
(see params.py) that can be saved and loaded generically (see hdf5.py),
instead of being serialized field-by-field in hand-written HDF5 code.
"""

from .params import (
    apply_params,
    CalibrationParams,
    ConfigurationParams,
    ImgParams,
    MapParams,
    MapRoiParams,
    MaskParams,
    OverlayItemParams,
    PatternParams,
    PhaseItemParams,
    PhaseParams,
    ViewParams,
    default_working_directories,
)
from .hdf5 import (
    save_params,
    load_params,
    params_to_dict,
    params_from_dict,
    SCHEMA_VERSION,
    PROJECT_FORMAT_VERSION,
)
from .derived import Derived
from .history import History
from .payload import Payload, PayloadStore

__all__ = [
    "apply_params",
    "CalibrationParams",
    "ConfigurationParams",
    "ImgParams",
    "MapParams",
    "MapRoiParams",
    "MaskParams",
    "OverlayItemParams",
    "PatternParams",
    "PhaseItemParams",
    "PhaseParams",
    "ViewParams",
    "default_working_directories",
    "save_params",
    "load_params",
    "params_to_dict",
    "params_from_dict",
    "SCHEMA_VERSION",
    "PROJECT_FORMAT_VERSION",
    "Derived",
    "History",
    "Payload",
    "PayloadStore",
]
