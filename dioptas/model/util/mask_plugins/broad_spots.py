# SPDX-License-Identifier: MIT
"""Experimental broad-region detection; no phase or unit-cell information."""

from __future__ import annotations

import numpy as np
from scipy.ndimage import (
    binary_propagation,
    gaussian_filter,
    label,
    uniform_filter,
    grey_opening,
    distance_transform_edt,
)


def _local_plane(values, weights, window):
    """Weighted local plane evaluated at each pixel, including partial windows.

    A local constant leaves a false positive residual along a sloping detector
    edge. Centered spatial covariances fit the slope without extrapolating
    through missing data. Box sums use constant padding for real coordinates.
    """
    y, x = np.indices(values.shape, dtype=float)
    w = weights.astype(float)
    denominator = uniform_filter(w, size=window, mode="constant")

    def average(v):
        return np.divide(
            uniform_filter(v, size=window, mode="constant"),
            denominator,
            out=np.zeros_like(values),
            where=denominator > 1e-12,
        )

    mx, my = average(w * x), average(w * y)
    mean = average(np.where(weights, values, 0))
    xx = average(w * x * x) - mx * mx
    yy = average(w * y * y) - my * my
    xy = average(w * x * y) - mx * my
    vx = average(np.where(weights, values * x, 0)) - mean * mx
    vy = average(np.where(weights, values * y, 0)) - mean * my
    det = xx * yy - xy * xy
    supported = (denominator > 1e-12) & (det > 1e-8)
    bx = np.divide(vx * yy - vy * xy, det, out=np.zeros_like(values), where=supported)
    by = np.divide(vy * xx - vx * xy, det, out=np.zeros_like(values), where=supported)
    return mean + bx * (x - mx) + by * (y - my), supported


def broad_spot_mask(
    image,
    bin_indices,
    num_bins,
    existing_mask=None,
    *,
    seed_sigma=5.0,
    grow_sigma=0.8,
    min_pixels=100,
    background_radius=128,
    smooth_sigma=1.5,
    exclude_zero=True,
    radial_coordinates=None,
    seed_ranges=None,
    max_growth=32.0,
    min_seed_radius=8.0,
):
    """Find spatially coherent excess above a radial + local background.

    First remove the per-2theta median profile. Bound its scaled MAD by a local
    high-pass noise estimate so azimuthal illumination variation does not set
    the wing cutoff (neither scale is a calibrated counting uncertainty). Estimate the local
    residual background with four positive-outlier-clipped local plane fits.
    Smooth the normalized residual, retain connected high-threshold
    seeds by area, then grow only those seeds through lower-threshold support.

    This selects morphology, not diamond. Narrow sample spots can survive the
    size filter, and broad/overlapping sample diffraction can be removed.
    Saturated pixels participate as observed lower bounds; no intensity is
    reconstructed and no maximum component size rejects large reflections.
    """
    if not (
        np.isfinite(seed_sigma)
        and np.isfinite(grow_sigma)
        and 0 < grow_sigma
        and 0 < seed_sigma
    ):
        raise ValueError("Thresholds must be finite and positive")
    grow_sigma = min(grow_sigma, seed_sigma)
    if (
        min_pixels < 1
        or background_radius < 1
        or smooth_sigma < 0
        or max_growth < 0
        or min_seed_radius < 0
    ):
        raise ValueError("Invalid broad-region size or smoothing setting")
    image = np.asarray(image, dtype=np.float64)
    bins = np.asarray(bin_indices).reshape(image.shape)
    valid = np.isfinite(image) & (bins >= 0) & (bins < num_bins)
    if exclude_zero:
        valid &= image != 0
    if existing_mask is not None:
        valid &= ~np.asarray(existing_mask, dtype=bool)
    empty = np.zeros(image.shape, dtype=bool)
    if not np.any(valid):
        return empty

    # Group once, rather than scan the full image once for each radial bin.
    indices = np.flatnonzero(valid)
    order = indices[np.argsort(bins.ravel()[indices])]
    cuts = np.searchsorted(bins.ravel()[order], np.arange(num_bins + 1))
    centers = np.zeros(num_bins)
    spreads = np.zeros(num_bins)
    angles = np.zeros(num_bins)
    populated = np.zeros(num_bins, bool)
    for b in range(num_bins):
        selected = order[cuts[b] : cuts[b + 1]]
        values = image.ravel()[selected]
        if values.size < 3:
            continue
        centers[b] = np.median(values)
        spread = 1.4826 * np.median(np.abs(values - centers[b]))
        spreads[b] = spread if spread > 0 else np.std(values)
        populated[b] = True
        if radial_coordinates is not None:
            angles[b] = np.median(np.asarray(radial_coordinates).ravel()[selected])

    safe_bins = np.clip(bins, 0, num_bins - 1)
    radial_center = centers[safe_bins]
    noise = spreads[safe_bins]
    if radial_coordinates is not None and np.count_nonzero(populated) >= 2:
        # A staircase profile creates artificial rings at bin boundaries;
        # interpolate the radial model at the actual pixel scattering angle.
        radial_center = np.interp(
            radial_coordinates, angles[populated], centers[populated]
        )
        noise = np.interp(radial_coordinates, angles[populated], spreads[populated])
    valid &= np.isfinite(noise) & (noise > 0)
    if not np.any(valid):
        return empty
    # Azimuthal illumination gradients inflate a whole-ring MAD. Estimate the
    # local noise from a one-pixel high-pass residual as well. Clip its absolute
    # deviations before averaging, so sharp/saturated peaks cannot dominate it.
    weights = valid.astype(float)
    denominator = gaussian_filter(weights, 1.0)
    local_mean = np.divide(
        gaussian_filter(np.where(valid, image, 0), 1.0),
        denominator,
        out=np.zeros_like(image),
        where=denominator > 1e-12,
    )
    deviations = np.where(valid, np.minimum(np.abs(image - local_mean), 3 * noise), 0)
    denominator = uniform_filter(weights, size=33)
    local_noise = np.divide(
        1.4826 * uniform_filter(deviations, size=33),
        denominator,
        out=np.zeros_like(image),
        where=denominator > 1e-12,
    )
    noise = np.where(local_noise > 0, np.minimum(noise, local_noise), noise)
    residual = np.where(valid, image - radial_center, 0)
    window = 2 * int(background_radius) + 1
    denominator = gaussian_filter(valid.astype(float), 1.5)
    smoothed_image = np.divide(
        gaussian_filter(np.where(valid, image, 0), 1.5),
        denominator,
        out=np.zeros_like(image),
        where=denominator > 1e-12,
    )
    if not np.all(valid):
        nearest = distance_transform_edt(
            ~valid, return_distances=False, return_indices=True
        )
        smoothed_image = smoothed_image[tuple(nearest)]
    envelope = grey_opening(smoothed_image, size=window) - radial_center
    background = np.zeros(image.shape)
    for iteration in range(4):
        weights = (
            valid if iteration == 0 else valid & (residual < background + 3 * noise)
        )
        background, supported = _local_plane(residual, weights, window)
    valid &= supported
    # An opening preserves a broad illumination step but removes a compact
    # peak. The conservative upper envelope prevents a local-plane fit across
    # that step from treating the illuminated side as a reflection.
    background = np.maximum(background, envelope)
    score = np.divide(
        residual - background, noise, out=np.zeros_like(image), where=valid
    )
    if smooth_sigma > 0:
        denominator = gaussian_filter(valid.astype(float), smooth_sigma)
        numerator = gaussian_filter(np.where(valid, score, 0), smooth_sigma)
        score = np.divide(
            numerator, denominator, out=np.zeros_like(image), where=denominator > 1e-12
        )

    # Four-connected components and propagation cannot bridge a masked gap.
    seed_pixels = valid & (score > seed_sigma)
    if min_seed_radius > 0:
        # Open the seed footprint so a thin powder arc attached to a broad
        # reflection cannot borrow that reflection's width and become a seed.
        interior = distance_transform_edt(seed_pixels) >= min_seed_radius
        if not np.any(interior):
            return empty
        seed_pixels &= distance_transform_edt(~interior) < min_seed_radius
    seeds, _ = label(seed_pixels)
    sizes = np.bincount(seeds.ravel())
    sizes[0] = 0
    accepted = sizes >= min_pixels
    if seed_ranges is not None:
        if radial_coordinates is None:
            raise ValueError("Seed ranges require scattering-angle coordinates")
        # Gate each seed's signal-weighted mean angle, not every wing pixel:
        # a broad diamond halo may extend outside its Bragg-spacing band.
        weights = np.where(seeds > 0, np.maximum(residual - background, 0), 0)
        totals = np.bincount(
            seeds.ravel(), weights=weights.ravel(), minlength=sizes.size
        )
        moment = np.bincount(
            seeds.ravel(),
            weights=(weights * np.where(valid, radial_coordinates, 0)).ravel(),
            minlength=sizes.size,
        )
        angles = np.divide(moment, totals, out=np.zeros_like(moment), where=totals > 0)
        in_band = np.zeros(sizes.size, bool)
        for low, high in seed_ranges:
            in_band |= (angles >= low) & (angles <= high)
        accepted &= in_band & (totals > 0)
    accepted[0] = False
    seeds = accepted[seeds]
    if not np.any(seeds):
        return empty
    reach = distance_transform_edt(~seeds) <= max_growth
    return binary_propagation(seeds, mask=valid & reach & (score > grow_sigma))
