import os
import numpy as np
import pytest
from pytest import approx
from qtpy import QtWidgets, QtCore
from qtpy.QtTest import QTest

from mock import MagicMock
from dioptas.controller.MapController import MapController
from dioptas.model.DioptasModel import DioptasModel

from dioptas.model.MapModel import MapModel, MapPointInfo
from dioptas.model.util.calc import convert_units
from dioptas.widgets.MapWidget import MapWidget
from dioptas.widgets.plot_widgets.PatternWidget import SymmetricModifiedLinearRegionItem


unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, os.pardir, "data")
map_img_path = os.path.join(data_path, "map")
map_pattern_path = os.path.join(data_path, "map", "xy")
map_img_file_names = [
    f for f in os.listdir(map_img_path) if os.path.isfile(os.path.join(map_img_path, f))
]
map_img_file_paths = [
    os.path.join(map_img_path, filename) for filename in map_img_file_names
]


@pytest.fixture
def dioptas_model():
    return DioptasModel()


@pytest.fixture
def map_controller(qapp, dioptas_model: DioptasModel):
    """Fixture providing a MainController instance"""
    widget = MapWidget()
    model = dioptas_model
    controller = MapController(widget, model)
    controller.widget.setAttribute(QtCore.Qt.WA_DeleteOnClose)
    QTest.qWaitForWindowExposed(controller.widget)
    try:
        yield controller
    finally:
        controller.widget.close()


@pytest.fixture
def map_model(map_controller) -> MapModel:
    return map_controller.model.map_model


def load_calibration(map_controller: MapController):
    map_controller.model.current_configuration.calibration_model.load(
        os.path.join(data_path, "CeO2_Pilatus1M.poni")
    )


def mock_open_filenames(filepaths):
    QtWidgets.QFileDialog.getOpenFileNames = MagicMock(return_value=filepaths)


def mock_save_filename(filepath):
    QtWidgets.QFileDialog.getSaveFileName = MagicMock(return_value=filepath)


def mock_map_model(map_model: MapModel):
    map_model.window_intensities = np.array([1, 2, 3, 4, 5, 6])
    map_model.filepaths = map_img_file_paths
    map_model.possible_dimensions = [(1, 6), (2, 3), (3, 2), (6, 1)]
    map_model.point_infos = [MapPointInfo(f) for f in map_img_file_paths]
    map_model.dimension = (2, 3)  # builds the map and emits map_changed


def mock_integrate_1d(map_controller: MapController):
    map_controller.model.calibration_model.integrate_1d = MagicMock(
        return_value=(np.arange(10), np.arange(10))
    )


def test_click_load_starts_creating_map(map_controller, map_model: MapModel):
    map_model.load = MagicMock()
    mock_open_filenames(map_img_file_paths)
    mock_integrate_1d(map_controller)
    map_controller.load_btn_clicked()
    map_model.load.assert_called_once()
    assert map_model.load.call_args[0][0] == map_img_file_paths


def test_click_load_empties_file_list_without_calibration(
    map_controller, map_model: MapModel
):
    mock_open_filenames(map_img_file_paths)
    QtWidgets.QMessageBox.critical = MagicMock()
    map_controller.load_btn_clicked()

    assert map_controller.widget.control_widget.file_list.count() == 0
    assert QtWidgets.QMessageBox.critical.assert_called_once


def test_load_empty_filelist(map_controller, map_model: MapModel):
    mock_open_filenames([])
    map_controller.load_btn_clicked()

    assert map_controller.widget.control_widget.file_list.count() == 0


def test_files_with_different_dimensions(map_controller, map_model: MapModel):
    load_calibration(map_controller)
    mock_open_filenames(
        [
            os.path.join(data_path, "CeO2_Pilatus1M.tif"),
            os.path.join(data_path, "image_001.tif"),
        ]
    )
    QtWidgets.QMessageBox.critical = MagicMock()
    map_controller.load_btn_clicked()
    assert QtWidgets.QMessageBox.critical.assert_called_once
    assert map_model.filepaths is None
    assert map_controller.widget.control_widget.file_list.count() == 0


def test_files_with_different_dimensions_shows_error_dialog(
    map_controller, map_model: MapModel
):
    """RuntimeError from dioptrin shape mismatch is caught and shown as error dialog."""
    mock_open_filenames(map_img_file_paths)
    map_model.load = MagicMock(
        side_effect=RuntimeError("mask dim1 mismatch: mask = 2048, data = 3262")
    )
    QtWidgets.QMessageBox.critical = MagicMock()
    map_controller.load_btn_clicked()
    QtWidgets.QMessageBox.critical.assert_called_once()
    assert "mask dim1 mismatch" in str(
        QtWidgets.QMessageBox.critical.call_args
    )


def test_click_load_fills_file_list(map_controller, map_model: MapModel):
    load_calibration(map_controller)
    assert map_controller.model.current_configuration.is_calibrated == True
    mock_open_filenames(map_img_file_paths)
    mock_integrate_1d(map_controller)
    map_controller.load_btn_clicked()

    assert map_model.filepaths == map_img_file_paths
    assert map_controller.widget.control_widget.file_list.count() == len(
        map_img_file_paths
    )


def test_mask_is_shown(map_controller):
    img_model = map_controller.model.img_model
    mask_model = map_controller.model.mask_model
    img_model.load(map_img_file_paths[0])

    map_controller.model.use_mask = True

    mask = np.zeros_like(img_model.img_data, dtype=bool)
    mask[0, 0] = True
    mask_model.set_mask(mask)
    img_model.img_changed.emit()

    assert map_controller.widget.img_plot_widget.mask_data is not None
    assert np.array_equal(map_controller.widget.img_plot_widget.mask_data, mask)


def test_loading_files_plots_map(map_controller: MapController, map_model: MapModel):
    load_calibration(map_controller)
    assert map_controller.model.current_configuration.is_calibrated == True
    assert map_controller.widget.map_plot_widget.img_data is None

    mock_open_filenames(map_img_file_paths)
    mock_integrate_1d(map_controller)
    map_controller.load_btn_clicked()

    plot_widget = map_controller.widget.map_plot_widget

    assert map_model.map is not None
    assert plot_widget.img_data is not None
    assert plot_widget.img_data.shape == map_model.map.shape
    assert plot_widget.data_img_item.image is not None


def test_loading_files_also_plots_first_image(
    map_controller: MapController, map_model: MapModel
):
    load_calibration(map_controller)
    assert map_controller.model.current_configuration.is_calibrated == True
    mock_open_filenames(map_img_file_paths)
    mock_integrate_1d(map_controller)
    map_controller.load_btn_clicked()

    plot_widget = map_controller.widget.img_plot_widget

    assert plot_widget.img_data is not None
    assert (
        plot_widget.img_data.shape == map_model.configuration.img_model.img_data.shape
    )
    assert np.array_equal(
        plot_widget.img_data, map_model.configuration.img_model.img_data
    )
    assert plot_widget.data_img_item.image is not None


def test_click_load_shows_error_if_not_calibrated(map_controller):
    mock_open_filenames(map_img_file_paths)
    assert map_controller.model.current_configuration.is_calibrated == False
    QtWidgets.QMessageBox.critical = MagicMock()
    map_controller.load_btn_clicked()
    assert QtWidgets.QMessageBox.critical.assert_called_once


def test_select_file_in_file_list_will_update_gui(map_controller):
    load_calibration(map_controller)
    mock_open_filenames(map_img_file_paths)
    map_controller.load_btn_clicked()

    # cache current image
    current_img = map_controller.widget.img_plot_widget.img_data.copy()

    # select second file in file list
    map_controller.widget.control_widget.file_list.setCurrentRow(1)
    assert (
        map_controller.model.current_configuration.img_model.filename
        == map_img_file_paths[1]
    )

    # check that image has changed
    assert not np.array_equal(
        map_controller.widget.img_plot_widget.img_data, current_img
    )


def test_mouse_click_item_in_map_plot_widget_updates_correctly(
    map_controller, dioptas_model
):
    load_calibration(map_controller)
    mock_open_filenames(map_img_file_paths)
    map_controller.load_btn_clicked()

    # loading selects the first point, so the marker starts on its center
    click_x, click_y = map_controller.widget.map_plot_widget.mouse_click_item.getData()
    assert click_x[0] == approx(0.5)
    assert click_y[0] == approx(2.5)

    map_controller.widget.control_widget.file_list.setCurrentRow(1)
    # check that mouse click item in map_plot_widget has changed
    click_x, click_y = map_controller.widget.map_plot_widget.mouse_click_item.getData()
    assert click_x[0] == approx(1.5)
    assert click_y[0] == approx(2.5)

    # check that replotting does not change po
    map_controller.widget.pattern_plot_widget.mouse_left_clicked.emit(10, 0)

    click_x, click_y = map_controller.widget.map_plot_widget.mouse_click_item.getData()
    assert click_x[0] == approx(1.5)
    assert click_y[0] == approx(2.5)


def test_select_file_in_file_list_integrates_1d_only_once(map_controller):
    load_calibration(map_controller)
    mock_open_filenames(map_img_file_paths[:2])
    mock_integrate_1d(map_controller)
    map_controller.load_btn_clicked()
    load_call_count = map_controller.model.calibration_model.integrate_1d.call_count
    map_controller.widget.control_widget.file_list.setCurrentRow(1)
    assert (
        map_controller.model.calibration_model.integrate_1d.call_count
        == load_call_count + 1
    )


def test_click_in_map_image_will_update_gui(map_controller):
    load_calibration(map_controller)
    mock_open_filenames(map_img_file_paths)
    mock_integrate_1d(map_controller)
    map_controller.load_btn_clicked()
    load_call_count = map_controller.model.calibration_model.integrate_1d.call_count

    # select second file in file list
    map_controller.widget.map_plot_widget.mouse_left_clicked.emit(2, 2)
    assert (
        map_controller.model.current_configuration.img_model.filename
        == map_img_file_paths[2]
    )
    assert map_controller.widget.control_widget.file_list.currentRow() == 2

    # check that integrate_1d was called only once
    assert (
        map_controller.model.calibration_model.integrate_1d.call_count
        == load_call_count + 1
    )


def test_click_in_pattern_will_update_region_of_interest(map_controller):
    click_pos = 30
    map_controller.widget.pattern_plot_widget.mouse_left_clicked.emit(click_pos, 10)
    assert (
        map_controller.widget.pattern_plot_widget.map_interactive_roi.center
        == approx(click_pos)
    )


def test_pattern_interactive_roi_updates_map(map_controller):
    map_controller.model.map_model.set_window = MagicMock()
    map_controller.widget.pattern_plot_widget.map_interactive_roi.sigRegionChanged.emit(
        SymmetricModifiedLinearRegionItem((10, 11))
    )
    map_controller.model.map_model.set_window.assert_called_once_with((10, 11))


def test_stored_pattern_is_converted_into_the_displayed_unit(map_controller):
    """With reintegrate off the pattern comes from the stored map data, which
    is kept in the unit the map was integrated in."""
    load_calibration(map_controller)
    mock_open_filenames(map_img_file_paths)
    map_controller.load_btn_clicked()
    map_controller._active = True

    model = map_controller.model
    assert model.map_model.pattern_unit == "2th_deg"
    tth_max = model.map_model.pattern_x.max()

    model.integration_unit = "q_A^-1"
    map_controller.widget.control_widget.file_list.setCurrentRow(1)

    wavelength = model.calibration_model.wavelength
    expected_max = convert_units(tth_max, wavelength, "2th_deg", "q_A^-1")
    assert model.pattern.x.max() == approx(expected_max, rel=1e-6)


def test_stored_pattern_of_a_map_in_the_displayed_unit_is_untouched(map_controller):
    load_calibration(map_controller)
    mock_open_filenames(map_img_file_paths)
    map_controller.load_btn_clicked()
    map_controller._active = True

    model = map_controller.model
    map_controller.widget.control_widget.file_list.setCurrentRow(1)

    np.testing.assert_array_equal(model.pattern.x, model.map_model.pattern_x)


def test_mouse_move_in_map_image_will_update_xyI(map_controller, map_model):
    mock_map_model(map_model)

    map_widget = map_controller.widget
    map_plot_widget = map_widget.map_plot_widget
    map_plot_control_widget = map_widget.map_plot_control_widget

    map_plot_widget.mouse_moved.emit(0, 1)
    assert map_plot_control_widget.mouse_x_label.text() == "X: 0"
    assert map_plot_control_widget.mouse_y_label.text() == "Y: 0"
    assert map_plot_control_widget.mouse_int_label.text() == "I: 1"

    # even when it is on fractional coordinates it should be rounded down
    map_plot_widget.mouse_moved.emit(0.7, 1.8)
    assert map_plot_control_widget.mouse_x_label.text() == "X: 0"
    assert map_plot_control_widget.mouse_y_label.text() == "Y: 0"
    assert map_plot_control_widget.mouse_int_label.text() == "I: 1"

    map_plot_widget.mouse_moved.emit(1, 0.7)
    assert map_plot_control_widget.mouse_x_label.text() == "X: 1"
    assert map_plot_control_widget.mouse_y_label.text() == "Y: 1"

    # it does not give coordinates, when outside of the map dimensions
    map_plot_widget.mouse_moved.emit(10, 10)
    assert map_plot_control_widget.mouse_x_label.text() == "X: "
    assert map_plot_control_widget.mouse_y_label.text() == "Y: "


def test_mouse_move_in_map_will_update_filename(map_controller, map_model):
    mock_map_model(map_model)
    map_controller.widget.map_plot_widget.mouse_moved.emit(0, 1)
    assert (
        map_controller.widget.map_plot_control_widget.filename_label.text()
        == map_img_file_names[0]
    )
    map_controller.widget.map_plot_widget.mouse_moved.emit(1, 1)
    assert (
        map_controller.widget.map_plot_control_widget.filename_label.text()
        == map_img_file_names[1]
    )
    map_controller.widget.map_plot_widget.mouse_moved.emit(0, 0)
    assert (
        map_controller.widget.map_plot_control_widget.filename_label.text()
        == map_img_file_names[3]
    )


def test_map_dimension_cb_updates_correctly(map_controller, map_model):
    map_model.window_intensities = np.array([1, 2, 3, 4, 5, 6])
    map_model.possible_dimensions = [(1, 6), (2, 3), (3, 2), (6, 1)]
    map_model.dimension = (2, 3)  # builds the map and emits map_changed

    # the grid sizes live in the grid popup, next to the rows/columns they
    # are shorthand for
    grid_popup = map_controller.panel_controller.grid_popup
    map_controller.widget.map_plot_control_widget.grid_btn.clicked.emit()
    dim_cb = grid_popup.map_dimension_cb
    assert dim_cb.currentText() == "2x3"
    assert dim_cb.count() == 4
    assert dim_cb.currentIndex() == 1

    cb_items = [dim_cb.itemText(i) for i in range(dim_cb.count())]
    dimension_str = [f"{x}x{y}" for x, y in map_model.possible_dimensions]
    assert cb_items == dimension_str

    # changing dimensions:
    dim_cb.setCurrentIndex(2)
    assert map_model.dimension == (3, 2)
    assert map_model.map.shape == (3, 2)
    grid_popup.hide()


def test_changing_configuration_updates_gui(map_controller, dioptas_model):
    load_calibration(map_controller)
    mock_open_filenames(map_img_file_paths)
    mock_integrate_1d(map_controller)
    map_controller.load_btn_clicked()

    map_config0 = map_controller.widget.map_plot_widget.img_data.copy()

    dioptas_model.add_configuration()
    assert dioptas_model.map_model.map is None

    load_calibration(map_controller)
    mock_open_filenames(list(reversed(map_img_file_paths)))
    map_controller.load_btn_clicked()

    assert dioptas_model.configurations[1].map_model.map is not None
    map_config1 = map_controller.widget.map_plot_widget.img_data.copy()
    assert np.array_equal(map_config1, map_config1)

    dioptas_model.select_configuration(0)
    assert map_controller.widget.map_plot_widget.img_data is not None
    assert np.array_equal(map_controller.widget.map_plot_widget.img_data, map_config0)

    items_text = [
        map_controller.widget.control_widget.file_list.item(i).text()
        for i in range(map_controller.widget.control_widget.file_list.count())
    ]
    assert items_text == map_img_file_names

    dioptas_model.select_configuration(1)
    assert np.array_equal(map_controller.widget.map_plot_widget.img_data, map_config1)

    items_text = [
        map_controller.widget.control_widget.file_list.item(i).text()
        for i in range(map_controller.widget.control_widget.file_list.count())
    ]
    assert items_text == list(reversed(map_img_file_names))


def test_progress_dialog_is_shown(map_controller):
    load_calibration(map_controller)
    mock_open_filenames(map_img_file_paths)
    mock_integrate_1d(map_controller)

    QtWidgets.QProgressDialog.setValue = MagicMock()
    map_controller.load_btn_clicked()

    # Progress dialog should be updated at least once (callbacks are throttled to
    # avoid GUI overhead, so the count may be less than the number of images)
    assert QtWidgets.QProgressDialog.setValue.call_count >= 1


def test_phase_is_displayed(map_controller, dioptas_model):
    load_calibration(map_controller)
    mock_integrate_1d(map_controller)
    mock_open_filenames(map_img_file_paths)
    map_controller.load_btn_clicked()

    pattern_widget = map_controller.widget.pattern_plot_widget

    assert pattern_widget.phases == []

    dioptas_model.phase_model.add_jcpds(os.path.join(data_path, "jcpds", "ar.jcpds"))
    assert len(pattern_widget.phases) == 1


def test_overlay_is_displayed(map_controller, dioptas_model: DioptasModel):
    dioptas_model.overlay_model.add_overlay(np.arange(10), np.arange(10), "test")
    pattern_widget = map_controller.widget.pattern_plot_widget

    assert len(pattern_widget.overlays) == 1


def test_green_line_in_pattern_plot(map_controller, dioptas_model):
    pattern_widget = map_controller.widget.pattern_plot_widget

    current_value = pattern_widget.get_pos_line()
    assert current_value is 0

    dioptas_model.clicked_tth_changed.emit(10)
    assert dioptas_model.clicked_tth == 10
    assert pattern_widget.get_pos_line() == 10

    # change unit, so that position of the line needs to
    # be in new unit
    dioptas_model.integration_unit = "q_A^-1"
    dioptas_model.clicked_tth_changed.emit(10)
    assert dioptas_model.clicked_tth == 10
    assert pattern_widget.get_pos_line() != 10


def test_green_line_shown_in_image(map_controller, dioptas_model):
    load_calibration(map_controller)
    mock_open_filenames(map_img_file_paths[:1])
    map_controller.load_btn_clicked()

    img_widget = map_controller.widget.img_plot_widget
    circle_plot_item = img_widget.circle_plot_items[0]
    x, y = circle_plot_item.getData()
    assert x is None
    assert y is None

    dioptas_model.clicked_tth_changed.emit(10)
    x, y = circle_plot_item.getData()
    assert len(x) > 0
    assert len(y) > 0


def test_green_line_shown_in_image_without_calibration(map_controller, dioptas_model):
    img_widget = map_controller.widget.img_plot_widget
    circle_plot_item = img_widget.circle_plot_items[0]

    dioptas_model.clicked_tth_changed.emit(10)
    x, y = circle_plot_item.getData()
    assert x is None
    assert y is None


def test_clicking_image_updates_tth_and_azi(map_controller, dioptas_model):
    load_calibration(map_controller)
    mock_open_filenames(map_img_file_paths[:1])
    map_controller.load_btn_clicked()

    img_widget = map_controller.widget.img_plot_widget
    assert dioptas_model.clicked_tth == 0
    assert dioptas_model.clicked_azi == 0
    img_widget.mouse_left_clicked.emit(100, 100)

    assert dioptas_model.clicked_tth != 0
    assert dioptas_model.clicked_azi != 0


def test_pattern_mouse_move_displays_positions(
    map_controller: MapController, dioptas_model: DioptasModel
):
    pattern_widget = map_controller.widget.pattern_plot_widget
    pos_widget = (
        map_controller.widget.pattern_footer_widget.mouse_unit_widget.cur_unit_widget
    )
    assert pos_widget.tth_lbl.text() == "2θ:"
    pattern_widget.mouse_moved.emit(10, 20)
    assert pos_widget.tth_lbl.text() == "2θ:%9.3f" % 10


def test_img_mouse_move_displays_positions(
    map_controller: MapController, dioptas_model: DioptasModel
):
    img_widget = map_controller.widget.img_plot_widget
    pos_widget = (
        map_controller.widget.pattern_footer_widget.mouse_unit_widget.cur_unit_widget
    )
    image_x = map_controller.widget.map_plot_control_widget.mouse_x_label
    image_y = map_controller.widget.map_plot_control_widget.mouse_y_label
    image_int = map_controller.widget.map_plot_control_widget.mouse_int_label
    assert pos_widget.tth_lbl.text() == "2θ:"

    img_widget.mouse_moved.emit(10, 20)
    assert image_x.text() == "X: 10"
    assert image_y.text() == "Y: 20"
    assert image_int.text() == "I: 0"

    load_calibration(map_controller)
    dioptas_model.img_model.load(map_img_file_paths[0])
    img_widget.mouse_moved.emit(100, 200)
    tth = dioptas_model.calibration_model.get_two_theta_img(200, 100)
    azi = dioptas_model.calibration_model.get_azi_img(200, 100)
    assert pos_widget.tth_lbl.text() == "2θ:%9.3f" % np.rad2deg(tth)
    assert pos_widget.azi_lbl.text() == "X:%9.3f" % np.rad2deg(azi)


def test_change_integration_unit(
    map_controller: MapController, dioptas_model: DioptasModel
):
    pattern_widget = map_controller.widget.pattern_plot_widget
    pattern_plot = pattern_widget.pattern_plot
    mock_integrate_1d(map_controller)
    load_calibration(map_controller)

    assert dioptas_model.integration_unit == "2th_deg"
    assert pattern_plot.getAxis("bottom").labelText == "2θ"
    assert pattern_plot.getAxis("bottom").labelUnits == "°"

    dioptas_model.integration_unit = "q_A^-1"
    assert pattern_plot.getAxis("bottom").labelText == "Q"
    assert pattern_plot.getAxis("bottom").labelUnits == "Å⁻¹"

    dioptas_model.integration_unit = "d_A"
    assert pattern_plot.getAxis("bottom").labelText == "d"
    assert pattern_plot.getAxis("bottom").labelUnits == "Å"

    dioptas_model.integration_unit = "2th_deg"
    assert pattern_plot.getAxis("bottom").labelText == "2θ"
    assert pattern_plot.getAxis("bottom").labelUnits == "°"


@pytest.mark.parametrize("file_type", ["png", "tiff", "txt"])
def test_save_map(map_controller, dioptas_model, tmp_path, file_type):
    mock_map_model(dioptas_model.map_model)
    map_widget = map_controller.widget

    filename = tmp_path / f"test_map.{file_type}"
    mock_save_filename(filename)

    map_widget.map_plot_control_widget.save_map_btn.clicked.emit()
    assert filename.exists()


def load_map(map_controller, count=6):
    load_calibration(map_controller)
    map_controller.model.map_model.load(map_img_file_paths[:count])
    return map_controller.model.map_model


def file_list_labels(map_controller):
    file_list = map_controller.widget.control_widget.file_list
    return [file_list.item(i).text() for i in range(file_list.count())]


def test_file_list_shows_one_row_per_grid_cell(map_controller):
    map_model = load_map(map_controller)
    assert len(file_list_labels(map_controller)) == 6

    map_model.insert_blank(2)
    labels = file_list_labels(map_controller)
    # the grid grew to 3x3 to make room, so the list grows with it
    assert len(labels) == 9
    assert labels[2] == "—"
    assert labels[3] == map_model.point_infos[2].filename


def test_file_list_row_selects_the_point_of_that_cell(map_controller):
    map_model = load_map(map_controller)
    map_model.insert_blank(0)

    map_controller.widget.control_widget.file_list.setCurrentRow(1)
    assert map_controller.model.img_model.filename == map_model.point_infos[0].filepath


def test_blank_row_selects_nothing(map_controller):
    map_model = load_map(map_controller)
    map_controller.widget.control_widget.file_list.setCurrentRow(2)
    loaded = map_controller.model.img_model.filename

    map_model.insert_blank(0)
    map_controller.widget.control_widget.file_list.setCurrentRow(0)
    assert map_controller.model.img_model.filename == loaded


def test_map_click_selects_the_matching_cell_row(map_controller):
    map_model = load_map(map_controller)
    map_model.insert_blank(0)

    # point 4 sits one cell later than it would without the blank
    map_controller.panel_controller.point_selected.emit(4)
    assert map_controller.widget.control_widget.file_list.currentRow() == 5


def test_dragging_a_row_rearranges_the_map(map_controller):
    map_model = load_map(map_controller)
    file_list = map_controller.widget.control_widget.file_list

    # an internal-move drag moves the row through the model, which is what
    # the controller listens to
    root = QtCore.QModelIndex()
    assert file_list.model().moveRow(root, 0, root, 3) is True
    assert map_model.get_slots()[:3] == [1, 2, 0]

    # and back the other way, where the insertion point needs no adjusting
    assert file_list.model().moveRow(root, 2, root, 0) is True
    assert map_model.get_slots()[:3] == [0, 1, 2]


def test_excluded_point_keeps_its_row_struck_through(map_controller):
    """Leaving a point out closes its cell in the map, but its row in the
    list stays where it was — struck through, not shuffled to the end."""
    map_model = load_map(map_controller)
    file_list = map_controller.widget.control_widget.file_list
    map_model.set_point_excluded(1)

    assert file_list.count() == map_model.num_slots
    row = file_list.item(1)
    assert row.text() == map_model.point_infos[1].filename
    assert row.font().strikeOut() is True
    # while the map closed up: point 2 moved into the freed cell
    assert map_model.get_point_index(0, 1) == 2

    # and putting it back restores everything
    map_model.set_point_excluded(1, False)
    assert file_list.item(1).font().strikeOut() is False
    assert map_model.get_point_index(0, 1) == 1


def test_grid_popup_shows_and_applies_the_layout(map_controller):
    map_model = load_map(map_controller)
    popup = map_controller.panel_controller.grid_popup

    map_controller.widget.map_plot_control_widget.grid_btn.clicked.emit()
    assert popup.rows_sb.value() == 2
    assert popup.columns_sb.value() == 3
    assert "no blanks" in popup.capacity_lbl.text()

    popup.sigGridChanged.emit(3, 3)
    assert map_model.dimension == (3, 3)
    assert "3 blank" in popup.capacity_lbl.text()

    popup.sigSnakeChanged.emit(True)
    assert map_model.snake is True
    popup.sigFlipVerticalChanged.emit(True)
    assert map_model.flip_vertical is True
    popup.hide()


def test_grid_popup_detects_dropped_frames(map_controller):
    map_model = load_map(map_controller)
    popup = map_controller.panel_controller.grid_popup

    for index, info in enumerate(map_model.point_infos):
        info.filepath = f"/scan/point_{index if index < 3 else index + 1:03d}.tif"

    popup.sigDetectGapsRequested.emit()
    assert "Inserted 1 blank cell" in popup.gaps_lbl.text()
    assert map_model.get_point_index(0, 3) is None


def test_grid_popup_reports_when_there_is_nothing_to_fix(map_controller):
    load_map(map_controller)
    popup = map_controller.panel_controller.grid_popup

    popup.sigDetectGapsRequested.emit()
    assert "No gaps" in popup.gaps_lbl.text()


def layer_widget(map_controller):
    return map_controller.widget.control_widget.layer_widget


def show_button(table, row):
    """The 'draw this layer' radio of a row."""
    holder = table.cellWidget(row, 0)
    return None if holder is None else holder.findChild(QtWidgets.QRadioButton)


def test_layer_widget_shows_the_map_windows(map_controller):
    load_map(map_controller)
    table = layer_widget(map_controller).roi_table
    assert table.rowCount() == 1
    assert table.item(0, 2).text() == "A"


def test_adding_a_window_adds_a_layer(map_controller):
    map_model = load_map(map_controller)
    layer_widget(map_controller).sigAddRoiRequested.emit()

    assert [roi.name for roi in map_model.rois] == ["A", "B"]
    assert layer_widget(map_controller).roi_table.rowCount() == 2

    layer_cb = map_controller.widget.map_plot_control_widget.layer_cb
    assert [layer_cb.itemText(i) for i in range(layer_cb.count())] == ["A", "B"]


def test_layer_combo_switches_which_layer_is_shown(map_controller):
    map_model = load_map(map_controller)
    map_model.add_roi(window=(15.0, 16.0))

    layer_cb = map_controller.widget.map_plot_control_widget.layer_cb
    layer_cb.setCurrentIndex(1)
    assert map_model.active_layer == "B"
    np.testing.assert_array_equal(
        map_model.window_intensities, map_model.layer_values("B")
    )


def test_editing_a_window_range_in_the_table(map_controller):
    map_model = load_map(map_controller)
    layer_widget(map_controller).sigRoiChanged.emit("A", "x_min", 14.0)
    layer_widget(map_controller).sigRoiChanged.emit("A", "x_max", 16.0)
    assert map_model.window == approx([14.0, 16.0])


def test_changing_the_reduction_changes_the_map(map_controller):
    map_model = load_map(map_controller)
    map_model.set_window((14.0, 16.0))
    before = map_model.map.copy()

    layer_widget(map_controller).sigRoiChanged.emit("A", "value_kind", ("center", False))
    assert map_model.rois[0].reduction == "center"
    assert not np.allclose(map_model.map, before)


def test_removing_the_only_window_is_refused_with_a_message(map_controller):
    load_map(map_controller)
    layer_widget(map_controller).sigRemoveRoiRequested.emit("A")
    assert "at least one window" in layer_widget(map_controller).message_lbl.text()


def test_adding_a_computed_layer_needs_two_windows(map_controller):
    load_map(map_controller)
    widget = layer_widget(map_controller)

    widget.sigAddExpressionRequested.emit()
    assert "second window" in widget.message_lbl.text()

    widget.sigAddRoiRequested.emit()
    widget.sigAddExpressionRequested.emit()
    assert widget.expression_table.rowCount() == 1
    assert widget.expression_table.item(0, 1).text() == "A/B"


def test_a_bad_expression_is_reported_rather_than_applied(map_controller):
    map_model = load_map(map_controller)
    map_model.add_roi(window=(15.0, 16.0))
    widget = layer_widget(map_controller)

    widget.sigExpressionChanged.emit("bad", "A/Z")
    assert "no layer called 'Z'" in widget.message_lbl.text()
    assert map_model.layer_values("bad") is None
    # the map keeps showing something valid
    assert map_model.map is not None


def test_extra_windows_get_their_own_region_in_the_pattern(map_controller):
    map_model = load_map(map_controller)
    roi_controller = map_controller.map_roi_controller
    assert roi_controller._extra_items == {}

    map_model.add_roi(window=(15.0, 16.0))
    assert list(roi_controller._extra_items) == ["B"]

    map_model.remove_roi("B")
    assert roi_controller._extra_items == {}


def test_dragging_an_extra_region_moves_that_window(map_controller):
    map_model = load_map(map_controller)
    map_model.add_roi(window=(15.0, 16.0))
    item = map_controller.map_roi_controller._extra_items["B"]

    item.setRegion((17.0, 18.0))
    assert map_model.get_roi("B").x_min == approx(17.0)
    assert map_model.get_roi("B").x_max == approx(18.0)
    # the active window is untouched
    assert map_model.get_roi("A").x_min != approx(17.0)


def test_layer_table_updates_in_place_while_the_windows_are_the_same(map_controller):
    """The map rebuilds on every edit, so the table must not be recreated
    each time: replaced cell widgets keep painting until Qt deletes them, and
    the row under the user's cursor would jump away."""
    map_model = load_map(map_controller)
    table = layer_widget(map_controller).roi_table
    value_cb = table.cellWidget(0, 5)

    map_model.set_window((14.0, 16.0))

    assert table.cellWidget(0, 5) is value_cb  # same widget, not a new one
    assert table.item(0, 3).text() == "14"
    assert table.item(0, 4).text() == "16"

    # a window appearing or going does rebuild, and leaves nothing behind
    map_model.add_roi(window=(16.5, 18.0))
    assert table.rowCount() == 2
    assert isinstance(table.cellWidget(1, 5), QtWidgets.QComboBox)
    assert show_button(table, 1) is not None


def test_selecting_a_window_survives_a_map_rebuild(map_controller):
    map_model = load_map(map_controller)
    map_model.add_roi(window=(16.5, 18.0))
    table = layer_widget(map_controller).roi_table

    table.setCurrentCell(1, 0)
    map_model.set_window((14.0, 16.0))
    assert table.currentRow() == 1


def test_image_moves_into_the_tabs_only_when_the_panel_is_narrow(map_controller):
    """The detector image sits beside the controls while there is room, and
    becomes the leftmost tab when there is not — side by side at small
    widths, the image and the tables squeezed each other."""
    widget = map_controller.widget
    tabs = widget.control_widget.tab_widget

    widget._set_image_tabbed(True)
    assert [tabs.tabText(i) for i in range(tabs.count())] == [
        "Image",
        "Points",
        "Layers",
    ]
    assert tabs.widget(0) is widget.img_pg_layout

    widget._set_image_tabbed(False)
    assert [tabs.tabText(i) for i in range(tabs.count())] == ["Points", "Layers"]
    assert widget.upper_right_splitter.widget(0) is widget.img_pg_layout


def test_image_home_follows_the_available_width(map_controller):
    widget = map_controller.widget
    controls_min = widget.control_widget.minimumSizeHint().width()

    assert widget._image_should_be_tabbed(controls_min + 100) is True
    assert widget._image_should_be_tabbed(controls_min + 400) is False


def test_switching_the_image_home_keeps_the_current_tab(map_controller):
    widget = map_controller.widget
    tabs = widget.control_widget.tab_widget
    widget._set_image_tabbed(False)

    tabs.setCurrentWidget(widget.control_widget.layer_widget)
    widget._set_image_tabbed(True)
    assert tabs.currentWidget() is widget.control_widget.layer_widget

    widget._set_image_tabbed(False)
    assert tabs.currentWidget() is widget.control_widget.layer_widget


def test_image_still_plots_after_moving_between_homes(map_controller):
    widget = map_controller.widget
    map_controller.activate()  # the image only updates while the mode is up
    load_map(map_controller)
    widget._set_image_tabbed(True)
    widget._set_image_tabbed(False)
    widget._set_image_tabbed(True)

    assert widget.img_plot_widget.img_data is not None



def test_show_radio_picks_which_layer_is_drawn(map_controller):
    """The explicit answer to 'how do I display another layer': a radio in
    each row, next to the window it belongs to."""
    map_model = load_map(map_controller)
    map_model.add_roi(window=(16.5, 18.0))
    map_model.set_expression("A/B", "A/B")
    table = layer_widget(map_controller).roi_table
    expression_table = layer_widget(map_controller).expression_table

    assert show_button(table, 0).isChecked() is True
    assert show_button(table, 1).isChecked() is False

    show_button(table, 1).setChecked(True)
    assert map_model.active_layer == "B"
    assert show_button(table, 0).isChecked() is False

    # the group spans both tables, so exactly one layer is ever drawn
    show_button(expression_table, 0).setChecked(True)
    assert map_model.active_layer == "A/B"
    assert show_button(table, 0).isChecked() is False
    assert show_button(table, 1).isChecked() is False


def test_show_radio_follows_a_layer_picked_elsewhere(map_controller):
    map_model = load_map(map_controller)
    map_model.add_roi(window=(16.5, 18.0))
    table = layer_widget(map_controller).roi_table

    map_controller.widget.map_plot_control_widget.layer_cb.setCurrentIndex(0)
    assert map_model.active_layer == "A"
    assert show_button(table, 0).isChecked() is True
    assert show_button(table, 1).isChecked() is False


def test_layer_table_columns_fit_what_the_style_draws(map_controller):
    """Widths are measured from the style, not hard-coded: qt-material draws
    the headers upper-cased, which clipped 'NAME' to 'AN' at fixed pixels."""
    load_map(map_controller)
    table = layer_widget(map_controller).roi_table
    header = table.horizontalHeader()

    for column in range(5):
        assert table.columnWidth(column) >= header.sectionSizeHint(column)

    # and the table refuses to be squeezed below what the stretching Value
    # column needs for its combo, which would otherwise just be clipped
    fixed = sum(table.columnWidth(column) for column in range(5))
    assert table.minimumWidth() > fixed


def test_windows_table_scrolls_instead_of_pushing_the_layers_down(map_controller):
    """Sizing the table to its rows meant every added window pushed the
    computed layers further down the panel. Each table now fills its own
    pane of the splitter and scrolls inside it."""
    map_model = load_map(map_controller)
    widget = layer_widget(map_controller)
    assert widget.splitter.count() == 2

    floor = widget.roi_table.minimumHeight()
    assert floor > 0  # a couple of rows stay reachable at any split

    for window in ((16.5, 18.0), (19.0, 21.0), (22.0, 24.0), (25.0, 27.0)):
        map_model.add_roi(window=window)

    assert widget.roi_table.minimumHeight() == floor
    # not pinned to its contents any more, so the pane decides its height
    assert widget.roi_table.maximumHeight() > 10000


def popup_and_button(map_controller):
    return (
        map_controller.panel_controller.grid_popup,
        map_controller.widget.map_plot_control_widget.grid_btn,
    )


def test_grid_popup_opens_upwards_when_there_is_no_room_below(map_controller):
    """Its button lives in the strip along the bottom of the map, so dropping
    downwards would put the popup off the screen."""
    from qtpy import QtGui

    load_map(map_controller)
    popup, button = popup_and_button(map_controller)
    available = QtGui.QGuiApplication.primaryScreen().availableGeometry()

    # put the window so its bottom strip sits at the bottom of the screen
    window = map_controller.widget
    window.move(available.left(), available.bottom() - window.height() + 1)
    QtWidgets.QApplication.processEvents()

    popup.popup_at(button)
    try:
        geometry = popup.frameGeometry()
        assert geometry.bottom() <= available.bottom()
        assert geometry.top() >= available.top()
        # opened above the button rather than over it
        assert geometry.bottom() <= button.mapToGlobal(QtCore.QPoint(0, 0)).y() + 1
    finally:
        popup.hide()


def test_grid_popup_stays_within_the_screen_horizontally(map_controller):
    from qtpy import QtGui

    load_map(map_controller)
    popup, button = popup_and_button(map_controller)
    available = QtGui.QGuiApplication.primaryScreen().availableGeometry()

    window = map_controller.widget
    window.move(available.right() - 60, available.top())
    QtWidgets.QApplication.processEvents()

    popup.popup_at(button)
    try:
        geometry = popup.frameGeometry()
        assert geometry.left() >= available.left()
        assert geometry.right() <= available.right()
    finally:
        popup.hide()


def click_map_cell(map_controller, row, col):
    """Clicks the given map cell through the plot widget's mouse signal."""
    rows = map_controller.model.map_model.map.shape[0]
    map_controller.widget.map_plot_widget.mouse_left_clicked.emit(
        col + 0.5, rows - row - 1 + 0.5
    )


def test_clicking_a_blank_cell_selects_nothing(map_controller):
    """A cell left blank by a dropped frame has no image behind it."""
    map_model = load_map(map_controller)
    # the stored-pattern path only runs while the map mode is up, which is
    # exactly when a click can happen
    map_controller.activate()
    map_model.insert_blank(0)
    assert map_model.get_point_index(0, 0) is None

    click_map_cell(map_controller, 1, 1)  # a real point first
    loaded = map_controller.model.img_model.filename
    pattern = map_controller.model.pattern.y.copy()

    click_map_cell(map_controller, 0, 0)  # the blank

    assert map_controller.model.img_model.filename == loaded
    np.testing.assert_array_equal(map_controller.model.pattern.y, pattern)


def test_row_highlight_uses_each_windows_own_colour(map_controller):
    """Every window is drawn in its own colour in the pattern plot; the
    highlight in the table keeps that link instead of a single accent."""
    from dioptas.widgets.MapLayerWidget import ColorSwatch, RowTintDelegate

    map_model = load_map(map_controller)
    map_model.add_roi(window=(16.5, 18.0))
    widget = layer_widget(map_controller)

    delegate = widget.roi_table.itemDelegate()
    assert isinstance(delegate, RowTintDelegate)
    assert delegate._color_for_row(0).name() == map_model.rois[0].color
    assert delegate._color_for_row(1).name() == map_model.rois[1].color
    assert map_model.rois[0].color != map_model.rois[1].color

    # and the colour is on show in the row, not only in the pattern plot
    swatch = widget.roi_table.cellWidget(0, 1)
    assert isinstance(swatch, ColorSwatch)
    assert swatch.color().name() == map_model.rois[0].color


def test_window_colour_can_be_changed(map_controller):
    from dioptas.widgets.MapLayerWidget import ColorSwatch

    map_model = load_map(map_controller)
    widget = layer_widget(map_controller)

    widget.sigRoiChanged.emit("A", "color", "#ff00ff")
    assert map_model.rois[0].color == "#ff00ff"

    swatch = widget.roi_table.cellWidget(0, 1)
    assert isinstance(swatch, ColorSwatch)
    assert swatch.color().name() == "#ff00ff"
    assert widget.roi_table.itemDelegate()._color_for_row(0).name() == "#ff00ff"


def test_unchecking_reintegrate_uses_the_point_behind_the_selected_cell(map_controller):
    """The list rows are grid cells, so the selected row is not the point
    index once a blank has been inserted."""
    map_model = load_map(map_controller)
    map_controller.activate()
    map_model.insert_blank(0)

    slot = map_model.get_slot_of_point(2)
    map_controller.widget.control_widget.file_list.setCurrentRow(slot)

    reintegrate_cb = map_controller.widget.control_widget.reintegrate_cb
    reintegrate_cb.setChecked(True)
    reintegrate_cb.setChecked(False)

    np.testing.assert_array_equal(
        map_controller.model.pattern.y, map_model.pattern_intensities[2]
    )


def test_region_hover_keeps_the_windows_colour(map_controller):
    """pyqtgraph's hover brush and pens default to blue; a window turning
    blue under the mouse loses the link to its row."""
    map_model = load_map(map_controller)
    map_model.add_roi(window=(16.5, 18.0))
    map_model.rois[0].color = "#ff0000"
    map_model.rois[1].color = "#00ff00"

    roi_controller = map_controller.map_roi_controller
    active_item = map_controller.widget.pattern_plot_widget.map_interactive_roi
    extra_item = roi_controller._extra_items["B"]

    for item, expected in ((active_item, (255, 0, 0)), (extra_item, (0, 255, 0))):
        assert item.brush.color().getRgb()[:3] == expected
        hover = item.hoverBrush.color()
        assert hover.getRgb()[:3] == expected
        # same colour, just more of it
        assert hover.alpha() > item.brush.color().alpha()
        for line in item.lines:
            assert line.pen.color().getRgb()[:3] == expected
            assert line.hoverPen.color().getRgb()[:3] == expected


def test_show_radio_takes_the_windows_colour(map_controller):
    map_model = load_map(map_controller)
    map_model.rois[0].color = "#ff00ff"
    widget = layer_widget(map_controller)

    button = show_button(widget.roi_table, 0)
    assert "#ff00ff" in button.styleSheet()
    # and the cell holding it does not paint over the row's tint
    holder = widget.roi_table.cellWidget(0, 0)
    assert "transparent" in holder.styleSheet()


def test_point_action_buttons_follow_the_selected_cell(map_controller):
    """The icon buttons say what is possible here, since a glyph on its own
    does not explain itself."""
    map_model = load_map(map_controller)
    control = map_controller.widget.control_widget
    map_model.insert_blank(0)

    control.file_list.setCurrentRow(0)  # the blank
    assert control.insert_blank_btn.isEnabled()
    assert control.remove_blank_btn.isEnabled()
    assert not control.exclude_btn.isEnabled()

    control.file_list.setCurrentRow(1)  # a real point
    assert not control.remove_blank_btn.isEnabled()
    assert control.exclude_btn.isEnabled()


def test_exclude_button_shows_which_way_it_goes(map_controller):
    map_model = load_map(map_controller)
    control = map_controller.widget.control_widget
    control.file_list.setCurrentRow(0)

    assert "Leave point out" in control.exclude_btn.toolTip()
    map_model.set_point_excluded(0)
    map_controller.update_point_actions()

    # the row stayed selected in place and offers the way back
    assert control.file_list.currentRow() == 0
    assert "back into the map" in control.exclude_btn.toolTip()
    map_controller.toggle_point_excluded()
    assert not map_model.is_point_excluded(0)


def test_disabled_point_action_fades_rather_than_filling(map_controller):
    """The theme fills a disabled flat button, which made an unavailable
    action louder than an available one."""
    load_map(map_controller)
    button = map_controller.widget.control_widget.remove_blank_btn

    button.setEnabled(True)
    enabled_icon = button.icon().cacheKey()
    button.setEnabled(False)
    assert button.icon().cacheKey() != enabled_icon

    assert "background: transparent" in button.styleSheet()


def test_move_selected_cell_up_and_down(map_controller):
    map_model = load_map(map_controller)
    control = map_controller.widget.control_widget
    before = map_model.get_slots()[:4]

    control.file_list.setCurrentRow(2)
    control.move_up_btn.clicked.emit()

    slots = map_model.get_slots()
    assert slots[1] == before[2]
    assert slots[2] == before[1]
    # the selection follows the cell that moved
    assert control.file_list.currentRow() == 1

    control.move_down_btn.clicked.emit()
    assert map_model.get_slots()[:4] == before
    assert control.file_list.currentRow() == 2


def test_blanks_can_be_moved_too(map_controller):
    """A blank in the wrong place is exactly what needs nudging once the
    dropped frame is found."""
    map_model = load_map(map_controller)
    control = map_controller.widget.control_widget
    map_model.insert_blank(3)
    assert map_model.get_slots()[3] is None

    control.file_list.setCurrentRow(3)
    control.move_down_btn.clicked.emit()

    assert map_model.get_slots()[3] is not None
    assert map_model.get_slots()[4] is None
    assert control.file_list.currentRow() == 4


def test_move_buttons_stop_at_the_ends(map_controller):
    map_model = load_map(map_controller)
    control = map_controller.widget.control_widget

    control.file_list.setCurrentRow(0)
    assert not control.move_up_btn.isEnabled()
    assert control.move_down_btn.isEnabled()

    control.file_list.setCurrentRow(map_model.num_slots - 1)
    assert control.move_up_btn.isEnabled()
    assert not control.move_down_btn.isEnabled()


def test_transparent_backgrounds_are_qualified_by_object_name(map_controller):
    """An unqualified 'background: transparent' cascades to every descendant
    — it reached the value combo's drop-down list, which then had none. Only
    visible under the app's stylesheet, which the tests do not apply, so the
    guard is on the rule rather than on the pixels."""
    load_map(map_controller)
    holder = layer_widget(map_controller).roi_table.cellWidget(0, 0)
    assert holder.styleSheet().lstrip().startswith("#")

def test_image_returns_at_a_real_width_not_a_sliver(map_controller, qapp):
    """A widget inserted into a splitter arrives at its own size hint — for
    the image a few pixels — so leaving the tabs made it a vertical stripe."""
    widget = map_controller.widget
    widget.resize(1600, 900)
    widget.show()  # hidden widgets never lay out, so nothing would resize
    for _ in range(10):  # let the resize reach the nested splitters
        qapp.processEvents()

    widget._set_image_tabbed(True)
    widget._set_image_tabbed(False)
    for _ in range(10):  # the split is applied once geometry has settled
        qapp.processEvents()

    sizes = widget.upper_right_splitter.sizes()
    assert sizes[0] >= widget._IMAGE_PANE_MIN_WIDTH


def test_image_returns_at_the_share_the_user_had(map_controller, qapp):
    widget = map_controller.widget
    widget.resize(1600, 900)
    widget.show()  # hidden widgets never lay out, so nothing would resize
    for _ in range(10):
        qapp.processEvents()

    widget.upper_right_splitter.setSizes([700, 500])
    widget._remember_wide_share()  # a real drag emits splitterMoved

    widget._set_image_tabbed(True)
    widget._set_image_tabbed(False)
    for _ in range(10):
        qapp.processEvents()

    sizes = widget.upper_right_splitter.sizes()
    share = sizes[0] / sum(sizes)
    assert share == pytest.approx(700 / 1200, abs=0.05)


def test_squeezed_sizes_at_flip_time_do_not_overwrite_the_share(map_controller):
    """While the window shrinks, the image is squeezed against the controls'
    minimum before the flip happens — those sizes say nothing about the
    split the user chose and must not replace it."""
    widget = map_controller.widget
    widget._wide_image_share = 0.6

    widget._set_image_tabbed(True)  # sizes at this moment are the squeezed ones
    assert widget._wide_image_share == 0.6
    widget._remember_wide_share()  # tabbed: a stray call must change nothing
    assert widget._wide_image_share == 0.6


def test_help_buttons_open_a_non_modal_reference(map_controller, qapp):
    """Modal help would freeze the application (and hang the test suite);
    the text is a reference meant to stay open while editing."""
    widget = layer_widget(map_controller)

    widget.roi_help_btn.clicked.emit()
    qapp.processEvents()
    dialog = widget._help_dialog
    assert dialog is not None and dialog.isVisible()
    assert not dialog.isModal()
    text = dialog.findChild(QtWidgets.QTextBrowser).toPlainText()
    assert "Nothing is fitted" in text
    assert "centre of mass" in text

    widget.expression_help_btn.clicked.emit()
    qapp.processEvents()
    assert widget._help_dialog is not dialog  # replaced, not stacked
    text = widget._help_dialog.findChild(QtWidgets.QTextBrowser).toPlainText()
    assert "(A-B)/(A+B)" in text
    widget._help_dialog.close()


def test_table_buttons_sit_beside_the_tables(map_controller, qapp):
    """Same arrangement as the phase and overlay lists: the actions in a
    column at the side, not underneath."""
    map_widget = map_controller.widget
    map_widget.resize(1600, 900)
    map_widget.show()  # hidden widgets never lay out
    map_widget.control_widget.tab_widget.setCurrentWidget(
        map_widget.control_widget.layer_widget
    )
    for _ in range(10):
        qapp.processEvents()
    widget = layer_widget(map_controller)
    for table, button in (
        (widget.roi_table, widget.add_roi_btn),
        (widget.expression_table, widget.add_expression_btn),
        (widget.roi_table, widget.roi_help_btn),
        (widget.expression_table, widget.expression_help_btn),
    ):
        assert button.parentWidget() is table.parentWidget()
        assert button.x() >= table.x() + table.width()


def test_negative_valued_layers_still_display(map_controller):
    """The histogram LUT works in log space and clamps levels <= 0 to 1;
    an all-negative layer — (A-B)/(A+B) with B stronger — showed as an
    empty map."""
    map_model = load_map(map_controller)
    map_model.add_roi(window=(16.5, 18.0))
    map_model.set_expression("c", "(A-B)/(A+B)")
    map_model.active_layer = "c"

    values = map_model.layer_values("c")
    assert np.all(values < 0)  # the case that used to blank out

    levels = map_controller.widget.map_plot_widget.data_img_item.getLevels()
    assert levels[0] < 0
    assert levels[0] < levels[1]


def test_an_expression_that_overflows_everywhere_says_so(map_controller):
    """A**B of two window sums is inf at every point; the map went blank
    with no explanation."""
    map_model = load_map(map_controller)
    map_model.add_roi(window=(16.5, 18.0))
    widget = layer_widget(map_controller)

    widget.sigExpressionChanged.emit("p", "A**B")
    assert "no finite values" in widget.message_lbl.text()

    widget.sigExpressionChanged.emit("p", "A/B")
    assert widget.message_lbl.text() == ""


def test_ovl_expression_uses_a_real_overlay(map_controller):
    map_model = load_map(map_controller)
    overlay_model = map_controller.model.overlay_model
    overlay_model.add_overlay(
        map_model.pattern_x.copy(), np.ones_like(map_model.pattern_x), "bkg_empty"
    )
    widget = layer_widget(map_controller)

    widget.sigExpressionChanged.emit("d", "A - ovl(bkg_empty)")
    assert widget.message_lbl.text() == ""
    values = map_model.layer_values("d")
    assert values is not None and np.all(np.isfinite(values))
    # and it is genuinely the difference to the overlay
    offset = map_model.overlay_window_value("bkg_empty", "A")
    np.testing.assert_allclose(values, map_model.layer_values("A") - offset)


def test_unknown_or_removed_overlay_is_reported(map_controller):
    map_model = load_map(map_controller)
    overlay_model = map_controller.model.overlay_model
    widget = layer_widget(map_controller)

    widget.sigExpressionChanged.emit("d", "A - ovl(bkg_empty)")
    assert "no overlay called 'bkg_empty'" in widget.message_lbl.text()

    overlay_model.add_overlay(
        map_model.pattern_x.copy(), np.ones_like(map_model.pattern_x), "bkg_empty"
    )
    widget.sigExpressionChanged.emit("d", "A - ovl(bkg_empty)")
    assert widget.message_lbl.text() == ""

    overlay_model.remove_overlay(0)
    assert map_model.layer_values("d") is None
    assert "no overlay called 'bkg_empty'" in widget.message_lbl.text()

def test_remove_blank_button_disabled_for_structural_blanks(map_controller):
    """The grid needs its cells: a trailing blank cannot be deleted, and the
    button saying otherwise was a false promise."""
    map_model = load_map(map_controller)
    control = map_controller.widget.control_widget
    map_model.set_dimension((3, 3))  # trailing blanks appear

    control.file_list.setCurrentRow(7)  # a structural blank
    assert not control.remove_blank_btn.isEnabled()

    map_model.insert_blank(1)  # a repair blank, points after it
    control.file_list.setCurrentRow(1)
    assert control.remove_blank_btn.isEnabled()


def test_help_reopens_after_the_user_closed_it(map_controller, qapp):
    """The dialog deletes itself on close; reopening then called close() on
    the dead wrapper and raised through the excepthook."""
    widget = layer_widget(map_controller)

    widget.roi_help_btn.clicked.emit()
    widget._help_dialog.close()  # what the user's window-close does
    for _ in range(5):  # delete-on-close finishes in the event loop
        qapp.processEvents()

    widget.roi_help_btn.clicked.emit()  # used to raise RuntimeError
    assert widget._help_dialog is not None and widget._help_dialog.isVisible()

    # and again for the other help, closing via the same path
    widget._help_dialog.close()
    for _ in range(5):
        qapp.processEvents()
    widget.expression_help_btn.clicked.emit()
    assert widget._help_dialog is not None and widget._help_dialog.isVisible()
    widget._help_dialog.close()


def test_clicking_a_blank_map_cell_selects_its_row(map_controller):
    """A blank cell has no image, but it has a row — where the actions that
    can do something with it (remove the blank, move it) live."""
    map_model = load_map(map_controller)
    map_controller.activate()
    map_model.insert_blank(4)
    assert map_model.get_point_index(1, 1) is None

    click_map_cell(map_controller, 1, 1)

    control = map_controller.widget.control_widget
    assert control.file_list.currentRow() == 4
    assert control.remove_blank_btn.isEnabled()

    # and with transforms on, the traced slot follows the layout
    map_model.snake = True
    row, col = next(
        (r, c)
        for r in range(map_model.map.shape[0])
        for c in range(map_model.map.shape[1])
        if map_model.get_point_index(r, c) is None
        and map_model.get_slot_at(r, c) == 4
    )
    click_map_cell(map_controller, row, col)
    assert control.file_list.currentRow() == 4


def test_blank_click_translation_skips_excluded_rows(map_controller):
    """The map closes up over excluded points while the list keeps them, so
    a clicked blank cell has to be traced past the excluded rows."""
    map_model = load_map(map_controller)
    map_controller.activate()
    map_model.insert_blank(4)          # blank at row 4
    map_model.set_point_excluded(0)    # row 0 excluded, map shifts by one

    # the blank now sits one cell earlier in the map than its row says
    row, col = next(
        (r, c)
        for r in range(map_model.map.shape[0])
        for c in range(map_model.map.shape[1])
        if map_model.get_point_index(r, c) is None
        and map_model.get_row_of_visible_slot(map_model.get_slot_at(r, c)) == 4
    )
    click_map_cell(map_controller, row, col)
    assert map_controller.widget.control_widget.file_list.currentRow() == 4


def test_saving_an_all_blank_map_as_tiff_does_not_crash(
    map_controller, tmp_path
):
    """A layer can be NaN everywhere (window outside the pattern, an
    overflowing expression); saving it must still produce a file."""
    map_model = load_map(map_controller)
    map_model.set_window((100.0, 200.0))  # outside the pattern
    assert np.all(np.isnan(map_model.map))

    filename = str(tmp_path / "blank_map.tiff")
    map_controller.panel_controller.save_map(filename)
    assert os.path.exists(filename)


def test_expression_taking_a_window_name_is_refused_with_a_message(
    map_controller,
):
    map_model = load_map(map_controller)
    widget = layer_widget(map_controller)

    widget.sigExpressionChanged.emit("A", "A*2")
    assert "already a window" in widget.message_lbl.text()
    assert "A" not in map_model.expressions


# ---------------------------------------------------------------- live maps


def _copy_scan_files(tmp_path, count, start=1):
    """Numbered copies of a real Pilatus image, as a beamline would write."""
    import shutil

    paths = []
    for number in range(start, start + count):
        destination = tmp_path / f"scan_{number:03d}.tif"
        shutil.copy(map_img_file_paths[0], destination)
        paths.append(str(destination))
    return paths


def test_live_needs_a_loaded_map(map_controller: MapController):
    QtWidgets.QMessageBox.information = MagicMock()
    live_btn = map_controller.panel_controller.widget.map_plot_control_widget.live_btn

    live_btn.setChecked(True)

    assert not live_btn.isChecked(), "no map to append to, so live turns off"
    QtWidgets.QMessageBox.information.assert_called_once()


def test_live_appends_files_as_they_appear(
    map_controller: MapController, tmp_path
):
    load_calibration(map_controller)
    panel = map_controller.panel_controller
    map_model = panel.model.map_model
    map_model.load(_copy_scan_files(tmp_path, 4))
    live_btn = panel.widget.map_plot_control_widget.live_btn

    live_btn.setChecked(True)
    try:
        assert live_btn.isChecked()

        (new_path,) = _copy_scan_files(tmp_path, 1, start=5)
        panel._live_file_appeared(new_path)  # what the watcher does
        panel._drain_live_queue()

        assert len(map_model.point_infos) == 5
        assert map_model.filepaths[-1] == new_path
        # the newest point is followed: its image is on screen
        assert panel.model.img_model.filename == new_path
    finally:
        live_btn.setChecked(False)
    assert not panel._live_timer.isActive()


def test_live_catches_up_on_files_written_since_the_map_was_loaded(
    map_controller: MapController, tmp_path
):
    """Frames the beamline wrote between Load and pressing Live are not
    lost — numbered continuations of the loaded files are picked up."""
    load_calibration(map_controller)
    panel = map_controller.panel_controller
    map_model = panel.model.map_model
    map_model.load(_copy_scan_files(tmp_path, 4))

    _copy_scan_files(tmp_path, 2, start=5)  # written "during" the toggle
    live_btn = panel.widget.map_plot_control_widget.live_btn
    live_btn.setChecked(True)
    try:
        panel._drain_live_queue()
        assert len(map_model.point_infos) == 6
        assert [os.path.basename(p) for p in map_model.filepaths[-2:]] == [
            "scan_005.tif",
            "scan_006.tif",
        ]
    finally:
        live_btn.setChecked(False)


def test_loading_a_new_map_stops_live(map_controller: MapController, tmp_path):
    load_calibration(map_controller)
    panel = map_controller.panel_controller
    panel.model.map_model.load(_copy_scan_files(tmp_path, 4))
    live_btn = panel.widget.map_plot_control_widget.live_btn
    live_btn.setChecked(True)

    mock_open_filenames([])  # user cancels the dialog; live is off regardless
    panel.load_map()

    assert not live_btn.isChecked()
    assert not panel._live_timer.isActive()


def test_switching_the_configuration_stops_live(
    map_controller: MapController, tmp_path
):
    load_calibration(map_controller)
    panel = map_controller.panel_controller
    panel.model.map_model.load(_copy_scan_files(tmp_path, 4))
    live_btn = panel.widget.map_plot_control_widget.live_btn
    live_btn.setChecked(True)

    panel.model.add_configuration()

    assert not live_btn.isChecked()


def test_live_without_the_batch_engine_takes_small_bites(
    map_controller: MapController, tmp_path
):
    """Every file costs a full pyFAI pass on the GUI thread when dioptrin is
    not available, so one tick appends a few files and leaves the rest
    queued for the next — the interface stays usable during a catch-up."""
    load_calibration(map_controller)
    panel = map_controller.panel_controller
    map_model = panel.model.map_model
    map_model.load(_copy_scan_files(tmp_path, 2))
    assert not map_model.configuration.calibration_model.can_use_dioptrin_batch(
        map_model.configuration.integration_unit,
        map_model.configuration.oned_azimuth_range,
    )

    _copy_scan_files(tmp_path, 7, start=3)
    live_btn = panel.widget.map_plot_control_widget.live_btn
    live_btn.setChecked(True)  # catch-up queues the 7 numbered files
    try:
        panel._drain_live_queue()
        assert len(map_model.point_infos) == 2 + panel._LIVE_SINGLE_LIMIT
        panel._drain_live_queue()
        assert len(map_model.point_infos) == 9, "the rest follows next tick"
    finally:
        live_btn.setChecked(False)


def test_live_ignores_files_that_are_not_part_of_the_scan(
    map_controller: MapController, tmp_path
):
    """The watcher matches on extension alone; a file from another scan (or
    a calibration image) in the same folder must not enter the map."""
    import shutil

    load_calibration(map_controller)
    panel = map_controller.panel_controller
    map_model = panel.model.map_model
    map_model.load(_copy_scan_files(tmp_path, 4))

    intruder = tmp_path / "LaB6_calibration_999.tif"
    shutil.copy(map_img_file_paths[0], intruder)

    live_btn = panel.widget.map_plot_control_widget.live_btn
    live_btn.setChecked(True)
    try:
        # catch-up must not have queued it, despite its high number
        panel._drain_live_queue()
        assert len(map_model.point_infos) == 4

        # nor does it get in when announced by the watcher
        panel._live_file_appeared(str(intruder))
        (scan_file,) = _copy_scan_files(tmp_path, 1, start=5)
        panel._live_file_appeared(scan_file)
        panel._drain_live_queue()

        assert len(map_model.point_infos) == 5
        assert map_model.filepaths[-1] == scan_file
    finally:
        live_btn.setChecked(False)


def test_the_scan_name_prefix_is_not_locked_to_shared_leading_digits():
    """Loading scan_11..13 must not shut out scan_20."""
    from dioptas.controller.MapPanelController import MapPanelController

    prefix = MapPanelController._name_prefix(
        ["/data/scan_11.tif", "/data/scan_12.tif", "/data/scan_13.tif"]
    )
    assert prefix == "scan_"
    assert MapPanelController._name_prefix(["/data/scan_005.tif"]) == "scan_"
