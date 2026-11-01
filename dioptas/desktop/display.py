# SPDX-License-Identifier: MIT
"""Qt-free counterparts of Dioptas plot_widgets.utils.AutoLevel calculations."""
import numpy as np


def _gap_value(image):
    for data in (image, image.T):
        columns = np.all(data == data[0], axis=0)
        values, counts = np.unique(data[0, columns], return_counts=True)
        keep = (counts > 1) & (counts < data.shape[1])
        if np.any(keep):
            return values[keep][np.argmax(counts[keep])]
    return None


def image_levels(image, mode="percentile", percentile=0.4, filter_gaps=True):
    if mode not in {"percentile", "minmax", "mean3std"}:
        raise ValueError("Choose Percentile, Min/max, or Mean ± 3 Std.")
    if not isinstance(filter_gaps, bool):
        raise ValueError("Filter gaps must be a boolean.")
    percentile = float(percentile)
    if not np.isfinite(percentile) or not 0 <= percentile < 50:
        raise ValueError("The clipping percentile must be between 0 and 50.")
    data = np.asarray(image)
    gap = _gap_value(data) if filter_gaps and data.ndim == 2 else None
    valid = np.isfinite(data)
    if gap is not None:
        valid &= data != gap
    values = data[valid]
    if not values.size:
        return None
    low, high = float(values.min()), float(values.max())
    if mode == "percentile":
        low, high = np.percentile(values, [percentile, 100 - percentile])
    elif mode == "mean3std":
        mean, std = np.mean(values, dtype=np.float64), np.std(values, dtype=np.float64)
        low, high = max(low, mean - 3 * std), min(high, mean + 3 * std)
    if high <= low:
        high = low + max(1.0, abs(low) * 1e-6)
    return [float(low), float(high)]
