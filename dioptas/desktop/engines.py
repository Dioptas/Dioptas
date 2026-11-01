# SPDX-License-Identifier: MIT
"""Replaceable calibration engines, independent of the desktop interface.

pyFAI is included with Dioptas. Dioptrin is an optional, separately installed
engine; importing or running this module does not require it.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Protocol

import numpy as np


class CalibrationEngine(Protocol):
    id: str
    label: str

    def find_peaks(
        self, calibration, image, x: float, y: float, ring: int
    ) -> np.ndarray: ...
    def fit(self, calibration, points: np.ndarray, calibrant_path: Path) -> float: ...


def available_engines():
    return [
        {"id": "pyfai", "label": "pyFAI", "available": True},
        {
            "id": "dioptrin",
            "label": "Dioptrin (optional)",
            "available": importlib.util.find_spec("dioptrin") is not None,
        },
    ]


class PyFAIEngine:
    id = "pyfai"
    label = "pyFAI"

    def find_peaks(self, calibration, image, x, y, ring):
        # The Qt controller also swaps image x/y into row/column here.
        return calibration.find_peaks_automatic(y, x, ring)

    def fit(self, calibration, points, calibrant_path):
        calibration.use_dioptrin = False
        if calibration.is_calibrated:
            calibration.pattern_geometry.wavelength = calibration.start_values[
                "wavelength"
            ]
            calibration.refine()
        else:
            calibration.calibrate()
        calibration.filename = ""
        return float(
            np.sqrt(calibration.pattern_geometry.chi2() / len(points)) * 180 / np.pi
        )


class DioptrinEngine:
    id = "dioptrin"
    label = "Dioptrin"

    def __init__(self):
        # Neither importing the GUI nor using pyFAI loads this dependency.
        try:
            import dioptrin
        except ImportError as exc:
            raise ValueError(
                "Install the optional engine: uv sync --python 3.13 --extra desktop --extra dioptrin"
            ) from exc
        for name in (
            "find_peaks_massif",
            "refine",
            "estimate_ring_center",
            "CalibrationPoints",
        ):
            if not hasattr(dioptrin, name):
                raise ValueError(
                    "This Dioptrin installation does not provide the required calibration API."
                )
        dioptrin.validate_license()
        self.native = dioptrin

    def find_peaks(self, calibration, image, x, y, ring):
        data = np.ascontiguousarray(image, dtype=np.float64)
        row = min(data.shape[0] - 1, int(round(y)))
        column = min(data.shape[1] - 1, int(round(x)))
        points = np.asarray(self.native.find_peaks_massif(data, (row, column)))
        if not len(points):
            # Mouse coordinates can land just outside the connected peak.
            # Retry at the measured local maximum, within five source pixels.
            bottom, left = max(0, row - 5), max(0, column - 5)
            patch = data[bottom : row + 6, left : column + 6]
            if np.any(np.isfinite(patch)):
                dr, dc = np.unravel_index(np.nanargmax(patch), patch.shape)
                points = np.asarray(
                    self.native.find_peaks_massif(
                        data, (bottom + int(dr), left + int(dc))
                    )
                )
        if len(points):
            calibration._append_peak_selection(points, ring)
        return points

    def fit(self, c, points, calibrant_path):
        if (
            c.distortion_spline_filename
            or not getattr(c.detector, "IS_FLAT", True)
            or not getattr(c.detector, "uniform_pixel", True)
        ):
            raise ValueError(
                "The optional native calibration adapter currently supports flat detectors with uniform pixels and no distortion spline. Use pyFAI for this detector."
            )
        native_points = self.native.CalibrationPoints()
        for row, column, ring in points:
            native_points.add(float(row), float(column), int(ring))
        calibrant = self.native.Calibrant.from_file(str(calibrant_path))
        if c.is_calibrated:
            start = c._get_poni_dict()
        else:
            center = self.native.estimate_ring_center(
                [(float(row), float(column)) for row, column, _ in points]
            )
            if center is None:
                raise ValueError(
                    "Could not estimate the ring center. Pick more positions around the rings."
                )
            start = {
                "pixel1": c.orig_pixel1,
                "pixel2": c.orig_pixel2,
                "distance": c.start_values["dist"],
                "poni1": (center[0] + 0.5) * c.orig_pixel1,
                "poni2": (center[1] + 0.5) * c.orig_pixel2,
                "rot1": 0.0,
                "rot2": 0.0,
                "rot3": 0.0,
            }
        start["wavelength"] = c.start_values["wavelength"]
        for key, value in c.fixed_values.items():
            start["distance" if key == "dist" else key] = value
        fixed = ([] if c.fit_wavelength else ["wavelength"]) + [
            "distance" if key == "dist" else key for key in c.fixed_values
        ]
        result = self.native.refine(
            start, native_points, calibrant, fix=fixed, loss="l2", max_iter=300
        )
        fitted = result.poni
        # Keep project, detector and PONI compatibility in the existing model.
        geometry = c.pattern_geometry.get_config()
        geometry.update(
            {
                key: fitted[key]
                for key in ("poni1", "poni2", "rot1", "rot2", "rot3", "wavelength")
            }
        )
        geometry["dist"] = fitted["distance"]
        c.set_pyFAI_config(geometry)
        c.pattern_geometry.data = points
        c._sync_calibration_params()
        c.calibration_name = "current"
        c.filename = ""
        return float(result.rms_rad * 180 / np.pi)


def make_engine(name: str) -> CalibrationEngine:
    if name == "pyfai":
        return PyFAIEngine()
    if name == "dioptrin":
        return DioptrinEngine()
    raise ValueError("Choose pyFAI or Dioptrin as the processing engine.")
