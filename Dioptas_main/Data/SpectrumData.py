# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
#     Copyright (C) 2014  Clemens Prescher (clemens.prescher@gmail.com)
#     GSECARS, University of Chicago
#
#     This program is free software: you can redistribute it and/or modify
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
from copy import deepcopy
from .HelperModule import Observable, FileNameIterator, get_base_name


class SpectrumData(Observable):
    def __init__(self):
        Observable.__init__(self)
        self.spectrum = Spectrum()
        self.overlays = []
        self.phases = []

        self.file_iteration_mode = 'number'
        self.bkg_ind = -1
        self.spectrum_filename = ''

    def set_spectrum(self, x, y, filename=''):
        self.spectrum_filename = filename
        self.spectrum.data = (x, y)
        self.spectrum.name = get_base_name(filename)
        self.notify()

    def load_spectrum(self, filename):
        self.spectrum_filename = filename
        self.spectrum.load(filename)
        self.notify()

    def load_next(self):
        next_file_name = FileNameIterator.get_next_filename(self.spectrum_filename, self.file_iteration_mode)
        if next_file_name is not None:
            self.load_spectrum(next_file_name)

    def load_previous(self):
        previous_file_name = FileNameIterator.get_previous_filename(self.spectrum_filename, self.file_iteration_mode)
        if previous_file_name is not None:
            self.load_spectrum(previous_file_name)

    def add_overlay(self, x, y, name=''):
        self.overlays.append(Spectrum(x, y, name))
        self.notify()

    def set_current_spectrum_as_overlay(self):
        self.overlays.append(deepcopy(self.spectrum))
        self.notify()

    def add_overlay_file(self, filename):
        self.overlays.append(Spectrum())
        self.overlays[-1].load(filename)
        self.notify()

    def del_overlay(self, ind):
        del self.overlays[ind]

    def set_file_iteration_mode(self, mode):
        """
        The file iteration_mode determines how to browse between files in a specific folder:
        possible values:
        'number'    - browsing by ending number (like in file_001.txt)
        'time'      - browsing by data of creation
        """
        if not (mode is 'number' or mode is 'time'):
            return -1
        else:
            self.mode = mode


class Spectrum(object):
    def __init__(self, x=None, y=None, name=''):
        if x is None:
            self._x = np.linspace(0, 15, 100)
        else:
            self._x = x
        if y is None:
            self._y = np.log(self._x ** 2)
        else:
            self._y = y
        self.name = name
        self.offset = 0
        self._scaling = 1
        self.bkg_spectrum = None

    def load(self, filename, skiprows=4):
        try:
            data = np.loadtxt(filename, skiprows=skiprows)
            self._x = data.T[0]
            self._y = data.T[1]
            self.name = os.path.basename(filename).split('.')[:-1][0]

        except ValueError:
            print('Wrong data format for spectrum file!')
            return -1

    def save(self, filename, header=''):
        data = np.dstack((self._x, self._y))
        np.savetxt(filename, data[0], header=header)

    def set_background(self, spectrum):
        self.bkg_spectrum = spectrum

    def reset_background(self):
        self.bkg_spectrum = None

    @property
    def data(self):
        if self.bkg_spectrum is not None:
            _, y_bkg = self.bkg_spectrum.data
            return self._x, self._y * self._scaling + self.offset - y_bkg
        else:
            return self.original_data


    @data.setter
    def data(self, xxx_todo_changeme):
        (x, y) = xxx_todo_changeme
        self._x = x
        self._y = y
        self.scaling = 1
        self.offset = 0

    @property
    def original_data(self):
        return self._x, self._y * self._scaling + self.offset

    @property
    def scaling(self):
        return self._scaling

    @scaling.setter
    def scaling(self, value):
        if value < 0:
            self._scaling = 0
        else:
            self._scaling = value


def test():
    my_spectrum = Spectrum()
    my_spectrum.save('test.txt')


if __name__ == '__main__':
    test()

