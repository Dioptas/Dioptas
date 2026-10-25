# SPDX-License-Identifier: MIT
"""Prepared serial diamond detector for the experimental single-crystal mode."""
from __future__ import annotations

from threading import Lock
from dataclasses import dataclass
from time import perf_counter_ns
import numpy as np

from .diamond_reference import diamond_seed_ranges

try:
    from . import _diamond_roi_c as native
except ImportError:
    native = None


@dataclass(frozen=True)
class AffineDiamondGeometry:
    shape: tuple[int, int]
    vectors: np.ndarray
    wavelength: float

    def angles(self, y, x):
        origin, fast, slow = self.vectors[:3]
        rays = [origin[k] + x * fast[k] + y * slow[k] for k in range(3)]
        if np.any(rays[2] <= 0):
            raise ValueError("Diamond mask requires a detector in front of the sample")
        return np.arctan2(np.hypot(rays[0], rays[1]), rays[2])


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
        affine = isinstance(geometry, AffineDiamondGeometry)
        self.shape = geometry.shape if affine else geometry.tth_array.shape
        if len(self.shape) != 2 or not 1 <= block <= 64:
            raise ValueError("Invalid detector shape or block size")
        if affine:
            h, w = self.shape
            maximum = float(geometry.angles(np.array([0, 0, h-1, h-1]),
                                           np.array([0, w-1, 0, w-1])).max())
        else:
            finite = np.isfinite(geometry.tth_array)
            maximum = float(geometry.tth_array[finite].max()) if finite.any() else None
        ranges = np.array(diamond_seed_ranges(maximum, geometry.wavelength, lattice_a,
                                             d_tolerance_percent) if maximum is not None else [],
                          dtype=float).reshape(-1, 2)
        # Symmetric samples of the geometry, not a per-frame subsampling of
        # intensities: the native reducer reads every image pixel.
        ch, cw = ((n + block - 1) // block for n in self.shape)
        coarse_angles = np.zeros((ch, cw))
        low = max(0, block // 4)
        high = block - 1 - low
        for dy, dx in [(low, low), (low, high), (high, low), (high, high)]:
            rows = np.minimum(np.arange(ch) * block + dy, self.shape[0] - 1)
            columns = np.minimum(np.arange(cw) * block + dx, self.shape[1] - 1)
            coarse_angles += (geometry.angles(rows[:, None], columns[None, :]) if affine
                              else geometry.tth_array[np.ix_(rows, columns)]) / 4
        coarse_angles.flags.writeable = ranges.flags.writeable = False
        self._arguments = (coarse_angles, ranges, self.shape, int(block),
                                      int(background_radius), float(seed_contrast),
                                      float(wing_contrast), int(min_seed_pixels), int(min_seed_radius),
                                      int(max_growth), int(max_window_pixels), bool(exclude_zero))
        self._initialize_context()

    def _initialize_context(self):
        self._context = native.create(*self._arguments)
        self._lock = Lock()
        self.last_regions = 0
        self.last_window_pixels = 0
        self.last_runtime_ms = 0.0

    def copy(self):
        """Independent worker scratch, sharing only immutable prepared geometry."""
        other = object.__new__(type(self))
        other.shape, other._arguments = self.shape, self._arguments
        other._initialize_context()
        return other

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
