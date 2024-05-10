import os
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

