# -*- coding: utf8 -*-

import unittest
import gc
import os
import numpy as np
import random
import copy

from ...model.MapModel import MapModel, Map, Pattern
from ..utility import unittest_data_path

jcpds_path = os.path.join(unittest_data_path, 'jcpds')
map_img_path = os.path.join(unittest_data_path, 'map')
map_pattern_path = os.path.join(unittest_data_path, 'map', 'xy')
map_img_file_names = [f for f in os.listdir(map_img_path) if os.path.isfile(os.path.join(map_img_path, f))]
map_img_file_paths = [os.path.join(map_img_path, filename) for filename in map_img_file_names]
map_pattern_file_paths = [os.path.join(map_pattern_path, os.path.splitext(filename)[0]+'.xy') for filename in
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
        self.map.sort_points()

        self.assertEqual(len(self.map.sorted_points), len(self.map.points))
        self.assertEqual(len(self.map.sorted_map), 3)
        self.assertEqual(len(self.map.sorted_map[0]), len(self.map.points))

        x_diffs = np.diff(self.map.sorted_map[1])
        for x_diff in x_diffs:
            self.assertGreater(x_diff, 0)

        # add a random point add end to see if it still works
        self.add_point(map_pattern_file_paths[0], (-3, 3))
        self.map.sort_points()

        x_diffs = np.diff(self.map.sorted_map[1])
        for x_diff in x_diffs:
            self.assertGreater(x_diff, 0)

    def test_get_map_dimensions(self):
        self.create_organized_grid()
        self.map.sort_points()
        self.map.get_map_dimensions()

        self.assertEqual(self.map.min_x, -0.005)
        self.assertEqual(self.map.min_y, -0.004)

        self.assertEqual(self.map.num_x, 3)
        self.assertEqual(self.map.num_y, 3)

        self.assertEqual(self.map.diff_x, 0.005)
        self.assertEqual(self.map.diff_y, 0.004)

    def test_create_empty_map(self):
        self.create_organized_grid()
        self.map.sort_points()
        self.map.get_map_dimensions()
        self.map.create_empty_map()

        self.assertEqual(self.map.hor_size, 300)
        self.assertEqual(self.map.um_per_px_in_x, 0.005 / 100)
        self.assertEqual(self.map.um_per_px_in_y, 0.004 / 100)
        self.assertEqual(self.map.new_image.shape, (300, 300))

    def test_reset_map_grid(self):
        self.create_organized_grid()
        self.map.reset()
        self.assertTrue(self.map.is_empty())

    def test_num_points(self):
        self.create_organized_grid()
        self.assertEqual(self.map.num_points, 9)


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

        self.map.add_manual_map_positions(min_x, min_y, diff_x, diff_y, num_x,
                                          num_y, is_hor_first=True)
        self.assertAlmostEqual(self.map.points[0].position[0], 0.2)
        self.assertAlmostEqual(self.map.points[0].position[1], -0.15)
        self.assertAlmostEqual(self.map.points[1].position[0], 0.202)
        self.assertAlmostEqual(self.map.points[1] .position[1], -0.15)
        self.assertAlmostEqual(self.map.points[-1].position[0], 0.204)
        self.assertAlmostEqual(self.map.points[-1].position[1], -0.142)

        self.assertTrue(self.map.all_positions_defined())

        self.map.add_manual_map_positions(min_x, min_y, diff_x, diff_y, num_x,
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
        sorted_points = self.map.sort_map_points_by_name()

        result_files = [p.pattern_filename for p in sorted_points]
        self.assertEqual(result_files, map_files)



class MapModelTest(unittest.TestCase):
    def setUp(self):
        self.map_model = MapModel()
        self.img = np.zeros((10, 10))

        self.maxDiff = None  # to enable large comparisons

    def tearDown(self):
        del self.map_model
        del self.img
        gc.collect()

    def test_add_file_to_map_data(self):
        self.map_model.add_map_point(map_pattern_file_paths[0],
                                     Pattern.from_file(map_pattern_file_paths[0]),
                                     (0.1234, -0.4568),
                                     map_img_file_paths[0])

        self.assertEqual(len(self.map_model.map.points), 1)  # 1 file in map data

        # make sure motor positions are within 3 decimal points
        self.assertAlmostEqual(self.map_model.map[0].position[0], 0.1234)
        self.assertAlmostEqual(self.map_model.map[0].position[1], -0.4568)

    def test_add_roi_to_roi_list(self):
        self.assertEqual(len(self.map_model.map_roi_list), 0)
        self.helper_add_roi_to_roi_list()
        self.assertEqual(len(self.map_model.map_roi_list), 1)
        self.assertEqual(self.map_model.map_roi_list[0]['roi_letter'], self.roi_letter)
        self.assertEqual(self.map_model.map_roi_list[0]['roi_start'], str(self.roi_start))
        self.assertEqual(self.map_model.map_roi_list[0]['roi_end'], str(self.roi_end))

    def helper_add_roi_to_roi_list(self):
        self.roi_letter = 'A'
        self.roi_start = 4.231
        self.roi_end = 5.879
        item = self.roi_letter + '_' + str(self.roi_start) + '-' + str(self.roi_end)
        roi_full_name = item.split('_')
        new_roi_name = roi_full_name[1].split('-')
        new_roi = {'roi_letter': roi_full_name[0], 'roi_start': new_roi_name[0], 'roi_end': new_roi_name[1]}
        self.map_model.add_roi_to_roi_list(new_roi)

    def test_is_val_in_roi_range(self):
        self.helper_add_roi_to_roi_list()
        val1 = self.roi_start - 0.001
        val2 = self.roi_end + 0.001
        val3 = self.roi_start + 0.001
        val4 = self.roi_end - 0.001
        self.assertFalse(self.map_model.is_val_in_roi_range(val1))
        self.assertFalse(self.map_model.is_val_in_roi_range(val2))
        self.assertTrue(self.roi_letter in self.map_model.is_val_in_roi_range(val3))
        self.assertTrue(self.roi_letter in self.map_model.is_val_in_roi_range(val4))

    def test_calculate_roi_math(self):
        math_to_perform = '(A + B)/2.0'
        self.map_model.roi_math = math_to_perform
        sum_int = {'A': 1.3,
                   'B': 4.7}
        result = self.map_model.calculate_roi_math(sum_int)
        for letter in sum_int:
            math_to_perform = math_to_perform.replace(letter, str(sum_int[letter]))
        self.assertEqual(result, eval(math_to_perform))

    def test_pos_to_range(self):
        min_hor = 0.14
        pix_per_hor = 100
        diff_hor = 0.005
        hor1 = min_hor + 3 * diff_hor
        range1 = self.map_model.pos_to_range(hor1, min_hor, pix_per_hor, diff_hor)
        self.assertAlmostEqual(range1.start, 3 * pix_per_hor, 7)
        self.assertAlmostEqual(range1.stop, 4 * pix_per_hor, 7)

    @unittest.skip
    def test_prepare_map_data_updates_map_image(self):
        map_path = os.path.join(unittest_data_path, 'map')
        self.helper_prepare_good_map(map_path)
        self.map_model.organize_map_files()

        self.helper_add_roi_to_roi_list()

        empty_map_image = self.map_model.new_image.copy()
        self.assertTrue(not np.any(empty_map_image))

        self.map_model.check_roi_math()
        self.map_model.prepare_map_data()
        self.assertFalse(np.array_equal(empty_map_image, self.map_model.new_image))
