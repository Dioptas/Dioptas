# SPDX-License-Identifier: MIT
"""Tests for the friendly error messages shown when a file of the wrong type
is loaded as an image, pattern, calibration or mask."""

import os

import pytest

from ...model.ImgModel import ImgModel
from ...model.PatternModel import PatternModel
from ...model.CalibrationModel import CalibrationModel
from ...model.MaskModel import MaskModel
from ...model.util.file_type import (
    FileLoadingError,
    detect_file_type,
    file_loading_error,
)

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, "../data")

poni_path = os.path.join(data_path, "CeO2_Pilatus1M.poni")
image_path = os.path.join(data_path, "CeO2_Pilatus1M.tif")
pattern_path = os.path.join(data_path, "pattern_001.xy")


def test_detect_file_type():
    assert detect_file_type(poni_path) == "calibration"
    assert detect_file_type(image_path) == "image"
    assert detect_file_type(pattern_path) == "pattern"
    # old-style poni content in a txt file is recognized by content
    assert (
        detect_file_type(os.path.join(data_path, "wrong_file_format.txt"))
        == "calibration"
    )


def test_message_for_missing_file():
    error = file_loading_error("/nonexistent/foo.tif", "image")
    assert "does not exist" in str(error)


@pytest.fixture
def img_model():
    return ImgModel()


@pytest.fixture
def pattern_model():
    return PatternModel()


@pytest.fixture
def mask_model():
    return MaskModel()


def test_img_model_rejects_poni_file(img_model):
    with pytest.raises(FileLoadingError) as excinfo:
        img_model.load(poni_path)
    assert "as an image" in str(excinfo.value)
    assert "Load Calibration" in str(excinfo.value)
    assert img_model.filename == ""


def test_img_model_rejects_pattern_file(img_model):
    with pytest.raises(FileLoadingError) as excinfo:
        img_model.load(pattern_path)
    assert "as an image" in str(excinfo.value)
    assert "pattern" in str(excinfo.value)


def test_pattern_model_rejects_image_file(pattern_model):
    with pytest.raises(FileLoadingError) as excinfo:
        pattern_model.load_pattern(image_path)
    assert "as a pattern" in str(excinfo.value)
    assert "Load Image" in str(excinfo.value)
    # the model state is untouched by the failed load
    assert pattern_model.pattern_filename == ""


def test_pattern_model_rejects_poni_file(pattern_model):
    with pytest.raises(FileLoadingError) as excinfo:
        pattern_model.load_pattern(poni_path)
    assert "as a pattern" in str(excinfo.value)
    assert "Load Calibration" in str(excinfo.value)


@pytest.fixture
def calibration_model(img_model):
    return CalibrationModel(img_model)


def test_calibration_model_rejects_pattern_file(calibration_model):
    with pytest.raises(FileLoadingError) as excinfo:
        calibration_model.load(pattern_path)
    assert "as a calibration" in str(excinfo.value)
    assert not calibration_model.is_calibrated


def test_calibration_model_rejects_image_file(calibration_model):
    with pytest.raises(FileLoadingError) as excinfo:
        calibration_model.load(image_path)
    assert "as a calibration" in str(excinfo.value)
    assert not calibration_model.is_calibrated


def test_calibration_model_still_loads_valid_poni(calibration_model):
    calibration_model.load(poni_path)
    assert calibration_model.is_calibrated


def test_mask_model_rejects_poni_file(mask_model):
    with pytest.raises(FileLoadingError) as excinfo:
        mask_model.load_mask(poni_path)
    assert "as a mask" in str(excinfo.value)
    assert "Load Calibration" in str(excinfo.value)
