# SPDX-License-Identifier: MIT

"""Generic HDF5 (de)serialization for params dataclasses.

A params object is stored as one JSON document inside a named subgroup:

    <parent group>/
        params/
            @schema_version = 1
            @class = "ConfigurationParams"
            @data = '{"use_mask": false, ...}'

JSON keeps the encoding independent of h5py attribute-type quirks (None,
heterogeneous lists, nested dicts) and makes the whole object diffable in
any HDF5 viewer. Loading is tolerant in both directions: unknown keys are
ignored (file newer than code), missing keys keep their dataclass defaults
(file older than code).
"""

from __future__ import annotations

import dataclasses
import json
import typing
from typing import Any, TypeVar

import h5py
import numpy as np

__all__ = ["save_params", "load_params", "params_to_dict", "params_from_dict"]

SCHEMA_VERSION = 1

T = TypeVar("T")


def _json_default(obj: object) -> int | float | list:
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def params_to_dict(params: Any) -> dict:
    """Converts a params dataclass (including nested dataclasses) to a dict."""
    return dataclasses.asdict(params)


def params_from_dict(cls: type[T], data: dict) -> T:
    """Constructs a params dataclass from a dict, tolerantly.

    Unknown keys in *data* are ignored, missing keys keep the dataclass
    defaults, and dict values for nested dataclass fields are recursed.
    """
    try:
        hints = typing.get_type_hints(cls)
    except Exception:
        hints = {}
    kwargs = {}
    for f in dataclasses.fields(cls):
        if f.name not in data:
            continue
        value = data[f.name]
        field_type = hints.get(f.name)
        if (
            dataclasses.is_dataclass(field_type)
            and isinstance(field_type, type)
            and isinstance(value, dict)
        ):
            value = params_from_dict(field_type, value)
        kwargs[f.name] = value
    return cls(**kwargs)


def save_params(parent: h5py.Group, params: Any, name: str = "params") -> None:
    """Saves a params dataclass as a JSON document in parent[name]."""
    group = parent.require_group(name)
    group.attrs["schema_version"] = SCHEMA_VERSION
    group.attrs["class"] = type(params).__name__
    group.attrs["data"] = json.dumps(params_to_dict(params), default=_json_default)


def load_params(parent: h5py.Group, cls: type[T], name: str = "params") -> T | None:
    """Loads a params dataclass from parent[name].

    Returns None if the group does not exist (e.g. project files written
    before the params layer was introduced).
    """
    if name not in parent:
        return None
    data = json.loads(parent[name].attrs["data"])
    return params_from_dict(cls, data)
