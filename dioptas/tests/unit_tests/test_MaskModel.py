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
from math import cos, sin

import pytest
from qtpy import QtCore

from ...model.MaskModel import MaskModel

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')


@pytest.fixture
def mask_model():
    mask_model = MaskModel()
    mask_model.set_dimension((10, 10))
    return mask_model


def test_growing_masks(mask_model):
    mask_model._mask_data[4, 4] = 1
    mask_model._mask_data[0, 0] = 1
    mask_model._mask_data[0, 9] = 1
    mask_model._mask_data[9, 9] = 1
    mask_model._mask_data[9, 0] = 1

    mask_model.grow()

    # tests corners
    assert mask_model._mask_data[0, 1] == 1
    assert mask_model._mask_data[1, 1] == 1
    assert mask_model._mask_data[1, 0] == 1

    assert mask_model._mask_data[0, 8] == 1
    assert mask_model._mask_data[1, 8] == 1
    assert mask_model._mask_data[1, 9] == 1

    assert mask_model._mask_data[8, 0] == 1
    assert mask_model._mask_data[8, 1] == 1
    assert mask_model._mask_data[9, 1] == 1

    assert mask_model._mask_data[8, 8] == 1
    assert mask_model._mask_data[8, 9] == 1
    assert mask_model._mask_data[9, 8] == 1

    # tests center
    assert mask_model._mask_data[3, 3] == 1
    assert mask_model._mask_data[4, 3] == 1
    assert mask_model._mask_data[5, 3] == 1

    assert mask_model._mask_data[3, 5] == 1
    assert mask_model._mask_data[4, 5] == 1
    assert mask_model._mask_data[5, 5] == 1

    assert mask_model._mask_data[3, 4] == 1
    assert mask_model._mask_data[5, 4] == 1


def test_shrink_mask(mask_model):
    mask_model._mask_data[4, 4] = 1
    mask_model._mask_data[0, 0] = 1
    mask_model._mask_data[0, 9] = 1
    mask_model._mask_data[9, 9] = 1
    mask_model._mask_data[9, 0] = 1

    before_mask = np.copy(mask_model._mask_data)
    mask_model.grow()
    mask_model.shrink()

    assert np.array_equal(before_mask, mask_model._mask_data)

    mask_model.clear_mask()

    mask_model._mask_data[4, 4] = 1
    mask_model._mask_data[5, 4] = 1
    mask_model._mask_data[5, 5] = 1
    mask_model._mask_data[4, 5] = 1
    mask_model.shrink()

    assert np.sum(mask_model._mask_data) == 0


@pytest.mark.parametrize("flipud", [False, True])
@pytest.mark.parametrize("extension", [".mask", ".npy", ".edf"])
def test_saving_and_loading(mask_model, tmp_path, extension, flipud):
    mask_model.mask_ellipse(1024, 1024, 100, 100)
    mask_model.set_dimension((2048, 2048))

    mask_array = np.copy(mask_model.get_img())

    filename = os.path.join(tmp_path, f"dummy{extension}")

    mask_model.save_mask(filename, flipud)
    mask_model.load_mask(filename, flipud)

    assert np.array_equal(mask_array, mask_model.get_img())

    mask_model.load_mask(filename, not flipud)
    assert np.array_equal(mask_array, np.flipud(mask_model.get_img()))


def test_use_roi(mask_model):
    mask_model.roi = [0, 2, 0, 2]

    assert np.array_equal(mask_model.get_mask()[0:3, 0:3],
                          np.array([[0, 0, 1],
                                    [0, 0, 1],
                                    [1, 1, 1]]))


@pytest.mark.parametrize("extension", [".mask", ".npy", ".edf"])
def test_save_mask(mask_model, tmp_path, extension):
    mask_model.mask_below_threshold(np.zeros(shape=(10, 10)), 1)
    filename = os.path.join(tmp_path, f"test_save{extension}")
    mask_model.save_mask(filename)

    assert os.path.exists(filename)


def test_find_center_of_circle_from_three_points(mask_model):
    x0 = 2.0
    y0 = 3.5
    r = 1.2
    phi1 = 0.1
    phi2 = 1.3
    phi3 = 6.0
    p1 = QtCore.QPointF(x0 + r * cos(phi1), y0 + r * sin(phi1))
    p2 = QtCore.QPointF(x0 + r * cos(phi2), y0 + r * sin(phi2))
    p3 = QtCore.QPointF(x0 + r * cos(phi3), y0 + r * sin(phi3))
    mask_model.find_center_of_circle_from_three_points(p1, p2, p3)
    assert pytest.approx(x0) == mask_model.center_for_arc.x()
    assert pytest.approx(y0) == mask_model.center_for_arc.y()


def test_find_radius_of_circle_from_center_and_point(mask_model):
    x0 = 2.0
    y0 = 3.5
    p0 = QtCore.QPointF(x0, y0)
    r = 1.2
    phi1 = 0.1
    p1 = QtCore.QPointF(x0 + r * cos(phi1), y0 + r * sin(phi1))
    rcalc = mask_model.find_radius_of_circle_from_center_and_point(p0, p1)
    assert r == rcalc


def test_find_n_points_on_arc_from_three_points(mask_model):
    n = 50
    x0 = 2.0
    y0 = 3.5
    p0 = QtCore.QPointF(x0, y0)
    r = 1.2
    width = 0

    phi1 = 0.1
    phi2 = 1.3
    phi3 = -0.2
    p1 = QtCore.QPointF(x0 + r * cos(phi1), y0 + r * sin(phi1))
    p2 = QtCore.QPointF(x0 + r * cos(phi2), y0 + r * sin(phi2))
    p3 = QtCore.QPointF(x0 + r * cos(phi3), y0 + r * sin(phi3))

    n_angles = mask_model.find_n_angles_on_arc_from_three_points_around_p0(p0, p1, p2, p3, n)
    n_points = mask_model.calc_arc_points_from_angles(p0, r, width, n_angles)
    for p in n_points:
        rcalc = mask_model.find_radius_of_circle_from_center_and_point(p0, p)
        assert r == pytest.approx(rcalc, abs=1e-6)
