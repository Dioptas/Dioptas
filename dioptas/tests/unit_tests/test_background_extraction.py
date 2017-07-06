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
import numpy as np

from ...model.util import extract_background
from ...model.util.PeakShapes import gaussian


class TestBackgroundExtraction(unittest.TestCase):
    """
    Tests the Background extraction module in the model.util package
    """
    def test_simple_linear_background_with_single_peak(self):
        """
        Here we produce a Gaussian peak on a linear background, and test if the background subtraction algorithm
        can find the correct background.
        """

        # Gaussian
        x = np.linspace(0, 25, 2500)
        y_data = gaussian(x, 10, 3, 0.1)

        # linear background
        y_bkg = x * 0.4 + 5.0

        # combination
        y_measurement = y_data + y_bkg

        y_extracted_bkg = extract_background(x, y_measurement, 1)
        self.assertAlmostEqual(np.sum(y_data - (y_measurement - y_extracted_bkg)), 0)

    def test_simple_linear_background_with_multiple_peaks(self):
        """
        Here we produce several Gaussian peaks on top of a linear background and test if the background subtraction
        algorithm can find the correct background.
        """

        # produce peaks
        x = np.linspace(0, 24, 2500)
        y_data = np.zeros(x.shape)

        peaks = [
            [10, 3, 0.05],
            [12, 6, 0.05],
            [12, 9, 0.05],
        ]
        for peak in peaks:
            y_data += gaussian(x, peak[0], peak[1], peak[2])


        # linear background
        y_bkg = x * 0.4 + 5.0

        # combination
        y_measurement = y_data + y_bkg

        y_extracted_bkg = extract_background(x, y_measurement, 0.3)
        self.assertAlmostEqual(np.sum(y_data - (y_measurement - y_extracted_bkg)), 0)

    def test_simple_linear_background_with_multiple_close_peaks(self):
        """
        Here we produce several close overlapping peaks on top of a linear background and check whether the background
        algorithm finds the correct background
        """

        # produce peaks
        x = np.linspace(0, 24, 2500)
        y_data = np.zeros(x.shape)

        peaks = [
            [10, 3, 0.1],
            [12, 3.1, 0.1],
            [12, 3.4, 0.1],
        ]
        for peak in peaks:
            y_data += gaussian(x, peak[0], peak[1], peak[2])

        # background
        y_bkg = x * 0.4 + 5.0

        # combination
        y_measurement = y_data + y_bkg

        y_extracted_bkg = extract_background(x, y_measurement, 1)
        self.assertAlmostEqual(np.sum(y_data - (y_measurement - y_extracted_bkg)), 0)
