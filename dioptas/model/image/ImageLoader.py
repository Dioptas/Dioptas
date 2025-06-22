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

import logging
import os
import numpy as np
from PIL import Image
import h5py
import fabio

from ..loader.spe import SpeFile
from ..loader.LambdaLoader import LambdaImage
from ..loader.KaraboLoader import KaraboFile
from ..loader.hdf5Loader import Hdf5Image
from ..loader.FabioLoader import FabioLoader

logger = logging.getLogger(__name__)


class ImageLoader:
    """
    Handles loading images from different file formats.
    Supports PIL, SPE, FabIO, Lambda, Karabo, and HDF5 formats.
    """

    def __init__(self):
        self.loader = None

    def get_image_data(self, filename, pos=0):
        """
        Tries to load the given file using different image loader libraries and returns a dictionary containing all
        retrieved file data.
        :param filename: string containing a path to an image file
        :param pos: position of image in the image file to be loaded
        :return: dictionary containing all retrieved file information. Look at "loadable data" for possible key names.
                 Present key names depend on applied image loader
        """
        img_loaders = [
            self.load_PIL,
            self.load_spe,
            self.load_fabio,
            self.load_lambda,
            self.load_karabo,
            self.load_hdf5,
        ]

        for loader in img_loaders:
            data = loader(filename, pos)
            if data:
                return data
        else:
            raise IOError("No handler found for given image with filename: " + filename)

    def load_PIL(self, filename, *args):
        """
        Loads an image using the PIL library. Also returns file and motor info if present
        :param filename: path to the image file to be loaded
        :return: dictionary with image_data and file_info and motors_info if present. None if unsuccessful
        """
        data = {}
        try:
            im = Image.open(filename)
            if np.prod(im.size) <= 1:
                im.close()
                return False
            data["img_data"] = np.array(im)[::-1]
            try:
                data["file_info"] = self._get_file_info(im)
                data["motors_info"] = self._get_motors_info(im)
            except AttributeError:
                pass
            im.close()
            return data

        except IOError:
            return None

    def load_spe(self, filename, *args):
        """
        Loads an image using the builtin spe library.
        :param filename: path to the image file to be loaded
        :return: dictionary with image_data, None if unsuccessful
        """
        if os.path.splitext(filename)[1].lower() == ".spe":
            spe = SpeFile(filename)
            return {"img_data": spe.img}
        else:
            return None

    def load_fabio(self, filename, frame_index=0):
        """
        Loads an image using the fabio library.
        :param filename: path to the image file to be loaded
        :param frame_index: frame index of the image file to be loaded inside of multi-frame file
        :return: dictionary with image_data and image_data_fabio, None if unsuccessful
        """
        try:
            self.loader = FabioLoader(filename)
            return {
                "img_data_fabio": self.loader.fabio_image,
                "img_data": self.loader.get_image(frame_index),
                "series_max": self.loader.series_max,
                "series_get_image": self.loader.get_image,
            }
        except (IOError, fabio.fabioutils.NotGoodReader):
            return None

    def load_lambda(self, filename, frame_index=0):
        """
        loads an image made by a lambda detector using the builtin lambda library.
        :param filename: path to the image file to be loaded
        :param frame_index: frame index of the image file to be loaded inside of multi-frame file
        :return: dictionary with img_data, series_max and series_get_image, None if unsuccessful
        """
        try:
            lambda_im = LambdaImage(filename)
        except IOError:
            return None

        if frame_index >= lambda_im.series_max:
            return None
        return {
            "img_data": lambda_im.get_image(frame_index),
            "series_max": lambda_im.series_max,
            "series_get_image": lambda_im.get_image,
        }

    def load_karabo(self, filename, frame_index=0):
        """
        Loads an Imageseries created from within the karabo-framework at XFEL.
        :param filename: path to the *.h5 karabo file
        :param frame_index: position of image in the image file to be loaded
        :return: dictionary with img_data of the first train_id, series_start, series_max and series_get_image,
                 None if unsuccessful
        """
        try:
            karabo_file = KaraboFile(filename)
        except IOError:
            return None
        if frame_index >= karabo_file.series_max:
            return None
        return {
            "img_data": karabo_file.get_image(frame_index),
            "series_max": karabo_file.series_max,
            "series_get_image": karabo_file.get_image,
        }

    def load_hdf5(self, filename, frame_index=0):
        """
        Loads an ESRF hdf5 file
        :param filename: filename with path to *.h5 ESRF file
        :param frame_index: frame index for multi-image file
        :return: dictionary with img_data of the first image in the first source, dataset_list, series_max, and
                 series_get_image
        """
        hdf5_image = Hdf5Image(filename)
        self.loader = hdf5_image
        return {
            "img_data": hdf5_image.get_image(frame_index),
            "series_max": hdf5_image.series_max,
            "series_get_image": hdf5_image.get_image,
            "sources": hdf5_image.image_sources,
            "select_source": hdf5_image.select_source,
        }

    def _get_file_info(self, image):
        """
        reads the file info from tif_tags and returns a file info
        """
        result = ""
        end_result = ""
        tags = image.tag
        useful_keys = []
        for key in tags.keys():
            if key > 300:
                useful_keys.append(key)

        useful_keys.sort()
        for key in useful_keys:
            tag = tags[key][0]
            if isinstance(tag, str):
                new_line = str(tag) + "\n"
                new_line = new_line.replace(":", ":\t", 1)
                if "TIFFImageDescription" in new_line:
                    end_result = new_line
                else:
                    result += new_line
        return result + end_result

    def _get_motors_info(self, image):
        """
        reads the file info from tif_tags and returns positions of vertical, horizontal, focus and omega motors
        """
        result = {}
        tags = image.tag

        useful_tags = ["Horizontal:", "Vertical:", "Focus:", "Omega:"]

        try:
            tag_values = tags.itervalues()
        except AttributeError:
            tag_values = tags.values()

        for value in tag_values:
            for key in useful_tags:
                if key in str(value):
                    k, v = str(value[0]).split(":")
                    result[str(k)] = float(v)
        return result 