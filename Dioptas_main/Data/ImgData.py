# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2014  Clemens Prescher (clemens.prescher@gmail.com)
# GSECARS, University of Chicago
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

import logging
logger = logging.getLogger(__name__)

import numpy as np
import random
import fabio
import pyFAI
import pyFAI.utils
from PIL import Image
from .HelperModule import Observable, rotate_matrix_p90, rotate_matrix_m90, \
    FileNameIterator, gauss_function


class ImgData(Observable):
    def __init__(self):
        super(ImgData, self).__init__()
        self.filename = ''
        self.img_transformations = []
        self.super_sampling_factor = 1


        self.file_iteration_mode = 'number'
        self.file_name_iterator = FileNameIterator()

        x = np.arange(2048)
        y = np.arange(2048)
        X, Y = np.meshgrid(x, y)
        self._img_data = 2000 * np.ones((2048.0, 2048.0))
        line_pos = np.linspace(0, 2047, 10)
        for pos in line_pos:
            self._img_data += gauss_function(X, 10000 * random.random(), 50 * random.random(), pos)
            self._img_data += gauss_function(Y, 10000 * random.random(), 50 * random.random(), pos)
        self._img_data += gauss_function(X, 200 + 200 * random.random(), 500 + 500 * random.random(),
                                        800 + 400 * random.random()) * \
                         gauss_function(Y, 200 + 200 * random.random(), 500 + 500 * random.random(),
                                        800 + 400 * random.random())

    def load(self, filename):
        logger.info("Loading {}.".format(filename))
        self.filename = filename
        try:
            self._img_data_fabio = fabio.open(filename)
            self._img_data = self._img_data_fabio.data[::-1]
        except AttributeError:
            self._img_data = np.array(Image.open(filename))[::-1]
        self.perform_img_transformations()
        self.notify()
        self.file_name_iterator.update_filename(filename)

    def load_next_file(self):
        next_file_name = self.file_name_iterator.get_next_filename(self.file_iteration_mode)
        if next_file_name is not None:
            self.load(next_file_name)
            return True
        return False

    def load_previous_file(self):
        previous_file_name = self.file_name_iterator.get_previous_filename(self.file_iteration_mode)
        if previous_file_name is not None:
            self.load(previous_file_name)
            return True
        return False

    def set_file_iteration_mode(self, mode):
        if mode == 'number':
            self.file_iteration_mode = 'number'
            self.file_name_iterator.create_timed_file_list = False
        elif mode == 'time':
            self.file_iteration_mode = 'time'
            self.file_name_iterator.create_timed_file_list = True
            self.file_name_iterator.update_filename(self.filename)

    def set_calibration_file(self, filename):
        self.integrator = pyFAI.load(filename)

    def get_spectrum(self):
        return self.tth, self.I

    def get_img_data(self):
        return self.img_data

    @property
    def img_data(self):
        return self._img_data

    def rotate_img_p90(self):
        self._img_data = rotate_matrix_p90(self.img_data)
        self.img_transformations.append(rotate_matrix_p90)
        self.notify()

    def rotate_img_m90(self):
        self._img_data = rotate_matrix_m90(self.img_data)
        self.img_transformations.append(rotate_matrix_m90)
        self.notify()

    def flip_img_horizontally(self):
        self._img_data = np.fliplr(self.img_data)
        self.img_transformations.append(np.fliplr)
        self.notify()

    def flip_img_vertically(self):
        self._img_data = np.flipud(self.img_data)
        self.img_transformations.append(np.flipud)
        self.notify()

    def reset_img_transformations(self):
        for transformation in reversed(self.img_transformations):
            if transformation == rotate_matrix_p90:
                self._img_data = rotate_matrix_m90(self.img_data)
            elif transformation == rotate_matrix_m90:
                self._img_data = rotate_matrix_p90(self.img_data)
            else:
                self._img_data = transformation(self.img_data)
        self.img_transformations = []
        self.notify()

    def perform_img_transformations(self):
        for transformation in self.img_transformations:
            self._img_data = transformation(self._img_data)

    def set_super_sampling(self, factor):
        self.super_sampling_factor = factor
        self._img_data_super_sampled = np.zeros((self._img_data.size()[0]*factor,
                                                 self._img_data.size()[1]*factor))

        for row in range(factor):
            for col in range(factor):
                self._img_data_super_sampled[row::factor, col::factor] = self._img_data
        self._img_data_super_sampled/=factor**2



def test():
    filename = '../ExampleData/test_999.tif'
    print((FileNameIterator.get_next_filename(filename)))

    filename = '../ExampleData/test_002.tif'
    print((FileNameIterator.get_previous_filename(filename)))

    filename = '../ExampleData/test_008.tif'
    print((FileNameIterator.get_next_filename(filename, 'date')))


if __name__ == '__main__':
    test()
