import numpy as np

from ..utility import QtTest
from ...model.util.calc import trim_trailing_zeros


class HelperModuleTest(QtTest):
    def test_trim_trailing_zeros(self):
        x = np.linspace(0, 20)
        y = np.ones_like(x)
        y[-10:] = 0

        x_trim, y_trim = trim_trailing_zeros(x, y)

        self.assertEqual(len(y_trim), len(y)-10)
        self.assertEqual(len(x_trim), len(y)-10)
