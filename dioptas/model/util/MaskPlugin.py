# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class GeometryContext:
    """Geometry information passed to geometry-aware mask plugins.

    All angles are in radians. Distances and pixel sizes are in meters.
    Arrays (tth_array, azi_array) have the same shape as the image.
    """

    tth_array: np.ndarray
    """Two-theta value per pixel in radians."""

    azi_array: np.ndarray
    """Azimuthal (chi) angle per pixel in radians."""

    dist: float
    """Sample-to-detector distance in meters."""

    wavelength: float
    """X-ray wavelength in meters."""

    poni1: float
    """Point of normal incidence coordinate 1 (beam center) in meters."""

    poni2: float
    """Point of normal incidence coordinate 2 (beam center) in meters."""

    rot1: float
    """Rotation 1 in radians."""

    rot2: float
    """Rotation 2 in radians."""

    rot3: float
    """Rotation 3 in radians."""

    pixel1: float
    """Pixel size along axis 1 in meters."""

    pixel2: float
    """Pixel size along axis 2 in meters."""


class MaskPluginBase:
    """Base class for mask plugins.

    Subclass this to create a mask plugin. Static plugins compute their mask
    once per image shape change. Dynamic plugins recompute on every new image.

    Plugins that need calibration geometry should set ``needs_geometry = True``.
    Their ``compute_mask`` will receive a :class:`GeometryContext` as the second
    argument (or ``None`` if no calibration is available).

    Example::

        class HotPixelPlugin(MaskPluginBase):
            name = "Hot Pixel Removal"
            is_dynamic = True

            def __init__(self):
                self.threshold = 1e6

            def compute_mask(self, img_data):
                return img_data > self.threshold

            def get_settings_schema(self):
                return {
                    'threshold': {
                        'type': 'float',
                        'default': 1e6,
                        'label': 'Threshold',
                    }
                }

            def update_settings(self, settings):
                self.threshold = settings.get('threshold', self.threshold)

    Geometry-aware example::

        class PowderRingMask(MaskPluginBase):
            name = "Powder Ring Outlier Mask"
            needs_geometry = True
            is_dynamic = True

            def compute_mask(self, img_data, geometry=None):
                if geometry is None:
                    return np.zeros(img_data.shape, dtype=bool)
                # Use geometry.tth_array to bin by 2theta and detect outliers
                ...
    """

    name: str = "Unnamed Plugin"
    description: str = ""
    is_dynamic: bool = False
    needs_geometry: bool = False

    def compute_mask(
        self,
        img_data: np.ndarray,
        geometry: GeometryContext | None = None,
        existing_mask: np.ndarray | None = None,
    ) -> np.ndarray:
        """Compute and return a boolean mask array.

        :param img_data: The current image data array.
        :param geometry: Calibration geometry context, or None if not calibrated.
            Only passed when the plugin declares ``needs_geometry = True``.
        :param existing_mask: User-drawn mask (detector gaps, manual masks), or None.
            True = pixel is already masked. Plugins can use this to exclude
            pre-masked pixels from statistics (e.g., detector gaps).
        :returns: Boolean array with same shape as img_data. True = masked pixel.
        """
        raise NotImplementedError

    def get_settings_schema(self) -> dict | None:
        """Return a dict describing configurable settings, or None.

        Each key is a parameter name, value is a dict with:
        - 'type': 'float', 'int', 'bool', or 'str'
        - 'default': default value
        - 'label': display label
        - 'description' (optional): tooltip text explaining the parameter
        - 'min' / 'max' (optional, for numeric types)
        """
        return None

    def update_settings(self, settings: dict) -> None:
        """Called when user changes settings via the UI."""
        pass

    def get_settings(self) -> dict:
        """Return current settings values. Override if plugin has settings."""
        return {}

    @property
    def has_settings(self) -> bool:
        return self.get_settings_schema() is not None
