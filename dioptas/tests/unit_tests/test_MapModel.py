# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2019 Clemens Prescher (clemens.prescher@gmail.com)
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
import numpy as np
import random

from ...model import ImgModel, CalibrationModel, MaskModel
from ...model.Configuration import Configuration
from ...model.MapModel import MapModel, Map, Pattern, Roi, find_possible_dimensions
from ..utility import unittest_data_path

jcpds_path = os.path.join(unittest_data_path, 'jcpds')
map_img_path = os.path.join(unittest_data_path, 'map')
map_pattern_path = os.path.join(unittest_data_path, 'map', 'xy')
map_img_file_names = [f for f in os.listdir(map_img_path) if os.path.isfile(os.path.join(map_img_path, f))]
map_img_file_paths = [os.path.join(map_img_path, filename) for filename in map_img_file_names]
map_pattern_file_paths = [os.path.join(map_pattern_path, os.path.splitext(filename)[0] + '.xy') for filename in
                          map_img_file_names]


class MapTest(unittest.TestCase):
    def setUp(self):
        self.map = Map()

    def add_point(self, pattern_filename, position=None, img_filename=None):
        pattern = Pattern.from_file(pattern_filename)
        self.map.add_point(pattern_filename, pattern, position, img_filename)

    def create_grid(self):
        x, y = 0, 0
        for ind in range(9):
            self.add_point(map_pattern_file_paths[ind], [x, y])
            x += 1
            y += 1

    def create_organized_grid(self):
        x = np.linspace(-.005, 0.005, 3)
        y = np.linspace(-.004, 0.004, 3)
        x_grid, y_grid = np.meshgrid(x, y)
        x_grid = x_grid.flatten()
        y_grid = y_grid.flatten()
        for filename, x, y in zip(map_pattern_file_paths, x_grid, y_grid):
            self.add_point(filename, (x, y))

    def test_add_point_to_grid(self):
        pattern_filename = map_pattern_file_paths[0]
        pattern = Pattern.from_file(map_pattern_file_paths[0])
        self.map.add_point(pattern_filename, pattern)
        self.assertGreater(len(self.map.points), 0)

    def test_all_positions_defined(self):
        self.create_grid()

        self.assertTrue(self.map.all_positions_defined())

        pattern = Pattern.from_file(map_pattern_file_paths[0])
        self.map.add_point(map_pattern_file_paths[0], pattern)

        self.assertFalse(self.map.all_positions_defined())

    def test_organize_map_points(self):
        self.create_grid()
        self.map._sort_points()

        self.assertEqual(len(self.map.sorted_points), len(self.map.points))
        self.assertEqual(len(self.map.sorted_map), 3)
        self.assertEqual(len(self.map.sorted_map[0]), len(self.map.points))

        x_diffs = np.diff(self.map.sorted_map[1])
        for x_diff in x_diffs:
            self.assertGreater(x_diff, 0)

        # add a random point add end to see if it still works
        self.add_point(map_pattern_file_paths[0], (-3, 3))
        self.map._sort_points()

        x_diffs = np.diff(self.map.sorted_map[1])
        for x_diff in x_diffs:
            self.assertGreater(x_diff, 0)

    def test_get_map_dimensions(self):
        self.create_organized_grid()
        self.map._sort_points()
        self.map._get_map_dimensions()

        self.assertEqual(self.map.min_x, -0.005)
        self.assertEqual(self.map.min_y, -0.004)

        self.assertEqual(self.map.num_x, 3)
        self.assertEqual(self.map.num_y, 3)

        self.assertEqual(self.map.diff_x, 0.005)
        self.assertEqual(self.map.diff_y, 0.004)

    def test_create_empty_map(self):
        self.create_organized_grid()
        self.map._sort_points()
        self.map._get_map_dimensions()
        self.map._create_empty_map()

        self.assertEqual(self.map.hor_size, 300)
        self.assertEqual(self.map.um_per_px_in_x, 0.005 / 100)
        self.assertEqual(self.map.um_per_px_in_y, 0.004 / 100)
        self.assertEqual(self.map.new_image.shape, (300, 300))

    def test_reset_map_grid(self):
        self.create_organized_grid()
        self.map.reset()
        self.assertTrue(self.map.is_empty())

    def test_len_of_map(self):
        self.create_organized_grid()
        self.assertEqual(len(self.map), 9)

    def test_add_manual_map_positions(self):
        for ind in range(9):
            self.add_point(map_pattern_file_paths[ind])
        self.assertFalse(self.map.all_positions_defined())
        # First change the positions manually to something different and make sure that map_data changes
        min_x = 0.2
        min_y = -0.15
        diff_x = 0.002
        diff_y = 0.004
        num_x = 3
        num_y = 3

        self.map.set_manual_positions(min_x, min_y, diff_x, diff_y, num_x,
                                      num_y, is_hor_first=True)
        self.assertAlmostEqual(self.map.points[0].position[0], 0.2)
        self.assertAlmostEqual(self.map.points[0].position[1], -0.15)
        self.assertAlmostEqual(self.map.points[1].position[0], 0.202)
        self.assertAlmostEqual(self.map.points[1].position[1], -0.15)
        self.assertAlmostEqual(self.map.points[-1].position[0], 0.204)
        self.assertAlmostEqual(self.map.points[-1].position[1], -0.142)

        self.assertTrue(self.map.all_positions_defined())

        self.map.set_manual_positions(min_x, min_y, diff_x, diff_y, num_x,
                                      num_y, is_hor_first=False)
        self.assertAlmostEqual(self.map.points[0].position[0], 0.2)
        self.assertAlmostEqual(self.map.points[0].position[1], -0.15)
        self.assertAlmostEqual(self.map.points[1].position[0], 0.200)
        self.assertAlmostEqual(self.map.points[1].position[1], -0.146)
        self.assertAlmostEqual(self.map.points[-1].position[0], 0.204)
        self.assertAlmostEqual(self.map.points[-1].position[1], -0.142)

    def test_sort_map_files_by_natural_name(self):
        map_files = ['map1', 'map2', 'map3', 'map4', 'map5', 'map6', 'map7', 'map8', 'map9']
        shuffled_map_files = map_files.copy()
        random.shuffle(shuffled_map_files)
        self.assertNotEqual(map_files, shuffled_map_files)

        for map_file in shuffled_map_files:
            self.map.add_point(map_file, Pattern())
        sorted_points = self.map.sort_points_by_name()

        result_files = [p.pattern_filename for p in sorted_points]
        self.assertEqual(result_files, map_files)

    def test_pos_to_range(self):
        min_hor = 0.14
        pix_per_hor = 100
        diff_hor = 0.005
        hor1 = min_hor + 3 * diff_hor
        range1 = self.map.pos_to_range(hor1, min_hor, pix_per_hor, diff_hor)
        self.assertAlmostEqual(range1.start, 3 * pix_per_hor, 7)
        self.assertAlmostEqual(range1.stop, 4 * pix_per_hor, 7)

    def test_map_coordinates_from_xy(self):
        self.create_organized_grid()
        self.map.prepare()
        self.assertEqual(self.map.position_from_xy(0, 0), (-0.005, -0.004))
        self.assertEqual(self.map.position_from_xy(101, 0), (0.000, -0.004))
        self.assertNotEqual(self.map.position_from_xy(99, 0), (0.000, -0.004))

        self.assertEqual(self.map.position_from_xy(0, 101), (-0.005, 0))
        self.assertEqual(self.map.position_from_xy(101, 101), (0, 0))

    def test_filename_from_map_coordinates(self):
        self.create_organized_grid()
        self.map.prepare()
        self.assertEqual(self.map.filenames_from_position((0, 0)),
                         (map_pattern_file_paths[4], None))
        self.assertEqual(self.map.filenames_from_position((0.005, 0.004)),
                         (map_pattern_file_paths[-1], None))
        self.assertEqual(self.map.filenames_from_position((0, -0.004)),
                         (map_pattern_file_paths[1], None))

    def test_find_possible_dimensions(self):
        self.assertEqual(find_possible_dimensions(9), [(3, 3), (1, 9), (9, 1)])
        self.assertEqual(find_possible_dimensions(12), [(3, 4), (4, 3), (2, 6), (6, 2), (1, 12), (12, 1)])
        self.assertEqual(find_possible_dimensions(24),
                         [(4, 6), (6, 4), (3, 8), (8, 3), (2, 12), (12, 2), (1, 24), (24, 1)])
        self.assertEqual(find_possible_dimensions(100),
                         [(10, 10), (5, 20), (20, 5), (4, 25), (25, 4), (2, 50), (50, 2), (1, 100), (100, 1)])

        self.assertEqual(find_possible_dimensions(40 ** 2),
                         [(40, 40), (32, 50), (50, 32), (25, 64), (64, 25), (20, 80), (80, 20), (16, 100), (100, 16),
                          (10, 160), (160, 10), (8, 200), (200, 8), (5, 320), (320, 5), (4, 400), (400, 4), (2, 800),
                          (800, 2), (1, 1600), (1600, 1)])


class RoiTest(unittest.TestCase):
    def setUp(self):
        self.roi = Roi(2, 4, 'A')

    def test_is_in_roi(self):
        self.assertTrue(self.roi.is_in_roi(2.5))
        self.assertTrue(self.roi.is_in_roi(3.999999))
        self.assertTrue(self.roi.is_in_roi(3))

        self.assertFalse(self.roi.is_in_roi(5))
        self.assertFalse(self.roi.is_in_roi(1))
        self.assertFalse(self.roi.is_in_roi(1.9))
        self.assertFalse(self.roi.is_in_roi(2))

    def test_ind_in_roi(self):
        x = np.array([1.0, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5])
        indices = self.roi.ind_in_roi(x)
        self.assertTrue(np.array_equal(indices, np.array([3, 4, 5])))

        x = np.linspace(4, 12)
        indices = self.roi.ind_in_roi(x)
        self.assertEqual(len(indices), 0)


class MapModelTest(unittest.TestCase):
    def setUp(self):
        self.configuration = Configuration()
        self.map_model = MapModel(self.configuration)
        self.img = np.zeros((10, 10))

        self.maxDiff = None  # to enable large comparisons

    def tearDown(self):
        del self.map_model
        del self.img
        gc.collect()

    def add_point(self, pattern_filename, position=None, img_filename=None):
        pattern = Pattern.from_file(pattern_filename)
        self.map_model.add_map_point(pattern_filename, pattern, position, img_filename)

    def create_organized_grid(self):
        x = np.linspace(-.005, 0.005, 3)
        y = np.linspace(-.004, 0.004, 3)
        x_grid, y_grid = np.meshgrid(x, y)
        x_grid = x_grid.flatten()
        y_grid = y_grid.flatten()
        for filename, x, y in zip(map_pattern_file_paths, x_grid, y_grid):
            self.add_point(filename, (x, y))

    def test_add_file_to_map_data(self):
        self.map_model.add_map_point(map_pattern_file_paths[0],
                                     Pattern.from_file(map_pattern_file_paths[0]),
                                     (0.1234, -0.4568),
                                     map_img_file_paths[0])

        self.assertEqual(len(self.map_model.map.points), 1)  # 1 file in map data

        # make sure motor positions are within 3 decimal points
        self.assertAlmostEqual(self.map_model.map[0].position[0], 0.1234)
        self.assertAlmostEqual(self.map_model.map[0].position[1], -0.4568)

    def test_calculate_roi_math(self):
        math_to_perform = '(A + B)/2.0'
        self.map_model.roi_math = math_to_perform
        sum_int = {'A': 1.3,
                   'B': 4.7}
        result = self.map_model.calculate_roi_math(sum_int)
        for letter in sum_int:
            math_to_perform = math_to_perform.replace(letter, str(sum_int[letter]))
        self.assertEqual(result, eval(math_to_perform))

    def test_create_a_map_image(self):
        self.create_organized_grid()
        self.map_model.add_roi(7, 9, 'A')
        self.map_model.calculate_map_data()

    def test_load_images(self):
        self.configuration.img_model.load(map_img_file_paths[0])
        self.configuration.calibration_model.load(os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni"))
        self.map_model.load_img_map(map_img_file_paths)
        self.assertEqual(self.map_model.data.shape[0], len(map_pattern_file_paths))
        self.assertEqual(len(self.map_model.map.points), len(map_pattern_file_paths))
        self.assertEqual(self.map_model.possible_dimensions, [(3, 3), (1, 9), (9, 1)])
        self.assertTrue(self.map_model.map.all_positions_defined())

        self.map_model.add_roi(4, 6, "interactive")
        self.map_model.calculate_map_data()

        print(self.map_model.map.filenames_from_position((1, 1)))
