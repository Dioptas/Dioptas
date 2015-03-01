__author__ = 'Clemens Prescher'

import unittest
import os
import numpy as np

from model.SpectrumModel import Spectrum, SpectrumModel
from model.Helper.Spectrum import BkgNotInRangeError
from model.Helper.PeakShapes import gaussian

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, 'data')

class SpectrumDataTest(unittest.TestCase):
    # TODO: needs to be rewritten to be more in small units etc.
    def setUp(self):
        self.x = np.linspace(0.1, 15, 100)
        self.y = np.sin(self.x)
        self.spectrum = Spectrum(self.x, self.y)
        self.spectrum_model = SpectrumModel()

    def test_auto_background_subtraction(self):
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

        self.spectrum_model.set_spectrum(x, y_measurement)

        auto_background_subtraction_parameters = [2, 50, 50]
        self.spectrum_model.set_auto_background_subtraction(auto_background_subtraction_parameters)

        x_spec, y_spec = self.spectrum_model.spectrum.data

        self.assertAlmostEqual(np.sum(y_spec- y),0)


if __name__ == '__main__':
    unittest.main()