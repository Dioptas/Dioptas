# SPDX-License-Identifier: MIT

"""Snapshots of a DioptasModel, and the recorder that drives its history.

This is the Dioptas-specific half of undo/redo; :class:`History` holds the
generic stack. Kept apart so the stack can be tested without a model, and so
the (long) list of decisions about *what* is undoable lives in one readable
place.

What a snapshot holds
---------------------
Every configuration's params, the global phase params, each configuration's
user-drawn mask, and the mask plugins' enabled state and settings. Params are
captured as plain dicts (about 1.5 kB for the whole tree), so settings-only
steps are essentially free. Masks are captured as compressed blobs and shared
by reference between snapshots that did not touch them — a hundred steps of
spinbox fiddling therefore costs one mask, not a hundred.

What it deliberately does not hold
----------------------------------
``ViewParams`` (panel layout, docking, image/cake mode): undo is for the work,
not the furniture — rewinding a settings change should not also undock a
window. ``working_directories``: bookkeeping that follows the last file
dialog, never something the user "did". Loaded images and integrated patterns:
undo covers edits, not navigation, and holding image data per step would cost
orders of magnitude more than everything else combined.

Configuration structure
-----------------------
Adding or removing a configuration resets the history rather than being
undoable. Restoring a snapshot with a different number of configurations would
mean creating or destroying Configuration objects along with their signal
wiring; the honest, predictable rule is that undo does not cross a structural
change.
"""

from __future__ import annotations

import zlib
from contextlib import ExitStack
from dataclasses import dataclass
from typing import Any

import numpy as np

from .history import History
from .params import apply_params
from .hdf5 import params_to_dict, params_from_dict

__all__ = ["Snapshot", "StateRecorder"]

#: params fields that are captured but never restored (see module docstring)
_CONFIG_EXCLUDED = {"working_directories"}


@dataclass(frozen=True)
class _MaskBlob:
    """A compressed, immutable mask. Shared between snapshots by reference."""

    data: bytes
    shape: tuple[int, ...]

    def unpack(self) -> np.ndarray:
        packed = np.frombuffer(zlib.decompress(self.data), dtype=np.uint8)
        size = int(np.prod(self.shape))
        return np.unpackbits(packed)[:size].reshape(self.shape).astype(bool)

    @classmethod
    def pack(cls, mask: np.ndarray) -> _MaskBlob:
        # level 1: masks are mostly large uniform regions, so the cheapest
        # setting already gets the bulk of the ratio (see changelog 0.8.7)
        return cls(zlib.compress(np.packbits(mask).tobytes(), 1), mask.shape)


@dataclass(frozen=True)
class _ConfigState:
    params: dict
    img: dict
    pattern: dict
    mask: dict
    calibration: dict
    map: dict
    mask_data: _MaskBlob
    plugins: tuple


@dataclass(frozen=True)
class Snapshot:
    configurations: tuple
    phase: dict


class StateRecorder:
    """Wires a :class:`History` to a DioptasModel.

    Owns the capture/restore functions and decides which model signals mark an
    undoable step. The history itself is exposed as ``.history``.
    """

    def __init__(self, model: Any, **history_kwargs: Any) -> None:
        self._model = model
        # capturing a mask costs about a millisecond, so the blob is reused
        # until something says the mask changed
        self._mask_cache: dict[int, _MaskBlob] = {}
        self._mask_shapes: dict[int, tuple] = {}
        self._mask_shapes_changed()  # seed, so the first edit is not a resize
        self.history = History(self.capture, self.restore, **history_kwargs)
        self._connect()

    # -- wiring -----------------------------------------------------------

    def _connect(self) -> None:
        model = self._model
        model.configuration_params_changed.connect(self._on_params_changed)
        model.mask_changed.connect(self._on_mask_changed)
        # a structural change makes older snapshots inapplicable
        model.configuration_added.connect(self._on_structure_changed)
        model.configuration_removed.connect(self._on_structure_changed)

    def _on_params_changed(self, field: str, new: Any, old: Any) -> None:
        self.history.record(label=_label_for(field), key=field)

    def _on_mask_changed(self) -> None:
        # the blob for the edited mask is stale; recaptured on demand
        self._mask_cache.clear()
        if self._mask_shapes_changed():
            # a new image of a different size resets the mask, so every older
            # snapshot holds a mask of the wrong shape; undoing into one would
            # put a mask on screen that does not match the image
            self.history.reset()
            return
        self.history.record(label="mask")

    def _mask_shapes_changed(self) -> bool:
        shapes = {
            id(c.mask_model): tuple(c.mask_model.mask_dimension)
            for c in self._model.configurations
        }
        changed = shapes != self._mask_shapes
        self._mask_shapes = shapes
        return changed

    def _on_structure_changed(self, *args: Any) -> None:
        self._mask_cache.clear()
        self.history.reset()

    # -- capture ----------------------------------------------------------

    def capture(self) -> Snapshot:
        return Snapshot(
            configurations=tuple(
                self._capture_configuration(c) for c in self._model.configurations
            ),
            phase=params_to_dict(self._model.phase_model.params),
        )

    def _capture_configuration(self, configuration: Any) -> _ConfigState:
        return _ConfigState(
            params=params_to_dict(configuration.params),
            img=params_to_dict(configuration.img_model.params),
            pattern=params_to_dict(configuration.pattern_model.params),
            mask=params_to_dict(configuration.mask_model.params),
            calibration=params_to_dict(configuration.calibration_model.params),
            map=params_to_dict(configuration.map_model.params),
            mask_data=self._capture_mask(configuration.mask_model),
            plugins=_capture_plugins(configuration.mask_plugin_manager),
        )

    def _capture_mask(self, mask_model: Any) -> _MaskBlob:
        key = id(mask_model)
        blob = self._mask_cache.get(key)
        if blob is None:
            blob = _MaskBlob.pack(mask_model.get_img())
            self._mask_cache[key] = blob
        return blob

    # -- restore ----------------------------------------------------------

    def restore(self, snapshot: Snapshot) -> None:
        model = self._model
        configurations = model.configurations
        if len(snapshot.configurations) != len(configurations):
            # cannot happen while structural changes reset the history, but
            # restoring a mismatched snapshot would corrupt state silently
            return

        with ExitStack() as stack:
            # one undo must cost one integration, not one per field it touches
            for configuration in configurations:
                stack.enter_context(configuration.pattern_integration.hold())
                stack.enter_context(configuration.cake_integration.hold())
            for state, configuration in zip(snapshot.configurations, configurations):
                self._restore_configuration(state, configuration)
            _apply_dict(model.phase_model.params, snapshot.phase)

        self._mask_cache.clear()

    def _restore_configuration(self, state: _ConfigState, configuration: Any) -> None:
        _apply_dict(configuration.params, state.params, exclude=_CONFIG_EXCLUDED)
        _apply_dict(configuration.img_model.params, state.img)
        _apply_dict(configuration.pattern_model.params, state.pattern)
        _apply_dict(configuration.mask_model.params, state.mask)
        _apply_dict(configuration.calibration_model.params, state.calibration)
        _apply_dict(configuration.map_model.params, state.map)

        _restore_plugins(configuration.mask_plugin_manager, state.plugins)
        # belt and braces: a resize resets the history, so a stale shape
        # should be unreachable — but writing one back would leave a mask
        # that does not match the image, which surfaces as a blocking dialog
        if tuple(state.mask_data.shape) == tuple(
            configuration.mask_model.mask_dimension
        ):
            configuration.mask_model.set_mask_data(state.mask_data.unpack())


def _apply_dict(target: Any, values: dict, exclude: set[str] | None = None) -> None:
    """Applies a captured params dict onto the live params instance.

    Goes through apply_params so the instance keeps its identity — every
    subscription on it stays valid and each changed field emits its event,
    which is what makes the GUI and the re-integrations follow an undo.
    """
    source = params_from_dict(type(target), values)
    apply_params(target, source, exclude=exclude)


def _capture_plugins(manager: Any) -> tuple:
    if manager is None:
        return ()
    return tuple(
        (name, entry.enabled, dict(entry.plugin.get_settings()))
        for name, entry in sorted(manager.plugins.items())
    )


def _restore_plugins(manager: Any, plugins: tuple) -> None:
    if manager is None:
        return
    for name, enabled, settings in plugins:
        entry = manager.plugins.get(name)
        if entry is None:
            continue
        if entry.plugin.get_settings() != settings:
            manager.update_plugin_settings(name, settings)
        if entry.enabled != enabled:
            manager.set_enabled(name, enabled)


#: field name -> what the user would call it, for the undo menu entry
_LABELS = {
    "integration_unit": "integration unit",
    "integration_rad_points": "integration points",
    "cake_azimuth_points": "cake azimuth points",
    "use_mask": "mask usage",
    "transparent_mask": "mask transparency",
    "img.factor": "image factor",
    "mask.roi": "mask region of interest",
    "mask.mode": "mask drawing mode",
}


def _label_for(field: str) -> str:
    if field in _LABELS:
        return _LABELS[field]
    return field.rsplit(".", 1)[-1].replace("_", " ")
