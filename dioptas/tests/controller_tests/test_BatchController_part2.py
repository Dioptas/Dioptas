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
from mock import MagicMock

from ..utility import click_button

from qtpy import QtWidgets, QtGui

from ...widgets.plot_widgets.ImgWidget import MyRectangle

from .test_BatchController_part1 import *


def test_set_range_img(batch_widget, batch_controller, load_proc_data):
    batch_widget.position_widget.step_series_widget.start_txt.setValue(25)
    batch_widget.position_widget.step_series_widget.stop_txt.setValue(50)

    batch_controller.set_range_img()
    assert batch_widget.position_widget.step_series_widget.slider.value() == 25

    batch_widget.position_widget.step_series_widget.start_txt.setValue(5)
    batch_widget.position_widget.step_series_widget.stop_txt.setValue(20)
    batch_controller.set_range_img()
    assert batch_widget.position_widget.step_series_widget.slider.value() == 20


def test_show_img_mouse_position(batch_widget, batch_controller, load_proc_data):
    batch_widget.activate_stack_plot()
    batch_controller.show_img_mouse_position(10, 15)

    assert batch_widget.position_widget.mouse_pos_widget.cur_pos_widget.x_pos_lbl.text() == 'Img: 15'
    assert batch_widget.position_widget.mouse_pos_widget.cur_pos_widget.y_pos_lbl.text() == '2θ: 9.7'
    assert batch_widget.position_widget.mouse_pos_widget.cur_pos_widget.int_lbl.text() == 'I: 0.1'


def test_load_raw_data(batch_widget, batch_controller, batch_model, load_proc_data):
    files = [os.path.join(unittest_data_path, 'lambda', 'testasapo1_1009_00002_m1_part00000.nxs'),
             os.path.join(unittest_data_path, 'lambda', 'testasapo1_1009_00002_m1_part00001.nxs')]

    QtWidgets.QFileDialog.getOpenFileNames = MagicMock(return_value=files)
    batch_controller.load_data()

    assert batch_model.data is None
    assert batch_model.binning is None
    assert batch_model.raw_available

    start, stop, step = batch_widget.position_widget.step_raw_widget.get_image_range()
    frame = str(batch_widget.position_widget.step_series_widget.pos_label.text())
    assert stop == 19
    assert start == 0
    assert frame == "Frame(None/20):"

    assert batch_widget.file_view_widget.tree_model.columnCount() == 2
    assert (batch_model.files == files).all()


def test_load_proc_data(batch_widget, batch_controller, batch_model, dioptas_model, load_proc_data):
    filename = os.path.join(unittest_data_path, 'lambda', 'testasapo1_1009_00002_proc.nxs')
    QtWidgets.QFileDialog.getOpenFileNames = MagicMock(return_value=[filename])
    dioptas_model.working_directories['image'] = os.path.join(unittest_data_path, 'lambda')
    batch_controller.load_data()

    assert batch_model.data is not None
    # self.assertTrue(self.model.batch_model.raw_available)
    assert batch_model.data.shape[0] == 50
    assert batch_model.data.shape[1] == batch_model.binning.shape[0]
    assert batch_model.data.shape[0] == batch_model.n_img
    start = int(str(batch_widget.position_widget.step_series_widget.start_txt.text()))
    stop = int(str(batch_widget.position_widget.step_series_widget.stop_txt.text()))
    frame = str(batch_widget.position_widget.step_series_widget.pos_label.text())
    assert stop == 49
    assert start == 0
    assert frame == "Frame(50/50):"

    assert batch_widget.position_widget.mouse_pos_widget.clicked_pos_widget.x_pos_lbl.text() == 'Img: 0'
    assert batch_widget.position_widget.step_series_widget.slider.value() == 0

    filename = os.path.join(unittest_data_path, 'lambda', 'testasapo1_1009_00002_m1_part00000.nxs').split(
        '/')[-1].split('\\')[-1]
    assert filename in batch_widget.windowTitle()


def test_plot_batch_2d(batch_widget, batch_controller, batch_model, load_proc_data):
    batch_widget.position_widget.step_series_widget.start_txt.setValue(10)
    batch_widget.position_widget.step_series_widget.stop_txt.setValue(40)
    batch_widget.activate_stack_plot()

    batch_controller.plot_batch()
    assert batch_widget.stack_plot_widget.img_view.img_data.shape == (31, 4038)
    assert batch_widget.stack_plot_widget.img_view._max_range
    assert batch_widget.stack_plot_widget.img_view.horizontal_line.value() == 0
    assert batch_widget.stack_plot_widget.img_view.left_axis_cake.range[0] == pytest.approx(7.28502051, 0.01)
    assert batch_widget.stack_plot_widget.img_view.left_axis_cake.range[1] == pytest.approx(42.7116293, 0.01)


def test_plot_batch_3d(batch_widget, batch_controller, batch_model, load_proc_data):
    batch_widget.activate_surface_view()
    batch_widget.position_widget.step_series_widget.start_txt.blockSignals(True)
    batch_widget.position_widget.step_series_widget.stop_txt.blockSignals(True)
    batch_widget.position_widget.step_series_widget.start_txt.setValue(10)
    batch_widget.position_widget.step_series_widget.stop_txt.setValue(40)
    batch_widget.position_widget.step_series_widget.start_txt.blockSignals(False)
    batch_widget.position_widget.step_series_widget.stop_txt.blockSignals(False)
    batch_controller.plot_batch()

    assert batch_widget.position_widget.step_series_widget.step_txt.value() == 1
    assert batch_widget.surface_widget.surface_view.data.shape == (31, 4038)


def test_img_mouse_click(batch_widget, batch_controller, batch_model, load_proc_data):
    # Test only image loading. Waterfall is already tested
    batch_controller.img_mouse_click(10, 15)

    assert batch_widget.surface_widget.surface_view.g_translate == 0
    assert batch_widget.position_widget.mouse_pos_widget.clicked_pos_widget.x_pos_lbl.text() == 'Img: 15'
    assert batch_widget.position_widget.step_series_widget.slider.value() == 15

    filename = os.path.join(unittest_data_path, 'lambda', 'testasapo1_1009_00002_m1_part00001.nxs')
    assert batch_widget.windowTitle() == f"Batch widget. {filename} - 5"


def test_process_waterfall(batch_controller, load_proc_data):
    batch_controller.process_waterfall(5, 7)
    assert batch_controller.rect.rect().left() == 5
    assert batch_controller.rect.rect().bottom() == 7
    assert batch_controller.clicks == 1

    batch_controller.process_waterfall(10, 17)
    assert batch_controller.clicks == 0


def test_plot_waterfall(batch_controller, dioptas_model, load_proc_data):
    batch_controller.rect = MyRectangle(5, 7, 10, 17, QtGui.QColor(255, 0, 0, 150))

    batch_controller.plot_waterfall()

    assert len(dioptas_model.overlay_model.overlays) == 17
    assert dioptas_model.overlay_model.overlays[0].name == 'testasapo1_1009_00002_m1_part00002.nxs, 4'
    assert dioptas_model.overlay_model.overlays[0]._pattern_x.shape == (10,)


def test_normalize(batch_widget, batch_controller, load_proc_data):
    click_button(batch_widget.control_widget.normalize_btn)
