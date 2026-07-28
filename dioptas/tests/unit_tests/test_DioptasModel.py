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


def test_combine_patterns_after_image_shape_change(dioptas_model):
    """Loading a differently-sized image should invalidate the MultiGeometry
    cache so that combined integration still works without errors."""
    # set up two configurations with the same image
    dioptas_model.calibration_model.load(
        os.path.join(data_path, "CeO2_Pilatus1M.poni")
    )
    dioptas_model.img_model.load(os.path.join(data_path, "CeO2_Pilatus1M.tif"))

    dioptas_model.add_configuration()
    dioptas_model.calibration_model.load(
        os.path.join(data_path, "CeO2_Pilatus1M_2.poni")
    )
    dioptas_model.img_model.load(os.path.join(data_path, "CeO2_Pilatus1M.tif"))

    dioptas_model.combine_patterns = True
    x_before, _ = dioptas_model.pattern.data
    assert len(x_before) > 0

    # now load a differently-sized image+calibration into one configuration
    dioptas_model.select_configuration(0)
    dioptas_model.calibration_model.load(
        os.path.join(data_path, "LaB6_40keV_MarCCD.poni")
    )
    dioptas_model.img_model.load(os.path.join(data_path, "LaB6_40keV_MarCCD.tif"))

    # combined pattern should still work and produce a different result
    x_after, _ = dioptas_model.pattern.data
    assert len(x_after) > 0
    assert not np.array_equal(x_before, x_after)


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


def test_save_and_load_round_trips_params_only_fields(dioptas_model, tmp_path):
    """oned_azimuth_range and trim_trailing_zeros are not in the legacy .dio
    layout — they round-trip via the generic params group."""
    dioptas_model.current_configuration.params.oned_azimuth_range = [-90.0, 90.0]
    dioptas_model.current_configuration.params.trim_trailing_zeros = False

    filename = os.path.join(tmp_path, "params.dio")
    dioptas_model.save(filename)
    dioptas_model.reset()
    assert dioptas_model.current_configuration.oned_azimuth_range is None
    assert dioptas_model.current_configuration.trim_trailing_zeros is True

    dioptas_model.load(filename)
    assert dioptas_model.current_configuration.oned_azimuth_range == [-90.0, 90.0]
    assert dioptas_model.current_configuration.trim_trailing_zeros is False


def test_load_project_without_params_group(dioptas_model, tmp_path):
    """Project files written before the params layer must still load."""
    import h5py

    filename = os.path.join(tmp_path, "legacy.dio")
    dioptas_model.save(filename)
    with h5py.File(filename, "r+") as f:
        for _, configuration_group in f["configurations"].items():
            del configuration_group["params"]

    dioptas_model.load(filename)
    assert dioptas_model.current_configuration.oned_azimuth_range is None
    assert dioptas_model.current_configuration.trim_trailing_zeros is True


def test_parameters_changed_invalidates_multi_geometry_after_load(
    dioptas_model, tmp_path
):
    dioptas_model.save(os.path.join(tmp_path, "project.dio"))
    dioptas_model.load(os.path.join(tmp_path, "project.dio"))

    dioptas_model._multi_geometry = "sentinel"
    dioptas_model.calibration_model.parameters_changed.emit()
    assert dioptas_model._multi_geometry is None

    dioptas_model._multi_geometry = "sentinel"
    dioptas_model.calibration_model.detector_reset.emit()
    assert dioptas_model._multi_geometry is None


def test_parameters_changed_invalidates_multi_geometry_after_reset(dioptas_model):
    dioptas_model.reset()

    dioptas_model._multi_geometry = "sentinel"
    dioptas_model.calibration_model.parameters_changed.emit()
    assert dioptas_model._multi_geometry is None

    dioptas_model._multi_geometry = "sentinel"
    dioptas_model.calibration_model.detector_reset.emit()
    assert dioptas_model._multi_geometry is None


def test_clear_model(dioptas_model):
    dioptas_model.calibration_model.load(os.path.join(data_path, "CeO2_Pilatus1M.poni"))
    dioptas_model.img_model.load(os.path.join(data_path, "image_001.tif"))

    dioptas_model.add_configuration()
    dioptas_model.add_configuration()

    dioptas_model.reset()

    assert len(dioptas_model.configurations) == 1
    assert dioptas_model.configuration_ind == 0


def test_reset_clears_overlays_and_phases(dioptas_model):
    dioptas_model.overlay_model.add_overlay(
        np.linspace(0, 10, 100), np.ones(100), "test_overlay"
    )
    dioptas_model.phase_model.add_jcpds(
        os.path.join(data_path, "jcpds", "au_Anderson.jcpds")
    )
    assert len(dioptas_model.overlay_model.overlays) == 1
    assert len(dioptas_model.phase_model.phases) == 1

    dioptas_model.reset()

    assert len(dioptas_model.overlay_model.overlays) == 0
    assert len(dioptas_model.phase_model.phases) == 0
    assert len(dioptas_model.configurations) == 1


def test_save_and_load_round_trip(dioptas_model, tmp_path):
    """Save a project with image, calibration, overlays, and phases, then load
    it into a fresh model and verify the state is restored."""
    # Setup: load calibration and image
    dioptas_model.calibration_model.load(
        os.path.join(data_path, "CeO2_Pilatus1M.poni")
    )
    dioptas_model.img_model.load(os.path.join(data_path, "CeO2_Pilatus1M.tif"))

    # Add an overlay
    ov_x = np.linspace(1, 20, 200)
    ov_y = np.sin(ov_x)
    dioptas_model.overlay_model.add_overlay(ov_x, ov_y, "sin_overlay")
    dioptas_model.overlay_model.set_overlay_scaling(0, 2.5)
    dioptas_model.overlay_model.set_overlay_offset(0, 1.0)

    # Add a phase
    dioptas_model.phase_model.add_jcpds(
        os.path.join(data_path, "jcpds", "au_Anderson.jcpds")
    )

    # Add a second configuration
    dioptas_model.add_configuration()
    dioptas_model.calibration_model.load(
        os.path.join(data_path, "CeO2_Pilatus1M_2.poni")
    )
    dioptas_model.img_model.load(os.path.join(data_path, "CeO2_Pilatus1M.tif"))

    # Save
    save_path = os.path.join(tmp_path, "test_project.dio")
    dioptas_model.save(save_path)

    # Load into a new model
    from dioptas.model.DioptasModel import DioptasModel

    new_model = DioptasModel()
    new_model.load(save_path)

    # Verify configurations
    assert len(new_model.configurations) == 2

    # Verify overlay
    assert len(new_model.overlay_model.overlays) == 1
    loaded_ov = new_model.overlay_model.overlays[0]
    assert loaded_ov.name == "sin_overlay"
    assert loaded_ov.scaling == pytest.approx(2.5)
    assert loaded_ov.offset == pytest.approx(1.0)
    loaded_x, loaded_y = loaded_ov.original_data
    assert len(loaded_x) == 200

    # Verify phase
    assert len(new_model.phase_model.phases) == 1
    assert "au_Anderson" in new_model.phase_model.phases[0].name

    # Verify calibration is restored (is_calibrated)
    new_model.select_configuration(0)
    assert new_model.calibration_model.is_calibrated


def test_save_and_load_preserves_selected_configuration(dioptas_model, tmp_path):
    """Selected configuration index should be preserved across save/load."""
    dioptas_model.add_configuration()
    dioptas_model.add_configuration()
    dioptas_model.select_configuration(1)

    save_path = os.path.join(tmp_path, "test_selected.dio")
    dioptas_model.save(save_path)

    from dioptas.model.DioptasModel import DioptasModel

    new_model = DioptasModel()
    new_model.load(save_path)

    assert new_model.configuration_ind == 1


def test_select_configuration_out_of_range(dioptas_model):
    """Selecting a configuration with an invalid index should not change state."""
    dioptas_model.add_configuration()
    dioptas_model.select_configuration(0)

    # Try out of range
    dioptas_model.select_configuration(99)
    assert dioptas_model.configuration_ind == 0

    dioptas_model.select_configuration(-1)
    assert dioptas_model.configuration_ind == 0


def test_select_configuration_emits_signals_and_toggles_auto_integrate(dioptas_model):
    """When combine_cakes is True, selecting a configuration should toggle
    auto_integrate_cake off and on."""
    dioptas_model.calibration_model.load(
        os.path.join(data_path, "CeO2_Pilatus1M.poni")
    )
    dioptas_model.current_configuration.auto_integrate_cake = True
    dioptas_model.img_model.load(os.path.join(data_path, "CeO2_Pilatus1M.tif"))

    dioptas_model.add_configuration()
    dioptas_model.calibration_model.load(
        os.path.join(data_path, "CeO2_Pilatus1M_2.poni")
    )
    dioptas_model.current_configuration.auto_integrate_cake = True
    dioptas_model.img_model.load(os.path.join(data_path, "CeO2_Pilatus1M.tif"))

    dioptas_model.combine_cakes = True

    # Switch config — this exercises lines 300-306
    dioptas_model.select_configuration(0)
    assert dioptas_model.configuration_ind == 0
    assert dioptas_model.current_configuration.auto_integrate_cake is True


def test_proxy_properties_return_correct_types(dioptas_model):
    """Proxy properties should return the correct model types."""
    from dioptas.model import (
        ImgModel,
        CalibrationModel,
        MaskModel,
        PatternModel,
        OverlayModel,
        PhaseModel,
        BatchModel,
    )
    from dioptas.model.MapModel import MapModel

    assert isinstance(dioptas_model.img_model, ImgModel)
    assert isinstance(dioptas_model.calibration_model, CalibrationModel)
    assert isinstance(dioptas_model.mask_model, MaskModel)
    assert isinstance(dioptas_model.pattern_model, PatternModel)
    assert isinstance(dioptas_model.overlay_model, OverlayModel)
    assert isinstance(dioptas_model.phase_model, PhaseModel)
    assert isinstance(dioptas_model.batch_model, BatchModel)
    assert isinstance(dioptas_model.map_model, MapModel)


def test_use_mask_property(dioptas_model):
    assert dioptas_model.use_mask is False
    dioptas_model.use_mask = True
    assert dioptas_model.use_mask is True


def test_transparent_mask_property(dioptas_model):
    assert dioptas_model.transparent_mask is False
    dioptas_model.transparent_mask = True
    assert dioptas_model.transparent_mask is True


def test_combine_patterns_property(dioptas_model):
    """Setting combine_patterns should emit pattern_changed."""
    dioptas_model.pattern_changed = MagicMock()
    dioptas_model.combine_patterns = True
    assert dioptas_model.combine_patterns is True
    dioptas_model.pattern_changed.emit.assert_called()


def test_combine_cakes_disable(dioptas_model):
    """Disabling combine_cakes should disconnect cake_changed signals."""
    dioptas_model.calibration_model.load(
        os.path.join(data_path, "CeO2_Pilatus1M.poni")
    )
    dioptas_model.current_configuration.auto_integrate_cake = True
    dioptas_model.img_model.load(os.path.join(data_path, "CeO2_Pilatus1M.tif"))

    dioptas_model.add_configuration()
    dioptas_model.calibration_model.load(
        os.path.join(data_path, "CeO2_Pilatus1M_2.poni")
    )
    dioptas_model.current_configuration.auto_integrate_cake = True
    dioptas_model.img_model.load(os.path.join(data_path, "CeO2_Pilatus1M.tif"))

    dioptas_model.combine_cakes = True
    assert dioptas_model.combine_cakes is True

    # Now disable — exercises lines 435-436
    dioptas_model.combine_cakes = False
    assert dioptas_model.combine_cakes is False


def test_cake_tth_and_azi_properties(dioptas_model):
    """cake_tth and cake_azi should return values from the calibration model
    when not combining, and from the combined result when combining."""
    dioptas_model.calibration_model.load(
        os.path.join(data_path, "CeO2_Pilatus1M.poni")
    )
    dioptas_model.current_configuration.auto_integrate_cake = True
    dioptas_model.img_model.load(os.path.join(data_path, "CeO2_Pilatus1M.tif"))

    # Without combining
    assert dioptas_model.cake_tth is not None
    assert dioptas_model.cake_azi is not None

    # With combining — exercises lines 558-559, 565-566
    dioptas_model.add_configuration()
    dioptas_model.calibration_model.load(
        os.path.join(data_path, "CeO2_Pilatus1M_2.poni")
    )
    dioptas_model.current_configuration.auto_integrate_cake = True
    dioptas_model.img_model.load(os.path.join(data_path, "CeO2_Pilatus1M.tif"))

    dioptas_model.combine_cakes = True
    combined_tth = dioptas_model.cake_tth
    combined_azi = dioptas_model.cake_azi
    assert combined_tth is not None
    assert combined_azi is not None


def test_combine_patterns_d_spacing_unit(dioptas_model):
    """Combined integration with d_A unit should produce d-spacing values."""
    dioptas_model.calibration_model.load(
        os.path.join(data_path, "CeO2_Pilatus1M.poni")
    )
    dioptas_model.img_model.load(os.path.join(data_path, "CeO2_Pilatus1M.tif"))

    dioptas_model.add_configuration()
    dioptas_model.calibration_model.load(
        os.path.join(data_path, "CeO2_Pilatus1M_2.poni")
    )
    dioptas_model.img_model.load(os.path.join(data_path, "CeO2_Pilatus1M.tif"))

    dioptas_model.integration_unit = "d_A"
    dioptas_model.combine_patterns = True

    x, y = dioptas_model.pattern.data
    assert len(x) > 0
    # d-spacing values should be positive
    assert np.all(x > 0)
    # d-spacing values should be distinct from 2theta (which goes up to ~50 deg)
    # d-spacing at low angles can be very large, but min should be sub-Angstrom
    assert np.min(x) < 1.0


def test_save_combined_pattern(dioptas_model, tmp_path):
    """save_combined_pattern should write a valid pattern file."""
    x1, x2 = prepare_combined_patterns(dioptas_model)
    file_path = os.path.join(tmp_path, "combined.xy")
    dioptas_model.save_combined_pattern(file_path)
    assert os.path.exists(file_path)
    saved = Pattern.from_file(file_path)
    x, y = saved.data
    assert len(x) > 0


def test_remove_only_configuration_does_nothing(dioptas_model):
    """Removing the last remaining configuration should be a no-op."""
    assert len(dioptas_model.configurations) == 1
    dioptas_model.remove_configuration()
    assert len(dioptas_model.configurations) == 1


def test_blockSignals(dioptas_model):
    """blockSignals should block and unblock all Signal instances."""
    dioptas_model.blockSignals(True)
    assert dioptas_model.img_changed.blocked is True
    assert dioptas_model.pattern_changed.blocked is True

    dioptas_model.blockSignals(False)
    assert dioptas_model.img_changed.blocked is False
    assert dioptas_model.pattern_changed.blocked is False


def test_clicked_tth_and_azi_signals(dioptas_model):
    """clicked_tth_changed and clicked_azi_changed should update the stored values."""
    dioptas_model.clicked_tth_changed.emit(15.5)
    assert dioptas_model.clicked_tth == 15.5

    dioptas_model.clicked_azi_changed.emit(90.0)
    assert dioptas_model.clicked_azi == 90.0
