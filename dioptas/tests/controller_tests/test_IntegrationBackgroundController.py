# -*- coding: utf8 -*-

from ..utility import QtTest
import os
import gc
import unittest

from PyQt4 import QtGui, QtCore
from PyQt4.QtTest import QTest
from mock import MagicMock

from ...controller.integration import BackgroundController
from ...controller.integration import PatternController
from ...model.DioptasModel import DioptasModel
from ...widgets.integration import IntegrationWidget

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')

QtGui.QApplication.processEvents = MagicMock()


class IntegrationBackgroundControllerTest(QtTest):

    def setUp(self):
        self.widget = IntegrationWidget()
        self.model = DioptasModel()

        self.pattern_controller = PatternController({}, self.widget, self.model)
        self.background_controller = BackgroundController({}, self.widget, self.model)
        self.overlay_tw = self.widget.overlay_tw

    def tearDown(self):
        del self.pattern_controller
        del self.background_controller
        del self.widget
        del self.model
        gc.collect()

    def test_spectrum_bkg_toggle_inspect_button(self):
        self.model.pattern_model.load_pattern(os.path.join(data_path, 'spectrum_001.xy'))
        self.widget.bkg_spectrum_gb.setChecked(True)
        self.widget.bkg_spectrum_inspect_btn.toggle()
        x_bkg, y_bkg = self.widget.pattern_widget.bkg_item.getData()
        self.assertGreater(len(x_bkg), 0)

        self.widget.bkg_spectrum_inspect_btn.toggle()
        x_bkg, y_bkg = self.widget.pattern_widget.bkg_item.getData()
        self.assertEqual(len(x_bkg), 0)

    def test_spectrum_bkg_inspect_btn_is_untoggled_when_disabling_spectrum_gb(self):
        self.model.pattern_model.load_pattern(os.path.join(data_path, 'spectrum_001.xy'))
        self.widget.bkg_spectrum_gb.setChecked(True)
        self.widget.bkg_spectrum_inspect_btn.toggle()
        self.widget.bkg_spectrum_gb.setChecked(False)
        x_bkg, y_bkg = self.widget.pattern_widget.bkg_item.getData()
        self.assertEqual(len(x_bkg), 0)

    def test_spectrum_bkg_linear_region_changes_txt_fields(self):
        self.model.pattern_model.load_pattern(os.path.join(data_path, 'spectrum_001.xy'))
        self.widget.bkg_spectrum_gb.setChecked(True)
        self.widget.bkg_spectrum_inspect_btn.toggle()

        self.widget.pattern_widget.set_linear_region(5, 11)

        x_min = float(str(self.widget.bkg_spectrum_x_min_txt.text()))
        x_max = float(str(self.widget.bkg_spectrum_x_max_txt.text()))

        self.assertEqual(x_min, 5)
        self.assertEqual(x_max, 11)

    def test_spectrum_bkg_txt_fields_change_linear_regions(self):
        self.model.pattern_model.load_pattern(os.path.join(data_path, 'spectrum_001.xy'))
        self.widget.bkg_spectrum_gb.setChecked(True)
        self.widget.bkg_spectrum_inspect_btn.toggle()

        self.widget.bkg_spectrum_x_min_txt.setText('5')
        QTest.keyPress(self.widget.bkg_spectrum_x_min_txt, QtCore.Qt.Key_Enter)
        self.widget.bkg_spectrum_x_max_txt.setText('11')
        QTest.keyPress(self.widget.bkg_spectrum_x_max_txt, QtCore.Qt.Key_Enter)

        x_min, x_max = self.widget.pattern_widget.linear_region_item.getRegion()

        self.assertEqual(x_min, 5)
        self.assertEqual(x_max, 11)


if __name__ == '__main__':
    unittest.main()
