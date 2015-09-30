# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2014  Clemens Prescher (clemens.prescher@gmail.com)
# GSECARS, University of Chicago
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <http://www.gnu.org/licenses/>.
__author__ = 'Clemens Prescher'

import unittest
import os
import sys

import numpy as np
from PyQt4 import QtGui, QtCore
from PyQt4.QtTest import QTest

from widgets.IntegrationWidget import IntegrationWidget
from model import PatternModel
from controller.integration import OverlayController

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, 'data')

class OverlayControllerTest(unittest.TestCase):
    def setUp(self):
        self.app = QtGui.QApplication(sys.argv)
        self.widget = IntegrationWidget()
        self.spectrum_model = PatternModel()
        self.overlay_controller = OverlayController({}, self.widget, self.spectrum_model)
        self.overlay_tw = self.widget.overlay_tw

    def tearDown(self):
        del self.overlay_tw
        del self.overlay_controller
        del self.app

    def test_manual_deleting_overlays(self):
        self.load_overlays()

        self.assertEqual(self.overlay_tw.rowCount(), 6)
        self.assertEqual(len(self.spectrum_model.overlays), 6)
        self.assertEqual(len(self.widget.spectrum_view.overlays), 6)
        self.assertEqual(self.overlay_tw.currentRow(), 5)

        self.overlay_controller.remove_overlay_btn_click_callback()
        self.assertEqual(self.overlay_tw.rowCount(), 5)
        self.assertEqual(len(self.spectrum_model.overlays), 5)
        self.assertEqual(len(self.widget.spectrum_view.overlays), 5)
        self.assertEqual(self.overlay_tw.currentRow(), 4)

        self.widget.select_overlay(1)
        self.overlay_controller.remove_overlay_btn_click_callback()
        self.assertEqual(self.overlay_tw.rowCount(), 4)
        self.assertEqual(len(self.spectrum_model.overlays), 4)
        self.assertEqual(len(self.widget.spectrum_view.overlays), 4)
        self.assertEqual(self.overlay_tw.currentRow(), 1)

        self.widget.select_overlay(0)
        self.overlay_controller.remove_overlay_btn_click_callback()
        self.assertEqual(self.overlay_tw.rowCount(), 3)
        self.assertEqual(len(self.spectrum_model.overlays), 3)
        self.assertEqual(len(self.widget.spectrum_view.overlays), 3)
        self.assertEqual(self.overlay_tw.currentRow(), 0)

        self.overlay_controller.remove_overlay_btn_click_callback()
        self.overlay_controller.remove_overlay_btn_click_callback()
        self.overlay_controller.remove_overlay_btn_click_callback()
        self.assertEqual(self.overlay_tw.rowCount(), 0)
        self.assertEqual(len(self.spectrum_model.overlays), 0)
        self.assertEqual(len(self.widget.spectrum_view.overlays), 0)
        self.assertEqual(self.overlay_tw.currentRow(), -1)

        self.overlay_controller.remove_overlay_btn_click_callback()
        self.assertEqual(self.overlay_tw.rowCount(), 0)
        self.assertEqual(self.overlay_tw.currentRow(), -1)

    def test_automatic_deleting_overlays(self):
        self.load_overlays()
        self.load_overlays()
        self.assertEqual(self.overlay_tw.rowCount(), 12)
        self.assertEqual(len(self.spectrum_model.overlays), 12)
        self.assertEqual(len(self.widget.spectrum_view.overlays), 12)

        self.overlay_controller.clear_overlays_btn_click_callback()
        self.assertEqual(self.overlay_tw.rowCount(), 0)
        self.assertEqual(len(self.spectrum_model.overlays), 0)
        self.assertEqual(len(self.widget.spectrum_view.overlays), 0)
        self.assertEqual(self.overlay_tw.currentRow(), -1)

        multiplier = 1
        for dummy_index in range(multiplier):
            self.load_overlays()

        self.assertEqual(self.overlay_tw.rowCount(), multiplier * 6)
        self.overlay_controller.clear_overlays_btn_click_callback()
        self.assertEqual(self.overlay_tw.rowCount(), 0)
        self.assertEqual(len(self.spectrum_model.overlays), 0)
        self.assertEqual(len(self.widget.spectrum_view.overlays), 0)
        self.assertEqual(self.overlay_tw.currentRow(), -1)

    def test_change_scaling_in_view(self):
        self.load_overlays()
        self.widget.select_overlay(2)

        self.widget.overlay_scale_sb.setValue(2.0)
        self.assertEqual(self.spectrum_model.get_overlay_scaling(2), 2)

        # test if overlay is updated in spectrum
        x, y = self.spectrum_model.overlays[2].data
        x_spec, y_spec = self.widget.spectrum_view.overlays[2].getData()

        self.assertAlmostEqual(np.sum(y-y_spec), 0)

    def test_change_offset_in_view(self):
        self.load_overlays()
        self.widget.select_overlay(3)

        self.widget.overlay_offset_sb.setValue(100)
        self.assertEqual(self.spectrum_model.get_overlay_offset(3), 100)

        x, y = self.spectrum_model.overlays[3].data
        x_spec, y_spec = self.widget.spectrum_view.overlays[3].getData()

        self.assertAlmostEqual(np.sum(y-y_spec), 0)

    def test_setting_overlay_as_bkg(self):
        self.load_overlays()
        self.spectrum_model.load_pattern(os.path.join(data_path, 'spectrum_001.xy'))
        self.widget.select_overlay(0)
        QTest.mouseClick(self.widget.overlay_set_as_bkg_btn, QtCore.Qt.LeftButton)

        self.assertTrue(self.widget.overlay_set_as_bkg_btn.isChecked())

        self.assertEqual(self.spectrum_model.bkg_ind, 0)
        x, y = self.spectrum_model.pattern.data
        self.assertEqual(np.sum(y), 0)

    def test_setting_overlay_as_bkg_and_changing_scale(self):
        self.load_overlays()
        self.spectrum_model.load_pattern(os.path.join(data_path, 'spectrum_001.xy'))
        self.widget.select_overlay(0)
        QTest.mouseClick(self.widget.overlay_set_as_bkg_btn, QtCore.Qt.LeftButton)

        self.widget.overlay_scale_sb.setValue(2)
        _, y = self.spectrum_model.pattern.data
        _, y_original = self.spectrum_model.pattern.data
        self.assertEqual(np.sum(y-y_original), 0)

    def test_setting_overlay_as_bkg_and_changing_offset(self):
        self.load_overlays()
        self.spectrum_model.load_pattern(os.path.join(data_path, 'spectrum_001.xy'))
        self.widget.select_overlay(0)
        QTest.mouseClick(self.widget.overlay_set_as_bkg_btn, QtCore.Qt.LeftButton)

        self.widget.overlay_offset_sb.setValue(100)
        _, y = self.spectrum_model.pattern.data
        self.assertEqual(np.sum(y), -100*y.size)

    def test_setting_overlay_as_bkg_and_then_change_to_new_overlay_as_bkg(self):
        self.load_overlays()
        self.spectrum_model.load_pattern(os.path.join(data_path, 'spectrum_001.xy'))
        self.widget.select_overlay(0)
        QTest.mouseClick(self.widget.overlay_set_as_bkg_btn, QtCore.Qt.LeftButton)


        _, y = self.spectrum_model.pattern.data
        self.assertEqual(np.sum(y), 0)

        self.widget.select_overlay(1)
        self.widget.overlay_scale_sb.setValue(2)
        QTest.mouseClick(self.widget.overlay_set_as_bkg_btn, QtCore.Qt.LeftButton)

        _, y = self.spectrum_model.pattern.data
        self.assertNotEqual(np.sum(y), 0)

    def test_setting_spectrum_as_bkg(self):
        self.spectrum_model.load_pattern(os.path.join(data_path, 'spectrum_001.xy'))
        QTest.mouseClick(self.widget.qa_set_as_background_btn, QtCore.Qt.LeftButton)

        self.assertTrue(self.widget.overlay_set_as_bkg_btn.isChecked())

        _, y = self.spectrum_model.pattern.data
        self.assertEqual(np.sum(y), 0)

    def test_having_overlay_as_bkg_and_deleting_it(self):
        self.spectrum_model.load_pattern(os.path.join(data_path, 'spectrum_001.xy'))
        QTest.mouseClick(self.widget.qa_set_as_background_btn, QtCore.Qt.LeftButton)

        QTest.mouseClick(self.widget.overlay_del_btn, QtCore.Qt.LeftButton)

        self.assertFalse(self.widget.overlay_set_as_bkg_btn.isChecked())
        self.assertEqual(self.widget.overlay_tw.rowCount(), 0)

        _, y = self.spectrum_model.pattern.data
        self.assertNotEqual(np.sum(y), 0)

    def test_overlay_waterfall(self):
        self.load_overlays()
        self.widget.waterfall_separation_txt.setText("10")
        QTest.mouseClick(self.widget.waterfall_btn, QtCore.Qt.LeftButton)

        self.assertEqual(self.spectrum_model.overlays[5].offset, -10)
        self.assertEqual(self.spectrum_model.overlays[4].offset, -20)


        QTest.mouseClick(self.widget.reset_waterfall_btn, QtCore.Qt.LeftButton)

        self.assertEqual(self.spectrum_model.overlays[5].offset, 0)




    def load_overlays(self):
        self.load_overlay('spectrum_001.xy')
        self.load_overlay('spectrum_001.xy')
        self.load_overlay('spectrum_001.xy')
        self.load_overlay('spectrum_001.xy')
        self.load_overlay('spectrum_001.xy')
        self.load_overlay('spectrum_001.xy')

    def load_overlay(self, filename):
        self.overlay_controller.add_overlay_btn_click_callback(os.path.join(data_path, filename))


if __name__ == '__main__':
    unittest.main()