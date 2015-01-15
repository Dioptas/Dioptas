__author__ = 'Clemens Prescher'

import os
import gc
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
        self.mask_data.mask_ellipse(500, 500, 100, 100)
        self.spectrum_data = SpectrumData()

    def tearDown(self):
        del self.calibration_data.cake_geometry
        del self.calibration_data.spectrum_geometry
        del self.img_data
        del self.calibration_data
        del self.mask_data
        del self.spectrum_data
        gc.collect()

    def test_dependencies(self):
        tth1, int1 = self.calibration_data.integrate_1d()
        self.img_data.load_next_file()

        self.assertEqual(os.path.abspath(self.img_data.filename),
                         os.path.abspath('Data/Mg2SiO4_ambient_002.tif'))
        tth2, int2 = self.calibration_data.integrate_1d()
        self.assertFalse(np.array_equal(int1, int2))

        plt.figure(1)
        plt.plot(tth1, int1)
        plt.plot(tth2, int2)
        plt.savefig('Results/dependencies1.png')

        tth3, int3 = self.calibration_data.integrate_1d(mask=self.mask_data.get_mask())
        self.assertFalse(np.array_equal(int2, int3))
        plt.figure(2)
        plt.plot(tth2, int2)
        plt.plot(tth3, int3)
        plt.savefig('Results/dependencies2.png')

        tth4, int4 = self.calibration_data.integrate_1d(polarization_factor=0.90, mask=None)
        plt.figure(3)
        plt.plot(tth2, int2)
        plt.plot(tth4, int4)
        plt.savefig('Results/dependencies3.png')

        tth5, int5 = self.calibration_data.integrate_1d(polarization_factor=.5, mask=None)
        plt.figure(4)
        plt.plot(tth4, int4)
        plt.plot(tth5, int5)
        plt.savefig('Results/dependencies4.png')

    def test_automatism(self):
        def integrate_and_set_spectrum():
            tth, I = self.calibration_data.integrate_1d()
            self.spectrum_data.set_spectrum(tth, I, self.img_data.filename)

        self.img_data.subscribe(integrate_and_set_spectrum)

        y1 = self.spectrum_data.spectrum.data[1]
        self.img_data.load_next_file()
        y2 = self.spectrum_data.spectrum.data[1]
        self.assertFalse(np.array_equal(y1, y2))



