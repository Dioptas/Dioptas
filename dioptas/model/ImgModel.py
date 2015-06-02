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
import fabio
from PIL import Image
from model.Helper.HelperModule import Observable, rotate_matrix_p90, rotate_matrix_m90, \
    FileNameIterator

from model.Helper.ImgCorrection import ImgCorrectionManager


class ImgModel(Observable):
    """
    Main Image handling class. Supports several features:
        - loading image files in any format using fabio
        - iterating through files either by file number or time of creation
        - image transformations like rotating and flipping
        - setting a background image
        - setting an absorption correction (img_data is divided by this)
        - using supersampling (splitting each pixel into n**2 pixel with equal intensity)

    It inherits the Observable interface for implementing the observer pattern. To subscribe a function to changes in
    ImgData use:
        img_data = ImgData()
        img_data.subscribe(function)

    The function will be called every time the img_data has changed.
    """
    def __init__(self):
        """
        Defines all object variables and creates a dummy image.
        :return:
        """
        super(ImgModel, self).__init__()
        self.filename = ''
        self.img_transformations = []
        self.supersampling_factor = 1

        self.file_iteration_mode = 'number'
        self.file_name_iterator = FileNameIterator()

        self._img_data = None
        self._img_data_background_subtracted = None
        self._img_data_absorption_corrected = None
        self._img_data_background_subtracted_absorption_corrected = None

        self._img_data_supersampled = None
        self._img_data_supersampled_background_subtracted = None
        self._img_data_supersampled_absorption_corrected = None
        self._img_data_supersampled_background_subtracted_absorption_corrected = None

        self.background_filename = ''
        self._background_data = None
        self._background_scaling = 1
        self._background_offset = 0

        self.file_info = ''

        self._img_corrections = ImgCorrectionManager()

        self._create_dummy_img()

    def _create_dummy_img(self):
        self._img_data = np.zeros((2048, 2048))

    def load(self, filename):
        """
        Loads an image file in any format known by fabIO. Automatically performs all previous img transformations,
        performs supersampling and recalculates background subtracted and absorption corrected image data. Observers
        will be notified after the process.
        :param filename: path of the image file to be loaded
        """
        logger.info("Loading {0}.".format(filename))
        self.filename = filename
        try:

            im = Image.open(filename)
            self.file_info = self._get_file_info(im)
            self._img_data = np.array(im)[::-1]
        except AttributeError:
            self._img_data_fabio = fabio.open(filename)
            self._img_data = self._img_data_fabio.data[::-1]
        self.file_name_iterator.update_filename(filename)

        self._perform_img_transformations()
        self._calculate_img_data()
        self.notify()

    def save(self, filename):
        try:
            self._img_data_fabio.save(filename)
        except AttributeError:
            im_array = np.int32(np.copy(np.flipud(self._img_data)))
            im = Image.fromarray(im_array)
            im.save(filename)

    def load_background(self, filename):
        """
        Loads an image file as background in any format known by fabIO. Automatically performs all previous img
        transformations, supersampling and recalculates background subtracted and absorption corrected image data.
        Observers will be notified after the process.
        :param filename: path of the image file to be loaded
        """
        self.background_filename = filename
        try:
            self._background_data_fabio = fabio.open(filename)
            self._background_data = self._background_data_fabio.data[::-1].astype(float)
        except AttributeError:
            self._background_data = np.array(Image.open(filename))[::-1].astype(float)

        self._perform_background_transformations()
        self._calculate_img_data()
        self.notify()

    def _image_and_background_shape_equal(self):
        """
        Tests if the original image and original background image have the same shape
        :return: Boolean
        """
        if self._background_data is None:
            return True
        if self._background_data.shape == self._img_data.shape:
            return True
        return False

    def _reset_background(self):
        """
        Resets the background data to None
        """
        self.background_filename = None
        self._background_data = None
        self._background_data_fabio = None
        self._calculate_img_data()

    def reset_background(self):
        self._reset_background()
        self.notify()

    def has_background(self):
        return self._background_data is not None

    def set_background_scaling(self, value):
        self._background_scaling = value
        self._calculate_img_data()
        self.notify()

    def set_background_offset(self, value):
        self._background_offset = value
        self._calculate_img_data()
        self.notify()

    def load_next_file(self, step=1):
        next_file_name = self.file_name_iterator.get_next_filename(mode=self.file_iteration_mode, step=step)
        if next_file_name is not None:
            self.load(next_file_name)

    def load_previous_file(self, step=1):
        previous_file_name = self.file_name_iterator.get_previous_filename(mode=self.file_iteration_mode, step=step)
        if previous_file_name is not None:
            self.load(previous_file_name)

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
            return self._img_data_background_subtracted
        else:
            return self._img_data

    def _calculate_img_data(self):
        """
        Calculates compound img_data based on the state of the object. This function is used internally to not compute
        those img arrays every time somebody requests the image data by get_img_data() and img_data.
        """

        #check that all data has the same dimensions
        if self._background_data is not None:
            if self._img_data.shape != self._background_data.shape:
                self._background_data = None
        if self._img_corrections.has_items():
            self._img_corrections.set_shape(self._img_data.shape)

        #calculate the current _img_data
        if self._background_data is not None and not self._img_corrections.has_items():
            self._img_data_background_subtracted = self._img_data - (self._background_scaling *
                                                                     self._background_data +
                                                                     self._background_offset)
        elif self._background_data is None and self._img_corrections.has_items():
            self._img_data_absorption_corrected = self._img_data / self._img_corrections.get_data()

        elif self._background_data is not None and self._img_corrections.has_items():
            self._img_data_background_subtracted_absorption_corrected = (self._img_data - (
                self._background_scaling * self._background_data + self._background_offset)) / \
                                                                        self._img_corrections.get_data()

        # supersample the current image data
        if self.supersampling_factor > 1:
            if self._background_data is None and not self._img_corrections.has_items():
                self._img_data_supersampled = self.supersample_data(self._img_data, self.supersampling_factor)

            if self._background_data is not None and not self._img_corrections.has_items():
                self._img_data_supersampled_background_subtracted = \
                    self.supersample_data(self._img_data_background_subtracted, self.supersampling_factor)

            elif self._background_data is None and self._img_corrections.has_items():
                self._img_data_supersampled_absorption_corrected = \
                    self.supersample_data(self._img_data_absorption_corrected, self.supersampling_factor)

            elif self._background_data is not None and self._img_corrections.has_items():
                self._img_data_supersampled_background_subtracted_absorption_corrected = \
                    self.supersample_data(self._img_data_background_subtracted_absorption_corrected,
                                          self.supersampling_factor)


    @property
    def img_data(self):
        """
        :return:
            The image based on the current state of the ImgData object. If supersampling is set it will return a
            supersampled image array if background_data is set it will return a background_subtracted array and so on.
            It also works for combinations of all these options.
        """
        if self.supersampling_factor == 1:
            if self._background_data is None and not self._img_corrections.has_items():
                return self._img_data

            elif self._background_data is not None and not self._img_corrections.has_items():
                return self._img_data_background_subtracted

            elif self._background_data is None and self._img_corrections.has_items():
                return self._img_data_absorption_corrected

            elif self._background_data is not None and self._img_corrections.has_items():
                return self._img_data_background_subtracted_absorption_corrected

        else:
            if self._background_data is None and not self._img_corrections.has_items():
                return self._img_data_supersampled

            elif self._background_data is not None and not self._img_corrections.has_items():
                return self._img_data_supersampled_background_subtracted

            elif self._background_data is None and self._img_corrections.has_items():
                return self._img_data_supersampled_absorption_corrected

            elif self._background_data is not None and self._img_corrections.has_items():
                return self._img_data_supersampled_background_subtracted_absorption_corrected

    def rotate_img_p90(self):
        """
        Rotates the image by 90 degree and updates the background accordingly (does not effect absorption correction).
        The transformation is saved and applied to every new image and background image loaded.
        Notifies observers.
        """
        self._img_data = rotate_matrix_p90(self._img_data)

        if self._background_data is not None:
            self._background_data = rotate_matrix_p90(self._background_data)

        self.img_transformations.append(rotate_matrix_p90)

        self._calculate_img_data()
        self.notify()

    def rotate_img_m90(self):
        """
        Rotates the image by -90 degree and updates the background accordingly (does not effect absorption correction).
        The transformation is saved and applied to every new image and background image loaded.
        Notifies observers.
        """
        self._img_data = rotate_matrix_m90(self._img_data)
        if self._background_data is not None:
            self._background_data = rotate_matrix_m90(self._background_data)
        self.img_transformations.append(rotate_matrix_m90)

        self._calculate_img_data()
        self.notify()

    def flip_img_horizontally(self):
        """
        Flips image about a horizontal axis and updates the background accordingly (does not effect absorption
        correction). The transformation is saved and applied to every new image and background image loaded.
        Notifies observers.
        """
        self._img_data = np.fliplr(self._img_data)
        if self._background_data is not None:
            self._background_data = np.fliplr(self._background_data)
        self.img_transformations.append(np.fliplr)

        self._calculate_img_data()
        self.notify()

    def flip_img_vertically(self):
        """
        Flips image about a vertical axis and updates the background accordingly (does not effect absorption
        correction). The transformation is saved and applied to every new image and background image loaded.
        Notifies observers.
        """
        self._img_data = np.flipud(self._img_data)
        if self._background_data is not None:
            self._background_data = np.flipud(self._background_data)
        self.img_transformations.append(np.flipud)

        self._calculate_img_data()
        self.notify()

    def reset_img_transformations(self):
        """
        Reverts all image transformations and resets the transformation stack.
        Notifies observers.
        """
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
        self._calculate_img_data()
        self.notify()

    def _perform_img_transformations(self):
        """
        Performs all saved image transformation on original image.
        """
        for transformation in self.img_transformations:
            self._img_data = transformation(self._img_data)

    def _perform_background_transformations(self):
        """
        Performs all saved image transformation on background image.
        """
        if self._background_data is not None:
            for transformation in self.img_transformations:
                self._background_data = transformation(self._background_data)


    def set_supersampling(self, factor=None):
        """
        Stores the supersampling factor and calculates supersampled original and background image arrays.
        Updates all data calculations according to current ImgData object state.
        Does not notify Observers!
        :param factor: int - supersampling factor
        """
        self.supersampling_factor = factor
        self._calculate_img_data()

    def supersample_data(self, img_data, factor):
        """
        Creates a supersampled array from img_data.
        :param img_data: image array
        :param factor: int - supersampling factor
        :return:
        """
        if factor > 1:
            img_data_supersampled = np.zeros((img_data.shape[0] * factor,
                                              img_data.shape[1] * factor))
            for row in range(factor):
                for col in range(factor):
                    img_data_supersampled[row::factor, col::factor] = img_data

            return img_data_supersampled
        else:
            return img_data

    def add_img_correction(self, correction, name=None):
        self._img_corrections.add(correction, name)
        self._calculate_img_data()
        self.notify()

    def get_img_correction(self, name):
        return self._img_corrections.get_correction(name)

    def delete_img_correction(self, name=None):
        self._img_corrections.delete(name)
        self._calculate_img_data()
        self.notify()

    def has_corrections(self):
        """
        :return: Whether the ImgData object has active absorption corrections or not
        """
        return self._img_corrections.has_items()

    def _get_file_info(self, image):
        """
        reads the file info from tif_tags and returns a file info
        """
        result = ""
        tags = image.tag
        useful_keys = []
        for key in tags.keys():
            if key>300:
                useful_keys.append(key)

        useful_keys.sort()
        for key in useful_keys:
            if isinstance(tags[key], basestring):
                new_line = str(tags[key])+"\n"
                new_line = new_line.replace(":", ":\t", 1)
                result += new_line
        return result