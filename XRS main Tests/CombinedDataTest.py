__author__ = 'Clemens Prescher'

__author__ = 'Clemens Prescher'

from Data.SpectrumData import Spectrum, SpectrumData
from Data.ImgData import ImgData
from Data.CalibrationData import CalibrationData
from Data.MaskData import MaskData
import unittest
import numpy as np
import matplotlib.pyplot as plt


class CombinedDataTest(unittest.TestCase):
    def setUp(self):
        self.img_data = ImgData()
        self.img_data.load('Data/Mg2SiO4_ambient_001.tif')
        self.calibration_data = CalibrationData(self.img_data)
        self.calibration_data.load('Data/calibration.poni')
        self.mask_data = MaskData()
        self.mask_data.load_mask('Data/test.mask')
        self.spectrum_data = SpectrumData()

    def test_dependencies(self):
        tth1, int1 = self.calibration_data.integrate_1d()
        self.img_data.load_next()
        tth2, int2 = self.calibration_data.integrate_1d()
        self.assertFalse(np.array_equal(int1, int2))

        plt.figure(1)
        plt.plot(tth1, int1)
        plt.plot(tth2, int2)
        plt.savefig('Results/dependencies1.jpg')

        tth3, int3 = self.calibration_data.integrate_1d(mask=self.mask_data.get_mask())
        self.assertFalse(np.array_equal(int2, int3))
        plt.figure(2)
        plt.plot(tth2, int2)
        plt.plot(tth3, int3)
        plt.savefig('Results/dependencies2.jpg')

        tth4, int4 = self.calibration_data.integrate_1d(polarization_factor=0.90, mask=None)
        plt.figure(3)
        plt.plot(tth2, int2)
        plt.plot(tth4, int4)
        plt.savefig('Results/dependencies3.jpg')

        tth5, int5 = self.calibration_data.integrate_1d(polarization_factor=.5, mask=None)
        plt.figure(4)
        plt.plot(tth4, int4)
        plt.plot(tth5, int5)
        plt.savefig('Results/dependencies4.jpg')

    def test_automatism(self):
        def integrate_and_set_spectrum():
            tth, I = self.calibration_data.integrate_1d()
            self.spectrum_data.set_spectrum(tth, I, self.img_data.filename)

        self.img_data.subscribe(integrate_and_set_spectrum)

        y1 = self.spectrum_data.spectrum.data[1]
        self.img_data.load_next()
        y2 = self.spectrum_data.spectrum.data[1]
        self.assertFalse(np.array_equal(y1, y2))



