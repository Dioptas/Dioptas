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

import gc
import os
import unittest

from ..utility import (
    QtTest,
    click_button,
    delete_folder_if_exists,
)

import numpy as np

from qtpy import QtWidgets
from mock import MagicMock
from xypattern import Pattern

from ...model.DioptasModel import DioptasModel
from ...widgets.integration import IntegrationWidget
from ...controller.integration import IntegrationController

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, os.pardir, "data")
jcpds_path = os.path.join(data_path, "jcpds")


class IntegrationFunctionalTest(QtTest):
    def setUp(self):
        self.model = DioptasModel()

        self.integration_widget = IntegrationWidget()
        self.integration_controller = IntegrationController(
            widget=self.integration_widget, dioptas_model=self.model
        )
        self.model.calibration_model.load(
            os.path.join(data_path, "CeO2_Pilatus1M.poni")
        )
        self.model.img_model.load(os.path.join(data_path, "CeO2_Pilatus1M.tif"))

        self.integration_pattern_controller = (
            self.integration_controller.pattern_controller
        )
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
        self.model.calibration_model.load(
            os.path.join(data_path, "CeO2_Pilatus1M_2.poni")
        )
        self.model.img_model.load(os.path.join(data_path, "CeO2_Pilatus1M.tif"))
        self.integration_image_controller.img_mouse_click(0, 500)
        self.model.select_configuration(0)

    def test_configuration_selected_changes_green_line_position_in_cake_mode(self):
        self.integration_image_controller.img_mouse_click(350, 100)
        click_button(self.integration_widget.img_mode_btn)
        self.model.add_configuration()
        self.model.calibration_model.load(
            os.path.join(data_path, "CeO2_Pilatus1M_2.poni")
        )
        click_button(self.integration_widget.img_mode_btn)
        self.model.img_model.load(os.path.join(data_path, "CeO2_Pilatus1M.tif"))
        self.integration_image_controller.img_mouse_click(1840, 500)
        self.model.select_configuration(0)

    def test_azimuthal_plot_shows_same_independent_of_unit(self):
        click_button(self.integration_widget.img_mode_btn)
        self.integration_image_controller.img_mouse_click(600, 150)
        x1, y1 = self.integration_widget.cake_widget.cake_integral_item.getData()
        click_button(self.integration_widget.pattern_q_btn)
        self.integration_image_controller.img_mouse_click(600, 150)
        x2, y2 = self.integration_widget.cake_widget.cake_integral_item.getData()
        self.assertAlmostEqual(np.nansum((x1 - x2) ** 2), 0)
        self.assertAlmostEqual(np.nansum((y1 - y2) ** 2), 0)


class BatchIntegrationFunctionalTest(QtTest):
    def setUp(self):
        self.model = DioptasModel()

        self.integration_widget = IntegrationWidget()
        self.integration_controller = IntegrationController(
            widget=self.integration_widget, dioptas_model=self.model
        )

        pattern = Pattern.from_file(os.path.join(data_path, "CeO2_Pilatus1M.xy"))
        self.model.calibration_model.integrate_1d = MagicMock(
            return_value=(pattern.x, pattern.y)
        )

        self.model.calibration_model.is_calibrated = True

        self.model.calibration_model.load(os.path.join(data_path, "lambda/L2.poni"))

        files = [
            os.path.join(data_path, "lambda/testasapo1_1009_00002_m1_part00000.nxs"),
            os.path.join(data_path, "lambda/testasapo1_1009_00002_m1_part00001.nxs"),
        ]

        QtWidgets.QFileDialog.getOpenFileNames = MagicMock(return_value=files)
        click_button(self.integration_widget.batch_widget.file_control_widget.load_btn)

        self.integration_controller.batch_controller.integrate()

    def tearDown(self):
        del self.integration_widget
        del self.integration_controller
        del self.model
        gc.collect()

        # delete_folder_if_exists(os.path.join(data_path, 'lambda_temp'))

    def test_data_is_ok(self):
        self.assertTrue(self.model.batch_model.data is not None)
        self.assertEqual(self.model.batch_model.data.shape[0], 20)
        self.assertEqual(
            self.model.batch_model.data.shape[1],
            self.model.batch_model.binning.shape[0],
        )
        self.assertEqual(
            self.model.batch_model.data.shape[0], self.model.batch_model.n_img
        )
        start = int(
            str(
                self.integration_widget.batch_widget.position_widget.step_series_widget.start_txt.text()
            )
        )
        stop = int(
            str(
                self.integration_widget.batch_widget.position_widget.step_series_widget.stop_txt.text()
            )
        )
        frame = str(
            self.integration_widget.batch_widget.position_widget.step_series_widget.pos_label.text()
        )
        self.assertEqual(stop, 19)
        self.assertEqual(start, 0)
        self.assertEqual(frame, "Frame(20/20):")

    def save_pattern(self, filename):
        QtWidgets.QFileDialog.getSaveFileName = MagicMock(return_value=filename)
        click_button(self.integration_widget.batch_widget.file_control_widget.save_btn)

    def test_save_data(self):
        for ext in ["nxs", "csv", "png"]:
            self.save_pattern(os.path.join(data_path, f"Test_spec.{ext}"))
            self.assertTrue(os.path.exists(os.path.join(data_path, f"Test_spec.{ext}")))
            self.assertGreater(
                os.stat(os.path.join(data_path, f"Test_spec.{ext}")).st_size, 1
            )
            os.remove(os.path.join(data_path, f"Test_spec.{ext}"))

        self.save_pattern(os.path.join(data_path, "Test_spec.dat"))
        for i in range(20):
            filepath = os.path.join(data_path, f"Test_spec_{i:03d}.dat")
            self.assertTrue(os.path.exists(filepath))
            self.assertGreater(os.stat(filepath).st_size, 1)
            os.remove(filepath)

    def test_save_load_reintegrate(self):
        self.save_pattern(os.path.join(data_path, "Test_spec.nxs"))

        QtWidgets.QFileDialog.getOpenFileNames = MagicMock(
            return_value=[os.path.join(data_path, "Test_spec.nxs")]
        )
        click_button(self.integration_widget.batch_widget.file_control_widget.load_btn)

        self.assertEqual(self.model.batch_model.data.shape[0], 20)
        self.assertEqual(
            self.model.batch_model.data.shape[1],
            self.model.batch_model.binning.shape[0],
        )
        start = int(
            str(
                self.integration_widget.batch_widget.position_widget.step_series_widget.start_txt.text()
            )
        )
        stop = int(
            str(
                self.integration_widget.batch_widget.position_widget.step_series_widget.stop_txt.text()
            )
        )
        frame = str(
            self.integration_widget.batch_widget.position_widget.step_series_widget.pos_label.text()
        )
        self.assertEqual(stop, 19)
        self.assertEqual(start, 0)
        self.assertEqual(frame, "Frame(20/20):")

        self.integration_widget.batch_widget.position_widget.step_series_widget.step_txt.setValue(
            2
        )
        self.integration_controller.batch_controller.integrate()
        self.assertEqual(self.model.batch_model.data.shape[0], 10)
        start = int(
            str(
                self.integration_widget.batch_widget.position_widget.step_series_widget.start_txt.text()
            )
        )
        stop = int(
            str(
                self.integration_widget.batch_widget.position_widget.step_series_widget.stop_txt.text()
            )
        )
        frame = str(
            self.integration_widget.batch_widget.position_widget.step_series_widget.pos_label.text()
        )
        self.assertEqual(stop, 9)
        self.assertEqual(start, 0)
        self.assertEqual(frame, "Frame(10/20):")

    def test_integrate_with_parameters(self):

        self.integration_widget.batch_widget.position_widget.step_series_widget.step_txt.setValue(
            1
        )
        self.integration_widget.batch_widget.position_widget.step_series_widget.start_txt.setValue(
            4
        )
        self.integration_widget.batch_widget.position_widget.step_series_widget.stop_txt.setValue(
            15
        )
        self.integration_controller.batch_controller.integrate()
        start = int(
            str(
                self.integration_widget.batch_widget.position_widget.step_series_widget.start_txt.text()
            )
        )
        stop = int(
            str(
                self.integration_widget.batch_widget.position_widget.step_series_widget.stop_txt.text()
            )
        )
        frame = str(
            self.integration_widget.batch_widget.position_widget.step_series_widget.pos_label.text()
        )
        self.assertEqual(self.model.batch_model.data.shape[0], 12)
        self.assertEqual(stop, 11)
        self.assertEqual(start, 0)
        self.assertEqual(frame, "Frame(12/20):")

        self.integration_widget.batch_widget.position_widget.step_series_widget.step_txt.setValue(
            2
        )
        self.integration_widget.batch_widget.position_widget.step_series_widget.start_txt.setValue(
            0
        )
        self.integration_widget.batch_widget.position_widget.step_series_widget.stop_txt.setValue(
            11
        )
        self.integration_controller.batch_controller.integrate()
        self.assertEqual(self.model.batch_model.data.shape[0], 6)
        start = int(
            str(
                self.integration_widget.batch_widget.position_widget.step_series_widget.start_txt.text()
            )
        )
        stop = int(
            str(
                self.integration_widget.batch_widget.position_widget.step_series_widget.stop_txt.text()
            )
        )
        frame = str(
            self.integration_widget.batch_widget.position_widget.step_series_widget.pos_label.text()
        )
        self.assertEqual(stop, 5)
        self.assertEqual(start, 0)
        self.assertEqual(frame, "Frame(6/20):")

    @unittest.skip("Test is not useful - feature will be disabled in future")
    def test_load_missing_raw(self):
        """
        Load processed data, while raw data not available.

        Fix error by giving correct path to raw data
        """

        # Create tmp raw data
        import shutil

        shutil.copytree(
            os.path.join(data_path, "lambda"), os.path.join(data_path, "lambda_temp")
        )
        # Integrate tmp data. Save proc. Delete tmp data.
        files = [
            os.path.join(
                data_path, "lambda_temp/testasapo1_1009_00002_m1_part00000.nxs"
            ),
            os.path.join(
                data_path, "lambda_temp/testasapo1_1009_00002_m1_part00001.nxs"
            ),
        ]

        # QtWidgets.QFileDialog.getOpenFileNames = MagicMock(return_value=files)
        # click_button(self.integration_widget.batch_widget.file_control_widget.load_btn)

        self.integration_controller.batch_controller.integrate()
        self.save_pattern(os.path.join(data_path, f"Test_missing_raw.nxs"))

        delete_folder_if_exists(os.path.join(data_path, "lambda_temp"))
        # Load proc data with missing raw data
        QtWidgets.QFileDialog.getOpenFileNames = MagicMock(
            return_value=[os.path.join(data_path, "Test_missing_raw.nxs")]
        )
        click_button(self.integration_widget.batch_widget.file_control_widget.load_btn)
        self.assertTrue(self.model.batch_model.raw_available is False)
        start = int(
            str(
                self.integration_widget.batch_widget.position_widget.step_series_widget.start_txt.text()
            )
        )
        stop = int(
            str(
                self.integration_widget.batch_widget.position_widget.step_series_widget.stop_txt.text()
            )
        )
        frame = str(
            self.integration_widget.batch_widget.position_widget.step_series_widget.pos_label.text()
        )
        self.assertEqual(stop, 19)
        self.assertEqual(start, 0)
        self.assertEqual(frame, "Frame(20/20):")

        # Pattern widget is still working
        self.integration_controller.batch_controller.img_mouse_click(5, 15)
        x1, y1 = self.model.pattern.data
        y = self.model.batch_model.data[15]
        x = self.model.batch_model.binning
        self.assertTrue(np.array_equal(y1, y))
        self.assertTrue(np.array_equal(x1, x))

        # Fix raw data path
        self.model.working_directories["image"] = os.path.join(data_path, "lambda")
        QtWidgets.QFileDialog.getOpenFileNames = MagicMock(
            return_value=[os.path.join(data_path, "Test_missing_raw.nxs")]
        )
        click_button(self.integration_widget.batch_widget.load_btn)
        self.assertEqual(self.model.batch_model.n_img_all, 20)
        self.assertTrue(self.model.batch_model.raw_available)
        self.assertEqual(
            os.path.basename(self.model.batch_model.calibration_model.filename),
            "L2.poni",
        )
        start = int(
            str(
                self.integration_widget.batch_widget.position_widget.step_series_widget.start_txt.text()
            )
        )
        stop = int(
            str(
                self.integration_widget.batch_widget.position_widget.step_series_widget.stop_txt.text()
            )
        )
        frame = str(
            self.integration_widget.batch_widget.position_widget.step_series_widget.pos_label.text()
        )
        self.assertEqual(stop, 19)
        self.assertEqual(start, 0)
        self.assertEqual(frame, "Frame(20/20):")

        # Cleanup
        os.remove(os.path.join(data_path, f"Test_missing_raw.nxs"))

    def test_create_waterfall(self):
        click_button(self.integration_widget.batch_widget.mode_widget.view_2d_btn)
        click_button(self.integration_widget.batch_widget.control_widget.waterfall_btn)
        QtWidgets.QApplication.processEvents()

        # Create waterfall
        self.integration_controller.batch_controller.img_mouse_click(5, 5)
        self.integration_controller.batch_controller.rect.set_size(10, 15)
        self.integration_controller.batch_controller.img_mouse_click(10, 15)
        self.assertEqual(len(self.model.overlay_model.overlays), 10)

        # edit waterfall
        self.integration_widget.batch_widget.position_widget.step_series_widget.step_txt.setValue(
            2
        )
        self.integration_controller.batch_controller.process_step()
        self.assertEqual(len(self.model.overlay_model.overlays), 5)

    def test_show_phases(self):
        click_button(self.integration_widget.batch_widget.mode_widget.view_2d_btn)

        self.model.phase_model.add_jcpds(os.path.join(jcpds_path, "FeGeO3_cpx.jcpds"))
        click_button(self.integration_widget.batch_widget.control_widget.phases_btn)

        self.assertEqual(
            len(self.integration_widget.batch_widget.stack_plot_widget.img_view.phases),
            1,
        )
        self.assertEqual(
            len(
                self.integration_widget.batch_widget.stack_plot_widget.img_view.phases[
                    0
                ].line_items
            ),
            27,
        )

        last_line_position = (
            self.integration_widget.batch_widget.stack_plot_widget.img_view.phases[0]
            .line_items[-1]
            .getPos()
        )
        self.assertGreater(last_line_position[0], 900)

    def test_change_view(self):
        self.integration_widget.batch_widget.position_widget.step_series_widget.step_txt.setValue(
            2
        )
        self.integration_widget.batch_widget.position_widget.step_series_widget.start_txt.setValue(
            0
        )
        self.integration_widget.batch_widget.position_widget.step_series_widget.stop_txt.setValue(
            12
        )
        self.integration_controller.batch_controller.integrate()
        start = int(
            str(
                self.integration_widget.batch_widget.position_widget.step_series_widget.start_txt.text()
            )
        )
        stop = int(
            str(
                self.integration_widget.batch_widget.position_widget.step_series_widget.stop_txt.text()
            )
        )
        frame = str(
            self.integration_widget.batch_widget.position_widget.step_series_widget.pos_label.text()
        )
        self.assertEqual(stop, 6)
        self.assertEqual(start, 0)
        self.assertEqual(frame, "Frame(7/20):")

        self.integration_widget.batch_widget.mode_widget.view_f_btn.setChecked(True)
        self.integration_controller.batch_controller.change_view()
        start = int(
            str(
                self.integration_widget.batch_widget.position_widget.step_series_widget.start_txt.text()
            )
        )
        stop = int(
            str(
                self.integration_widget.batch_widget.position_widget.step_series_widget.stop_txt.text()
            )
        )
        frame = str(
            self.integration_widget.batch_widget.position_widget.step_series_widget.pos_label.text()
        )
        self.assertEqual(stop, 6)
        self.assertEqual(start, 0)
        self.assertEqual(frame, "Frame(7/20):")

    def test_change_unit(self):
        self.integration_controller.batch_controller.img_mouse_click(5, 15)
        x1, y1 = self.model.pattern.data
        y = self.model.batch_model.data[15]
        x = self.model.batch_model.binning
        self.assertTrue(np.array_equal(y1, y))
        self.assertTrue(np.array_equal(x1, x))
        self.assertGreater(x1[-1], x1[0])

        click_button(self.integration_widget.batch_widget.options_widget.q_btn)
        self.model.calibration_model.integrate_1d.assert_called_with(
            mask=None, num_points=None, unit="q_A^-1", azi_range=None, trim_zeros=True
        )

        click_button(self.integration_widget.batch_widget.options_widget.d_btn)
        self.model.calibration_model.integrate_1d.assert_called_with(
            mask=None, num_points=None, unit="d_A", azi_range=None, trim_zeros=True
        )

        click_button(self.integration_widget.batch_widget.options_widget.tth_btn)
        self.model.calibration_model.integrate_1d.assert_called_with(
            mask=None, num_points=None, unit="2th_deg", azi_range=None, trim_zeros=True
        )
