# SPDX-License-Identifier: MIT

"""Reading and writing ``.dio`` project files (format 2).

The layout follows the state rules the migration established, so the file is
essentially the state tree plus the binary it references:

``/state``
    One JSON document holding every params document in the model — view,
    per-configuration settings, overlays, phases — plus the small structural
    values that tie them together. One place to read, one place to version,
    and no per-field attribute writing: adding a params field changes nothing
    here.
``/payloads/<content-id>``
    *Owned* binary data — the user-drawn masks, overlay curves, an anonymous
    background pattern. Irreproducible, so the bytes are the state. Stored
    under a content hash, which deduplicates identical masks across
    configurations for free.
``/cache/<content-id>``
    *External* payloads: copies of the image (and background image) pixels.
    The state is the file path; these copies only make the project readable
    when the original files have moved. Same content addressing.
``/configurations/<i>/map``
    The map sub-document keeps its own layout — it is bulk array data with
    its own save/load, and squeezing it through JSON would be a step
    backwards.

What this replaced: a tree of per-field HDF5 attributes written alongside the
params documents (so every value existed twice, and the two could disagree),
with one *group per reflection* — a two-phase project spent 72 groups on what
is now two JSON entries.

Files written before format 2 are refused by DioptasModel.load; there is no
legacy reader here.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Any

import h5py
import numpy as np

from .hdf5 import params_to_dict, params_from_dict
from .params import apply_params

__all__ = ["save_project", "load_project"]

logger = logging.getLogger(__name__)


def _json_default(obj: Any) -> Any:
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.generic):
        return obj.item()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


class _ArrayStore:
    """Content-addressed array storage inside one HDF5 group.

    Arrays are written natively (not as opaque blobs) with gzip+shuffle, so
    any HDF5 viewer can still read a project. Identical content is stored
    once — two configurations masking the same detector share a dataset.
    """

    def __init__(self, group: h5py.Group) -> None:
        self._group = group
        self._written: set[str] = set()

    def put(self, array: np.ndarray | None) -> str | None:
        if array is None:
            return None
        array = np.ascontiguousarray(array)
        key = hashlib.sha1(
            f"{array.dtype.str}:{array.shape}:".encode() + array.tobytes()
        ).hexdigest()
        if key not in self._written:
            self._group.create_dataset(
                key, data=array, compression="gzip", compression_opts=1, shuffle=True
            )
            self._written.add(key)
        return key

    def get(self, key: str | None) -> np.ndarray | None:
        if key is None or key not in self._group:
            return None
        return self._group[key][...]


# ---------------------------------------------------------------------------
# saving
# ---------------------------------------------------------------------------


def save_project(model: Any, f: h5py.File) -> None:
    payloads = _ArrayStore(f.create_group("payloads"))
    cache = _ArrayStore(f.create_group("cache"))

    document = {
        "selected_configuration": int(model.configuration_ind),
        "view": params_to_dict(model.view),
        "phase": params_to_dict(model.phase_model.params),
        "configurations": [
            _capture_configuration(configuration, payloads, cache)
            for configuration in model.configurations
        ],
        "overlays": [
            {
                "params": params_to_dict(overlay.params),
                "x": payloads.put(overlay.original_data[0]),
                "y": payloads.put(overlay.original_data[1]),
            }
            for overlay in model.overlay_model.overlays
        ],
        "phases": [_capture_phase(item) for item in model.phase_model.items],
    }
    f.create_dataset("state", data=json.dumps(document, default=_json_default))

    # the map keeps its own layout: bulk arrays with a tested save/load
    configurations_group = f.create_group("configurations")
    for ind, configuration in enumerate(model.configurations):
        configuration.map_model.save_in_hdf5(
            configurations_group.create_group(str(ind))
        )


def _capture_configuration(
    configuration: Any, payloads: _ArrayStore, cache: _ArrayStore
) -> dict:
    img_model = configuration.img_model
    pattern_model = configuration.pattern_model

    background_pattern = pattern_model.background_pattern
    anonymous_background = None
    if (
        background_pattern is not None
        and pattern_model.params.background_overlay_uid is None
    ):
        # a background no overlay owns (see PatternParams.background_overlay_uid)
        anonymous_background = {
            "x": payloads.put(background_pattern._original_x),
            "y": payloads.put(background_pattern._original_y),
        }

    return {
        "params": params_to_dict(configuration.params),
        "img": params_to_dict(img_model.params),
        "pattern": params_to_dict(pattern_model.params),
        "mask": params_to_dict(configuration.mask_model.params),
        "calibration": params_to_dict(configuration.calibration_model.params),
        "map": params_to_dict(configuration.map_model.params),
        # owned: the user drew it, nothing else can reproduce it
        "mask_data": payloads.put(configuration.mask_model.get_img()),
        # external: copies so the project opens when the files have moved
        # untransformed: the transformations are state and re-applied on
        # load, so caching the transformed pixels would apply them twice
        "image_data": cache.put(img_model.untransformed_raw_img_data),
        "background_data": cache.put(img_model.untransformed_background_data)
        if img_model.has_background()
        else None,
        "series_max": int(img_model.series_max),
        "plugins": {
            name: {
                "enabled": bool(entry.enabled),
                # has_settings is a property on the plugin base
                "settings": entry.plugin.get_settings()
                if entry.plugin.has_settings
                else {},
            }
            for name, entry in configuration.mask_plugin_manager.plugins.items()
        },
        "anonymous_background": anonymous_background,
        "pattern_x": payloads.put(getattr(pattern_model.pattern, "_original_x", None)),
        "pattern_y": payloads.put(getattr(pattern_model.pattern, "_original_y", None)),
    }


def _capture_phase(item: Any) -> dict:
    return {
        "params": params_to_dict(item.params),
        "filename": item.filename,
        "name": str(item.jcpds._name),
        "crystal": params_to_dict(item.jcpds.state),
        "reflections": [
            [r.h, r.k, r.l, r.intensity, r.d0] for r in item.jcpds.reflections
        ],
    }


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------


def load_project(model: Any, f: h5py.File, make_configuration) -> None:
    """Applies a project file onto *model*.

    *make_configuration* builds a fresh Configuration — passed in rather than
    imported to keep this module free of a cycle back to the model package.
    """
    document = json.loads(f["state"][()])
    payloads = _ArrayStore(f["payloads"]) if "payloads" in f else _ArrayStore(f)
    cache = _ArrayStore(f["cache"]) if "cache" in f else _ArrayStore(f)

    # loading a project replaces the session. Phases and overlays are global
    # rather than per-configuration, so clearing the configurations is not
    # enough — without this they accumulate across loads.
    model.phase_model.reset()
    model.overlay_model.reset()
    model.configurations = []
    for ind, config_document in enumerate(document["configurations"]):
        configuration = make_configuration()
        _apply_configuration(configuration, config_document, payloads, cache)
        model.attach_configuration(configuration)
        if "configurations" in f and str(ind) in f["configurations"]:
            configuration.map_model.load_from_hdf5(f["configurations"][str(ind)])

    model.configuration_ind = int(document.get("selected_configuration", 0))
    model.connect_models()
    model.invalidate_multi_geometry()
    model.configuration_added.emit()
    model.select_configuration(model.configuration_ind)

    for phase_document in document.get("phases", []):
        _add_phase(model.phase_model, phase_document)

    for overlay_document in document.get("overlays", []):
        overlay = model.overlay_model.add_overlay(
            payloads.get(overlay_document["x"]),
            payloads.get(overlay_document["y"]),
            overlay_document["params"].get("name", ""),
        )
        _apply_params_dict(overlay.params, overlay_document["params"])

    _apply_params_dict(model.phase_model.params, document.get("phase", {}))
    _apply_params_dict(model.view, document.get("view", {}))

    # overlays exist now, so background references can be pointed at them
    model.resolve_background_overlays()

    for configuration in model.configurations:
        if configuration.calibration_model.is_calibrated:
            configuration.integrate_image_1d()
        else:
            configuration.pattern_model.pattern.recalculate_pattern()


def _apply_configuration(
    configuration: Any, document: dict, payloads: _ArrayStore, cache: _ArrayStore
) -> None:
    img_model = configuration.img_model

    # the pixels first: everything below is applied on top of the image the
    # project was saved with, and the mask has to fit it
    image_data = cache.get(document.get("image_data"))
    if image_data is not None:
        img_model._img_data = np.copy(image_data)
    background_data = cache.get(document.get("background_data"))
    if background_data is not None:
        img_model.background_data = np.copy(background_data)
    img_model.series_max = int(document.get("series_max", 1))
    # announce the restored pixels: the detector learns its shape here, and
    # the mask plugins get their image — without this the cake geometry is
    # built from a detector that never saw one
    img_model.img_changed.emit()

    # Calibration before the image params: rebuilding an absorption
    # correction (part of the img params) needs the geometry's angle grids —
    # the same order the undo restore uses.
    _apply_params_dict(
        configuration.calibration_model.params,
        document["calibration"],
        # machine-specific, deliberately not restored from project files
        exclude={"use_dioptrin", "dioptrin_num_workers"},
    )
    _apply_params_dict(
        configuration.params,
        document["params"],
        # the working directories of the machine that saved the file may not
        # exist here; validated separately below
        # auto-save is applied last: integrations run while this document is
        # being applied, and auto-saving them before the image filename is
        # restored would write patterns named after nothing
        exclude={"working_directories", "auto_save_integrated_pattern"},
    )
    configuration.params.working_directories = {
        key: value if os.path.isdir(value) else ""
        for key, value in document["params"].get("working_directories", {}).items()
    }

    # the image is already on screen (restored from the cache above), so the
    # params must say which file it was without the reconcile re-reading it
    img_params = document["img"]
    _apply_params_dict(
        img_model.params,
        img_params,
        exclude={"filename", "series_pos", "background_filename", "transformations"},
    )
    img_model.set_transformations(img_params.get("transformations", []))
    img_model.set_loaded_file_state(
        filename=img_params.get("filename", ""),
        series_pos=int(img_params.get("series_pos", 1)),
        background_filename=img_params.get("background_filename", ""),
    )
    try:
        img_model.file_name_iterator.update_filename(img_model.filename)
        img_model._directory_watcher.path = os.path.dirname(img_model.filename)
    except EnvironmentError:
        logger.warning("Could not follow the image directory from the project")

    _apply_params_dict(configuration.mask_model.params, document["mask"])
    mask_data = payloads.get(document.get("mask_data"))
    if mask_data is not None:
        configuration.mask_model.set_mask_data(np.array(mask_data, dtype=bool))

    for name, plugin_state in document.get("plugins", {}).items():
        manager = configuration.mask_plugin_manager
        if name not in manager.plugins:
            continue
        settings = plugin_state.get("settings") or {}
        if settings:
            manager.update_plugin_settings(name, settings)
        manager.set_enabled(name, bool(plugin_state.get("enabled", False)))

    pattern_x = payloads.get(document.get("pattern_x"))
    pattern_y = payloads.get(document.get("pattern_y"))
    if pattern_x is not None and pattern_y is not None and len(pattern_x):
        configuration.pattern_model.pattern.data = (pattern_x, pattern_y)
    _apply_params_dict(
        configuration.pattern_model.params,
        document["pattern"],
        # the pattern itself was just restored; re-reading or re-resolving is
        # the loader's job below, not a side effect of applying the params
        exclude={"pattern_source", "pattern_filename", "background_overlay_uid"},
    )
    configuration.pattern_model.pattern_source = document["pattern"].get(
        "pattern_source", "integrated"
    )
    configuration.pattern_model.pattern_filename = document["pattern"].get(
        "pattern_filename", ""
    )
    configuration.pattern_model._sync_file_params()

    anonymous = document.get("anonymous_background")
    if anonymous is not None:
        from xypattern import Pattern

        configuration.pattern_model.background_pattern = Pattern(
            payloads.get(anonymous["x"]),
            payloads.get(anonymous["y"]),
            "background_pattern",
        )
        configuration.pattern_model.params.background_overlay_uid = None
    else:
        configuration.pattern_model.params.background_overlay_uid = document[
            "pattern"
        ].get("background_overlay_uid", "")

    _apply_params_dict(configuration.map_model.params, document["map"])

    # everything is in place now, so auto-saving an integration is safe
    configuration.params.auto_save_integrated_pattern = bool(
        document["params"].get("auto_save_integrated_pattern", False)
    )


def _add_phase(phase_model: Any, document: dict) -> None:
    from ..util.jcpds import CrystalState, jcpds, jcpds_reflection

    phase = jcpds()
    phase._filename = document.get("filename", "")
    phase._name = document.get("name", "")
    apply_params(phase.state, params_from_dict(CrystalState, document["crystal"]))
    phase.reflections = [
        jcpds_reflection(h, k, l, intensity, d0)
        for h, k, l, intensity, d0 in document.get("reflections", [])
    ]
    phase.compute_d()
    # applying the state must not invent an edit: the flag travels with it
    phase.state.modified = bool(document["crystal"].get("modified", False))

    phase_model.add_jcpds_object(phase, filename=document.get("filename", ""))
    _apply_params_dict(phase_model.items[-1].params, document["params"])


def _apply_params_dict(
    target: Any, values: dict, exclude: set[str] | None = None
) -> None:
    """Applies a saved params document onto a live params instance, so every
    changed field emits its event and runs its reaction."""
    apply_params(target, params_from_dict(type(target), values), exclude=exclude)
