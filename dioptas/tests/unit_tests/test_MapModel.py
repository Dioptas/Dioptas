# -*- coding: utf8 -*-

import unittest
import gc
import os
import numpy as np

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
        start_hor = 0.123
        hor_pos = start_hor
        ver_pos = -0.456
        hor_step = 0.005
        ver_step = 0.003
        counter = 1
        for map_file in map_files:
            motor_info = {'Horizontal': hor_pos,
                          'Vertical': ver_pos}
            self.map_model.add_file_to_map_data(map_file,
                                                os.path.join(map_path, 'patterns'),
                                                motor_info)
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

        self.fail()
