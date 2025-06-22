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
import os

from ..util.HelperModule import FileNameIterator

logger = logging.getLogger(__name__)


class FileNavigator:
    """
    Handles file iteration and navigation.
    Manages file iteration modes and provides navigation methods.
    """

    def __init__(self):
        self.file_iteration_mode = "number"
        self.file_name_iterator = FileNameIterator()
        self.current_filename = ""

    def update_filename(self, filename):
        """
        Update the current filename for navigation.
        :param filename: new filename to set as current
        """
        self.current_filename = str(filename)
        self.file_name_iterator.update_filename(filename)

    def set_file_iteration_mode(self, mode):
        """
        Sets the file iteration mode for the load_next_file and load_previous_file functions. Possible modes:
            * 'number' will increment or decrement based on numbers in the filename.
            * 'time' will increment or decrement based on creation time for the files.
        """
        if mode == "number":
            self.file_iteration_mode = "number"
            self.file_name_iterator.create_timed_file_list = False
        elif mode == "time":
            self.file_iteration_mode = "time"
            self.file_name_iterator.create_timed_file_list = True
            self.file_name_iterator.update_filename(self.current_filename)

    def get_next_filename(self, step=1, pos=None):
        """
        Get the next filename based on the current iteration mode.
        :param step: Defining how much you want to increment the file number. (default=1)
        :param pos: position parameter for file iteration
        :return: next filename or None if not found
        """
        return self.file_name_iterator.get_next_filename(
            mode=self.file_iteration_mode, step=step, pos=pos
        )

    def get_previous_filename(self, step=1, pos=None):
        """
        Get the previous filename based on the current iteration mode.
        :param step: Defining how much you want to decrement the file number. (default=1)
        :param pos: position parameter for file iteration
        :return: previous filename or None if not found
        """
        return self.file_name_iterator.get_previous_filename(
            mode=self.file_iteration_mode, step=step, pos=pos
        )

    def get_next_folder(self, mec_mode=False):
        """
        Get a filename with the current filename in the next folder, whereby the folder has to be iteratable by numbers.
        :param mec_mode: Boolean which enables specific mode for MEC beamline at SLAC, where the folders and the
                        files change their during increment. (default = False)
        :return: next folder filename or None if not found
        """
        return self.file_name_iterator.get_next_folder(mec_mode=mec_mode)

    def get_previous_folder(self, mec_mode=False):
        """
        Get a filename with the current filename in the previous folder, whereby the folder has to be iteratable by
        numbers.
        :param mec_mode: Boolean which enables specific mode for MEC beamline at SLAC, where the folders and the
                        files change their during increment. (default = False)
        :return: previous folder filename or None if not found
        """
        return self.file_name_iterator.get_previous_folder(mec_mode=mec_mode)

    def set_directory_watcher_path(self, filename):
        """
        Set the directory path for file watching.
        :param filename: filename to extract directory from
        """
        return os.path.dirname(str(filename)) 