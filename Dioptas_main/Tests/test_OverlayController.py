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
#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <http://www.gnu.org/licenses/>.
__author__ = 'Clemens Prescher'

import unittest

from PyQt4 import QtGui
from Data.ImgData import ImgData
from Controller.MainController import MainController

import sys


class OverlayControllerTest(unittest.TestCase):
    def setUp(self):
        self.app = QtGui.QApplication(sys.argv)
        self.image_data = ImgData()
        self.controller = MainController(use_settings=False)
        self.controller.view.show()

        self.overlay_controller = self.controller.integration_controller.overlay_controller
        self.spectrum_data = self.controller.spectrum_data
        self.spectrum_view = self.controller.view.integration_widget
        self.overlay_tw = self.spectrum_view.overlay_tw

    def tearDown(self):
        del self.controller.calibration_data
        del self.app

    def test_manual_deleting_overlays(self):
        self.load_overlays()

        self.assertEqual(self.overlay_tw.rowCount(), 6)
        self.assertEqual(len(self.spectrum_data.overlays), 6)
        self.assertEqual(len(self.spectrum_view.spectrum_view.overlays), 6)
        self.assertEqual(self.overlay_tw.currentRow(), 5)

        self.overlay_controller.del_overlay()
        self.assertEqual(self.overlay_tw.rowCount(), 5)
        self.assertEqual(len(self.spectrum_data.overlays), 5)
        self.assertEqual(len(self.spectrum_view.spectrum_view.overlays), 5)
        self.assertEqual(self.overlay_tw.currentRow(), 4)

        self.spectrum_view.select_overlay(1)
        self.overlay_controller.del_overlay()
        self.assertEqual(self.overlay_tw.rowCount(), 4)
        self.assertEqual(len(self.spectrum_data.overlays), 4)
        self.assertEqual(len(self.spectrum_view.spectrum_view.overlays), 4)
        self.assertEqual(self.overlay_tw.currentRow(), 1)

        self.spectrum_view.select_overlay(0)
        self.overlay_controller.del_overlay()
        self.assertEqual(self.overlay_tw.rowCount(), 3)
        self.assertEqual(len(self.spectrum_data.overlays), 3)
        self.assertEqual(len(self.spectrum_view.spectrum_view.overlays), 3)
        self.assertEqual(self.overlay_tw.currentRow(), 0)

        self.overlay_controller.del_overlay()
        self.overlay_controller.del_overlay()
        self.overlay_controller.del_overlay()
        self.assertEqual(self.overlay_tw.rowCount(), 0)
        self.assertEqual(len(self.spectrum_data.overlays), 0)
        self.assertEqual(len(self.spectrum_view.spectrum_view.overlays), 0)
        self.assertEqual(self.overlay_tw.currentRow(), -1)

        self.overlay_controller.del_overlay()
        self.assertEqual(self.overlay_tw.rowCount(), 0)
        self.assertEqual(self.overlay_tw.currentRow(), -1)

    def test_automatic_deleting_overlays(self):
        self.load_overlays()
        self.load_overlays()
        self.assertEqual(self.overlay_tw.rowCount(), 12)
        self.assertEqual(len(self.spectrum_data.overlays), 12)
        self.assertEqual(len(self.spectrum_view.spectrum_view.overlays), 12)

        self.overlay_controller.clear_overlays()
        self.assertEqual(self.overlay_tw.rowCount(), 0)
        self.assertEqual(len(self.spectrum_data.overlays), 0)
        self.assertEqual(len(self.spectrum_view.spectrum_view.overlays), 0)
        self.assertEqual(self.overlay_tw.currentRow(), -1)

        multiplier = 1
        for dummy_index in range(multiplier):
            self.load_overlays()

        self.assertEqual(self.overlay_tw.rowCount(), multiplier * 6)
        self.overlay_controller.clear_overlays()
        self.assertEqual(self.overlay_tw.rowCount(), 0)
        self.assertEqual(len(self.spectrum_data.overlays), 0)
        self.assertEqual(len(self.spectrum_view.spectrum_view.overlays), 0)
        self.assertEqual(self.overlay_tw.currentRow(), -1)

    def load_overlays(self):
        self.load_overlay('FoG_D3_001.xy')
        self.load_overlay('FoG_D3_002.xy')
        self.load_overlay('FoG_D3_003.xy')
        self.load_overlay('FoG_D3_004.xy')
        self.load_overlay('FoG_D3_005.xy')
        self.load_overlay('FoG_D3_006.xy')

    def load_overlay(self, filename):
        self.controller.integration_controller.overlay_controller.add_overlay(
            'Data/' + filename)
