import pytest
import os

from dioptas.model.Configuration import Configuration
from dioptas.model.MapModel2 import MapModel2
from dioptas.tests.utility import unittest_data_path
import numpy as np

jcpds_path = os.path.join(unittest_data_path, 'jcpds')
map_img_path = os.path.join(unittest_data_path, 'map')
map_pattern_path = os.path.join(unittest_data_path, 'map', 'xy')
map_img_file_names = [f for f in os.listdir(map_img_path) if os.path.isfile(os.path.join(map_img_path, f))]
map_img_file_paths = [os.path.join(map_img_path, filename) for filename in map_img_file_names]

multi_file_img_path = os.path.join(unittest_data_path, 'lambda', 'testasapo1_1009_00002_m1_part00000.nxs')


@pytest.fixture
def configuration() -> Configuration:
    return Configuration()


@pytest.fixture
def map_model(configuration: Configuration) -> MapModel2:
    return MapModel2(configuration)


def test_create_map(map_model: MapModel2, configuration: Configuration):
    configuration.calibration_model.load(os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni"))
    map_model.load(map_img_file_paths)
    assert map_model.filepaths == map_img_file_paths
    assert len(map_model.pattern_intensities) == len(map_img_file_paths)
    assert map_model.dimension == (3, 3)
    assert map_model.map.shape == (3, 3)


def test_set_dimensions(map_model: MapModel2, configuration: Configuration):
    configuration.calibration_model.load(os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni"))
    map_model.load(map_img_file_paths[:6])
    assert len(map_model.pattern_intensities) == 6
    assert map_model.dimension == (2, 3)
    assert map_model.map.shape == (2, 3)

    map_model.set_dimension((3, 2))
    assert map_model.dimension == (3, 2)
    assert map_model.map.shape == (3, 2)

    map_model.set_dimension((1, 6))
    assert map_model.dimension == (1, 6)
    assert map_model.map.shape == (1, 6)


def test_set_wrong_dimensions(map_model: MapModel2, configuration: Configuration):
    configuration.calibration_model.load(os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni"))
    map_model.load(map_img_file_paths[:6])
    assert len(map_model.pattern_intensities) == 6
    assert map_model.dimension == (2, 3)
    assert map_model.map.shape == (2, 3)

    map_model.set_dimension((3, 3))
    assert map_model.dimension == (2, 3)
    assert map_model.map.shape == (2, 3)


def test_set_different_window(map_model: MapModel2, configuration: Configuration):
    configuration.calibration_model.load(os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni"))
    map_model.load(map_img_file_paths[:6])

    map_model.set_window((15, 16))
    assert map_model.window_intensities.all() > 0

    map_model.set_window((35, 40))  # window outside of pattern range
    assert map_model.window_intensities.all() == 0


def test_get_point_information(map_model: MapModel2, configuration: Configuration):
    configuration.calibration_model.load(os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni"))
    map_model.load(map_img_file_paths[:6])

    assert map_model.dimension == (2, 3)
    for i in range(6):
        column_index = i % 3
        row_index = i // 3
        point_info = map_model.get_point_info(row_index, column_index)
        assert point_info.filename == map_img_file_names[i]


def test_use_multi_file_img(map_model: MapModel2, configuration: Configuration):
    configuration.calibration_model.load(os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni"))
    map_model.load([multi_file_img_path])

    img_model = configuration.img_model

    assert map_model.filepaths == [multi_file_img_path]
    assert img_model.series_max == 10
    assert map_model.pattern_intensities.shape[0] == 10
