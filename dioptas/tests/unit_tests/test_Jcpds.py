# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2017  Clemens Prescher (clemens.prescher@gmail.com)
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
import gc
import os
from ...model.util import jcpds

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')
jcpds_path = os.path.join(data_path, 'jcpds')


class JcpdsUnitTest(unittest.TestCase):
    def setUp(self):
        self.jcpds = jcpds()

    def tearDown(self):
        del self.jcpds
        gc.collect()

    def test_sorting_of_reflections(self):
        self.jcpds.add_reflection(1, 0, 0, 100, 4.0)
        self.jcpds.add_reflection(1, 2, 0, 90, 2.0)
        self.jcpds.add_reflection(2, 2, 0, 23, 3.0)
        self.jcpds.add_reflection(5, 2, 1, 50, 6.0)
        self.jcpds.add_reflection(3, 2, 2, 10, 41.0)
        self.jcpds.add_reflection(4, 3, 0, 30, 1.0)
        self.jcpds.add_reflection(2, 2, 5, 2, 0.3)

        self.jcpds.sort_reflections_by_h()
        self.assertEqual(self.jcpds.reflections[0].d0, 4.0)
        self.assertEqual(self.jcpds.reflections[6].d0, 6.0)

        self.jcpds.sort_reflections_by_k()
        self.assertEqual(self.jcpds.reflections[0].d0, 4.0)
        self.assertEqual(self.jcpds.reflections[6].d0, 1.0)

        self.jcpds.sort_reflections_by_l()
        self.assertEqual(self.jcpds.reflections[0].d0, 4.0)
        self.assertEqual(self.jcpds.reflections[6].d0, 0.3)

        self.jcpds.sort_reflections_by_intensity()
        self.assertEqual(self.jcpds.reflections[0].d0, 0.3)
        self.assertEqual(self.jcpds.reflections[6].d0, 4.0)

        self.jcpds.sort_reflections_by_d()
        self.assertEqual(self.jcpds.reflections[0].intensity, 2)
        self.assertEqual(self.jcpds.reflections[6].intensity, 10)

    def test_modified_flag(self):
        self.assertFalse(self.jcpds.params['modified'])
        self.jcpds.params['a0'] = 3
        self.assertTrue(self.jcpds.params['modified'])
        self.assertEqual(self.jcpds.params['a0'], 3)
        self.jcpds.modified = False

        self.jcpds.load_file(os.path.join(jcpds_path, 'au_Anderson.jcpds'))
        self.assertFalse(self.jcpds.params['modified'])
        self.jcpds.params['k0'] = 200
        self.assertTrue(self.jcpds.params['modified'])
        self.assertEqual(os.path.join(jcpds_path, 'au_Anderson.jcpds*'), self.jcpds.filename)
        self.assertEqual('au_Anderson*', self.jcpds.name)

    def get_reflection_d_spacing(self, reflections, h, k, l):
        for reflection in reflections:
            if reflection.h == h and reflection.k == k and reflection.l == l:
                return reflection.d0

    def test_consistency_d_spacing_calculation(self):
        # loading a monoclinic jcpds and check if different signs will change the d spacing
        self.jcpds.load_file(os.path.join(jcpds_path, 'FeGeO3_cpx.jcpds'))

        d1_mon = self.get_reflection_d_spacing(self.jcpds.reflections, 2, 2, 1)
        d2_mon = self.get_reflection_d_spacing(self.jcpds.reflections, -2, 2, 1)

        self.jcpds.params['symmetry'] = 'TRICLINIC'
        self.jcpds.compute_d0()

        d1_tri = self.get_reflection_d_spacing(self.jcpds.reflections, 2, 2, 1)
        d2_tri = self.get_reflection_d_spacing(self.jcpds.reflections, -2, 2, 1)

        self.assertAlmostEqual(d1_mon, d1_tri)
        self.assertAlmostEqual(d2_mon, d2_tri)

    def test_using_negative_pressures(self):
        self.jcpds.load_file(os.path.join(jcpds_path, 'au_Anderson.jcpds'))
        self.jcpds.pressure = -1.

        self.jcpds.compute_d(-1, 298)
        self.assertGreater(self.jcpds.params['v'], self.jcpds.params['v0'])


if __name__ == '__main__':
    unittest.main()
