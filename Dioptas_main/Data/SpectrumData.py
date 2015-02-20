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

import logging

logger = logging.getLogger(__name__)

import os
import numpy as np
from scipy.interpolate import interp1d
from copy import deepcopy
from PyQt4 import QtCore

from .HelperModule import FileNameIterator, get_base_name


class SpectrumData(QtCore.QObject):
    """
    Main Spectrum handling class. Supporting several features:
      - loading spectra from any tabular source (readable by numpy)
      - having overlays
      - setting overlays as background
      - spectra and overlays can be scaled and have offset values

    all changes to the internal data throw pyqtSignals.
    """
    spectrum_changed = QtCore.pyqtSignal()
    overlay_changed = QtCore.pyqtSignal(int)  # changed index
    overlay_added = QtCore.pyqtSignal()
    overlay_removed = QtCore.pyqtSignal(int)  # removed index
    overlay_set_as_bkg = QtCore.pyqtSignal(int)  # index set as background
    overlay_unset_as_bkg = QtCore.pyqtSignal(int)  # index unset os background

    def __init__(self):
        super(SpectrumData, self).__init__()
        self.spectrum = Spectrum()
        self.overlays = []
        self.phases = []

        self.file_iteration_mode = 'number'
        self.file_name_iterator = FileNameIterator()

        self.bkg_ind = -1
        self.spectrum_filename = ''

    def set_spectrum(self, x, y, filename='', unit=''):
        """
        set the current data spectrum.
        :param x: x-values
        :param y: y-values
        :param filename: name for the spectrum, defaults to ''
        :param unit: unit for the x values
        """
        self.spectrum_filename = filename
        self.spectrum.data = (x, y)
        self.spectrum.name = get_base_name(filename)
        self.unit = unit
        self.spectrum_changed.emit()

    def load_spectrum(self, filename):
        """
        Loads a spectrum from a tabular spectrum file (2 column txt file)
        :param filename: filename of the data file
        """
        logger.info("Load spectrum: {0}".format(filename))
        self.spectrum_filename = filename

        skiprows = 0
        if filename.endswith('.chi'):
            skiprows = 4
        self.spectrum.load(filename, skiprows)
        self.file_name_iterator.update_filename(filename)
        self.spectrum_changed.emit()

    def save_spectrum(self, filename, header=None, subtract_background=False):
        """
        Saves the current data spectrum.
        :param filename: where to save
        :param header: you can specify any specific header
        :param subtract_background: whether or not the background set will be used for saving or not
        """
        if subtract_background:
            x, y = self.spectrum.data
        else:
            x, y = self.spectrum._x, self.spectrum._y

        file_handle = open(filename, 'w')
        num_points = len(x)

        if filename.endswith('.chi'):
            if header is None or header == '':
                file_handle.write(filename + '\n')
                file_handle.write(self.unit + '\n\n')
                file_handle.write("       {0}\n".format(num_points))
            else:
                file_handle.write(header)
            for ind in xrange(num_points):
                file_handle.write(' {0:.7E}  {1:.7E}\n'.format(x[ind], y[ind]))
        else:
            if header is not None:
                file_handle.write(header)
                file_handle.write('\n')
            for ind in xrange(num_points):
                file_handle.write('{0:.9E}  {1:.9E}\n'.format(x[ind], y[ind]))
        file_handle.close()

    def load_next_file(self):
        """
        Loads the next file from a sequel of filenames (e.g. *_001.xy --> *_002.xy)
        It assumes that the file numbers are at the end of the filename
        """
        next_file_name = self.file_name_iterator.get_next_filename(self.file_iteration_mode)
        if next_file_name is not None:
            self.load_spectrum(next_file_name)
            return True
        return False

    def load_previous_file(self):
        """
        Loads the previous file from a sequel of filenames (e.g. *_002.xy --> *_001.xy)
        It assumes that the file numbers are at the end of the filename
        """
        next_file_name = self.file_name_iterator.get_previous_filename(self.file_iteration_mode)
        if next_file_name is not None:
            self.load_spectrum(next_file_name)
            return True
        return False

    def set_file_iteration_mode(self, mode):
        if mode == 'number':
            self.file_iteration_mode = 'number'
            self.file_name_iterator.create_timed_file_list = False
        elif mode == 'time':
            self.file_iteration_mode = 'time'
            self.file_name_iterator.create_timed_file_list = True
            self.file_name_iterator.update_filename(self.filename)

    def add_overlay(self, x, y, name=''):
        """
        Adds an overlay to the list of overlays
        :param x: x-values
        :param y: y-values
        :param name: name of overlay to be used for displaying etc.
        """
        self.overlays.append(Spectrum(x, y, name))
        self.overlay_added.emit()

    def remove_overlay(self, ind):
        """
        Removes an overlay from the list of overlays
        :param ind: index of the overlay
        """
        if ind >= 0:
            del self.overlays[ind]
            if self.bkg_ind > ind:
                self.bkg_ind -= 1
            elif self.bkg_ind == ind:
                self.spectrum.reset_background()
                self.bkg_ind = -1
                self.spectrum_changed.emit()
            self.overlay_removed.emit(ind)

    def add_spectrum_as_overlay(self):
        """
        Adds the current data spectrum as overlay to the list of overlays
        """
        self.overlays.append(deepcopy(self.spectrum))
        self.overlay_added.emit()

    def add_overlay_file(self, filename):
        """
        Reads a 2-column (x,y) text file and adds it as overlay to the list of overlays
        :param filename: path of the file to be loaded
        """
        self.overlays.append(Spectrum())
        self.overlays[-1].load(filename)
        self.overlay_added.emit()

    def get_overlay_name(self, ind):
        """
        :param ind: overlay index
        """
        return self.overlays[-1].name

    def set_overlay_scaling(self, ind, scaling):
        """
        Sets the scaling of the specified overlay
        :param ind: index of the overlay
        :param scaling: new scaling value
        """
        self.overlays[ind].scaling = scaling
        self.overlay_changed.emit(ind)
        if self.bkg_ind == ind:
            self.spectrum_changed.emit()

    def get_overlay_scaling(self, ind):
        """
        Returns the scaling of the specified overlay
        :param ind: index of the overlay
        :return: scaling value
        """
        return self.overlays[ind].scaling

    def set_overlay_offset(self, ind, offset):
        """
        Sets the offset of the specified overlay
        :param ind: index of the overlay
        :param offset: new offset value
        """
        self.overlays[ind].offset = offset
        self.overlay_changed.emit(ind)
        if self.bkg_ind == ind:
            self.spectrum_changed.emit()

    def get_overlay_offset(self, ind):
        """
        Return the offset of the specified overlay
        :param ind: index of the overlay
        :return: overlay value
        """
        return self.overlays[ind].offset

    def set_overlay_as_bkg(self, ind):
        """
        Sets an overlay as background for the data spectrum, and unsets any previously used background
        :param ind: index of the overlay
        """
        if self.bkg_ind >= 0:
            self.unset_overlay_as_bkg()
        self.bkg_ind = ind
        self.spectrum.set_background(self.overlays[ind])
        self.spectrum_changed.emit()
        self.overlay_set_as_bkg.emit(ind)

    def set_spectrum_as_bkg(self):
        """
        Adds the current spectrum as Overlay and sets it as background spectrum and unsets any previously used
        background.
        """
        self.add_spectrum_as_overlay()
        self.set_overlay_as_bkg(len(self.overlays) - 1)

    def unset_overlay_as_bkg(self):
        """
        Unsets the currently used background overlay.
        """
        previous_bkg_ind = self.bkg_ind
        self.bkg_ind = -1
        self.spectrum.reset_background()
        self.spectrum_changed.emit()
        self.overlay_unset_as_bkg.emit(previous_bkg_ind)

    def overlay_is_bkg(self, ind):
        """
        :param ind: overlay ind
        """
        return ind == self.bkg_ind and self.bkg_ind != -1


class Spectrum(object):
    def __init__(self, x=None, y=None, name=''):
        if x is None:
            self._x = np.linspace(0.1, 15, 100)
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

    def load(self, filename, skiprows=0):
        try:
            data = np.loadtxt(filename, skiprows=skiprows)
            self._x = data.T[0]
            self._y = data.T[1]
            self.name = os.path.basename(filename).split('.')[:-1][0]

        except ValueError:
            print('Wrong data format for spectrum file! - ' + filename)
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
            # create background function
            x_bkg, y_bkg = self.bkg_spectrum.data

            if np.array_equal(x_bkg, self._x):
                # if spectrum and bkg have the same x basis we just delete y-y_bkg
                return self._x, self._y * self._scaling + self.offset - y_bkg

            # otherwise the background will be interpolated
            f_bkg = interp1d(x_bkg, y_bkg, kind='linear')

            #find overlapping x and y values:
            ind = np.where((self._x <= np.max(x_bkg)) & (self._x >= np.min(x_bkg)))
            x = self._x[ind]
            y = self._y[ind]

            if len(x) == 0:
                #if there is no overlapping between background and spectrum, raise an error
                raise BkgNotInRangeError(self.name)

            return x, y * self._scaling + self.offset - f_bkg(x)
        else:
            return self.original_data


    @data.setter
    def data(self, data):
        (x, y) = data
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


class BkgNotInRangeError(Exception):
    def __init__(self, spectrum_name):
        self.spectrum_name = spectrum_name

    def __str__(self):
        return "The background range does not overlap with the Spectrum range for " + self.spectrum_name


def test():
    my_spectrum = Spectrum()
    my_spectrum.save('test.txt')


if __name__ == '__main__':
    test()

