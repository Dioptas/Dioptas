# -*- coding: utf8 -*-

import unittest
import os
import numpy as np

from PyQt4 import QtGui

from model.util.HelperModule import get_partial_index

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')


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
