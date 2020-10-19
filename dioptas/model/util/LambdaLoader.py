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


class LambdaImage:
    def __init__(self, filename):
        """
        Loads an image produced by a Lambda detector.
        :param filename: path to the image file to be loaded
        :return: dictionary with image_data, img_data_lambda and series_max, None if unsuccessful
        """
        detector_identifiers = [["/entry/instrument/detector/description", "Lambda"], ["/entry/instrument/detector/description", b"Lambda"]]
        filenumber_list = [1, 2, 3]
        regex_in = r"(.+_m)\d(.+nxs)"
        regex_out = r"\g<1>{}\g<2>"
        data_path = "entry/instrument/detector/data"
        module_positions_path = "/entry/instrument/detector/translation/distance"

        try:
            nx_file = h5py.File(filename, "r")
        except OSError:
            raise IOError("not a loadable hdf5 file")

        for identifier in detector_identifiers:
            try:
                if nx_file[identifier[0]][0] == identifier[1]:
                    break
            except KeyError:
                pass
        else:
            raise IOError("not a lambda image")


        # the image data is spread over multiple files, so we compile a list of them here
        lambda_files = []

        for moduleIndex in filenumber_list:
            try:
                lambda_files.append(h5py.File(re.sub(regex_in, regex_out.format(moduleIndex), filename), "r"))
            except OSError:
                pass

        self.full_img_data = [imageFile[data_path] for imageFile in lambda_files]

        self._module_pos = np.array([np.ravel(nxim[module_positions_path]).astype(int) for nxim in lambda_files])

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
        # the empty array needs to have the width of the detector data for concatenate()
        image = np.empty((0, self.full_img_data[-1].shape[-1] + self._module_pos[:, 0].max()))

        for modulenr, moduleImageData in enumerate(self.full_img_data):
            # generate empty columns to the left and right of the data to match with the others
            imagedata = np.concatenate([np.zeros((moduleImageData.shape[1], self._module_pos[modulenr, 0])),
                                        moduleImageData[image_nr],
                                        np.zeros((moduleImageData.shape[1], self._module_pos[:, 0].max() - self._module_pos[modulenr, 0]))], axis=1)

            image = np.concatenate(
                [image,
                 np.zeros((
                     # generate as many empty rows as needed to get to the position where the module data wants to be
                     int(self._module_pos[modulenr, 1]) -
                     image.shape[0],
                     moduleImageData.shape[-1] + self._module_pos[:, 0].max())),
                 imagedata])  # append the actual new image data

        return image[::-1]
