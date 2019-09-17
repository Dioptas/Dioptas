# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
# Principal author: Clemens Prescher (clemens.prescher@gmail.com)
# Copyright (C) 2014-2019 GSECARS, University of Chicago, USA
# Copyright (C) 2015-2018 Institute for Geology and Mineralogy, University of Cologne, Germany
# Copyright (C) 2019 DESY, Hamburg, Germany
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
from PIL import Image
from past.builtins import basestring

from .ImgLoader import ImageLoader


class PILLoader(ImageLoader):
    def load(self, filename):
        """
        Loads an image using the PIL library. Also returns file and motor info if present
        :param filename: path to the image file to be loaded
        :return: dictionary with image_data and file_info and motors_info if present. None if unsuccessful
        """
        try:
            im = Image.open(filename)

            if np.prod(im.size) <= 1:
                im.close()
                return False

            self.img_data = np.array(im)[::-1]

            try:
                self.file_info = read_PIL_tiff_file_info(im)
                self.motors_info = read_PIL_tiff_motors_info(im)
            except AttributeError:
                pass

            im.close()
            self.filename = filename
            return self.img_data
        except IOError:
            return None


def read_PIL_tiff_file_info(image):
    """
    reads the file info from tif_tags and returns a file info
    """
    result = ""
    tags = image.tag
    useful_keys = []
    for key in tags.keys():
        if key > 300:
            useful_keys.append(key)

    useful_keys.sort()
    for key in useful_keys:
        tag = tags[key][0]
        if isinstance(tag, basestring):
            new_line = str(tag) + "\n"
            new_line = new_line.replace(":", ":\t", 1)
            result += new_line
    return result


def read_PIL_tiff_motors_info(image):
    """
    reads the file info from tif_tags and returns positions of vertical, horizontal, focus and omega motors
    """
    result = {}
    tags = image.tag

    useful_tags = ['Horizontal:', 'Vertical:', 'Focus:', 'Omega:']

    try:
        tag_values = tags.itervalues()
    except AttributeError:
        tag_values = tags.values()

    for value in tag_values:
        for key in useful_tags:
            if key in str(value):
                k, v = str(value[0]).split(':')
                result[str(k)] = float(v)
    return result
