# SPDX-License-Identifier: MIT

import numpy as np

s2pi = np.sqrt(2 * np.pi)


def gaussian(
    x: np.ndarray,
    amplitude: float = 1.0,
    center: float = 0.0,
    sigma: float = 1.0,
) -> np.ndarray:
    """1-dimensional Gaussian."""
    return (amplitude / (s2pi * sigma)) * np.exp(-(1.0 * x - center) ** 2 / (2 * sigma ** 2))
