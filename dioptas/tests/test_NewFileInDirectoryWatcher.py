# -*- coding: utf8 -*-

import unittest
import os
import shutil

from PyQt4 import QtGui
from mock import MagicMock

from controller.integration.ImageController import NewFileInDirectoryWatcher

unittest_data_path = os.path.join(os.path.dirname(__file__), 'data')


class NewFileInDirectoryWatcherTest(unittest.TestCase):
    app = QtGui.QApplication([])

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
