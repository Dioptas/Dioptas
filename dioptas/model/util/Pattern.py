# -*- coding: utf8 -*-


import os
import logging
from PyQt4 import QtCore


import numpy as np
from scipy.interpolate import interp1d
from scipy.ndimage import gaussian_filter1d

from model.util import extract_background

logger = logging.getLogger(__name__)


class Pattern(QtCore.QObject):
    pattern_changed = QtCore.pyqtSignal(np.ndarray, np.ndarray)
    
    def __init__(self, x=None, y=None, name=''):
        super(Pattern, self).__init__()
        if x is None:
            self._original_x = np.linspace(0.1, 15, 100)
        else:
            self._original_x = x
        if y is None:
            self._original_y = np.log(self._original_x ** 2) - (self._original_x * 0.2) ** 2
        else:
            self._original_y = y

        self.name = name
        self._offset = 0
        self._scaling = 1
        self._smoothing = 0
        self._background_pattern = None

        self._spectrum_x = self._original_x
        self._spectrum_y = self._original_y

        self.auto_background_subtraction = False
        self.auto_background_subtraction_roi = None
        self.auto_background_subtraction_parameters = [2, 50, 50]

        self._auto_background_before_subtraction_spectrum = None
        self._auto_background_spectrum = None

    def load(self, filename, skiprows=0):
        try:
            if filename.endswith('.chi'):
                skiprows = 4
            data = np.loadtxt(filename, skiprows=skiprows)
            self._original_x = data.T[0]
            self._original_y = data.T[1]
            self.name = os.path.basename(filename).split('.')[:-1][0]
            self.recalculate_pattern()

        except ValueError:
            print('Wrong data format for spectrum file! - ' + filename)
            return -1

    def save(self, filename, header=''):
        data = np.dstack((self._original_x, self._original_y))
        np.savetxt(filename, data[0], header=header)

    @property
    def background_pattern(self):
        return self._background_pattern

    @background_pattern.setter
    def background_pattern(self, pattern):
        """
        :param pattern: new background spectrum
        :type pattern: Pattern
        """
        self._background_pattern = pattern
        self._background_pattern.pattern_changed.connect(self.recalculate_pattern)
        self.recalculate_pattern()

    def unset_background_spectrum(self):
        self._background_pattern = None
        self.recalculate_pattern()

    def set_auto_background_subtraction(self, parameters, roi=None):
        self.auto_background_subtraction = True
        self.auto_background_subtraction_parameters = parameters
        self.auto_background_subtraction_roi = roi
        self.recalculate_pattern()

    def unset_auto_background_subtraction(self):
        self.auto_background_subtraction = False
        self.recalculate_pattern()

    def get_auto_background_subtraction_parameters(self):
        return self.auto_background_subtraction_parameters

    def set_smoothing(self, amount):
        self._smoothing = amount
        self.recalculate_pattern()

    def recalculate_pattern(self):
        x = self._original_x
        y = self._original_y * self._scaling + self._offset

        if self._background_pattern is not None:
            # create background function
            x_bkg, y_bkg = self._background_pattern.data

            if not np.array_equal(x_bkg, self._original_x):
                # the background will be interpolated
                f_bkg = interp1d(x_bkg, y_bkg, kind='linear')

                # find overlapping x and y values:
                ind = np.where((self._original_x <= np.max(x_bkg)) & (self._original_x >= np.min(x_bkg)))
                x = self._original_x[ind]
                y = self._original_y[ind]

                if len(x) == 0:
                    # if there is no overlapping between background and spectrum, raise an error
                    raise BkgNotInRangeError(self.name)

                y = y - f_bkg(x)
            else:
                # if spectrum and bkg have the same x basis we just delete y-y_bkg
                y = y - y_bkg

        if self.auto_background_subtraction:
            self._auto_background_before_subtraction_spectrum = Pattern(x, y)
            if self.auto_background_subtraction_roi is not None:
                ind = (x > self.auto_background_subtraction_roi[0]) & \
                      (x < self.auto_background_subtraction_roi[1])
                x = x[ind]
                y = y[ind]

            y_bkg = extract_background(x, y,
                                       self.auto_background_subtraction_parameters[0],
                                       self.auto_background_subtraction_parameters[1],
                                       self.auto_background_subtraction_parameters[2])
            self._auto_background_spectrum = Pattern (x, y_bkg)

            y -= y_bkg

        if self._smoothing > 0:
            y = gaussian_filter1d(y, self._smoothing)

        self._spectrum_x = x
        self._spectrum_y = y

        self.pattern_changed.emit(self._spectrum_x, self._spectrum_y)


    @property
    def data(self):
        return self._spectrum_x, self._spectrum_y


    @data.setter
    def data(self, data):
        (x, y) = data
        self._original_x = x
        self._original_y = y
        self._scaling = 1
        self._offset = 0
        self.recalculate_pattern()

    @property
    def x(self):
        return self._spectrum_x

    @property
    def y(self):
        return self._spectrum_y

    @property
    def original_data(self):
        return self._original_x, self._original_y

    @property
    def original_x(self):
        return self._original_x

    @property
    def original_y(self):
        return self._original_y

    @property
    def scaling(self):
        return self._scaling

    @scaling.setter
    def scaling(self, value):
        if value < 0:
            self._scaling = 0
        else:
            self._scaling = value
        self.recalculate_pattern()

    def limit(self, x_min, x_max):
        x, y = self.data
        return Pattern(x[np.where((x_min < x) & (x < x_max))],
                       y[np.where((x_min < x) & (x < x_max))])

    @property
    def offset(self):
        return self._offset

    @offset.setter
    def offset(self, value):
        self._offset = value
        self.recalculate_pattern()

    @property
    def auto_background_before_subtraction_spectrum(self):
        return self._auto_background_before_subtraction_spectrum

    @property
    def auto_background_pattern(self):
        return self._auto_background_spectrum


    def has_background(self):
        return (self.background_pattern is not None) or self.auto_background_subtraction

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
            return Pattern(x, y - other_fcn(x))
        else:
            return Pattern(orig_x, orig_y - other_y)

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
            return Pattern(x, y + other_fcn(x))
        else:
            return Pattern(orig_x, orig_y + other_y)

    def __rmul__(self, other):
        orig_x, orig_y = self.data
        return Pattern(orig_x, orig_y * other)

    def __len__(self):
        return len(self._original_x)


class BkgNotInRangeError(Exception):
    def __init__(self, pattern_name):
        self.pattern_name = pattern_name

    def __str__(self):
        return "The background range does not overlap with the Pattern range for " + self.pattern_name