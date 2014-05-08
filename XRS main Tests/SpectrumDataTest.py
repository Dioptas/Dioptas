__author__ = 'Clemens Prescher'

from Data.SpectrumData import Spectrum, SpectrumData
import unittest
import numpy as np


class SpectrumDataTest(unittest.TestCase):
    def setUp(self):
        self.spectrum = Spectrum()
        self.spectrum_data = SpectrumData()

    def test_spectrum_class(self):
        self.spectrum.save('Data/spec_test.txt')
        self.spectrum.save('Data/spec_test2.txt',
                           header='This is not only ridiculous\n but more and more '
                                  'challenging...')
        self.spectrum.load('Data/spec_test.txt')
        self.spectrum.load('Data/spec_test2.txt')

        self.assertTrue(np.array_equal(self.spectrum.data[0], np.linspace(0, 30, 100)))
        self.assertTrue(self.spectrum.load('Data/test_001.tif') == -1)

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

    def test_spectrum_data_class(self):
        self.spectrum_data.set_spectrum(np.linspace(0, 10), np.linspace(0, 10) ** 2, 'SQUARED')
        self.spectrum_data.add_overlay(np.linspace(0, 10), np.linspace(0, 10) ** 3, 'CUBED')
        self.spectrum_data.add_overlay(np.linspace(0, 10), np.linspace(0, 10) ** 4, 'QUADRUPOLED')

        self.assertTrue(len(self.spectrum_data.overlays) == 2)
        self.spectrum_data.del_overlay(0)
        self.assertTrue(self.spectrum_data.overlays[0].name == 'QUADRUPOLED')

        self.spectrum_data.add_overlay_file('Data/spec_test2.txt')
        self.assertTrue(self.spectrum_data.overlays[-1].name == 'spec_test2')

