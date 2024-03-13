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
import os
import numpy as np
import pytest
from pytest import approx

from xypattern.pattern import BkgNotInRangeError
from ...model.util import Pattern
from ...model.util.PeakShapes import gaussian

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, "../data")


def test_loading_chi_file():
    spec = Pattern()
    x, y = spec.data

    spec.load(os.path.join(data_path, "pattern_001.chi"))
    new_x, new_y = spec.data

    assert len(x) != len(new_x)
    assert len(y) != len(new_y)


def test_loading_invalid_file():
    pattern = Pattern()
    with pytest.raises(ValueError):
        pattern.load(os.path.join(data_path, "wrong_file_format.txt"))


def test_saving_a_file(tmp_path):
    x = np.linspace(-5, 5, 100)
    y = x**2
    pattern = Pattern(x, y)
    filename = os.path.join(tmp_path, "test.dat")
    pattern.save(filename)

    pattern2 = Pattern()
    pattern2.load(filename)

    pattern2_x, pattern2_y = pattern2.data
    assert pattern2_x == pytest.approx(x)
    assert pattern2_y == pytest.approx(y)


def test_plus_and_minus_operators():
    x = np.linspace(0, 10, 100)
    pattern1 = Pattern(x, np.sin(x))
    pattern2 = Pattern(x, np.sin(x))

    pattern3 = pattern1 + pattern2
    assert np.array_equal(pattern3.y, np.sin(x) * 2)
    assert np.array_equal(pattern2._original_y, np.sin(x) * 1)
    assert np.array_equal(pattern1._original_y, np.sin(x) * 1)

    pattern3 = pattern1 + pattern1
    assert np.array_equal(pattern3.y, np.sin(x) * 2)
    assert np.array_equal(pattern1._original_y, np.sin(x) * 1)
    assert np.array_equal(pattern1._original_y, np.sin(x) * 1)

    pattern3 = pattern2 - pattern1
    assert np.array_equal(pattern3.y, np.sin(x) * 0)
    assert np.array_equal(pattern2._original_y, np.sin(x) * 1)
    assert np.array_equal(pattern1._original_y, np.sin(x) * 1)

    pattern3 = pattern1 - pattern1
    assert np.array_equal(pattern3.y, np.sin(x) * 0)
    assert np.array_equal(pattern1._original_y, np.sin(x) * 1)
    assert np.array_equal(pattern1._original_y, np.sin(x) * 1)


def test_plus_and_minus_operators_with_different_shapes():
    x = np.linspace(0, 10, 1000)
    x2 = np.linspace(0, 12, 1300)
    pattern1 = Pattern(x, np.sin(x))
    pattern2 = Pattern(x2, np.sin(x2))

    pattern3 = pattern1 + pattern2
    assert pattern3.x == approx(pattern1._original_x)
    assert pattern3.y == approx(pattern1._original_y * 2, abs=1e-4)

    pattern3 = pattern1 + pattern1
    assert pattern3.y == approx(np.sin(x) * 2, abs=1e-4)

    pattern3 = pattern1 - pattern2
    assert pattern3.y == approx(np.sin(x) * 0, abs=1e-4)

    pattern3 = pattern1 - pattern1
    assert pattern3.y == approx(np.sin(x) * 0, abs=1e-4)


def test_multiply_with_scalar_operator():
    x = np.linspace(0, 10, 100)
    pattern = 2 * Pattern(x, np.sin(x))
    assert np.array_equal(pattern.y, np.sin(x) * 2)


def test_using_background_pattern():
    x = np.linspace(-5, 5, 100)
    pattern_y = x**2
    bkg_y = x

    spec = Pattern(x, pattern_y)
    background_pattern = Pattern(x, bkg_y)

    spec.background_pattern = background_pattern
    new_x, new_y = spec.data

    assert np.array_equal(new_x, x)
    assert np.array_equal(new_y, pattern_y - bkg_y)


def test_using_background_pattern_with_different_spacing():
    x = np.linspace(-5, 5, 100)
    pattern_y = x**2
    x_bkg = np.linspace(-5, 5, 99)
    bkg_y = x_bkg

    spec = Pattern(x, pattern_y)
    background_pattern = Pattern(x_bkg, bkg_y)

    spec.background_pattern = background_pattern
    new_x, new_y = spec.data

    assert np.array_equal(new_x, x)
    assert np.array_equal(new_y, pattern_y - x)


def test_background_out_of_range_throws_error():
    x1 = np.linspace(0, 10)
    x2 = np.linspace(-10, -1)

    spec = Pattern(x1, x1)
    background_pattern = Pattern(x2, x2)

    with pytest.raises(BkgNotInRangeError):
        spec.background_pattern = background_pattern


def test_automatic_background_subtraction():
    x = np.linspace(0, 24, 2500)
    y = np.zeros(x.shape)

    peaks = [
        [10, 3, 0.1],
        [12, 4, 0.1],
        [12, 6, 0.1],
    ]
    for peak in peaks:
        y += gaussian(x, peak[0], peak[1], peak[2])
    y_bkg = x * 0.4 + 5.0
    y_measurement = y + y_bkg

    pattern = Pattern(x, y_measurement)

    auto_background_subtraction_parameters = [2, 50, 50]
    pattern.set_auto_background_subtraction(auto_background_subtraction_parameters)

    x_spec, y_spec = pattern.data

    assert y_spec == approx(y, abs=1e-4)


def test_automatic_background_subtraction_with_roi():
    x = np.linspace(0, 24, 2500)
    y = np.zeros(x.shape)

    peaks = [
        [10, 3, 0.1],
        [12, 4, 0.1],
        [12, 6, 0.1],
    ]
    for peak in peaks:
        y += gaussian(x, peak[0], peak[1], peak[2])
    y_bkg = x * 0.4 + 5.0
    y_measurement = y + y_bkg

    roi = [1, 23]

    pattern = Pattern(x, y_measurement)

    auto_background_subtraction_parameters = [2, 50, 50]
    pattern.set_auto_background_subtraction(auto_background_subtraction_parameters, roi)

    x_spec, y_spec = pattern.data

    assert x_spec[0] > roi[0]
    assert x_spec[-1] < roi[1]


def test_setting_new_data():
    spec = Pattern()
    x = np.linspace(0, 10)
    y = np.sin(x)
    spec.data = x, y

    new_x, new_y = spec.data
    assert np.array_equal(new_x, x)
    assert np.array_equal(new_y, y)


def test_using_len():
    x = np.linspace(0, 10, 234)
    y = x**2
    spec = Pattern(x, y)

    assert len(spec) == 234
