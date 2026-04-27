# SPDX-License-Identifier: MIT

from __future__ import annotations

import logging

import numpy as np
from scipy import ndimage

from ..MaskPlugin import MaskPluginBase

logger = logging.getLogger(__name__)


class CosmicRayMaskPlugin(MaskPluginBase):
    """Detect and mask cosmic ray artifacts using local statistics.

    Identifies pixels that are significantly brighter than their local
    neighborhood using z-scores and intensity thresholds. Runs iteratively
    to catch cosmic rays revealed after removing the most obvious ones.
    """

    name = "Cosmic Ray Mask"
    description = (
        "Detects cosmic ray artifacts by comparing each pixel's intensity to "
        "local statistics (mean and standard deviation) in a sliding window. "
        "Pixels significantly brighter than their neighborhood are flagged. "
        "Runs iteratively to catch fainter artifacts revealed after removing "
        "bright ones."
    )
    is_dynamic = True

    def __init__(self):
        self.sigma = 5.0
        self.window_size = 5
        self.iterations = 2
        self.min_intensity = 100.0

    def compute_mask(self, img_data: np.ndarray, existing_mask: np.ndarray | None = None, **kwargs) -> np.ndarray:
        return _detect_cosmic_rays_iterative(
            img_data,
            sigma=self.sigma,
            window_size=self.window_size,
            iterations=self.iterations,
            min_intensity=self.min_intensity,
        )

    def get_settings_schema(self) -> dict:
        return {
            "sigma": {
                "type": "float",
                "default": 5.0,
                "label": "Sigma",
                "min": 1.0,
                "max": 50.0,
                "decimals": 1,
                "description": (
                    "Number of standard deviations above the local mean for a pixel "
                    "to be flagged as a cosmic ray. Higher values are more conservative."
                ),
            },
            "window_size": {
                "type": "int",
                "default": 5,
                "label": "Window size",
                "min": 3,
                "max": 51,
                "description": (
                    "Size of the local neighborhood window (in pixels) used to "
                    "calculate mean and standard deviation. Should be odd."
                ),
            },
            "iterations": {
                "type": "int",
                "default": 2,
                "label": "Iterations",
                "min": 1,
                "max": 10,
                "description": (
                    "Number of detection passes. Each pass removes found cosmic rays "
                    "before the next, catching fainter artifacts revealed by removal "
                    "of bright ones."
                ),
            },
            "min_intensity": {
                "type": "float",
                "default": 100.0,
                "label": "Min intensity",
                "min": 0.0,
                "max": 1e12,
                "decimals": 1,
                "description": (
                    "Minimum absolute pixel intensity to consider as a cosmic ray. "
                    "Pixels below this value are never flagged, regardless of their "
                    "local z-score."
                ),
            },
        }

    def update_settings(self, settings: dict) -> None:
        self.sigma = settings.get("sigma", self.sigma)
        self.window_size = settings.get("window_size", self.window_size)
        self.iterations = settings.get("iterations", self.iterations)
        self.min_intensity = settings.get("min_intensity", self.min_intensity)

    def get_settings(self) -> dict:
        return {
            "sigma": self.sigma,
            "window_size": self.window_size,
            "iterations": self.iterations,
            "min_intensity": self.min_intensity,
        }


def _detect_cosmic_rays(
    data: np.ndarray,
    sigma: float,
    window_size: int,
    min_intensity: float,
) -> np.ndarray:
    """Detect cosmic rays by comparing pixel values to local statistics."""
    positive_mask = data > 0
    data_positive = np.where(positive_mask, data, 0)

    sum_positive = ndimage.uniform_filter(data_positive, size=window_size)
    count_positive = ndimage.uniform_filter(
        positive_mask.astype(float), size=window_size
    )

    local_mean = np.where(count_positive > 0, sum_positive / count_positive, 0)

    sum_squares = ndimage.uniform_filter(data_positive**2, size=window_size)
    local_var = np.where(
        count_positive > 0, (sum_squares / count_positive) - local_mean**2, 0
    )
    local_std = np.sqrt(np.maximum(local_var, 0))

    z_scores = np.zeros_like(data)
    valid_mask = np.logical_and(positive_mask, local_std > 0)
    z_scores[valid_mask] = (data[valid_mask] - local_mean[valid_mask]) / (
        local_std[valid_mask] + 1e-10
    )

    cosmic_mask = np.logical_and(z_scores > sigma, positive_mask)
    intensity_mask = np.logical_and(data > (2 * local_mean), positive_mask)
    combined_mask = np.logical_or(cosmic_mask, intensity_mask)
    combined_mask = np.logical_and(combined_mask, data > min_intensity)

    return combined_mask


def _detect_cosmic_rays_iterative(
    image: np.ndarray,
    sigma: float,
    window_size: int,
    iterations: int,
    min_intensity: float,
) -> np.ndarray:
    """Apply cosmic ray detection iteratively."""
    image = image.astype(np.float64, copy=True)
    combined_mask = np.zeros(image.shape, dtype=bool)

    for i in range(iterations):
        cosmic_mask = _detect_cosmic_rays(image, sigma, window_size, min_intensity)
        image[cosmic_mask] = np.nan
        combined_mask |= cosmic_mask
        n_found = np.sum(cosmic_mask)
        logger.debug("Cosmic ray iteration %d: found %d pixels", i + 1, n_found)

    return combined_mask
