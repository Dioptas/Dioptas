# -*- coding: utf8 -*-

from ..utility import QtTest, click_button
import os
import gc
from mock import MagicMock

import numpy as np
from qtpy import QtWidgets, QtCore
from qtpy.QtTest import QTest

from ...controller.integration import OverlayController
from ...model.DioptasModel import DioptasModel
from ...widgets.integration import IntegrationWidget

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')


class OverlayControllerTest(QtTest):

    def setUp(self):
        self.widget = IntegrationWidget()
        self.model = DioptasModel()
        self.overlay_controller = OverlayController({'overlay': data_path}, self.widget, self.model)
        self.overlay_tw = self.widget.overlay_tw

    def tearDown(self):
        del self.overlay_controller
        del self.overlay_tw
        del self.widget
        del self.model
        gc.collect()

    def test_manual_deleting_overlays(self):
        self.load_overlays()

        self.assertEqual(self.overlay_tw.rowCount(), 6)
        self.assertEqual(len(self.model.overlay_model.overlays), 6)
        self.assertEqual(len(self.widget.pattern_widget.overlays), 6)
        self.assertEqual(self.overlay_tw.currentRow(), 5)

        self.overlay_controller.remove_overlay_btn_click_callback()
        self.assertEqual(self.overlay_tw.rowCount(), 5)
        self.assertEqual(len(self.model.overlay_model.overlays), 5)
        self.assertEqual(len(self.widget.pattern_widget.overlays), 5)
        self.assertEqual(self.overlay_tw.currentRow(), 4)

        self.widget.select_overlay(1)
        self.overlay_controller.remove_overlay_btn_click_callback()
        self.assertEqual(self.overlay_tw.rowCount(), 4)
        self.assertEqual(len(self.model.overlay_model.overlays), 4)
        self.assertEqual(len(self.widget.pattern_widget.overlays), 4)
        self.assertEqual(self.overlay_tw.currentRow(), 1)

        self.widget.select_overlay(0)
        self.overlay_controller.remove_overlay_btn_click_callback()
        self.assertEqual(self.overlay_tw.rowCount(), 3)
        self.assertEqual(len(self.model.overlay_model.overlays), 3)
        self.assertEqual(len(self.widget.pattern_widget.overlays), 3)
        self.assertEqual(self.overlay_tw.currentRow(), 0)

        self.overlay_controller.remove_overlay_btn_click_callback()
        self.overlay_controller.remove_overlay_btn_click_callback()
        self.overlay_controller.remove_overlay_btn_click_callback()
        self.assertEqual(self.overlay_tw.rowCount(), 0)
        self.assertEqual(len(self.model.overlay_model.overlays), 0)
        self.assertEqual(len(self.widget.pattern_widget.overlays), 0)
        self.assertEqual(self.overlay_tw.currentRow(), -1)

        self.overlay_controller.remove_overlay_btn_click_callback()
        self.assertEqual(self.overlay_tw.rowCount(), 0)
        self.assertEqual(self.overlay_tw.currentRow(), -1)

    def test_automatic_deleting_overlays(self):
        self.load_overlays()
        self.load_overlays()
        QtWidgets.QApplication.processEvents()
        QtWidgets.QApplication.processEvents()
        self.assertEqual(self.overlay_tw.rowCount(), 12)
        self.assertEqual(len(self.model.overlay_model.overlays), 12)
        self.assertEqual(len(self.widget.pattern_widget.overlays), 12)

        self.overlay_controller.clear_overlays_btn_click_callback()
        self.assertEqual(self.overlay_tw.rowCount(), 0)
        self.assertEqual(len(self.model.overlay_model.overlays), 0)
        self.assertEqual(len(self.widget.pattern_widget.overlays), 0)
        self.assertEqual(self.overlay_tw.currentRow(), -1)

        multiplier = 1
        for dummy_index in range(multiplier):
            self.load_overlays()

        self.assertEqual(self.overlay_tw.rowCount(), multiplier * 6)
        self.overlay_controller.clear_overlays_btn_click_callback()
        self.assertEqual(self.overlay_tw.rowCount(), 0)
        self.assertEqual(len(self.model.overlay_model.overlays), 0)
        self.assertEqual(len(self.widget.pattern_widget.overlays), 0)
        self.assertEqual(self.overlay_tw.currentRow(), -1)

    def test_change_scaling_in_view(self):
        self.load_overlays()
        self.widget.select_overlay(2)

        self.widget.overlay_scale_sb.setValue(2.0)
        self.app.processEvents()
        self.assertEqual(self.model.overlay_model.get_overlay_scaling(2), 2)

        # tests if overlay is updated in spectrum
        x, y = self.model.overlay_model.overlays[2].data
        x_spec, y_spec = self.widget.pattern_widget.overlays[2].getData()

        self.assertAlmostEqual(np.sum(y - y_spec), 0)

    def test_change_offset_in_view(self):
        self.load_overlays()
        self.widget.select_overlay(3)

        self.widget.overlay_offset_sb.setValue(100)
        self.assertEqual(self.model.overlay_model.get_overlay_offset(3), 100)

        x, y = self.model.overlay_model.overlays[3].data
        x_spec, y_spec = self.widget.pattern_widget.overlays[3].getData()

        self.assertAlmostEqual(np.sum(y - y_spec), 0)

    def test_setting_overlay_as_bkg(self):
        self.load_overlays()
        self.model.pattern_model.load_pattern(os.path.join(data_path, 'spectrum_001.xy'))
        self.widget.select_overlay(0)
        QTest.mouseClick(self.widget.overlay_set_as_bkg_btn, QtCore.Qt.LeftButton)

        self.assertTrue(self.widget.overlay_set_as_bkg_btn.isChecked())

        self.assertEqual(self.model.pattern_model.background_pattern, self.model.overlay_model.overlays[0])
        x, y = self.model.pattern.data
        self.assertEqual(np.sum(y), 0)

    def test_setting_overlay_as_bkg_and_changing_scale(self):
        self.load_overlays()
        self.model.pattern_model.load_pattern(os.path.join(data_path, 'spectrum_001.xy'))
        self.widget.select_overlay(0)
        QTest.mouseClick(self.widget.overlay_set_as_bkg_btn, QtCore.Qt.LeftButton)

        self.widget.overlay_scale_sb.setValue(2)
        _, y = self.model.pattern.data
        _, y_original = self.model.pattern.data
        self.assertEqual(np.sum(y - y_original), 0)

    def test_setting_overlay_as_bkg_and_changing_offset(self):
        self.load_overlays()
        self.model.pattern_model.load_pattern(os.path.join(data_path, 'spectrum_001.xy'))
        self.widget.select_overlay(0)
        QTest.mouseClick(self.widget.overlay_set_as_bkg_btn, QtCore.Qt.LeftButton)

        self.widget.overlay_offset_sb.setValue(100)
        _, y = self.model.pattern.data
        self.assertEqual(np.sum(y), -100 * y.size)

    def test_setting_overlay_as_bkg_and_then_change_to_new_overlay_as_bkg(self):
        self.load_overlays()
        self.model.pattern_model.load_pattern(os.path.join(data_path, 'spectrum_001.xy'))
        self.widget.select_overlay(0)
        QTest.mouseClick(self.widget.overlay_set_as_bkg_btn, QtCore.Qt.LeftButton)

        _, y = self.model.pattern.data
        self.assertEqual(np.sum(y), 0)

        self.widget.select_overlay(1)
        self.widget.overlay_scale_sb.setValue(2)
        QTest.mouseClick(self.widget.overlay_set_as_bkg_btn, QtCore.Qt.LeftButton)

        _, y = self.model.pattern.data
        self.assertNotEqual(np.sum(y), 0)

    def test_setting_spectrum_as_bkg(self):
        self.model.pattern_model.load_pattern(os.path.join(data_path, 'spectrum_001.xy'))
        QTest.mouseClick(self.widget.qa_set_as_background_btn, QtCore.Qt.LeftButton)
        QtWidgets.QApplication.processEvents()

        self.assertTrue(self.widget.overlay_set_as_bkg_btn.isChecked())

        _, y = self.model.pattern.data
        self.assertEqual(np.sum(y), 0)

    def test_having_overlay_as_bkg_and_deleting_it(self):
        self.model.pattern_model.load_pattern(os.path.join(data_path, 'spectrum_001.xy'))
        QTest.mouseClick(self.widget.qa_set_as_background_btn, QtCore.Qt.LeftButton)
        self.assertEqual(len(self.model.overlay_model.overlays), 1)
        self.assertIsNotNone(self.model.pattern_model.background_pattern)

        QTest.mouseClick(self.widget.overlay_del_btn, QtCore.Qt.LeftButton)

        self.assertFalse(self.widget.overlay_set_as_bkg_btn.isChecked())
        self.assertEqual(self.widget.overlay_tw.rowCount(), 0)

        _, y = self.model.pattern.data
        self.assertNotEqual(np.sum(y), 0)

    def test_overlay_waterfall(self):
        self.load_overlays()
        self.widget.waterfall_separation_txt.setText("10")
        QTest.mouseClick(self.widget.waterfall_btn, QtCore.Qt.LeftButton)

        self.assertEqual(self.model.overlay_model.overlays[5].offset, -10)
        self.assertEqual(self.model.overlay_model.overlays[4].offset, -20)

        QTest.mouseClick(self.widget.reset_waterfall_btn, QtCore.Qt.LeftButton)

        self.assertEqual(self.model.overlay_model.overlays[5].offset, 0)
        self.assertEqual(self.model.overlay_model.overlays[5].offset, 0)

    def load_overlays(self):
        self.load_overlay('spectrum_001.xy')
        self.load_overlay('spectrum_001.xy')
        self.load_overlay('spectrum_001.xy')
        self.load_overlay('spectrum_001.xy')
        self.load_overlay('spectrum_001.xy')
        self.load_overlay('spectrum_001.xy')

    def load_overlay(self, filename):
        QtWidgets.QFileDialog.getOpenFileNames = MagicMock(return_value=[os.path.join(data_path, filename)])
        click_button(self.widget.overlay_add_btn)


if __name__ == '__main__':
    unittest.main()
