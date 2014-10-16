# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2014  Clemens Prescher (clemens.prescher@gmail.com)
# GSECARS, University of Chicago
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


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
        self.supersampling_factor = 1

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
        self._background_data = None
        self._background_scaling = 1
        self._background_offset = 0
        self._absorption_correction = None

    def load(self, filename):
        logger.info("Loading {}.".format(filename))
        self.filename = filename
        try:
            self._img_data_fabio = fabio.open(filename)
            self._img_data = self._img_data_fabio.data[::-1]
        except AttributeError:
            self._img_data = np.array(Image.open(filename))[::-1]
        self.perform_img_transformations()
        self.set_supersampling()
        self.notify()
        self.file_name_iterator.update_filename(filename)

    def load_background(self, filename):
        self.background_filename = filename
        try:
            self._background_data_fabio = fabio.open(filename)
            self._background_data = self._background_data_fabio.data[::-1].astype(float)
        except AttributeError:
            self._background_data = np.array(Image.open(filename))[::-1].astype(float)
        self.perform_background_transformations()
        self.set_supersampling()
        self.notify()

    def reset_background(self):
        self._background_data = None
        self.notify()

    def set_background_scaling(self, value):
        self._background_scaling = value
        self.notify()

    def set_background_offset(self, value):
        self._background_offset = value
        self.notify()

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

    def get_img_data(self):
        return self.img_data

    def get_img(self):
        if self._background_data is not None:
            return self._img_data - (self._background_scaling * self._background_data + self._background_offset)
        else:
            return self._img_data

    @property
    def img_data(self):
        """

        :return:
            img data with background and absorption correction if available
        """

        if self.supersampling_factor == 1:
            if self._background_data is None and self._absorption_correction is None:
                return self._img_data

            elif self._background_data is not None and self._absorption_correction is None:
                return self._img_data - (self._background_scaling * self._background_data + self._background_offset)

            elif self._background_data is None and self._absorption_correction is not None:
                return self._img_data / self._absorption_correction

            elif self._background_data is not None and self._absorption_correction is not None:
                return (self._img_data - (
                self._background_scaling * self._background_data + self._background_offset)) / self._absorption_correction

        else:
            if self._background_data is None and self._absorption_correction is None:
                return self._img_data_supersampled

            elif self._background_data is not None and self._absorption_correction is None:
                return self._img_data_supersampled - (self._background_scaling * self._background_data_supersampled + self._background_offset)

            elif self._background_data is None and self._absorption_correction is not None:
                return self._img_data_supersampled / self._absorption_correction

            elif self._background_data is not None and self._absorption_correction is not None:
                return (self._img_data_supersampled - (
                self._background_scaling * self._background_data_supersampled + self._background_offset)) / self._absorption_correction

    def rotate_img_p90(self):
        self._img_data = rotate_matrix_p90(self._img_data)
        if self._background_data is not None:
            self._background_data = rotate_matrix_p90(self._background_data)
        self.img_transformations.append(rotate_matrix_p90)
        self.notify()

    def rotate_img_m90(self):
        self._img_data = rotate_matrix_m90(self._img_data)
        if self._background_data is not None:
            self._background_data = rotate_matrix_m90(self._background_data)
        self.img_transformations.append(rotate_matrix_m90)
        self.notify()

    def flip_img_horizontally(self):
        self._img_data = np.fliplr(self._img_data)
        if self._background_data is not None:
            self._background_data = np.fliplr(self._background_data)
        self.img_transformations.append(np.fliplr)
        self.notify()

    def flip_img_vertically(self):
        self._img_data = np.flipud(self._img_data)
        if self._background_data is not None:
            self._background_data = np.flipud(self._background_data)
        self.img_transformations.append(np.flipud)
        self.notify()

    def reset_img_transformations(self):
        for transformation in reversed(self.img_transformations):
            if transformation == rotate_matrix_p90:
                self._img_data = rotate_matrix_m90(self._img_data)
                if self._background_data is not None:
                    self._background_data = rotate_matrix_m90(self._background_data)
            elif transformation == rotate_matrix_m90:
                self._img_data = rotate_matrix_p90(self._img_data)
                if self._background_data is not None:
                    self._background_data = rotate_matrix_p90(self._background_data)
            else:
                self._img_data = transformation(self._img_data)
                if self._background_data is not None:
                    self._background_data = transformation(self._background_data)
        self.img_transformations = []
        self.notify()

    def perform_img_transformations(self):
        for transformation in self.img_transformations:
            self._img_data = transformation(self._img_data)

    def perform_background_transformations(self):
        for transformation in self.img_transformations:
            self._background_data = transformation(self._background_data)

    def set_supersampling(self, factor=None):
        if factor is None:
            factor = self.supersampling_factor
        else:
            self.supersampling_factor = factor
        self._img_data_supersampled = self.supersample_data(self._img_data, factor)

        if self._background_data is not None:
            self._background_data_supersampled = self.supersample_data(self._background_data, factor)


    def supersample_data(self, img_data, factor):
        if factor > 1:
            img_data_supersampled = np.zeros((img_data.shape[0] * factor,
                                              img_data.shape[1] * factor))
            for row in range(factor):
                for col in range(factor):
                    img_data_supersampled[row::factor, col::factor] = img_data

            return img_data_supersampled
        else:
            return img_data


    def set_absorption_correction(self, absorption_correction):
        self._absorption_correction = absorption_correction
        self.notify()