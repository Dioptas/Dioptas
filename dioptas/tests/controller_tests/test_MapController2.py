import os
import pytest
from qtpy import QtWidgets
from mock import MagicMock

from dioptas.model.MapModel2 import MapModel2


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
def map_controller(main_controller):
    return main_controller.map_controller


@pytest.fixture
def map_model(map_controller):
    return map_controller.model.map_model

 
def mock_open_filenames(filepaths):
    QtWidgets.QFileDialog.getOpenFileNames = MagicMock(return_value=filepaths)


def test_click_load_starts_creating_map(map_controller, map_model: MapModel2):
    map_model.create_map = MagicMock()
    mock_open_filenames(map_img_file_paths)
    map_controller.load_btn_clicked()
    map_model.create_map.assert_called_once_with(map_img_file_paths)


def test_click_load_fills_file_list(map_controller, map_model: MapModel2):
    mock_open_filenames(map_img_file_paths)
    map_controller.load_btn_clicked()

    assert map_model.filenames == map_img_file_paths
    assert map_controller.widget.control_widget.file_list.count() == len(
        map_img_file_paths
    )


def test_loading_files_plots_map(map_controller, map_model: MapModel2):
    mock_open_filenames(map_img_file_paths)
    map_controller.load_btn_clicked()

    assert map_model.map is not None
    assert map_controller.widget.map_widget.map is not None


def test_click_load_shows_error_if_not_calibrated(map_controller):
    mock_open_filenames(map_img_file_paths)
    assert map_controller.model.configuration.is_calibrated == False
    map_controller.load_btn_clicked()
    map_widget = map_controller.widget
    # TODO: decide what kind of error message and how to guide the user here
