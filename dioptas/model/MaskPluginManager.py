# SPDX-License-Identifier: MIT

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

from .util import Signal
from .util.MaskPlugin import MaskPluginBase, GeometryContext

logger = logging.getLogger(__name__)


@dataclass
class MaskPluginEntry:
    plugin: MaskPluginBase
    enabled: bool = False
    cached_mask: np.ndarray | None = None


class MaskPluginManager:
    """Manages mask plugin instances, their enabled state, and cached masks."""

    def __init__(self) -> None:
        self._plugins: dict[str, MaskPluginEntry] = {}
        self._current_shape: tuple[int, int] | None = None
        self._current_img_data: np.ndarray | None = None
        self._geometry: GeometryContext | None = None
        self._existing_mask: np.ndarray | None = None
        self.mask_changed: Signal = Signal()

    def register(self, plugin: MaskPluginBase) -> None:
        name = plugin.name
        if name in self._plugins:
            logger.warning("Mask plugin '%s' already registered, skipping", name)
            return
        self._plugins[name] = MaskPluginEntry(plugin=plugin)
        logger.info("Registered mask plugin: %s (dynamic=%s)", name, plugin.is_dynamic)

    def unregister(self, name: str) -> None:
        if name in self._plugins:
            del self._plugins[name]
            self.mask_changed.emit()

    @property
    def plugin_names(self) -> list[str]:
        return list(self._plugins.keys())

    @property
    def plugins(self) -> dict[str, MaskPluginEntry]:
        return self._plugins

    def get_plugin(self, name: str) -> MaskPluginBase | None:
        entry = self._plugins.get(name)
        return entry.plugin if entry is not None else None

    def is_enabled(self, name: str) -> bool:
        entry = self._plugins.get(name)
        return entry.enabled if entry is not None else False

    def set_enabled(self, name: str, enabled: bool) -> None:
        entry = self._plugins.get(name)
        if entry is None:
            return
        if entry.enabled == enabled:
            return

        entry.enabled = enabled

        if enabled and entry.cached_mask is None and self._current_img_data is not None:
            self._compute_plugin_mask(entry)

        self.mask_changed.emit()

    def update_image(
        self, img_data: np.ndarray, existing_mask: np.ndarray | None = None
    ) -> None:
        """Called when a new image is loaded. Recomputes dynamic plugin masks.

        :param img_data: The current image data array.
        :param existing_mask: User-drawn mask (detector gaps, etc.) passed to
            plugins that declare ``needs_existing_mask = True``.
        """
        self._current_img_data = img_data
        self._existing_mask = existing_mask
        new_shape = img_data.shape[:2]
        shape_changed = new_shape != self._current_shape
        self._current_shape = new_shape

        changed = False
        for entry in self._plugins.values():
            if not entry.enabled:
                if shape_changed:
                    entry.cached_mask = None
                continue

            if entry.plugin.is_dynamic or shape_changed or entry.cached_mask is None:
                if self._compute_plugin_mask(entry):
                    changed = True

        if changed:
            self.mask_changed.emit()

    def update_geometry(self, geometry: GeometryContext | None) -> None:
        """Called when calibration geometry changes. Recomputes geometry-aware plugins."""
        self._geometry = geometry

        changed = False
        for entry in self._plugins.values():
            if not entry.plugin.needs_geometry or not entry.enabled:
                continue
            if self._current_img_data is not None:
                if self._compute_plugin_mask(entry):
                    changed = True
            else:
                entry.cached_mask = None

        if changed:
            self.mask_changed.emit()

    def update_shape(self, shape: tuple[int, int]) -> None:
        """Called when mask dimensions change. Invalidates static caches."""
        if shape != self._current_shape:
            self._current_shape = shape
            for entry in self._plugins.values():
                if not entry.plugin.is_dynamic:
                    entry.cached_mask = None

    def get_combined_mask(self) -> np.ndarray | None:
        """OR all enabled plugin masks together. Returns None if none active."""
        result = None
        for entry in self._plugins.values():
            if entry.enabled and entry.cached_mask is not None:
                if result is None:
                    result = entry.cached_mask.copy()
                else:
                    np.logical_or(result, entry.cached_mask, out=result)
        return result

    def update_plugin_settings(self, name: str, settings: dict) -> None:
        """Update settings for a plugin and recompute its mask."""
        entry = self._plugins.get(name)
        if entry is None:
            return
        entry.plugin.update_settings(settings)
        entry.cached_mask = None
        if entry.enabled and self._current_img_data is not None:
            self._compute_plugin_mask(entry)
            self.mask_changed.emit()

    def _compute_plugin_mask(self, entry: MaskPluginEntry) -> bool:
        """Compute mask for a single plugin. Returns True if successful."""
        try:
            kwargs = {"existing_mask": self._existing_mask}
            if entry.plugin.needs_geometry:
                kwargs["geometry"] = self._geometry
            mask = entry.plugin.compute_mask(self._current_img_data, **kwargs)
            if mask.shape != self._current_shape:
                logger.warning(
                    "Plugin '%s' returned mask with shape %s, expected %s. Skipping.",
                    entry.plugin.name,
                    mask.shape,
                    self._current_shape,
                )
                entry.cached_mask = None
                return False
            entry.cached_mask = np.asarray(mask, dtype=bool)
            return True
        except Exception:
            logger.exception(
                "Plugin '%s' failed to compute mask. Disabling.",
                entry.plugin.name,
            )
            entry.enabled = False
            entry.cached_mask = None
            return False
