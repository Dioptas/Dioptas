# -*- coding: utf8 -*-
# Py2DeX - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2014  Clemens Prescher (clemens.prescher@gmail.com)
# GSECARS, University of Chicago
#
# This program is free software: you can redistribute it and/or modify
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

import numpy as np
import os
from PyQt4 import QtCore, QtGui
from stat import S_ISREG, ST_CTIME, ST_MODE
from colorsys import hsv_to_rgb
import time

#distinguishable_colors = np.loadtxt('Data/distinguishable_colors.txt')[::-1]


class Observable(object):
    def __init__(self):
        self.observer = []
        self.notification = True

    def subscribe(self, function):
        self.observer.append(function)

    def unsubscribe(self, function):
        try:
            self.observer.remove(function)
        except ValueError:
            pass

    def notify(self):
        if self.notification:
            for observer in self.observer:
                observer()

    def turn_off_notification(self):
        self.notification = False

    def turn_on_notification(self):
        self.notification = True


class FileNameIterator(object):
    # TODO create an File Index and then just get the next files according to this.
    # Otherwise searching a network is always to slow...

    @staticmethod
    def get_next_filename(filepath, mode='number'):
        complete_path = os.path.abspath(filepath)
        directory, file_str = os.path.split(complete_path)
        filename, file_type_str = file_str.split('.')

        if mode == 'number':
            file_number_str = FileNameIterator._get_ending_number(filename)
            file_number = int(file_number_str)
            file_base_str = filename[:-len(file_number_str)]

            format_str = '0' + str(len(file_number_str)) + 'd'
            number_str = ("{0:" + format_str + '}').format(file_number + 1)
            new_file_name = file_base_str + number_str + '.' + file_type_str
            new_complete_path = os.path.join(directory, new_file_name)
            if os.path.exists(new_complete_path):
                return new_complete_path
        elif mode == 'time':
            files_list = os.listdir(directory)
            files = []
            for file in files_list:
                if file.endswith(file_type_str):
                    files.append(file)

            paths = (os.path.join(directory, file) for file in files)
            entries = ((os.stat(path), path) for path in paths)

            entries = list(sorted(((stat[ST_CTIME], path)
                                   for stat, path in entries if S_ISREG(stat[ST_MODE]))))

            for ind, entry in enumerate(entries):
                if entry[1] == complete_path:
                    try:
                        return entries[ind + 1][1]
                    except IndexError:
                        return None


    @staticmethod
    def get_previous_filename(filepath, mode='number'):
        complete_path = os.path.abspath(filepath)
        directory, file_str = os.path.split(complete_path)
        filename, file_type_str = file_str.split('.')

        file_number_str = FileNameIterator._get_ending_number(filename)
        file_number = int(file_number_str)
        file_base_str = filename[:-len(file_number_str)]

        if mode == 'number':
            format_str = '0' + str(len(file_number_str)) + 'd'
            number_str = ("{0:" + format_str + '}').format(file_number - 1)
            new_file_name = file_base_str + number_str + '.' + file_type_str

            new_complete_path = os.path.join(directory, new_file_name)
            if os.path.exists(new_complete_path):
                return new_complete_path

            format_str = '0' + str(len(file_number_str) - 1) + 'd'
            number_str = ("{0:" + format_str + '}').format(file_number - 1)
            new_file_name = file_base_str + number_str + '.' + file_type_str

            new_complete_path = os.path.join(directory, new_file_name)
            if os.path.exists(new_complete_path):
                return new_complete_path

        elif mode == 'time':
            files_list = os.listdir(directory)
            files = []
            for file in files_list:
                if file.endswith(file_type_str):
                    files.append(file)

            paths = (os.path.join(directory, file) for file in files)
            entries = ((os.stat(path), path) for path in paths)

            entries = list(sorted(((stat[ST_CTIME], path)
                                   for stat, path in entries if S_ISREG(stat[ST_MODE]))))

            for ind, entry in enumerate(entries):
                if entry[1] == complete_path and ind is not 0:
                    return entries[ind - 1][1]

    @staticmethod
    def _get_ending_number(basename):
        res = ''
        for char in reversed(basename):
            if char.isdigit():
                res += char
            else:
                return res[::-1]


class SignalFrequencyLimiter(object):
    def __init__(self, connect_function, callback_function, time=100, disconnect_function=None):
        """
        Limits the frequency of callback_function calls.

        :param connect_function:
            function which connects the callback to the signal. For qt signal it would be "signal.connect"
        :param callback_function:
            callback function responding to the signal
        :param time:
            time in milliseconds between each new callback_function call
        """
        self.connect_function = connect_function
        self.disconnect_function = disconnect_function
        self.callback_function = callback_function
        self.update_timer = QtCore.QTimer()
        self.update_timer.setInterval(time)
        self.update_timer.timeout.connect(self.timer_function)
        self.connect_function(self.update_vars)
        self.update_function = None
        self.update_timer.start(time)

    def update_vars(self, *args):
        self.vars = args
        self.update_function = self.callback_function

    def timer_function(self):
        if self.update_function is not None:
            if self.disconnect_function is not None:
                self.disconnect_function(self.update_vars)
            self.update_function(*self.vars)
            self.update_function = None
            if self.disconnect_function is not None:
                self.connect_function(self.update_vars)


def rotate_matrix_m90(matrix):
    return np.rot90(matrix, -1)


def rotate_matrix_p90(matrix):
    return np.rot90(matrix)


def get_base_name(filename):
    str = os.path.basename(filename)
    if '.' in str:
        str = str.split('.')[:-1][0]
    return str


def calculate_color(ind):
    s = 0.8
    v = 0.8
    h = (0.19 * ind) % 1
    return np.array(hsv_to_rgb(h, s, v)) * 255