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

from model.util.cif import CifPhase, CifConverter

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')


class TestCifPhase(unittest.TestCase):
    def test_reading_phase(self):
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
        self.assertEqual(cif_phase.comments, 'HoN - NaCl structure type, ICSD 44776')

    def test_calculating_xrd_pattern_from_cif_file(self):
        fcc_cif = ReadCif(os.path.join(data_path, 'fcc.cif'))
        cif_phase = CifPhase(fcc_cif[fcc_cif.keys()[0]])
        cif_converter = CifConverter(0.31)
        jcpds_phase = cif_converter.convert_cif_phase_to_jcpds(cif_phase)

        self.assertAlmostEqual(jcpds_phase.reflections[0].intensity, 100, places=4)
        self.assertAlmostEqual(jcpds_phase.reflections[0].d0, 2.814, places=4)
        self.assertAlmostEqual(jcpds_phase.reflections[1].d0, 2.437, places=4)

    def test_loading_cif_phase_and_calculate_jcpds(self):
        cif_converter = CifConverter(0.31)
        jcpds_phase = cif_converter.convert_cif_to_jcpds(os.path.join(data_path, 'fcc.cif'))
        self.assertEqual(jcpds_phase.name, 'fcc')
        self.assertAlmostEqual(jcpds_phase.reflections[0].intensity, 100, places=4)
        self.assertAlmostEqual(jcpds_phase.reflections[0].d0, 2.814, places=4)
        self.assertAlmostEqual(jcpds_phase.reflections[1].d0, 2.437, places=4)

    def test_loading_cif_phase_with_occupancies_specified(self):
        cif_converter = CifConverter(0.31)
        jcpds_phase = cif_converter.convert_cif_to_jcpds(os.path.join(data_path, 'magnesiowustite.cif'))
        self.assertAlmostEqual(jcpds_phase.reflections[0].intensity, 27.53, delta=0.2)
        self.assertAlmostEqual(jcpds_phase.reflections[1].intensity, 100)
        self.assertAlmostEqual(jcpds_phase.reflections[2].intensity, 65.02, delta=0.2)
