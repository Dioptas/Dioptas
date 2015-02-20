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

from Views.IntegrationView import IntegrationView
from Data.SpectrumData import SpectrumData
from Controller.IntegrationOverlayController import IntegrationOverlayController


class OverlayControllerTest(unittest.TestCase):
    def setUp(self):
        self.app = QtGui.QApplication(sys.argv)
        self.view = IntegrationView()
        self.spectrum_data = SpectrumData()
        self.controller = IntegrationOverlayController({}, self.view, self.spectrum_data)
        self.overlay_tw = self.view.overlay_tw

    def tearDown(self):
        del self.overlay_tw
        del self.controller
        del self.app

    def test_manual_deleting_overlays(self):
        self.load_overlays()

        self.assertEqual(self.overlay_tw.rowCount(), 6)
        self.assertEqual(len(self.spectrum_data.overlays), 6)
        self.assertEqual(len(self.view.spectrum_view.overlays), 6)
        self.assertEqual(self.overlay_tw.currentRow(), 5)

        self.controller.remove_overlay_btn_click_callback()
        self.assertEqual(self.overlay_tw.rowCount(), 5)
        self.assertEqual(len(self.spectrum_data.overlays), 5)
        self.assertEqual(len(self.view.spectrum_view.overlays), 5)
        self.assertEqual(self.overlay_tw.currentRow(), 4)

        self.view.select_overlay(1)
        self.controller.remove_overlay_btn_click_callback()
        self.assertEqual(self.overlay_tw.rowCount(), 4)
        self.assertEqual(len(self.spectrum_data.overlays), 4)
        self.assertEqual(len(self.view.spectrum_view.overlays), 4)
        self.assertEqual(self.overlay_tw.currentRow(), 1)

        self.view.select_overlay(0)
        self.controller.remove_overlay_btn_click_callback()
        self.assertEqual(self.overlay_tw.rowCount(), 3)
        self.assertEqual(len(self.spectrum_data.overlays), 3)
        self.assertEqual(len(self.view.spectrum_view.overlays), 3)
        self.assertEqual(self.overlay_tw.currentRow(), 0)

        self.controller.remove_overlay_btn_click_callback()
        self.controller.remove_overlay_btn_click_callback()
        self.controller.remove_overlay_btn_click_callback()
        self.assertEqual(self.overlay_tw.rowCount(), 0)
        self.assertEqual(len(self.spectrum_data.overlays), 0)
        self.assertEqual(len(self.view.spectrum_view.overlays), 0)
        self.assertEqual(self.overlay_tw.currentRow(), -1)

        self.controller.remove_overlay_btn_click_callback()
        self.assertEqual(self.overlay_tw.rowCount(), 0)
        self.assertEqual(self.overlay_tw.currentRow(), -1)

    def test_automatic_deleting_overlays(self):
        self.load_overlays()
        self.load_overlays()
        self.assertEqual(self.overlay_tw.rowCount(), 12)
        self.assertEqual(len(self.spectrum_data.overlays), 12)
        self.assertEqual(len(self.view.spectrum_view.overlays), 12)

        self.controller.clear_overlays_btn_click_callback()
        self.assertEqual(self.overlay_tw.rowCount(), 0)
        self.assertEqual(len(self.spectrum_data.overlays), 0)
        self.assertEqual(len(self.view.spectrum_view.overlays), 0)
        self.assertEqual(self.overlay_tw.currentRow(), -1)

        multiplier = 1
        for dummy_index in range(multiplier):
            self.load_overlays()

        self.assertEqual(self.overlay_tw.rowCount(), multiplier * 6)
        self.controller.clear_overlays_btn_click_callback()
        self.assertEqual(self.overlay_tw.rowCount(), 0)
        self.assertEqual(len(self.spectrum_data.overlays), 0)
        self.assertEqual(len(self.view.spectrum_view.overlays), 0)
        self.assertEqual(self.overlay_tw.currentRow(), -1)

    def test_change_scaling_in_view(self):
        self.load_overlays()
        self.view.select_overlay(2)

        self.view.overlay_scale_sb.setValue(2.0)
        self.assertEqual(self.spectrum_data.get_overlay_scaling(2), 2)

    def test_change_offset_in_view(self):
        self.load_overlays()
        self.view.select_overlay(3)
        self.view.overlay_offset_sb.setValue(100)
        self.assertEqual(self.spectrum_data.get_overlay_offset(3), 100)

    def test_setting_overlay_as_bkg(self):
        self.load_overlays()
        self.spectrum_data.load_spectrum(os.path.join('Data', 'FoG_D3_001.xy'))
        self.view.select_overlay(0)
        QTest.mouseClick(self.view.overlay_set_as_bkg_btn, QtCore.Qt.LeftButton)

        self.assertEqual(self.spectrum_data.bkg_ind, 0)
        x, y = self.spectrum_data.spectrum.data
        self.assertEqual(np.sum(y), 0)

    def test_setting_overlay_as_bkg_and_changing_scale(self):
        self.load_overlays()
        self.spectrum_data.load_spectrum(os.path.join('Data', 'FoG_D3_001.xy'))
        self.view.select_overlay(0)
        QTest.mouseClick(self.view.overlay_set_as_bkg_btn, QtCore.Qt.LeftButton)

        self.view.overlay_scale_sb.setValue(2)
        _, y = self.spectrum_data.spectrum.data
        _, y_original = self.spectrum_data.spectrum.data
        self.assertEqual(np.sum(y-y_original), 0)

    def test_setting_overlay_as_bkg_and_changing_offset(self):
        self.load_overlays()
        self.spectrum_data.load_spectrum(os.path.join('Data', 'FoG_D3_001.xy'))
        self.view.select_overlay(0)
        QTest.mouseClick(self.view.overlay_set_as_bkg_btn, QtCore.Qt.LeftButton)

        self.view.overlay_offset_sb.setValue(100)
        _, y = self.spectrum_data.spectrum.data
        self.assertEqual(np.sum(y), -100*y.size)

    def test_setting_overlay_as_bkg_and_then_change_to_new_overlay_as_bkg(self):
        self.load_overlays()
        self.spectrum_data.load_spectrum(os.path.join('Data', 'FoG_D3_001.xy'))
        self.view.select_overlay(0)
        QTest.mouseClick(self.view.overlay_set_as_bkg_btn, QtCore.Qt.LeftButton)


        _, y = self.spectrum_data.spectrum.data
        self.assertEqual(np.sum(y), 0)

        self.view.select_overlay(1)
        QTest.mouseClick(self.view.overlay_set_as_bkg_btn, QtCore.Qt.LeftButton)

        _, y = self.spectrum_data.spectrum.data
        self.assertNotEqual(np.sum(y), 0)




    def load_overlays(self):
        self.load_overlay('FoG_D3_001.xy')
        self.load_overlay('FoG_D3_002.xy')
        self.load_overlay('FoG_D3_003.xy')
        self.load_overlay('FoG_D3_004.xy')
        self.load_overlay('FoG_D3_005.xy')
        self.load_overlay('FoG_D3_006.xy')

    def load_overlay(self, filename):
        self.controller.add_overlay_btn_click_callback('Data/' + filename)


