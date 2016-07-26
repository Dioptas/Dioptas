# -*- coding: utf8 -*-

import unittest
from PyQt4 import QtGui
import os


class QtTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtGui.QApplication.instance()
        if cls.app is None:
            cls.app = QtGui.QApplication([])


def delete_if_exists(data_path):
    if os.path.exists(data_path):
        os.remove(data_path)