# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2017  Clemens Prescher (clemens.prescher@gmail.com)
# Institute for Geology and Mineralogy, University of Cologne
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
import numpy as np

from ..utility import QtTest
from ...model.util.HelperModule import get_partial_index, FileNameIterator

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data', 'FileIterator')


class HelperModuleTest(QtTest):
    def test_get_partial_ind(self):
        data = np.arange(0, 10, 1)
        value = 2.5
        self.assertEqual(get_partial_index(data, value), 2.5)

    def test_get_next_filename(self):
        filename = os.path.join(data_path, "dummy1_1.txt")
        self.file_iterator = FileNameIterator(filename)
        new_filename = self.file_iterator.get_next_filename(1, filename)

        self.assertEqual(new_filename, os.path.join(data_path, 'dummy1_2.txt'))

    def test_get_next_filename_with_pos(self):
        filename = os.path.join(data_path, "dummy1_1.txt")
        self.file_iterator = FileNameIterator()
        new_filename = self.file_iterator.get_next_filename(1, filename, pos=1)

        self.assertEqual(new_filename, os.path.join(data_path, 'dummy2_1.txt'))

    def test_get_previous_filename_with_pos(self):
        filename = os.path.join(data_path, "dummy2_1.txt")
        self.file_iterator = FileNameIterator()
        new_filename = self.file_iterator.get_previous_filename(1, filename, pos=1)

        self.assertEqual(new_filename, os.path.join(data_path, 'dummy1_1.txt'))

    def test_get_next_folder(self):
        filename = os.path.join(data_path, "run1", "dummy_1.txt")
        self.file_iterator = FileNameIterator()
        new_filename = self.file_iterator.get_next_folder(filename)
        self.assertEqual(new_filename, os.path.join(data_path, 'run2', "dummy_1.txt"))

    def test_get_previous_folder(self):
        filename = os.path.join(data_path, "run2", "dummy_1.txt")
        self.file_iterator = FileNameIterator()
        new_filename = self.file_iterator.get_previous_folder(filename)
        self.assertEqual(new_filename, os.path.join(data_path, 'run1', "dummy_1.txt"))

    def test_get_next_folder_mec(self):
        filename = os.path.join(data_path, "run1", "run_1_evt_2.0.txt")
        self.file_iterator = FileNameIterator()
        new_filename = self.file_iterator.get_next_folder(filename, mec_mode=True)
        self.assertEqual(new_filename, os.path.join(data_path, 'run2', "run_2_evt_2.0.txt"))

    def test_get_previous_folder_mec(self):
        filename = os.path.join(data_path, "run2", "run_2_evt_2.0.txt")
        self.file_iterator = FileNameIterator()
        new_filename = self.file_iterator.get_previous_folder(filename, mec_mode=True)
        self.assertEqual(new_filename, os.path.join(data_path, 'run1', "run_1_evt_2.0.txt"))
