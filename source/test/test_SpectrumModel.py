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

    def test_spectrum_class(self):
        self.spectrum.save(os.path.join(data_path, 'spec_test.txt'))
        self.spectrum.save(os.path.join(data_path, 'spec_test2.txt'),
                           header='This is not only ridiculous\n but more and more '
                                  'challenging...')
        self.spectrum.load(os.path.join(data_path, 'spec_test.txt'), 0)
        self.spectrum.load(os.path.join(data_path, 'spec_test2.txt'), 0)

        self.assertTrue(np.array_equal(self.spectrum.data[0], np.linspace(0.1, 15, 100)))
        self.assertTrue(self.spectrum.load(os.path.join(data_path, 'image_001.tif')) == -1)

        self.spectrum.data = (np.linspace(0, 30), np.linspace(0, 20))
        self.spectrum.offset = 100
        self.assertTrue(np.array_equal(self.spectrum.data[1], np.linspace(0, 20) + 100))
        self.assertTrue(np.array_equal(self.spectrum.data[0], np.linspace(0, 30)))

        self.spectrum.scaling = 10
        self.assertTrue(np.array_equal(self.spectrum.data[1], np.linspace(0, 20) * 10 + 100))

        self.spectrum.data = (np.linspace(0, 20), np.linspace(0, 30))
        self.assertTrue(np.array_equal(self.spectrum.data[1], np.linspace(0, 30)))

        self.spectrum.scaling = -100
        self.assertTrue(np.array_equal(self.spectrum.data[1], np.zeros(self.spectrum.data[0].shape)))

        os.remove(os.path.join(data_path, 'spec_test.txt'))
        os.remove(os.path.join(data_path, 'spec_test2.txt'))

    def test_spectrum_data_class(self):
        self.spectrum_model.set_spectrum(np.linspace(0, 10), np.linspace(0, 10) ** 2, 'SQUARED')
        self.spectrum_model.add_overlay(np.linspace(0, 10), np.linspace(0, 10) ** 3, 'CUBED')
        self.spectrum_model.add_overlay(np.linspace(0, 10), np.linspace(0, 10) ** 4, 'QUADRUPOLED')

        self.assertTrue(len(self.spectrum_model.overlays) == 2)
        self.spectrum_model.remove_overlay(0)
        self.assertTrue(self.spectrum_model.overlays[0].name == 'QUADRUPOLED')

        self.spectrum_model.add_overlay_file(os.path.join(data_path, 'spectrum_001.xy'))
        self.assertEqual(self.spectrum_model.overlays[-1].name, 'spectrum_001')

    def test_background_spectrum(self):
        x_spectrum = np.linspace(0,100,1001)
        y_spectrum = np.sin(x_spectrum)
        x_background = np.linspace(0,91, 1002)
        y_background = np.cos(x_background)

        spec = Spectrum(x_spectrum, y_spectrum)
        spec.background_spectrum = Spectrum(x_background, y_background)

        x, y = spec.data

        self.assertTrue(x[-1]<1000)
        self.assertEqual(len(x), 911)

        test_x = np.linspace(0,91, 911)
        test_y = np.sin(test_x) - np.cos(test_x)

        diff = abs(np.sum(test_y-y))
        self.assertLess(diff, 1e-3)

    def test_background_spectrum_not_in_spectrum_range(self):
        x_spectrum = np.linspace(0,30,101)
        y_spectrum = np.sin(x_spectrum)
        x_background = np.linspace(50,60, 102)
        y_background = np.cos(x_background)

        spec = Spectrum(x_spectrum, y_spectrum)

        with self.assertRaises(BkgNotInRangeError):
            spec.background_spectrum = Spectrum(x_background, y_background)


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









