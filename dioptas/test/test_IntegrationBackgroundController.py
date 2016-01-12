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

import unittest
import os
import sys

from PyQt4 import QtGui, QtCore
from PyQt4.QtTest import QTest

from widgets.IntegrationWidget import IntegrationWidget
from model import PatternModel
from model import ImgModel
from controller.integration import BackgroundController
from controller.integration import PatternController

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, 'data')


class IntegrationBackgroundControllerTest(unittest.TestCase):
    app = QtGui.QApplication([])

    def setUp(self):
        self.widget = IntegrationWidget()
        self.spectrum_model = PatternModel()
        self.img_model = ImgModel()
        self.spectrum_controller = PatternController({}, self.widget, self.img_model,
                                                     None, None, self.spectrum_model)
        self.background_controller = BackgroundController({}, self.widget, self.img_model, self.spectrum_model)
        self.overlay_tw = self.widget.overlay_tw

    def test_spectrum_bkg_toggle_inspect_button(self):
        self.spectrum_model.load_pattern(os.path.join(data_path, 'spectrum_001.xy'))
        self.widget.bkg_spectrum_gb.setChecked(True)
        self.widget.bkg_spectrum_inspect_btn.toggle()
        x_bkg, y_bkg = self.widget.spectrum_view.bkg_item.getData()
        self.assertGreater(len(x_bkg), 0)

        self.widget.bkg_spectrum_inspect_btn.toggle()
        x_bkg, y_bkg = self.widget.spectrum_view.bkg_item.getData()
        self.assertEqual(len(x_bkg), 0)

    def test_spectrum_bkg_inspect_btn_is_untoggled_when_disabling_spectrum_gb(self):
        self.spectrum_model.load_pattern(os.path.join(data_path, 'spectrum_001.xy'))
        self.widget.bkg_spectrum_gb.setChecked(True)
        self.widget.bkg_spectrum_inspect_btn.toggle()
        self.widget.bkg_spectrum_gb.setChecked(False)
        x_bkg, y_bkg = self.widget.spectrum_view.bkg_item.getData()
        self.assertEqual(len(x_bkg), 0)

    def test_spectrum_bkg_linear_region_changes_txt_fields(self):
        self.spectrum_model.load_pattern(os.path.join(data_path, 'spectrum_001.xy'))
        self.widget.bkg_spectrum_gb.setChecked(True)
        self.widget.bkg_spectrum_inspect_btn.toggle()

        self.widget.spectrum_view.set_linear_region(5, 11)

        x_min = float(str(self.widget.bkg_spectrum_x_min_txt.text()))
        x_max = float(str(self.widget.bkg_spectrum_x_max_txt.text()))

        self.assertEqual(x_min, 5)
        self.assertEqual(x_max, 11)

    def test_spectrum_bkg_txt_fields_change_linear_regions(self):
        self.spectrum_model.load_pattern(os.path.join(data_path, 'spectrum_001.xy'))
        self.widget.bkg_spectrum_gb.setChecked(True)
        self.widget.bkg_spectrum_inspect_btn.toggle()

        self.widget.bkg_spectrum_x_min_txt.setText('5')
        QTest.keyPress(self.widget.bkg_spectrum_x_min_txt, QtCore.Qt.Key_Enter)
        self.widget.bkg_spectrum_x_max_txt.setText('11')
        QTest.keyPress(self.widget.bkg_spectrum_x_max_txt, QtCore.Qt.Key_Enter)

        x_min, x_max = self.widget.spectrum_view.linear_region_item.getRegion()

        self.assertEqual(x_min, 5)
        self.assertEqual(x_max, 11)


if __name__ == '__main__':
    unittest.main()
