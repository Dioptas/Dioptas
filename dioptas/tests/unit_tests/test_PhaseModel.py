# -*- coding: utf8 -*-

import unittest
import os

from model.PhaseModel import PhaseModel

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, 'data')
cif_path = os.path.join(data_path, "test.cif")


class PhaseModelTest(unittest.TestCase):
    def setUp(self):
        self.phase_model = PhaseModel()
