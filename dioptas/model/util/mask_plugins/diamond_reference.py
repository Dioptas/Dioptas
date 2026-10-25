# SPDX-License-Identifier: MIT
"""Diamond kinematic spacing prior; not a phase classifier."""
from math import ceil, sqrt
import numpy as np


def diamond_d_spacings(lattice_a: float, d_min: float) -> np.ndarray:
    """Cubic diamond kinematic reflections, unique d values in Angstrom.

    FCC translations require unmixed parity; the (1/4,1/4,1/4) basis cancels
    even reflections unless h+k+l is divisible by four. Thus 200 and 222
    are absent. Multiple diffraction/defect scattering is not modeled.
    """
    if not (
        np.isfinite(lattice_a) and np.isfinite(d_min) and lattice_a > 0 and d_min > 0
    ):
        raise ValueError("Lattice parameter and minimum spacing must be positive")
    limit = ceil(lattice_a / d_min)
    norms = set()
    for h in range(limit + 1):
        for k in range(h + 1):
            for l in range(k + 1):
                if h == k == l == 0:
                    continue
                if h % 2 != k % 2 or k % 2 != l % 2:
                    continue
                if h % 2 == 0 and (h + k + l) % 4 != 0:
                    continue
                n = h * h + k * k + l * l
                if n <= (lattice_a / d_min) ** 2:
                    norms.add(n)
    return np.array([lattice_a / sqrt(n) for n in sorted(norms)])


def diamond_seed_ranges(tth_max, wavelength, lattice_a=3.567, d_tolerance_percent=3.0):
    """Angle bounds in radians; wavelength in metres, lattice parameter in Å."""
    if not (np.isfinite(lattice_a) and lattice_a > 0
            and np.isfinite(d_tolerance_percent) and 0 < d_tolerance_percent < 100):
        raise ValueError("Invalid diamond lattice parameter or spacing tolerance")
    if not (np.isfinite(wavelength) and wavelength > 0 and 0 < tth_max <= np.pi):
        raise ValueError("Diamond masking requires a valid wavelength and scattering angles")
    wavelength *= 1e10
    tolerance = d_tolerance_percent / 100
    d_min = wavelength / (2 * np.sin(tth_max / 2)) / (1 + tolerance)
    ranges = []
    for d in diamond_d_spacings(lattice_a, d_min):
        low = wavelength / (2 * d * (1 + tolerance))
        high = wavelength / (2 * d * (1 - tolerance))
        if low <= 1:
            ranges.append((2 * np.arcsin(low), 2 * np.arcsin(min(high, 1))))
    return ranges
