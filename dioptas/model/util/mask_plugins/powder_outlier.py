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
    from ._powder_outlier_c import compute_outlier_mask_binned as _c_compute_binned
except ImportError:
    _c_compute_binned = None


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

    name = "Spot Mask"
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
        self.smooth_sigma = 1.0
        self.smooth_threshold = 0.3

        # Cached geometry-derived data (recomputed only when geometry/bins change)
        self._cached_bin_indices: np.ndarray | None = None
        self._cached_geometry_id: int | None = None

    def compute_mask(
        self,
        img_data: np.ndarray,
        geometry: GeometryContext | None = None,
        existing_mask: np.ndarray | None = None,
    ) -> np.ndarray:
        if geometry is None:
            return np.zeros(img_data.shape, dtype=bool)

        return _compute_powder_outlier_mask(
            img_data,
            geometry=geometry,
            existing_mask=existing_mask,
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
                "step": 0.1,
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
                "step": 20,
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
                "default": 1.0,
                "label": "Smooth sigma (px)",
                "min": 0.0,
                "max": 10.0,
                "decimals": 1,
                "step": 0.1,
                "description": (
                    "Gaussian smoothing sigma applied to the raw binary mask "
                    "before thresholding. Merges nearby flagged pixels into "
                    "coherent spot regions. Set to 0 to disable smoothing."
                ),
            },
            "smooth_threshold": {
                "type": "float",
                "default": 0.3,
                "label": "Smooth threshold",
                "min": 0.01,
                "max": 1.0,
                "decimals": 2,
                "step": 0.01,
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
            self._cached_bin_indices = None
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


def _get_bin_indices(
    plugin: PowderDiffSpotMaskPlugin, geometry: GeometryContext, num_bins: int
) -> np.ndarray:
    """Get or compute equal-width bin indices, caching on the plugin."""
    geo_id = id(geometry.tth_array)
    if (plugin._cached_geometry_id == geo_id
            and plugin._cached_bin_indices is not None
            and plugin.num_bins == num_bins):
        return plugin._cached_bin_indices

    bin_indices = _compute_bin_indices(geometry.tth_array, num_bins)
    plugin._cached_bin_indices = bin_indices
    plugin._cached_geometry_id = geo_id
    return bin_indices


def _compute_bin_indices(tth_array: np.ndarray, num_bins: int) -> np.ndarray:
    """Compute equal-width bin indices from 2-theta array."""
    tth_flat = tth_array.ravel()
    tth_min = np.nanmin(tth_flat)
    tth_max = np.nanmax(tth_flat)
    dtth = (tth_max - tth_min) / num_bins
    bin_indices = ((tth_flat - tth_min) / dtth).astype(np.int32)
    np.clip(bin_indices, 0, num_bins - 1, out=bin_indices)
    return bin_indices


def _compute_powder_outlier_mask(
    img_data: np.ndarray,
    geometry: GeometryContext,
    existing_mask: np.ndarray | None = None,
    esdmul: float = 3.0,
    num_bins: int = 445,
    method: str = "median",
    iterations: int = 1,
    smooth_sigma: float = 2.5,
    smooth_threshold: float = 0.8,
    plugin: PowderDiffSpotMaskPlugin | None = None,
    num_threads: int = 0,
) -> np.ndarray:
    """Core algorithm: bin by 2-theta, detect outliers.

    Uses equal-width 2-theta bins matching the original XRD-Powder-Mask
    algorithm. The bin indices are cached on the plugin instance so they're
    only computed once per geometry change.

    :param img_data: Raw image data (must not be normalized).
    :param geometry: Calibration geometry context.
    :param existing_mask: User-drawn mask (detector gaps, etc.). Pre-masked
        pixels are excluded from per-bin statistics. None means no mask.
    :param esdmul: Threshold multiplier (sigma or MAD units).
    :param num_bins: Number of 2-theta bins.
    :param method: "mean" for mean+std, "median" for median+MAD.
    :param iterations: Number of sigma-clipping iterations (Python fallback only).
    :param smooth_sigma: Gaussian smoothing sigma for post-processing.
    :param smooth_threshold: Threshold after smoothing.
    :param plugin: Plugin instance for caching (optional).
    :param num_threads: Max OpenMP threads (0 = all available, 1 = single-threaded).
    :returns: Boolean mask (True = masked/outlier pixel).
    """
    img_flat = np.ascontiguousarray(img_data.ravel(), dtype=np.float64)

    # Get cached bin indices or compute them
    if plugin is not None:
        bin_indices = _get_bin_indices(plugin, geometry, num_bins)
    else:
        bin_indices = _compute_bin_indices(geometry.tth_array, num_bins)

    # Exclude pre-masked pixels by setting their bin index to -1.
    # The C code and Python fallback skip pixels with bin < 0.
    if existing_mask is not None:
        bin_indices = bin_indices.copy()
        bin_indices[existing_mask.ravel().astype(bool)] = -1

    use_median = method == "median"

    # Try C extension first
    if _c_compute_binned is not None:
        mask_flat = _c_compute_binned(
            img_flat, bin_indices, num_bins, esdmul, use_median, num_threads
        )
        mask = mask_flat.astype(bool).reshape(img_data.shape)
    else:
        mask = _compute_python_fallback(
            img_flat, bin_indices, num_bins,
            esdmul, use_median, iterations, img_data.shape,
        )

    # Post-process: Gaussian smooth + threshold to merge nearby spots
    if smooth_sigma > 0:
        gap = existing_mask.astype(bool) if existing_mask is not None else None
        mask = _smooth_mask(mask, smooth_sigma, smooth_threshold, gap)

    return mask


def _smooth_mask(
    mask: np.ndarray, sigma: float, threshold: float, gap: np.ndarray | None = None
) -> np.ndarray:
    """Apply Gaussian smoothing and threshold.

    When a gap mask is provided, detected spots are dilated into gap pixels
    before smoothing so that the Gaussian kernel sees continuous mask values
    at gap edges. This prevents spots adjacent to gaps from being eroded
    regardless of sigma/threshold settings.

    The result is restricted to within the smoothing radius of an originally
    detected pixel, so the gap-fill values cannot bleed across narrow gaps to
    create false detections on the other side.
    """
    gap_active = gap is not None and np.any(gap)

    if gap_active:
        from scipy.ndimage import binary_dilation

        # Deep dilation into gap so the Gaussian kernel sees continuous values
        # at gap edges (no erosion of spots adjacent to gaps).
        fill_iter = max(int(np.ceil(sigma * 3)), 1)
        deep_dilated = binary_dilation(mask, iterations=fill_iter)
        mask_filled = mask.copy()
        mask_filled[gap] = deep_dilated[gap]
        mask_float = mask_filled.astype(np.float32)
        # Tighter dilation for the output reach: smoothing of a spot only
        # extends ~sigma pixels past its edge before falling below threshold.
        # Limiting the result to this reach prevents gap-fill bleed-through.
        reach_iter = max(int(np.round(sigma)), 1)
        reach = binary_dilation(mask, iterations=reach_iter)
    else:
        mask_float = mask.astype(np.float32)

    if _cv2 is not None:
        ksize = int(np.ceil(sigma * 6)) | 1
        smoothed = _cv2.GaussianBlur(mask_float, (ksize, ksize), sigma)
    else:
        from scipy.ndimage import gaussian_filter

        smoothed = gaussian_filter(mask_float, sigma=sigma)

    result = smoothed > threshold
    if gap_active:
        # Restrict to within the smoothing reach of a detected pixel, so the
        # gap-fill values cannot bleed across narrow gaps to create false
        # detections on the other side.
        result &= reach
        result[gap] = False
    return result


def _compute_python_fallback(
    img_flat: np.ndarray,
    bin_indices: np.ndarray,
    num_bins: int,
    esdmul: float,
    use_median: bool,
    iterations: int,
    img_shape: tuple[int, ...],
) -> np.ndarray:
    """Pure Python/NumPy fallback when C extension is unavailable."""
    mask = np.zeros(len(img_flat), dtype=bool)

    for b in range(num_bins):
        bin_mask = bin_indices == b
        bin_vals = img_flat[bin_mask]
        n = len(bin_vals)
        if n < 3:
            continue

        if use_median:
            center = np.median(bin_vals)
            spread = np.median(np.abs(bin_vals - center)) * 1.4826
            if spread <= 0:
                spread = np.std(bin_vals)
        else:
            center = np.mean(bin_vals)
            spread = np.std(bin_vals)

        if spread <= 0:
            continue

        if iterations > 1 and not use_median:
            # Sigma-clipping for mean/std method
            valid = np.ones(n, dtype=bool)
            for _ in range(iterations):
                v = bin_vals[valid]
                if len(v) < 3:
                    break
                c = np.mean(v)
                s = np.std(v)
                if s <= 0:
                    break
                new_outliers = bin_vals > c + esdmul * s
                valid &= ~new_outliers
            outliers = ~valid
        else:
            outliers = bin_vals > center + esdmul * spread

        mask[bin_mask] = outliers

    return mask.reshape(img_shape)
