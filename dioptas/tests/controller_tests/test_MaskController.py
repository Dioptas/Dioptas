# -*- coding: utf-8 -*-

from ..utility import QtTest
import os
import gc
import numpy as np

from qtpy import QtWidgets, QtCore
from qtpy.QtTest import QTest

from ...model.DioptasModel import DioptasModel
from ...controller.MaskController import MaskController
from ...widgets.MaskWidget import MaskWidget

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')


class MaskControllerTest(QtTest):

    def setUp(self):
        self.working_dir = {}

        self.model = DioptasModel()
        self.mask_widget = MaskWidget()
        self.mask_controller = MaskController(self.working_dir, self.mask_widget, self.model)

    def tearDown(self):
        del self.model
        self.mask_widget.close()
        del self.mask_widget
        del self.mask_controller
        gc.collect()

    def get_file_size(self, filename):
        stat_info = os.stat(filename)
        return stat_info.st_size

    def test_loading_and_saving_mask_files(self):
        self.mask_controller.load_mask_btn_click(os.path.join(data_path, 'test.mask'))
        self.model.mask_model.mask_below_threshold(self.model.img_data, 1)
        filename = os.path.join(data_path, 'dummy.mask')
        self.mask_controller.save_mask_btn_click(filename)
        self.assertTrue(os.path.exists(filename))
        os.remove(filename)

    def test_loading_and_saving_with_super_sampling(self):
        self.model.mask_model.set_supersampling(2)
        self.mask_controller.load_mask_btn_click(os.path.join(data_path, 'test.mask'))

        self.assertEqual(self.model.mask_model.get_mask().shape[0], 4096)
        self.assertEqual(self.model.mask_model.get_mask().shape[1], 4096)

        self.assertEqual(self.model.mask_model.get_img().shape[0], 2048)
        self.assertEqual(self.model.mask_model.get_img().shape[1], 2048)

        self.model.mask_model.mask_below_threshold(self.model.img_data, 1)

        filename = os.path.join(data_path, 'dummy.mask')
        self.mask_controller.save_mask_btn_click(filename)
        self.assertAlmostEqual(self.get_file_size(filename), self.get_file_size(os.path.join(data_path, 'test.mask')),
                               delta=1000)

    def test_grow_and_shrinking(self):
        self.model.mask_model.mask_ellipse(100, 100, 20, 20)
        previous_mask = np.copy(self.model.mask_model._mask_data)

        QTest.mouseClick(self.mask_widget.grow_btn, QtCore.Qt.LeftButton)
        self.assertFalse(np.array_equal(previous_mask, self.model.mask_model._mask_data))

        QTest.mouseClick(self.mask_widget.shrink_btn, QtCore.Qt.LeftButton)
        self.assertTrue(np.array_equal(previous_mask, self.model.mask_model._mask_data))


if __name__ == '__main__':
    unittest.main()
