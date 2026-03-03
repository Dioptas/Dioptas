# SPDX-License-Identifier: MIT

import os
import numpy as np

from ...model.util.HelperModule import get_partial_index, FileNameIterator, get_partial_value

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data', 'FileIterator')


def test_get_partial_index():
    data = np.arange(0, 10, 1)
    value = 2.5
    assert get_partial_index(data, value) == 2.5
    assert get_partial_index(data, data[4]) == 4


def test_get_partial_index_out_of_range():
    data = np.arange(0, 10, 1)
    assert get_partial_index(data, -1) is None
    assert get_partial_index(data, 11) is None


def test_get_partial_value():
    data = np.arange(2, 11, 2)
    assert get_partial_value(data, 1.5) == 5
    assert get_partial_value(data, 0.3) == 2 + 0.3 * 2


def test_get_partial_value_out_of_range():
    data = np.arange(2, 11, 2)
    assert get_partial_value(data, -1) is None
    assert get_partial_value(data, 10) is None


def test_get_next_filename():
    filename = os.path.join(data_path, "dummy1_1.txt")
    file_iterator = FileNameIterator(filename)
    new_filename = file_iterator.get_next_filename(1, filename)

    assert new_filename == os.path.join(data_path, 'dummy1_2.txt')


def test_get_next_filename_with_pos():
    filename = os.path.join(data_path, "dummy1_1.txt")
    file_iterator = FileNameIterator()
    new_filename = file_iterator.get_next_filename(1, filename, pos=1)

    assert new_filename == os.path.join(data_path, 'dummy2_1.txt')


def test_get_previous_filename_with_pos():
    filename = os.path.join(data_path, "dummy2_1.txt")
    file_iterator = FileNameIterator()
    new_filename = file_iterator.get_previous_filename(1, filename, pos=1)

    assert new_filename == os.path.join(data_path, 'dummy1_1.txt')


def test_get_next_folder():
    filename = os.path.join(data_path, "run1", "dummy_1.txt")
    file_iterator = FileNameIterator()
    new_filename = file_iterator.get_next_folder(filename)
    assert new_filename == os.path.join(data_path, 'run2', "dummy_1.txt")


def test_get_previous_folder():
    filename = os.path.join(data_path, "run2", "dummy_1.txt")
    file_iterator = FileNameIterator()
    new_filename = file_iterator.get_previous_folder(filename)
    assert new_filename == os.path.join(data_path, 'run1', "dummy_1.txt")


def test_get_next_folder_mec():
    filename = os.path.join(data_path, "run1", "run_1_evt_2.0.txt")
    file_iterator = FileNameIterator()
    new_filename = file_iterator.get_next_folder(filename, mec_mode=True)
    assert new_filename == os.path.join(data_path, 'run2', "run_2_evt_2.0.txt")


def test_get_previous_folder_mec():
    filename = os.path.join(data_path, "run2", "run_2_evt_2.0.txt")
    file_iterator = FileNameIterator()
    new_filename = file_iterator.get_previous_folder(filename, mec_mode=True)
    assert new_filename == os.path.join(data_path, 'run1', "run_1_evt_2.0.txt")
