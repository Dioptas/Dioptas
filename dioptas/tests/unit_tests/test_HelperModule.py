# -*- coding: utf8 -*-

import unittest
import os
import shutil
import numpy as np

from PyQt4 import QtGui

from model.util.HelperModule import get_partial_index, FileNameIterator

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data', 'FileIterator')


class HelperModuleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtGui.QApplication.instance()
        if cls.app is None:
            cls.app = QtGui.QApplication([])

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
