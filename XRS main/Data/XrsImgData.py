__author__ = 'Clemens Prescher'

import numpy as np
import fabio
import pyFAI
import pyFAI.utils
import matplotlib.pyplot as plt
from XrsHelper import Observable, rotate_matrix_p90, rotate_matrix_m90


class XrsImgData(Observable):

    def __init__(self):
        super(XrsImgData, self).__init__()

        self.img_data = None
        self.integrator = None

        self.tth = None
        self.I = None

        self.img_transformations = []

    def load_file(self, filename):
        self.filename = filename
        try:
            self.img_data_fabio = fabio.open(filename)
            self.img_data = self.img_data_fabio.data[::-1]
        except TypeError:
            self.img_data = plt.imread(filename)
            if len(self.img_data.shape) > 2:
                self.img_data = np.average(self.img_data, 2)
        self.perform_img_transformations()
        self.integrate_img()
        self.notify()

    def load_next_file(self):
        self.img_data_fabio = self.img_data_fabio.next()
        self.img_data = self.img_data_fabio.data
        self.integrate_img()
        self.notify()

    def load_previous_file(self):
        self.img_data_fabio = self.img_data_fabio.previous()
        self.img_data = self.img_data_fabio.data
        self.integrate_img()
        self.notify()

    def set_calibration_file(self, filename):
        self.integrator = pyFAI.load(filename)

    def integrate_img(self):
        if self.integrator is not None:
            self.tth, self.I = self.integrator.integrate1d(
                self.img_data, 1000, unit='2th_deg', method="lut_ocl")

    def get_spectrum(self):
        return self.tth, self.I

    def get_img_data(self):
        return self.img_data

    def rotate_img_p90(self):
        self.img_data = rotate_matrix_p90(self.img_data)
        self.img_transformations.append(rotate_matrix_p90)
        self.notify()

    def rotate_img_m90(self):
        self.img_data = rotate_matrix_m90(self.img_data)
        self.img_transformations.append(rotate_matrix_m90)
        self.notify()

    def flip_img_horizontally(self):
        self.img_data = np.fliplr(self.img_data)
        self.img_transformations.append(np.fliplr)
        self.notify()

    def flip_img_vertically(self):
        self.img_data = np.flipud(self.img_data)
        self.img_transformations.append(np.flipud)
        self.notify()

    def reset_img_transformations(self):
        for transformation in reversed(self.img_transformations):
            if transformation == rotate_matrix_p90:
                self.img_data = rotate_matrix_m90(self.img_data)
            elif transformation == rotate_matrix_m90:
                self.img_data = rotate_matrix_p90(self.img_data)
            else:
                self.img_data = transformation(self.img_data)
        self.img_transformations = []
        self.notify()

    def perform_img_transformations(self):
        for transformation in self.img_transformations:
            self.img_data = transformation(self.img_data)


if __name__ == '__main__':
    my_observable = Observable()
    my_observable.subscribe(test)
    my_observable.notify()
