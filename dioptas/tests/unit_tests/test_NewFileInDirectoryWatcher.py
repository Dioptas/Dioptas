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
import shutil
import unittest
import time

from mock import MagicMock

from ...model.util.NewFileWatcher import NewFileInDirectoryWatcher

unittest_data_path = os.path.join(os.path.dirname(__file__), '../data')


class NewFileInDirectoryWatcherTest(unittest.TestCase):
    def setUp(self):
        self.directory_watcher = NewFileInDirectoryWatcher(path=None)

    def tearDown(self):
        if os.path.exists(os.path.join(unittest_data_path, 'image_003.tif')):
            os.remove(os.path.join(unittest_data_path, 'image_003.tif'))

    @unittest.skip('inotify Limit does not allow to run this on CI')
    def test_getting_callback_for_new_file(self):
        def callback_fcn(filepath):
            self.assertEqual(filepath, os.path.abspath(os.path.join(unittest_data_path, 'image_003.tif')))

        self.directory_watcher.path = unittest_data_path
        self.directory_watcher.file_added.connect(callback_fcn)
        self.directory_watcher.file_types.add('.tif')
        self.directory_watcher.activate()

        shutil.copy2(os.path.join(unittest_data_path, 'image_001.tif'),
                     os.path.join(unittest_data_path, 'image_003.tif'))

        self.directory_watcher.deactivate()

    @unittest.skip('inotify Limit does not allow to run this on CI')
    def test_filename_is_emitted_with_full_file_available(self):
        original_path = os.path.join(unittest_data_path, 'image_001.tif')
        destination_path = os.path.join(unittest_data_path, 'image_003.tif')
        original_filesize = os.stat(original_path).st_size

        def callback_fcn(filepath):
            filesize = os.stat(filepath).st_size
            self.assertEqual(filesize, original_filesize)

        self.directory_watcher.path = unittest_data_path
        self.directory_watcher.file_added.connect(callback_fcn)
        self.directory_watcher.file_types.add('.tif')
        self.directory_watcher.activate()

        shutil.copy2(original_path, destination_path)

        self.directory_watcher.deactivate()
