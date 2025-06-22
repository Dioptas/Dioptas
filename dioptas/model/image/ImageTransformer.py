# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
# Principal author: Clemens Prescher (clemens.prescher@gmail.com)
# Copyright (C) 2014-2019 GSECARS, University of Chicago, USA
# Copyright (C) 2015-2018 Institute for Geology and Mineralogy, University of Cologne, Germany
# Copyright (C) 2019-2020 DESY, Hamburg, Germany
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

import numpy as np

from ..util import Signal
from ..util.HelperModule import rotate_matrix_p90, rotate_matrix_m90


class ImageTransformer:
    """
    Manages image transformations.
    Handles rotation, flipping, and transformation stack management.
    """

    def __init__(self):
        self.img_transformations = []
        self.transformations_changed = Signal()

    def rotate_img_p90(self, img_data, background_data=None):
        """
        Rotates the image by 90 degrees and updates the background accordingly.
        The transformation is saved and applied to every new image and background image loaded.
        :param img_data: image data to transform
        :param background_data: background data to transform (optional)
        :return: tuple of (transformed_img_data, transformed_background_data)
        """
        transformed_img = rotate_matrix_p90(img_data)
        transformed_background = None
        
        if background_data is not None:
            transformed_background = rotate_matrix_p90(background_data)

        self.img_transformations.append(rotate_matrix_p90)
        self.transformations_changed.emit()
        
        return transformed_img, transformed_background

    def rotate_img_m90(self, img_data, background_data=None):
        """
        Rotates the image by -90 degrees and updates the background accordingly.
        The transformation is saved and applied to every new image and background image loaded.
        :param img_data: image data to transform
        :param background_data: background data to transform (optional)
        :return: tuple of (transformed_img_data, transformed_background_data)
        """
        transformed_img = rotate_matrix_m90(img_data)
        transformed_background = None
        
        if background_data is not None:
            transformed_background = rotate_matrix_m90(background_data)

        self.img_transformations.append(rotate_matrix_m90)
        self.transformations_changed.emit()
        
        return transformed_img, transformed_background

    def flip_img_horizontally(self, img_data, background_data=None):
        """
        Flips image about a horizontal axis and updates the background accordingly.
        The transformation is saved and applied to every new image and background image loaded.
        :param img_data: image data to transform
        :param background_data: background data to transform (optional)
        :return: tuple of (transformed_img_data, transformed_background_data)
        """
        transformed_img = np.fliplr(img_data)
        transformed_background = None
        
        if background_data is not None:
            transformed_background = np.fliplr(background_data)

        self.img_transformations.append(np.fliplr)
        self.transformations_changed.emit()
        
        return transformed_img, transformed_background

    def flip_img_vertically(self, img_data, background_data=None):
        """
        Flips image about a vertical axis and updates the background accordingly.
        The transformation is saved and applied to every new image and background image loaded.
        :param img_data: image data to transform
        :param background_data: background data to transform (optional)
        :return: tuple of (transformed_img_data, transformed_background_data)
        """
        transformed_img = np.flipud(img_data)
        transformed_background = None
        
        if background_data is not None:
            transformed_background = np.flipud(background_data)

        self.img_transformations.append(np.flipud)
        self.transformations_changed.emit()
        
        return transformed_img, transformed_background

    def reset_transformations(self):
        """
        Reverts all image transformations and resets the transformation stack.
        """
        self.img_transformations = []
        self.transformations_changed.emit()

    def _reset_img_transformations(self, img_data):
        """
        Reset transformations on image data by applying inverse transformations.
        :param img_data: image data to reset transformations on
        :return: reset image data
        """
        reset_data = img_data.copy()
        for transformation in reversed(self.img_transformations):
            if transformation == rotate_matrix_p90:
                reset_data = rotate_matrix_m90(reset_data)
            elif transformation == rotate_matrix_m90:
                reset_data = rotate_matrix_p90(reset_data)
            else:
                reset_data = transformation(reset_data)
        return reset_data

    def _reset_background_transformations(self, background_data):
        """
        Reset transformations on background data by applying inverse transformations.
        :param background_data: background data to reset transformations on
        :return: reset background data
        """
        if background_data is None:
            return None
            
        reset_data = background_data.copy()
        for transformation in reversed(self.img_transformations):
            if transformation == rotate_matrix_p90:
                reset_data = rotate_matrix_m90(reset_data)
            elif transformation == rotate_matrix_m90:
                reset_data = rotate_matrix_p90(reset_data)
            else:
                reset_data = transformation(reset_data)
        return reset_data

    def _perform_img_transformations(self, img_data):
        """
        Performs all saved image transformations on original image.
        :param img_data: image data to transform
        :return: transformed image data
        """
        transformed_data = img_data.copy()
        for transformation in self.img_transformations:
            transformed_data = transformation(transformed_data)
        return transformed_data

    def _perform_background_transformations(self, background_data):
        """
        Performs all saved image transformations on background image.
        :param background_data: background data to transform
        :return: transformed background data
        """
        if background_data is None:
            return None
            
        transformed_data = background_data.copy()
        for transformation in self.img_transformations:
            transformed_data = transformation(transformed_data)
        return transformed_data

    def get_transformations_string_list(self):
        """
        Get list of transformation function names.
        :return: list of transformation names
        """
        transformation_list = []
        for transformation in self.img_transformations:
            transformation_list.append(transformation.__name__)
        return transformation_list

    def load_transformations_string_list(self, transformations):
        """
        Load transformations from a list of transformation names.
        :param transformations: list of transformation names
        """
        self.img_transformations = []
        for transformation in transformations:
            if transformation == "flipud":
                self.img_transformations.append(np.flipud)
            elif transformation == "fliplr":
                self.img_transformations.append(np.fliplr)
            elif transformation == "rotate_matrix_m90":
                self.img_transformations.append(rotate_matrix_m90)
            elif transformation == "rotate_matrix_p90":
                self.img_transformations.append(rotate_matrix_p90)
        self.transformations_changed.emit() 