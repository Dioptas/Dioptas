# -*- coding: utf8 -*-

import unittest
import os
import numpy as np
from mock import MagicMock

from qtpy import QtWidgets

from ...model.DioptasModel import DioptasModel
from ...model.util import Pattern

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')


class ImgConfigurationManagerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance()
        if cls.app is None:
            cls.app = QtWidgets.QApplication([])

    def setUp(self):
        self.model = DioptasModel()

    def test_add_configuration(self):
        self.model.img_model.load(os.path.join(data_path, "image_001.tif"))

        prev_sum = np.sum(self.model.img_data)
        self.assertTrue(np.array_equal(self.model.img_data,
                                       self.model.configurations[0].img_model.img_data))

        self.model.add_configuration()
        new_sum = np.sum(self.model.img_data)
        self.assertTrue(np.array_equal(self.model.img_data,
                                       self.model.configurations[1].img_model.img_data))

        self.assertNotEqual(prev_sum, new_sum)

    def test_remove_configuration(self):
        self.model.add_configuration()
        self.model.img_model.load(os.path.join(data_path, "image_001.tif"))
        old_img = self.model.img_data

        self.model.remove_configuration()
        self.assertFalse(np.array_equal(self.model.img_data,
                                        old_img))

    def test_select_configuration(self):
        img_1 = self.model.img_data

        self.model.add_configuration()
        self.model.img_model.load(os.path.join(data_path, "image_001.tif"))
        img_2 = self.model.img_data

        self.model.add_configuration()
        self.model.img_model.load(os.path.join(data_path, "image_002.tif"))
        img_3 = self.model.img_data

        self.model.select_configuration(0)
        self.assertTrue(np.array_equal(self.model.img_data,
                                       img_1))

        self.model.select_configuration(2)
        self.assertTrue(np.array_equal(self.model.img_data,
                                       img_3))

        self.model.select_configuration(1)
        self.assertTrue(np.array_equal(self.model.img_data,
                                       img_2))

    def test_signals_are_raised(self):
        self.model.configuration_added = MagicMock()
        self.model.configuration_selected = MagicMock()
        self.model.configuration_removed = MagicMock()

        self.model.add_configuration()
        self.model.add_configuration()
        self.model.configuration_added.emit.assert_called()

        self.model.select_configuration(0)
        self.model.configuration_selected.emit.assert_called_with(0)

        self.model.remove_configuration()
        self.model.configuration_removed.emit.assert_called_with(0)

    def test_integrate_cakes(self):
        self.model.calibration_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.poni'))
        self.model.current_configuration.integrate_cake = True
        self.model.img_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.tif'))
        self.assertFalse(np.array_equal(self.model.current_configuration.cake_img,
                                        np.zeros((2048, 2048))))

    def test_integrate_cake_with_mask(self):
        self.model.calibration_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.poni'))
        self.model.current_configuration.integrate_cake = True
        self.model.img_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.tif'))
        cake_img1 = self.model.current_configuration.cake_img

        self.model.use_mask = True
        self.model.mask_model.mask_below_threshold(self.model.img_data, 1)
        self.model.img_model.img_changed.emit()
        cake_img2 = self.model.current_configuration.cake_img
        self.assertFalse(np.array_equal(cake_img1, cake_img2))

    def test_combine_patterns(self):
        x1 = np.linspace(0, 10)
        y1 = np.ones(x1.shape)
        pattern1 = Pattern(x1, y1)

        x2 = np.linspace(7, 15)
        y2 = np.ones(x2.shape) * 2
        pattern2 = Pattern(x2, y2)

        self.model.pattern_model.pattern = pattern1
        self.model.add_configuration()
        self.model.pattern_model.pattern = pattern2

        self.model.combine_patterns = True

        x3, y3 = self.model.pattern.data
        self.assertLess(np.min(x3), 7)
        self.assertGreater(np.max(x3), 10)

    def test_combine_cakes(self):
        self.model.calibration_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.poni'))
        self.model.current_configuration.integrate_cake = True
        self.model.img_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.tif'))

        cake1 = self.model.cake_data
        self.model.add_configuration()

        self.model.calibration_model.load(os.path.join(data_path, 'CeO2_Pilatus1M_2.poni'))
        self.model.current_configuration.integrate_cake = True
        self.model.img_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.tif'))

        self.model.combine_cakes = True
        self.assertFalse(np.array_equal(self.model.cake_data, cake1))

    def test_setting_factors(self):
        self.model.img_model.load(os.path.join(data_path, "image_001.tif"))
        data1 = np.copy(self.model.img_data)
        self.model.img_model.factor = 2
        self.assertTrue(np.array_equal(2 * data1, self.model.img_data))

    def test_iterate_next_image(self):
        self.model.img_model.load(os.path.join(data_path, "image_001.tif"))
        self.model.add_configuration()
        self.model.img_model.load(os.path.join(data_path, "image_001.tif"))

        self.model.next_image()

        self.assertEqual(self.model.configurations[0].img_model.filename,
                         os.path.abspath(os.path.join(data_path, "image_002.tif")))
        self.assertEqual(self.model.configurations[1].img_model.filename,
                         os.path.abspath(os.path.join(data_path, "image_002.tif")))

    def test_iterate_previous_image(self):
        self.model.img_model.load(os.path.join(data_path, "image_002.tif"))
        self.model.add_configuration()
        self.model.img_model.load(os.path.join(data_path, "image_002.tif"))

        self.model.previous_image()

        self.assertEqual(self.model.configurations[0].img_model.filename,
                         os.path.abspath(os.path.join(data_path, "image_001.tif")))
        self.assertEqual(self.model.configurations[1].img_model.filename,
                         os.path.abspath(os.path.join(data_path, "image_001.tif")))


