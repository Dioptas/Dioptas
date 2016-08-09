import unittest
import os
import numpy as np
from numpy.testing import assert_array_almost_equal

from model.PatternModel import Pattern, PatternModel
from model.util.PeakShapes import gaussian

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')


class PatternModelTest(unittest.TestCase):
    # TODO: needs to be rewritten to be more in small units etc.
    def setUp(self):
        self.x = np.linspace(0.1, 15, 100)
        self.y = np.sin(self.x)
        self.pattern = Pattern(self.x, self.y)
        self.pattern_model = PatternModel()

    def test_set_spectrum(self):
        self.pattern_model.set_pattern(self.x, self.y, 'hoho')
        assert_array_almost_equal(self.pattern_model.get_pattern().x, self.x)
        assert_array_almost_equal(self.pattern_model.get_pattern().y, self.y)
        self.assertEqual(self.pattern_model.get_pattern().name, 'hoho')

    def test_load_spectrum(self):
        self.pattern_model.load_pattern(os.path.join(data_path, 'spectrum_001.xy'))
        self.assertEqual(self.pattern_model.get_pattern().name, 'spectrum_001')
        self.assertNotEqual(len(self.x), len(self.pattern_model.get_pattern().x))
        self.assertNotEqual(len(self.y), len(self.pattern_model.get_pattern().y))

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

        self.pattern_model.set_pattern(x, y_measurement)

        auto_background_subtraction_parameters = [2, 50, 50]
        self.pattern_model.set_auto_background_subtraction(auto_background_subtraction_parameters)

        x_spec, y_spec = self.pattern_model.pattern.data

        self.assertAlmostEqual(np.sum(y_spec - y), 0)


if __name__ == '__main__':
    unittest.main()
