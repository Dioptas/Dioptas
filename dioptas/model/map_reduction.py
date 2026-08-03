# SPDX-License-Identifier: MIT

"""Reducing a window of each pattern to the single number a map cell shows.

Summing the counts in a window is the obvious reduction and the one Dioptas
started with, but it answers a narrow question. A raw sum tracks how much
sample the beam went through as much as it tracks the phase, so maps made
that way often show thickness. The alternatives here separate those:

- ``area`` subtracts the straight line joining the window edges first, so
  what is left is the peak rather than the peak plus whatever background it
  sits on.
- ``center`` is the intensity-weighted centre of the peak, i.e. its
  position. Mapped over a scan that is a d-spacing map, and so a strain map.
- ``width`` is the full width at half maximum, which tracks grain size and
  mosaicity.

Every function takes the whole (points × channels) intensity block and
returns one value per point, with NaN wherever the window holds too little
to answer.
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "REDUCTIONS",
    "REDUCTION_LABELS",
    "VALUE_KINDS",
    "linear_background",
    "reduce_window",
    "window_indices",
]

#: reduction key -> short label for the UI
REDUCTION_LABELS = {
    "sum": "Sum",
    "mean": "Mean",
    "max": "Maximum",
    "area": "Peak area",
    "center": "Peak position",
    "width": "Peak width (FWHM)",
}

REDUCTIONS = tuple(REDUCTION_LABELS)

#: what the UI offers in one list, as (short label, reduction,
#: subtract_background). Background subtraction is a property of the choice
#: rather than a separate switch: it is mandatory for the peak-shape
#: reductions, so a column of sometimes-disabled checkboxes said less than
#: folding it in here. The long names in REDUCTION_LABELS become the
#: tooltips.
VALUE_KINDS = (
    ("Sum", "sum", False),
    ("Sum − bkg", "sum", True),
    ("Mean", "mean", False),
    ("Max", "max", False),
    ("Peak area", "area", False),
    ("Peak pos.", "center", False),
    ("Peak FWHM", "width", False),
)

#: reductions that are about the peak rather than the raw counts, and so
#: always want the background taken off first
_ALWAYS_SUBTRACT = ("area", "center", "width")

#: fraction of the window at each end averaged to anchor the background line
_EDGE_FRACTION = 0.1


def window_indices(pattern_x, window) -> np.ndarray:
    """Channel indices of *pattern_x* inside the (low, high) *window*."""
    pattern_x = np.asarray(pattern_x)
    low, high = float(window[0]), float(window[1])
    return np.where((pattern_x > low) & (pattern_x < high))[0]


def linear_background(x: np.ndarray, block: np.ndarray) -> np.ndarray:
    """The straight line joining the two ends of each row of *block*.

    Both ends are averaged over a small fraction of the window rather than
    read off a single channel, so noise in one channel cannot tilt the whole
    baseline.
    """
    num_channels = block.shape[1]
    edge = max(1, int(round(_EDGE_FRACTION * num_channels)))

    left_y = block[:, :edge].mean(axis=1)
    right_y = block[:, -edge:].mean(axis=1)
    left_x = float(x[:edge].mean())
    right_x = float(x[-edge:].mean())

    span = right_x - left_x
    if span == 0:
        return np.repeat(left_y[:, None], num_channels, axis=1)

    slope = (right_y - left_y) / span
    return left_y[:, None] + slope[:, None] * (x - left_x)[None, :]


def reduce_window(
    pattern_x,
    intensities,
    window,
    reduction: str = "sum",
    subtract_background: bool = False,
) -> np.ndarray:
    """Reduces each pattern's *window* to one value.

    :param pattern_x: radial axis shared by all patterns
    :param intensities: (points × channels) array of pattern intensities
    :param window: (low, high) of the radial axis
    :param reduction: one of :data:`REDUCTIONS`
    :param subtract_background: take off the straight line joining the window
        edges first. Implied by the peak-shape reductions.
    :returns: one value per point, NaN where the window holds too little
    """
    intensities = np.asarray(intensities, dtype=float)
    if intensities.ndim != 2:
        raise ValueError("intensities must be a 2D (points x channels) array")
    num_points = intensities.shape[0]

    indices = window_indices(pattern_x, window)
    if len(indices) == 0:
        return np.full(num_points, np.nan)

    x = np.asarray(pattern_x, dtype=float)[indices]
    block = intensities[:, indices]

    if reduction in _ALWAYS_SUBTRACT or subtract_background:
        if len(indices) < 2:
            return np.full(num_points, np.nan)
        block = block - linear_background(x, block)

    if reduction == "sum":
        return block.sum(axis=1)
    if reduction == "mean":
        return block.mean(axis=1)
    if reduction == "max":
        return block.max(axis=1)

    if len(indices) < 2:
        return np.full(num_points, np.nan)

    if reduction == "area":
        # d spacing runs the other way round, which would flip the sign
        return np.abs(np.trapezoid(block, x, axis=1))
    if reduction == "center":
        return _weighted_center(x, block)
    if reduction == "width":
        return _fwhm(x, block)

    raise ValueError(f"Unknown reduction: {reduction}")


def _weighted_center(x: np.ndarray, block: np.ndarray) -> np.ndarray:
    """Intensity-weighted centre of each row, in units of *x*."""
    # negative excursions of a background-subtracted profile would pull the
    # centre the wrong way, so only what rises above the baseline counts
    weights = np.clip(block, 0, None)
    total = weights.sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        center = (weights * x[None, :]).sum(axis=1) / total
    center[total <= 0] = np.nan
    return center


def _fwhm(x: np.ndarray, block: np.ndarray) -> np.ndarray:
    """Full width at half maximum of each row, in units of *x*.

    Measured by interpolating where the profile crosses half its maximum on
    either side of the peak — no fitting, so it survives peaks that are not
    quite Gaussian, and gives NaN when the peak runs off the window edge.
    """
    # ascending x keeps the crossing search in one direction for d spacing too
    if x[0] > x[-1]:
        x = x[::-1]
        block = block[:, ::-1]

    widths = np.full(block.shape[0], np.nan)
    for row_index, profile in enumerate(block):
        peak = profile.max()
        if not np.isfinite(peak) or peak <= 0:
            continue
        half = peak / 2.0
        apex = int(np.argmax(profile))

        left = _crossing(x, profile, apex, half, step=-1)
        right = _crossing(x, profile, apex, half, step=1)
        if left is None or right is None:
            # the peak does not come back down inside the window, so its
            # width is not something this window can say anything about
            continue
        widths[row_index] = right - left
    return widths


def _crossing(x, profile, apex: int, half: float, step: int) -> float | None:
    """Where the profile crosses *half* going outwards from *apex*."""
    index = apex
    end = -1 if step < 0 else len(profile)
    while index + step != end:
        following = index + step
        if profile[following] <= half:
            # linear interpolation between the straddling channels
            y0, y1 = profile[index], profile[following]
            if y1 == y0:
                return float(x[following])
            fraction = (profile[index] - half) / (y0 - y1)
            return float(x[index] + fraction * (x[following] - x[index]))
        index = following
    return None
