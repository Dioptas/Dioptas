# SPDX-License-Identifier: MIT

from __future__ import annotations

import numpy as np

from ..MaskPlugin import MaskPluginBase


class ThresholdMaskPlugin(MaskPluginBase):
    """Mask pixels above and/or below intensity thresholds.

    When enabled, automatically masks pixels outside the configured intensity
    range on every new image.
    """

    name = "Threshold Mask"
    description = (
        "Masks pixels with intensity outside a configurable range. "
        "Useful for removing hot pixels, dead pixels, or saturated detector regions."
    )
    is_dynamic = True

    def __init__(self):
        self.above_enabled = True
        self.above_value = 1e7
        self.below_enabled = False
        self.below_value = 0.0

    def compute_mask(self, img_data: np.ndarray, existing_mask: np.ndarray | None = None, **kwargs) -> np.ndarray:
        mask = np.zeros(img_data.shape, dtype=bool)
        if self.above_enabled:
            mask |= img_data > self.above_value
        if self.below_enabled:
            mask |= img_data < self.below_value
        return mask

    def get_settings_schema(self) -> dict:
        return {
            "above_enabled": {
                "type": "bool",
                "default": True,
                "label": "Mask above",
                "description": "Enable masking of pixels with intensity above the upper threshold.",
            },
            "above_value": {
                "type": "float",
                "default": 1e7,
                "label": "Upper threshold",
                "min": -1e12,
                "max": 1e12,
                "decimals": 1,
                "description": "Pixels with intensity above this value will be masked.",
            },
            "below_enabled": {
                "type": "bool",
                "default": False,
                "label": "Mask below",
                "description": "Enable masking of pixels with intensity below the lower threshold.",
            },
            "below_value": {
                "type": "float",
                "default": 0.0,
                "label": "Lower threshold",
                "min": -1e12,
                "max": 1e12,
                "decimals": 1,
                "description": "Pixels with intensity below this value will be masked.",
            },
        }

    def update_settings(self, settings: dict) -> None:
        self.above_enabled = settings.get("above_enabled", self.above_enabled)
        self.above_value = settings.get("above_value", self.above_value)
        self.below_enabled = settings.get("below_enabled", self.below_enabled)
        self.below_value = settings.get("below_value", self.below_value)

    def get_settings(self) -> dict:
        return {
            "above_enabled": self.above_enabled,
            "above_value": self.above_value,
            "below_enabled": self.below_enabled,
            "below_value": self.below_value,
        }
