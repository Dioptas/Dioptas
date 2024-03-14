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
import pytest
from unittest.mock import MagicMock

import numpy as np

from ..utility import click_button
from ...model.util.HelperModule import get_partial_value
from .test_BatchController_part1 import *

unittest_data_path = os.path.join(os.path.dirname(__file__), "../data")
jcpds_path = os.path.join(unittest_data_path, "jcpds")


def test_set_unit(
    batch_controller, batch_widget, integration_widget, dioptas_model, load_proc_data
):
    batch_widget.activate_stack_plot()
    bottom_axis = batch_widget.stack_plot_widget.img_view.bottom_axis_cake

    class DummyViewRect(object):
        _width = 3500
        _left = 5

        def width(self):
            return self._width

        def left(self):
            return self._left

    batch_widget.stack_plot_widget.img_view.img_view_rect = MagicMock(
        return_value=DummyViewRect()
    )

    batch_controller.set_unit_tth()
    assert dioptas_model.current_configuration.integration_unit == "2th_deg"
    assert bottom_axis._tickLevels is None
    assert bottom_axis.range[0] == pytest.approx(9.7129, 0.001)

    click_button(batch_widget.options_widget.q_btn)
    assert bottom_axis._tickLevels is not None
    assert bottom_axis._tickLevels[0][0][0] == pytest.approx(22.092006, 0.001)

    batch_controller.set_unit_tth()
    assert dioptas_model.current_configuration.integration_unit == "2th_deg"
    assert bottom_axis._tickLevels is None

    batch_controller.set_unit_d()
    assert integration_widget.integration_pattern_widget.d_btn.isChecked()
    assert dioptas_model.current_configuration.integration_unit == "d_A"
    assert bottom_axis._tickLevels[0][0][0] == pytest.approx(10.484, 0.001)


def test_show_phases(
    batch_controller, phase_controller, batch_widget, dioptas_model, load_proc_data
):
    # Load phases
    dioptas_model.phase_model.add_jcpds(os.path.join(jcpds_path, "FeGeO3_cpx.jcpds"))
    assert str(batch_widget.control_widget.phases_btn.text()) == "Show Phases"
    batch_widget.control_widget.phases_btn.setChecked(True)
    batch_controller.toggle_show_phases()
    assert str(batch_widget.control_widget.phases_btn.text()) == "Hide Phases"

    assert len(batch_widget.stack_plot_widget.img_view.phases) == 1
    assert len(batch_widget.stack_plot_widget.img_view.phases[0].line_items) == 27


def test_load_single_image(batch_controller, batch_widget, load_proc_data):
    batch_widget.activate_stack_plot()
    batch_controller.load_single_image(10, 15)

    assert (
        batch_widget.position_widget.mouse_pos_widget.clicked_pos_widget.x_pos_lbl.text()
        == "Img: 15"
    )

    filename = os.path.join(
        unittest_data_path, "lambda", "testasapo1_1009_00002_m1_part00001.nxs"
    )
    assert batch_widget.windowTitle() == f"Batch widget. {filename} - 5"
    assert batch_widget.stack_plot_widget.img_view.horizontal_line.value() == 15


def test_plot_image(batch_controller, batch_widget, dioptas_model, load_proc_data):
    batch_widget.activate_stack_plot()
    batch_controller.plot_image(15)

    filename = os.path.join(
        unittest_data_path, "lambda", "testasapo1_1009_00002_m1_part00001.nxs"
    )
    assert batch_widget.windowTitle() == f"Batch widget. {filename} - 5"
    assert dioptas_model.current_configuration.auto_integrate_pattern
    assert (
        batch_widget.position_widget.mouse_pos_widget.clicked_pos_widget.x_pos_lbl.text()
        == f"Img: 15"
    )


def test_plot_pattern(batch_controller, dioptas_model, load_proc_data):
    batch_controller.plot_pattern(10, 15)

    assert dioptas_model.pattern_model.pattern.data[0][0] == pytest.approx(
        9.6926780, 0.001
    )
    assert dioptas_model.pattern_model.pattern.data[1][0] == np.float32(0.1)


def test_update_y_axis(batch_controller, batch_widget, load_proc_data):
    batch_widget.activate_stack_plot()
    batch_widget.position_widget.step_series_widget.slider.setValue(15)
    batch_widget.position_widget.step_series_widget.start_txt.blockSignals(True)
    batch_widget.position_widget.step_series_widget.stop_txt.blockSignals(True)
    batch_widget.position_widget.step_series_widget.start_txt.setValue(5)
    batch_widget.position_widget.step_series_widget.stop_txt.setValue(28)
    batch_widget.position_widget.step_series_widget.start_txt.blockSignals(False)
    batch_widget.position_widget.step_series_widget.stop_txt.blockSignals(False)
    batch_controller.plot_batch()

    batch_controller.update_y_axis()
    assert batch_widget.stack_plot_widget.img_view.left_axis_cake.range[
        0
    ] == pytest.approx(2.904, 0.01)
    assert batch_widget.stack_plot_widget.img_view.left_axis_cake.range[
        1
    ] == pytest.approx(30.321324, 0.01)


def test_click_in_2d_widget_sends_clicked_change(
    batch_controller, batch_widget, dioptas_model, load_proc_data
):
    dioptas_model.clicked_tth_changed.emit = MagicMock()
    batch_widget.stack_plot_widget.img_view.mouse_left_clicked.emit(20, 10)
    dioptas_model.clicked_tth_changed.emit.assert_called_once_with(
        get_partial_value(dioptas_model.batch_model.binning, 20 - 0.5)
    )


def test_click_in_2d_widget_out_of_range_does_not_send_clicked_change(
    batch_controller, batch_widget, dioptas_model, load_proc_data
):
    dioptas_model.clicked_tth_changed.emit = MagicMock()
    batch_widget.stack_plot_widget.img_view.mouse_left_clicked.emit(-1, 10)
    dioptas_model.clicked_tth_changed.emit.assert_not_called()


def test_clicked_tth_change_signal_changes_line_pos(
    batch_controller, batch_widget, dioptas_model, load_proc_data
):
    batch_controller.plot_batch()

    # in plot range
    dioptas_model.clicked_tth_changed.emit(12)
    new_line_pos = batch_widget.stack_plot_widget.img_view.vertical_line.pos()[0]
    assert get_partial_value(
        dioptas_model.batch_model.binning, new_line_pos
    ) == pytest.approx(12, 0.01)

    #  lower than range
    dioptas_model.clicked_tth_changed.emit(8)
    assert (
        batch_widget.stack_plot_widget.img_view.vertical_line
        not in batch_widget.stack_plot_widget.img_view.img_view_box.addedItems
    )

    # in range again
    dioptas_model.clicked_tth_changed.emit(12)
    assert (
        batch_widget.stack_plot_widget.img_view.vertical_line
        in batch_widget.stack_plot_widget.img_view.img_view_box.addedItems
    )
    new_line_pos = batch_widget.stack_plot_widget.img_view.vertical_line.pos()[0]
    assert get_partial_value(
        dioptas_model.batch_model.binning, new_line_pos
    ) == pytest.approx(12, 0.01)

    # larger than range
    dioptas_model.clicked_tth_changed.emit(35)
    assert (
        batch_widget.stack_plot_widget.img_view.vertical_line
        not in batch_widget.stack_plot_widget.img_view.img_view_box.addedItems
    )


def test_set_navigation_range(batch_controller, batch_widget, load_proc_data):
    batch_controller.set_navigation_range((10, 50))
    assert batch_widget.position_widget.step_series_widget.start_txt.text() == "10"
    assert batch_widget.position_widget.step_series_widget.stop_txt.text() == "50"
    assert batch_widget.position_widget.step_series_widget.slider.value() == 10

    batch_widget.position_widget.step_series_widget.slider.setValue(50)
    batch_controller.set_navigation_range((10, 50))
    assert batch_widget.position_widget.step_series_widget.start_txt.text() == "10"
    assert batch_widget.position_widget.step_series_widget.stop_txt.text() == "50"
    assert batch_widget.position_widget.step_series_widget.slider.value() == 50

    # ToDo Test interaction with other controllers: Integration window vertical line. Patterns


@pytest.mark.skip("needs to be fixed")
def test_integrate(
    batch_controller, batch_widget, integration_widget, dioptas_model, load_proc_data
):
    batch_widget.position_widget.step_series_widget.start_txt.blockSignals(True)
    batch_widget.position_widget.step_series_widget.stop_txt.blockSignals(True)
    batch_widget.position_widget.step_series_widget.start_txt.setValue(5)
    batch_widget.position_widget.step_series_widget.stop_txt.setValue(28)
    batch_widget.position_widget.step_series_widget.step_txt.setValue(3)
    batch_widget.position_widget.step_series_widget.start_txt.blockSignals(False)
    batch_widget.position_widget.step_series_widget.stop_txt.blockSignals(False)

    batch_widget.mode_widget.view_f_btn.setChecked(False)
    integration_widget.automatic_binning_cb.setChecked(False)
    integration_widget.bin_count_txt.setText(str(4000))

    dioptas_model.calibration_model.load(
        os.path.join(unittest_data_path, "lambda", "L2.poni")
    )

    batch_controller.integrate()

    assert dioptas_model.batch_model.data.shape == (8, 3984)
    assert dioptas_model.batch_model.binning.shape == (3984,)
    assert dioptas_model.batch_model.n_img == 8
    assert dioptas_model.batch_model.n_img_all == 50
    assert dioptas_model.batch_model.pos_map.shape == (8, 2)
