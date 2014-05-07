__author__ = 'Clemens Prescher'


__author__ = 'Clemens Prescher'

from Data.SpectrumData import Spectrum, SpectrumData
from Data.ImgData import ImgData
from Data.CalibrationData import CalibrationData
from Data.MaskData import MaskData
import unittest
import numpy as np
import matplotlib.pyplot as plt


class SpectrumDataTest(unittest.TestCase):
    def setUp(self):
        self.img_data = ImgData()
        self.calibration_data = CalibrationData()
        self.mask_data = MaskData()
        self.spectrum_data = SpectrumData()
