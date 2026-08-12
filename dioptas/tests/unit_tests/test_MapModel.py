from unittest.mock import MagicMock, patch
import tempfile
import pytest
import os

import h5py

from dioptas.model.Configuration import Configuration
from dioptas.model.MapModel import MapModel
from dioptas.model.util.integration import iter_frames_sequential
from dioptas.tests.utility import unittest_data_path
import numpy as np

jcpds_path = os.path.join(unittest_data_path, "jcpds")
map_img_path = os.path.join(unittest_data_path, "map")
map_pattern_path = os.path.join(unittest_data_path, "map", "xy")
map_img_file_names = [
    f for f in os.listdir(map_img_path) if os.path.isfile(os.path.join(map_img_path, f))
]
map_img_file_paths = [
    os.path.join(map_img_path, filename) for filename in map_img_file_names
]

multi_file_img_path = os.path.join(
    unittest_data_path, "lambda", "testasapo1_1009_00002_m1_part00000.nxs"
)


@pytest.fixture
def configuration() -> Configuration:
    return Configuration()


@pytest.fixture
def map_model(configuration: Configuration) -> MapModel:
    return MapModel(configuration)


def test_create_map(map_model: MapModel, configuration: Configuration):
    configuration.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    map_model.load(map_img_file_paths)
    assert map_model.filepaths == map_img_file_paths
    assert len(map_model.pattern_intensities) == len(map_img_file_paths)
    assert map_model.dimension == (3, 3)
    assert map_model.map.shape == (3, 3)


def test_load_empty_filelist(map_model: MapModel, configuration: Configuration):
    with pytest.raises(ValueError):
        map_model.load([])


def test_load_files_with_different_dimensions(
    map_model: MapModel, configuration: Configuration
):
    file_paths = [
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.tif"),
        os.path.join(unittest_data_path, "image_001.tif"),
    ]
    configuration.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    with pytest.raises(ValueError):
        map_model.load(file_paths)
    
    assert map_model.filepaths is None
    assert map_model.pattern_intensities is None
    assert map_model.dimension is None
    assert configuration.img_model.img_changed.blocked is False
    assert configuration.trim_trailing_zeros is True


def test_set_dimensions(map_model: MapModel, configuration: Configuration):
    configuration.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
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


def test_set_too_small_dimension_is_rejected(
    map_model: MapModel, configuration: Configuration
):
    configuration.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    map_model.load(map_img_file_paths[:6])
    assert len(map_model.pattern_intensities) == 6
    assert map_model.dimension == (2, 3)
    assert map_model.map.shape == (2, 3)

    map_model.set_dimension((2, 2))  # no room for all six points
    assert map_model.dimension == (2, 3)
    assert map_model.map.shape == (2, 3)


def test_set_oversized_dimension_leaves_blanks(
    map_model: MapModel, configuration: Configuration
):
    """A grid larger than the point count is allowed — that is what a scan
    with dropped frames needs."""
    configuration.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    map_model.load(map_img_file_paths[:6])

    map_model.set_dimension((3, 3))
    assert map_model.dimension == (3, 3)
    assert map_model.map.shape == (3, 3)
    # the six points fill the grid in order, the last three cells stay blank
    assert np.count_nonzero(np.isnan(map_model.map)) == 3
    assert map_model.get_point_index(0, 0) == 0
    assert map_model.get_point_index(2, 2) is None


def test_set_different_window(map_model: MapModel, configuration: Configuration):
    configuration.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    map_model.load(map_img_file_paths[:6])

    map_model.set_window((15, 16))
    assert np.all(map_model.window_intensities > 0)

    # a window outside the pattern range holds no data to reduce, which is
    # not the same as a measured zero — those points read blank
    map_model.set_window((35, 40))
    assert np.all(np.isnan(map_model.window_intensities))
    assert np.all(np.isnan(map_model.map))


def test_get_point_information(map_model: MapModel, configuration: Configuration):
    configuration.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    map_model.load(map_img_file_paths[:6])

    assert map_model.dimension == (2, 3)
    for i in range(6):
        column_index = i % 3
        row_index = i // 3
        point_info = map_model.get_point_info(row_index, column_index)
        assert point_info.filename == map_img_file_names[i]


def test_use_multi_file_img(map_model: MapModel, configuration: Configuration):
    configuration.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    map_model.load([multi_file_img_path])

    img_model = configuration.img_model

    assert map_model.filepaths == [multi_file_img_path]
    assert img_model.series_max == 10
    assert map_model.pattern_intensities.shape[0] == 10


def test_integrates_each_image_only_once(
    map_model: MapModel, configuration: Configuration
):
    configuration.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    x = np.linspace(0, 10, 100)
    y = np.sin(x)
    configuration.calibration_model.integrate_1d = MagicMock(return_value=(x, y))
    configuration.calibration_model.can_use_dioptrin_batch = MagicMock(return_value=False)
    map_model.load(map_img_file_paths)

    assert configuration.calibration_model.integrate_1d.call_count == len(
        map_img_file_paths
    )


def test_emits_point_integrated_signal(
    map_model: MapModel, configuration: Configuration
):
    configuration.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    # mock the integrate_1d method
    x = np.linspace(0, 10, 100)
    y = np.sin(x)
    configuration.calibration_model.integrate_1d = MagicMock(return_value=(x, y))

    listener = MagicMock()
    map_model.point_integrated.connect(listener)

    map_model.load(map_img_file_paths)
    assert listener.call_count == 9
    # assert listener.call_args_list == [(1), (2), (3), (4), (5), (6), (7), (8), (9)]


def test_emits_point_integrated_signal_with_multiimage_file(
    map_model: MapModel, configuration: Configuration
):
    configuration.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    # mock the integrate_1d method
    x = np.linspace(0, 10, 100)
    y = np.sin(x)
    configuration.calibration_model.integrate_1d = MagicMock(return_value=(x, y))

    listener = MagicMock()
    map_model.point_integrated.connect(listener)

    map_model.load([multi_file_img_path])
    assert listener.call_count == 10


def test_iter_frames_sequential_bitshuffle_shape_mismatch(configuration: Configuration):
    """Bitshuffle HDF5 path in iter_frames_sequential must reject shape mismatches."""
    img_model = configuration.img_model

    expected_shape = (2048, 2048)
    wrong_shape = (3262, 3108)

    mock_loader = MagicMock()
    mock_loader.gen_frames.return_value = iter([np.zeros(wrong_shape)])

    with patch(
        "dioptas.model.util.integration.try_open_bitshuffle_hdf5",
        return_value=mock_loader,
    ):
        gen = iter_frames_sequential(
            img_model,
            ["/fake/file.h5"],
            img_shape=expected_shape,
        )
        with pytest.raises(ValueError, match="expected"):
            next(gen)


def test_save_load_hdf5_round_trip(map_model: MapModel, configuration: Configuration):
    """Map state survives a save/load round-trip through HDF5."""
    configuration.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    map_model.load(map_img_file_paths)

    # tweak window and dimension so we verify they are restored
    map_model.set_window((15, 20))
    map_model.set_dimension((3, 3))

    with tempfile.NamedTemporaryFile(suffix=".h5", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        # save
        with h5py.File(tmp_path, "w") as f:
            map_model.save_in_hdf5(f)

        # load into a fresh model
        new_model = MapModel(configuration)
        with h5py.File(tmp_path, "r") as f:
            new_model.load_from_hdf5(f)

        np.testing.assert_array_equal(new_model.pattern_x, map_model.pattern_x)
        np.testing.assert_array_equal(
            new_model.pattern_intensities, map_model.pattern_intensities
        )
        assert new_model.filepaths == map_model.filepaths
        assert len(new_model.point_infos) == len(map_model.point_infos)
        for a, b in zip(new_model.point_infos, map_model.point_infos):
            assert a.filepath == b.filepath
            assert a.frame_index == b.frame_index
        assert new_model.window == pytest.approx(map_model.window)
        assert new_model.dimension == map_model.dimension
        np.testing.assert_array_equal(new_model.map, map_model.map)
    finally:
        os.unlink(tmp_path)


def test_pattern_unit_is_stored_on_integration(
    map_model: MapModel, configuration: Configuration
):
    """The unit pattern_x is expressed in is recorded with the map data."""
    configuration.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    configuration.integration_unit = "q_A^-1"
    map_model.load(map_img_file_paths)

    assert map_model.pattern_unit == "q_A^-1"

    # switching the display unit afterwards must not change the stored data
    configuration.integration_unit = "2th_deg"
    assert map_model.pattern_unit == "q_A^-1"


def test_pattern_unit_round_trips_through_hdf5(
    map_model: MapModel, configuration: Configuration
):
    configuration.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    configuration.integration_unit = "q_A^-1"
    map_model.load(map_img_file_paths)

    with tempfile.NamedTemporaryFile(suffix=".h5", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        with h5py.File(tmp_path, "w") as f:
            map_model.save_in_hdf5(f)

        # a different current unit must not overwrite the stored one
        configuration.integration_unit = "2th_deg"
        new_model = MapModel(configuration)
        with h5py.File(tmp_path, "r") as f:
            new_model.load_from_hdf5(f)

        assert new_model.pattern_unit == "q_A^-1"
    finally:
        os.unlink(tmp_path)


def test_pattern_unit_falls_back_for_legacy_files(
    map_model: MapModel, configuration: Configuration
):
    """Project files written before the unit was stored use the current unit."""
    configuration.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    map_model.load(map_img_file_paths)

    with tempfile.NamedTemporaryFile(suffix=".h5", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        with h5py.File(tmp_path, "w") as f:
            map_model.save_in_hdf5(f)
            del f["map"].attrs["pattern_unit"]

        configuration.integration_unit = "d_A"
        new_model = MapModel(configuration)
        with h5py.File(tmp_path, "r") as f:
            new_model.load_from_hdf5(f)

        assert new_model.pattern_unit == "d_A"
    finally:
        os.unlink(tmp_path)


def test_pattern_unit_is_cleared_on_failed_integration(
    map_model: MapModel, configuration: Configuration
):
    file_paths = [
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.tif"),
        os.path.join(unittest_data_path, "image_001.tif"),
    ]
    configuration.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    with pytest.raises(ValueError):
        map_model.load(file_paths)

    assert map_model.pattern_unit is None


def test_get_index_of_file(map_model: MapModel, configuration: Configuration):
    configuration.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    map_model.load(map_img_file_paths[:6])

    for i, filepath in enumerate(map_img_file_paths[:6]):
        assert map_model.get_index_of_file(filepath) == i

    assert map_model.get_index_of_file(map_img_file_paths[6]) is None
    assert map_model.get_index_of_file(None) is None
    # right file, but a frame that is not part of the map
    assert map_model.get_index_of_file(map_img_file_paths[0], 3) is None


def test_get_index_of_file_with_multi_frame_file(
    map_model: MapModel, configuration: Configuration
):
    configuration.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    map_model.load([multi_file_img_path])

    for frame_index in range(10):
        assert (
            map_model.get_index_of_file(multi_file_img_path, frame_index)
            == frame_index
        )
    assert map_model.get_index_of_file(multi_file_img_path, 10) is None


def test_load_hdf5_without_map_group(map_model: MapModel):
    """Loading from an HDF5 file with no 'map' group is a no-op."""
    with tempfile.NamedTemporaryFile(suffix=".h5", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        with h5py.File(tmp_path, "w") as f:
            pass  # empty file

        map_model.load_from_hdf5(h5py.File(tmp_path, "r"))
        assert map_model.filepaths is None
        assert map_model.map is None
    finally:
        os.unlink(tmp_path)


def test_insert_blank_shifts_later_points(
    map_model: MapModel, configuration: Configuration
):
    """The repair for a dropped frame: everything after the gap moves on."""
    configuration.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    map_model.load(map_img_file_paths[:6])
    assert map_model.dimension == (2, 3)

    map_model.insert_blank(1)

    # the grid grew a row to make room for the extra cell
    assert map_model.dimension == (3, 3)
    assert map_model.get_point_index(0, 0) == 0
    assert map_model.get_point_index(0, 1) is None
    assert map_model.get_point_index(0, 2) == 1
    assert np.isnan(map_model.map[0, 1])

    map_model.remove_blank(1)
    assert map_model.get_point_index(0, 1) == 1


def test_excluded_point_loses_its_cell_and_returns_to_it(
    map_model: MapModel, configuration: Configuration
):
    configuration.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    map_model.load(map_img_file_paths[:6])

    map_model.set_point_excluded(2)
    assert map_model.is_point_excluded(2)
    # the later points close up; the freed cell joins the blanks at the end
    assert map_model.get_point_index(0, 2) == 3
    assert map_model.get_point_index(1, 2) is None
    assert np.isnan(map_model.map[1, 2])

    map_model.set_point_excluded(2, False)
    assert map_model.get_point_index(0, 2) == 2
    assert not np.any(np.isnan(map_model.map))


def test_snake_reverses_every_other_row(
    map_model: MapModel, configuration: Configuration
):
    configuration.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    map_model.load(map_img_file_paths[:6])

    map_model.snake = True
    assert map_model.get_point_index(1, 0) == 5
    assert map_model.get_point_index(1, 2) == 3
    assert map_model.get_point_coordinates(3) == (1, 2)


def test_detect_gaps_from_filename_numbering(
    map_model: MapModel, configuration: Configuration
):
    configuration.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    map_model.load(map_img_file_paths[:6])

    # the test images are named ..._map_<n>_P1_E1_001.tif, so the trailing
    # number is the same for all of them and says nothing about gaps
    for index, info in enumerate(map_model.point_infos):
        info.filepath = f"/scan/point_{index if index < 3 else index + 2:03d}.tif"

    inserted = map_model.detect_gaps()
    assert inserted == 2
    assert map_model.get_point_index(0, 2) == 2
    assert map_model.get_point_index(1, 0) is None
    assert map_model.get_point_index(1, 1) is None
    assert map_model.get_point_index(1, 2) == 3


def test_detect_gaps_does_nothing_without_a_usable_numbering(
    map_model: MapModel, configuration: Configuration
):
    configuration.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    map_model.load(map_img_file_paths[:6])

    assert map_model.detect_gaps() == 0
    assert map_model.dimension == (2, 3)


def test_layout_round_trips_through_hdf5(
    map_model: MapModel, configuration: Configuration
):
    configuration.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    map_model.load(map_img_file_paths[:6])

    map_model.insert_blank(2)
    map_model.set_point_excluded(4)
    map_model.snake = True
    map_model.flip_vertical = True

    with tempfile.NamedTemporaryFile(suffix=".h5", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        with h5py.File(tmp_path, "w") as f:
            map_model.save_in_hdf5(f)

        new_model = MapModel(configuration)
        with h5py.File(tmp_path, "r") as f:
            new_model.load_from_hdf5(f)

        assert new_model.dimension == map_model.dimension
        assert new_model.get_slots() == map_model.get_slots()
        assert new_model.snake is True
        assert new_model.flip_vertical is True
        assert new_model.excluded_points == [4]
        np.testing.assert_array_equal(new_model.index_map, map_model.index_map)
        np.testing.assert_array_equal(new_model.map, map_model.map)
    finally:
        os.unlink(tmp_path)


def test_new_map_starts_from_a_plain_arrangement(
    map_model: MapModel, configuration: Configuration
):
    """An arrangement describes one set of files; loading others drops it."""
    configuration.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    map_model.load(map_img_file_paths[:6])
    map_model.insert_blank(1)
    map_model.set_point_excluded(3)

    map_model.load(map_img_file_paths[:6])

    assert map_model.slots is None
    assert map_model.excluded_points == []
    assert map_model.dimension == (2, 3)
    assert not np.any(np.isnan(map_model.map))


def test_a_fresh_map_has_one_roi(map_model: MapModel, configuration: Configuration):
    configuration.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    map_model.load(map_img_file_paths[:6])

    assert [roi.name for roi in map_model.rois] == ["A"]
    assert map_model.active_layer == "A"
    assert map_model.window == pytest.approx(
        [map_model.rois[0].x_min, map_model.rois[0].x_max]
    )


def test_second_roi_gives_a_second_layer(
    map_model: MapModel, configuration: Configuration
):
    configuration.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    map_model.load(map_img_file_paths[:6])

    map_model.add_roi(window=(15.0, 16.0))
    assert map_model.layer_names() == ["A", "B"]

    a_values = map_model.layer_values("A")
    b_values = map_model.layer_values("B")
    assert a_values is not None and b_values is not None
    assert not np.allclose(a_values, b_values)

    # the map still shows A until asked otherwise
    np.testing.assert_array_equal(map_model.window_intensities, a_values)
    map_model.active_layer = "B"
    np.testing.assert_array_equal(map_model.window_intensities, b_values)


def test_changing_a_reduction_changes_the_layer(
    map_model: MapModel, configuration: Configuration
):
    configuration.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    map_model.load(map_img_file_paths[:6])
    map_model.set_window((14.0, 16.0))
    summed = map_model.window_intensities.copy()

    map_model.rois[0].reduction = "center"

    assert not np.allclose(map_model.window_intensities, summed)
    # a peak position lands inside the window it was measured in
    assert np.all(map_model.window_intensities > 14.0)
    assert np.all(map_model.window_intensities < 16.0)


def test_expression_layer(map_model: MapModel, configuration: Configuration):
    configuration.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    map_model.load(map_img_file_paths[:6])
    map_model.add_roi(window=(15.0, 16.0))
    map_model.set_expression("ratio", "A/B")

    assert map_model.layer_names() == ["A", "B", "ratio"]
    expected = map_model.layer_values("A") / map_model.layer_values("B")
    np.testing.assert_allclose(map_model.layer_values("ratio"), expected)

    map_model.active_layer = "ratio"
    np.testing.assert_allclose(map_model.window_intensities, expected)
    np.testing.assert_allclose(map_model.map.ravel(), expected)


def test_expression_follows_a_renamed_roi(
    map_model: MapModel, configuration: Configuration
):
    configuration.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    map_model.load(map_img_file_paths[:6])
    map_model.add_roi(window=(15.0, 16.0))
    map_model.set_expression("ratio", "A/B")

    assert map_model.rename_roi("A", "quartz") is True
    assert map_model.expressions["ratio"] == "quartz / B"
    assert map_model.layer_values("ratio") is not None


def test_removing_an_roi_drops_expressions_that_needed_it(
    map_model: MapModel, configuration: Configuration
):
    configuration.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    map_model.load(map_img_file_paths[:6])
    map_model.add_roi(window=(15.0, 16.0))
    map_model.set_expression("ratio", "A/B")
    map_model.active_layer = "ratio"

    assert map_model.remove_roi("B") is True
    assert map_model.layer_names() == ["A"]
    assert map_model.active_layer == "A"
    assert map_model.map is not None

    # the last window cannot go, or there would be nothing to show
    assert map_model.remove_roi("A") is False


def test_rois_round_trip_through_hdf5(
    map_model: MapModel, configuration: Configuration
):
    configuration.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    map_model.load(map_img_file_paths[:6])
    map_model.rois[0].reduction = "area"
    map_model.add_roi(window=(15.0, 16.0))
    map_model.set_expression("ratio", "A/B")
    map_model.active_layer = "ratio"

    with tempfile.NamedTemporaryFile(suffix=".h5", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        with h5py.File(tmp_path, "w") as f:
            map_model.save_in_hdf5(f)

        new_model = MapModel(configuration)
        with h5py.File(tmp_path, "r") as f:
            new_model.load_from_hdf5(f)

        assert new_model.layer_names() == ["A", "B", "ratio"]
        assert new_model.rois[0].reduction == "area"
        assert new_model.active_layer == "ratio"
        np.testing.assert_allclose(new_model.map, map_model.map)

        # and the restored ROIs are live, not a frozen copy
        new_model.rois[1].x_max = 17.0
        assert not np.allclose(new_model.layer_values("B"), map_model.layer_values("B"))
    finally:
        os.unlink(tmp_path)


def test_legacy_project_without_rois_gets_one_from_its_window(
    map_model: MapModel, configuration: Configuration
):
    configuration.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    map_model.load(map_img_file_paths[:6])
    map_model.set_window((14.0, 16.0))

    with tempfile.NamedTemporaryFile(suffix=".h5", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        with h5py.File(tmp_path, "w") as f:
            map_model.save_in_hdf5(f)
            # emulate a file written before layers existed
            import json

            data = json.loads(f["map"]["params"].attrs["data"])
            data.pop("rois", None)
            f["map"]["params"].attrs["data"] = json.dumps(data)

        new_model = MapModel(configuration)
        with h5py.File(tmp_path, "r") as f:
            new_model.load_from_hdf5(f)

        assert [roi.name for roi in new_model.rois] == ["A"]
        assert new_model.window == pytest.approx([14.0, 16.0])
        np.testing.assert_allclose(new_model.map, map_model.map)
    finally:
        os.unlink(tmp_path)


def _overlay_lookup(x, y):
    return lambda name: (x, y) if name == "ref" else None


def _prepare_two_windows(map_model, configuration):
    configuration.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    map_model.load(map_img_file_paths[:6])
    map_model.set_window((14.0, 16.0))
    map_model.add_roi(name="B", window=(16.5, 18.0))


def test_ovl_in_an_expression_subtracts_the_reference(
    map_model: MapModel, configuration: Configuration
):
    """A - ovl(ref): the overlay put through window A, taken off A."""
    configuration.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    map_model.load(map_img_file_paths[:6])
    map_model.set_window((14.0, 16.0))
    plain = map_model.layer_values("A").copy()

    map_model.overlay_lookup = _overlay_lookup(
        map_model.pattern_x.copy(), np.full_like(map_model.pattern_x, 100.0)
    )
    map_model.set_expression("d", "A - ovl(ref)")

    import dioptas.model.map_reduction as mr
    channels = len(mr.window_indices(map_model.pattern_x, (14.0, 16.0)))
    np.testing.assert_allclose(
        map_model.layer_values("d"), plain - 100.0 * channels, rtol=1e-6
    )


def test_ovl_with_two_windows_needs_the_window_named(
    map_model: MapModel, configuration: Configuration
):
    _prepare_two_windows(map_model, configuration)
    map_model.overlay_lookup = _overlay_lookup(
        map_model.pattern_x.copy(), np.full_like(map_model.pattern_x, 100.0)
    )

    # ambiguous: two windows in the expression, no window given
    map_model.set_expression("d", "A - B - ovl(ref)")
    assert map_model.layer_values("d") is None

    map_model.set_expression("d", "A - B - ovl(ref, A)")
    expected = (
        map_model.layer_values("A")
        - map_model.layer_values("B")
        - map_model.overlay_window_value("ref", "A")
    )
    np.testing.assert_allclose(map_model.layer_values("d"), expected)


def test_ovl_respects_the_windows_value_kind(
    map_model: MapModel, configuration: Configuration
):
    """ovl(ref, A) uses A's reduction, not always a sum."""
    configuration.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    map_model.load(map_img_file_paths[:6])
    map_model.set_window((14.0, 16.0))
    x = map_model.pattern_x.copy()
    map_model.overlay_lookup = _overlay_lookup(x, np.full_like(x, 100.0))

    as_sum = map_model.overlay_window_value("ref", "A")
    map_model.rois[0].reduction = "mean"
    as_mean = map_model.overlay_window_value("ref", "A")

    assert as_mean == pytest.approx(100.0, rel=1e-6)
    assert as_sum > as_mean


def test_unknown_overlay_blanks_the_expression_layer(
    map_model: MapModel, configuration: Configuration
):
    configuration.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    map_model.load(map_img_file_paths[:6])
    map_model.overlay_lookup = _overlay_lookup(
        map_model.pattern_x.copy(), np.ones_like(map_model.pattern_x)
    )

    map_model.set_expression("d", "A - ovl(gone)")
    assert map_model.layer_values("d") is None
    assert map_model.overlay_exists("ref") is True
    assert map_model.overlay_exists("gone") is False


def test_overlay_outside_its_range_blanks_rather_than_extrapolates(
    map_model: MapModel, configuration: Configuration
):
    configuration.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    map_model.load(map_img_file_paths[:6])
    map_model.set_window((14.0, 16.0))

    # overlay only covers up to 10 — nowhere near the window
    x = np.linspace(0.0, 10.0, 50)
    map_model.overlay_lookup = _overlay_lookup(x, np.ones_like(x))
    map_model.set_expression("d", "A - ovl(ref)")

    assert np.all(np.isnan(map_model.layer_values("d")))


def test_overlays_changed_recomputes_referencing_expressions(
    map_model: MapModel, configuration: Configuration
):
    configuration.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    map_model.load(map_img_file_paths[:6])
    map_model.set_window((14.0, 16.0))

    x = map_model.pattern_x.copy()
    level = {"value": 100.0}
    map_model.overlay_lookup = lambda name: (x, np.full_like(x, level["value"]))
    map_model.set_expression("d", "A - ovl(ref)")
    map_model.active_layer = "d"
    first = map_model.window_intensities.copy()

    level["value"] = 200.0
    map_model.overlays_changed()  # what an overlay edit triggers

    assert not np.allclose(map_model.window_intensities, first)


def test_renaming_a_window_follows_into_ovl_but_not_the_overlay_name(
    map_model: MapModel, configuration: Configuration
):
    _prepare_two_windows(map_model, configuration)
    map_model.set_expression("d", "A - ovl(A, A)")  # overlay happens to share the name

    assert map_model.rename_roi("A", "quartz") is True
    assert map_model.expressions["d"] == "quartz - ovl(A, quartz)"


def test_structural_blanks_cannot_pretend_to_be_removable(
    map_model: MapModel, configuration: Configuration
):
    """A blank with no point after it belongs to the grid size: the grid
    keeps its cell count, so removing it would visibly do nothing."""
    configuration.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    map_model.load(map_img_file_paths[:6])
    map_model.set_dimension((3, 3))  # six points, three trailing blanks

    # trailing blanks: "removing" them changes nothing
    for slot in (6, 7, 8):
        assert map_model.can_remove_blank(slot) is False
    before = map_model.get_slots()
    map_model.remove_blank(7)
    assert map_model.get_slots() == before

    # a blank with points after it does shift them when removed
    map_model.insert_blank(2)
    assert map_model.can_remove_blank(2) is True
    map_model.remove_blank(2)
    assert map_model.get_point_index(0, 2) == 2

    # points are never removable, blanks out of range neither
    assert map_model.can_remove_blank(0) is False
    assert map_model.can_remove_blank(99) is False


def test_windows_cannot_take_the_expression_grammars_names(
    map_model: MapModel, configuration: Configuration
):
    """A window called "sqrt" or "ovl" would shadow the functions and the
    overlay reference in every expression."""
    configuration.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    map_model.load(map_img_file_paths[:6])

    assert map_model.rename_roi("A", "ovl") is False
    assert map_model.rename_roi("A", "sqrt") is False
    assert map_model.rename_roi("A", "quartz") is True


def test_windows_and_expressions_share_one_namespace(
    map_model: MapModel, configuration: Configuration
):
    """Windows are looked up first, so a colliding name would make the
    expression layer unreachable (found by review on the PR)."""
    configuration.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    map_model.load(map_img_file_paths[:6])
    map_model.set_expression("ratio", "A*2")

    # an expression cannot take a window's name, a window cannot take an
    # expression's, and the automatic window names skip taken ones
    assert map_model.set_expression("A", "A*2") is False
    assert map_model.rename_roi("A", "ratio") is False
    map_model.set_expression("B", "A*3")
    added = map_model.add_roi()
    assert added.name == "C"
    assert sorted(map_model.layer_names()) == sorted(["A", "C", "ratio", "B"])


def _calibrated_map(map_model: MapModel, configuration: Configuration, count: int):
    configuration.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    map_model.load(map_img_file_paths[:count])


def test_append_files_grows_the_map(
    map_model: MapModel, configuration: Configuration
):
    """The live path: new frames arrive while the scan runs, and the grid
    keeps its columns and gains rows rather than being re-derived."""
    _calibrated_map(map_model, configuration, 6)
    assert map_model.dimension == (2, 3)

    failed = map_model.append_files(map_img_file_paths[6:9])

    assert failed == []
    assert map_model.filepaths == map_img_file_paths[:9]
    assert len(map_model.point_infos) == 9
    assert map_model.pattern_intensities.shape[0] == 9
    assert len(map_model.window_intensities) == 9
    assert map_model.dimension == (3, 3)
    assert map_model.get_point_index(2, 2) == 8


def test_append_files_ignores_files_already_in_the_map(
    map_model: MapModel, configuration: Configuration
):
    _calibrated_map(map_model, configuration, 6)
    changed = []
    map_model.map_changed.connect(lambda: changed.append(True))

    failed = map_model.append_files(map_img_file_paths[:6])

    assert failed == []
    assert len(map_model.point_infos) == 6
    assert changed == []


def test_append_files_keeps_the_arrangement(
    map_model: MapModel, configuration: Configuration
):
    """Blanks inserted for dropped frames keep their meaning; the new point
    goes after the last arranged cell."""
    _calibrated_map(map_model, configuration, 6)
    map_model.insert_blank(1)
    map_model.set_point_excluded(3)
    assert map_model.dimension == (3, 3)

    map_model.append_files([map_img_file_paths[6]])

    assert map_model.get_point_index(0, 1) is None, "blank survives the append"
    assert map_model.is_point_excluded(3)
    # 6 points + 1 blank before the append; the new point takes the cell
    # after the last one
    assert map_model.get_slots()[7] == 6
    assert map_model.dimension == (3, 3)


def test_append_files_reports_unreadable_files_and_keeps_going(
    map_model: MapModel, configuration: Configuration
):
    _calibrated_map(map_model, configuration, 6)

    failed = map_model.append_files(
        ["/nowhere/dropped_frame.tif", map_img_file_paths[6]]
    )

    assert failed == ["/nowhere/dropped_frame.tif"]
    assert len(map_model.point_infos) == 7
    assert map_model.filepaths[-1] == map_img_file_paths[6]


def test_append_files_without_a_map_is_refused(
    map_model: MapModel, configuration: Configuration
):
    with pytest.raises(ValueError):
        map_model.append_files(map_img_file_paths[:1])


def test_append_files_refuses_a_changed_integration_unit(
    map_model: MapModel, configuration: Configuration
):
    """Appending in a different unit would mix incompatible x-axes."""
    _calibrated_map(map_model, configuration, 6)
    configuration.integration_unit = "q_A^-1"

    with pytest.raises(ValueError):
        map_model.append_files([map_img_file_paths[6]])
    assert len(map_model.point_infos) == 6


def test_append_files_fills_unfilled_grid_capacity(
    map_model: MapModel, configuration: Configuration
):
    """A grid set to the full scan size up front fills in cell by cell —
    capacity blanks are taken by new points, no growth until they run out."""
    _calibrated_map(map_model, configuration, 4)
    map_model.set_dimension((3, 3))
    assert map_model.get_point_index(1, 1) is None

    map_model.append_files([map_img_file_paths[4]])

    assert map_model.get_point_index(1, 1) == 4
    assert map_model.dimension == (3, 3)


def test_append_files_batches_several_files(
    map_model: MapModel, configuration: Configuration
):
    """A beamline can write faster than one-by-one integration keeps up, so
    a multi-file append goes through the same batch engine as the bulk load."""
    from dioptas.model.MapModel import MapPointInfo

    _calibrated_map(map_model, configuration, 4)
    configuration.calibration_model.can_use_dioptrin_batch = MagicMock(
        return_value=True
    )

    def fake_batch(filepaths):
        infos = [MapPointInfo(path, 0) for path in filepaths]
        intensities = [np.zeros_like(map_model.pattern_x) for _ in filepaths]
        return infos, intensities

    map_model._integrate_files_dioptrin = MagicMock(side_effect=fake_batch)

    failed = map_model.append_files(map_img_file_paths[4:7])

    assert failed == []
    map_model._integrate_files_dioptrin.assert_called_once_with(
        map_img_file_paths[4:7]
    )
    assert len(map_model.point_infos) == 7
    assert map_model.filepaths == map_img_file_paths[:7]


def test_append_files_retries_one_by_one_when_the_batch_fails(
    map_model: MapModel, configuration: Configuration
):
    """One bad file fails the whole batch; the retry drops only that file."""
    _calibrated_map(map_model, configuration, 4)
    configuration.calibration_model.can_use_dioptrin_batch = MagicMock(
        return_value=True
    )
    map_model._integrate_files_dioptrin = MagicMock(
        side_effect=RuntimeError("bad frame in the batch")
    )

    failed = map_model.append_files(
        [map_img_file_paths[4], "/nowhere/dropped.tif", map_img_file_paths[5]]
    )

    assert failed == ["/nowhere/dropped.tif"]
    assert len(map_model.point_infos) == 6
    assert map_model.filepaths[-2:] == map_img_file_paths[4:6]
