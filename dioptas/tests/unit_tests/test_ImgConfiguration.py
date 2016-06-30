# -*- coding: utf8 -*-

import unittest
import os
import numpy as np
from mock import MagicMock

from PyQt4 import QtGui

from model.ImgConfiguration import ImgConfigurationManager

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')


class ImgConfigurationManagerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtGui.QApplication.instance()
        if cls.app is None:
            cls.app = QtGui.QApplication([])

    def setUp(self):
        self.config_manager = ImgConfigurationManager()

    def test_add_configuration(self):
        self.config_manager.img_model.load(os.path.join(data_path, "image_001.tif"))

        prev_sum = np.sum(self.config_manager.img_model.img_data)
        self.assertTrue(np.array_equal(self.config_manager.img_model.img_data,
                                       self.config_manager.configurations[0].img_model.img_data))

        self.config_manager.add_configuration()
        new_sum = np.sum(self.config_manager.img_model.img_data)
        self.assertTrue(np.array_equal(self.config_manager.img_model.img_data,
                                       self.config_manager.configurations[1].img_model.img_data))

        self.assertNotEqual(prev_sum, new_sum)

    def test_remove_configuration(self):
        self.config_manager.add_configuration()
        self.config_manager.img_model.load(os.path.join(data_path, "image_001.tif"))
        old_img = self.config_manager.img_model.img_data

        self.config_manager.remove_configuration()
        self.assertFalse(np.array_equal(self.config_manager.img_model.img_data,
                                        old_img))

    def test_select_configuration(self):
        img_1 = self.config_manager.img_model.img_data

        self.config_manager.add_configuration()
        self.config_manager.img_model.load(os.path.join(data_path, "image_001.tif"))
        img_2 = self.config_manager.img_model.img_data


        self.config_manager.add_configuration()
        self.config_manager.img_model.load(os.path.join(data_path, "image_002.tif"))
        img_3 = self.config_manager.img_model.img_data

        self.config_manager.select_configuration(0)
        self.assertTrue(np.array_equal(self.config_manager.img_model.img_data,
                                        img_1))

        self.config_manager.select_configuration(2)
        self.assertTrue(np.array_equal(self.config_manager.img_model.img_data,
                                       img_3))

        self.config_manager.select_configuration(1)
        self.assertTrue(np.array_equal(self.config_manager.img_model.img_data,
                                       img_2))

    def test_signals_are_raised(self):
        self.config_manager.configuration_added = MagicMock()
        self.config_manager.configuration_selected = MagicMock()
        self.config_manager.configuration_removed = MagicMock()

        self.config_manager.add_configuration()
        self.config_manager.add_configuration()
        self.config_manager.configuration_added.emit.assert_called()

        self.config_manager.select_configuration(0)
        self.config_manager.configuration_selected.emit.assert_called_with(0)

        self.config_manager.remove_configuration(0)
        self.config_manager.configuration_removed.emit.assert_called_with(0)



