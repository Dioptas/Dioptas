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


import os
import re
import time

import numpy as np
from qtpy import QtCore
from colorsys import hsv_to_rgb


class FileNameIterator(QtCore.QObject):
    # TODO create an File Index and then just get the next files according to this.
    # Otherwise searching a network is always to slow...

    def __init__(self, filename=None):
        super(FileNameIterator, self).__init__()
        self.acceptable_file_endings = []
        self.directory_watcher = QtCore.QFileSystemWatcher()
        self.directory_watcher.directoryChanged.connect(self.add_new_files_to_list)
        self.create_timed_file_list = False

        if filename is None:
            self.complete_path = None
            self.directory = None
            self.filename = None
            self.file_list = []
            self.ordered_file_list = []
            self.filename_list = []
        else:
            self.complete_path = os.path.abspath(filename)
            self.directory, self.filename = os.path.split(self.complete_path)
            self.acceptable_file_endings.append(self.filename.split(".")[-1])

    def _get_files_list(self):
        t1 = time.time()
        filename_list = os.listdir(self.directory)
        files = []
        for file in filename_list:
            if self.is_correct_file_type(file):
                files.append(file)
        paths = [os.path.join(self.directory, file) for file in files]
        file_list = [(os.path.getctime(path), path) for path in paths]
        self.filename_list = paths
        print("Time needed  for getting files: {0}s.".format(time.time() - t1))
        return file_list

    def is_correct_file_type(self, filename):
        for ending in self.acceptable_file_endings:
            if filename.endswith(ending):
                return True
        return False

    def _order_file_list(self):
        t1 = time.time()
        self.ordered_file_list = self.file_list
        self.ordered_file_list.sort(key=lambda x: x[0])

        print("Time needed  for ordering files: {0}s.".format(time.time() - t1))

    def update_file_list(self):
        self.file_list = self._get_files_list()
        self._order_file_list()

    def _iterate_file_number(self, path, step, pos=None):
        directory, file_str = os.path.split(path)
        pattern = re.compile(r"\d+")

        match_iterator = pattern.finditer(file_str)

        for ind, match in enumerate(reversed(list(match_iterator))):
            if (pos is None) or (ind == pos):
                number_span = match.span()
                left_ind = number_span[0]
                right_ind = number_span[1]
                number = int(file_str[left_ind:right_ind]) + step
                new_file_str = "{left_str}{number:0{len}}{right_str}".format(
                    left_str=file_str[:left_ind],
                    number=number,
                    len=right_ind - left_ind,
                    right_str=file_str[right_ind:],
                )
                new_file_str_no_leading_zeros = "{left_str}{number}{right_str}".format(
                    left_str=file_str[:left_ind],
                    number=number,
                    right_str=file_str[right_ind:],
                )
                new_complete_path = os.path.join(directory, new_file_str)
                if os.path.exists(new_complete_path):
                    self.complete_path = new_complete_path
                    return new_complete_path
                new_complete_path = os.path.join(
                    directory, new_file_str_no_leading_zeros
                )
                if os.path.exists(new_complete_path):
                    self.complete_path = new_complete_path
                    return new_complete_path
        return None

    def _iterate_folder_number(self, path, step, mec_mode=False):
        directory_str, file_str = os.path.split(path)
        pattern = re.compile(r"\d+")

        match_iterator = pattern.finditer(directory_str)

        for ind, match in enumerate(reversed(list(match_iterator))):
            number_span = match.span()
            left_ind = number_span[0]
            right_ind = number_span[1]
            number = int(directory_str[left_ind:right_ind]) + step
            new_directory_str = "{left_str}{number:0{len}}{right_str}".format(
                left_str=directory_str[:left_ind],
                number=number,
                len=right_ind - left_ind,
                right_str=directory_str[right_ind:],
            )
            print(mec_mode)
            if mec_mode:
                match_file_iterator = pattern.finditer(file_str)
                for ind_file, match_file in enumerate(
                    reversed(list(match_file_iterator))
                ):
                    if ind_file != 2:
                        continue
                    number_span = match_file.span()
                    left_ind = number_span[0]
                    right_ind = number_span[1]
                    number = int(file_str[left_ind:right_ind]) + step
                    new_file_str = "{left_str}{number:0{len}}{right_str}".format(
                        left_str=file_str[:left_ind],
                        number=number,
                        len=right_ind - left_ind,
                        right_str=file_str[right_ind:],
                    )
                new_complete_path = os.path.join(new_directory_str, new_file_str)
                print(new_complete_path)
            else:
                new_complete_path = os.path.join(new_directory_str, file_str)
            if os.path.exists(new_complete_path):
                self.complete_path = new_complete_path
                return new_complete_path

    def get_next_filename(self, step=1, filename=None, mode="number", pos=None):
        if filename is not None:
            self.complete_path = filename

        if self.complete_path is None:
            return None

        if mode == "time":
            time_stat = os.path.getctime(self.complete_path)
            cur_ind = self.ordered_file_list.index((time_stat, self.complete_path))
            # cur_ind = self.ordered_file_list.index(self.complete_path)
            try:
                self.complete_path = self.ordered_file_list[cur_ind + step][1]
                return self.complete_path
            except IndexError:
                return None
        elif mode == "number":
            return self._iterate_file_number(self.complete_path, step, pos)

    def get_previous_filename(self, step=1, filename=None, mode="number", pos=None):
        """
        Tries to get the previous filename.

        :param step:
        :param pos:
        :param mode:
            can have two values either number or mode. Number will decrement the last digits of the file name \
            and time will get the next file by creation time.
        :param filename:
            Filename to get previous number from
        :return:
            either new filename as a string if it exists or None
        """
        if filename is not None:
            self.complete_path = filename

        if self.complete_path is None:
            return None

        if mode == "time":
            time_stat = os.path.getctime(self.complete_path)
            cur_ind = self.ordered_file_list.index((time_stat, self.complete_path))
            # cur_ind = self.ordered_file_list.index(self.complete_path)
            if cur_ind > 0:
                try:
                    self.complete_path = self.ordered_file_list[cur_ind - step][1]
                    return self.complete_path
                except IndexError:
                    return None
        elif mode == "number":
            return self._iterate_file_number(self.complete_path, -step, pos)

    def get_next_folder(self, filename=None, mec_mode=False):
        if filename is not None:
            self.complete_path = filename

        if self.complete_path is None:
            return None
        return self._iterate_folder_number(self.complete_path, 1, mec_mode)

    def get_previous_folder(self, filename=None, mec_mode=False):
        if filename is not None:
            self.complete_path = filename

        if self.complete_path is None:
            return None
        return self._iterate_folder_number(self.complete_path, -1, mec_mode)

    def update_filename(self, new_filename):
        self.complete_path = os.path.abspath(new_filename)
        new_directory, file_str = os.path.split(self.complete_path)
        try:
            self.acceptable_file_endings.append(file_str.split(".")[-1])
        except AttributeError:
            pass
        if self.directory != new_directory:
            if self.directory is not None and self.directory != "":
                self.directory_watcher.removePath(self.directory)
            self.directory_watcher.addPath(new_directory)
            self.directory = new_directory
            if self.create_timed_file_list:
                self.update_file_list()

        if self.create_timed_file_list and self.ordered_file_list == []:
            self.update_file_list()

    def add_new_files_to_list(self):
        """
        checks for new files in folder and adds them to the sorted_file_list
        :return:
        """
        cur_filename_list = os.listdir(self.directory)
        cur_filename_list = [
            os.path.join(self.directory, filename)
            for filename in cur_filename_list
            if self.is_correct_file_type(filename)
        ]
        new_filename_list = [
            filename
            for filename in cur_filename_list
            if filename not in list(self.filename_list)
        ]
        self.filename_list = cur_filename_list
        for filename in new_filename_list:
            creation_time = os.path.getctime(filename)
            if len(self.ordered_file_list) > 0:
                if creation_time > self.ordered_file_list[-1][0]:
                    self.ordered_file_list.append((creation_time, filename))
                else:
                    for ind in range(len(self.ordered_file_list)):
                        if creation_time < self.ordered_file_list[ind][0]:
                            self.ordered_file_list.insert(
                                ind, (creation_time, filename)
                            )
                            break
            else:
                self.ordered_file_list.append((creation_time, filename))


def rotate_matrix_m90(matrix):
    return np.rot90(matrix, -1)


def rotate_matrix_p90(matrix):
    return np.rot90(matrix)


def get_base_name(filename):
    str = os.path.basename(filename)
    if "." in str:
        str = str.split(".")[:-1][0]
    return str


def calculate_color(ind):
    s = 0.8
    v = 0.8
    h = (0.19 * (ind + 2)) % 1
    return np.array(hsv_to_rgb(h, s, v)) * 255


def rgb_to_hex(rgb):
    return "#%02x%02x%02x" % (int(rgb[0]), int(rgb[1]), int(rgb[2]))


def convert_d_to_two_theta(d, wavelength):
    return np.arcsin(wavelength / (2 * d)) / np.pi * 360


def get_partial_index(array, value):
    """
    Calculates the partial index for a value from an array using linear interpolation.
    e.g. with array = [0,1,2,3,4,5] and value = 2.5 it would return 2.5, since it in between the second and third
    element.
    :param array: list or numpy array
    :param value: value for which to get the index
    :return: partial index
    """
    try:
        upper_ind = np.where(array >= value)[0]
        lower_ind = np.where(array < value)[0]
    except TypeError:
        return None

    try:
        spacing = array[upper_ind[0]] - array[lower_ind[-1]]
        new_pos = lower_ind[-1] + (value - array[lower_ind[-1]]) / spacing
    except IndexError:
        return None

    return new_pos


def get_partial_value(array, ind):
    """
    Calculates the value for a non-integer array from an array using linear interpolation.
    e.g. with array = [0,2,4,6,8,10] and value = 2.5 it would return 5, since it is in between the second and third
    element.
    :param array: list or numpy array
    :param ind: float index for which to get value
    """
    if ind < 0 or ind > len(array):
        return None

    step = array[int(np.floor(ind)) + 1] - array[int(np.floor(ind))]
    value = array[int(np.floor(ind))] + (ind - np.floor(ind)) * step
    return value


def reverse_interpolate_two_array(
    value1, array1, value2, array2, delta1=0.1, delta2=0.1
):
    """
    Tries to reverse interpolate two vales from two arrays with the same dimensions, and finds a common index
    for value1 and value2 in their respective arrays. the deltas define the search radius for a close value match
    to the arrays.

    :return: index1, index2
    """
    tth_ind = np.argwhere(np.abs(array1 - value1) < delta1)
    azi_ind = np.argwhere(np.abs(array2 - value2) < delta2)

    tth_ind_ravel = np.ravel_multi_index(
        (tth_ind[:, 0], tth_ind[:, 1]), dims=array1.shape
    )
    azi_ind_ravel = np.ravel_multi_index(
        (azi_ind[:, 0], azi_ind[:, 1]), dims=array2.shape
    )

    common_ind_ravel = np.intersect1d(tth_ind_ravel, azi_ind_ravel)
    result_ind = np.unravel_index(common_ind_ravel, dims=array1.shape)

    while len(result_ind[0]) > 1:
        if np.max(np.diff(array1)) > 0:
            delta1 = np.max(np.diff(array1[result_ind]))

        if np.max(np.diff(array2)) > 0:
            delta2 = np.max(np.diff(array2[result_ind]))

        tth_ind = np.argwhere(np.abs(array1[result_ind] - value1) < delta1)
        azi_ind = np.argwhere(np.abs(array2[result_ind] - value2) < delta2)

        print(result_ind)

        common_ind = np.intersect1d(tth_ind, azi_ind)
        result_ind = (result_ind[0][common_ind], result_ind[1][common_ind])

    return result_ind[0], result_ind[1]
