# SPDX-License-Identifier: MIT
"""Spacing-informed diamond candidates; deliberately not a phase classifier."""

from math import ceil, sqrt
import numpy as np

from .powder_outlier import PowderDiffSpotMaskPlugin


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


class DiamondSpotMaskPlugin(PowderDiffSpotMaskPlugin):
    name = "Diamond Spot Mask (experimental)"
    description = (
        "Detects broad spots near allowed diamond d-spacings, then grows their "
        "connected wings. Requires calibration. Does not mask complete rings. "
        "Sample signal overlapping a detected diamond footprint is excluded too. "
        "A matching d-spacing alone does not identify diamond; review the overlay."
    )

    def __init__(self):
        super().__init__()
        self.algorithm = "broad"
        # Approximate ambient reference, not a pressure/strain correction.
        # Yamanaka et al. (1994), doi:10.1103/PhysRevB.49.9341.
        self.lattice_a = 3.567
        self.d_tolerance_percent = 3.0

    def _seed_ranges(self, geometry):
        wavelength = geometry.wavelength * 1e10  # meters -> Angstrom
        finite = np.isfinite(geometry.tth_array)
        if not np.any(finite):
            return []
        tth_max = float(np.max(geometry.tth_array[finite]))
        if not (np.isfinite(wavelength) and wavelength > 0 and 0 < tth_max <= np.pi):
            raise ValueError(
                "Diamond masking requires a valid wavelength and scattering angles"
            )
        tolerance = self.d_tolerance_percent / 100
        # Include nominal lines whose lower-d band reaches the detector.
        d_min = wavelength / (2 * np.sin(tth_max / 2)) / (1 + tolerance)
        spacings = diamond_d_spacings(self.lattice_a, d_min)
        ranges = []
        for d in spacings:
            low = wavelength / (2 * d * (1 + tolerance))
            high = wavelength / (2 * d * (1 - tolerance))
            if low <= 1:
                ranges.append((2 * np.arcsin(low), 2 * np.arcsin(min(high, 1))))
        return ranges

    def get_settings_schema(self):
        common = self._get_all_settings_schema()
        return {
            "lattice_a": {
                "type": "float",
                "default": 3.567,
                "label": "Diamond a (Å)",
                "min": 2.0,
                "max": 5.0,
                "decimals": 4,
                "step": 0.001,
                "description": "Approximate ambient default; adjust for the anvil state. No sample-pressure EOS is assumed.",
            },
            "d_tolerance_percent": {
                "type": "float",
                "default": 3.0,
                "label": "Seed d-spacing tolerance (±%)",
                "min": 0.1,
                "max": 20.0,
                "decimals": 1,
                "step": 0.1,
                "description": "Tolerance on the signal-weighted seed center for strain/calibration offsets. Wings may grow outside this band.",
            },
            **{
                key: value
                for key, value in common.items()
                if key == "num_bins" or key.startswith("broad_")
            },
        }

    def get_settings(self):
        common = super().get_settings()
        return {
            "lattice_a": self.lattice_a,
            "d_tolerance_percent": self.d_tolerance_percent,
            **{
                key: value
                for key, value in common.items()
                if key == "num_bins" or key.startswith("broad_")
            },
        }

    def update_settings(self, settings):
        lattice_a = settings.get("lattice_a", self.lattice_a)
        tolerance = settings.get("d_tolerance_percent", self.d_tolerance_percent)
        if not (
            np.isfinite(lattice_a)
            and lattice_a > 0
            and np.isfinite(tolerance)
            and 0 < tolerance < 100
        ):
            raise ValueError("Invalid diamond lattice parameter or spacing tolerance")
        super().update_settings({**settings, "algorithm": "broad"})
        self.lattice_a = lattice_a
        self.d_tolerance_percent = tolerance
