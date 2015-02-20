# -*- coding: utf8 -*-
__author__ = 'Clemens Prescher'

import os

import numpy as np
from scipy.interpolate import interp1d
from scipy.ndimage import gaussian_filter1d

from .Helper import extract_background


class Spectrum(object):
    def __init__(self, x=None, y=None, name=''):
        if x is None:
            self._x = np.linspace(0.1, 15, 100)
        else:
            self._x = x
        if y is None:
            self._y = np.log(self._x ** 2) - (self._x * 0.2) ** 2
        else:
            self._y = y
        self.name = name
        self.offset = 0
        self._scaling = 1
        self.smoothing = 0
        self.bkg_spectrum = None
        self.auto_background_subtraction = False
        self.auto_background_subtraction_parameters = [2, 50, 50]

    def load(self, filename, skiprows=0):
        try:
            if filename.endswith('.chi'):
                skiprows = 4
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

    def set_background_spectrum(self, spectrum):
        self.bkg_spectrum = spectrum

    def unset_background_spectrum(self):
        self.bkg_spectrum = None

    def set_auto_background_subtraction(self, parameters):
        self.auto_background_subtraction = True
        self.auto_background_subtraction_parameters = parameters

    def unset_auto_background_subtraction(self):
        self.auto_background_subtraction = False

    def get_auto_background_subtraction_parameters(self):
        return self.auto_background_subtraction_parameters

    def set_smoothing(self, amount):
        self.smoothing = amount

    @property
    def data(self):
        if self.bkg_spectrum is not None:
            # create background function
            x_bkg, y_bkg = self.bkg_spectrum.data

            if not np.array_equal(x_bkg, self._x):
                # the background will be interpolated
                f_bkg = interp1d(x_bkg, y_bkg, kind='linear')

                # find overlapping x and y values:
                ind = np.where((self._x <= np.max(x_bkg)) & (self._x >= np.min(x_bkg)))
                x = self._x[ind]
                y = self._y[ind]

                if len(x) == 0:
                    # if there is no overlapping between background and spectrum, raise an error
                    raise BkgNotInRangeError(self.name)

                y = y * self._scaling + self.offset - f_bkg(x)
            else:
                # if spectrum and bkg have the same x basis we just delete y-y_bkg
                x, y = self._x, self._y * self._scaling + self.offset - y_bkg
        else:
            x, y = self.original_data

        if self.auto_background_subtraction:
            y -= extract_background(x, y,
                                    self.auto_background_subtraction_parameters[0],
                                    self.auto_background_subtraction_parameters[1],
                                    self.auto_background_subtraction_parameters[2])

        if self.smoothing > 0:
            y = gaussian_filter1d(y, self.smoothing)
        return x, y


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

    # Operators:
    def __sub__(self, other):
        orig_x, orig_y = self.data
        other_x, other_y = other.data

        if orig_x.shape != other_x.shape:
            # the background will be interpolated
            other_fcn = interp1d(other_x, other_y, kind='cubic')

            # find overlapping x and y values:
            ind = np.where((orig_x <= np.max(other_x)) & (orig_x >= np.min(other_x)))
            x = orig_x[ind]
            y = orig_y[ind]

            if len(x) == 0:
                # if there is no overlapping between background and spectrum, raise an error
                raise BkgNotInRangeError(self.name)
            return Spectrum(x, y - other_fcn(x))
        else:
            return Spectrum(orig_x, orig_y - other_y)

    def __add__(self, other):
        orig_x, orig_y = self.data
        other_x, other_y = other.data

        if orig_x.shape != other_x.shape:
            # the background will be interpolated
            other_fcn = interp1d(other_x, other_y, kind='linear')

            # find overlapping x and y values:
            ind = np.where((orig_x <= np.max(other_x)) & (orig_x >= np.min(other_x)))
            x = orig_x[ind]
            y = orig_y[ind]

            if len(x) == 0:
                # if there is no overlapping between background and spectrum, raise an error
                raise BkgNotInRangeError(self.name)
            return Spectrum(x, y + other_fcn(x))
        else:
            return Spectrum(orig_x, orig_y + other_y)

    def __rmul__(self, other):
        orig_x, orig_y = self.data
        return Spectrum(orig_x, orig_y * other)

    def __len__(self):
        return len(self._x)




class BkgNotInRangeError(Exception):
    def __init__(self, spectrum_name):
        self.spectrum_name = spectrum_name

    def __str__(self):
        return "The background range does not overlap with the Spectrum range for " + self.spectrum_name