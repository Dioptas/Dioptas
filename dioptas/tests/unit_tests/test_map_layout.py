# SPDX-License-Identifier: MIT

import numpy as np
import pytest

from dioptas.model import map_layout
from dioptas.model.map_layout import BLANK


def values(n):
    return np.arange(n, dtype=float)


def test_plain_arrangement_is_row_major():
    grid, index_grid = map_layout.arrange(values(6), (2, 3))
    np.testing.assert_array_equal(grid, [[0, 1, 2], [3, 4, 5]])
    np.testing.assert_array_equal(index_grid, [[0, 1, 2], [3, 4, 5]])


def test_grid_larger_than_point_count_leaves_blanks():
    grid, index_grid = map_layout.arrange(values(4), (2, 3))
    np.testing.assert_array_equal(grid[0], [0, 1, 2])
    assert grid[1, 0] == 3
    assert np.isnan(grid[1, 1]) and np.isnan(grid[1, 2])
    np.testing.assert_array_equal(index_grid[1], [3, BLANK, BLANK])


def test_explicit_slots_place_a_blank_mid_scan():
    """A dropped frame: point 3 onwards shifts one cell along."""
    slots = [0, 1, 2, None, 3, 4]
    grid, index_grid = map_layout.arrange(values(5), (2, 3), slots=slots)
    np.testing.assert_array_equal(grid[0], [0, 1, 2])
    assert np.isnan(grid[1, 0])
    np.testing.assert_array_equal(grid[1, 1:], [3, 4])
    np.testing.assert_array_equal(index_grid[1], [BLANK, 3, 4])


def test_snake_reverses_every_other_row():
    grid, index_grid = map_layout.arrange(values(6), (2, 3), snake=True)
    np.testing.assert_array_equal(grid, [[0, 1, 2], [5, 4, 3]])
    np.testing.assert_array_equal(index_grid, [[0, 1, 2], [5, 4, 3]])


def test_transpose_and_flips():
    grid, _ = map_layout.arrange(values(6), (2, 3), transpose=True)
    np.testing.assert_array_equal(grid, [[0, 3], [1, 4], [2, 5]])

    grid, _ = map_layout.arrange(values(6), (2, 3), flip_horizontal=True)
    np.testing.assert_array_equal(grid, [[2, 1, 0], [5, 4, 3]])

    grid, _ = map_layout.arrange(values(6), (2, 3), flip_vertical=True)
    np.testing.assert_array_equal(grid, [[3, 4, 5], [0, 1, 2]])


def test_excluded_point_loses_its_cell_and_the_rest_close_up():
    grid, index_grid = map_layout.arrange(values(6), (2, 3), excluded=[4])
    # point 5 moves into the freed cell; the blank collects at the end
    np.testing.assert_array_equal(index_grid, [[0, 1, 2], [3, 5, BLANK]])
    assert np.isnan(grid[1, 2])


def test_including_a_point_again_restores_its_stored_place():
    slots = [0, 1, 2, 3, 4, 5]
    with_out = map_layout.fit_slots(slots, 6, 6, excluded=[2])
    assert with_out == [0, 1, 3, 4, 5, None]
    back = map_layout.fit_slots(slots, 6, 6, excluded=[])
    assert back == slots


def test_fit_slots_appends_points_the_arrangement_does_not_mention():
    # arrangement from a 3-point map, now used with 5 points
    slots = map_layout.fit_slots([0, None, 1, 2], 5, 6)
    assert slots == [0, 3, 1, 2, 4, None]


def test_fit_slots_drops_stale_and_duplicate_indices():
    slots = map_layout.fit_slots([0, 0, 9, 1], 3, 4)
    assert slots == [0, 2, None, 1]


def test_slot_edits():
    assert map_layout.insert_blank([0, 1, 2], 1) == [0, None, 1, 2]
    assert map_layout.remove_blank([0, None, 1], 1) == [0, 1]
    # a cell holding a point is not removable — excluding it is the way
    assert map_layout.remove_blank([0, 1, 2], 1) == [0, 1, 2]
    assert map_layout.move_slot([0, 1, 2], 0, 2) == [1, 2, 0]


def test_grid_for_rounds_up():
    assert map_layout.grid_for(10, 3) == (4, 3)
    assert map_layout.grid_for(9, 3) == (3, 3)


@pytest.mark.parametrize(
    "name, expected",
    [
        ("scan_0042.tif", 42),
        ("map_8_P1_E1_001.tif", 1),
        ("/some/dir/img.0007.cbf", 7),
        ("noNumbersHere.tif", None),
    ],
)
def test_filename_number(name, expected):
    assert map_layout.filename_number(name) == expected


def test_slots_from_filenames_inserts_blanks_for_missing_numbers():
    names = ["s_001.tif", "s_002.tif", "s_004.tif", "s_005.tif"]
    assert map_layout.slots_from_filenames(names) == [0, 1, None, 2, 3]


def test_slots_from_filenames_returns_none_when_nothing_is_missing():
    names = ["s_001.tif", "s_002.tif", "s_003.tif"]
    assert map_layout.slots_from_filenames(names) is None


def test_slots_from_filenames_ignores_unusable_numbering():
    # not increasing — the order tells us nothing about gaps
    assert map_layout.slots_from_filenames(["b_2.tif", "a_1.tif"]) is None
    # numbers too far apart to be a scan index
    assert map_layout.slots_from_filenames(["a_1.tif", "b_900.tif"]) is None
    # no numbers at all
    assert map_layout.slots_from_filenames(["a.tif", "b.tif"]) is None
