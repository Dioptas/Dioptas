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

import unittest
import os

import numpy as np

from ...model.util.Pattern import BkgNotInRangeError
from ...model.util import Pattern
from ...model.util.PeakShapes import gaussian

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')


class PatternTest(unittest.TestCase):
    def array_almost_equal(self, array1, array2, places=7):
        self.assertAlmostEqual(np.sum(array1 - array2), 0, places=places)

    def array_not_almost_equal(self, array1, array2, places=7):
        self.assertNotAlmostEqual(np.sum(array1 - array2), 0, places=places)

    def test_loading_chi_file(self):
        spec = Pattern()
        x, y = spec.data

        spec.load(os.path.join(data_path, 'pattern_001.chi'))
        new_x, new_y = spec.data

        self.assertNotEqual(len(x), len(new_x))
        self.assertNotEqual(len(y), len(new_y))

    def test_loading_invalid_file(self):
        spec = Pattern()
        self.assertEqual(-1, spec.load(os.path.join(data_path, 'wrong_file_format.txt')))

    def test_saving_a_file(self):
        x = np.linspace(-5, 5, 100)
        y = x ** 2
        spec = Pattern(x, y)
        filename = os.path.join(data_path, "test.dat")
        spec.save(filename)

        spec2 = Pattern()
        spec2.load(filename)

        spec2_x, spec2_y = spec2.data
        self.array_almost_equal(spec2_x, x)
        self.array_almost_equal(spec2_y, y)

        os.remove(filename)

    def test_plus_and_minus_operators(self):
        x = np.linspace(0, 10, 100)
        pattern1 = Pattern(x, np.sin(x))
        pattern2 = Pattern(x, np.sin(x))

        pattern3 = pattern1 + pattern2
        self.assertTrue(np.array_equal(pattern3.y, np.sin(x) * 2))
        self.assertTrue(np.array_equal(pattern2.original_y, np.sin(x) * 1))
        self.assertTrue(np.array_equal(pattern1.original_y, np.sin(x) * 1))

        pattern3 = pattern1 + pattern1
        self.assertTrue(np.array_equal(pattern3.y, np.sin(x) * 2))
        self.assertTrue(np.array_equal(pattern1.original_y, np.sin(x) * 1))
        self.assertTrue(np.array_equal(pattern1.original_y, np.sin(x) * 1))

        pattern3 = pattern2 - pattern1
        self.assertTrue(np.array_equal(pattern3.y, np.sin(x) * 0))
        self.assertTrue(np.array_equal(pattern2.original_y, np.sin(x) * 1))
        self.assertTrue(np.array_equal(pattern1.original_y, np.sin(x) * 1))

        pattern3 = pattern1 - pattern1
        self.assertTrue(np.array_equal(pattern3.y, np.sin(x) * 0))
        self.assertTrue(np.array_equal(pattern1.original_y, np.sin(x) * 1))
        self.assertTrue(np.array_equal(pattern1.original_y, np.sin(x) * 1))

    def test_plus_and_minus_operators_with_different_shapes(self):
        x = np.linspace(0, 10, 1000)
        x2 = np.linspace(0, 12, 1300)
        pattern1 = Pattern(x, np.sin(x))
        pattern2 = Pattern(x2, np.sin(x2))

        pattern3 = pattern1 + pattern2
        self.array_almost_equal(pattern3.x, pattern1._original_x)
        self.array_almost_equal(pattern3.y, pattern1._original_y * 2, 2)

        pattern3 = pattern1 + pattern1
        self.array_almost_equal(pattern3.y, np.sin(x) * 2, 2)

        pattern3 = pattern1 - pattern2
        self.array_almost_equal(pattern3.y, np.sin(x) * 0, 2)

        pattern3 = pattern1 - pattern1
        self.array_almost_equal(pattern3.y, np.sin(x) * 0, 2)

    def test_multiply_with_scalar_operator(self):
        x = np.linspace(0, 10, 100)
        pattern1 = 2 * Pattern(x, np.sin(x))

        pattern2 = 2 * Pattern(x, np.sin(x))

        self.assertTrue(np.array_equal(pattern2.y, np.sin(x) * 2))

    def test_using_background_pattern(self):
        x = np.linspace(-5, 5, 100)
        pattern_y = x ** 2
        bkg_y = x

        spec = Pattern(x, pattern_y)
        background_pattern = Pattern(x, bkg_y)

        spec.background_pattern = background_pattern
        new_x, new_y = spec.data

        self.array_almost_equal(new_x, x)
        self.array_almost_equal(new_y, pattern_y - bkg_y)

    def test_using_background_pattern_with_different_spacing(self):
        x = np.linspace(-5, 5, 100)
        pattern_y = x ** 2
        x_bkg = np.linspace(-5, 5, 99)
        bkg_y = x_bkg

        spec = Pattern(x, pattern_y)
        background_pattern = Pattern(x_bkg, bkg_y)

        spec.background_pattern = background_pattern
        new_x, new_y = spec.data

        self.array_almost_equal(new_x, x)
        self.array_almost_equal(new_y, pattern_y - x)

    def test_background_out_of_range_throws_error(self):
        x1 = np.linspace(0, 10)
        x2 = np.linspace(-10, -1)

        spec = Pattern(x1, x1)
        background_pattern = Pattern(x2, x2)

        with self.assertRaises(BkgNotInRangeError):
            spec.background_pattern = background_pattern

    def test_automatic_background_subtraction(self):
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

        self.array_almost_equal(y_spec, y)

    def test_automatic_background_subtraction_with_roi(self):
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

        self.assertGreater(x_spec[0], roi[0])
        self.assertLess(x_spec[-1], roi[1])

        # self.array_almost_equal(y_spec, y)

    def test_setting_new_data(self):
        spec = Pattern()
        x = np.linspace(0, 10)
        y = np.sin(x)
        spec.data = x, y

        new_x, new_y = spec.data
        self.array_almost_equal(new_x, x)
        self.array_almost_equal(new_y, y)

    def test_using_len(self):
        x = np.linspace(0, 10, 234)
        y = x ** 2
        spec = Pattern(x, y)

        self.assertEqual(len(spec), 234)


if __name__ == '__main__':
    unittest.main()
