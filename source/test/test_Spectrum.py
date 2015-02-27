# -*- coding: utf8 -*-
__author__ = 'Clemens Prescher'
import unittest
import os

import numpy as np

from model.Helper.Spectrum import BkgNotInRangeError
from model.Helper import Spectrum
from model.Helper.PeakShapes import gaussian

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, 'data')

class SpectrumTest(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def array_almost_equal(self, array1, array2, places=7):
        self.assertAlmostEqual(np.sum(array1 - array2), 0, places=places)

    def array_not_almost_equal(self, array1, array2, places=7):
        self.assertNotAlmostEqual(np.sum(array1 - array2), 0, places=places)

    def test_loading_chi_file(self):
        spec = Spectrum()
        x, y = spec.data

        spec.load(os.path.join(data_path,'spectrum_001.chi'))
        new_x, new_y = spec.data

        self.assertNotEqual(len(x), len(new_x))
        self.assertNotEqual(len(y), len(new_y))

    def test_loading_invalid_file(self):
        spec = Spectrum()
        self.assertEqual(-1, spec.load(os.path.join(data_path,'wrong_file_format.txt')))

    def test_saving_a_file(self):
        x = np.linspace(-5, 5, 100)
        y = x ** 2
        spec = Spectrum(x, y)
        filename = os.path.join(data_path, "test.dat")
        spec.save(filename)

        spec2 = Spectrum()
        spec2.load(filename)

        spec2_x, spec2_y = spec2.data
        self.array_almost_equal(spec2_x, x)
        self.array_almost_equal(spec2_y, y)

        os.remove(filename)

    def test_plus_and_minus_operators(self):
        x = np.linspace(0, 10, 100)
        spectrum1 = Spectrum(x, np.sin(x))
        spectrum2 = Spectrum(x, np.sin(x))

        spectrum3 = spectrum1 + spectrum2
        self.assertTrue(np.array_equal(spectrum3.y, np.sin(x) * 2))
        self.assertTrue(np.array_equal(spectrum2.original_y, np.sin(x) * 1))
        self.assertTrue(np.array_equal(spectrum1.original_y, np.sin(x) * 1))

        spectrum3 = spectrum1 + spectrum1
        self.assertTrue(np.array_equal(spectrum3.y, np.sin(x) * 2))
        self.assertTrue(np.array_equal(spectrum1.original_y, np.sin(x) * 1))
        self.assertTrue(np.array_equal(spectrum1.original_y, np.sin(x) * 1))

        spectrum3 = spectrum2 - spectrum1
        self.assertTrue(np.array_equal(spectrum3.y, np.sin(x) * 0))
        self.assertTrue(np.array_equal(spectrum2.original_y, np.sin(x) * 1))
        self.assertTrue(np.array_equal(spectrum1.original_y, np.sin(x) * 1))

        spectrum3 = spectrum1 - spectrum1
        self.assertTrue(np.array_equal(spectrum3.y, np.sin(x) * 0))
        self.assertTrue(np.array_equal(spectrum1.original_y, np.sin(x) * 1))
        self.assertTrue(np.array_equal(spectrum1.original_y, np.sin(x) * 1))

    def test_plus_and_minus_operators_with_different_shapes(self):
        x = np.linspace(0, 10, 1000)
        x2 = np.linspace(0, 12, 1300)
        spectrum1 = Spectrum(x, np.sin(x))
        spectrum2 = Spectrum(x2, np.sin(x2))

        spectrum3 = spectrum1 + spectrum2
        self.array_almost_equal(spectrum3.x, spectrum1._original_x)
        self.array_almost_equal(spectrum3.y, spectrum1._original_y * 2, 2)

        spectrum3 = spectrum1 + spectrum1
        self.array_almost_equal(spectrum3.y, np.sin(x) * 2, 2)

        spectrum3 = spectrum1 - spectrum2
        self.array_almost_equal(spectrum3.y, np.sin(x) * 0, 2)

        spectrum3 = spectrum1 - spectrum1
        self.array_almost_equal(spectrum3.y, np.sin(x) * 0, 2)


    def test_multiply_with_scalar_operator(self):
        x = np.linspace(0, 10, 100)
        spectrum1 = 2 * Spectrum(x, np.sin(x))

        spectrum2 = 2 * Spectrum(x, np.sin(x))

        self.assertTrue(np.array_equal(spectrum2.y, np.sin(x) * 2))

    def test_using_background_spectrum(self):
        x = np.linspace(-5, 5, 100)
        spec_y = x ** 2
        bkg_y = x

        spec = Spectrum(x, spec_y)
        background_spectrum = Spectrum(x, bkg_y)

        spec.background_spectrum = background_spectrum
        new_x, new_y = spec.data

        self.array_almost_equal(new_x, x)
        self.array_almost_equal(new_y, spec_y - bkg_y)

    def test_using_background_spectrum_with_different_spacing(self):
        x = np.linspace(-5, 5, 100)
        spec_y = x ** 2
        x_bkg = np.linspace(-5, 5, 99)
        bkg_y = x_bkg

        spec = Spectrum(x, spec_y)
        background_spectrum = Spectrum(x_bkg, bkg_y)

        spec.background_spectrum = background_spectrum
        new_x, new_y = spec.data

        self.array_almost_equal(new_x, x)
        self.array_almost_equal(new_y, spec_y - x)

    def test_background_out_of_range_throws_error(self):
        x1 = np.linspace(0, 10)
        x2 = np.linspace(-10, -1)

        spec = Spectrum(x1, x1)
        background_spectrum = Spectrum(x2, x2)

        with self.assertRaises(BkgNotInRangeError):
            spec.background_spectrum = background_spectrum

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

        spectrum = Spectrum(x, y_measurement)

        auto_background_subtraction_parameters = [2, 50, 50]
        spectrum.set_auto_background_subtraction(auto_background_subtraction_parameters)

        x_spec, y_spec = spectrum.data

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

        spectrum = Spectrum(x, y_measurement)

        auto_background_subtraction_parameters = [2, 50, 50]
        spectrum.set_auto_background_subtraction(auto_background_subtraction_parameters, roi)

        x_spec, y_spec = spectrum.data

        self.assertGreater(x_spec[0],roi[0])
        self.assertLess(x_spec[-1], roi[1])

        # self.array_almost_equal(y_spec, y)


    def test_setting_new_data(self):
        spec = Spectrum()
        x = np.linspace(0, 10)
        y = np.sin(x)
        spec.data = x, y

        new_x, new_y = spec.data
        self.array_almost_equal(new_x, x)
        self.array_almost_equal(new_y, y)

    def test_using_len(self):
        x = np.linspace(0,10,234)
        y = x**2
        spec = Spectrum(x, y)

        self.assertEqual(len(spec), 234)