__author__ = 'Clemens Prescher'

import unittest
import os
import numpy as np
from numpy.testing import assert_array_almost_equal

from model.SpectrumModel import Pattern, SpectrumModel
from model.util.Pattern import BkgNotInRangeError
from model.util.PeakShapes import gaussian

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, 'data')

class SpectrumModelTest(unittest.TestCase):
    # TODO: needs to be rewritten to be more in small units etc.
    def setUp(self):
        self.x = np.linspace(0.1, 15, 100)
        self.y = np.sin(self.x)
        self.spectrum = Pattern(self.x, self.y)
        self.spectrum_model = SpectrumModel()

    def test_set_spectrum(self):
        self.spectrum_model.set_spectrum(self.x, self.y, 'hoho')
        assert_array_almost_equal(self.spectrum_model.get_spectrum().x, self.x)
        assert_array_almost_equal(self.spectrum_model.get_spectrum().y, self.y)
        self.assertEqual(self.spectrum_model.get_spectrum().name, 'hoho')

    def test_load_spectrum(self):
        self.spectrum_model.load_spectrum(os.path.join(data_path, 'spectrum_001.xy'))
        self.assertEqual(self.spectrum_model.get_spectrum().name, 'spectrum_001')
        self.assertNotEqual(len(self.x), len(self.spectrum_model.get_spectrum().x))
        self.assertNotEqual(len(self.y), len(self.spectrum_model.get_spectrum().y))

    def test_add_overlay(self):
        x_overlay = np.linspace(0, 10)
        y_overlay = np.linspace(0, 100)
        self.spectrum_model.add_overlay(x_overlay, y_overlay, "dummy")

        self.assertEqual(len(self.spectrum_model.overlays), 1)
        new_overlay = self.spectrum_model.get_overlay(0)
        self.assertEqual(new_overlay.name, "dummy")
        assert_array_almost_equal(new_overlay.x, x_overlay)
        assert_array_almost_equal(new_overlay.y, y_overlay)

    def test_add_overlay_from_file(self):
        filename = os.path.join(data_path, 'spectrum_001.xy')
        self.spectrum_model.add_overlay_file(filename)

        self.assertEqual(len(self.spectrum_model.overlays), 1)
        self.assertEqual(self.spectrum_model.get_overlay(0).name, ''.join(os.path.basename(filename).split('.')[0:-1]))

    def test_add_spectrum_as_overlay(self):
        self.spectrum_model.add_spectrum_as_overlay()
        self.assertEqual(len(self.spectrum_model.overlays), 1)


        assert_array_almost_equal(self.spectrum_model.get_overlay(0).x, self.spectrum_model.spectrum.x)
        assert_array_almost_equal(self.spectrum_model.get_overlay(0).y, self.spectrum_model.spectrum.y)


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