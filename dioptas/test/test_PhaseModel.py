# -*- coding: utf8 -*-
__author__ = 'Clemens Prescher'

import unittest
import os

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, 'data')
cif_path = os.path.join(data_path, "test.cif")

from model.PhaseModel import PhaseModel

class PhaseModelTest(unittest.TestCase):
    def setUp(self):
        self.phase_model = PhaseModel()

    def test_read_cif_file(self):
        self.phase_model.add_phase(cif_path)
        self.assertGreater(len(self.phase_model.phases), 0)

        print(self.phase_model.phases[0].a0)

