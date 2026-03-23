# SPDX-License-Identifier: MIT

import numpy as np


_HC_EV_M = 6.62607015e-34 * 299792458.0 / 1.602176634e-19  # h*c in eV·m


def wavelength_to_energy(wavelength_m: float) -> float:
    """Convert wavelength in meters to energy in eV."""
    return _HC_EV_M / wavelength_m


def energy_to_wavelength(energy_eV: float) -> float:
    """Convert energy in eV to wavelength in meters."""
    return _HC_EV_M / energy_eV


def calculate_mu(formula: str, energy_eV: float, density: float | None = None) -> float:
    """Calculate linear absorption coefficient using xraydb.

    Returns the linear absorption coefficient in 1/mm.
    """
    import xraydb

    kwargs = {}
    if density is not None:
        kwargs["density"] = density
    mu_per_cm = xraydb.material_mu(formula, energy_eV, **kwargs)
    return mu_per_cm / 10.0  # convert 1/cm to 1/mm


def convert_units(
    value: float | np.ndarray,
    wavelength: float,
    previous_unit: str,
    new_unit: str,
) -> float | np.ndarray | None:
    """Converts a value between units.

    Supported units: ``'2th_deg'``, ``'q_A^-1'``, ``'d_A'``.
    *wavelength* is in Angstrom.  Returns None if the unit is unknown.
    """
    if previous_unit == '2th_deg':
        tth = value
    elif previous_unit == 'q_A^-1':
        tth = np.arcsin(
            value * 1e10 * wavelength / (4 * np.pi)) * 360 / np.pi
    elif previous_unit == 'd_A':
        tth = 2 * np.arcsin(wavelength / (2 * value * 1e-10)) * 180 / np.pi
    else:
        tth = 0

    if new_unit == '2th_deg':
        res = tth
    elif new_unit == 'q_A^-1':
        res = 4 * np.pi * \
              np.sin(tth / 360 * np.pi) / \
              wavelength / 1e10
    elif new_unit == 'd_A':
        res = wavelength / (2 * np.sin(tth / 360 * np.pi)) * 1e10
    else:
        res = None
    return res


def supersample_image(img_data: np.ndarray, factor: int) -> np.ndarray:
    """Creates a supersampled array from *img_data*."""
    if factor > 1:
        img_data_supersampled = np.zeros((img_data.shape[0] * factor,
                                          img_data.shape[1] * factor))
        for row in range(factor):
            for col in range(factor):
                img_data_supersampled[row::factor, col::factor] = img_data

        return img_data_supersampled
    else:
        return img_data


def trim_trailing_zeros(
    x: np.ndarray, y: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Trims trailing zeros from a pattern."""
    y_trim = np.trim_zeros(y, 'b')
    x_trim = x[:len(y_trim)]

    return x_trim, y_trim
