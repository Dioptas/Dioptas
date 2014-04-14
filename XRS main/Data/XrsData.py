__author__ = 'Clemens Prescher'

import numpy as np
import fabio
import pyFAI, pyFAI.utils
import matplotlib.pyplot as plt


class XrsData(object):
    def __init__(self):
        self.img_data = None
        self.integrator = None
        self.tth = None
        self.I = None

    def load_file(self, filename):
        self.filename = filename
        try:
            self.img_data_fabio = fabio.open(filename)
            self.img_data = fabio.data
        except TypeError:
            self.img_data = plt.imread(filename)
            if len(self.img_data.shape) > 2:
                self.img_data = np.average(self.img_data, 2)
        if self.integrator is not None:
            self.integrate_img()

    def load_next_file(self):
        self.img_data = self.img_data.next()
        self.integrate_img()

    def load_previous_file(self):
        self.img_data = self.img_data.previous()
        self.integrate_img()

    def set_calibration_file(self, filename):
        self.integrator = pyFAI.load(filename)

    def integrate_img(self):
        self.tth, self.I = self.integrator.integrate1d(self.img_data, 1000, unit='2th_deg', method="lut_ocl")

    def get_spectrum(self):
        return self.tth, self.I

    def get_img_data(self):
        return self.img_data

