# SPDX-License-Identifier: MIT

import os
import numpy as np
import pytest

from ..utility import MockMouseEvent

unittest_data_path = os.path.join(os.path.dirname(__file__), "../data")
jcpds_path = os.path.join(unittest_data_path, "jcpds")

__all__ = ["load_proc_data", "jcpds_path", "unittest_data_path"]


@pytest.fixture
def load_proc_data(dioptas_model):
    filename = os.path.join(
        unittest_data_path, "lambda", "testasapo1_1009_00002_proc.nxs"
    )
    dioptas_model.batch_model.load_proc_data(filename)
    raw_files = dioptas_model.batch_model.files
    raw_files = [
        os.path.join(os.path.dirname(filename), os.path.basename(f)) for f in raw_files
    ]
    dioptas_model.batch_model.set_image_files(raw_files)
    return raw_files


def test_initial_state(batch_model, load_proc_data, qtbot):
    assert batch_model.n_img_all == 50
    assert batch_model.n_img == 50
    assert batch_model.binning.shape == (4038,)
    assert batch_model.data.shape == (50, 4038)


def test_is_proc(batch_controller, load_proc_data):
    filename = os.path.join(
        unittest_data_path, "lambda", "testasapo1_1009_00002_m1_part00000.nxs"
    )
    assert not batch_controller.is_proc(filename)

    filename = os.path.join(
        unittest_data_path, "lambda", "testasapo1_1009_00002_proc.nxs"
    )
    assert batch_controller.is_proc(filename)


def test_is_proc_closes_the_file_even_when_reading_raises(
    batch_controller, tmp_path, monkeypatch
):
    """is_proc must close the file on every path.

    On a normal return CPython's refcounting closes it anyway, but when an
    exception propagates the traceback keeps the frame — and with it a bare
    handle — alive, and every later write to that file then fails."""
    from unittest.mock import MagicMock

    handle = MagicMock()
    handle.__enter__.return_value = handle
    handle.__contains__.side_effect = OSError("corrupt file")
    monkeypatch.setattr("h5py.File", MagicMock(return_value=handle))

    with pytest.raises(OSError):
        batch_controller.is_proc(os.path.join(tmp_path, "corrupt.nxs"))

    handle.__exit__.assert_called()


def test_change_3d_view(batch_controller, batch_widget):
    batch_widget.activate_surface_view()

    batch_controller.set_3d_view_f()
    pg_layout = batch_widget.surface_widget.surface_view.pg_layout
    assert pg_layout.opts["azimuth"] == 0
    assert pg_layout.opts["elevation"] == 0

    batch_controller.set_3d_view_t()
    pg_layout = batch_widget.surface_widget.surface_view.pg_layout
    assert pg_layout.opts["azimuth"] == 0
    assert pg_layout.opts["elevation"] == 90

    batch_controller.set_3d_view_s()
    pg_layout = batch_widget.surface_widget.surface_view.pg_layout
    assert pg_layout.opts["azimuth"] == 90
    assert pg_layout.opts["elevation"] == 0

    batch_controller.set_3d_view_i()
    pg_layout = batch_widget.surface_widget.surface_view.pg_layout
    assert pg_layout.opts["azimuth"] == 45
    assert pg_layout.opts["elevation"] == 30


def test_wheel_event_3d(batch_controller, batch_widget, load_proc_data):
    batch_widget.activate_surface_view()
    batch_controller.change_view()

    pg_layout = batch_widget.surface_widget.surface_view.pg_layout
    show_scale = batch_widget.surface_widget.surface_view.show_scale
    show_range = batch_widget.surface_widget.surface_view.show_range
    surf_view = batch_widget.surface_widget.surface_view

    assert pg_layout.opts["distance"] == 3
    assert list(show_scale) == [2, 2, 1]
    assert list(show_range) == [0, 1]
    assert surf_view.g_translate == 0
    assert surf_view.marker == 0

    batch_controller.wheel_event_3d(MockMouseEvent())
    assert pg_layout.opts["distance"] < 10

    batch_controller.key_pressed_3d(MockMouseEvent(key=76))
    batch_controller.wheel_event_3d(MockMouseEvent())
    assert show_range[0] > 0

    batch_controller.key_pressed_3d(MockMouseEvent(key=88))
    batch_controller.wheel_event_3d(MockMouseEvent())
    assert show_scale[0] > 2.0

    batch_controller.key_pressed_3d(MockMouseEvent(key=89))
    batch_controller.wheel_event_3d(MockMouseEvent())
    assert show_scale[1] > 2.0

    batch_controller.key_pressed_3d(MockMouseEvent(key=90))
    batch_controller.wheel_event_3d(MockMouseEvent())
    assert show_scale[2] > 1.0

    batch_controller.key_pressed_3d(MockMouseEvent(key=71))
    batch_controller.wheel_event_3d(MockMouseEvent())
    assert surf_view.g_translate == 2

    batch_controller.key_pressed_3d(MockMouseEvent(key=77))
    batch_controller.wheel_event_3d(MockMouseEvent())
    assert surf_view.marker > 0


def test_pattern_left_click(
    batch_controller, pattern_controller, batch_widget, load_proc_data
):
    batch_widget.activate_stack_plot()
    batch_controller.change_view()
    assert batch_widget.stack_plot_widget.img_view.vertical_line.getXPos() == 0
    pattern_controller.pattern_left_click(15, None)
    first_pos = batch_widget.stack_plot_widget.img_view.vertical_line.getXPos()
    pattern_controller.pattern_left_click(16, None)
    second_pos = batch_widget.stack_plot_widget.img_view.vertical_line.getXPos()
    assert first_pos != second_pos


def test_subtract_background(
    batch_controller, batch_widget, batch_model, load_proc_data
):
    batch_widget.activate_stack_plot()
    batch_model.data = np.ones((100, 1000))
    batch_model.bkg = np.ones((100, 1000))
    batch_widget.options_widget.background_btn.setChecked(True)
    batch_controller.subtract_background()
    assert batch_widget.options_widget.background_btn.isChecked()
    assert np.all(
        batch_widget.stack_plot_widget.img_view.img_data
        == batch_controller.min_val["lin"]
    )


def test_extract_background(batch_controller, batch_model, load_proc_data):
    batch_model.data[...] = 1.0
    assert batch_model.bkg is None
    batch_controller.extract_background()
    assert np.allclose(batch_model.bkg, 1.0)


def test_change_scale(batch_controller, batch_widget, batch_model, load_proc_data):
    batch_widget.activate_stack_plot()
    batch_model.data[:, :] = 100

    batch_controller.change_scale_log(MockMouseEvent())
    assert batch_controller.scale == np.log10
    assert np.allclose(batch_widget.stack_plot_widget.img_view.img_data, 2.0)

    batch_controller.change_scale_sqrt(MockMouseEvent())
    assert batch_controller.scale == np.sqrt
    assert np.allclose(batch_widget.stack_plot_widget.img_view.img_data, 10.0)

    batch_controller.change_scale_lin(MockMouseEvent())
    assert batch_controller.scale == np.array
    assert np.all(batch_widget.stack_plot_widget.img_view.img_data == 100.0)


def test_process_step(batch_controller, batch_widget, batch_model, load_proc_data):
    batch_widget.position_widget.step_series_widget.stop_txt.setValue(
        batch_model.n_img - 1
    )
    # Test here only 3D plot, because waterfall is tested on functional tests
    batch_widget.activate_surface_view()
    batch_controller.plot_batch()

    assert batch_widget.surface_widget.surface_view.data.shape[0] == 50
    batch_widget.position_widget.step_series_widget.step_txt.setValue(2)
    batch_controller.process_step()
    assert batch_widget.surface_widget.surface_view.data.shape[0] == 25


def test_switch_frame(batch_controller, batch_widget, batch_model, load_proc_data):
    batch_widget.position_widget.step_series_widget.stop_txt.setValue(
        batch_model.n_img - 1
    )
    batch_widget.activate_surface_view()
    batch_controller.switch_frame(49)
    assert batch_widget.surface_widget.surface_view.g_translate == 49
    assert (
        batch_widget.position_widget.mouse_pos_widget.clicked_pos_widget.x_pos_lbl.text()
        == "Img: 49"
    )

    filename = os.path.join(
        unittest_data_path, "lambda", "testasapo1_1009_00002_m1_part00004.nxs"
    )
    assert batch_widget.windowTitle() == f"Batch widget. {filename} - 9"
