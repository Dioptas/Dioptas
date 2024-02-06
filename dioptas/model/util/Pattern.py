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
import logging
from qtpy import QtCore

import numpy as np
from scipy.interpolate import interp1d
from scipy.ndimage import gaussian_filter1d

from . import extract_background

logger = logging.getLogger(__name__)


class Pattern(QtCore.QObject):
    pattern_changed = QtCore.Signal(np.ndarray, np.ndarray)

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
        self.filename = ""
        self._offset = 0
        self._scaling = 1
        self._smoothing = 0
        self._background_pattern = None

        self._pattern_x = self._original_x
        self._pattern_y = self._original_y

        self.auto_background_subtraction = False
        self.auto_background_subtraction_roi = None
        self.auto_background_subtraction_parameters = [0.1, 50, 50]

        self._auto_background_before_subtraction_pattern = None
        self._auto_background_pattern = None

    def load(self, filename, skiprows=0):
        factor = 1.0
        try:
            if filename.endswith('.chi'):
                skiprows = 4
            if filename.endswith('fxye'):
                factor = 1.0/100.0
                with open(filename, 'r') as fxye_file:
                    skiprows = 0
                    for line in fxye_file:
                        skiprows += 1
                        if "BANK" in line:
                            if "CONQ" in line:
                                factor = 1.0
                            break

            data = np.loadtxt(filename, skiprows=skiprows)
            self.filename = filename
            self._original_x = data.T[0]*factor
            self._original_y = data.T[1]
            self.name = os.path.basename(filename).split('.')[:-1][0]
            self.recalculate_pattern()
            return self

        except ValueError:
            print('Wrong data format for pattern file! - ' + filename)
            return -1

    @classmethod
    def from_file(cls, filename):
        pattern = cls()
        pattern.load(filename)
        return pattern

    def save(self, filename, header='', subtract_background=False, unit='2th_deg'):
        """
        Saves the x, y data to file. Supporting several file formats: .chi, .xy, .fxye
        :param filename: where to save the data
        :param header: header for file
        :param subtract_background: whether or not to save subtracted data
        :param unit: x-unit used for the standard chi header (unused for other formats)
        """
        if subtract_background:
            x, y = self.data
        else:
            x, y = self._original_x, self._original_y

        file_handle = open(filename, 'w')
        num_points = len(x)

        if filename.endswith('.chi'):
            if header is None or header == '':
                file_handle.write(filename + '\n')
                file_handle.write(unit + '\n\n')
                file_handle.write("       {0}\n".format(num_points))
            else:
                file_handle.write(header)
            for ind in range(num_points):
                file_handle.write(' {0:.7E}  {1:.7E}\n'.format(x[ind], y[ind]))
        elif filename.endswith('.fxye'):
            factor = 100
            if 'CONQ' in header:
                factor = 1
            header = header.replace('NUM_POINTS', '{0:.6g}'.format(num_points))
            header = header.replace('MIN_X_VAL', '{0:.6g}'.format(factor * x[0]))
            header = header.replace('STEP_X_VAL', '{0:.6g}'.format(factor * (x[1] - x[0])))

            file_handle.write(header)
            file_handle.write('\n')
            for ind in range(num_points):
                file_handle.write('\t{0:.6g}\t{1:.6g}\t{2:.6g}\n'.format(factor * x[ind], y[ind], np.sqrt(abs(y[ind]))))
        else:
            if header is not None:
                file_handle.write(header)
                file_handle.write('\n')
            for ind in range(num_points):
                file_handle.write('{0:.9E}  {1:.9E}\n'.format(x[ind], y[ind]))
        file_handle.close()

    @property
    def background_pattern(self):
        return self._background_pattern

    @background_pattern.setter
    def background_pattern(self, pattern):
        """
        :param pattern: new background pattern
        :type pattern: Pattern
        """
        self._background_pattern = pattern
        self._background_pattern.pattern_changed.connect(self.recalculate_pattern)
        self.recalculate_pattern()

    def unset_background_pattern(self):
        self._background_pattern = None
        self.recalculate_pattern()

    def set_auto_background_subtraction(self, parameters, roi=None, recalc_pattern=True):
        self.auto_background_subtraction = True
        self.auto_background_subtraction_parameters = parameters
        self.auto_background_subtraction_roi = roi
        if recalc_pattern:
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
                    # if there is no overlapping between background and pattern, raise an error
                    raise BkgNotInRangeError(self.name)

                y = y - f_bkg(x)
            else:
                # if pattern and bkg have the same x basis we just delete y-y_bkg
                y = y - y_bkg

        if self.auto_background_subtraction:
            self._auto_background_before_subtraction_pattern = Pattern(x, y)
            if self.auto_background_subtraction_roi is not None:
                ind = (x >= np.min(self.auto_background_subtraction_roi)) & \
                      (x <= np.max(self.auto_background_subtraction_roi))
                x = x[ind]
                y = y[ind]
                if len(x) == 0:
                    return
                self.auto_background_subtraction_roi = [np.min(x), np.max(x)]
            else:
                self.auto_background_subtraction_roi = [np.min(x), np.max(x)]

            # reset ROI if limits are larger or smaller than the actual data
            x_min, x_max = np.min(x), np.max(x)
            if self.auto_background_subtraction_roi[0] < x_min:
                self.auto_background_subtraction_roi[0] = x_min

            if self.auto_background_subtraction_roi[1] > x_max:
                self.auto_background_subtraction_roi[1] = x_max

            y_bkg = extract_background(x, y,
                                       self.auto_background_subtraction_parameters[0],
                                       self.auto_background_subtraction_parameters[1],
                                       self.auto_background_subtraction_parameters[2])
            self._auto_background_pattern = Pattern(x, y_bkg, name='auto_bg_' + self.name)
            y -= y_bkg

        if self._smoothing > 0:
            y = gaussian_filter1d(y, self._smoothing)

        self._pattern_x = x
        self._pattern_y = y

        self.pattern_changed.emit(self._pattern_x, self._pattern_y)

    @property
    def data(self):
        return self._pattern_x, self._pattern_y

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
        return self._pattern_x

    @property
    def y(self):
        return self._pattern_y

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
    def auto_background_before_subtraction_pattern(self):
        return self._auto_background_before_subtraction_pattern

    @property
    def auto_background_pattern(self):
        """
        :rtype: Pattern
        """
        return self._auto_background_pattern

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
                # if there is no overlapping between background and pattern, raise an error
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
                # if there is no overlapping between background and pattern, raise an error
                raise BkgNotInRangeError(self.name)
            return Pattern(x, y + other_fcn(x))
        else:
            return Pattern(orig_x, orig_y + other_y)

    def __rmul__(self, other):
        orig_x, orig_y = self.data
        return Pattern(orig_x, orig_y * other)

    def __len__(self):
        return len(self._original_x)


def combine_patterns(patterns):
    x_min = []
    for pattern in patterns:
        x = pattern.x
        x_min.append(np.min(x))

    sorted_pattern_ind = np.argsort(x_min)

    pattern = patterns[sorted_pattern_ind[0]]
    for ind in sorted_pattern_ind[1:]:
        x1, y1 = pattern.data
        x2, y2 = patterns[ind].data

        pattern2_interp1d = interp1d(x2, y2, kind='linear')

        overlap_ind_pattern1 = np.where((x1 <= np.max(x2)) & (x1 >= np.min(x2)))[0]
        left_ind_pattern1 = np.where((x1 <= np.min(x2)))[0]
        right_ind_pattern2 = np.where((x2 >= np.max(x1)))[0]

        combined_x1 = x1[left_ind_pattern1]
        combined_y1 = y1[left_ind_pattern1]
        combined_x2 = x1[overlap_ind_pattern1]
        combined_y2 = (y1[overlap_ind_pattern1] + pattern2_interp1d(combined_x2)) / 2
        combined_x3 = x2[right_ind_pattern2]
        combined_y3 = y2[right_ind_pattern2]

        combined_x = np.hstack((combined_x1, combined_x2, combined_x3))
        combined_y = np.hstack((combined_y1, combined_y2, combined_y3))

        pattern = Pattern(combined_x, combined_y)

    pattern.name = "Combined Pattern"
    return pattern


class BkgNotInRangeError(Exception):
    def __init__(self, pattern_name):
        self.pattern_name = pattern_name

    def __str__(self):
        return "The background range does not overlap with the Pattern range for " + self.pattern_name
