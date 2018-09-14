# -*- coding: utf8 -*-

import unittest
import gc
import os
import numpy as np
import random
import copy

from mock import MagicMock


from ...model.MapModel import MapModel

from ..utility import delete_if_exists

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')


class MapModelTest(unittest.TestCase):
    def setUp(self):
        self.map_model = MapModel()
        self.img = np.zeros((10, 10))

    def tearDown(self):
        # delete_if_exists(os.path.join(data_path, "test_save.mask"))
        del self.map_model
        del self.img
        gc.collect()

    def test_add_file_to_map_data(self):
        # QtWidgets.QFileDialog.getSaveFileName = MagicMock(return_value=os.path.join(unittest_data_path, "test.xy"))
        first_file = 'CeO2_Pilatus1M.tif'
        first_file_path = os.path.join(data_path, first_file)
        hor = 0.1234
        ver = -0.4568
        motors_info = {'Horizontal': str(hor),
                       'Vertical': str(ver),
                       }
        self.assertEqual(len(self.map_model.map_data), 0)  # start with empty map data
        self.map_model.add_file_to_map_data(first_file_path,
                                            os.path.join(data_path, 'map/patterns'),
                                            motors_info)
        self.assertEqual(len(self.map_model.map_data), 1)  # 1 file in map data
        # make sure motor positions are within 3 decimal points
        self.assertAlmostEqual(float(self.map_model.map_data[first_file_path]['pos_hor']), hor, 3)
        self.assertAlmostEqual(float(self.map_model.map_data[first_file_path]['pos_ver']), ver, 3)

    def test_add_file_to_map_data_without_motor_info(self):
        first_file = 'CeO2_Pilatus1M.tif'
        first_file_path = os.path.join(data_path, first_file)
        self.map_model.add_file_to_map_data(first_file_path,
                                            os.path.join(data_path, 'map/patterns'),
                                            None)
        self.assertFalse(self.map_model.all_positions_defined_in_files)

    def test_organize_map_data(self):
        map_path = os.path.join(data_path, 'map')
        map_files = [f for f in os.listdir(map_path) if os.path.isfile(os.path.join(map_path, f))]
        working_dir = os.path.join(map_path, 'patterns')
        if not os.path.exists(working_dir):
            os.mkdir(working_dir)
        start_hor = 0.123
        hor_pos = start_hor
        ver_pos = -0.456
        hor_step = 0.005
        ver_step = 0.003
        counter = 1
        for map_file in map_files:
            motor_info = {'Horizontal': hor_pos,
                          'Vertical': ver_pos}
            self.map_model.add_file_to_map_data(map_file, working_dir, motor_info)
            hor_pos += hor_step
            if counter == 3:
                ver_pos += ver_step
                hor_pos = start_hor
                counter = 0
            counter += 1

        self.assertEqual(len(self.map_model.map_data), len(map_files))
        self.assertTrue(self.map_model.all_positions_defined_in_files)
        # after all files loaded, test organization
        self.map_model.organize_map_files()
        self.assertEqual(self.map_model.num_hor, 3)
        self.assertEqual(self.map_model.num_ver, 3)
        self.assertAlmostEqual(self.map_model.diff_hor, 0.005, 5)
        self.assertAlmostEqual(self.map_model.diff_ver, 0.003, 5)

    def test_check_map(self):
        map_path = os.path.join(data_path, 'map')
        map_files = [f for f in os.listdir(map_path) if os.path.isfile(os.path.join(map_path, f))]
        working_dir = os.path.join(map_path, 'patterns')
        if not os.path.exists(working_dir):
            os.mkdir(working_dir)
        hor_pos = 0.123
        ver_pos = -0.456
        hor_step = 0.005
        ver_step = 0.003
        for map_file in map_files:
            motor_info = {'Horizontal': hor_pos,
                          'Vertical': ver_pos}
            self.map_model.add_file_to_map_data(map_file, working_dir, motor_info)
            hor_pos += hor_step
            ver_pos += ver_step

        self.assertEqual(len(self.map_model.map_data), len(map_files))
        self.assertTrue(self.map_model.all_positions_defined_in_files)
        # after all files loaded, test organization
        self.map_model.organize_map_files()
        self.assertFalse(self.map_model.check_map())

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

    def test_sort_map_files_by_natural_name(self):
        map_files = ['map1', 'map2', 'map3']
        for map_file in map_files:
            self.map_model.map_data[map_file] = {}
        sorted_list = self.map_model.sort_map_files_by_natural_name()
        self.assertEqual(sorted_list, map_files)

    def test_add_manual_map_positions(self):
        map_path = os.path.join(data_path, 'map')
        map_files = [f for f in os.listdir(map_path) if os.path.isfile(os.path.join(map_path, f))]
        self.test_organize_map_data()
        old_map_data = copy.deepcopy(self.map_model.map_data)

        # First change the positions manually to something different and make sure that map_data changes

        hor_min = 0.268
        ver_min = -0.101
        hor_step = 0.002
        ver_step = 0.004

        hor_num = 3
        ver_num = 3
        is_hor_first = True
        self.map_model.add_manual_map_positions(hor_min, ver_min, hor_step, ver_step, hor_num, ver_num,
                                                is_hor_first, map_files)
        self.assertNotEqual(self.map_model.map_data, old_map_data)

        # Then change back manually to the same positions in the organize_map_test and make sure the map_data returns

        hor_min = 0.123
        ver_min = -0.456
        hor_step = 0.005
        ver_step = 0.003
        self.map_model.add_manual_map_positions(hor_min, ver_min, hor_step, ver_step, hor_num, ver_num,
                                                is_hor_first, map_files)
        self.assertEqual(self.map_model.map_data, old_map_data)
        self.assertDictEqual(self.map_model.map_data, old_map_data)

    def test_prepare_map_data(self):
        map_path = os.path.join(data_path, 'map')
        map_files = [f for f in os.listdir(map_path) if os.path.isfile(os.path.join(map_path, f))]
        self.test_organize_map_data()
        self.helper_add_roi_to_roi_list()
        self.map_model.prepare_map_data()
