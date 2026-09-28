# SPDX-License-Identifier: MIT
import numpy as np
import pytest
from xypattern import Pattern


def test_panel_modes_linked_zoom_background_and_configuration(
    pattern_controller, qtbot, tmp_path, monkeypatch
):
    controller = pattern_controller
    model = controller.model
    config = model.current_configuration
    config.auto_integrate_pattern = False
    widget = controller.widget
    display = widget.integration_pattern_widget
    options = widget.integration_control_widget.integration_options_widget
    widget.resize(1000, 700)
    widget.show()
    config.calculate_azimuthal_std = True
    model.pattern_model.set_pattern(
        np.array([1.0, 2.0, 3.0]),
        np.array([10.0, 0.0, 20.0]),
        unit="2th_deg",
        azimuthal_std=np.array([2.0, 1.0, 4.0]),
    )
    qtbot.wait(20)
    assert display._spottiness_visible
    assert widget.integration_control_widget.integration_options_widget.calculate_azimuthal_std_cb.isChecked()
    np.testing.assert_allclose(display.spottiness_curve.yData, [2.0, 1.0, 4.0])
    options.spottiness_relative_cb.setChecked(True)
    assert config.spottiness_relative
    np.testing.assert_allclose(
        display.spottiness_curve.yData, [0.2, np.nan, 0.2], equal_nan=True
    )
    model.pattern_model.background_pattern = Pattern(
        np.array([1.0, 2.0, 3.0]), np.array([9.0, 0.0, 19.0])
    )
    controller.plot_pattern()
    np.testing.assert_allclose(
        display.spottiness_curve.yData, [0.2, np.nan, 0.2], equal_nan=True
    )
    import importlib
    module = importlib.import_module("dioptas.controller.integration.PatternController")
    filename = tmp_path / "spottiness.csv"
    monkeypatch.setattr(module, "save_file_dialog", lambda *args, **kwargs: str(filename))
    options.save_spottiness_btn.click()
    saved = np.loadtxt(filename, delimiter=",")
    np.testing.assert_allclose(saved[:, 2], [2., 1., 4.])
    np.testing.assert_allclose(saved[:, 3], [.2, np.nan, .2], equal_nan=True)

    main = widget.pattern_widget.pattern_plot
    main.setXRange(1.25, 2.5, padding=0)
    qtbot.wait(20)
    np.testing.assert_allclose(
        display.spottiness_plot.viewRange()[0], main.viewRange()[0], atol=0.02
    )
    display.spottiness_plot.setXRange(1.5, 2.25, padding=0)
    qtbot.wait(20)
    np.testing.assert_allclose(
        main.viewRange()[0], display.spottiness_plot.viewRange()[0], atol=0.02
    )
    display.spottiness_plot.setYRange(0, 1, padding=0)
    original_y_range = main.viewRange()[1]
    display.spottiness_plot.setYRange(0, 10, padding=0)
    np.testing.assert_allclose(main.viewRange()[1], original_y_range)
    model.calibration_model.pattern_geometry.wavelength = 1e-10
    config.integration_unit = "d_A"
    assert display.spottiness_plot.getViewBox().state["xInverted"]
    np.testing.assert_allclose(
        display.spottiness_curve.xData, model.pattern.original_data[0]
    )
    assert model.pattern_model.unit == "d_A"
    model.add_configuration()
    assert not display._spottiness_visible
    assert not widget.integration_control_widget.integration_options_widget.calculate_azimuthal_std_cb.isChecked()
    model.select_configuration(0)
    assert display._spottiness_visible
    assert widget.integration_control_widget.integration_options_widget.spottiness_relative_cb.isChecked()
    config.calculate_azimuthal_std = False
    assert not display._spottiness_visible


def test_loading_pattern_clears_spread(pattern_controller, tmp_path):
    controller = pattern_controller
    config = controller.model.current_configuration
    config.calculate_azimuthal_std = True
    model = controller.model.pattern_model
    model.set_pattern(np.arange(3.0), np.ones(3), azimuthal_std=np.ones(3))
    filename = tmp_path / "plain.xy"
    np.savetxt(filename, np.column_stack((np.arange(3.0), np.ones(3))))
    model.load_pattern(str(filename))
    assert model.azimuthal_std is None
    assert (
        not controller.widget.integration_control_widget.integration_options_widget.save_spottiness_btn.isEnabled()
    )
    assert controller.widget.integration_pattern_widget.spottiness_curve.xData is None


def test_image_multifile_export_keeps_spread_and_poisson_separate(
    image_controller, tmp_path, monkeypatch
):
    controller = image_controller
    config = controller.model.current_configuration
    config.auto_integrate_pattern = False
    config.calculate_azimuthal_std = True
    config.calculate_poisson_errors = True
    config.oned_azimuth_range = (-20.0, 40.0)
    config.trim_trailing_zeros = False
    cal = controller.model.calibration_model
    cal.sigma = np.array([0.5, 0.6, 0.7])
    cal.azimuthal_std = np.array([2.0, 3.0, 4.0])
    kwargs_seen = {}

    def integrate(**kwargs):
        kwargs_seen.update(kwargs)
        return np.array([1.0, 2.0, 3.0]), np.array([10.0, 15.0, 20.0])

    monkeypatch.setattr(cal, "integrate_1d", integrate)
    x, y = controller.integrate_pattern()
    assert kwargs_seen["calculate_azimuthal_std"]
    assert kwargs_seen["calculate_errors"]
    assert kwargs_seen["azi_range"] == (-20.0, 40.0)
    assert not kwargs_seen["trim_zeros"]
    controller.widget.pattern_header_xy_cb.setChecked(True)
    controller.widget.pattern_header_xye_cb.setChecked(True)
    controller._save_pattern("frame.tif", str(tmp_path), x, y)
    spread = np.loadtxt(tmp_path / "frame_spottiness.csv", delimiter=",")
    xye = np.loadtxt(tmp_path / "frame.xye")
    np.testing.assert_allclose(spread[:, 2], [2.0, 3.0, 4.0])
    np.testing.assert_allclose(xye[:, 2], [0.5, 0.6, 0.7])

    monkeypatch.setattr(controller, "_get_pattern_file_endings", lambda: [])
    controller._save_pattern("spread_only.tif", str(tmp_path), x, y)
    np.testing.assert_allclose(config.pattern_model.errors, [0.5, 0.6, 0.7])
    config.save_pattern(str(tmp_path / "later.xye"))
    np.testing.assert_allclose(np.loadtxt(tmp_path / "later.xye")[:, 2], [.5, .6, .7])


@pytest.mark.parametrize("batch_unit,display_unit", [
    ("2th_deg", "2th_deg"),
    ("q_A^-1", "q_A^-1"),
    ("d_A", "d_A"),
    ("q_A^-1", "d_A"),
    ("d_A", "q_A^-1"),
])
def test_batch_selection_and_multifile_export_keep_spread(
    batch_controller, tmp_path, monkeypatch, batch_unit, display_unit
):
    import importlib

    controller = batch_controller
    config = controller.model.current_configuration
    config.auto_integrate_pattern = False
    config.calculate_azimuthal_std = True
    config.integration_unit = display_unit
    # These q values are valid for a synchrotron batch, but exceed the
    # inverse-sine domain of the current Cu calibration. q/d conversion
    # and identity conversion must still preserve every coordinate.
    config.calibration_model.pattern_geometry.wavelength = 1.5406e-10
    batch = controller.model.batch_model
    batch.data = np.array([[10.0, 20.0, 30.0], [12.0, 24.0, 36.0]])
    q = np.array([2.0, 10.0, 15.0])
    batch.binning = 2 * np.pi / q if batch_unit == "d_A" else q
    batch.integration_unit = batch_unit
    expected_x = (batch.binning if batch_unit == display_unit
                  else 2 * np.pi / batch.binning)
    batch.azimuthal_std = np.array([[2.0, 3.0, 4.0], [3.0, 4.0, 5.0]])
    controller.plot_pattern(1, 1)
    np.testing.assert_allclose(controller.model.pattern.original_data[0], expected_x)
    label = controller._UNIT_DISPLAY[display_unit][0]
    positions = controller.widget.batch_widget.position_widget.mouse_pos_widget
    assert positions.clicked_pos_widget.y_pos_lbl.text() == f"{label}: {expected_x[1]:.1f}"
    controller.show_img_mouse_position(1.2, 0)
    assert positions.cur_pos_widget.y_pos_lbl.text() == f"{label}: {expected_x[1]:.1f}"
    np.testing.assert_allclose(
        controller.model.pattern_model.azimuthal_std, [3.0, 4.0, 5.0]
    )
    module = importlib.import_module("dioptas.controller.integration.BatchController")
    monkeypatch.setattr(
        module, "save_file_dialog", lambda *args, **kwargs: str(tmp_path / "batch.xy")
    )
    controller.save_data()
    for i in range(2):
        table = np.loadtxt(tmp_path / f"batch_{i:03d}_spottiness.csv", delimiter=",")
        pattern = np.loadtxt(tmp_path / f"batch_{i:03d}.xy")
        np.testing.assert_allclose(pattern[:, 0], expected_x, rtol=1e-6)
        np.testing.assert_allclose(table[:, 0], expected_x)
        np.testing.assert_allclose(table[:, 1], batch.data[i])
        np.testing.assert_allclose(table[:, 2], batch.azimuthal_std[i])


def test_spottiness_click_cursor_and_right_click_zoom(pattern_controller, qtbot):
    from qtpy import QtCore

    controller = pattern_controller
    widget = controller.widget
    config = controller.model.current_configuration
    config.auto_integrate_pattern = False
    widget.resize(1100, 850)
    widget.show()
    options = widget.integration_control_widget.integration_options_widget
    options.calculate_azimuthal_std_cb.setChecked(True)
    assert config.calculate_azimuthal_std
    assert options.calculate_azimuthal_std_cb.parent() is options.spottiness_gb
    x = np.linspace(1, 20, 200)
    controller.model.pattern_model.set_pattern(
        x, 100 + x**2, unit="2th_deg", azimuthal_std=2 + np.sin(x)
    )
    display = widget.integration_pattern_widget
    main = display.pattern_view
    spread = display.spottiness_view
    graph = display.pattern_pg_layout
    qtbot.wait(30)

    def at(x, y):
        return graph.mapFromScene(spread.view_box.mapViewToScene(QtCore.QPointF(x, y)))

    qtbot.mouseClick(graph.viewport(), QtCore.Qt.LeftButton, pos=at(8, 2))
    qtbot.wait(20)
    assert abs(main.get_pos_line() - 8) < 0.15
    assert spread.get_pos_line() == main.get_pos_line()
    # Cursor updates from other views also reach this panel.
    controller.model.clicked_tth_changed.emit(11.0)
    assert spread.get_pos_line() == 11.0

    main.auto_range = False
    spread.view_box.setRange(xRange=(7, 9), yRange=(1.5, 2.5), padding=0)
    qtbot.wait(20)
    main_y = main.view_box.viewRange()[1]
    qtbot.mouseClick(graph.viewport(), QtCore.Qt.RightButton, pos=at(8, 2))
    qtbot.wait(20)
    bounds = spread.view_box.viewRange()
    assert abs(np.diff(bounds[0])[0] - 4.0) < 0.05
    assert abs(np.diff(bounds[1])[0] - 2.0) < 0.05
    np.testing.assert_allclose(main.view_box.viewRange()[1], main_y)
    assert not main.auto_range

    qtbot.mouseDClick(graph.viewport(), QtCore.Qt.RightButton, pos=at(8, 2))
    qtbot.wait(30)
    assert main.auto_range
    bounds = spread.view_box.viewRange()
    assert bounds[0][0] <= 1 and bounds[0][1] >= 20
    assert bounds[1][0] <= 1.01 and bounds[1][1] >= 2.99
    np.testing.assert_allclose(bounds[0], main.view_box.viewRange()[0], atol=0.03)


def test_spottiness_phase_lines_follow_positions_color_and_visibility(
    pattern_controller,
):
    import pyqtgraph as pg

    controller = pattern_controller
    controller.model.current_configuration.calculate_azimuthal_std = True
    display = controller.widget.integration_pattern_widget
    main, spread = display.pattern_view, display.spottiness_view
    main.add_phase("phase", [2.0, 4.0], [100.0, 300.0], 0, (200, 40, 30))
    lines = spread.phase_lines[0]
    assert all(isinstance(line, pg.InfiniteLine) for line in lines)
    assert [line.value() for line in lines] == [2.0, 4.0]
    assert lines[0].pen.color().getRgb()[:3] == (200, 40, 30)
    main.set_phase_color(0, (20, 80, 220))
    assert lines[0].pen.color().getRgb()[:3] == (20, 80, 220)
    main.update_phase_intensities(0, [3.0, 5.0, 7.0], [50.0, 30.0, 10.0], 2.0)
    assert [line.value() for line in spread.phase_lines[0]] == [3.0, 5.0, 7.0]
    main.hide_phase(0)
    assert all(not line.isVisible() for line in spread.phase_lines[0])
    main.show_phase(0)
    assert all(line.isVisible() for line in spread.phase_lines[0])
    main.del_phase(0)
    assert spread.phase_lines == []


def test_options_reflow_without_horizontal_clipping(qtbot):
    from dioptas.widgets.integration.control.OptionsWidget import OptionsWidget

    widget = OptionsWidget()
    qtbot.addWidget(widget)
    widget.resize(450, 650)
    widget.show()
    qtbot.wait(20)
    scroll = widget._tab_widget.tab_widgets[0]
    assert scroll.horizontalScrollBar().maximum() == 0
    assert widget.spottiness_gb.geometry().top() > widget.corrections_gb.geometry().top()
    widget.resize(900, 650)
    qtbot.wait(20)
    assert scroll.horizontalScrollBar().maximum() == 0
    assert widget.spottiness_gb.geometry().top() == widget.corrections_gb.geometry().top()
