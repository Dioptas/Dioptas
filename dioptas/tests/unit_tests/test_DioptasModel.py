# SPDX-License-Identifier: MIT

import os

import numpy as np
import pytest
from mock import MagicMock
from xypattern import Pattern
from xypattern.auto_background import SmoothBrucknerBackground

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, "../data")


def test_add_configuration(dioptas_model):
    dioptas_model.img_model.load(os.path.join(data_path, "image_001.tif"))

    prev_sum = np.sum(dioptas_model.img_data)
    assert np.array_equal(
        dioptas_model.img_data, dioptas_model.configurations[0].img_model.img_data
    )

    dioptas_model.add_configuration()
    new_sum = np.sum(dioptas_model.img_data)
    assert np.array_equal(
        dioptas_model.img_data, dioptas_model.configurations[1].img_model.img_data
    )

    assert prev_sum == new_sum


def test_remove_configuration(dioptas_model):
    dioptas_model.add_configuration()
    dioptas_model.img_model.load(os.path.join(data_path, "image_001.tif"))
    old_img = dioptas_model.img_data

    dioptas_model.remove_configuration()
    assert not np.array_equal(dioptas_model.img_data, old_img)


def test_select_configuration(dioptas_model):
    img_1 = dioptas_model.img_data

    dioptas_model.add_configuration()
    dioptas_model.img_model.load(os.path.join(data_path, "image_001.tif"))
    img_2 = dioptas_model.img_data

    dioptas_model.add_configuration()
    dioptas_model.img_model.load(os.path.join(data_path, "image_002.tif"))
    img_3 = dioptas_model.img_data

    dioptas_model.select_configuration(0)
    assert np.array_equal(dioptas_model.img_data, img_1)

    dioptas_model.select_configuration(2)
    assert np.array_equal(dioptas_model.img_data, img_3)

    dioptas_model.select_configuration(1)
    assert np.array_equal(dioptas_model.img_data, img_2)


def test_signals_are_raised(dioptas_model):
    dioptas_model.configuration_added = MagicMock()
    dioptas_model.configuration_selected = MagicMock()
    dioptas_model.configuration_removed = MagicMock()

    dioptas_model.add_configuration()
    dioptas_model.add_configuration()
    dioptas_model.configuration_added.emit.assert_called()

    dioptas_model.select_configuration(0)
    dioptas_model.configuration_selected.emit.assert_called_with(0)

    dioptas_model.remove_configuration()
    dioptas_model.configuration_removed.emit.assert_called_with(0)


def test_integrate_cakes(dioptas_model):
    dioptas_model.calibration_model.load(os.path.join(data_path, "CeO2_Pilatus1M.poni"))
    dioptas_model.current_configuration.auto_integrate_cake = True
    dioptas_model.img_model.load(os.path.join(data_path, "CeO2_Pilatus1M.tif"))
    assert not np.array_equal(
        dioptas_model.current_configuration.cake_img, np.zeros((2048, 2048))
    )


def test_integrate_cake_with_mask(dioptas_model):
    dioptas_model.calibration_model.load(os.path.join(data_path, "CeO2_Pilatus1M.poni"))
    dioptas_model.current_configuration.auto_integrate_cake = True
    dioptas_model.img_model.load(os.path.join(data_path, "CeO2_Pilatus1M.tif"))
    cake_img1 = dioptas_model.current_configuration.cake_img

    dioptas_model.use_mask = True
    dioptas_model.mask_model.mask_below_threshold(dioptas_model.img_data, 1)
    dioptas_model.img_model.img_changed.emit()
    cake_img2 = dioptas_model.current_configuration.cake_img
    assert not np.array_equal(cake_img1, cake_img2)


def test_integrate_cake_with_different_azimuth_points(dioptas_model):
    dioptas_model.calibration_model.load(os.path.join(data_path, "CeO2_Pilatus1M.poni"))
    dioptas_model.current_configuration.auto_integrate_cake = True
    dioptas_model.img_model.load(os.path.join(data_path, "CeO2_Pilatus1M.tif"))

    assert dioptas_model.current_configuration.cake_img.shape[0] == 360
    dioptas_model.current_configuration.cake_azimuth_points = 720
    assert dioptas_model.current_configuration.cake_img.shape[0] == 720


def test_integrate_cake_with_different_rad_points(dioptas_model):
    dioptas_model.calibration_model.load(os.path.join(data_path, "CeO2_Pilatus1M.poni"))
    dioptas_model.current_configuration.auto_integrate_cake = True
    dioptas_model.img_model.load(os.path.join(data_path, "CeO2_Pilatus1M.tif"))

    assert dioptas_model.current_configuration.cake_img.shape[1] > 360
    dioptas_model.current_configuration.integration_rad_points = 720
    assert dioptas_model.current_configuration.cake_img.shape[1], 720


def test_change_cake_azimuth_range(dioptas_model):
    dioptas_model.calibration_model.load(os.path.join(data_path, "CeO2_Pilatus1M.poni"))
    dioptas_model.current_configuration.auto_integrate_cake = True
    dioptas_model.img_model.load(os.path.join(data_path, "CeO2_Pilatus1M.tif"))

    dioptas_model.current_configuration.cake_azimuth_range = [-180, 180]

    assert dioptas_model.current_configuration.calibration_model.cake_azi[
        0
    ] == pytest.approx(-179.5)
    assert dioptas_model.current_configuration.calibration_model.cake_azi[
        -1
    ] == pytest.approx(179.5)

    dioptas_model.current_configuration.cake_azimuth_range = [-100, 100]
    assert dioptas_model.current_configuration.calibration_model.cake_azi[0] > -100
    assert dioptas_model.current_configuration.calibration_model.cake_azi[-1] < 100


def prepare_combined_patterns(model):
    model.calibration_model.load(os.path.join(data_path, "CeO2_Pilatus1M.poni"))
    model.img_model.load(os.path.join(data_path, "CeO2_Pilatus1M.tif"))

    x1, _ = model.pattern_model.pattern.data

    model.add_configuration()
    model.calibration_model.load(os.path.join(data_path, "CeO2_Pilatus1M_2.poni"))
    model.img_model.load(os.path.join(data_path, "CeO2_Pilatus1M.tif"))

    x2, _ = model.pattern_model.pattern.data

    model.combine_patterns = True
    return x1, x2


def test_combine_patterns(dioptas_model):
    x1, x2 = prepare_combined_patterns(dioptas_model)

    assert dioptas_model.pattern is not None
    x3, y3 = dioptas_model.pattern.data
    # combined pattern should cover wider range than either individual pattern alone
    assert np.max(x3) > np.max(x1)
    assert len(x3) > 0


def test_save_combine_patterns(dioptas_model, tmp_path):
    x1, x2 = prepare_combined_patterns(dioptas_model)
    file_path = os.path.join(tmp_path, "combined_pattern.xy")
    dioptas_model.pattern.save(file_path)
    saved_pattern = Pattern.from_file(file_path)
    x3, y3 = saved_pattern.data
    assert np.max(x3) > np.max(x1)
    assert len(x3) > 0


def test_combine_cakes(dioptas_model):
    dioptas_model.calibration_model.load(os.path.join(data_path, "CeO2_Pilatus1M.poni"))
    dioptas_model.current_configuration.auto_integrate_cake = True
    dioptas_model.img_model.load(os.path.join(data_path, "CeO2_Pilatus1M.tif"))

    cake1 = dioptas_model.cake_data
    dioptas_model.add_configuration()

    dioptas_model.calibration_model.load(
        os.path.join(data_path, "CeO2_Pilatus1M_2.poni")
    )
    dioptas_model.current_configuration.auto_integrate_cake = True
    dioptas_model.img_model.load(os.path.join(data_path, "CeO2_Pilatus1M.tif"))

    cake2 = dioptas_model.cake_data
    dioptas_model.combine_cakes = True
    assert not np.array_equal(dioptas_model.cake_data, cake1)
    assert not np.array_equal(dioptas_model.cake_data, cake2)


def test_setting_factors(dioptas_model):
    dioptas_model.img_model.load(os.path.join(data_path, "image_001.tif"))
    data1 = np.copy(dioptas_model.img_data)
    dioptas_model.img_model.factor = 2
    assert np.array_equal(2 * data1, dioptas_model.img_data)


def test_iterate_next_image(dioptas_model):
    dioptas_model.img_model.load(os.path.join(data_path, "image_001.tif"))
    dioptas_model.add_configuration()
    dioptas_model.img_model.load(os.path.join(data_path, "image_001.tif"))

    dioptas_model.next_image()

    assert dioptas_model.configurations[0].img_model.filename == os.path.abspath(
        os.path.join(data_path, "image_002.tif")
    )
    assert dioptas_model.configurations[1].img_model.filename == os.path.abspath(
        os.path.join(data_path, "image_002.tif")
    )


def test_iterate_previous_image(dioptas_model):
    dioptas_model.img_model.load(os.path.join(data_path, "image_002.tif"))
    dioptas_model.add_configuration()
    dioptas_model.img_model.load(os.path.join(data_path, "image_002.tif"))

    dioptas_model.previous_image()

    assert dioptas_model.configurations[0].img_model.filename == os.path.abspath(
        os.path.join(data_path, "image_001.tif")
    )
    assert dioptas_model.configurations[1].img_model.filename == os.path.abspath(
        os.path.join(data_path, "image_001.tif")
    )


def test_unit_change_with_auto_background_subtraction(dioptas_model):
    # load calibration and image
    dioptas_model.calibration_model.load(os.path.join(data_path, "CeO2_Pilatus1M.poni"))
    dioptas_model.img_model.load(os.path.join(data_path, "image_001.tif"))

    # check that background subtraction works
    x, y = dioptas_model.pattern_model.pattern.data
    x_max_2th = np.max(x)
    roi = (0, np.max(x) + 1)
    dioptas_model.pattern_model.set_auto_background_subtraction((0.1, 50, 50), roi)
    new_y = dioptas_model.pattern_model.pattern.y
    assert np.sum(y - new_y) != 0

    x_bkg, _ = dioptas_model.pattern_model.pattern.auto_background_pattern.data

    # change the unit to q
    dioptas_model.integration_unit = "q_A^-1"

    # check that the pattern is integrated with different unit
    x, y = dioptas_model.pattern_model.pattern.data
    x_max_q = np.max(x)
    assert x_max_q < x_max_2th

    auto_bkg = dioptas_model.pattern_model.pattern.auto_bkg
    assert type(auto_bkg) == SmoothBrucknerBackground
    assert auto_bkg.smooth_width < 0.1

    # check that the background roi has changed
    assert dioptas_model.pattern_model.pattern.auto_bkg_roi[1] != roi[1]
    assert dioptas_model.pattern_model.pattern.auto_bkg is not None

    # check that the background pattern has changed:
    x_bkg_2, _ = dioptas_model.pattern_model.pattern.auto_background_pattern.data
    assert np.max(x_bkg) != np.max(x_bkg_2)


def test_save_empty_configuration(dioptas_model, tmp_path):
    dioptas_model.save(os.path.join(tmp_path, "empty.dio"))


def test_clear_model(dioptas_model):
    dioptas_model.calibration_model.load(os.path.join(data_path, "CeO2_Pilatus1M.poni"))
    dioptas_model.img_model.load(os.path.join(data_path, "image_001.tif"))

    dioptas_model.add_configuration()
    dioptas_model.add_configuration()

    dioptas_model.reset()
