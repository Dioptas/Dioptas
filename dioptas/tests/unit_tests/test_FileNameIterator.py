# SPDX-License-Identifier: MIT

import os
from unittest.mock import MagicMock

import pytest

from ...model.util.HelperModule import FileNameIterator

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')


@pytest.fixture
def filename_iterator():
    return FileNameIterator()


def test_empty_filename_does_not_scan_working_directory(filename_iterator, monkeypatch):
    filename_iterator.create_timed_file_list = True
    monkeypatch.setattr(os, "listdir", MagicMock(side_effect=AssertionError("unexpected scan")))
    filename_iterator.update_filename("")
    assert filename_iterator.complete_path is None
    assert filename_iterator.get_next_filename(mode="time") is None


def test_time_scan_skips_unreadable_entries(filename_iterator, tmp_path, monkeypatch):
    image = tmp_path / "image_001.tif"
    missing = tmp_path / "gone.tif"
    image.touch()
    (tmp_path / "directory.tif").mkdir()
    missing.symlink_to(tmp_path / "missing-target")
    filename_iterator.create_timed_file_list = True
    filename_iterator.update_filename(str(image))
    assert filename_iterator.filename_list == [str(image)]


def test_time_scan_tolerates_files_disappearing(filename_iterator, tmp_path, monkeypatch):
    image = tmp_path / "image_001.tif"
    image.touch()
    monkeypatch.setattr(os.path, "getctime", MagicMock(side_effect=FileNotFoundError("removed")))
    filename_iterator.create_timed_file_list = True
    filename_iterator.update_filename(str(image))
    assert filename_iterator.file_list == []
    assert filename_iterator.get_next_filename(mode="time") is None


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


def test_time_iteration_refreshes_directory_only_when_browsing(
    filename_iterator, tmp_path, monkeypatch
):
    first = tmp_path / "image_001.tif"
    second = tmp_path / "image_002.tif"
    first.write_bytes(b"first")
    creation_times = {
        str(first): 1.0,
        str(second): 2.0,
    }
    monkeypatch.setattr(
        os.path,
        "getctime",
        lambda filename: creation_times[str(filename)],
    )

    filename_iterator.create_timed_file_list = True
    filename_iterator.update_filename(str(first))
    second.write_bytes(b"second")

    assert filename_iterator.get_next_filename(mode="time") == str(second)
