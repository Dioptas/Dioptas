import matplotlib.pyplot as plt
import os
import numpy as np
from ImageCalibration import ImageCalibration, Point
from utilities import Subscriptable, Spectrum, FileIterator


class XRS_GraphData(Subscriptable):
    def __init__(self):
        Subscriptable.__init__(self)
        self.create_dummy_data()

    def create_dummy_data(self):
        x = np.linspace(2, 30, 100)
        self.spectrum = Spectrum(x, x + np.sin(x))

    def get_spectrum(self):
        return self.spectrum


class XRS_ImageData(Subscriptable):
    def __init__(self):
        Subscriptable.__init__(self)
        self._create_dummy_data()
        self.file_iterator = FileIterator(self.load_image_file)
        self.image_calibration = ImageCalibration(Point(1024, 1024), 14, -0.211, 201.0467e-3, 79e-6)

    def _create_dummy_data(self):
        self.img_data = plt.imread("test_002.tif")
        self.file_name = "test_002.tif"

    def load_image_file(self, file_name):
        self.img_data = plt.imread(file_name)
        self.file_name = file_name
        self.update_subscriber()

    def load_next_image_file(self):
        self.file_iterator.load_next_file(self.file_name)

    def load_previous_image_file(self):
        self.file_iterator.load_previous_file(self.file_name)

    def get_image_data(self):
        return self.img_data

    def get_spectrum(self):
        x, y = self.image_calibration.integrate_image(self.img_data)
        return Spectrum(x, y)


