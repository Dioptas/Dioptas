# SPDX-License-Identifier: MIT

import os
import numpy as np
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

    assert (
        batch_widget.position_widget.mouse_pos_widget.cur_pos_widget.x_pos_lbl.text()
        == "Img: 15"
    )
    assert (
        batch_widget.position_widget.mouse_pos_widget.cur_pos_widget.y_pos_lbl.text()
        == "2θ: 9.7"
    )
    assert (
        batch_widget.position_widget.mouse_pos_widget.cur_pos_widget.int_lbl.text()
        == "I: 0.1"
    )


def test_load_raw_data(batch_widget, batch_controller, batch_model, load_proc_data):
    files = [
        os.path.join(
            unittest_data_path, "lambda", "testasapo1_1009_00002_m1_part00000.nxs"
        ),
        os.path.join(
            unittest_data_path, "lambda", "testasapo1_1009_00002_m1_part00001.nxs"
        ),
    ]

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


def test_load_proc_data(
    batch_widget, batch_controller, batch_model, dioptas_model, load_proc_data
):
    filename = os.path.join(
        unittest_data_path, "lambda", "testasapo1_1009_00002_proc.nxs"
    )
    QtWidgets.QFileDialog.getOpenFileNames = MagicMock(return_value=[filename])
    dioptas_model.working_directories["image"] = os.path.join(
        unittest_data_path, "lambda"
    )
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

    assert (
        batch_widget.position_widget.mouse_pos_widget.clicked_pos_widget.x_pos_lbl.text()
        == "Img: 0"
    )
    assert batch_widget.position_widget.step_series_widget.slider.value() == 0

    filename = (
        os.path.join(
            unittest_data_path, "lambda", "testasapo1_1009_00002_m1_part00000.nxs"
        )
        .split("/")[-1]
        .split("\\")[-1]
    )
    assert filename in batch_widget.windowTitle()


def test_plot_batch_2d(batch_widget, batch_controller, batch_model, load_proc_data):
    batch_widget.position_widget.step_series_widget.start_txt.setValue(10)
    batch_widget.position_widget.step_series_widget.stop_txt.setValue(40)
    batch_widget.activate_stack_plot()

    batch_controller.plot_batch()
    assert batch_widget.stack_plot_widget.img_view.img_data.shape == (31, 4038)
    assert batch_widget.stack_plot_widget.img_view._max_range
    assert batch_widget.stack_plot_widget.img_view.horizontal_line.value() == 0
    assert batch_widget.stack_plot_widget.img_view.left_axis_cake.range[
        0
    ] == pytest.approx(8.0766, abs=0.1)
    assert batch_widget.stack_plot_widget.img_view.left_axis_cake.range[
        1
    ] == pytest.approx(41.8757, abs=0.1)


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
    assert (
        batch_widget.position_widget.mouse_pos_widget.clicked_pos_widget.x_pos_lbl.text()
        == "Img: 15"
    )
    assert batch_widget.position_widget.step_series_widget.slider.value() == 15

    filename = os.path.join(
        unittest_data_path, "lambda", "testasapo1_1009_00002_m1_part00001.nxs"
    )
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
    assert (
        dioptas_model.overlay_model.overlays[0].name
        == "testasapo1_1009_00002_m1_part00002.nxs, 4"
    )
    assert dioptas_model.overlay_model.overlays[0]._pattern_x.shape == (10,)


def test_normalize(batch_widget, batch_controller, load_proc_data):
    batch_widget.activate_stack_plot()
    batch_controller.plot_batch()
    batch = batch_controller.model.batch_model
    original = batch.data.copy()
    click_button(batch_widget.control_widget.normalize_btn)
    assert batch_widget.control_widget.normalize_btn.isChecked()
    assert batch.normalization_enabled
    np.testing.assert_allclose(batch.data[:, 10:30].mean(axis=1),
                               original[0, 10:30].mean())
    click_button(batch_widget.control_widget.normalize_btn)
    assert not batch_widget.control_widget.normalize_btn.isChecked()
    np.testing.assert_array_equal(batch.data, original)


def test_normalization_popup_applies_while_active(batch_widget, batch_controller, load_proc_data):
    batch_widget.activate_stack_plot()
    batch_controller.plot_batch()
    click_button(batch_widget.control_widget.normalize_btn)
    original = batch_controller.model.batch_model._normalization_source[0].copy()
    click_button(batch_widget.control_widget.normalize_settings_btn)
    popup = batch_widget.control_widget.normalization_popup
    assert popup.isVisible()
    popup.end_bin.setValue(49)
    popup.start_bin.setValue(20)
    popup.reference_frame.setValue(2)
    click_button(popup.apply_btn)
    batch = batch_controller.model.batch_model
    assert batch.normalization_range == (20, 50)
    assert batch.normalization_reference == 2
    assert not popup.isVisible()
    np.testing.assert_allclose(batch.data[:, 20:50].mean(axis=1), original[2, 20:50].mean())
    click_button(batch_widget.control_widget.normalize_btn)
    np.testing.assert_array_equal(batch.data, original)


def test_plotting_does_not_modify_original_intensities(batch_controller, load_proc_data):
    batch = batch_controller.model.batch_model
    batch.data[0, 0] = -1
    original = batch.data.copy()
    batch_controller.plot_batch()
    np.testing.assert_array_equal(batch.data, original)


def test_normalization_controls_follow_batch_view(batch_widget, batch_controller):
    batch_widget.activate_stack_plot()
    assert not batch_widget.control_widget.normalization_widget.isHidden()
    batch_widget.activate_files_view()
    assert batch_widget.control_widget.normalization_widget.isHidden()
    batch_widget.activate_surface_view()
    assert batch_widget.control_widget.normalization_widget.isHidden()


def test_normalization_settings_do_not_enable_normalization(batch_widget, batch_controller, load_proc_data):
    batch = batch_controller.model.batch_model
    original = batch.data.copy()
    batch_controller.apply_normalization_settings(20, 50, 2)
    assert not batch.normalization_enabled
    assert not batch_widget.control_widget.normalize_btn.isChecked()
    np.testing.assert_array_equal(batch.data, original)
