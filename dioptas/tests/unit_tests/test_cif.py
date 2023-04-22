# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
# Principal author: Clemens Prescher (clemens.prescher@gmail.com)
# Copyright (C) 2014-2019 GSECARS, University of Chicago, USA
# Copyright (C) 2015-2018 Institute for Geology and Mineralogy, University of Cologne, Germany
# Copyright (C) 2019-2020 DESY, Hamburg, Germany
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
import os
import unittest
try:
    from urllib import pathname2url
except ImportError:
    from urllib.request import pathname2url

from CifFile import ReadCif

from ...model.util.cif import CifPhase, CifConverter

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')
cif_path = os.path.join(data_path, 'cif')


def get_cif_url(cif_filename):
    file_path = 'file:' + pathname2url(
        os.path.join(cif_path, cif_filename))
    return file_path


class TestCifModule(unittest.TestCase):
    def test_reading_phase(self):
        fcc_cif = ReadCif(get_cif_url('fcc.cif'))

        cif_phase = CifPhase(fcc_cif[fcc_cif.keys()[0]])

        self.assertEqual(cif_phase.a, 4.874)
        self.assertEqual(cif_phase.b, 4.874)
        self.assertEqual(cif_phase.c, 4.874)

        self.assertEqual(cif_phase.alpha, 90)
        self.assertEqual(cif_phase.beta, 90)
        self.assertEqual(cif_phase.gamma, 90)

        self.assertAlmostEqual(cif_phase.volume, 115.79, places=2)
        self.assertEqual(cif_phase.space_group_number, 225)

        self.assertEqual(len(cif_phase.atoms), 8)
        self.assertEqual(cif_phase.comments, 'HoN, Fm-3m - NaCl structure type, ICSD 44776')

    def test_calculating_xrd_pattern_from_cif_file(self):
        fcc_cif = ReadCif(get_cif_url('fcc.cif'))
        cif_phase = CifPhase(fcc_cif[fcc_cif.keys()[0]])
        cif_converter = CifConverter(0.31)
        jcpds_phase = cif_converter.convert_cif_phase_to_jcpds(cif_phase)

        self.assertAlmostEqual(jcpds_phase.reflections[0].intensity, 100, places=4)
        self.assertAlmostEqual(jcpds_phase.reflections[0].d0, 2.814, places=4)
        self.assertAlmostEqual(jcpds_phase.reflections[1].d0, 2.437, places=4)

    def test_loading_cif_phase_and_calculate_jcpds(self):
        cif_converter = CifConverter(0.31)
        jcpds_phase = cif_converter.convert_cif_to_jcpds(os.path.join(cif_path, 'fcc.cif'))
        self.assertEqual(jcpds_phase.name, 'fcc')
        self.assertAlmostEqual(jcpds_phase.reflections[0].intensity, 100, places=4)
        self.assertAlmostEqual(jcpds_phase.reflections[0].d0, 2.814, places=4)
        self.assertAlmostEqual(jcpds_phase.reflections[1].d0, 2.437, places=4)

    def test_loading_cif_phase_with_occupancies_specified(self):
        cif_converter = CifConverter(0.31)
        jcpds_phase = cif_converter.convert_cif_to_jcpds(os.path.join(cif_path, 'magnesiowustite.cif'))
        self.assertAlmostEqual(jcpds_phase.reflections[0].intensity, 27.53, delta=0.2)
        self.assertAlmostEqual(jcpds_phase.reflections[1].intensity, 100)
        self.assertAlmostEqual(jcpds_phase.reflections[2].intensity, 65.02, delta=0.2)

    def test_reading_american_mineralogist_db_cif(self):
        cif_converter = CifConverter(0.31)
        jcpds_phase = cif_converter.convert_cif_to_jcpds(os.path.join(cif_path, 'amcsd.cif'))
        self.assertEqual(jcpds_phase.params['a0'], 5.4631)
        self.assertAlmostEqual(jcpds_phase.reflections[0].intensity, 73.48, delta=0.6)
        self.assertAlmostEqual(jcpds_phase.reflections[1].intensity, 100)
        self.assertAlmostEqual(jcpds_phase.reflections[2].intensity, 33.6, delta=0.4)
        self.assertAlmostEqual(jcpds_phase.reflections[3].intensity, 14.65, delta=0.4)

    def test_read_cif_with_errors_in_atomic_positions(self):
        cif_converter = CifConverter(0.31, min_d_spacing=1.5, min_intensity=10)
        jcpds_phase = cif_converter.convert_cif_to_jcpds(os.path.join(cif_path, 'apatite.cif'))
        self.assertEqual(jcpds_phase.params['a0'], 9.628)

    def test_read_cif_from_shelx(self):
        cif_converter = CifConverter(0.31)
        jcpds_phase = cif_converter.convert_cif_to_jcpds(os.path.join(cif_path, 'Fe2O3_shelx.cif'))
        self.assertEqual(jcpds_phase.params['a0'], 6.524)
        self.assertEqual(jcpds_phase.params['b0'], 4.702)
        self.assertEqual(jcpds_phase.params['c0'], 4.603)

    def test_read_cif_with_triclinic_geometry(self):
        cif_converter = CifConverter(0.31, min_d_spacing=1, min_intensity=5)
        jcpds_phase = cif_converter.convert_cif_to_jcpds(os.path.join(cif_path, 'ICSD_triclinic.cif'))



