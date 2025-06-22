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
import h5py
import re


def first(array):
    """  get first element if the only

    :param array: numpy array
    :type array: :class:`numpy.ndarray`
    :returns: first element of the array
    :type array: :obj:`any`
    """
    try:
        if isinstance(array, np.ndarray) and len(array) == 1:
            return array[0]
    except Exception:
        pass
    return array[...]


class LambdaImage:
    def __init__(self, filename=None, file_list=None):
        """
        Loads an image produced by a Lambda detector.
        :param filename: path to the image file to be loaded
        :return: dictionary with image_data, img_data_lambda and series_max, None if unsuccessful
        """
        detector_identifiers = [["/entry/instrument/detector/description", "Lambda"],
                                ["/entry/instrument/detector/description", b"Lambda"]]
        filenumber_list = [1, 2, 3]
        regex_in = r"(.+_m)\d((_part\d+|).nxs)"
        regex_out = r"\g<1>{}\g<2>"
        data_path = "entry/instrument/detector/data"
        module_positions_path = "/entry/instrument/detector/translation/distance"

        if not filename:
            filename = file_list[0]

        try:
            nx_file = h5py.File(filename, "r")
        except OSError:
            raise IOError("not a loadable hdf5 file")

        for identifier in detector_identifiers:
            try:
                if first(nx_file[identifier[0]]) == identifier[1]:
                    break
            except KeyError:
                pass
        else:
            raise IOError("not a lambda image")

        # the image data is spread over multiple files, so we compile a list of them here
        lambda_files = []
        if file_list:
            for f_name in file_list:
                try:
                    lambda_files.append(h5py.File(f_name, "r"))
                except OSError:
                    pass
        else:
            for moduleIndex in filenumber_list:
                try:
                    lambda_files.append(h5py.File(re.sub(regex_in, regex_out.format(moduleIndex), filename), "r"))
                except OSError:
                    pass

        self.file_list = file_list
        self.full_img_data = [imageFile[data_path] for imageFile in lambda_files]
        self.shapes = np.array([module[0].shape for module in self.full_img_data])
        self._module_pos = np.array([np.ravel(nxim[module_positions_path]).astype(int) for nxim in lambda_files])
        self.img_idx = lambda_files[0]['entry/instrument/detector/sequence_number']

        # remove any empty columns/rows to the left or top of the image data or shift any negative rows/columns into the positive
        np.subtract(self._module_pos, self._module_pos[:, 0].min(), self._module_pos, where=[1, 0, 0])
        np.subtract(self._module_pos, self._module_pos[0][1], self._module_pos, where=[0, 1, 0])
        self.series_max = lambda_files[0][data_path].shape[0]

    def get_image(self, image_nr):
        """
        Gets the data for the given image nr and stitches the tiles together
        :param image_nr: position from which to take the image from the image set
        :return: image_data
        """

        tmp = self.shapes + self._module_pos[:, :2][:, ::-1]
        shape = (np.max(tmp[:, 0]), np.max(tmp[:, 1]))
        image = np.zeros(shape)

        for modulenr, moduleImageData in enumerate(self.full_img_data):
            image[self._module_pos[modulenr, 1]:self._module_pos[modulenr, 1] + self.shapes[modulenr][0],
            self._module_pos[modulenr, 0]:self._module_pos[modulenr, 0] + self.shapes[modulenr][1]] = moduleImageData[
                image_nr]

        return image[::-1]
