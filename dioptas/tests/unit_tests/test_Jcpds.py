# SPDX-License-Identifier: MIT
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


def test_copying_does_not_mark_as_modified(jcpds):
    """Copying is not editing.

    params is a dict subclass that flags itself when certain keys are written,
    and Python rebuilds a dict subclass by replaying its items through
    __setitem__ — so a plain copy used to come back claiming it had been
    edited, asterisk on the name and all.
    """
    from copy import copy, deepcopy

    jcpds.load_file(os.path.join(jcpds_path, 'au_Anderson.jcpds'))
    assert not jcpds.params['modified']

    for duplicate in (deepcopy(jcpds), copy(jcpds.params), deepcopy(jcpds.params)):
        params = duplicate.params if hasattr(duplicate, 'params') else duplicate
        assert not params['modified']

    assert deepcopy(jcpds).name == 'au_Anderson'
    assert not jcpds.params['modified']  # nor is the original touched


def test_copying_preserves_an_existing_modified_flag(jcpds):
    """A copy of an edited phase is still an edited phase."""
    from copy import copy, deepcopy

    jcpds.load_file(os.path.join(jcpds_path, 'au_Anderson.jcpds'))
    jcpds.params['k0'] = 200
    assert jcpds.params['modified']

    assert deepcopy(jcpds).params['modified']
    assert deepcopy(jcpds).name == 'au_Anderson*'
    assert copy(jcpds.params)['modified']


def test_deep_copy_is_independent_of_the_original(jcpds):
    from copy import deepcopy

    jcpds.load_file(os.path.join(jcpds_path, 'au_Anderson.jcpds'))
    jcpds.add_reflection(1, 0, 0, 100, 4.0)
    duplicate = deepcopy(jcpds)

    # add_reflection is a real edit, so both carry the flag
    assert duplicate.params['modified'] == jcpds.params['modified'] is True

    jcpds.params['k0'] = 999
    jcpds.reflections[0].d0 = 42.0
    assert duplicate.params['k0'] != 999
    assert duplicate.reflections[0].d0 != 42.0


def test_load_version3_file():
    # Dan Shim's old fixed format: bare version number, title,
    # "symmetry_code K0 K0'", lattice line, placeholder, labels, peaks.
    # The first line has no space, which crashed the loader for years.
    from ...model.util.jcpds import jcpds
    j = jcpds()
    j.load_file(os.path.join(jcpds_path, "au_version3.jcpds"))
    assert j.params["symmetry"] == "CUBIC"
    assert j.params["a0"] == pytest.approx(4.0786)
    assert j.params["k0"] == pytest.approx(166.6)
    assert j.params["k0p0"] == pytest.approx(5.5)
    assert len(j.reflections) == 3
    assert j.reflections[0].d0 == pytest.approx(2.355, abs=1e-3)
    assert j.params["comments"] == ["Gold (04-0784, Heinz and Jeanloz 1984)"]
