import os
import numpy as np
import pytest
from pytest import approx
from qtpy import QtWidgets, QtCore
from qtpy.QtTest import QTest

from mock import MagicMock
from dioptas.controller.MapController import MapController
from dioptas.model.DioptasModel import DioptasModel

from dioptas.model.MapModel2 import MapModel2, MapPointInfo, create_map
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
def map_model(map_controller) -> MapModel2:
    return map_controller.model.map_model


def load_calibration(map_controller: MapController):
    map_controller.model.current_configuration.calibration_model.load(
        os.path.join(data_path, "CeO2_Pilatus1M.poni")
    )


def mock_open_filenames(filepaths):
    QtWidgets.QFileDialog.getOpenFileNames = MagicMock(return_value=filepaths)


def mock_map_model(map_model: MapModel2):
    map_model.map = create_map(np.array([1, 2, 3, 4, 5, 6]), (2, 3))
    map_model.filepaths = map_img_file_paths
    map_model.possible_dimensions = [(1, 6), (2, 3), (3, 2), (6, 1)]
    map_model.point_infos = [MapPointInfo(f) for f in map_img_file_paths]
    map_model.dimension = (2, 3)
    map_model.map_changed.emit()


def mock_integrate_1d(map_controller: MapController):
    map_controller.model.calibration_model.integrate_1d = MagicMock(
        return_value=(np.arange(10), np.arange(10))
    )


def test_click_load_starts_creating_map(map_controller, map_model: MapModel2):
    map_model.load = MagicMock()
    mock_open_filenames(map_img_file_paths)
    mock_integrate_1d(map_controller)
    map_controller.load_btn_clicked()
    map_model.load.assert_called_once_with(map_img_file_paths)


def test_click_load_empties_file_list_without_calibration(
    map_controller, map_model: MapModel2
):
    mock_open_filenames(map_img_file_paths)
    QtWidgets.QMessageBox.critical = MagicMock()
    map_controller.load_btn_clicked()

    assert map_controller.widget.control_widget.file_list.count() == 0
    assert QtWidgets.QMessageBox.critical.assert_called_once


def test_load_empty_filelist(map_controller, map_model: MapModel2):
    mock_open_filenames([])
    map_controller.load_btn_clicked()

    assert map_controller.widget.control_widget.file_list.count() == 0


def test_files_with_different_dimensions(map_controller, map_model: MapModel2):
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


def test_click_load_fills_file_list(map_controller, map_model: MapModel2):
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


def test_loading_files_plots_map(map_controller: MapController, map_model: MapModel2):
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
    map_controller: MapController, map_model: MapModel2
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

    click_x, click_y = map_controller.widget.map_plot_widget.mouse_click_item.getData()
    assert click_x[0] == approx(0)
    assert click_y[0] == approx(0)

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
    map_model.map = create_map(map_model.window_intensities, (2, 3))
    map_model.possible_dimensions = [(1, 6), (2, 3), (3, 2), (6, 1)]
    map_model.dimension = (2, 3)
    map_model.map_changed.emit()

    dim_cb = map_controller.widget.map_plot_control_widget.map_dimension_cb
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

    assert QtWidgets.QProgressDialog.setValue.call_count == len(map_img_file_paths)


def test_phase_is_displayed(map_controller, dioptas_model):
    load_calibration(map_controller)
    mock_integrate_1d(map_controller)
    mock_open_filenames(map_img_file_paths)
    map_controller.load_btn_clicked()

    pattern_widget = map_controller.widget.pattern_plot_widget

    assert pattern_widget.phases == []

    dioptas_model.phase_model.add_jcpds(os.path.join(data_path, "jcpds", "ar.jcpds"))
    assert len(pattern_widget.phases) == 1


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
