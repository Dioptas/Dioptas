# SPDX-License-Identifier: MIT
"""Prepared diamond exclusions, and rejection of entire overlapping supports."""
from dataclasses import replace
import hashlib
from pathlib import Path

import numpy as np

from .util.mask_plugins.diamond_roi import AffineDiamondGeometry, DiamondROIDetector, native


def available():
    return native is not None


class DiamondMaskPlan:
    def __init__(self, filename, shape, *, transformations=(), original_rows=False,
                 lattice_a=3.567, tolerance=3.0, exclude_zero=True):
        from .single_crystal_indexing import geometry_from_poni

        panel, self.geometry = geometry_from_poni(
            filename, axis_sign=1, shape=shape, original_rows=original_rows,
            transformations=transformations,
        )
        self.settings = dict(block=8, background_radius=128, seed_contrast=5.0,
                             wing_contrast=0.8, min_seed_pixels=100, min_seed_radius=8,
                             max_growth=32, max_window_pixels=1_000_000,
                             lattice_a=lattice_a, d_tolerance_percent=tolerance,
                             exclude_zero=exclude_zero)
        self.engine_sha256 = hashlib.sha256(Path(native.__file__).read_bytes()).hexdigest() if native else None
        self.detector = DiamondROIDetector(
            AffineDiamondGeometry(tuple(shape), panel.vectors, panel.wavelength * 1e-10),
            **self.settings,
        )
        self.records = []

    def copy(self):
        other = object.__new__(type(self))
        other.geometry, other.settings = self.geometry, self.settings.copy()
        other.engine_sha256 = self.engine_sha256
        other.detector = self.detector.copy()
        other.records = []
        return other

    def compute(self, image, existing_mask=None, *, frame=None):
        mask = self.detector.compute_mask(image, existing_mask)
        mask.flags.writeable = False
        self.records.append(dict(frame=frame, runtime_ms=self.detector.last_runtime_ms,
                                 pixels=int(np.count_nonzero(mask))))
        return mask

    def metadata(self):
        return dict(algorithm="serial-diamond-roi-v1", settings=self.settings,
                    geometry=self.geometry, frames=list(self.records),
                    image_shape=list(self.detector.shape), native_engine_sha256=self.engine_sha256,
                    time_limit_ms=10,
                    overlap_policy="Reject entire measured aperture / linked track when any "
                    "frame support intersects the diamond mask; no partial intensity retained",
                    interpretation="Spacing-compatible broad candidates; not confirmed diamond identification")


def overlapping_supports(table, mask):
    return np.array([np.any(mask[y0:y1, x0:x1]) for x0, y0, x1, y1 in table.boxes], bool)


def exclude_overlapping_spots(table, mask):
    rejected = overlapping_supports(table, mask)
    if not rejected.any():
        return table, 0
    keep = ~rejected
    return replace(table, boxes=table.boxes[keep], values=table.values[keep],
                   flags=table.flags[keep]), int(rejected.sum())


def observation_key(frame, x, y):
    # Invalid centroids still have an unambiguous per-frame rejection key.
    return int(frame), float(x) if np.isfinite(x) else None, float(y) if np.isfinite(y) else None


def exclude_overlapping_tracks(table, rejected_observations):
    bad = {int(track) for track, frame, x, y, _ in table.observations
           if observation_key(frame, x, y) in rejected_observations}
    if not bad:
        return table, 0
    keep = np.ones(len(table), bool)
    keep[list(bad)] = False
    remap = np.full(len(table), -1, int)
    remap[keep] = np.arange(int(keep.sum()))
    observations = table.observations[keep[table.observations[:, 0].astype(int)]].copy()
    observations[:, 0] = remap[observations[:, 0].astype(int)]
    return replace(table, boxes=table.boxes[keep], frame_ranges=table.frame_ranges[keep],
                   values=table.values[keep], flags=table.flags[keep],
                   observations=observations), len(bad)
