# -*- coding: utf-8 -*-

from ..utility import QtTest, click_button
import os
import gc
import numpy as np
from mock import MagicMock

from qtpy import QtWidgets, QtCore, QtGui
from qtpy.QtTest import QTest

from ...model.DioptasModel import DioptasModel
from ...controller.MaskController import MaskController
from ...widgets.MaskWidget import MaskWidget

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')


class MaskControllerTest(QtTest):
    def setUp(self):
        self.working_dir = {'mask': data_path}

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
        QtWidgets.QFileDialog.getOpenFileName = MagicMock(return_value=os.path.join(data_path, 'test.mask'))
        click_button(self.mask_widget.load_mask_btn)
        self.model.mask_model.mask_below_threshold(self.model.img_data, 1)
        filename = os.path.join(data_path, 'dummy.mask')

        QtWidgets.QFileDialog.getSaveFileName = MagicMock(return_value=filename)
        click_button(self.mask_widget.save_mask_btn)
        self.assertTrue(os.path.exists(filename))
        os.remove(filename)

    def test_loading_and_saving_with_super_sampling(self):
        self.model.mask_model.set_supersampling(2)
        QtWidgets.QFileDialog.getOpenFileName = MagicMock(return_value=os.path.join(data_path, 'test.mask'))
        click_button(self.mask_widget.load_mask_btn)

        self.assertEqual(self.model.mask_model.get_mask().shape[0], 4096)
        self.assertEqual(self.model.mask_model.get_mask().shape[1], 4096)

        self.assertEqual(self.model.mask_model.get_img().shape[0], 2048)
        self.assertEqual(self.model.mask_model.get_img().shape[1], 2048)

        self.model.mask_model.mask_below_threshold(self.model.img_data, 1)

        filename = os.path.join(data_path, 'dummy.mask')
        QtWidgets.QFileDialog.getSaveFileName = MagicMock(return_value=filename)
        click_button(self.mask_widget.save_mask_btn)
        self.assertAlmostEqual(self.get_file_size(filename), self.get_file_size(os.path.join(data_path, 'test.mask')),
                               delta=1000)

    def test_grow_and_shrinking(self):
        self.model.mask_model.mask_ellipse(100, 100, 20, 20)
        previous_mask = np.copy(self.model.mask_model._mask_data)

        QTest.mouseClick(self.mask_widget.grow_btn, QtCore.Qt.LeftButton)
        self.assertFalse(np.array_equal(previous_mask, self.model.mask_model._mask_data))

        QTest.mouseClick(self.mask_widget.shrink_btn, QtCore.Qt.LeftButton)
        self.assertTrue(np.array_equal(previous_mask, self.model.mask_model._mask_data))

    def test_mask_and_unmask(self):
        # test that changing mask mode modifies the model and the color in img_widget
        self.mask_widget.mask_rb.click()
        self.assertEqual(self.model.mask_model.mode, True)
        self.assertEqual(self.mask_widget.img_widget.mask_preview_fill_color, QtGui.QColor(255, 0, 0, 150))
        self.mask_widget.unmask_rb.click()
        self.assertEqual(self.model.mask_model.mode, False)
        self.assertEqual(self.mask_widget.img_widget.mask_preview_fill_color, QtGui.QColor(0, 255, 0, 150))

        # test that masking and unmasking the same area results in the same mask
        previous_mask = np.copy(self.model.mask_model._mask_data)
        self.mask_widget.mask_rb.click()
        self.model.mask_model.mask_ellipse(100, 100, 20, 20)
        self.assertFalse(np.array_equal(previous_mask, self.model.mask_model._mask_data))
        self.mask_widget.unmask_rb.click()
        self.model.mask_model.mask_ellipse(100, 100, 20, 20)
        self.assertTrue(np.array_equal(previous_mask, self.model.mask_model._mask_data))

if __name__ == '__main__':
    unittest.main()
