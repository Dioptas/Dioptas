# -*- coding: utf-8 -*-
__author__ = 'Clemens Prescher'

import unittest
import sys
import os
import numpy as np
import gc
import time

from PyQt4 import QtGui, QtCore
from PyQt4.QtTest import QTest


from model.ImgModel import ImgModel
from model.MaskModel import MaskModel
from controller.MaskController import MaskController
from widgets.MaskWidget import MaskWidget

class MaskControllerTest(unittest.TestCase):
    def setUp(self):
        self.app = QtGui.QApplication(sys.argv)
        self.working_dir = {}

        self.img_model = ImgModel()
        self.mask_model = MaskModel()
        self.mask_widget = MaskWidget()
        self.mask_controller = MaskController(self.working_dir, self.mask_widget, self.img_model, self.mask_model)

    def tearDown(self):
        del self.img_model
        del self.mask_model
        self.mask_widget.close()
        del self.mask_widget
        del self.mask_controller
        del self.app
        gc.collect()


    def get_file_size(self, filename):
        stat_info = os.stat(filename)
        return stat_info.st_size

    def test_loading_and_saving_mask_files(self):
        self.mask_controller.load_mask_btn_click('Data/test.mask')
        self.mask_model.mask_below_threshold(self.img_model, 1)
        self.mask_controller.save_mask_btn_click('Data/test2.mask')
        self.assertTrue(os.path.exists('Data/test2.mask'))
        os.remove('Data/test2.mask')

    def test_loading_and_saving_with_super_sampling(self):
        self.mask_model.set_supersampling(2)
        self.mask_controller.load_mask_btn_click('Data/test.mask')

        self.assertEqual(self.mask_model.get_mask().shape[0], 4096)
        self.assertEqual(self.mask_model.get_mask().shape[1], 4096)

        self.assertEqual(self.mask_model.get_img().shape[0], 2048)
        self.assertEqual(self.mask_model.get_img().shape[1], 2048)

        self.mask_model.mask_below_threshold(self.img_model, 1)
        self.mask_controller.save_mask_btn_click('Data/test1.mask')
        self.assertEqual(self.get_file_size('Data/test1.mask'), self.get_file_size('Data/test.mask'))

    def test_grow_and_shrinking(self):
        self.mask_model.mask_ellipse(100,100,20,20)
        previous_mask = np.copy(self.mask_model._mask_data)

        QTest.mouseClick(self.mask_widget.grow_btn, QtCore.Qt.LeftButton)
        self.assertFalse(np.array_equal(previous_mask, self.mask_model._mask_data))

        QTest.mouseClick(self.mask_widget.shrink_btn, QtCore.Qt.LeftButton)
        self.assertTrue(np.array_equal(previous_mask, self.mask_model._mask_data))

