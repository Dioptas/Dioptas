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
import gc

from PyQt4 import QtGui
import sys


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
        gc.collect()

    def test_manual_deleting_overlays(self):
        self.load_overlays()

        self.assertEqual(self.overlay_tw.rowCount(), 6)
        self.assertEqual(len(self.spectrum_data.overlays), 6)
        self.assertEqual(len(self.view.spectrum_view.overlays), 6)
        self.assertEqual(self.overlay_tw.currentRow(), 5)

        self.controller.del_overlay()
        self.assertEqual(self.overlay_tw.rowCount(), 5)
        self.assertEqual(len(self.spectrum_data.overlays), 5)
        self.assertEqual(len(self.view.spectrum_view.overlays), 5)
        self.assertEqual(self.overlay_tw.currentRow(), 4)

        self.view.select_overlay(1)
        self.controller.del_overlay()
        self.assertEqual(self.overlay_tw.rowCount(), 4)
        self.assertEqual(len(self.spectrum_data.overlays), 4)
        self.assertEqual(len(self.view.spectrum_view.overlays), 4)
        self.assertEqual(self.overlay_tw.currentRow(), 1)

        self.view.select_overlay(0)
        self.controller.del_overlay()
        self.assertEqual(self.overlay_tw.rowCount(), 3)
        self.assertEqual(len(self.spectrum_data.overlays), 3)
        self.assertEqual(len(self.view.spectrum_view.overlays), 3)
        self.assertEqual(self.overlay_tw.currentRow(), 0)

        self.controller.del_overlay()
        self.controller.del_overlay()
        self.controller.del_overlay()
        self.assertEqual(self.overlay_tw.rowCount(), 0)
        self.assertEqual(len(self.spectrum_data.overlays), 0)
        self.assertEqual(len(self.view.spectrum_view.overlays), 0)
        self.assertEqual(self.overlay_tw.currentRow(), -1)

        self.controller.del_overlay()
        self.assertEqual(self.overlay_tw.rowCount(), 0)
        self.assertEqual(self.overlay_tw.currentRow(), -1)

    def test_automatic_deleting_overlays(self):
        self.load_overlays()
        self.load_overlays()
        self.assertEqual(self.overlay_tw.rowCount(), 12)
        self.assertEqual(len(self.spectrum_data.overlays), 12)
        self.assertEqual(len(self.view.spectrum_view.overlays), 12)

        self.controller.clear_overlays()
        self.assertEqual(self.overlay_tw.rowCount(), 0)
        self.assertEqual(len(self.spectrum_data.overlays), 0)
        self.assertEqual(len(self.view.spectrum_view.overlays), 0)
        self.assertEqual(self.overlay_tw.currentRow(), -1)

        multiplier = 1
        for dummy_index in range(multiplier):
            self.load_overlays()

        self.assertEqual(self.overlay_tw.rowCount(), multiplier * 6)
        self.controller.clear_overlays()
        self.assertEqual(self.overlay_tw.rowCount(), 0)
        self.assertEqual(len(self.spectrum_data.overlays), 0)
        self.assertEqual(len(self.view.spectrum_view.overlays), 0)
        self.assertEqual(self.overlay_tw.currentRow(), -1)


    def load_overlays(self):
        self.load_overlay('FoG_D3_001.xy')
        self.load_overlay('FoG_D3_002.xy')
        self.load_overlay('FoG_D3_003.xy')
        self.load_overlay('FoG_D3_004.xy')
        self.load_overlay('FoG_D3_005.xy')
        self.load_overlay('FoG_D3_006.xy')

    def load_overlay(self, filename):
        self.controller.add_overlay('Data/' + filename)


