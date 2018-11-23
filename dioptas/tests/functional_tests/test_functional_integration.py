# -*- coding: utf-8 -*-
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

import gc
import os
import unittest

from ..utility import QtTest, click_button, delete_if_exists

import numpy as np

from qtpy import QtWidgets, QtCore
from qtpy.QtTest import QTest

from mock import MagicMock

from ...model.DioptasModel import DioptasModel
from ...widgets.integration import IntegrationWidget
from ...controller.integration import IntegrationController

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, os.pardir, 'data')


class IntegrationMockFunctionalTest(QtTest):
    def setUp(self):
        self.model = DioptasModel()
        self.model.working_directories['pattern'] = data_path
        self.model.working_directories['image'] = data_path

        self.integration_widget = IntegrationWidget()
        self.integration_controller = IntegrationController(widget=self.integration_widget,
                                                            dioptas_model=self.model)
        self.model.calibration_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.poni'))
        self.model.img_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.tif'))
        self.model.current_configuration.integrate_image_1d()

        self.model.calibration_model.integrate_1d = MagicMock(return_value=(self.model.calibration_model.tth,
                                                                            self.model.calibration_model.int))

        self.integration_pattern_controller = self.integration_controller.pattern_controller
        self.integration_image_controller = self.integration_controller.image_controller

    def tearDown(self):
        del self.integration_pattern_controller
        del self.integration_controller
        self.model.delete_configurations()
        del self.model
        gc.collect()

        delete_if_exists(os.path.join(data_path, 'Test_img.png'))
        delete_if_exists(os.path.join(data_path, 'Test_img.tiff'))

    def enter_value_into_text_field(self, text_field, value):
        text_field.setText('')
        QTest.keyClicks(text_field, str(value))
        QTest.keyPress(text_field, QtCore.Qt.Key_Enter)
        QtWidgets.QApplication.processEvents()

    def test_changing_number_of_integration_bins(self):
        # Edith wants to change the number of integration bins in order to see the effect of binning onto her line
        # shape. She sees that there is an option in the X tab and deselects automatic and sees that the sbinbox
        # becomes editable.
        self.assertFalse(self.integration_widget.bin_count_txt.isEnabled())
        self.integration_widget.automatic_binning_cb.setChecked(False)
        self.assertTrue(self.integration_widget.bin_count_txt.isEnabled())

        # she sees that the current value and wants to double it and notices that the pattern looks a little bit
        # smoother
        previous_number_of_points = len(self.model.pattern.x)
        self.enter_value_into_text_field(self.integration_widget.bin_count_txt, 2 * previous_number_of_points)

        self.model.calibration_model.integrate_1d.assert_called_with(num_points=2 * previous_number_of_points,
                                                                     mask=None, unit='2th_deg')

        # then she decides that having an automatic estimation may probably be better and changes back to automatic.
        # immediately the number is restored and the image looks like when she started
        self.integration_widget.automatic_binning_cb.setChecked(True)
        self.model.calibration_model.integrate_1d.assert_called_with(num_points=None,
                                                                     mask=None, unit='2th_deg')

    def test_changing_supersampling_amount_integrating_to_cake_with_mask(self):
        # Edith opens the program, calibrates everything and looks in to the options menu. She sees that there is a
        # miraculous parameter called supersampling. It is currently set to 1 which seems to be normal
        self.assertEqual(self.integration_widget.supersampling_sb.value(), 1)

        # then she sets it to two and she sees that the number of pattern bin changes and that the pattern looks
        # smoother

        # values before:
        px1 = self.model.calibration_model.pattern_geometry.pixel1
        px2 = self.model.calibration_model.pattern_geometry.pixel2

        img_shape = self.model.img_data.shape

        self.integration_widget.supersampling_sb.setValue(2)
        self.assertEqual(self.model.calibration_model.pattern_geometry.pixel1, 0.5 * px1)
        self.assertEqual(self.model.calibration_model.pattern_geometry.pixel2, 0.5 * px2)
        self.assertEqual(self.model.calibration_model.cake_geometry.pixel1, px1)
        self.assertEqual(self.model.calibration_model.cake_geometry.pixel2, px2)

        # img data has doubled dimensions
        self.assertEqual(self.model.img_data.shape[0], 2 * img_shape[0])
        self.assertEqual(self.model.img_data.shape[1], 2 * img_shape[1])
        # but plot should still be the same:
        self.assertEqual(self.integration_widget.img_widget.img_data.shape[0], img_shape[0])
        self.assertEqual(self.integration_widget.img_widget.img_data.shape[1], img_shape[1])

        self.model.mask_model.mask_below_threshold(self.model.img_model._img_data, 100)
        QTest.mouseClick(self.integration_widget.img_mask_btn, QtCore.Qt.LeftButton)
        QTest.mouseClick(self.integration_widget.img_mode_btn, QtCore.Qt.LeftButton)

    def test_saving_image(self):
        # the widget has to be shown to be able to save the image:
        self.integration_widget.show()
        # Tests if the image save procedures are working for the different possible file endings
        QtWidgets.QFileDialog.getSaveFileName = MagicMock(return_value=os.path.join(data_path, 'Test_img.png'))
        QTest.mouseClick(self.integration_widget.qa_save_img_btn, QtCore.Qt.LeftButton)
        QtWidgets.QFileDialog.getSaveFileName = MagicMock(return_value=os.path.join(data_path, 'Test_img.tiff'))
        QTest.mouseClick(self.integration_widget.qa_save_img_btn, QtCore.Qt.LeftButton)

        self.assertTrue(os.path.exists(os.path.join(data_path, 'Test_img.png')))
        self.assertTrue(os.path.exists(os.path.join(data_path, 'Test_img.tiff')))

    def test_saving_pattern(self):
        # the widget has to be shown to be able to save the image:
        self.integration_widget.show()

        # Tests if the pattern save procedures is are working for all file-endings
        def save_test_for_size_and_delete(self):

            def save_pattern(filename):
                QtWidgets.QFileDialog.getSaveFileName = MagicMock(return_value=filename)
                click_button(self.integration_widget.qa_save_pattern_btn)

            save_pattern(os.path.join(data_path, 'Test_spec.xy'))
            save_pattern(os.path.join(data_path, 'Test_spec.chi'))
            save_pattern(os.path.join(data_path, 'Test_spec.dat'))
            save_pattern(os.path.join(data_path, 'Test_spec.png'))
            save_pattern(os.path.join(data_path, 'Test_spec.svg'))

            self.assertTrue(os.path.exists(os.path.join(data_path, 'Test_spec.xy')))
            self.assertTrue(os.path.exists(os.path.join(data_path, 'Test_spec.chi')))
            self.assertTrue(os.path.exists(os.path.join(data_path, 'Test_spec.dat')))
            self.assertTrue(os.path.exists(os.path.join(data_path, 'Test_spec.png')))
            self.assertTrue(os.path.exists(os.path.join(data_path, 'Test_spec.svg')))

            self.assertGreater(os.stat(os.path.join(data_path, 'Test_spec.xy')).st_size, 1)
            self.assertGreater(os.stat(os.path.join(data_path, 'Test_spec.chi')).st_size, 1)
            self.assertGreater(os.stat(os.path.join(data_path, 'Test_spec.dat')).st_size, 1)
            self.assertGreater(os.stat(os.path.join(data_path, 'Test_spec.png')).st_size, 1)
            self.assertGreater(os.stat(os.path.join(data_path, 'Test_spec.svg')).st_size, 1)

            os.remove(os.path.join(data_path, 'Test_spec.xy'))
            os.remove(os.path.join(data_path, 'Test_spec.chi'))
            os.remove(os.path.join(data_path, 'Test_spec.dat'))
            os.remove(os.path.join(data_path, 'Test_spec.png'))
            os.remove(os.path.join(data_path, 'Test_spec.svg'))

        save_test_for_size_and_delete(self)
        QTest.mouseClick(self.integration_pattern_controller.widget.pattern_q_btn, QtCore.Qt.LeftButton)
        save_test_for_size_and_delete(self)
        QTest.mouseClick(self.integration_pattern_controller.widget.pattern_d_btn, QtCore.Qt.LeftButton)
        save_test_for_size_and_delete(self)

    def test_undocking_and_docking_img_frame(self):
        QTest.mouseClick(self.integration_widget.img_dock_btn, QtCore.Qt.LeftButton)
        QTest.mouseClick(self.integration_widget.img_dock_btn, QtCore.Qt.LeftButton)

    def test_loading_multiple_images_and_batch_integrate_them(self):
        self.integration_widget.pattern_autocreate_cb.setChecked(True)
        self.assertTrue(self.integration_widget.pattern_autocreate_cb.isChecked())

        QtWidgets.QFileDialog.getOpenFileNames = MagicMock(return_value=
                                                           [os.path.join(data_path, 'image_001.tif'),
                                                            os.path.join(data_path, 'image_002.tif')])
        click_button(self.integration_widget.load_img_btn)

        self.assertTrue(os.path.exists(os.path.join(data_path, 'image_001.xy')))
        self.assertTrue(os.path.exists(os.path.join(data_path, 'image_002.xy')))
        os.remove(os.path.join(data_path, 'image_001.xy'))
        os.remove(os.path.join(data_path, 'image_002.xy'))

    def test_loading_multiple_images_and_batch_saving_them(self):
        QtWidgets.QFileDialog.getOpenFileNames = MagicMock(return_value=
                                                           [os.path.join(data_path, 'image_001.tif'),
                                                            os.path.join(data_path, 'image_002.tif')])
        QtWidgets.QFileDialog.getExistingDirectory = MagicMock(return_value=data_path)
        self.integration_widget.img_batch_mode_image_save_rb.setChecked(True)
        click_button(self.integration_widget.load_img_btn)

        self.assertTrue(os.path.exists(os.path.join(data_path, 'batch_image_001.tif')))
        self.assertTrue(os.path.exists(os.path.join(data_path, 'batch_image_002.tif')))
        os.remove(os.path.join(data_path, 'batch_image_001.tif'))
        os.remove(os.path.join(data_path, 'batch_image_002.tif'))


class IntegrationFunctionalTest(QtTest):
    def setUp(self):
        self.model = DioptasModel()

        self.integration_widget = IntegrationWidget()
        self.integration_controller = IntegrationController(widget=self.integration_widget,
                                                            dioptas_model=self.model)
        self.model.calibration_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.poni'))
        self.model.img_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.tif'))

        self.integration_pattern_controller = self.integration_controller.pattern_controller
        self.integration_image_controller = self.integration_controller.image_controller

    def test_activating_mask_mode(self):
        y1 = self.model.pattern.y

        self.model.mask_model.mask_below_threshold(self.model.img_data, 1)
        click_button(self.integration_widget.img_mask_btn)
        y2 = self.model.pattern.y
        self.assertFalse(np.array_equal(y1, y2))

        click_button(self.integration_widget.img_mask_btn)
        y3 = self.model.pattern.y
        self.assertTrue(np.array_equal(y1, y3))

    def test_activating_roi_mode(self):
        y1 = self.model.pattern.y

        click_button(self.integration_widget.img_roi_btn)
        self.assertIsNotNone(self.model.current_configuration.mask_model.roi_mask)

        y2 = self.model.pattern.y
        self.assertFalse(np.array_equal(y1, y2))

        click_button(self.integration_widget.img_roi_btn)
        y3 = self.model.pattern.y
        self.assertTrue(np.array_equal(y1, y3))

    def test_activating_roi_mode_and_mask_mode(self):
        y1 = self.model.pattern.y

        self.model.mask_model.mask_below_threshold(self.model.img_data, 1)
        click_button(self.integration_widget.img_mask_btn)
        y2 = self.model.pattern.y

        click_button(self.integration_widget.img_roi_btn)
        y3 = self.model.pattern.y

        click_button(self.integration_widget.img_roi_btn)
        y4 = self.model.pattern.y

        click_button(self.integration_widget.img_mask_btn)
        y5 = self.model.pattern.y

        self.assertFalse(np.array_equal(y3, y1))
        self.assertFalse(np.array_equal(y3, y2))
        self.assertFalse(np.array_equal(y3, y4))

        self.assertFalse(np.array_equal(y1, y2))
        self.assertFalse(np.array_equal(y1, y4))
        self.assertFalse(np.array_equal(y1, y3))
        self.assertTrue(np.array_equal(y1, y5))

    def test_moving_roi(self):
        click_button(self.integration_widget.img_roi_btn)
        roi_limits1 = self.integration_widget.img_widget.roi.getRoiLimits()
        y1 = self.model.pattern.y
        self.integration_widget.img_widget.roi.setX(30)
        self.integration_widget.img_widget.roi.setPos((31, 31))
        self.integration_widget.img_widget.roi.setSize((100, 100))
        roi_limits2 = self.integration_widget.img_widget.roi.getRoiLimits()
        y2 = self.model.pattern.y

        self.assertNotEqual(roi_limits1, roi_limits2)
        self.assertFalse(np.array_equal(y1, y2))

    def test_changing_integration_unit(self):
        x1, y1 = self.model.pattern.data

        click_button(self.integration_widget.pattern_q_btn)
        x2, y2 = self.model.pattern.data
        self.assertLess(np.max(x2), np.max(x1))

        click_button(self.integration_widget.pattern_d_btn)
        x3, y3 = self.model.pattern.data
        self.assertGreater(np.max(x3), np.max(x2))

        click_button(self.integration_widget.pattern_tth_btn)
        x4, y4 = self.model.pattern.data
        self.assertTrue(np.array_equal(x1, x4))
        self.assertTrue(np.array_equal(y1, y4))

    def test_configuration_selected_changes_img_mode(self):
        click_button(self.integration_widget.img_mode_btn)
        self.assertEqual(self.integration_widget.img_mode, "Cake")
        self.assertTrue(self.model.current_configuration.auto_integrate_cake)

        self.model.add_configuration()
        self.model.select_configuration(0)
        self.assertEqual(self.integration_widget.img_mode, "Cake")
        self.model.select_configuration(1)
        self.assertFalse(self.model.current_configuration.auto_integrate_cake)
        self.assertEqual(self.integration_widget.img_mode, "Image")

    def test_configuration_selected_changes_green_line_position_in_image_mode(self):
        self.integration_image_controller.img_mouse_click(0, 500)
        self.model.add_configuration()
        self.model.calibration_model.load(os.path.join(data_path, "CeO2_Pilatus1M_2.poni"))
        self.model.img_model.load(os.path.join(data_path, "CeO2_Pilatus1M.tif"))
        self.integration_image_controller.img_mouse_click(0, 500)
        self.model.select_configuration(0)

    def test_configuration_selected_changes_green_line_position_in_cake_mode(self):
        self.integration_image_controller.img_mouse_click(0, 500)
        click_button(self.integration_widget.img_mode_btn)
        self.model.add_configuration()
        self.model.calibration_model.load(os.path.join(data_path, "CeO2_Pilatus1M_2.poni"))
        click_button(self.integration_widget.img_mode_btn)
        self.model.img_model.load(os.path.join(data_path, "CeO2_Pilatus1M.tif"))
        self.integration_image_controller.img_mouse_click(1840, 500)
        self.model.select_configuration(0)
