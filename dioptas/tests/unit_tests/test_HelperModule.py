# -*- coding: utf8 -*-

import unittest
import os
import numpy as np

from PyQt4 import QtGui

from model.CalibrationModel import CalibrationModel
from model.ImgModel import ImgModel
from model.util.HelperModule import reverse_interpolate_two_array, reverse_interpolate_two_array2

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')


class HelperModuleTest(unittest.TestCase):
    app = QtGui.QApplication([])

    def setUp(self):
        pass

    def tearDown(self):
        pass
