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

import h5py
import hdf5plugin


class Hdf5Image:
    def __init__(self, filename):
        """
        Loads an Hdf5 image produced by ESRF
        :param filename: path to the hdf5 file to be loaded
        """

        self.f = h5py.File(filename, 'r')
        self.image_sources = find_image_sources(self.f)

        self.__current_source = self.image_sources[0]
        self.series_max = self.f[self.__current_source].shape[0]

    def get_image(self, ind):
        return self.f[self.__current_source][ind]

    def select_source(self, source):
        self.__current_source = source
        self.series_max = self.f[source].shape[0]


def find_image_sources(hd5_file):
    image_paths = []

    def traverse_groups(group, parent_path=''):
        if isinstance(group, h5py.Dataset):
            if len(group.shape) >= 3:
                image_paths.append(parent_path)
        else:  # node is a group
            for key in group.keys():
                traverse_groups(group[key], parent_path + '/' + key)

    traverse_groups(hd5_file)

    return image_paths
