# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
# Principal author: Clemens Prescher (clemens.prescher@gmail.com)
# Copyright (C) 2014-2019 GSECARS, University of Chicago, USA
# Copyright (C) 2015-2018 Institute for Geology and Mineralogy, University of Cologne, Germany
# Copyright (C) 2019 DESY, Hamburg, Germany
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import numpy as np


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
