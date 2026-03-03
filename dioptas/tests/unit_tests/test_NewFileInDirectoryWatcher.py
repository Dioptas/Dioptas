# SPDX-License-Identifier: MIT

import os
import shutil
import unittest

from ...model.util.NewFileWatcher import NewFileInDirectoryWatcher

unittest_data_path = os.path.join(os.path.dirname(__file__), '../data')


@unittest.skip('inotify Limit does not allow to run this on CI')
def test_getting_callback_for_new_file(tmp_path):
    directory_watcher = NewFileInDirectoryWatcher()

    def callback_fcn(filepath):
        assert filepath == os.path.abspath(os.path.join(tmp_path, 'image_003.tif'))

    directory_watcher.path = tmp_path
    directory_watcher.file_added.connect(callback_fcn)
    directory_watcher.file_types.add('.tif')
    directory_watcher.activate()

    shutil.copy2(os.path.join(unittest_data_path, 'image_001.tif'),
                 os.path.join(tmp_path, 'image_003.tif'))

    directory_watcher.deactivate()


@unittest.skip('inotify Limit does not allow to run this on CI')
def test_filename_is_emitted_with_full_file_available(tmp_path):
    directory_watcher = NewFileInDirectoryWatcher()
    original_path = os.path.join(unittest_data_path, 'image_001.tif')
    destination_path = os.path.join(tmp_path, 'image_003.tif')
    original_filesize = os.stat(original_path).st_size

    def callback_fcn(filepath):
        filesize = os.stat(filepath).st_size
        assert filesize == original_filesize

    directory_watcher.path = tmp_path
    directory_watcher.file_added.connect(callback_fcn)
    directory_watcher.file_types.add('.tif')
    directory_watcher.activate()

    shutil.copy2(original_path, destination_path)

    directory_watcher.deactivate()
