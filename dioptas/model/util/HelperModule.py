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


import os
import re
import time

import numpy as np
from qtpy import QtCore
from colorsys import hsv_to_rgb




def rotate_matrix_m90(matrix):
    return np.rot90(matrix, -1)


def rotate_matrix_p90(matrix):
    return np.rot90(matrix)


def get_base_name(filename):
    str = os.path.basename(filename)
    if '.' in str:
        str = str.split('.')[:-1][0]
    return str


def calculate_color(ind):
    s = 0.8
    v = 0.8
    h = (0.19 * (ind + 2)) % 1
    return np.array(hsv_to_rgb(h, s, v)) * 255


def convert_d_to_two_theta(d, wavelength):
    return np.arcsin(wavelength / (2 * d)) / np.pi * 360


def get_partial_index(array, value):
    """
    Calculates the partial index for a value from an array using linear interpolation.
    e.g. with array = [0,1,2,3,4,5] and value = 2.5 it would return 2.5, since it in between the second and third
    element.
    :param array: list or numpy array
    :param value: value for which to get the index
    :return: partial index
    """
    try:
        upper_ind = np.where(array >= value)[0]
        lower_ind = np.where(array < value)[0]
    except TypeError:
        return None

    try:
        spacing = array[upper_ind[0]] - array[lower_ind[-1]]
        new_pos = lower_ind[-1] + (value - array[lower_ind[-1]]) / spacing
    except IndexError:
        return None

    return new_pos


def get_partial_value(array, ind):
    """
    Calculates the value for a non-integer array from an array using linear interpolation.
    e.g. with array = [0,2,4,6,8,10] and value = 2.5 it would return 5, since it is in between the second and third
    element.
    :param array: list or numpy array
    :param ind: float index for which to get value
    """
    step = array[int(np.floor(ind)) + 1] - array[int(np.floor(ind))]
    value = array[int(np.floor(ind))] + (ind - np.floor(ind)) * step
    return value


def reverse_interpolate_two_array(value1, array1, value2, array2, delta1=0.1, delta2=0.1):
    """
    Tries to reverse interpolate two vales from two arrays with the same dimensions, and finds a common index
    for value1 and value2 in their respective arrays. the deltas define the search radius for a close value match
    to the arrays.

    :return: index1, index2
    """
    tth_ind = np.argwhere(np.abs(array1 - value1) < delta1)
    azi_ind = np.argwhere(np.abs(array2 - value2) < delta2)

    tth_ind_ravel = np.ravel_multi_index((tth_ind[:, 0], tth_ind[:, 1]), dims=array1.shape)
    azi_ind_ravel = np.ravel_multi_index((azi_ind[:, 0], azi_ind[:, 1]), dims=array2.shape)

    common_ind_ravel = np.intersect1d(tth_ind_ravel, azi_ind_ravel)
    result_ind = np.unravel_index(common_ind_ravel, dims=array1.shape)

    while len(result_ind[0]) > 1:
        if np.max(np.diff(array1)) > 0:
            delta1 = np.max(np.diff(array1[result_ind]))

        if np.max(np.diff(array2)) > 0:
            delta2 = np.max(np.diff(array2[result_ind]))

        tth_ind = np.argwhere(np.abs(array1[result_ind] - value1) < delta1)
        azi_ind = np.argwhere(np.abs(array2[result_ind] - value2) < delta2)

        print(result_ind)

        common_ind = np.intersect1d(tth_ind, azi_ind)
        result_ind = (result_ind[0][common_ind], result_ind[1][common_ind])

    return result_ind[0], result_ind[1]
