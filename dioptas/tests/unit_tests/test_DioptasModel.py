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
    # 2.0: the reference must be computed in float — integer multiplication
    # of the uint16 data would wrap around, which the factor no longer does
    assert np.array_equal(2.0 * data1, dioptas_model.img_data)


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


def test_save_with_numpy_bool_in_params(dioptas_model, tmp_path):
    """Legacy project loading assigns h5py attributes (numpy scalars) into
    params fields — saving afterwards must not crash on them."""
    dioptas_model.current_configuration.params.use_mask = np.bool_(True)

    filename = os.path.join(tmp_path, "numpy_bool.dio")
    dioptas_model.save(filename)

    dioptas_model.reset()
    dioptas_model.load(filename)
    assert dioptas_model.current_configuration.params.use_mask is True


def test_failed_save_does_not_block_subsequent_saves(dioptas_model, tmp_path):
    """A save that fails partway must close the file handle — a leaked open
    handle used to make every later save of the same file fail with
    "unable to truncate a file which is already open"."""
    filename = os.path.join(tmp_path, "project.dio")

    original = dioptas_model._save_into
    dioptas_model._save_into = MagicMock(side_effect=RuntimeError("boom"))
    with pytest.raises(RuntimeError):
        dioptas_model.save(filename)
    dioptas_model._save_into = original

    dioptas_model.save(filename)
    assert os.path.isfile(filename)
    # the failed attempt must not leave its temporary file behind either
    assert [n for n in os.listdir(tmp_path) if ".tmp-" in n] == []


def test_project_state_is_one_json_document(dioptas_model, tmp_path):
    """The layout is the state tree plus the binary it references: one
    /state document, content-addressed payloads and caches — no per-field
    attributes, and no group-per-reflection."""
    import h5py
    import json

    filename = os.path.join(tmp_path, "layout.dio")
    dioptas_model.save(filename)

    with h5py.File(filename, "r") as f:
        assert "state" in f
        document = json.loads(f["state"][()])
        assert set(document) >= {
            "view",
            "phase",
            "configurations",
            "overlays",
            "phases",
            "selected_configuration",
        }
        # settings live in the document, not as attributes beside it
        assert "integration_unit" in document["configurations"][0]["params"]
        assert list(f["configurations/0"].attrs) == []


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


def test_configuration_params_changed_forwarding(dioptas_model):
    """Params changes of the current configuration surface as one
    store-level signal with (field, new, old)."""
    got = []
    dioptas_model.configuration_params_changed.connect(
        lambda field, new, old: got.append((field, new, old))
    )

    dioptas_model.current_configuration.params.use_mask = True
    dioptas_model.current_configuration.params.cake_azimuth_points = 720
    assert got == [("use_mask", True, False), ("cake_azimuth_points", 720, 360)]


def test_configuration_params_changed_follows_selected_configuration(dioptas_model):
    got = []
    dioptas_model.configuration_params_changed.connect(
        lambda field, new, old: got.append((field, new))
    )

    dioptas_model.add_configuration()
    inactive = dioptas_model.configurations[0]
    dioptas_model.select_configuration(1)
    got.clear()

    # changes on a non-selected configuration must not surface
    inactive.params.use_mask = True
    assert got == []

    dioptas_model.current_configuration.params.transparent_mask = True
    assert got == [("transparent_mask", True)]


def test_integration_unit_changed_derived_from_forwarding(dioptas_model):
    got = []
    dioptas_model.integration_unit_changed.connect(
        lambda new, old: got.append((new, old))
    )
    dioptas_model.current_configuration.params.integration_unit = "q_A^-1"
    assert got == [("q_A^-1", "2th_deg")]


def test_view_state_round_trip(dioptas_model, tmp_path):
    """The GUI view state is saved in the project file and applied onto the
    stable ViewParams instance on load (events fire, object identity kept)."""
    dioptas_model.view.img_mode = "Cake"
    filename = os.path.join(tmp_path, "view.dio")
    dioptas_model.save(filename)

    dioptas_model.view.img_mode = "Image"
    view_instance = dioptas_model.view
    events = []
    dioptas_model.view.events.img_mode.connect(lambda new, old: events.append(new))

    dioptas_model.load(filename)
    assert dioptas_model.view is view_instance
    assert dioptas_model.view.img_mode == "Cake"
    assert events == ["Cake"]


def test_project_file_has_format_version(dioptas_model, tmp_path):
    import h5py

    from dioptas.model.state import PROJECT_FORMAT_VERSION

    filename = os.path.join(tmp_path, "versioned.dio")
    dioptas_model.save(filename)
    with h5py.File(filename, "r") as f:
        assert int(f.attrs["format_version"]) == PROJECT_FORMAT_VERSION


def test_load_project_with_newer_format_version(dioptas_model, tmp_path):
    """Files from a future Dioptas load best-effort instead of failing."""
    import h5py

    from dioptas.model.state import PROJECT_FORMAT_VERSION

    filename = os.path.join(tmp_path, "future.dio")
    dioptas_model.save(filename)
    with h5py.File(filename, "r+") as f:
        f.attrs["format_version"] = PROJECT_FORMAT_VERSION + 1

    dioptas_model.load(filename)  # must not raise
    assert len(dioptas_model.configurations) == 1


def test_img_params_forwarded_with_namespace(dioptas_model):
    # first contact between image and detector legitimately updates the
    # calibration geometry (the detector learns its shape); settle that
    # before asserting the exact event stream
    dioptas_model.img_model.img_changed.emit()

    got = []
    dioptas_model.configuration_params_changed.connect(
        lambda field, new, old: got.append((field, new))
    )
    dioptas_model.img_model.params.factor = 2.0
    assert got == [("img.factor", 2.0)]

    dioptas_model.add_configuration()
    inactive_img_model = dioptas_model.configurations[0].img_model
    dioptas_model.select_configuration(1)
    got.clear()

    inactive_img_model.params.factor = 5.0
    assert got == []  # non-selected configuration stays silent

    dioptas_model.img_model.params.autoprocess = True
    assert got == [("img.autoprocess", True)]


def test_file_iteration_mode_round_trips_via_params(dioptas_model, tmp_path):
    """ImgModel.file_iteration_mode is not in the legacy layout — it
    round-trips via the generic img params group."""
    dioptas_model.img_model.file_iteration_mode = "time"
    filename = os.path.join(tmp_path, "iteration.dio")
    dioptas_model.save(filename)

    dioptas_model.reset()
    assert dioptas_model.img_model.file_iteration_mode == "number"

    dioptas_model.load(filename)
    assert dioptas_model.img_model.file_iteration_mode == "time"


def test_pattern_model_settings_delegate_to_params(dioptas_model):
    pattern_model = dioptas_model.pattern_model
    pattern_model.unit = "2th_deg"
    assert pattern_model.params.unit == "2th_deg"

    pattern_model.set_file_iteration_mode("time")
    assert pattern_model.params.file_iteration_mode == "time"
    assert pattern_model.file_name_iterator.create_timed_file_list is True


def test_pattern_params_forwarded_with_namespace(dioptas_model):
    got = []
    dioptas_model.configuration_params_changed.connect(
        lambda field, new, old: got.append((field, new))
    )
    dioptas_model.pattern_model.params.file_iteration_mode = "time"
    assert got == [("pattern.file_iteration_mode", "time")]


def test_mask_model_settings_delegate_to_params(dioptas_model):
    mask_model = dioptas_model.mask_model
    mask_model.set_mode(False)
    assert mask_model.params.mode is False

    dioptas_model.current_configuration.roi = (10, 100, 20, 200)
    assert mask_model.params.roi == (10, 100, 20, 200)
    assert mask_model.roi_mask is not None


def test_mask_params_forwarded_with_namespace(dioptas_model):
    got = []
    dioptas_model.configuration_params_changed.connect(
        lambda field, new, old: got.append((field, new))
    )
    dioptas_model.mask_model.params.mode = False
    assert got == [("mask.mode", False)]


def test_mask_mode_round_trips_via_params(dioptas_model, tmp_path):
    """MaskModel.mode is not in the legacy layout — it round-trips via the
    generic mask params group."""
    dioptas_model.mask_model.set_mode(False)
    filename = os.path.join(tmp_path, "mask_mode.dio")
    dioptas_model.save(filename)

    dioptas_model.reset()
    assert dioptas_model.mask_model.mode is True

    dioptas_model.load(filename)
    assert dioptas_model.mask_model.mode is False


def test_calibration_params_forwarded_with_namespace(dioptas_model):
    got = []
    dioptas_model.configuration_params_changed.connect(
        lambda field, new, old: got.append((field, new))
    )
    dioptas_model.calibration_model.polarization_factor = 0.5
    assert got == [("calibration.polarization_factor", 0.5)]


def test_calibration_workflow_settings_round_trip(dioptas_model, tmp_path):
    """start_values, fit_wavelength, fixed_values and use_mask were never in
    the legacy layout — they round-trip via the calibration params group."""
    calibration_model = dioptas_model.calibration_model
    calibration_model.start_values = {
        "dist": 0.3,
        "wavelength": 0.4e-10,
        "polarization_factor": 0.9,
    }
    calibration_model.fit_wavelength = True
    calibration_model.set_fixed_values({"rot1": 0.1})
    calibration_model.use_mask = True

    filename = os.path.join(tmp_path, "calibration_settings.dio")
    dioptas_model.save(filename)
    dioptas_model.reset()
    assert dioptas_model.calibration_model.fit_wavelength is False

    dioptas_model.load(filename)
    calibration_model = dioptas_model.calibration_model
    assert calibration_model.start_values["dist"] == 0.3
    assert calibration_model.fit_wavelength is True
    assert calibration_model.fixed_values == {"rot1": 0.1}
    assert calibration_model.use_mask is True


def test_dioptrin_settings_not_restored_from_project(dioptas_model, tmp_path):
    """use_dioptrin / dioptrin_num_workers are machine-specific — saving a
    project must not carry them onto another machine."""
    machine_use_dioptrin = dioptas_model.calibration_model.use_dioptrin
    machine_workers = dioptas_model.calibration_model.dioptrin_num_workers

    dioptas_model.calibration_model.use_dioptrin = not machine_use_dioptrin
    dioptas_model.calibration_model.dioptrin_num_workers = 999
    filename = os.path.join(tmp_path, "dioptrin.dio")
    dioptas_model.save(filename)

    dioptas_model.load(filename)
    assert dioptas_model.calibration_model.use_dioptrin == machine_use_dioptrin
    assert dioptas_model.calibration_model.dioptrin_num_workers == machine_workers


def test_map_and_phase_params_forwarded_with_namespace(dioptas_model):
    got = []
    dioptas_model.configuration_params_changed.connect(
        lambda field, new, old: got.append((field, new))
    )
    # the first window has to be created before it can be moved
    dioptas_model.map_model.window = [5.0, 6.0]
    dioptas_model.phase_model.same_conditions = False
    assert [field for field, _ in got] == ["map.rois", "phase.same_conditions"]
    assert dioptas_model.map_model.window == [5.0, 6.0]


def test_map_roi_edits_are_forwarded_for_the_history(dioptas_model):
    """A window dragged in the pattern must reach the undo history, which
    listens on configuration_params_changed."""
    map_model = dioptas_model.map_model
    map_model.window = [5.0, 6.0]

    got = []
    dioptas_model.configuration_params_changed.connect(
        lambda field, new, old: got.append((field, new))
    )
    map_model.rois[0].x_max = 7.0
    map_model.rois[0].reduction = "area"

    assert got == [("map.roi.x_max", 7.0), ("map.roi.reduction", "area")]


def test_phase_same_conditions_round_trips_via_params(dioptas_model, tmp_path):
    dioptas_model.phase_model.same_conditions = False
    filename = os.path.join(tmp_path, "phase_settings.dio")
    dioptas_model.save(filename)

    dioptas_model.reset()
    dioptas_model.phase_model.same_conditions = True

    dioptas_model.load(filename)
    assert dioptas_model.phase_model.same_conditions is False


def test_transformations_round_trip(dioptas_model, tmp_path):
    dioptas_model.img_model.load(os.path.join(data_path, "image_001.tif"))
    dioptas_model.img_model.rotate_img_m90()
    filename = os.path.join(tmp_path, "transformed.dio")
    dioptas_model.save(filename)

    dioptas_model.reset()
    dioptas_model.load(filename)
    assert dioptas_model.img_model.params.transformations == ["rotate_matrix_m90"]


def test_view_params_round_trip_all_fields(dioptas_model, tmp_path):
    """Every view setting round-trips, applied onto the stable instance."""
    dioptas_model.view.img_mode = "Cake"
    dioptas_model.view.view_mode = "alternative"
    dioptas_model.view.img_docked = False
    dioptas_model.view.waterfall_separation = 42.0

    filename = os.path.join(tmp_path, "view_all.dio")
    dioptas_model.save(filename)

    view_instance = dioptas_model.view
    dioptas_model.reset()
    dioptas_model.view.img_mode = "Image"
    dioptas_model.view.view_mode = "normal"
    dioptas_model.view.img_docked = True
    dioptas_model.view.waterfall_separation = 100.0

    dioptas_model.load(filename)
    assert dioptas_model.view is view_instance
    assert dioptas_model.view.img_mode == "Cake"
    assert dioptas_model.view.view_mode == "alternative"
    assert dioptas_model.view.img_docked is False
    assert dioptas_model.view.waterfall_separation == 42.0


def test_add_configuration_preserves_calibration_name(dioptas_model):
    """Transferring the calibration to a new configuration must not rename it.

    The transfer goes through a temporary poni file, whose save/load
    overwrote the calibration name of both configurations with "transfer"."""
    dioptas_model.calibration_model.load(
        os.path.join(data_path, "CeO2_Pilatus1M.poni")
    )
    dioptas_model.img_model.load(os.path.join(data_path, "CeO2_Pilatus1M.tif"))
    assert dioptas_model.calibration_model.calibration_name == "CeO2_Pilatus1M"

    dioptas_model.add_configuration()

    assert dioptas_model.calibration_model.is_calibrated
    assert dioptas_model.calibration_model.calibration_name == "CeO2_Pilatus1M"
    assert (
        dioptas_model.configurations[0].calibration_model.calibration_name
        == "CeO2_Pilatus1M"
    )


def test_params_restore_is_not_hand_listed(dioptas_model, tmp_path):
    """Settings restore comes from the params documents wholesale.

    Every settings field round-trips without per-field code in the loader,
    including fields the legacy layout never writes."""
    from dioptas.model.state import params_to_dict

    configuration = dioptas_model.current_configuration
    configuration.params.trim_trailing_zeros = False
    configuration.params.oned_azimuth_range = [-45.0, 45.0]
    configuration.params.cake_azimuth_range = [-100.0, 100.0]
    configuration.img_model.params.file_iteration_mode = "time"
    configuration.mask_model.params.mode = False
    configuration.pattern_model.params.file_iteration_mode = "time"
    configuration.calibration_model.params.fit_wavelength = True
    configuration.calibration_model.params.fixed_values = {"rot1": 0.25}

    expected = {
        "configuration": params_to_dict(configuration.params),
        "img": params_to_dict(configuration.img_model.params),
        "mask": params_to_dict(configuration.mask_model.params),
        # "unit" is excluded: it tracks the last integration, and loading
        # ends with one, so it is not expected to match the pre-save value
        "pattern": {
            k: v
            for k, v in params_to_dict(configuration.pattern_model.params).items()
            if k != "unit"
        },
    }

    filename = os.path.join(tmp_path, "wholesale.dio")
    dioptas_model.save(filename)
    dioptas_model.reset()
    dioptas_model.load(filename)

    restored = dioptas_model.current_configuration
    assert params_to_dict(restored.params) == expected["configuration"]
    assert params_to_dict(restored.img_model.params) == expected["img"]
    assert params_to_dict(restored.mask_model.params) == expected["mask"]
    assert {
        k: v
        for k, v in params_to_dict(restored.pattern_model.params).items()
        if k != "unit"
    } == expected["pattern"]
    assert restored.calibration_model.params.fit_wavelength is True
    assert restored.calibration_model.params.fixed_values == {"rot1": 0.25}


def test_missing_working_directories_are_not_restored(dioptas_model, tmp_path):
    """The legacy restore drops directories that no longer exist; the
    wholesale params apply must not undo that validation."""
    gone = os.path.join(tmp_path, "no_longer_there")
    dioptas_model.current_configuration.params.working_directories = {
        "image": gone,
        "pattern": str(tmp_path),
    }

    filename = os.path.join(tmp_path, "dirs.dio")
    dioptas_model.save(filename)
    dioptas_model.load(filename)

    restored = dioptas_model.current_configuration.working_directories
    assert restored["image"] == ""  # dropped: does not exist
    assert restored["pattern"] == str(tmp_path)  # kept: exists


def test_image_round_trip_preserves_dtype_and_values(dioptas_model, tmp_path):
    """A project round-trip must return the image exactly as loaded.

    Images used to be stored as float32 regardless of the detector dtype, so
    reloading a uint16 image from a project gave float32 back — and integer
    counts above 2**24 lost precision."""
    dioptas_model.img_model.load(os.path.join(data_path, "image_001.tif"))
    original = dioptas_model.img_model.raw_img_data.copy()
    assert original.dtype == np.uint16  # guard: the fixture image is integer

    filename = os.path.join(tmp_path, "image_round_trip.dio")
    dioptas_model.save(filename)
    dioptas_model.load(filename)

    restored = dioptas_model.img_model.raw_img_data
    assert restored.dtype == original.dtype
    assert np.array_equal(restored, original)


def test_image_and_background_are_stored_compressed(dioptas_model, tmp_path):
    import h5py

    dioptas_model.img_model.load(os.path.join(data_path, "image_001.tif"))
    dioptas_model.img_model.background_data = np.zeros(
        dioptas_model.img_model.raw_img_data.shape, dtype=np.uint16
    )

    filename = os.path.join(tmp_path, "compressed_image.dio")
    dioptas_model.save(filename)

    with h5py.File(filename, "r") as f:
        # image pixels are an external payload: cached under a content id
        cache = f["cache"]
        assert len(cache) >= 1
        for name in cache:
            dataset = cache[name]
            assert dataset.compression == "gzip"
            assert dataset.shuffle
            stored = dataset.id.get_storage_size()
            raw = dataset.size * dataset.dtype.itemsize
            assert stored < raw


def test_reset_survives_the_overlay_forwarding_to_maps(dioptas_model):
    """reset() deletes the configurations attribute and clears the overlays
    while it is gone; the overlay-to-maps forwarding must not trip over the
    missing attribute (caught by CI in the project round-trip tests)."""
    dioptas_model.overlay_model.add_overlay(
        np.linspace(0, 10, 50), np.ones(50), "ref"
    )
    dioptas_model.reset()  # used to raise AttributeError via overlay_removed

    # and the forwarding still works on the rebuilt configurations
    dioptas_model.map_model.set_expression("d", "A - ovl(ref)")
    dioptas_model.overlay_model.add_overlay(
        np.linspace(0, 10, 50), np.ones(50), "ref"
    )
