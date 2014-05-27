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
        self.img_data.load('Data/LaB6_p49_40keV_006.tif')
        self.calibration_data = CalibrationData(self.img_data)
        self.calibration_data.calibrant.load_file('Data/Calibrants/LaB6.D')
        self.calibration_data.calibrant.set_wavelength(0.31 * 1e-10)
        self.calibration_data.load('Data/LaB6_p49_40keV_006.poni')

    def test_recalibration(self):
        self.calibration_data.recalibrate()
        plt.imshow(self.img_data.img_data)
        plt.plot(self.calibration_data.geometry.data[:, 0], self.calibration_data.geometry.data[:, 1], 'g.')
        plt.savefig('Results/recalib_massif.jpg')

        self.calibration_data.recalibrate('blob')
        plt.figure(2)
        plt.imshow(self.img_data.img_data)
        plt.plot(self.calibration_data.geometry.data[:, 0], self.calibration_data.geometry.data[:, 1], 'g.')
        plt.savefig('Results/recalib_blob.jpg')

        self.calibration_data.recalibrate('blob')
        plt.figure(3)
        plt.imshow(self.img_data.img_data)
        plt.plot(self.calibration_data.geometry.data[:, 0], self.calibration_data.geometry.data[:, 1], 'g.')
        plt.savefig('Results/recalib_blob2.jpg')