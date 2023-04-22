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

import pytest

from ...model.util import jcpds as jcpds_class

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')
jcpds_path = os.path.join(data_path, 'jcpds')


@pytest.fixture
def jcpds():
    return jcpds_class()


def test_sorting_of_reflections(jcpds):
    jcpds.add_reflection(1, 0, 0, 100, 4.0)
    jcpds.add_reflection(1, 2, 0, 90, 2.0)
    jcpds.add_reflection(2, 2, 0, 23, 3.0)
    jcpds.add_reflection(5, 2, 1, 50, 6.0)
    jcpds.add_reflection(3, 2, 2, 10, 41.0)
    jcpds.add_reflection(4, 3, 0, 30, 1.0)
    jcpds.add_reflection(2, 2, 5, 2, 0.3)

    jcpds.sort_reflections_by_h()
    assert jcpds.reflections[0].d0 == 4.0
    assert jcpds.reflections[6].d0 == 6.0

    jcpds.sort_reflections_by_k()
    assert jcpds.reflections[0].d0 == 4.0
    assert jcpds.reflections[6].d0 == 1.0

    jcpds.sort_reflections_by_l()
    assert jcpds.reflections[0].d0 == 4.0
    assert jcpds.reflections[6].d0 == 0.3

    jcpds.sort_reflections_by_intensity()
    assert jcpds.reflections[0].d0 == 0.3
    assert jcpds.reflections[6].d0 == 4.0

    jcpds.sort_reflections_by_d()
    assert jcpds.reflections[0].intensity == 2
    assert jcpds.reflections[6].intensity == 10


def test_modified_flag(jcpds):
    assert not jcpds.params['modified']
    jcpds.params['a0'] = 3
    assert jcpds.params['modified']
    assert jcpds.params['a0'] == 3
    jcpds.modified = False

    jcpds.load_file(os.path.join(jcpds_path, 'au_Anderson.jcpds'))
    assert not jcpds.params['modified']
    jcpds.params['k0'] = 200
    assert jcpds.params['modified']
    assert os.path.join(jcpds_path, 'au_Anderson.jcpds*') == jcpds.filename
    assert 'au_Anderson*' == jcpds.name


def get_reflection_d_spacing(reflections, h, k, l):
    for reflection in reflections:
        if reflection.h == h and reflection.k == k and reflection.l == l:
            return reflection.d0


def test_consistency_d_spacing_calculation(jcpds):
    # loading a monoclinic jcpds and check if different signs will change the d spacing
    jcpds.load_file(os.path.join(jcpds_path, 'FeGeO3_cpx.jcpds'))

    d1_mon = get_reflection_d_spacing(jcpds.reflections, 2, 2, 1)
    d2_mon = get_reflection_d_spacing(jcpds.reflections, -2, 2, 1)

    jcpds.params['symmetry'] = 'TRICLINIC'
    jcpds.compute_d0()

    d1_tri = get_reflection_d_spacing(jcpds.reflections, 2, 2, 1)
    d2_tri = get_reflection_d_spacing(jcpds.reflections, -2, 2, 1)

    assert d1_mon == pytest.approx(d1_tri)
    assert d2_mon == pytest.approx(d2_tri)


def test_using_negative_pressures(jcpds):
    jcpds.load_file(os.path.join(jcpds_path, 'au_Anderson.jcpds'))
    jcpds.pressure = -1.

    jcpds.compute_d(-1, 298)
    assert jcpds.params['v'] > jcpds.params['v0']


def test_using_negative_pressures_with_zero_bulk_modulus(jcpds):
    jcpds.load_file(os.path.join(jcpds_path, 're_K0.jcpds'))
    jcpds.pressure = -1.

    jcpds.compute_d(-1, 298)
    assert jcpds.params['v'] == jcpds.params['v0']
