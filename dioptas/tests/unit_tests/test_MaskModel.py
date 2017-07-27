# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2017  Clemens Prescher (clemens.prescher@gmail.com)
# Institute for Geology and Mineralogy, University of Cologne
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

import unittest
import gc
import os
import numpy as np
from math import sqrt, atan2, cos, sin
from qtpy import QtCore

from ...model.MaskModel import MaskModel

from ..utility import delete_if_exists

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')


class MaskModelTest(unittest.TestCase):
    def setUp(self):
        self.mask_model = MaskModel()
        self.img = np.zeros((10, 10))
        self.mask_model.set_dimension(self.img.shape)

    def tearDown(self):
        delete_if_exists(os.path.join(data_path, "test_save.mask"))
        del self.mask_model
        del self.img
        gc.collect()

    def test_growing_masks(self):
        self.mask_model._mask_data[4, 4] = 1
        self.mask_model._mask_data[0, 0] = 1
        self.mask_model._mask_data[0, 9] = 1
        self.mask_model._mask_data[9, 9] = 1
        self.mask_model._mask_data[9, 0] = 1

        self.mask_model.grow()

        # tests corners
        self.assertEqual(self.mask_model._mask_data[0, 1], 1)
        self.assertEqual(self.mask_model._mask_data[1, 1], 1)
        self.assertEqual(self.mask_model._mask_data[1, 0], 1)

        self.assertEqual(self.mask_model._mask_data[0, 8], 1)
        self.assertEqual(self.mask_model._mask_data[1, 8], 1)
        self.assertEqual(self.mask_model._mask_data[1, 9], 1)

        self.assertEqual(self.mask_model._mask_data[8, 0], 1)
        self.assertEqual(self.mask_model._mask_data[8, 1], 1)
        self.assertEqual(self.mask_model._mask_data[9, 1], 1)

        self.assertEqual(self.mask_model._mask_data[8, 8], 1)
        self.assertEqual(self.mask_model._mask_data[8, 9], 1)
        self.assertEqual(self.mask_model._mask_data[9, 8], 1)

        # tests center
        self.assertEqual(self.mask_model._mask_data[3, 3], 1)
        self.assertEqual(self.mask_model._mask_data[4, 3], 1)
        self.assertEqual(self.mask_model._mask_data[5, 3], 1)

        self.assertEqual(self.mask_model._mask_data[3, 5], 1)
        self.assertEqual(self.mask_model._mask_data[4, 5], 1)
        self.assertEqual(self.mask_model._mask_data[5, 5], 1)

        self.assertEqual(self.mask_model._mask_data[3, 4], 1)
        self.assertEqual(self.mask_model._mask_data[5, 4], 1)

    def test_shrink_mask(self):
        self.mask_model._mask_data[4, 4] = 1
        self.mask_model._mask_data[0, 0] = 1
        self.mask_model._mask_data[0, 9] = 1
        self.mask_model._mask_data[9, 9] = 1
        self.mask_model._mask_data[9, 0] = 1

        self.before_mask = np.copy(self.mask_model._mask_data)
        self.mask_model.grow()
        self.mask_model.shrink()

        self.assertTrue(np.array_equal(self.before_mask, self.mask_model._mask_data))

        self.mask_model.clear_mask()

        self.mask_model._mask_data[4, 4] = 1
        self.mask_model._mask_data[5, 4] = 1
        self.mask_model._mask_data[5, 5] = 1
        self.mask_model._mask_data[4, 5] = 1
        self.mask_model.shrink()

        self.assertEqual(np.sum(self.mask_model._mask_data), 0)

    def test_saving_and_loading(self):
        self.mask_model.mask_ellipse(1024, 1024, 100, 100)
        self.mask_model.set_dimension((2048, 2048))

        mask_array = np.copy(self.mask_model.get_img())

        filename = os.path.join(data_path, 'dummy.mask')

        self.mask_model.save_mask(filename)
        self.mask_model.load_mask(filename)

        self.assertTrue(np.array_equal(mask_array, self.mask_model.get_img()))
        os.remove(filename)

    def test_use_roi(self):
        self.mask_model.roi = [0, 2, 0, 2]

        self.assertTrue(np.array_equal(self.mask_model.get_mask()[0:3, 0:3],
                                       np.array([[0, 0, 1],
                                                 [0, 0, 1],
                                                 [1, 1, 1]]))
                        )

    def test_use_roi_with_supersampling(self):
        self.mask_model.roi = [0, 2, 0, 2]
        self.mask_model.set_supersampling(2)
        self.assertTrue(np.array_equal(self.mask_model.get_mask()[0:6, 0:6],
                                       np.array([[0, 0, 0, 0, 1, 1],
                                                 [0, 0, 0, 0, 1, 1],
                                                 [0, 0, 0, 0, 1, 1],
                                                 [0, 0, 0, 0, 1, 1],
                                                 [1, 1, 1, 1, 1, 1],
                                                 [1, 1, 1, 1, 1, 1]]))
                        )

    def test_save_mask(self):
        self.mask_model.mask_below_threshold(self.img, 1)
        self.mask_model.save_mask(os.path.join(data_path, "test_save.mask"))

        self.assertTrue(os.path.exists(os.path.join(data_path, "test_save.mask")))

    def test_find_center_of_circle_from_three_points(self):
        x0 = 2.0
        y0 = 3.5
        r = 1.2
        phi1 = 0.1
        phi2 = 1.3
        phi3 = 6.0
        p1 = QtCore.QPointF(x0 + r * cos(phi1), y0 + r * sin(phi1))
        p2 = QtCore.QPointF(x0 + r * cos(phi2), y0 + r * sin(phi2))
        p3 = QtCore.QPointF(x0 + r * cos(phi3), y0 + r * sin(phi3))
        # p1 = (x0 + r * cos(phi1), y0 + r * sin(phi1))
        # p2 = (x0 + r * cos(phi2), y0 + r * sin(phi2))
        # p3 = (x0 + r * cos(phi3), y0 + r * sin(phi3))
        self.mask_model.find_center_of_circle_from_three_points(p1, p2, p3)
        self.assertAlmostEqual(x0, self.mask_model.center_for_arc.x(), 6)
        self.assertAlmostEqual(y0, self.mask_model.center_for_arc.y(), 6)

    def test_find_radius_of_circle_from_center_and_point(self):
        x0 = 2.0
        y0 = 3.5
        p0 = QtCore.QPointF(x0, y0)
        r = 1.2
        phi1 = 0.1
        p1 = QtCore.QPointF(x0 + r * cos(phi1), y0 + r * sin(phi1))
        rcalc = self.mask_model.find_radius_of_circle_from_center_and_point(p0, p1)
        self.assertEqual(r, rcalc)

    def test_find_n_points_on_arc_from_three_points(self):
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

        n_angles = self.mask_model.find_n_angles_on_arc_from_three_points_around_p0(p0, p1, p2, p3, n)
        n_points = self.mask_model.calc_arc_points_from_angles(p0, r, width, n_angles)
        for p in n_points:
            rcalc = self.mask_model.find_radius_of_circle_from_center_and_point(p0, p)
            self.assertAlmostEqual(r, rcalc, 5)
