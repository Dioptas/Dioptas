# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
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


class FileNameIterator(QtCore.QObject):
    # TODO create an File Index and then just get the next files according to this.
    # Otherwise searching a network is always to slow...
    file_added = QtCore.pyqtSignal(str)

    def __init__(self, filename=None):
        super(FileNameIterator, self).__init__()
        self.acceptable_file_endings = ['.img', '.sfrm', '.dm3', '.edf', '.xml',
                                       '.cbf', '.kccd', '.msk', '.spr', '.tif',
                                       '.mccd', '.mar3450', '.pnm']

        self.directory_watcher = QtCore.QFileSystemWatcher()
        self.directory_watcher.directoryChanged.connect(self.directory_changed)
        if  filename is None:
            self.complete_path = None
            self.directory = None
            self.filename = None
        else:
            self.complete_path = os.path.abspath(filename)
            self.directory, self.filename = os.path.split(self.complete_path)
            self.directory_watcher.addPath(self.directory)
            self._files_before = dict(
                [(f, None) for f in os.listdir(self.directory)])
            self._get_files_list()
            self._order_file_list()

    def _order_file_list(self):
        self.ordered_file_list = list(sorted(((stat[ST_CTIME], path)
                               for stat, path in self.file_list if S_ISREG(stat[ST_MODE]))))

    def _get_files_list(self):
        file_list = os.listdir(self.directory)
        files = []
        for file in file_list:
            is_correct_ending = False
            for ending in self.acceptable_file_endings:
                if file.endswith(ending):
                    is_correct_ending = True
                    break
            if is_correct_ending:
                files.append(file)
        paths = (os.path.join(self.directory, file) for file in files)
        self.file_list = ((os.stat(path), path) for path in paths)
        return self.file_list

    def get_next_filename(self,  mode='number'):
        if self.complete_path is None:
            return None
        if mode == 'time':
            time_stat = os.stat(self.complete_path)[ST_CTIME]
            cur_ind = self.ordered_file_list.index((time_stat, self.complete_path))
            try:
                self.complete_path = self.ordered_file_list[cur_ind + 1][1]
                return self.complete_path
            except IndexError:
                return None
        elif mode == 'number':
            directory, file_str = os.path.split(self.complete_path)
            filename, file_type_str = file_str.split('.')
            file_number_str = FileNameIterator._get_ending_number(filename)
            try:
                file_number = int(file_number_str)
            except ValueError:
                return None
            file_base_str = filename[:-len(file_number_str)]

            format_str = '0' + str(len(file_number_str)) + 'd'
            number_str = ("{0:" + format_str + '}').format(file_number + 1)
            new_file_name = file_base_str + number_str + '.' + file_type_str
            new_complete_path = os.path.join(directory, new_file_name)
            if os.path.exists(new_complete_path):
                self.complete_path = new_complete_path
                return new_complete_path
            return None


    def get_previous_filename(self,  mode='number'):
        """
        Tries to get the previous filename.

        :param mode:
            can have two values either number or mode. Number will decrement the last digits of the file name \
            and time will get the next file by creation time.
        :return:
            either new filename as a string if it exists or None
        """
        if self.complete_path is None:
            return None
        if mode == 'time':
            time_stat = os.stat(self.complete_path)[ST_CTIME]
            cur_ind = self.ordered_file_list.index((time_stat, self.complete_path))
            try:
                self.complete_path = self.ordered_file_list[cur_ind - 1][1]
                return self.complete_path
            except IndexError:
                return None
        elif mode == 'number':
            directory, file_str = os.path.split(self.complete_path)
            filename, file_type_str = file_str.split('.')
            file_number_str = FileNameIterator._get_ending_number(filename)
            try:
                file_number = int(file_number_str)
            except ValueError:
                return None
            file_base_str = filename[:-len(file_number_str)]
            format_str = '0' + str(len(file_number_str)) + 'd'
            number_str = ("{0:" + format_str + '}').format(file_number - 1)
            new_file_name = file_base_str + number_str + '.' + file_type_str

            new_complete_path = os.path.join(directory, new_file_name)
            if os.path.exists(new_complete_path):
                self.complete_path = new_complete_path
                return new_complete_path

            format_str = '0' + str(len(file_number_str) - 1) + 'd'
            number_str = ("{0:" + format_str + '}').format(file_number - 1)
            new_file_name = file_base_str + number_str + '.' + file_type_str

            new_complete_path = os.path.join(directory, new_file_name)
            if os.path.exists(new_complete_path):
                self.complete_path = new_complete_path
                return new_complete_path
            return None

    def update_filename(self, new_filename):

        self.complete_path = os.path.abspath(new_filename)
        new_directory, file_str = os.path.split(self.complete_path)

        if self.directory is not None:
            self.directory_watcher.removePath(self.directory)
            if self.directory == new_directory:
                return

        self.directory = new_directory
        self._files_before = dict(
            [(f, None) for f in os.listdir(self.directory)])
        self.directory_watcher.addPath(self.directory)
        self._get_files_list()
        self._order_file_list()


    def directory_changed(self, path):
        if self.complete_path is None:
            return
        self._get_files_list()
        self._order_file_list()

        self._files_now = dict(
            [(f, None) for f in os.listdir(self.working_dir['image'])])
        self._files_added = [
            f for f in self._files_now if not f in self._files_before]
        self._files_removed = [
            f for f in self._files_before if not f in self._files_now]
        if len(self._files_added) > 0:
            new_file_str = self._files_added[-1]
            path = os.path.join(self.working_dir['image'], new_file_str)

            read_file = False
            for ending in self.acceptable_file_endings:
                if path.endswith(ending):
                    read_file = True
                    break
            file_info = os.stat(path)
            if file_info.st_size > 100:
                if read_file:
                    self.file_added.emit(path)
                self._files_before = self._files_now



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
        :param disconnect_function:
            function for disconnecting the callback function
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
    h = (0.19 * (ind+2)) % 1
    return np.array(hsv_to_rgb(h, s, v)) * 255

def gauss_function(x,int,hwhm,center):
    return int*np.exp(-(x-float(center))**2/(2*hwhm**2))