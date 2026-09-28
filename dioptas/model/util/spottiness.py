# SPDX-License-Identifier: MIT
"""Azimuthal population spread, independent of uncertainty of the mean.

For signal s, correction n and pixel/bin overlap c, use x=s/n and w=c*n.
pyFAI's azimuthal error model uses different weights; its std is not this
statistic. Reuse its CSR overlaps instead, including sector and mask selection.
"""

import numpy as np


def weighted_spread(lut, signal, normalization):
    """Return stable weighted mean and population std for a CSR overlap LUT.

    Invalid pixels contribute no weight. Empty bins have mean 0 and std NaN.
    A shifted mean and a second residual pass avoid cancellation at high DC
    offsets. Work on contributions in chunks to bound temporary memory.
    """
    signal = np.asarray(signal, dtype=np.float64).ravel()
    normalization = np.asarray(normalization, dtype=np.float64).ravel()
    valid = np.isfinite(signal) & np.isfinite(normalization) & (normalization > 0)
    corrected = np.zeros_like(signal)
    np.divide(signal, normalization, out=corrected, where=valid)
    valid &= np.isfinite(corrected)
    corrected[~valid] = 0
    norm = np.where(valid, normalization, 0)
    coefficients, indices, indptr = lut
    weights = np.asarray(coefficients, dtype=np.float64) * norm[indices]
    weights[~np.isfinite(weights) | (weights <= 0)] = 0
    # Shift independently in each bin. A global origin would lose small
    # differences in a weak bin when another bin (or a masked pixel) is bright.
    origin = np.zeros(len(indptr) - 1)
    for row, (start, stop) in enumerate(zip(indptr[:-1], indptr[1:])):
        positive = np.flatnonzero(weights[start:stop] > 0)
        if positive.size:
            origin[row] = corrected[indices[start + positive[0]]]
    total = np.zeros_like(origin)
    first_moment = np.zeros_like(origin)
    for start in range(0, len(indices), 262144):
        stop = min(start + 262144, len(indices))
        rows = np.searchsorted(indptr, np.arange(start, stop), side="right") - 1
        delta = corrected[indices[start:stop]] - origin[rows]
        delta[weights[start:stop] == 0] = 0
        total += np.bincount(rows, weights=weights[start:stop], minlength=len(total))
        first_moment += np.bincount(
            rows, weights=weights[start:stop] * delta, minlength=len(total)
        )
    shifted_mean = np.divide(
        first_moment, total, out=np.zeros_like(total), where=total > 0
    )
    variance_sum = np.zeros_like(total)
    for start in range(0, len(indices), 262144):
        stop = min(start + 262144, len(indices))
        rows = np.searchsorted(indptr, np.arange(start, stop), side="right") - 1
        residual = (corrected[indices[start:stop]] - origin[rows]) - shifted_mean[rows]
        residual[weights[start:stop] == 0] = 0
        variance_sum += np.bincount(
            rows, weights=weights[start:stop] * residual**2, minlength=len(total)
        )
    std = np.sqrt(
        np.divide(variance_sum, total, out=np.full_like(total, np.nan), where=total > 0)
    )
    mean = np.where(total > 0, origin + shifted_mean, 0)
    return mean, std


def _correction_for_shape(array, shape):
    """Repeat detector corrections onto an integer supersampling grid."""
    if array is None or array.shape == shape:
        return array
    if (array.ndim != 2 or len(shape) != 2
            or any(target % source for target, source in zip(shape, array.shape))):
        raise ValueError("Detector correction does not match the integration image")
    factors = tuple(target // source for target, source in zip(shape, array.shape))
    if factors[0] != factors[1] or factors[0] < 1:
        raise ValueError("Detector correction requires uniform integer supersampling")
    return np.repeat(np.repeat(array, factors[0], axis=0), factors[1], axis=1)


def integrate_spottiness(integrator, image, num_points, kwargs):
    """Integrate with pyFAI and calculate population spread on the same bins."""
    kwargs = dict(kwargs, method=("bbox", "csr", "cython"))
    signal = np.asarray(image, dtype=np.float64)
    dark = _correction_for_shape(integrator.detector.darkcurrent, image.shape)
    if dark is not None:
        kwargs["dark"] = dark
    if dark is not None:
        signal = signal - dark
    norm = np.ones(image.shape, dtype=np.float64)
    if kwargs.get("correctSolidAngle", True):
        norm *= integrator.solidAngleArray(image.shape)
    polarization = kwargs.get("polarization_factor")
    if polarization is not None:
        norm *= integrator.polarization(image.shape, factor=polarization)
    flat = _correction_for_shape(integrator.detector.flatfield, image.shape)
    if flat is not None:
        kwargs["flat"] = flat
        norm *= flat
    invalid = ~np.isfinite(signal) | ~np.isfinite(norm) | (norm <= 0)
    # Passing an explicit mask replaces the detector mask in pyFAI.
    mask = kwargs.get("mask")
    if mask is None:
        mask = _correction_for_shape(integrator.detector.mask, image.shape)
    if mask is not None:
        invalid |= np.asarray(mask, dtype=bool)
    kwargs["mask"] = invalid
    try:
        result = integrator.integrate1d(image, num_points, **kwargs)
    except NameError:
        # Let pyFAI resolve an available CSR implementation, retaining a LUT
        # for the independent population statistic.
        kwargs["method"] = "csr"
        result = integrator.integrate1d(image, num_points, **kwargs)
    engine = integrator.engines[result.method].engine
    intensity, std = weighted_spread(engine.lut, signal, norm)
    return result, intensity, std


def relative_spread(intensity, std):
    """Coefficient of variation; omit nonpositive and numerically tiny means.

    The cutoff is 1e-12 of the largest finite absolute mean (with a unit floor).
    This keeps ratios finite and avoids misleading spikes near a zero crossing.
    """
    intensity = np.asarray(intensity, dtype=float)
    std = np.asarray(std, dtype=float)
    finite = np.where(np.isfinite(intensity), np.abs(intensity), 0)
    threshold = 1e-12 * np.maximum(1.0, finite.max(axis=-1, keepdims=True, initial=0))
    result = np.full_like(std, np.nan)
    np.divide(
        std,
        intensity,
        out=result,
        where=np.isfinite(intensity) & np.isfinite(std) & (intensity > threshold),
    )
    result[~np.isfinite(result)] = np.nan
    return result


def trim_spread(radial, intensity, sigma, std):
    """Trim unpopulated trailing bins, retaining measured bins with zero mean."""
    populated = np.flatnonzero(np.isfinite(std))
    length = int(populated[-1]) + 1 if populated.size else len(std)
    return (
        radial[:length],
        intensity[:length],
        None if sigma is None else sigma[:length],
        std[:length],
    )
