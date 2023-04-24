# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
# Principal author: Clemens Prescher (clemens.prescher@gmail.com)
# Copyright (C) 2014-2019 GSECARS, University of Chicago, USA
# Copyright (C) 2015-2018 Institute for Geology and Mineralogy, University of Cologne, Germany
# Copyright (C) 2019-2020 DESY, Hamburg, Germany
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
from pytest import approx

from ...model.util import extract_background
from ...model.util.PeakShapes import gaussian


def test_simple_linear_background_with_single_peak():
    """ We produce a Gaussian peak on a linear background, and test if the background subtraction algorithm
    can find the correct background.
    """

    peaks = [[10, 3, 0.1]]

    x, y_data, y_bkg = generate_pattern(peaks)

    # combination
    y_measurement = y_data + y_bkg

    y_extracted_bkg = extract_background(x, y_measurement, 1)
    assert np.sum(y_data - (y_measurement - y_extracted_bkg)) == approx(0, abs=1e-7)


def test_simple_linear_background_with_multiple_peaks():
    """ We produce several Gaussian peaks on top of a linear background and test if the background subtraction
    algorithm can find the correct background.
    """
    peaks = [
        [10, 3, 0.05],
        [12, 6, 0.05],
        [12, 9, 0.05],
    ]

    x, y_data, y_bkg = generate_pattern(peaks)

    # combination
    y_measurement = y_data + y_bkg

    y_extracted_bkg = extract_background(x, y_measurement, 0.3)
    assert np.sum(y_data - (y_measurement - y_extracted_bkg)) == approx(0, abs=1e-7)


def test_simple_linear_background_with_multiple_close_peaks():
    """ We produce several close overlapping peaks on top of a linear background and check whether the background
    algorithm finds the correct background
    """

    peaks = [
        [10, 3, 0.1],
        [12, 3.1, 0.1],
        [12, 3.4, 0.1],
    ]
    x, y_data, y_bkg = generate_pattern(peaks)

    # combination
    y_measurement = y_data + y_bkg

    y_extracted_bkg = extract_background(x, y_measurement, 1)
    assert np.sum(y_data - (y_measurement - y_extracted_bkg)) == approx(0, abs=1e-7)


def generate_pattern(peaks):
    """ Generates a pattern with the given peaks. Peaks is a list of lists, where each list contains the
    parameters of a single peak. The parameters are [position, width, intensity]
    """
    x = np.linspace(0, 24, 2500)
    y_data = np.zeros(x.shape)

    for peak in peaks:
        y_data += gaussian(x, peak[0], peak[1], peak[2])

    y_bkg = x * 0.4 + 5.0

    return x, y_data, y_bkg
