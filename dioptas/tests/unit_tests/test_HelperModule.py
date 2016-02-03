# -*- coding: utf8 -*-

import unittest
import os

from PyQt4 import QtGui


unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')


class HelperModuleTest(unittest.TestCase):
    app = QtGui.QApplication([])

    def setUp(self):
        pass

    def tearDown(self):
        pass
