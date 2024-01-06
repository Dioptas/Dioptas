import os
import pytest
from qtpy import QtWidgets, QtCore
from qtpy.QtTest import QTest

from mock import MagicMock
from dioptas.controller.MapController import MapController
from dioptas.model.DioptasModel import DioptasModel

from dioptas.model.MapModel2 import MapModel2
from dioptas.widgets.MapWidget import MapWidget


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
def map_controller(qapp):
    """Fixture providing a MainController instance"""
    widget = MapWidget()
    model = DioptasModel()
    controller = MapController(widget, model)
    # controller.show_window()
    controller.widget.setAttribute(QtCore.Qt.WA_DeleteOnClose)
    QTest.qWaitForWindowExposed(controller.widget)
    # controller.widget.activateWindow()
    # controller.widget.raise_()
    try:
        yield controller
    finally:
        controller.widget.close()


@pytest.fixture
def map_model(map_controller):
    return map_controller.model.map_model


def load_calibration(map_controller: MapController):
    map_controller.model.current_configuration.calibration_model.load(
        os.path.join(data_path, "CeO2_Pilatus1M.poni")
    )


def mock_open_filenames(filepaths):
    QtWidgets.QFileDialog.getOpenFileNames = MagicMock(return_value=filepaths)


def test_click_load_starts_creating_map(map_controller, map_model: MapModel2):
    map_model.load = MagicMock()
    mock_open_filenames(map_img_file_paths)
    map_controller.load_btn_clicked()
    map_model.load.assert_called_once_with(map_img_file_paths)


def test_click_load_fills_file_list_without_calibration(map_controller, map_model: MapModel2):
    mock_open_filenames(map_img_file_paths)
    map_controller.load_btn_clicked()

    assert map_model.filenames == map_img_file_paths
    assert map_controller.widget.control_widget.file_list.count() == len(
        map_img_file_paths
    )

def test_click_load_fills_file_list(map_controller, map_model: MapModel2):
    load_calibration(map_controller)
    assert map_controller.model.current_configuration.is_calibrated == True
    mock_open_filenames(map_img_file_paths)
    map_controller.load_btn_clicked()

    assert map_model.filenames == map_img_file_paths
    assert map_controller.widget.control_widget.file_list.count() == len(
        map_img_file_paths
    )
    assert map_controller.widget.control_widget.file_list.currentRow() == 0


def test_loading_files_plots_map(map_controller: MapController, map_model: MapModel2):
    load_calibration(map_controller)
    assert map_controller.model.current_configuration.is_calibrated == True
    assert map_controller.widget.map_plot_widget.img_data is None

    mock_open_filenames(map_img_file_paths)
    map_controller.load_btn_clicked()

    plot_widget = map_controller.widget.map_plot_widget

    assert map_model.map is not None
    assert plot_widget.img_data is not None
    assert plot_widget.img_data.shape == map_model.map.shape
    assert plot_widget.data_img_item.image is not None



def test_click_load_shows_error_if_not_calibrated(map_controller):
    mock_open_filenames(map_img_file_paths)
    assert map_controller.model.current_configuration.is_calibrated == False
    map_controller.load_btn_clicked()
    map_widget = map_controller.widget
    # TODO: decide what kind of error message and how to guide the user here
