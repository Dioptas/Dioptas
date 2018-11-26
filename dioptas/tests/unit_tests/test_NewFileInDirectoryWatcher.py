# -*- coding: utf-8 -*-
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
import shutil

from mock import MagicMock

from ..utility import QtTest
from ...model.util.NewFileWatcher import NewFileInDirectoryWatcher

unittest_data_path = os.path.join(os.path.dirname(__file__), '../data')


class NewFileInDirectoryWatcherTest(QtTest):
    def setUp(self):
        self.directory_watcher = NewFileInDirectoryWatcher(path=None)

    def tearDown(self):
        if os.path.exists(os.path.join(unittest_data_path, 'image_003.tif')):
            os.remove(os.path.join(unittest_data_path, 'image_003.tif'))

    def test_getting_callback_for_new_file(self):
        callback_fcn = MagicMock()

        self.directory_watcher.path = unittest_data_path
        self.directory_watcher.file_added.connect(callback_fcn)
        self.directory_watcher.file_types.add('.tif')
        self.directory_watcher.activate()

        shutil.copy2(os.path.join(unittest_data_path, 'image_001.tif'),
                     os.path.join(unittest_data_path, 'image_003.tif'))

        self.directory_watcher._file_system_watcher.directoryChanged.emit('test')
        callback_fcn.assert_called_with(os.path.join(unittest_data_path, 'image_003.tif'))
