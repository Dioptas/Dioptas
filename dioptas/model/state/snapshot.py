# SPDX-License-Identifier: MIT

"""Snapshots of a DioptasModel, and the recorder that drives its history.

This is the Dioptas-specific half of undo/redo; :class:`History` holds the
generic stack. Kept apart so the stack can be tested without a model, and so
the (long) list of decisions about *what* is undoable lives in one readable
place.

What a snapshot holds
---------------------
Every configuration's params, the global phase params, each configuration's
user-drawn mask, the mask plugins' enabled state and settings, and the overlay
and phase lists with their display state. Params are captured as plain dicts
(about 1.5 kB for the whole tree), so settings-only steps are essentially
free.

The bulky parts are shared rather than copied, each according to how it is
mutated:

- Masks live in the model's content-addressed PayloadStore (see payload.py);
  snapshots hold their ids, so unchanged masks contribute a string to each
  snapshot rather than a copy, and identical masks are stored once however
  many steps or configurations reference them. Payloads are garbage-collected
  against the history whenever it changes.
- Overlays are referenced directly. Their x/y data is replaced, never edited
  in place, so undoing a removal can put the original object back instead of a
  look-alike the pattern view would have to re-create.
- Phases are deep-copied, because jcpds objects *are* edited in place when
  pressure or temperature change; a reference would let a later edit rewrite
  history. A content fingerprint decides when a fresh copy is needed, so an
  unchanged phase is copied once no matter how many steps it survives.

The image is held as a *path* (ImgParams.filename), not as pixels — the
pixels are re-readable from the file, so the path is the state and holding
data per step would dwarf everything else. Restoring the params makes
ImgModel's reconcile reaction re-read the file; the mask is applied after the
img params, so it always fits the image it was drawn on, even across
detectors of different sizes. A file that has since moved is skipped with a
warning (inside the reaction) rather than aborting the rest of the restore.

What it deliberately does not hold
----------------------------------
``ViewParams`` (panel layout, docking, image/cake mode): undo is for the work,
not the furniture — rewinding a settings change should not also undock a
window. ``working_directories``: bookkeeping that follows the last file
dialog, never something the user "did". Integrated patterns and cakes: they
are derived, and recomputed from what is restored.

Configuration structure
-----------------------
Adding or removing a configuration resets the history rather than being
undoable. Restoring a snapshot with a different number of configurations would
mean creating or destroying Configuration objects along with their signal
wiring; the honest, predictable rule is that undo does not cross a structural
change.
"""

from __future__ import annotations

import copy as _copy
import logging
import os
from contextlib import ExitStack
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .history import History
from .params import apply_params
from .hdf5 import params_to_dict, params_from_dict

logger = logging.getLogger(__name__)

__all__ = ["Snapshot", "StateRecorder"]

#: params fields that are captured but never restored (see module docstring)
_CONFIG_EXCLUDED = {"working_directories"}

#: Fields whose change is only part of a larger operation that goes on to emit
#: a signal of its own. Recording them as well would cost two undo steps for
#: one action, and — worse — the first of those steps would be captured
#: mid-operation: rotating an image records the new transformation before the
#: mask has been resized to match, a state that never actually existed.
#: fields where consecutive writes are separate decisions, never a drag
_NO_COALESCE = {"calibration.peak_selections"}

_RECORDED_ELSEWHERE = {
    "img.transformations",
    # file loads end with img_changed, which records the settled state;
    # these fire mid-load and would capture a half-applied one
    "img.filename",
    "img.series_pos",
    "img.background_filename",
    # the calibration result settles via parameters_changed, which records
    # once; these fire mid-operation while the sync writes them field by field
    "calibration.detector_mode",
    "calibration.detector_name",
    "calibration.detector_filename",
    "calibration.geometry",
    "calibration.is_calibrated",
    "calibration.poni_filename",
    "calibration.calibration_name",
    # pattern loads and background changes settle via pattern_changed;
    # unit is written by set_pattern inside every integration cascade
    "pattern.unit",
    "pattern.pattern_source",
    "pattern.pattern_filename",
    "pattern.background_overlay_uid",
}


@dataclass(frozen=True, eq=False)
class _Ref:
    """Holds a value that must be compared by identity rather than content.

    Snapshots are compared with ``==`` to spot writes that changed nothing.
    A numpy array inside one breaks that: ``==`` is element-wise and yields an
    array, which is neither True nor False. Identity is also the question we
    actually want to ask of shared immutable payloads — overlay data and phase
    copies are replaced, never edited in place, so "same object" means
    "unchanged" and costs a pointer comparison instead of a full scan.
    """

    value: Any

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, _Ref) and other.value is self.value

    def __hash__(self) -> int:
        return id(self.value)


@dataclass(frozen=True)
class _ConfigState:
    params: dict
    img: dict
    pattern: dict
    mask: dict
    calibration: dict
    map: dict
    #: content id of the user-drawn mask in the model's PayloadStore —
    #: a plain string, so snapshot equality never touches the pixels and
    #: identical masks (across steps or configurations) share one blob
    mask_data: str
    plugins: tuple


@dataclass(frozen=True)
class _OverlayState:
    #: the Overlay object itself, so undoing a removal puts the original back
    #: rather than a look-alike the pattern view would have to re-create
    overlay: _Ref
    params: dict


@dataclass(frozen=True)
class _PhaseState:
    #: An immutable deep copy — unlike overlays, jcpds objects are edited in
    #: place when pressure or temperature change, so a reference would let
    #: later edits rewrite history. Excluded from equality: two copies of an
    #: unchanged phase are different objects, and comparing them by identity
    #: would report a change on every capture that had to re-copy.
    phase: _Ref = field(compare=False)
    #: what equality actually rests on — cheap and content-based
    fingerprint: tuple = ()
    item_params: dict = field(default_factory=dict)
    filename: str = ""


@dataclass(frozen=True)
class Snapshot:
    configurations: tuple
    phase: dict
    overlays: tuple
    phases: tuple


class StateRecorder:
    """Wires a :class:`History` to a DioptasModel.

    Owns the capture/restore functions and decides which model signals mark an
    undoable step. The history itself is exposed as ``.history``.
    """

    def __init__(self, model: Any, **history_kwargs: Any) -> None:
        self._model = model
        # capturing a mask costs about a millisecond, so the blob is reused
        # until something says the mask changed
        self._mask_cache: dict[int, str] = {}
        # copying a phase costs a few tens of microseconds, which would dwarf
        # a settings snapshot if it happened on every capture
        self._phase_cache: dict[int, _Ref] = {}
        #: label of an action whose own record is suppressed, applied to
        #: the next record so the step is named after the action
        self._pending_label = ""
        self.history = History(self.capture, self.restore, **history_kwargs)
        self._connect()

    # -- wiring -----------------------------------------------------------

    def _connect(self) -> None:
        model = self._model
        # payload liveness follows the history: whenever steps are added,
        # trimmed or reset, blobs no snapshot references anymore are dropped
        self.history.changed.connect(self._sweep_payloads)
        model.configuration_params_changed.connect(self._on_params_changed)
        model.mask_changed.connect(self._on_mask_changed)
        # a structural change makes older snapshots inapplicable
        model.configuration_added.connect(self._on_structure_changed)
        model.configuration_removed.connect(self._on_structure_changed)

        overlays = model.overlay_model
        overlays.overlay_added.connect(lambda: self.history.record("add overlay"))
        overlays.overlay_removed.connect(
            lambda ind: self.history.record("remove overlay")
        )
        overlays.overlay_changed.connect(self._on_overlay_changed)

        # Peak picking and image loading live on the per-configuration models
        # and have no store-level forwarding, so they are wired per
        # configuration and rewired whenever the set of them changes.
        self._watch_configurations()
        model.configuration_added.connect(self._watch_configurations)
        model.configuration_removed.connect(self._watch_configurations)

        phases = model.phase_model
        phases.phase_added.connect(lambda: self.history.record("add phase"))
        phases.phase_removed.connect(self._on_phase_removed)
        phases.phase_changed.connect(self._on_phase_changed)
        phases.phase_reloaded.connect(self._on_phase_changed)

    def _watch_configurations(self, *args: Any) -> None:
        """Subscribes to signals that only exist per configuration.

        Connecting is not idempotent — a second connect of the same slot makes
        it fire twice — so already-wired signals are skipped rather than
        blindly reconnected when this runs again after a configuration is
        added.
        """
        for configuration in self._model.configurations:
            for signal, handler in (
                (
                    configuration.calibration_model.parameters_changed,
                    self._on_calibration_changed,
                ),
                (configuration.img_model.img_changed, self._on_img_changed),
                (
                    configuration.pattern_model.pattern_changed,
                    self._on_pattern_changed,
                ),
            ):
                if not signal.has_listener(handler):
                    signal.connect(handler)

    def _on_calibration_changed(self) -> None:
        self._record("calibration")

    def _on_img_changed(self) -> None:
        self._record("image")

    def _on_pattern_changed(self) -> None:
        # fires after every integration too — those captures are identical
        # to the step already recorded and are dropped by the equality check
        self._record("pattern")

    def _record(self, label: str, key: Any = None) -> None:
        """Records a step, preferring the label of the action that caused it."""
        label, self._pending_label = self._pending_label or label, ""
        self.history.record(label=label, key=key)

    def _on_overlay_changed(self, ind: int) -> None:
        self.history.record(label="overlay", key="overlay")

    def _on_phase_changed(self, ind: int) -> None:
        # Keyed by kind rather than by index on purpose. With "apply to all
        # phases" switched on, one pressure change emits phase_changed for
        # every phase; per-index keys would make that as many undo steps, so
        # a single Ctrl+Z would revert one phase and look broken. The cost is
        # that two deliberate phase edits within the coalescing window merge,
        # which is the same trade the spinbox drags already make.
        self.history.record(label="phase", key="phase")

    def _on_phase_removed(self, ind: int) -> None:
        self.history.record("remove phase")

    def _on_params_changed(self, field: str, new: Any, old: Any) -> None:
        if field in _NO_COALESCE:
            # an automatic search adds its whole burst in one write and so
            # records once anyway; two clicks are two decisions the user
            # may well want to take back one at a time
            self.history.record(label=_label_for(field))
            return
        if field in _RECORDED_ELSEWHERE:
            # remember what the user actually did, so the step is not labelled
            # after whichever consequence happens to be recorded first; the
            # FIRST suppressed field names the action — everything after it
            # in the same burst is a consequence
            if not self._pending_label:
                self._pending_label = _label_for(field)
            return
        self.history.record(label=_label_for(field), key=field)

    def _on_mask_changed(self) -> None:
        # the id for the edited mask is stale; recaptured on demand
        self._mask_cache.clear()
        self._record("mask")

    def _sweep_payloads(self) -> None:
        """Drops payloads no held snapshot (and no current capture) references."""
        live: set[str] = set(self._mask_cache.values())
        for state in self.history.states():
            for config_state in state.configurations:
                live.add(config_state.mask_data)
        self._model.payloads.sweep(live)

    def _on_structure_changed(self, *args: Any) -> None:
        self._mask_cache.clear()
        self.history.reset()

    # -- capture ----------------------------------------------------------

    def capture(self) -> Snapshot:
        return Snapshot(
            configurations=tuple(
                self._capture_configuration(c) for c in self._model.configurations
            ),
            phase=_capture_params(self._model.phase_model.params),
            overlays=self._capture_overlays(),
            phases=self._capture_phases(),
        )

    def _capture_overlays(self) -> tuple:
        # the overlay's x/y are only replaced, never edited in place, so the
        # object can be referenced instead of copied
        return tuple(
            _OverlayState(overlay=_Ref(overlay), params=_capture_params(overlay.params))
            for overlay in self._model.overlay_model.overlays
        )

    def _capture_phases(self) -> tuple:
        phase_model = self._model.phase_model
        states = []
        for ind, phase in enumerate(phase_model.phases):
            fingerprint = _phase_fingerprint(phase)
            # the fingerprint doubles as the cache key: a phase whose content
            # is unchanged reuses its copy, so no signal has to be trusted to
            # invalidate anything
            cached = self._phase_cache.get(id(phase))
            if cached is None or cached[0] != fingerprint:
                cached = (fingerprint, _Ref(_copy.deepcopy(phase)))
                self._phase_cache[id(phase)] = cached
            states.append(
                _PhaseState(
                    phase=cached[1],
                    fingerprint=fingerprint,
                    item_params=_capture_params(phase_model.item_params[ind]),
                    filename=phase_model.phase_files[ind]
                    if ind < len(phase_model.phase_files)
                    else "",
                )
            )
        return tuple(states)

    def _capture_configuration(self, configuration: Any) -> _ConfigState:
        return _ConfigState(
            params=_capture_params(configuration.params),
            img=_capture_params(configuration.img_model.params),
            pattern=_capture_params(configuration.pattern_model.params),
            mask=_capture_params(configuration.mask_model.params),
            calibration=_capture_params(configuration.calibration_model.params),
            map=_capture_params(configuration.map_model.params),
            mask_data=self._capture_mask(configuration.mask_model),
            plugins=_capture_plugins(configuration.mask_plugin_manager),
        )

    def _capture_mask(self, mask_model: Any) -> str:
        # putting a mask costs a packbits + compress + hash (~1 ms at 2048²),
        # so the id is cached until mask_changed says the pixels moved
        key = id(mask_model)
        payload_id = self._mask_cache.get(key)
        if payload_id is None:
            payload_id = self._model.payloads.put(mask_model.get_img())
            self._mask_cache[key] = payload_id
        return payload_id

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
            self._restore_overlays(snapshot.overlays)
            self._restore_phases(snapshot.phases)
            # a background uid may have been applied before its overlay was
            # restored; re-point every configuration now that the list is back
            model.resolve_background_overlays()

        self._mask_cache.clear()

    def _restore_overlays(self, states: tuple) -> None:
        # untouched overlays must be left strictly alone: rebuilding them
        # would make the pattern view drop and re-create plot items on an
        # undo that had nothing to do with overlays
        if self._capture_overlays() == states:
            return
        overlays = [state.overlay.value for state in states]
        self._model.overlay_model.restore(overlays)
        for state, overlay in zip(states, overlays):
            _apply_dict(overlay.params, state.params)

    def _restore_phases(self, states: tuple) -> None:
        if self._capture_phases() == states:
            return
        phase_model = self._model.phase_model
        # hand the model fresh copies: keeping the snapshot's own objects out
        # of the live model is what stops a later pressure change from
        # editing the history
        phases = [_copy.deepcopy(state.phase.value) for state in states]
        phase_model.restore(phases, [state.filename for state in states])
        for state, item_params in zip(states, phase_model.item_params):
            _apply_dict(item_params, state.item_params)
        # point the cache at the snapshot's copies, so capturing straight
        # after a restore reuses them instead of copying all over again
        for state, phase in zip(states, phases):
            self._phase_cache[id(phase)] = (state.fingerprint, state.phase)

    def _restore_configuration(self, state: _ConfigState, configuration: Any) -> None:
        _apply_dict(configuration.params, state.params, exclude=_CONFIG_EXCLUDED)
        # transformations are excluded from the generic copy: the field is a
        # log of what was applied to the pixels rather than something they are
        # derived from, so assigning it would record a rotation that never
        # happened. set_transformations makes the image follow.
        _apply_dict(
            configuration.img_model.params, state.img, exclude={"transformations"}
        )
        configuration.img_model.set_transformations(state.img["transformations"])
        _apply_dict(configuration.pattern_model.params, state.pattern)
        _apply_dict(configuration.mask_model.params, state.mask)
        _apply_dict(configuration.calibration_model.params, state.calibration)
        _apply_dict(configuration.map_model.params, state.map)

        _restore_plugins(configuration.mask_plugin_manager, state.plugins)
        # The image was restored first, so the mask normally fits again by the
        # time we get here. It will not if that reload failed (file moved) or
        # if the mask was resized without the image changing — writing a
        # mismatched mask back would leave one on screen that does not match
        # the image, which surfaces as a blocking dialog.
        payload = self._model.payloads.get(state.mask_data)
        if tuple(payload.shape) == tuple(configuration.mask_model.mask_dimension):
            configuration.mask_model.set_mask_data(payload.array())


def _apply_dict(target: Any, values: dict, exclude: set[str] | None = None) -> None:
    """Applies a captured params dict onto the live params instance.

    Goes through apply_params so the instance keeps its identity — every
    subscription on it stays valid and each changed field emits its event,
    which is what makes the GUI and the re-integrations follow an undo.
    """
    source = params_from_dict(type(target), values)
    apply_params(target, source, exclude=exclude)


def _capture_params(params: Any) -> dict:
    """Captures a params object as a plain, comparable dict.

    Values can arrive as numpy types — a phase colour loaded from a project
    file is an ``np.ndarray``, and h5py hands back numpy scalars generally.
    Comparing two snapshots holding those raises instead of returning a bool,
    so they are coerced here to the plain types the fields are declared as.
    """
    return _plain(params_to_dict(params))


def _plain(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return tuple(value.tolist())
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(_plain(item) for item in value)
    return value


def _phase_fingerprint(phase: Any) -> tuple:
    """Content summary of a jcpds, cheap enough to compute on every capture.

    Covers what a user can edit — the parameters (pressure, temperature, unit
    cell, ...) and the resulting reflections — which is what decides whether a
    phase needs a fresh copy in the history.
    """
    return (
        phase.name,
        repr(phase.params),
        tuple(
            (r.h, r.k, r.l, r.d, r.d0, r.intensity) for r in phase.reflections
        ),
    )


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
    "img.filename": "image file",
    "img.series_pos": "series position",
    "img.background_filename": "background image",
    "calibration.peak_selections": "calibration peaks",
    "pattern.pattern_filename": "pattern file",
    "pattern.pattern_source": "pattern file",
    "pattern.background_overlay_uid": "pattern background",
    # the calibration result fields are one action to the user
    "calibration.detector_mode": "calibration",
    "calibration.detector_name": "calibration",
    "calibration.detector_filename": "calibration",
    "calibration.geometry": "calibration",
    "calibration.is_calibrated": "calibration",
    "calibration.poni_filename": "calibration",
    "calibration.calibration_name": "calibration",
    "mask.roi": "mask region of interest",
    "mask.mode": "mask drawing mode",
}


def _label_for(field: str) -> str:
    if field in _LABELS:
        return _LABELS[field]
    return field.rsplit(".", 1)[-1].replace("_", " ")
