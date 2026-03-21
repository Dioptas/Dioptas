# SPDX-License-Identifier: MIT

import numpy as np


_HC_EV_M = 6.62607015e-34 * 299792458.0 / 1.602176634e-19  # h*c in eV·m


def wavelength_to_energy(wavelength_m):
    """Convert wavelength in meters to energy in eV.

    :param wavelength_m: wavelength in meters
    :returns: energy in eV
    """
    return _HC_EV_M / wavelength_m


def energy_to_wavelength(energy_eV):
    """Convert energy in eV to wavelength in meters.

    :param energy_eV: energy in eV
    :returns: wavelength in meters
    """
    return _HC_EV_M / energy_eV


def calculate_mu(formula, energy_eV, density=None):
    """Calculate linear absorption coefficient using xraydb.

    :param formula: chemical formula string (e.g. 'CeO2', 'Au', 'Fe2O3')
    :param energy_eV: X-ray energy in eV
    :param density: material density in g/cm³. If None, xraydb uses
        its built-in density for known materials.
    :returns: linear absorption coefficient in 1/mm
    """
    import xraydb

    kwargs = {}
    if density is not None:
        kwargs["density"] = density
    mu_per_cm = xraydb.material_mu(formula, energy_eV, **kwargs)
    return mu_per_cm / 10.0  # convert 1/cm to 1/mm


def convert_units(value, wavelength, previous_unit, new_unit):
    """
    Converts a value from a unit into a new unit
    :param value: value in old unit
    :param wavelength: in Angstrom
    :param previous_unit: possible values are '2th_deg', 'q_A^-1', 'd_A'
    :param new_unit: possible values are '2th_deg', 'q_A^-1', 'd_A'
    :return: new value or None if unit does not exist
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


def supersample_image(img_data, factor):
    """
    Creates a supersampled array from img_data.
    :param img_data: image array
    :param factor: int - supersampling factor
    :return: supersampled image
    """
    if factor > 1:
        img_data_supersampled = np.zeros((img_data.shape[0] * factor,
                                          img_data.shape[1] * factor))
        for row in range(factor):
            for col in range(factor):
                img_data_supersampled[row::factor, col::factor] = img_data

        return img_data_supersampled
    else:
        return img_data


def trim_trailing_zeros(x, y):
    """
    Trims the trailing zeros of a x, y pattern
    :param x: x-values
    :param y: y-values
    :return: trimmed x, y values as tuple (x, y)
    """

    y_trim = np.trim_zeros(y, 'b')
    x_trim = x[:len(y_trim)]

    return x_trim, y_trim
