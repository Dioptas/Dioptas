import os
import numpy as np
from dioptas.model.Configuration import Configuration
from ..utility import unittest_data_path


def test_auto_save_patterns(tmp_path):
    config = Configuration()
    config.calibration_model.is_calibrated = True
    config.auto_save_integrated_pattern = True
    config.working_directories["pattern"] = tmp_path
    config.img_model.load(os.path.join(unittest_data_path, "image_001.tif"))
    config.integrate_image_1d()

    assert os.path.exists(os.path.join(tmp_path, "image_001.xy"))


def test_auto_save_background_subtracted_pattern(tmp_path):
    config = Configuration()
    config.calibration_model.is_calibrated = True
    config.auto_save_integrated_pattern = True
    config.working_directories["pattern"] = tmp_path
    config.img_model.load(os.path.join(unittest_data_path, "image_001.tif"))
    config.pattern_model.set_auto_background_subtraction([2, 50, 50])
    config.integrate_image_1d()

    assert os.path.exists(os.path.join(tmp_path, "image_001.xy"))
    assert os.path.exists(os.path.join(tmp_path, "bkg_subtracted", "image_001.xy"))


# ---------------------------------------------------------------------------
# Property getter/setter tests
# ---------------------------------------------------------------------------


def test_integration_rad_points_property():
    config = Configuration()
    assert config.integration_rad_points is None
    config.params.integration_rad_points = 1500
    assert config.integration_rad_points == 1500


def test_calculate_poisson_errors_property():
    config = Configuration()
    assert config.calculate_poisson_errors is False
    config.calculate_poisson_errors = True
    assert config.params.calculate_poisson_errors is True


def test_oned_azimuth_range_property():
    config = Configuration()
    assert config.oned_azimuth_range is None
    config.params.oned_azimuth_range = [0.0, 180.0]
    assert config.oned_azimuth_range == [0.0, 180.0]
    config.params.oned_azimuth_range = None
    assert config.oned_azimuth_range is None


def test_cake_azimuth_range_property():
    config = Configuration()
    assert config.cake_azimuth_range is None
    config.params.cake_azimuth_range = [-180.0, 180.0]
    assert config.cake_azimuth_range == [-180.0, 180.0]
    config.params.cake_azimuth_range = None
    assert config.cake_azimuth_range is None


def test_integration_unit_property():
    config = Configuration()
    assert config.integration_unit == "2th_deg"
    config.params.integration_unit = "q_A^-1"
    assert config.integration_unit == "q_A^-1"


def test_correct_solid_angle_property():
    config = Configuration()
    original = config.correct_solid_angle
    config.calibration_model.correct_solid_angle = not original
    assert config.correct_solid_angle == (not original)


def test_auto_integrate_cake_property():
    config = Configuration()
    assert config.auto_integrate_cake is False
    config.auto_integrate_cake = True
    assert config.auto_integrate_cake is True
    # setting same value again should be a no-op
    config.auto_integrate_cake = True
    assert config.auto_integrate_cake is True
    config.auto_integrate_cake = False
    assert config.auto_integrate_cake is False


def test_auto_integrate_pattern_property():
    config = Configuration()
    assert config.auto_integrate_pattern is True
    config.auto_integrate_pattern = False
    assert config.auto_integrate_pattern is False
    # setting same value again should be a no-op
    config.auto_integrate_pattern = False
    assert config.auto_integrate_pattern is False
    config.auto_integrate_pattern = True
    assert config.auto_integrate_pattern is True


def test_auto_save_integrated_pattern_property():
    config = Configuration()
    assert config.auto_save_integrated_pattern is False
    config.auto_save_integrated_pattern = True
    assert config.auto_save_integrated_pattern is True


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

def _load_calibrated_config():
    """Helper: return a Configuration with calibration and image loaded."""
    config = Configuration()
    config.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    config.img_model.load(os.path.join(unittest_data_path, "CeO2_Pilatus1M.tif"))
    return config


def test_integrate_image_2d():
    config = _load_calibrated_config()
    config.integrate_image_2d()
    assert config.cake_img is not None
    assert config.cake_img.shape[0] > 0
    assert config.cake_img.shape[1] > 0


# ---------------------------------------------------------------------------
# save_pattern tests
# ---------------------------------------------------------------------------

def test_save_pattern_xy(tmp_path):
    config = _load_calibrated_config()
    config.integrate_image_1d()
    out = os.path.join(tmp_path, "output.xy")
    config.save_pattern(out)
    assert os.path.exists(out)
    assert os.path.getsize(out) > 0


def test_save_pattern_fxye(tmp_path):
    config = _load_calibrated_config()
    config.integrate_image_1d()
    out = os.path.join(tmp_path, "output.fxye")
    config.save_pattern(out)
    assert os.path.exists(out)
    assert os.path.getsize(out) > 0


def test_integrate_and_save_pattern_xye_with_poisson_errors(tmp_path):
    config = _load_calibrated_config()
    config.calculate_poisson_errors = True

    assert config.pattern_model.errors is not None
    out = os.path.join(tmp_path, "output.xye")
    config.save_pattern(out)

    saved = np.loadtxt(out)
    assert saved.shape[1] == 3
    np.testing.assert_allclose(saved[:, 2], config.pattern_model.errors)


def test_save_pattern_chi(tmp_path):
    config = _load_calibrated_config()
    config.integrate_image_1d()
    out = os.path.join(tmp_path, "output.chi")
    config.save_pattern(out)
    assert os.path.exists(out)


# ---------------------------------------------------------------------------
# Header creation tests
# ---------------------------------------------------------------------------

def test_create_xy_header():
    config = _load_calibrated_config()
    header = config._create_xy_header()
    assert isinstance(header, str)
    assert len(header) > 0
    assert "2th_deg" in header


def test_create_fxye_header():
    config = _load_calibrated_config()
    header = config._create_fxye_header("test.fxye")
    assert isinstance(header, str)
    assert len(header) > 0
    assert "DIOPTAS" in header
    assert "FXYE" in header


def test_create_fxye_header_q_unit():
    config = _load_calibrated_config()
    config.params.integration_unit = "q_A^-1"
    header = config._create_fxye_header("test.fxye")
    assert "CONQ" in header


# ---------------------------------------------------------------------------
# copy() test
# ---------------------------------------------------------------------------

def test_copy():
    config = _load_calibrated_config()
    config.working_directories["pattern"] = "/some/path"
    copied = config.copy()
    # image data should match
    import numpy as np
    np.testing.assert_array_equal(copied.img_model._img_data, config.img_model._img_data)
    # calibration should be set
    assert copied.calibration_model.is_calibrated
    # working directories should be shared
    assert copied.working_directories["pattern"] == "/some/path"


# ---------------------------------------------------------------------------
# update_mask_dimension test
# ---------------------------------------------------------------------------

def test_update_mask_dimension():
    config = Configuration()
    config.img_model.load(os.path.join(unittest_data_path, "CeO2_Pilatus1M.tif"))
    img_shape = config.img_model._img_data.shape
    mask_shape = config.mask_model.get_mask().shape
    assert mask_shape == img_shape


# ---------------------------------------------------------------------------
# HDF5 round-trip test
# ---------------------------------------------------------------------------

def _calibrated_model():
    """A DioptasModel whose current configuration is calibrated with an
    image loaded — the round-trip tests below go through the model, since
    project files are written for the whole model rather than per
    configuration."""
    from dioptas.model.DioptasModel import DioptasModel

    model = DioptasModel()
    config = model.current_configuration
    config.calibration_model.load(
        os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    )
    config.img_model.load(os.path.join(unittest_data_path, "CeO2_Pilatus1M.tif"))
    return model, config


def test_save_and_load_hdf5_round_trip(tmp_path):
    import h5py
    import numpy as np

    # Set up a fully configured Configuration
    model, config = _calibrated_model()
    config.integrate_image_1d()

    config.use_mask = True
    config.transparent_mask = True
    config.params.integration_unit = "q_A^-1"
    config.params.integration_rad_points = 2000
    config.params.calculate_poisson_errors = True
    config.params.cake_azimuth_points = 180
    config.params.cake_azimuth_range = [-90.0, 90.0]
    config.auto_save_integrated_pattern = True
    config.integrated_patterns_file_formats = [".xy", ".fxye"]

    config.working_directories["calibration"] = str(tmp_path)
    config.working_directories["mask"] = str(tmp_path)
    config.working_directories["pattern"] = str(tmp_path)

    # Create a mask with some pixels masked
    mask = np.zeros(config.img_model._img_data.shape, dtype=bool)
    mask[0:10, 0:10] = True
    config.mask_model.set_mask(mask)

    # Add a correction (oiadac is lightweight)
    from dioptas.model.util.ImgCorrection import ObliqueAngleDetectorAbsorptionCorrection
    tth_array = 180.0 / np.pi * config.calibration_model.tth_array
    azi_array = 180.0 / np.pi * config.calibration_model.azi_array
    oiadac = ObliqueAngleDetectorAbsorptionCorrection(
        tth_array=tth_array, azi_array=azi_array
    )
    oiadac.set_params({"detector_thickness": 0.03, "absorption_length": 0.3, "tilt": 0.0, "rotation": 0.0})
    oiadac.update()
    config.img_model.add_img_correction(oiadac, "oiadac")

    # loading replaces the configurations, so what is compared afterwards
    # has to be captured first
    expected_image = np.copy(config.img_model._img_data)

    # round-trip through a project file: configurations are saved and
    # loaded as part of the model now (see state/project.py)
    project_path = os.path.join(tmp_path, "test_project.dio")
    model.save(project_path)
    model.load(project_path)
    loaded = model.current_configuration

    # Verify general information
    assert loaded.integration_unit == "q_A^-1"
    assert loaded.integration_rad_points == 2000
    assert loaded.calculate_poisson_errors is True
    assert loaded.use_mask == True
    assert loaded.transparent_mask == True
    assert loaded.auto_save_integrated_pattern == True
    assert loaded.integrated_patterns_file_formats == [".xy", ".fxye"]
    assert loaded.cake_azimuth_points == 180
    assert loaded.cake_azimuth_range is not None
    np.testing.assert_allclose(loaded.cake_azimuth_range, [-90.0, 90.0])

    # Verify working directories (they may be empty strings if dirs don't exist on load,
    # but tmp_path should still exist during test)
    assert loaded.working_directories["calibration"] == str(tmp_path)
    assert loaded.working_directories["mask"] == str(tmp_path)
    assert loaded.working_directories["pattern"] == str(tmp_path)

    # Verify calibration
    assert loaded.calibration_model.is_calibrated

    # Verify image data shape
    assert loaded.img_model._img_data.shape == expected_image.shape
    np.testing.assert_array_almost_equal(
        loaded.img_model._img_data, expected_image, decimal=3
    )

    # Verify mask
    loaded_mask = loaded.mask_model.get_mask()
    assert loaded_mask[0, 0] == True
    assert loaded_mask.shape == mask.shape

    # Verify correction was loaded
    assert loaded.img_model.has_corrections()

    # Verify pattern was loaded
    assert loaded.pattern_model.pattern is not None


def test_save_and_load_hdf5_no_corrections(tmp_path):
    """Round-trip without corrections or background to cover default branches."""
    import h5py
    import numpy as np

    model, config = _calibrated_model()
    config.integrate_image_1d()

    # loading replaces the configurations, so what is compared afterwards
    # has to be captured first
    expected_shape = config.img_model._img_data.shape

    project_path = os.path.join(tmp_path, "test_minimal.dio")
    model.save(project_path)
    model.load(project_path)
    loaded = model.current_configuration

    assert loaded.calibration_model.is_calibrated
    assert loaded.img_model._img_data.shape == expected_shape
    assert loaded.integration_unit == "2th_deg"


def test_save_and_load_hdf5_with_cake_azimuth_range_none(tmp_path):
    """Verify that cake_azimuth_range=None round-trips correctly."""
    import h5py

    model, config = _calibrated_model()
    config.integrate_image_1d()
    config.params.cake_azimuth_range = None

    project_path = os.path.join(tmp_path, "test_cake_none.dio")
    model.save(project_path)
    model.load(project_path)
    loaded = model.current_configuration

    assert loaded.cake_azimuth_range is None



# ---------------------------------------------------------------------------
# Params state layer
# ---------------------------------------------------------------------------


def test_properties_delegate_to_params():
    config = Configuration()
    config.use_mask = True
    config.transparent_mask = True
    config.trim_trailing_zeros = False
    assert config.params.use_mask is True
    assert config.params.transparent_mask is True
    assert config.params.trim_trailing_zeros is False

    config.params.use_mask = False
    assert config.use_mask is False


def test_property_changes_emit_params_events():
    config = Configuration()
    got = []
    config.params.events.use_mask.connect(lambda new, old: got.append((new, old)))
    config.use_mask = True
    assert got == [(True, False)]


def test_working_directories_passed_by_reference():
    directories = {"image": "/somewhere"}
    config = Configuration(directories)
    assert config.working_directories is directories


def test_direct_params_writes_trigger_same_reactions_as_properties():
    """Uniform writes: a direct params write behaves like the property write."""
    from unittest.mock import MagicMock

    config = Configuration()
    config.pattern_integration.recompute = MagicMock()
    config.cake_integration.invalidate = MagicMock()

    config.params.integration_rad_points = 1500
    config.pattern_integration.recompute.assert_called_once()
    config.cake_integration.invalidate.assert_called_once()

    config.params.auto_integrate_cake = True
    assert config.cake_integration.active is True
    config.params.auto_integrate_pattern = False
    assert config.pattern_integration.active is False

    config.calibration_model.params.correct_solid_angle = False
    config.cake_integration.invalidate.assert_called()


def test_copy_carries_all_settings():
    """copy() copies every settings tree generically, not a hand-picked subset."""
    config = _load_calibrated_config()
    config.use_mask = True
    config.transparent_mask = True
    config.integration_unit = "q_A^-1"
    config.cake_azimuth_points = 720
    config.params.oned_azimuth_range = [-90.0, 90.0]
    config.img_model.params.factor = 3.0
    config.mask_model.params.mode = False
    config.calibration_model.params.polarization_factor = 0.5

    copied = config.copy()

    assert copied.use_mask is True
    assert copied.transparent_mask is True
    assert copied.integration_unit == "q_A^-1"
    assert copied.cake_azimuth_points == 720
    assert copied.oned_azimuth_range == [-90.0, 90.0]
    assert copied.img_model.factor == 3.0
    assert copied.mask_model.mode is False
    assert copied.calibration_model.polarization_factor == 0.5


def test_copy_does_not_share_mutable_settings():
    config = _load_calibrated_config()
    copied = config.copy()

    copied.params.working_directories["image"] = "/copied/only"
    assert config.working_directories["image"] != "/copied/only"


def test_apply_params_preserves_instance_and_fires_events():
    from dioptas.model.state import ConfigurationParams, apply_params

    target = ConfigurationParams()
    source = ConfigurationParams(use_mask=True, cake_azimuth_points=720)
    got = []
    target.events.use_mask.connect(lambda new, old: got.append(new))

    apply_params(target, source)

    assert target.use_mask is True
    assert target.cake_azimuth_points == 720
    assert got == [True]  # subscriptions on the target stayed valid
