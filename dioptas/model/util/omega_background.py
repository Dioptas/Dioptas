# SPDX-License-Identifier: MIT
"""Independent arPLS for detector-pixel sequences along omega.

Equations: Baek et al., Analyst 140 (2015), 250–257,
doi:10.1039/C4AN01061B. The application along omega is inspired by
Konstantin Glazyrin's background-sc. No implementation code is imported
or adapted from that project. See docs/source/omega_background.rst.
"""

from __future__ import annotations

from dataclasses import dataclass
import os

import numpy as np
from scipy.linalg import solveh_banded
from scipy.special import expit

try:
    from . import _omega_arpls
except ImportError:
    _omega_arpls = None


@dataclass(frozen=True)
class ArPLSParameters:
    smoothness: float = 1e4
    tolerance: float = 1e-3
    max_iterations: int = 30

    def __post_init__(self):
        if not np.isfinite(self.smoothness) or not 1e-6 <= self.smoothness <= 1e9:
            raise ValueError("Smoothness must be between 1e-6 and 1e9.")
        if not np.isfinite(self.tolerance) or not 0 < self.tolerance < 1:
            raise ValueError("Tolerance must be between 0 and 1.")
        if (
            isinstance(self.max_iterations, bool)
            or not isinstance(self.max_iterations, int)
            or not 1 <= self.max_iterations <= 1000
        ):
            raise ValueError("Maximum iterations must be an integer from 1 to 1000.")


def default_workers():
    return min(8, os.cpu_count() or 1)


def backend_name():
    if _omega_arpls is None:
        return "SciPy CPU (native extension unavailable)"
    return (
        "Native CPU + OpenMP" if _omega_arpls.openmp_enabled else "Native CPU (serial)"
    )


def arpls_rows(rows, parameters=None, *, workers=1, backend="auto"):
    """Return (baseline, iteration_counts, converged) for (pixels, frames).

    Natural second-difference boundaries, no padding; negative residuals are
    retained. A 1e-8 weight floor keeps the penalized system positive definite.
    Rows are normalized internally; calculations and returned baselines use
    float64. Inputs are never modified. The SciPy path is an independent,
    deliberately simple reference and a portable fallback.
    """
    parameters = parameters or ArPLSParameters()
    rows = np.asarray(rows)
    if rows.ndim != 2 or rows.shape[1] < 3 or rows.dtype.kind not in "fiu":
        raise ValueError(
            "Expected a real numeric (pixels, frames) array with at least 3 frames."
        )
    if not np.all(np.isfinite(rows)):
        raise ValueError("Pixel sequences must contain only finite values.")
    if (
        isinstance(workers, bool)
        or not isinstance(workers, int)
        or not 1 <= workers <= 128
    ):
        raise ValueError("CPU workers must be an integer from 1 to 128.")
    if backend not in ("auto", "native", "scipy"):
        raise ValueError("Backend must be auto, native or scipy.")
    data = np.ascontiguousarray(rows, dtype=np.float64)
    if backend == "native" and _omega_arpls is None:
        raise RuntimeError("The native omega-background extension is not installed.")
    if backend != "scipy" and _omega_arpls is not None:
        return _omega_arpls.baselines(
            data,
            parameters.smoothness,
            parameters.tolerance,
            parameters.max_iterations,
            workers,
        )
    return _scipy_baselines(data, parameters)


def _scipy_baselines(data, p):
    # Construct D.T @ D by accumulating each [1, -2, 1] row's outer
    # product directly into LAPACK's lower-band representation.
    n = data.shape[1]
    penalty = np.zeros((3, n))
    for j in range(n - 2):
        penalty[0, j : j + 3] += p.smoothness * np.array([1.0, 4.0, 1.0])
        penalty[1, j : j + 2] -= 2 * p.smoothness
        penalty[2, j] += p.smoothness
    result = np.empty_like(data)
    iterations = np.zeros(len(data), dtype=np.int32)
    converged = np.zeros(len(data), dtype=bool)
    for row_index, original in enumerate(data):
        offset = original[0]
        scale = np.max(np.abs(original - offset))
        if scale == 0:
            result[row_index] = original
            converged[row_index] = True
            continue
        y = (original - offset) / scale
        weights = np.ones(n)
        for iteration in range(p.max_iterations):
            band = penalty.copy()
            band[0] += weights
            z = solveh_banded(band, weights * y, lower=True, check_finite=False)
            iterations[row_index] = iteration + 1
            residual = y - z
            negative = residual[residual < 0]
            if negative.size < 2 or np.max(np.abs(residual)) < 1e-10:
                converged[row_index] = True
                break
            # Zero negative-residual variance is common for noiseless sparse
            # peaks. Use the limiting sharp transition, rather than returning
            # the initial symmetric smoother (which would absorb the peak).
            sigma = max(float(np.std(negative)), 1e-8)
            argument = 2 * (residual - (2 * sigma - negative.mean())) / sigma
            new_weights = np.maximum(expit(-np.clip(argument, -40, 40)), 1e-8)
            if (
                np.linalg.norm(new_weights - weights) / np.linalg.norm(weights)
                < p.tolerance
            ):
                converged[row_index] = True
                break
            weights = new_weights
        result[row_index] = z * scale + offset
    return result, iterations, converged
