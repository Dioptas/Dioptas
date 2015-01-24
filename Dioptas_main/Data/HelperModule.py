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

import numpy as np
import os
from PyQt4 import QtCore, QtGui
from stat import S_ISREG, ST_MTIME, ST_MODE, ST_CTIME
from copy import deepcopy
from colorsys import hsv_to_rgb

import time


# distinguishable_colors = np.loadtxt('Data/distinguishable_colors.txt')[::-1]


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
            self.acceptable_file_endings.append(self.filename.split('.')[-1])

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
        print('Time needed  for getting files: {0}s.'.format(time.time() - t1))
        return file_list

    def is_correct_file_type(self, filename):
        is_correct_ending = False
        for ending in self.acceptable_file_endings:
            if filename.endswith(ending):
                is_correct_ending = True
                break
        return is_correct_ending

    def _order_file_list(self):
        t1 = time.time()
        self.ordered_file_list = self.file_list
        self.ordered_file_list.sort(key=lambda x: x[0])

        print('Time needed  for ordering files: {0}s.'.format(time.time() - t1))

    def update_file_list(self):
        self.file_list = self._get_files_list()
        self._order_file_list()

    def get_next_filename(self, mode='number'):
        if self.complete_path is None:
            return None
        if mode == 'time':
            time_stat = os.path.getctime(self.complete_path)
            cur_ind = self.ordered_file_list.index((time_stat, self.complete_path))
            # cur_ind = self.ordered_file_list.index(self.complete_path)
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

    def get_previous_filename(self, mode='number'):
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
            time_stat = os.path.getctime(self.complete_path)
            cur_ind = self.ordered_file_list.index((time_stat, self.complete_path))
            # cur_ind = self.ordered_file_list.index(self.complete_path)
            if cur_ind > 0:
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
        try:
            self.acceptable_file_endings.append(file_str.split('.')[-1])
        except AttributeError:
            pass
        if self.directory != new_directory:
            if self.directory is not None:
                self.directory_watcher.removePath(self.directory)
            self.directory_watcher.addPath(new_directory)
            self.directory = new_directory
            if self.create_timed_file_list:
                self.update_file_list()

        if (self.create_timed_file_list and self.ordered_file_list == []):
            self.update_file_list()

    def add_new_files_to_list(self):
        """
        checks for new files in folder and adds them to the sorted_file_list
        :return:
        """
        cur_filename_list = os.listdir(self.directory)
        cur_filename_list = [os.path.join(self.directory, filename) for filename in cur_filename_list if
                             self.is_correct_file_type(filename)]
        new_filename_list = [filename for filename in cur_filename_list if filename not in list(self.filename_list)]
        self.filename_list = cur_filename_list
        for filename in new_filename_list:
            creation_time = os.path.getctime(filename)
            if len(self.ordered_file_list) > 0:
                if creation_time > self.ordered_file_list[-1][0]:
                    self.ordered_file_list.append((creation_time, filename))
                else:
                    for ind in xrange(len(self.ordered_file_list)):
                        if creation_time < self.ordered_file_list[ind][0]:
                            self.ordered_file_list.insert(ind, (creation_time, filename))
                            break
            else:
                self.ordered_file_list.append((creation_time, filename))


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
    h = (0.19 * (ind + 2)) % 1
    return np.array(hsv_to_rgb(h, s, v)) * 255


def gauss_function(x, int, hwhm, center):
    return int * np.exp(-(x - float(center)) ** 2 / (2 * hwhm ** 2))


def save_chi_file(filename, unit, x, y):
    file_handle = open(filename, 'w')
    num_points = len(x)

    file_handle.write(filename + '\n')
    file_handle.write(unit + '\n\n')
    file_handle.write("       {0}\n".format(num_points))
    for ind in xrange(num_points):
        file_handle.write(' {0:.7E}  {1:.7E}\n'.format(x[ind], y[ind]))
    file_handle.close()


def convert_d_to_two_theta(d, wavelength):
    return np.arcsin(wavelength / (2 * d)) / np.pi * 360


def calculate_cbn_absorption_correction(tth_array, azi_array,
                                        diamond_thickness, seat_thickness,
                                        small_cbn_seat_radius, large_cbn_seat_radius,
                                        tilt=0, tilt_rotation=0):
    #diam - diamond thickness
    #ds - seat thickness
    #r1 - small radius
    #r2 - large radius
    #tilt - tilting angle of DAC

    diam = diamond_thickness
    ds = seat_thickness
    r1 = small_cbn_seat_radius
    r2 = large_cbn_seat_radius
    tilt = -tilt

    t = tth_array
    a = azi_array

    scor = 0
    dtor = np.pi / 180.0

    # ;calculate 2-theta limit for seat
    ts1 = 180 / np.pi * np.arctan(r1 / diam)
    ts2 = 180 / np.pi * np.arctan(r2 / (diam + ds))
    tseat = 180 / np.pi * np.arctan((r2 - r1) / ds)
    tcell = 180 / np.pi * np.arctan(((19. - 7) / 2) / 15.)
    tc1 = 180 / np.pi * np.arctan((7. / 2) / (diam + ds))
    tc2 = 180 / np.pi * np.arctan((19. / 2) / (diam + ds + 10.))
    print 'ts1=', ts1, '  ts2=', ts2, '  tseat=', tseat, '   tcell=', tc1, tc2, tcell


    # rut=np.sqrt((1-np.tan(dtor*tilt)*np.cos(dtor*a))**2+(np.tan(dtor*tilt)*np.sin(dtor*a))**2)
    #
    # tt=t+180/np.pi*np.arctan(1.-rut)

    #my first version (equivalent to vitalis equations!!!
    # tt=np.abs(t+np.cos(np.pi/180.*a)*tilt)

    #final good version:
    tt = np.sqrt(t ** 2 + tilt ** 2 - 2 * t * tilt * np.cos(dtor * (a+tilt_rotation)))

    # ;absorption by diamond
    c = diam / np.cos(dtor * tt)
    ac = np.exp(-0.215680897 * 3.516 * c / 10)


    # ;absorption by conic part of seat
    if (ts2 >= ts1):
        deltar = (c * np.sin(dtor * tt) - r1).clip(min=0)
        cc = deltar * np.sin(dtor * (90 - tseat)) / np.sin(dtor * (tseat - tt.clip(max=ts2)))
        acc = np.exp(-(0.183873713 + 0.237310767) / 2 * 3.435 * cc / 10)
        accc = (acc - 1.) * (np.logical_and(tt >= ts1, tt <= ts2)) + 1
        # ;absorption by seat
        ccs = ds / np.cos(dtor * tt)
        accs = np.exp(-(0.183873713 + 0.237310767) / 2 * 3.435 * ccs / 10)
        accsc = (accs - 1.) * (tt >= ts2) + 1

    else:
        print 'in the else path'
        delta = ((diam + ds) * np.tan(dtor * tt) - r2).clip(min=0)

        cc = delta * np.sin(dtor * (90 + tseat)) / np.sin(dtor * (tt.clip(max < ts1) - tseat))

        acc = np.exp(-(0.183873713 + 0.237310767) / 2 * 3.435 * cc / 10)

        accc = (acc - 1.) * (np.logical_and(tt >= ts2, tt <= ts1)) + 1
        # ;absorption by seat
        ccs = ds / np.cos(dtor * tt)
        accs = np.exp(-(0.183873713 + 0.237310767) / 2 * 3.435 * ccs / 10)
        accsc = (accs - 1.) * (tt >= ts1) + 1
    cor = ac * accc * accsc

    return cor


if __name__ == '__main__':
    tth = np.linspace(0, 30, 1000)
    cor = calculate_cbn_absorption_correction(tth, 0, 2.3, 5.3, .4, 1.95)