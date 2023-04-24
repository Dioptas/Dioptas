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

import os
import gc
import unittest
from unittest.mock import MagicMock

import numpy as np

from ..utility import QtTest, click_button
from ...model.util.HelperModule import get_partial_value

from ...widgets.integration import IntegrationWidget
from ...controller.integration.BatchController import BatchController
from ...controller.integration.PatternController import PatternController
from ...controller.integration.phase.PhaseController import PhaseController
from ...model.DioptasModel import DioptasModel

unittest_data_path = os.path.join(os.path.dirname(__file__), '../data')
jcpds_path = os.path.join(unittest_data_path, 'jcpds')


class BatchControllerTest(QtTest):
    def setUp(self):
        self.working_dir = {'image': ''}

        self.widget = IntegrationWidget()
        self.model = DioptasModel()

        self.controller = BatchController(
            widget=self.widget,
            dioptas_model=self.model)

        self.phase_controller = PhaseController(self.widget, self.model)
        self.pattern_controller = PatternController(self.widget, self.model)

        # Load existing proc+raw data
        filename = os.path.join(unittest_data_path, 'lambda', 'testasapo1_1009_00002_proc.nxs')
        self.model.batch_model.load_proc_data(filename)
        raw_files = self.model.batch_model.files
        raw_files = [os.path.join(os.path.dirname(filename), os.path.basename(f)) for f in raw_files]
        self.model.batch_model.set_image_files(raw_files)
        self.widget.batch_widget.position_widget.step_series_widget.stop_txt.setValue(self.model.batch_model.n_img - 1)

    def tearDown(self):
        del self.phase_controller
        del self.controller
        del self.model
        del self.widget
        gc.collect()

    def test_set_unit(self):
        self.widget.batch_widget.activate_stack_plot()
        bottom_axis = self.widget.batch_widget.stack_plot_widget.img_view.bottom_axis_cake

        class DummyViewRect(object):
            _width = 3500
            _left = 5

            def width(self):
                return self._width

            def left(self):
                return self._left

        self.widget.batch_widget.stack_plot_widget.img_view.img_view_rect = MagicMock(return_value=DummyViewRect())

        self.controller.set_unit_tth()
        self.assertEqual(self.model.current_configuration.integration_unit, '2th_deg')
        self.assertIsNone(bottom_axis._tickLevels)
        self.assertAlmostEqual(bottom_axis.range[0], 9.7129, places=2)

        click_button(self.widget.batch_widget.options_widget.q_btn)
        self.assertIsNotNone(bottom_axis._tickLevels)
        self.assertAlmostEqual(bottom_axis._tickLevels[0][0][0], 22.092006, places=2)

        self.controller.set_unit_tth()
        self.assertEqual(self.model.current_configuration.integration_unit, '2th_deg')
        self.assertIsNone(bottom_axis._tickLevels)

        self.controller.set_unit_d()
        self.assertTrue(self.widget.integration_pattern_widget.d_btn.isChecked())
        self.assertEqual(self.model.current_configuration.integration_unit, 'd_A')
        self.assertAlmostEqual(bottom_axis._tickLevels[0][0][0], 10.484, places=2)

    def test_show_phases(self):
        # Load phases
        self.model.phase_model.add_jcpds(os.path.join(jcpds_path, 'FeGeO3_cpx.jcpds'))

        self.assertEqual(str(self.widget.batch_widget.control_widget.phases_btn.text()), 'Show Phases')
        self.widget.batch_widget.control_widget.phases_btn.setChecked(True)
        self.controller.toggle_show_phases()
        self.assertEqual(str(self.widget.batch_widget.control_widget.phases_btn.text()), 'Hide Phases')

        self.assertEqual(len(self.widget.batch_widget.stack_plot_widget.img_view.phases), 1)
        self.assertEqual(len(self.widget.batch_widget.stack_plot_widget.img_view.phases[0].line_items), 27)

    def test_load_single_image(self):
        self.widget.batch_widget.activate_stack_plot()
        self.controller.load_single_image(10, 15)

        self.assertEqual(self.widget.batch_widget.position_widget.mouse_pos_widget.clicked_pos_widget.x_pos_lbl.text(),
                         'Img: 15')

        filename = os.path.join(unittest_data_path, 'lambda', 'testasapo1_1009_00002_m1_part00001.nxs')
        self.assertEqual(self.widget.batch_widget.windowTitle(), f"Batch widget. {filename} - 5")
        self.assertEqual(self.widget.batch_widget.stack_plot_widget.img_view.horizontal_line.value(), 15)

    def test_plot_pattern(self):
        self.controller.plot_pattern(10, 15)

        self.assertAlmostEqual(self.model.pattern_model.pattern.data[0][0], 9.6926780, places=3)
        self.assertEqual(self.model.pattern_model.pattern.data[1][0], np.float32(0.1))

    def test_plot_image(self):
        self.widget.batch_widget.activate_stack_plot()
        self.controller.plot_image(15)

        filename = os.path.join(unittest_data_path, 'lambda', 'testasapo1_1009_00002_m1_part00001.nxs')
        self.assertEqual(self.widget.batch_widget.windowTitle(), f"Batch widget. {filename} - 5")
        self.assertTrue(self.model.current_configuration.auto_integrate_pattern)
        self.assertEqual(self.widget.batch_widget.position_widget.mouse_pos_widget.clicked_pos_widget.x_pos_lbl.text(),
                         f'Img: 15')

    @unittest.skip('3d Axis has been removed for now. Tick positions need to be reworked.')
    def test_update_3d_axis(self):
        self.controller.update_3d_axis(np.full((10, 1000), 80))

        self.assertEqual(self.widget.batch_widget.surface_widget.surface_view.axis.ticks[0].text, '9.69')
        self.assertEqual(self.widget.batch_widget.surface_widget.surface_view.back_grid.spacing(), [10.0, 1000., 1])

    def test_update_y_axis(self):
        self.widget.batch_widget.activate_stack_plot()
        self.widget.batch_widget.position_widget.step_series_widget.slider.setValue(15)
        self.widget.batch_widget.position_widget.step_series_widget.start_txt.setValue(5)
        self.widget.batch_widget.position_widget.step_series_widget.stop_txt.setValue(28)

        self.controller.update_y_axis()
        self.assertAlmostEqual(self.widget.batch_widget.stack_plot_widget.img_view.left_axis_cake.range[0],
                               2.904, places=2)
        self.assertAlmostEqual(self.widget.batch_widget.stack_plot_widget.img_view.left_axis_cake.range[1],
                               30.3251324, places=2)

    def test_click_in_2d_widget_sends_clicked_change(self):
        self.model.clicked_tth_changed.emit = MagicMock()
        self.widget.batch_widget.stack_plot_widget.img_view.mouse_left_clicked.emit(20, 10)
        self.model.clicked_tth_changed.emit.assert_called_once_with(
            get_partial_value(self.model.batch_model.binning, 20 - 0.5))

    def test_click_in_2d_widget_out_of_range_does_not_send_clicked_change(self):
        self.model.clicked_tth_changed.emit = MagicMock()
        self.widget.batch_widget.stack_plot_widget.img_view.mouse_left_clicked.emit(-1, 10)
        self.model.clicked_tth_changed.emit.assert_not_called()

    def test_clicked_tth_change_signal_changes_line_pos(self):
        self.controller.plot_batch()

        # in plot range
        self.model.clicked_tth_changed.emit(12)
        new_line_pos = self.widget.batch_widget.stack_plot_widget.img_view.vertical_line.pos()[0]
        self.assertAlmostEqual(12, get_partial_value(self.model.batch_model.binning, new_line_pos))

        #  lower than range
        self.model.clicked_tth_changed.emit(8)
        self.assertFalse(self.widget.batch_widget.stack_plot_widget.img_view.vertical_line in
                         self.widget.batch_widget.stack_plot_widget.img_view.img_view_box.addedItems)

        # in range again
        self.model.clicked_tth_changed.emit(12)
        self.assertTrue(self.widget.batch_widget.stack_plot_widget.img_view.vertical_line in
                        self.widget.batch_widget.stack_plot_widget.img_view.img_view_box.addedItems)
        new_line_pos = self.widget.batch_widget.stack_plot_widget.img_view.vertical_line.pos()[0]
        self.assertAlmostEqual(12, get_partial_value(self.model.batch_model.binning, new_line_pos))

        # larger than range
        self.model.clicked_tth_changed.emit(35)
        self.assertFalse(self.widget.batch_widget.stack_plot_widget.img_view.vertical_line in
                         self.widget.batch_widget.stack_plot_widget.img_view.img_view_box.addedItems)

    @unittest.skip("needs to be worked on, why is the number of images different?")
    # TODO: Fix test
    def test_integrate(self):
        self.widget.batch_widget.position_widget.step_series_widget.start_txt.setValue(5)
        self.widget.batch_widget.position_widget.step_series_widget.stop_txt.setValue(28)
        self.widget.batch_widget.position_widget.step_series_widget.step_txt.setValue(3)
        self.widget.batch_widget.mode_widget.view_f_btn.setChecked(False)
        self.widget.automatic_binning_cb.setChecked(False)
        self.widget.bin_count_txt.setText(str(4000))

        self.model.calibration_model.load(os.path.join(unittest_data_path, 'lambda', 'L2.poni'))

        self.controller.integrate()

        self.assertEqual(self.model.batch_model.data.shape, (8, 3984))
        self.assertEqual(self.model.batch_model.binning.shape, (3984,))
        self.assertEqual(self.model.batch_model.n_img, 8)
        self.assertEqual(self.model.batch_model.n_img_all, 50)
        self.assertEqual(self.model.batch_model.pos_map.shape, (8, 2))

    def test_set_navigation_range(self):
        self.controller.set_navigation_range((10, 50))
        self.assertEqual(self.widget.batch_widget.position_widget.step_series_widget.start_txt.text(), '10')
        self.assertEqual(self.widget.batch_widget.position_widget.step_series_widget.stop_txt.text(), '50')
        self.assertEqual(self.widget.batch_widget.position_widget.step_series_widget.slider.value(), 10)

        self.widget.batch_widget.position_widget.step_series_widget.slider.setValue(50)
        self.controller.set_navigation_range((10, 50))
        self.assertEqual(self.widget.batch_widget.position_widget.step_series_widget.start_txt.text(), '10')
        self.assertEqual(self.widget.batch_widget.position_widget.step_series_widget.stop_txt.text(), '50')
        self.assertEqual(self.widget.batch_widget.position_widget.step_series_widget.slider.value(), 50)

        # ToDo Test interaction with other controllers: Integration window vertical line. Patterns

