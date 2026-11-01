# SPDX-License-Identifier: MIT
"""Optional map display interpolation and contours; never alters scan values."""
import numpy as np
from scipy.ndimage import zoom
from skimage.measure import find_contours


def preview(array, smooth=1, contours=0):
    """Qt uses cubic interpolation and threefold contour upsampling.

    Unlike Qt's raw NaN interpolation, retain the blank footprint so a missing
    scan cell cannot turn into a finite interpolated observation.
    """
    data = np.flipud(np.asarray(array, dtype=float))
    finite = np.isfinite(data)
    minimum = float(data[finite].min()) if finite.any() else 0.0
    filled = np.where(finite, data, minimum)
    if smooth > 1:
        image = zoom(filled, smooth, order=3)
        valid = zoom(finite, smooth, order=0)
        image[~valid] = np.nan
    else:
        image = data
    paths = []
    if contours and min(data.shape) > 1 and finite.any():
        upsampled = zoom(filled, 3, order=3)
        lo, hi = float(upsampled.min()), float(upsampled.max())
        if lo < hi:
            for level in np.linspace(lo, hi, contours+2)[1:-1]:
                for path in find_contours(upsampled, level):
                    paths.append(np.column_stack(((path[:, 1]+0.5)/3, (path[:, 0]+0.5)/3)).tolist())
    return image, paths
