# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
# Principal author: Clemens Prescher (clemens.prescher@gmail.com)
# Copyright (C) 2014-2019 GSECARS, University of Chicago, USA
# Copyright (C) 2015-2018 Institute for Geology and Mineralogy, University of Cologne, Germany
# Copyright (C) 2019-2020 DESY, Hamburg, Germany
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
from __future__ import annotations

import re
from typing import Optional
import numpy as np


def _auto_level(hist_x: np.ndarray, hist_y: np.ndarray) -> tuple[float, float]:
    """Compute colormap range from histogram

    :param hist_x: Bin left edges
    :param hist_y: Histogram count
    :returns: (min, max)
    """
    hist_y_cumsum = np.cumsum(hist_y)
    hist_y_sum = np.sum(hist_y)

    max_ind = np.where(hist_y_cumsum < (0.996 * hist_y_sum))
    min_level = np.mean(hist_x[:2])

    if len(max_ind[0]):
        max_level = hist_x[max_ind[0][-1]]
    else:
        max_level = 0.5 * np.max(hist_x)

    if len(hist_x[hist_x > 0]) > 0:
        min_level = max(min_level, np.nanmin(hist_x[hist_x > 0]))
    return min_level, max_level


def _default_auto_level(data: np.ndarray) -> tuple[float, float]:
    """Compute colormap range from data through histogram

    :param data: Data from which to compute levels
    :returns: (lower limit, upper limit)
    """
    counts, bin_edges = np.histogram(data, bins=3000)
    left_edges = bin_edges[:-1]
    left_edges = left_edges[np.where(counts > 0)]
    counts = counts[np.where(counts > 0)]

    hist_y_cumsum = np.cumsum(counts)
    hist_y_sum = np.sum(counts)

    max_ind = np.where(hist_y_cumsum < (0.996 * hist_y_sum))
    min_level = np.mean(left_edges[:2])

    if len(max_ind[0]):
        max_level = left_edges[max_ind[0][-1]]
    else:
        max_level = 0.5 * np.max(left_edges)

    if len(left_edges[left_edges > 0]) > 0:
        min_level = max(min_level, np.nanmin(left_edges[left_edges > 0]))
    return min_level, max_level


def _minmax_auto_level(data: np.ndarray) -> tuple[float, float]:
    """Returns min/max of the data

    :param data: Data from which to compute levels
    :returns: (min, max)
    """
    return float(np.min(data)), float(np.max(data))


def _mean3std_auto_level(data: np.ndarray) -> tuple[float, float]:
    """Returns mean+/-3std clipped to min/max of the data

    :param data: Data from which to compute levels
    :returns: (lower limit, upper limit)
    """
    mean = np.mean(data, dtype=np.float64)
    std = np.std(data, dtype=np.float64)
    minimum, maximum = _minmax_auto_level(data)
    return max(mean - 3 * std, minimum), min(mean + 3 * std, maximum)


def _percentile_auto_level(
    data: np.ndarray, percentile: float = 1.0
) -> tuple[float, float]:
    """Returns data range corresponding to [precentile, 100-percentile]

    :param data: Data from which to compute levels
    :returns: (lower limit, upper limit)
    """
    if not 0.0 <= percentile < 50.0:
        raise ValueError("Percentiles must be in the range [0, 50[")
    lower, upper = np.percentile(data, [percentile, 100.0 - percentile])
    return float(lower), float(upper)


def detector_gap_mask(data: np.ndarray) -> np.ndarray:
    """Probe detector gap value and returns mask of pixels not belonging to gaps.

    :param data: 2D image array for which to compute the mask
    :returns: Mask with True for valid pixels and False for mask
    """
    if data.ndim != 2:
        raise ValueError("2D array only are supported")

    # Find columns with same values
    equal_columns_mask = np.all(np.equal(data[0], data), axis=0)
    if not np.any(equal_columns_mask):
        return np.ones(data.shape, dtype=bool)

    equal_values, counts = np.unique(data[0, equal_columns_mask], return_counts=True)
    # At least 2 columns and not the whole image
    mask = np.logical_and(counts > 1, counts < data.shape[1])
    equal_values = equal_values[mask]
    counts = counts[mask]
    if len(equal_values) == 0:
        return np.ones(data.shape, dtype=bool)

    value = equal_values[np.argmax(counts)]
    return data != value


def auto_level(
    data: Optional[np.ndarray],
    hist_x: Optional[np.ndarray],
    hist_y: Optional[np.ndarray],
    mode: str = "default",
    filter_gaps: bool = False,
) -> Optional[tuple[float, float]]:
    """Compute colormap range from data

    :param data: Data from which to compute colormap range
    :param hist_x: Bin left edges
    :param hist_y: Histogram count
    :param mode: Mode of autoscale computation: "default", "minmax", "mean3std"
    :param filter_gaps: Whether or not to probe and filter gaps
    :returns: (min, max) or None
    :raise ValueError: If the mode is not supported
    """
    if data is None:
        return None

    if filter_gaps:
        data = data[detector_gap_mask(data)]

    filtered_data = data[np.isfinite(data)]
    if filtered_data.size == 0:
        return None

    if mode == "default":
        if hist_x is None or hist_y is None:
            return _default_auto_level(filtered_data)
        else:
            return _auto_level(hist_x, hist_y)
    if mode == "minmax":
        return _minmax_auto_level(filtered_data)
    if mode == "mean3std":
        return _mean3std_auto_level(filtered_data)
    match = re.match(r"(?P<value>\d+(\.\d*)?|\.\d+)percentile", mode)
    if match is not None:
        return _percentile_auto_level(filtered_data, percentile=float(match["value"]))
    raise ValueError(f"Unsupported mode: {mode}")
