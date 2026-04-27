# SPDX-License-Identifier: MIT

from __future__ import annotations

import logging

import numpy as np

from ..MaskPlugin import MaskPluginBase, GeometryContext

logger = logging.getLogger(__name__)

try:
    import cv2 as _cv2
except ImportError:
    _cv2 = None

try:
    from ._powder_outlier_c import compute_outlier_mask as _c_compute
except ImportError:
    _c_compute = None


class PowderDiffSpotMaskPlugin(MaskPluginBase):
    """Detect and mask single-crystal or spot diffraction artifacts in powder data.

    Bins image pixels by their 2-theta angle (from calibration geometry) and
    identifies outlier pixels within each bin using sigma-clipping (iterative
    mean + standard deviation thresholding). This targets single-crystal spots,
    satellite reflections, and other non-powder features that appear as intensity
    outliers at a given scattering angle.

    The 2-theta sort order is cached per geometry, so only the per-image
    outlier detection runs on each new frame (~8ms for 2048x2048).

    Algorithm inspired by XRD-Powder-Mask by Albert Vong.
    """

    name = "Powder Diffraction Spot Mask"
    description = (
        "Masks single-crystal spots and intensity outliers in powder diffraction "
        "images by binning pixels by 2-theta and flagging those that deviate "
        "significantly from the bin mean. Requires calibration geometry."
    )
    needs_geometry = True
    is_dynamic = True

    def __init__(self):
        self.esdmul = 3.0
        self.num_bins = 445
        self.method = "median"  # "mean" (fast) or "median" (robust)
        self.iterations = 1
        self.smooth_sigma = 2.5
        self.smooth_threshold = 0.8

        # Cached geometry-derived data (recomputed only when geometry changes)
        self._cached_tth_sort_idx: np.ndarray | None = None
        self._cached_geometry_id: int | None = None

    def compute_mask(
        self, img_data: np.ndarray, geometry: GeometryContext | None = None
    ) -> np.ndarray:
        if geometry is None:
            return np.zeros(img_data.shape, dtype=bool)

        return _compute_powder_outlier_mask(
            img_data,
            geometry=geometry,
            esdmul=self.esdmul,
            num_bins=self.num_bins,
            method=self.method,
            iterations=self.iterations,
            smooth_sigma=self.smooth_sigma,
            smooth_threshold=self.smooth_threshold,
            plugin=self,
        )

    def get_settings_schema(self) -> dict:
        return {
            "method": {
                "type": "choice",
                "default": "median",
                "label": "Method",
                "choices": ["median", "mean"],
                "description": (
                    "Statistical method for outlier detection. "
                    "'median' uses median + k×MAD (robust, recommended). "
                    "'mean' uses mean + k×std (faster but less sensitive)."
                ),
            },
            "esdmul": {
                "type": "float",
                "default": 3.0,
                "label": "Sigma multiplier",
                "min": 1.0,
                "max": 50.0,
                "decimals": 1,
                "description": (
                    "Number of standard deviations (or MADs) above the bin "
                    "center for a pixel to be flagged as an outlier. Lower "
                    "values mask more aggressively."
                ),
            },
            "num_bins": {
                "type": "int",
                "default": 445,
                "label": "Number of 2θ bins",
                "min": 64,
                "max": 8192,
                "description": (
                    "Number of angular bins to divide the 2-theta range into. "
                    "More bins give finer angular resolution but fewer pixels per "
                    "bin for statistics."
                ),
            },
            "iterations": {
                "type": "int",
                "default": 1,
                "label": "Iterations",
                "min": 1,
                "max": 5,
                "description": (
                    "Number of sigma-clipping iterations. More iterations improve "
                    "robustness when many outliers are present in a bin, but each "
                    "iteration roughly doubles computation time. Only used with "
                    "Python fallback (C extension always uses single pass)."
                ),
            },
            "smooth_sigma": {
                "type": "float",
                "default": 2.5,
                "label": "Smooth sigma (px)",
                "min": 0.0,
                "max": 10.0,
                "decimals": 1,
                "description": (
                    "Gaussian smoothing sigma applied to the raw binary mask "
                    "before thresholding. Merges nearby flagged pixels into "
                    "coherent spot regions. Set to 0 to disable smoothing."
                ),
            },
            "smooth_threshold": {
                "type": "float",
                "default": 0.8,
                "label": "Smooth threshold",
                "min": 0.01,
                "max": 1.0,
                "decimals": 2,
                "description": (
                    "Threshold applied after Gaussian smoothing. Pixels with "
                    "smoothed values above this are included in the final mask. "
                    "Lower values expand masked regions."
                ),
            },
        }

    def update_settings(self, settings: dict) -> None:
        old_num_bins = self.num_bins
        self.method = settings.get("method", self.method)
        self.esdmul = settings.get("esdmul", self.esdmul)
        self.num_bins = settings.get("num_bins", self.num_bins)
        self.iterations = settings.get("iterations", self.iterations)
        self.smooth_sigma = settings.get("smooth_sigma", self.smooth_sigma)
        self.smooth_threshold = settings.get("smooth_threshold", self.smooth_threshold)
        # Invalidate cache if num_bins changed
        if self.num_bins != old_num_bins:
            self._cached_tth_sort_idx = None
            self._cached_geometry_id = None

    def get_settings(self) -> dict:
        return {
            "method": self.method,
            "esdmul": self.esdmul,
            "num_bins": self.num_bins,
            "iterations": self.iterations,
            "smooth_sigma": self.smooth_sigma,
            "smooth_threshold": self.smooth_threshold,
        }


def _get_sort_index(
    plugin: PowderDiffSpotMaskPlugin, geometry: GeometryContext
) -> np.ndarray:
    """Get or compute the 2-theta sort index, caching it on the plugin."""
    geo_id = id(geometry.tth_array)
    if plugin._cached_geometry_id == geo_id and plugin._cached_tth_sort_idx is not None:
        return plugin._cached_tth_sort_idx

    tth_sort_idx = np.argsort(geometry.tth_array.ravel())
    plugin._cached_tth_sort_idx = tth_sort_idx
    plugin._cached_geometry_id = geo_id
    return tth_sort_idx


def _compute_powder_outlier_mask(
    img_data: np.ndarray,
    geometry: GeometryContext,
    esdmul: float,
    num_bins: int,
    method: str,
    iterations: int,
    smooth_sigma: float,
    smooth_threshold: float,
    plugin: PowderDiffSpotMaskPlugin | None = None,
) -> np.ndarray:
    """Core algorithm: bin by 2-theta, detect outliers.

    Uses equal-count bins (sorted by 2-theta) for optimal statistical power.
    The sort index is cached on the plugin instance so it's only computed once
    per geometry change.

    :param img_data: Raw image data (must not be normalized).
    :param geometry: Calibration geometry context.
    :param esdmul: Threshold multiplier (sigma or MAD units).
    :param num_bins: Number of 2-theta bins.
    :param method: "mean" for mean+std, "median" for median+MAD.
    :param iterations: Number of sigma-clipping iterations (Python fallback only).
    :param smooth_sigma: Gaussian smoothing sigma for post-processing.
    :param smooth_threshold: Threshold after smoothing.
    :param plugin: Plugin instance for caching (optional).
    :returns: Boolean mask (True = masked/outlier pixel).
    """
    img_flat = img_data.ravel().astype(np.float64)
    n_pixels = img_flat.size

    # Get cached sort index or compute it
    if plugin is not None:
        tth_sort_idx = _get_sort_index(plugin, geometry)
    else:
        tth_sort_idx = np.argsort(geometry.tth_array.ravel())

    # Equal-count bins: trim to evenly divisible size
    pixels_per_bin = n_pixels // num_bins
    if pixels_per_bin < 3:
        return np.zeros(img_data.shape, dtype=bool)
    n_used = pixels_per_bin * num_bins

    # Sort image values by 2-theta order
    sorted_img = img_flat[tth_sort_idx[:n_used]]

    use_median = method == "median"

    # Try C extension first (single-pass, fastest)
    if _c_compute is not None:
        sorted_contiguous = np.ascontiguousarray(sorted_img)
        mask_sorted = _c_compute(
            sorted_contiguous, num_bins, pixels_per_bin, esdmul, use_median
        )
        mask_flat = np.zeros(n_pixels, dtype=np.uint8)
        mask_flat[tth_sort_idx[:n_used]] = mask_sorted
        mask = mask_flat.astype(bool).reshape(img_data.shape)
    else:
        # Python fallback
        mask = _compute_python_fallback(
            sorted_img, tth_sort_idx, n_pixels, num_bins, pixels_per_bin,
            n_used, esdmul, use_median, iterations, img_data.shape,
        )

    # Post-process: Gaussian smooth + threshold to merge nearby spots
    if smooth_sigma > 0:
        mask = _smooth_mask(mask, smooth_sigma, smooth_threshold)

    return mask


def _smooth_mask(
    mask: np.ndarray, sigma: float, threshold: float
) -> np.ndarray:
    """Apply Gaussian smoothing and threshold. Uses OpenCV when available."""
    if _cv2 is not None:
        mask32 = mask.astype(np.float32)
        ksize = int(np.ceil(sigma * 6)) | 1
        smoothed = _cv2.GaussianBlur(mask32, (ksize, ksize), sigma)
        return smoothed > threshold
    else:
        from scipy.ndimage import gaussian_filter

        smoothed = gaussian_filter(mask.astype(np.float64), sigma=sigma)
        return smoothed > threshold


def _compute_python_fallback(
    sorted_img: np.ndarray,
    tth_sort_idx: np.ndarray,
    n_pixels: int,
    num_bins: int,
    pixels_per_bin: int,
    n_used: int,
    esdmul: float,
    use_median: bool,
    iterations: int,
    img_shape: tuple[int, ...],
) -> np.ndarray:
    """Pure Python/NumPy fallback when C extension is unavailable."""
    binned = sorted_img.reshape(num_bins, pixels_per_bin)

    if use_median:
        # Median + MAD via np.partition
        mid = pixels_per_bin // 2
        binned_copy = binned.copy()
        np.partition(binned_copy, mid, axis=1)
        bin_center = binned_copy[:, mid]
        abs_dev = np.abs(binned - bin_center[:, np.newaxis])
        abs_dev_copy = abs_dev.copy()
        np.partition(abs_dev_copy, mid, axis=1)
        bin_spread = abs_dev_copy[:, mid] * 1.4826  # MAD to std scale
        # When MAD is 0 (uniform bin), use std as fallback spread estimate
        zero_spread = bin_spread == 0
        if np.any(zero_spread):
            bin_std_fallback = binned[zero_spread].std(axis=1)
            bin_spread[zero_spread] = bin_std_fallback
        threshold_per_bin = bin_center + esdmul * bin_spread
        mask_2d = binned > threshold_per_bin[:, np.newaxis]
        mask_2d &= (bin_spread > 0)[:, np.newaxis]
    elif iterations <= 1:
        # Fast path: single-pass mean + std
        bin_mean = binned.mean(axis=1)
        bin_std = binned.std(axis=1)
        threshold_per_bin = bin_mean + esdmul * bin_std
        mask_2d = binned > threshold_per_bin[:, np.newaxis]
        mask_2d &= (bin_std > 0)[:, np.newaxis]
    else:
        # Sigma-clipping: iteratively exclude outliers from statistics
        valid = np.ones((num_bins, pixels_per_bin), dtype=bool)
        mask_2d = np.zeros((num_bins, pixels_per_bin), dtype=bool)

        for _ in range(iterations):
            masked_binned = np.where(valid, binned, np.nan)
            bin_mean = np.nanmean(masked_binned, axis=1)
            bin_std = np.nanstd(masked_binned, axis=1)
            threshold_per_bin = bin_mean + esdmul * bin_std
            new_outliers = binned > threshold_per_bin[:, np.newaxis]
            new_outliers &= (bin_std > 0)[:, np.newaxis]
            valid &= ~new_outliers
            mask_2d |= new_outliers

    mask_flat = np.zeros(n_pixels, dtype=bool)
    mask_flat[tth_sort_idx[:n_used]] = mask_2d.ravel()
    return mask_flat.reshape(img_shape)
