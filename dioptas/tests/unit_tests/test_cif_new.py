# Dioptas - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2015  Clemens Prescher (clemens.prescher@gmail.com)
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

import unittest
import os

from CifFile import ReadCif

from model.util.cif_new import CifPhase
from model.util.xrd import XRDCalculator

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')

class TestCifPhase(unittest.TestCase):
    def test_reading_phase(self):
        path = os.path.join(data_path, 'fcc.cif')
        print path
        fcc_cif = ReadCif(os.path.join(data_path, 'fcc.cif'))

        cif_phase = CifPhase(fcc_cif[fcc_cif.keys()[0]])


        self.assertEqual(cif_phase.a, 4.874)
        self.assertEqual(cif_phase.b, 4.874)
        self.assertEqual(cif_phase.c, 4.874)

        self.assertEqual(cif_phase.alpha, 90)
        self.assertEqual(cif_phase.beta, 90)
        self.assertEqual(cif_phase.gamma, 90)

        self.assertEqual(cif_phase.volume, 115.79)
        self.assertEqual(cif_phase.space_group_number, 225)

        self.assertEqual(len(cif_phase.atoms), 8)

    def test_calculating_xrd_pattern(self):
        fcc_cif = ReadCif(os.path.join(data_path, 'fcc.cif'))
        cif_phase = CifPhase(fcc_cif[fcc_cif.keys()[0]])

        xrd_calculator = XRDCalculator(cif_phase, 0.31)
        self.assertEqual
        self.assertEqual(xrd_calculator.peaks[0][1], 100)
        for peak in xrd_calculator.peaks:
            print peak
