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
any HDF5 viewer.

Versioning policy for .dio project files
----------------------------------------

Three version markers exist, each with a distinct job:

- ``/@__version__`` (root attribute, string): the Dioptas application
  version that wrote the file. Informational only — never used to branch
  loading logic.
- ``/@format_version`` (root attribute, int, :data:`PROJECT_FORMAT_VERSION`):
  the overall .dio layout version. Files written before its introduction
  have no such attribute and are treated as the legacy layout (version 0,
  field-by-field attributes only). Increment when groups/datasets move or
  change meaning; add a migration branch in the loader keyed on it.
- ``params/@schema_version`` (per params group, int,
  :data:`SCHEMA_VERSION`): the encoding of the params document itself.
  Adding/removing dataclass fields does NOT bump this — that is handled by
  tolerant loading (unknown keys are ignored: file newer than code; missing
  keys keep their dataclass defaults: file older than code). Increment only
  when the encoding mechanics change (e.g. the JSON layout), with a
  migration keyed on the stored value.

A params group with a ``schema_version`` newer than this code can decode is
skipped (:func:`load_params` returns None) so the loader falls back to the
legacy attributes, which writers keep emitting alongside the params group.

Caution: when a params group is placed inside an HDF5 group whose children
are *iterated* as items (e.g. the numbered phase groups in ``phases``), the
iterating loader must skip the reserved ``params`` name.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import types
import typing
from typing import Any, TypeVar

import h5py
import numpy as np

__all__ = [
    "save_params",
    "load_params",
    "params_to_dict",
    "params_from_dict",
    "SCHEMA_VERSION",
    "PROJECT_FORMAT_VERSION",
]

logger = logging.getLogger(__name__)

#: version of the params-group JSON encoding (see module docstring)
SCHEMA_VERSION = 1

#: version of the overall .dio project file layout (see module docstring).
#: Stays at 1 while writers still emit the legacy field-by-field attributes
#: alongside the params documents: the file remains readable by Dioptas
#: versions that predate the params layer, so there is nothing for a reader
#: to branch on. Bump to 2 together with dropping the legacy writer — that
#: is the change older versions must not silently misread.
PROJECT_FORMAT_VERSION = 1

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


def _wants_tuple(field_type: Any) -> bool:
    """Whether a dataclass field is declared as a tuple (JSON has no tuples)."""
    if field_type is tuple:
        return True
    origin = typing.get_origin(field_type)
    if origin is tuple:
        return True
    if origin in (typing.Union, types.UnionType):
        return any(_wants_tuple(arg) for arg in typing.get_args(field_type))
    return False


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
        elif isinstance(value, list) and _wants_tuple(field_type):
            # JSON round-trips tuples as lists; restore the declared type so
            # a loaded value compares equal to a freshly set one
            value = tuple(value)
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
    before the params layer was introduced) or if its schema_version is
    newer than this code can decode — callers fall back to the legacy
    field-by-field attributes in both cases.
    """
    if name not in parent:
        return None
    group = parent[name]
    try:
        version = int(group.attrs.get("schema_version", 1))
        if version > SCHEMA_VERSION:
            logger.warning(
                "params group '%s' has schema_version %d, newer than supported %d "
                "— falling back to legacy attributes",
                name,
                version,
                SCHEMA_VERSION,
            )
            return None
        data = json.loads(group.attrs["data"])
        return params_from_dict(cls, data)
    except (KeyError, ValueError, TypeError) as e:
        # corrupt params must not abort loading — the legacy attributes are
        # still present in the file and cover the overlapping fields
        logger.warning(
            "params group '%s' could not be decoded (%s) "
            "— falling back to legacy attributes",
            name,
            e,
        )
        return None
