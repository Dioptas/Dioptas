# SPDX-License-Identifier: MIT
"""Compiled diamond ROI experiment. Not registered in the interactive UI."""
from __future__ import annotations

from threading import Lock
from time import perf_counter_ns
import numpy as np

from .diamond import DiamondSpotMaskPlugin

try:
    from . import _diamond_roi_c as native
except ImportError:
    native = None


class DiamondROIDetector:
    """Reuse preparation/scratch; return independently owned full-size masks.

    Geometry preparation is explicit so first-call and per-frame timings cannot
    be conflated. This is a morphology + spacing prior, not phase indexing.
    """

    def __init__(self, geometry, *, block=8, background_radius=128,
                 seed_contrast=5.0, wing_contrast=0.8, min_seed_pixels=100, min_seed_radius=8,
                 max_growth=32, max_window_pixels=1_000_000, exclude_zero=True,
                 lattice_a=3.567, d_tolerance_percent=3.0):
        if native is None:
            raise RuntimeError("The compiled diamond ROI experiment is unavailable")
        self.shape = geometry.tth_array.shape
        if len(self.shape) != 2 or not 1 <= block <= 64:
            raise ValueError("Invalid detector shape or block size")
        reference = DiamondSpotMaskPlugin()
        reference.update_settings(dict(lattice_a=lattice_a,
                                       d_tolerance_percent=d_tolerance_percent))
        ranges = np.array(reference._seed_ranges(geometry), dtype=float).reshape(-1, 2)
        # Symmetric samples of the geometry, not a per-frame subsampling of
        # intensities: the native reducer reads every image pixel.
        ch, cw = ((n + block - 1) // block for n in self.shape)
        coarse_angles = np.zeros((ch, cw))
        low = max(0, block // 4)
        high = block - 1 - low
        for dy, dx in [(low, low), (low, high), (high, low), (high, high)]:
            rows = np.minimum(np.arange(ch) * block + dy, self.shape[0] - 1)
            columns = np.minimum(np.arange(cw) * block + dx, self.shape[1] - 1)
            coarse_angles += geometry.tth_array[np.ix_(rows, columns)] / 4
        self._context = native.create(coarse_angles, ranges, self.shape, int(block),
                                      int(background_radius), float(seed_contrast),
                                      float(wing_contrast), int(min_seed_pixels), int(min_seed_radius),
                                      int(max_growth), int(max_window_pixels), bool(exclude_zero))
        self._lock = Lock()
        self.last_regions = 0
        self.last_window_pixels = 0
        self.last_runtime_ms = 0.0

    def compute_mask(self, image, existing_mask=None):
        start = perf_counter_ns()
        with self._lock:
            # The application's empty user mask is common. Avoid a per-pixel
            # mask branch in the native reducer while still validating shape.
            if (isinstance(existing_mask, np.ndarray)
                    and existing_mask.dtype == np.bool_ and existing_mask.shape == self.shape
                    and not existing_mask.any()):
                existing_mask = None
            mask, self.last_regions, self.last_window_pixels = native.compute(
                self._context, image, existing_mask)
            self.last_runtime_ms = (perf_counter_ns() - start) / 1e6
            if self.last_runtime_ms >= 10:
                raise RuntimeError(
                    f"Diamond ROI detection exceeded 10 ms ({self.last_runtime_ms:.2f} ms); "
                    "no mask returned"
                )
        return mask
