# -*- coding: utf8 -*-
# Py2DeX - GUI program for fast processing of 2D X-ray data
#     Copyright (C) 2014  Clemens Prescher (clemens.prescher@gmail.com)
#     GSECARS, University of Chicago
#
#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.
#
#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <http://www.gnu.org/licenses/>.
__author__ = 'Clemens Prescher'

import numpy as np
import fabio
import pyFAI
import pyFAI.utils
import matplotlib.pyplot as plt
from HelperModule import Observable, rotate_matrix_p90, rotate_matrix_m90, \
    FileNameIterator


class ImgData(Observable):
    def __init__(self):
        super(ImgData, self).__init__()
        self.img_data = np.zeros((2048, 2048))
        self.filename = ''
        self.file_iteration_mode = 'number'
        self.img_transformations = []

    def load(self, filename):
        self.filename = filename
        try:
            self.img_data_fabio = fabio.open(filename)
            self.img_data = self.img_data_fabio.data[::-1]
        except TypeError:
            self.img_data = plt.imread(filename)
            if len(self.img_data.shape) > 2:
                self.img_data = np.average(self.img_data, 2)
        self.perform_img_transformations()
        self.notify()

    def load_next(self):
        next_file_name = FileNameIterator.get_next_filename(
            self.filename, self.file_iteration_mode)
        if next_file_name is not None:
            self.load(next_file_name)
            return True
        return False

    def load_previous_file(self):
        previous_file_name = FileNameIterator.get_previous_filename(
            self.filename, self.file_iteration_mode)
        if previous_file_name is not None:
            self.load(previous_file_name)

    def set_calibration_file(self, filename):
        self.integrator = pyFAI.load(filename)

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


def test():
    filename = '../ExampleData/test_999.tif'
    print FileNameIterator.get_next_filename(filename)

    filename = '../ExampleData/test_002.tif'
    print FileNameIterator.get_previous_filename(filename)

    filename = '../ExampleData/test_008.tif'
    print FileNameIterator.get_next_filename(filename, 'date')


if __name__ == '__main__':
    test()
