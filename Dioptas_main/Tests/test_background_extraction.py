# -*- coding: utf8 -*-
__author__ = 'Clemens Prescher'

import unittest
import numpy as np

from Data.Helper import extract_background
from Data.Helper.PeakShapes import gaussian


class TestBackgroundExtraction(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_simple_linear_background_with_single_peak(self):
        x = np.linspace(0, 25, 2500)
        y_data = gaussian(x, 10, 3, 0.1)
        y_bkg = x * 0.4 + 5.0
        y_measurement = y_data + y_bkg

        y_extracted_bkg = extract_background(x, y_measurement, 1)
        self.assertAlmostEqual(np.sum(y_data - (y_measurement - y_extracted_bkg)), 0)

    def test_simple_linear_background_with_multiple_peaks(self):
        x = np.linspace(0, 24, 2500)
        y_data = np.zeros(x.shape)

        peaks = [
            [10, 3, 0.05],
            [12, 6, 0.05],
            [12, 9, 0.05],
        ]
        for peak in peaks:
            y_data += gaussian(x, peak[0], peak[1], peak[2])

        y_bkg = x * 0.4 + 5.0
        y_measurement = y_data + y_bkg

        y_extracted_bkg = extract_background(x, y_measurement, 0.3)
        self.assertAlmostEqual(np.sum(y_data - (y_measurement - y_extracted_bkg)), 0)

    def test_simple_linear_background_with_multiple_close_peaks(self):

        x = np.linspace(0, 24, 2500)
        y_data = np.zeros(x.shape)

        peaks = [
            [10, 3, 0.1],
            [12, 3.1, 0.1],
            [12, 3.4, 0.1],
        ]
        for peak in peaks:
            y_data += gaussian(x, peak[0], peak[1], peak[2])

        y_bkg = x * 0.4 + 5.0
        y_measurement = y_data + y_bkg

        y_extracted_bkg = extract_background(x, y_measurement, 1)
        self.assertAlmostEqual(np.sum(y_data - (y_measurement - y_extracted_bkg)), 0)

