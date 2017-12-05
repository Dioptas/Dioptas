# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2017  Clemens Prescher (clemens.prescher@gmail.com)
# Institute for Geology and Mineralogy, University of Cologne
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from ..utility import QtTest
import os
import gc
import unittest

from qtpy import QtWidgets, QtCore
from qtpy.QtTest import QTest
from mock import MagicMock

from ...controller.integration import BackgroundController
from ...controller.integration import PatternController
from ...model.DioptasModel import DioptasModel
from ...widgets.integration import IntegrationWidget

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')

QtWidgets.QApplication.processEvents = MagicMock()


class IntegrationBackgroundControllerTest(QtTest):

    def setUp(self):
        self.widget = IntegrationWidget()
        self.model = DioptasModel()

        self.pattern_controller = PatternController(self.widget, self.model)
        self.background_controller = BackgroundController(self.widget, self.model)
        self.overlay_tw = self.widget.overlay_tw

    def tearDown(self):
        del self.pattern_controller
        del self.background_controller
        del self.widget
        del self.model
        gc.collect()

    def test_pattern_bkg_toggle_inspect_button(self):
        self.model.pattern_model.load_pattern(os.path.join(data_path, 'pattern_001.xy'))
        self.widget.bkg_pattern_gb.setChecked(True)
        self.widget.bkg_pattern_inspect_btn.toggle()
        x_bkg, y_bkg = self.widget.pattern_widget.bkg_item.getData()
        self.assertGreater(len(x_bkg), 0)

        self.widget.bkg_pattern_inspect_btn.toggle()
        x_bkg, y_bkg = self.widget.pattern_widget.bkg_item.getData()
        self.assertEqual(len(x_bkg), 0)

    def test_pattern_bkg_inspect_btn_is_untoggled_when_disabling_pattern_gb(self):
        self.model.pattern_model.load_pattern(os.path.join(data_path, 'pattern_001.xy'))
        self.widget.bkg_pattern_gb.setChecked(True)
        self.widget.bkg_pattern_inspect_btn.toggle()
        self.widget.bkg_pattern_gb.setChecked(False)
        x_bkg, y_bkg = self.widget.pattern_widget.bkg_item.getData()
        self.assertEqual(len(x_bkg), 0)

    def test_pattern_bkg_linear_region_changes_txt_fields(self):
        self.model.pattern_model.load_pattern(os.path.join(data_path, 'pattern_001.xy'))
        self.widget.bkg_pattern_gb.setChecked(True)
        self.widget.bkg_pattern_inspect_btn.toggle()

        self.widget.pattern_widget.set_linear_region(5, 11)

        x_min = float(str(self.widget.bkg_pattern_x_min_txt.text()))
        x_max = float(str(self.widget.bkg_pattern_x_max_txt.text()))

        self.assertAlmostEqual(x_min, 5,  delta=0.02)
        self.assertAlmostEqual(x_max, 11, delta=0.02)

    def test_pattern_bkg_txt_fields_change_linear_regions(self):
        self.model.pattern_model.load_pattern(os.path.join(data_path, 'pattern_001.xy'))
        self.widget.bkg_pattern_gb.setChecked(True)
        self.widget.bkg_pattern_inspect_btn.toggle()

        self.widget.bkg_pattern_x_min_txt.setText('5')
        QTest.keyPress(self.widget.bkg_pattern_x_min_txt, QtCore.Qt.Key_Enter)
        self.widget.bkg_pattern_x_max_txt.setText('11')
        QTest.keyPress(self.widget.bkg_pattern_x_max_txt, QtCore.Qt.Key_Enter)

        x_min, x_max = self.widget.pattern_widget.linear_region_item.getRegion()

        self.assertAlmostEqual(x_min, 5,  delta=0.02)
        self.assertAlmostEqual(x_max, 11, delta=0.02)

    def test_pattern_bkg_range_remains_when_loading_new_pattern(self):
        self.model.pattern_model.load_pattern(os.path.join(data_path, 'pattern_001.xy'))
        self.widget.bkg_pattern_gb.setChecked(True)
        self.widget.bkg_pattern_inspect_btn.toggle()

        self.widget.bkg_pattern_x_min_txt.setText('5')
        QTest.keyPress(self.widget.bkg_pattern_x_min_txt, QtCore.Qt.Key_Enter)
        self.widget.bkg_pattern_x_max_txt.setText('11')
        QTest.keyPress(self.widget.bkg_pattern_x_max_txt, QtCore.Qt.Key_Enter)

        x_min = self.widget.bkg_pattern_x_min_txt.text()
        x_max = self.widget.bkg_pattern_x_max_txt.text()

        self.model.pattern_model.load_pattern(os.path.join(data_path, 'pattern_001.xy'))
        self.assertEqual(x_min, self.widget.bkg_pattern_x_min_txt.text())
        self.assertEqual(x_max, self.widget.bkg_pattern_x_max_txt.text())


if __name__ == '__main__':
    unittest.main()
