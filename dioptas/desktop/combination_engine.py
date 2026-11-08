# SPDX-License-Identifier: MIT
"""Adapter to Dioptrin's shared-grid multi-detector integration API.

All accumulation, splitting, masks and normalization remain in Dioptrin. The
one-azimuth-bin call also gives a correctly weighted combined radial pattern;
legacy MultiIntegrator.integrate1d has a different normalization contract.
"""

import hashlib
import numpy as np


def native_combination_key(configurations, unit, polarization):
    entries = []
    radial_low, radial_high = np.inf, -np.inf
    azimuth_low, azimuth_high = np.inf, -np.inf
    masks = []
    for c in configurations:
        calibration = c.calibration_model
        geometry = calibration.pattern_geometry
        shape = c.img_model.raw_img_data.shape
        radial = geometry.array_from_unit(shape=shape, unit=unit)
        azimuth = geometry.chiArray(shape)
        radial_low = min(radial_low, float(radial.min()))
        radial_high = max(radial_high, float(radial.max()))
        azimuth_low = min(azimuth_low, float(azimuth.min()))
        azimuth_high = max(azimuth_high, float(azimuth.max()))
        mask = (
            c.mask_model.get_mask()
            if c.use_mask
            else c.mask_model.roi_mask
            if c.mask_model.roi is not None
            else None
        )
        mask = np.ascontiguousarray(mask, dtype=np.uint8) if mask is not None else None
        masks.append(mask)
        entries.append(
            (
                tuple(sorted(calibration._get_poni_dict().items())),
                shape,
                hashlib.sha256(mask.tobytes()).digest() if mask is not None else None,
            )
        )
    # pyFAI expands its upper radial edge by float32 epsilon internally.
    radial_range = (max(0.0, radial_low), radial_high * (1 + np.finfo(np.float32).eps))
    azimuth_range = (
        azimuth_low,
        min(np.pi, azimuth_high + abs(azimuth_high) * np.finfo(np.float32).eps),
    )
    return (
        (unit, polarization, radial_range, tuple(entries)),
        masks,
        radial_range,
        azimuth_range,
    )


def native_unavailable(configurations, selected):
    if not selected.calibration_model.correct_solid_angle:
        return "solid-angle correction is disabled"
    for c in configurations:
        calibration = c.calibration_model
        if (
            calibration.distortion_spline_filename
            or not getattr(calibration.detector, "IS_FLAT", True)
            or not getattr(calibration.detector, "uniform_pixel", True)
        ):
            return "a detector requires its full pyFAI geometry"
        if calibration.supersampling_factor != 1:
            return "detector supersampling is enabled"
    try:
        import dioptrin
    except ImportError:
        return "Dioptrin is not installed"
    if not hasattr(getattr(dioptrin, "MultiIntegrator", None), "integrate2d"):
        return "the installed Dioptrin has no shared-grid 2D API"
    return None


def make_native_multi(
    configurations, unit, polarization, masks, radial_range, *, method="pixel_split"
):
    import dioptrin

    integrators = []
    for c, mask in zip(configurations, masks):
        integrator = dioptrin.Integrator.from_poni_dict(
            c.calibration_model._get_poni_dict(),
            method=method,
            unit=unit,
            radial_range=radial_range,
            polarization_factor=polarization,
        )
        integrator.set_mask(mask)
        integrators.append(integrator)
    return dioptrin.MultiIntegrator(integrators)
