# SPDX-License-Identifier: MIT

from __future__ import annotations

import numpy as np


class MaskPluginBase:
    """Base class for mask plugins.

    Subclass this to create a mask plugin. Static plugins compute their mask
    once per image shape change. Dynamic plugins recompute on every new image.

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
    """

    name: str = "Unnamed Plugin"
    is_dynamic: bool = False

    def compute_mask(self, img_data: np.ndarray) -> np.ndarray:
        """Compute and return a boolean mask array.

        :param img_data: The current image data array.
        :returns: Boolean array with same shape as img_data. True = masked pixel.
        """
        raise NotImplementedError

    def get_settings_schema(self) -> dict | None:
        """Return a dict describing configurable settings, or None.

        Each key is a parameter name, value is a dict with:
        - 'type': 'float', 'int', 'bool', or 'str'
        - 'default': default value
        - 'label': display label
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
