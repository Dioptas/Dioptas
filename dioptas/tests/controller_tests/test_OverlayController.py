# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
# Principal author: Clemens Prescher (clemens.prescher@gmail.com)
# Copyright (C) 2014-2019 GSECARS, University of Chicago, USA
# Copyright (C) 2015-2018 Institute for Geology and Mineralogy, University of Cologne, Germany
# Copyright (C) 2019-2020 DESY, Hamburg, Germany
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

from ..utility import QtTest, click_button, click_checkbox
import os
import gc
from mock import MagicMock

import numpy as np
from qtpy import QtWidgets, QtCore, QtGui
from qtpy.QtTest import QTest

from ...controller.integration import OverlayController
from ...model.DioptasModel import DioptasModel
from ...widgets.integration import IntegrationWidget

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')


class OverlayControllerTest(QtTest):

    def setUp(self):
        self.integration_widget = IntegrationWidget()
        self.overlay_widget = self.integration_widget.overlay_widget
        self.model = DioptasModel()
        self.model.working_directories['overlay'] = data_path
        self.overlay_controller = OverlayController(self.integration_widget, self.model)
        self.overlay_tw = self.integration_widget.overlay_tw

    def tearDown(self):
        del self.overlay_controller
        del self.overlay_tw
        del self.integration_widget
        del self.model
        gc.collect()

    def test_manual_deleting_overlays(self):
        self.load_overlays()

        self.assertEqual(self.overlay_tw.rowCount(), 6)
        self.assertEqual(len(self.model.overlay_model.overlays), 6)
        self.assertEqual(len(self.integration_widget.pattern_widget.overlays), 6)
        self.assertEqual(self.overlay_tw.currentRow(), 5)

        self.overlay_controller.delete_btn_click_callback()
        self.assertEqual(self.overlay_tw.rowCount(), 5)
        self.assertEqual(len(self.model.overlay_model.overlays), 5)
        self.assertEqual(len(self.integration_widget.pattern_widget.overlays), 5)
        self.assertEqual(self.overlay_tw.currentRow(), 4)

        self.overlay_widget.select_overlay(1)
        self.overlay_controller.delete_btn_click_callback()
        self.assertEqual(self.overlay_tw.rowCount(), 4)
        self.assertEqual(len(self.model.overlay_model.overlays), 4)
        self.assertEqual(len(self.integration_widget.pattern_widget.overlays), 4)
        self.assertEqual(self.overlay_tw.currentRow(), 1)

        self.overlay_widget.select_overlay(0)
        self.overlay_controller.delete_btn_click_callback()
        self.assertEqual(self.overlay_tw.rowCount(), 3)
        self.assertEqual(len(self.model.overlay_model.overlays), 3)
        self.assertEqual(len(self.integration_widget.pattern_widget.overlays), 3)
        self.assertEqual(self.overlay_tw.currentRow(), 0)

        self.overlay_controller.delete_btn_click_callback()
        self.overlay_controller.delete_btn_click_callback()
        self.overlay_controller.delete_btn_click_callback()
        self.assertEqual(self.overlay_tw.rowCount(), 0)
        self.assertEqual(len(self.model.overlay_model.overlays), 0)
        self.assertEqual(len(self.integration_widget.pattern_widget.overlays), 0)
        self.assertEqual(self.overlay_tw.currentRow(), -1)

        self.overlay_controller.delete_btn_click_callback()
        self.assertEqual(self.overlay_tw.rowCount(), 0)
        self.assertEqual(self.overlay_tw.currentRow(), -1)

    def test_automatic_deleting_overlays(self):
        self.load_overlays()
        self.load_overlays()
        QtWidgets.QApplication.processEvents()
        QtWidgets.QApplication.processEvents()
        self.assertEqual(self.overlay_tw.rowCount(), 12)
        self.assertEqual(len(self.model.overlay_model.overlays), 12)
        self.assertEqual(len(self.integration_widget.pattern_widget.overlays), 12)

        self.overlay_controller.clear_overlays_btn_click_callback()
        self.assertEqual(self.overlay_tw.rowCount(), 0)
        self.assertEqual(len(self.model.overlay_model.overlays), 0)
        self.assertEqual(len(self.integration_widget.pattern_widget.overlays), 0)
        self.assertEqual(self.overlay_tw.currentRow(), -1)

        multiplier = 1
        for dummy_index in range(multiplier):
            self.load_overlays()

        self.assertEqual(self.overlay_tw.rowCount(), multiplier * 6)
        self.overlay_controller.clear_overlays_btn_click_callback()
        self.assertEqual(self.overlay_tw.rowCount(), 0)
        self.assertEqual(len(self.model.overlay_model.overlays), 0)
        self.assertEqual(len(self.integration_widget.pattern_widget.overlays), 0)
        self.assertEqual(self.overlay_tw.currentRow(), -1)

    def test_change_scaling_in_view(self):
        self.load_overlays()
        for ind in [0, 3, 4]:
            self.overlay_widget.scale_sbs[ind].setValue(2.0)
            self.assertEqual(self.model.overlay_model.get_overlay_scaling(ind), 2)

            # tests if overlay is updated in pattern
            x, y = self.model.overlay_model.overlays[ind].data
            x_spec, y_spec = self.integration_widget.pattern_widget.overlays[ind].getData()

            self.assertAlmostEqual(np.sum(y - y_spec), 0)

    def test_change_offset_in_view(self):
        self.load_overlays()

        for ind in [0, 3, 4]:
            self.overlay_widget.offset_sbs[ind].setValue(100)
            self.assertEqual(self.model.overlay_model.get_overlay_offset(ind), 100)

            x, y = self.model.overlay_model.overlays[ind].data
            x_spec, y_spec = self.integration_widget.pattern_widget.overlays[ind].getData()

            self.assertAlmostEqual(np.sum(y - y_spec), 0)

    def test_scaling_auto_step_change(self):
        self.load_overlays()
        self.overlay_widget.scale_step_msb.setValue(0.5)
        self.overlay_widget.scale_step_msb.stepUp()

        new_scale_step = self.overlay_widget.scale_step_msb.value()
        self.assertAlmostEqual(new_scale_step, 1.0, places=5)

        self.overlay_widget.scale_step_msb.stepDown()
        self.overlay_widget.scale_step_msb.stepDown()
        new_scale_step = self.overlay_widget.scale_step_msb.value()
        self.assertAlmostEqual(new_scale_step, 0.2, places=5)

    def test_scalestep_spinbox_changes_scale_spinboxes(self):
        self.load_overlays()
        for ind in range(6):
            self.assertEqual(self.overlay_widget.scale_sbs[ind].singleStep(), 0.01)

        new_step = 5
        self.overlay_widget.scale_step_msb.setValue(new_step)
        for ind in range(6):
            self.assertEqual(self.overlay_widget.scale_sbs[ind].singleStep(), new_step)

    def test_offsetstep_spinbox_changes_offset_spinboxes(self):
        self.load_overlays()
        for ind in range(6):
            self.assertEqual(self.overlay_widget.offset_sbs[ind].singleStep(), 100)

        new_step = 5
        self.overlay_widget.offset_step_msb.setValue(new_step)
        for ind in range(6):
            self.assertEqual(self.overlay_widget.offset_sbs[ind].singleStep(), new_step)

    def test_offset_auto_step_change(self):
        self.load_overlays()
        self.overlay_widget.offset_step_msb.setValue(10.0)
        self.overlay_widget.offset_step_msb.stepUp()

        new_offset_step = self.overlay_widget.offset_step_msb.value()
        self.assertAlmostEqual(new_offset_step, 20.0, places=5)

        self.overlay_widget.offset_step_msb.stepDown()
        self.overlay_widget.offset_step_msb.stepDown()
        new_offset_step = self.overlay_widget.offset_step_msb.value()
        self.assertAlmostEqual(new_offset_step, 5.0, places=5)

    def test_setting_overlay_as_bkg(self):
        self.load_overlays()
        self.model.pattern_model.load_pattern(os.path.join(data_path, 'pattern_001.xy'))
        self.overlay_widget.select_overlay(0)
        QTest.mouseClick(self.integration_widget.overlay_set_as_bkg_btn, QtCore.Qt.LeftButton)

        self.assertTrue(self.integration_widget.overlay_set_as_bkg_btn.isChecked())

        self.assertEqual(self.model.pattern_model.background_pattern, self.model.overlay_model.overlays[0])
        x, y = self.model.pattern.data
        self.assertEqual(np.sum(y), 0)

    def test_setting_overlay_as_bkg_and_changing_scale(self):
        self.load_overlays()
        self.model.pattern_model.load_pattern(os.path.join(data_path, 'pattern_001.xy'))

        ind = 2

        self.overlay_widget.select_overlay(ind)
        QTest.mouseClick(self.integration_widget.overlay_set_as_bkg_btn, QtCore.Qt.LeftButton)

        self.overlay_widget.scale_sbs[ind].setValue(2)

        _, y = self.model.pattern.data
        _, y_original = self.model.pattern.data
        self.assertEqual(np.sum(y - y_original), 0)

    def test_setting_overlay_as_bkg_and_changing_offset(self):
        self.load_overlays()
        self.model.pattern_model.load_pattern(os.path.join(data_path, 'pattern_001.xy'))

        ind = 2
        self.overlay_widget.select_overlay(2)
        QTest.mouseClick(self.integration_widget.overlay_set_as_bkg_btn, QtCore.Qt.LeftButton)

        self.overlay_widget.offset_sbs[ind].setValue(100)
        _, y = self.model.pattern.data
        self.assertEqual(np.sum(y), -100 * y.size)

    def test_setting_overlay_as_bkg_and_then_change_to_new_overlay_as_bkg(self):
        self.load_overlays()
        self.model.pattern_model.load_pattern(os.path.join(data_path, 'pattern_001.xy'))

        ind = 2
        self.overlay_widget.select_overlay(ind)
        QTest.mouseClick(self.integration_widget.overlay_set_as_bkg_btn, QtCore.Qt.LeftButton)

        _, y = self.model.pattern.data
        self.assertEqual(np.sum(y), 0)

        new_ind = 1
        self.overlay_widget.select_overlay(new_ind)
        self.overlay_widget.scale_sbs[new_ind].setValue(2)
        QTest.mouseClick(self.integration_widget.overlay_set_as_bkg_btn, QtCore.Qt.LeftButton)

        _, y = self.model.pattern.data
        self.assertNotEqual(np.sum(y), 0)

    def test_setting_pattern_as_bkg(self):
        self.model.pattern_model.load_pattern(os.path.join(data_path, 'pattern_001.xy'))
        QTest.mouseClick(self.integration_widget.qa_set_as_background_btn, QtCore.Qt.LeftButton)
        QtWidgets.QApplication.processEvents()

        self.assertTrue(self.integration_widget.overlay_set_as_bkg_btn.isChecked())

        _, y = self.model.pattern.data
        self.assertEqual(np.sum(y), 0)

    def test_having_overlay_as_bkg_and_deleting_it(self):
        self.model.pattern_model.load_pattern(os.path.join(data_path, 'pattern_001.xy'))
        QTest.mouseClick(self.integration_widget.qa_set_as_background_btn, QtCore.Qt.LeftButton)
        self.assertEqual(len(self.model.overlay_model.overlays), 1)
        self.assertIsNotNone(self.model.pattern_model.background_pattern)

        QTest.mouseClick(self.integration_widget.overlay_del_btn, QtCore.Qt.LeftButton)

        self.assertFalse(self.integration_widget.overlay_set_as_bkg_btn.isChecked())
        self.assertEqual(self.integration_widget.overlay_tw.rowCount(), 0)

        _, y = self.model.pattern.data
        self.assertNotEqual(np.sum(y), 0)

    def test_overlay_waterfall(self):
        self.load_overlays()
        self.overlay_widget.waterfall_separation_msb.setValue(10)
        click_button(self.overlay_widget.waterfall_btn)

        self.assertEqual(self.model.overlay_model.overlays[5].offset, -10)
        self.assertEqual(self.model.overlay_model.overlays[4].offset, -20)

        click_button(self.integration_widget.reset_waterfall_btn)

        self.assertEqual(self.model.overlay_model.overlays[5].offset, 0)
        self.assertEqual(self.model.overlay_model.overlays[5].offset, 0)

    def test_overlay_waterfall_after_deleting_one_overlay(self):
        self.load_overlays()
        self.overlay_widget.select_overlay(4)
        click_button(self.overlay_widget.delete_btn)
        click_button(self.overlay_widget.delete_btn)

        click_button(self.overlay_widget.waterfall_btn)

    def load_overlays(self):
        self.load_overlay('pattern_001.xy')
        self.load_overlay('pattern_001.xy')
        self.load_overlay('pattern_001.xy')
        self.load_overlay('pattern_001.xy')
        self.load_overlay('pattern_001.xy')
        self.load_overlay('pattern_001.xy')

    def load_overlay(self, filename):
        QtWidgets.QFileDialog.getOpenFileNames = MagicMock(return_value=[os.path.join(data_path, filename)])
        click_button(self.integration_widget.overlay_add_btn)

    def test_move_single_overlay_one_step_up(self):
        # setting up the test
        self.load_overlays()
        self.overlay_widget.select_overlay(3)
        new_name = 'special'
        self.assertEqual(self.integration_widget.overlay_tw.item(3, 2).text(), 'pattern_001')
        self.overlay_controller.rename_overlay(3, new_name)
        self.integration_widget.overlay_tw.item(3, 2).setText(new_name)
        self.assertEqual(self.model.overlay_model.overlays[3].name, new_name)
        self.assertEqual(self.integration_widget.overlay_tw.item(3, 2).text(), new_name)
        self.assertEqual(self.model.overlay_model.overlays[2].name, 'pattern_001')

        # moving the overlay
        self.integration_widget.overlay_move_up_btn.click()

        # test for wanted result
        self.assertEqual(self.model.overlay_model.overlays[2].name, new_name)
        self.assertEqual(self.integration_widget.overlay_tw.item(2, 2).text(), new_name)
        self.assertEqual(self.model.overlay_model.overlays[3].name, 'pattern_001')
        self.assertEqual(self.integration_widget.overlay_tw.item(3, 2).text(), 'pattern_001')

    def test_move_single_overlay_one_step_down(self):
        # setting up the test
        self.load_overlays()
        self.overlay_widget.select_overlay(3)
        new_name = 'special'
        self.assertEqual(self.integration_widget.overlay_tw.item(3, 2).text(), 'pattern_001')
        self.overlay_controller.rename_overlay(3, new_name)
        self.integration_widget.overlay_tw.item(3, 2).setText(new_name)
        self.assertEqual(self.model.overlay_model.overlays[3].name, new_name)
        self.assertEqual(self.integration_widget.overlay_tw.item(3, 2).text(), new_name)
        self.assertEqual(self.model.overlay_model.overlays[4].name, 'pattern_001')

        # moving the overlay
        self.integration_widget.overlay_move_down_btn.click()

        # test for wanted result
        self.assertEqual(self.model.overlay_model.overlays[4].name, new_name)
        self.assertEqual(self.integration_widget.overlay_tw.item(4, 2).text(), new_name)
        self.assertEqual(self.model.overlay_model.overlays[3].name, 'pattern_001')
        self.assertEqual(self.integration_widget.overlay_tw.item(3, 2).text(), 'pattern_001')

    def test_bulk_change_visibility_of_overlays(self):
        self.load_overlays()
        for cb in self.overlay_widget.show_cbs:
            self.assertTrue(cb.isChecked())

        self.overlay_controller.overlay_tw_header_section_clicked(0)
        for cb in self.overlay_widget.show_cbs:
            self.assertFalse(cb.isChecked())

        click_checkbox(self.overlay_widget.show_cbs[1])
        self.overlay_controller.overlay_tw_header_section_clicked(0)
        for ind, cb in enumerate(self.overlay_widget.show_cbs):
                self.assertFalse(cb.isChecked())

        self.overlay_controller.overlay_tw_header_section_clicked(0)
        for ind, cb in enumerate(self.overlay_widget.show_cbs):
            self.assertTrue(cb.isChecked())

    def test_change_overlay_color(self):
        """
        We are setting color of overlay 3 to color of overlay 1
        """
        self.load_overlays()
        color1 = self.overlay_widget.color_btns[1].palette().color(QtGui.QPalette.Button)
        QtWidgets.QColorDialog.getColor = MagicMock(return_value=color1)
        click_button(self.overlay_widget.color_btns[3])

        self.assertEqual(self.overlay_widget.color_btns[3].palette().color(QtGui.QPalette.Button), color1)
        overlay_plot_color = self.integration_widget.pattern_widget.overlays[3].opts['pen'].color()

        # legend index needs to be one higher since we also have a legend item for the original pattern:
        legend_color = self.integration_widget.pattern_widget.legend.legendItems[4][1].opts['color']
        self.assertEqual(overlay_plot_color, color1)
        self.assertEqual(legend_color, color1.name())
