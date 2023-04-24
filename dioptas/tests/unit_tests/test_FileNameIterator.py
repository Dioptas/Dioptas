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

import pytest

from ...model.util.HelperModule import FileNameIterator

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')


@pytest.fixture
def filename_iterator():
    return FileNameIterator()


def test_get_next_filename_with_existent_file(filename_iterator):
    filename = 'image_001.tif'
    filename_iterator.update_filename(os.path.join(data_path, filename))
    new_filename = os.path.basename(filename_iterator.get_next_filename())
    assert new_filename == 'image_002.tif'


def test_get_next_filename_with_non_existent_file(filename_iterator):
    filename = 'image_002.tif'
    filename_iterator.update_filename(os.path.join(data_path, filename))
    assert filename_iterator.get_next_filename() is None


def test_get_next_filename_with_larger_Step(filename_iterator):
    filename = 'image_000.tif'
    filename_iterator.update_filename(os.path.join(data_path, filename))
    new_filename = os.path.basename(filename_iterator.get_next_filename(step=2))
    assert new_filename == 'image_002.tif'


def test_get_next_filename_with_two_numbers_in_name(filename_iterator, tmp_path):
    filename1 = 'image_001w_001.tif'
    filename2 = 'image_002w_001.tif'
    file_path1 = os.path.join(tmp_path, filename1)
    file_path2 = os.path.join(tmp_path, filename2)

    open(file_path1, "w")
    open(file_path2, "w")

    filename_iterator.update_filename(file_path1)
    new_filename = filename_iterator.get_next_filename()
    assert os.path.abspath(new_filename) == os.path.abspath(file_path2)

    os.remove(file_path1)
    os.remove(file_path2)

    filename1 = 'image_003w_001.tif'
    filename2 = 'image_003w_002.tif'
    filename3 = 'image_004w_001.tif'

    file_path1 = os.path.join(tmp_path, filename1)
    file_path2 = os.path.join(tmp_path, filename2)
    file_path3 = os.path.join(tmp_path, filename3)

    open(file_path1, "w")
    open(file_path2, "w")
    open(file_path3, "w")

    filename_iterator.update_filename(file_path1)
    new_filename = filename_iterator.get_next_filename()
    assert os.path.abspath(new_filename) == os.path.abspath(file_path2)


def test_get_previous_filename_with_existent_file(filename_iterator):
    filename = 'image_002.tif'
    filename_iterator.update_filename(os.path.join(data_path, filename))
    new_filename = os.path.basename(filename_iterator.get_previous_filename())
    assert new_filename == 'image_001.tif'


def test_get_previous_filename_with_non_existent_file(filename_iterator):
    filename = 'image_001.tif'
    filename_iterator.update_filename(os.path.join(data_path, filename))
    assert filename_iterator.get_previous_filename() is None


def test_get_previous_filename_with_larger_Step(filename_iterator):
    filename = 'image_003.tif'
    filename_iterator.update_filename(os.path.join(data_path, filename))
    new_filename = os.path.basename(filename_iterator.get_previous_filename(step=2))
    assert new_filename == 'image_001.tif'
