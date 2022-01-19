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

import logging

from math import sqrt
from .util import Signal
from .util.HelperModule import FileNameIterator, get_base_name
from .util import Pattern

logger = logging.getLogger(__name__)


class PatternModel(object):
    """
    Main Pattern handling class. Supporting:
        - setting background pattern
        - setting automatic background subtraction
        - file browsing

    all changes to the internal data throw a pattern_changed signal.
    """

    def __init__(self):
        super(PatternModel, self).__init__()
        self.pattern = Pattern()
        self.pattern_filename = ''

        self.unit = ''
        self.file_iteration_mode = 'number'
        self.file_name_iterator = FileNameIterator()

        self._background_pattern = None

        self.pattern_changed = Signal()

    def set_pattern(self, x, y, filename='', unit=''):
        """
        set the current data pattern.
        :param x: x-values
        :param y: y-values
        :param filename: name for the pattern, defaults to ''
        :param unit: unit for the x values
        """
        self.pattern_filename = filename
        self.pattern.data = (x, y)
        self.pattern.name = get_base_name(filename)
        self.unit = unit
        self.pattern_changed.emit()

    def load_pattern(self, filename):
        """
        Loads a pattern from a tabular pattern file (2 column txt file)
        :param filename: filename of the data file
        """
        logger.info("Load pattern: {0}".format(filename))
        self.pattern_filename = filename

        skiprows = 0
        if filename.endswith('.chi'):
            skiprows = 4
        self.pattern.load(filename, skiprows)
        self.file_name_iterator.update_filename(filename)
        self.pattern_changed.emit()

    def save_pattern(self, filename, header=None, subtract_background=False):
        """
        Saves the current data pattern.
        :param filename: where to save
        :param header: you can specify any specific header
        :param subtract_background: whether the background set will be used for saving or not
        """
        self.pattern.save(filename, header, subtract_background, self.unit)

    def save_auto_background_as_pattern(self, filename, header=None):
        """
        Saves the current automatic extracted background data pattern to file
        :param filename: where to save
        :param header: you can specify any specific header
        """
        self.pattern.auto_background_pattern.save(filename, header, unit=self.unit)

    def get_pattern(self):
        return self.pattern

    def load_next_file(self, step=1):
        """
        Loads the next file from a sequel of filenames (e.g. *_001.xy --> *_002.xy)
        It assumes that the file numbers are at the end of the filename
        """
        next_file_name = self.file_name_iterator.get_next_filename(mode=self.file_iteration_mode, step=step)
        if next_file_name is not None:
            self.load_pattern(next_file_name)
            return True
        return False

    def load_previous_file(self, step=1):
        """
        Loads the previous file from a sequel of filenames (e.g. *_002.xy --> *_001.xy)
        It assumes that the file numbers are at the end of the filename
        """
        next_file_name = self.file_name_iterator.get_previous_filename(mode=self.file_iteration_mode, step=step)
        if next_file_name is not None:
            self.load_pattern(next_file_name)
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

    @property
    def background_pattern(self):
        return self._background_pattern

    @background_pattern.setter
    def background_pattern(self, pattern):
        if pattern is not None:
            self.pattern.background_pattern = pattern
        else:
            self.pattern.unset_background_pattern()
        self._background_pattern = pattern
        self.pattern_changed.emit()

    def set_auto_background_subtraction(self, parameters, roi=None):
        """
        Enables auto background extraction and removal from the data pattern
        :param parameters: array of parameters with [window_width, iterations, polynomial_order]
        :param roi: array of size two with [x_min, x_max] specifying the range for the background subtraction
        will be performed
        """
        self.pattern.set_auto_background_subtraction(parameters, roi)
        self.pattern_changed.emit()

    def unset_auto_background_subtraction(self):
        """
        Disables auto background extraction and removal.
        """
        self.pattern.unset_auto_background_subtraction()
        self.pattern_changed.emit()
