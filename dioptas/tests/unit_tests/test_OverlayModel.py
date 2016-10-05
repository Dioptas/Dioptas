import unittest
import os
import numpy as np
from numpy.testing import assert_array_almost_equal

from ...model.util import Pattern
from ...model.OverlayModel import OverlayModel

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')


class OverlayModelTest(unittest.TestCase):
    def setUp(self):
        self.x = np.linspace(0.1, 15, 100)
        self.y = np.sin(self.x)
        self.pattern = Pattern(self.x, self.y)
        self.overlay_model = OverlayModel()

    def test_add_overlay(self):
        x_overlay = np.linspace(0, 10)
        y_overlay = np.linspace(0, 100)
        self.overlay_model.add_overlay(x_overlay, y_overlay, "dummy")

        self.assertEqual(len(self.overlay_model.overlays), 1)
        new_overlay = self.overlay_model.get_overlay(0)
        self.assertEqual(new_overlay.name, "dummy")
        assert_array_almost_equal(new_overlay.x, x_overlay)
        assert_array_almost_equal(new_overlay.y, y_overlay)

    def test_add_overlay_from_file(self):
        filename = os.path.join(data_path, 'spectrum_001.xy')
        self.overlay_model.add_overlay_file(filename)

        self.assertEqual(len(self.overlay_model.overlays), 1)
        self.assertEqual(self.overlay_model.get_overlay(0).name, ''.join(os.path.basename(filename).split('.')[0:-1]))