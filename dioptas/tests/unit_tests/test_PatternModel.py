# SPDX-License-Identifier: MIT

import pytest
from pytest import approx
import os
import numpy as np
from xypattern.auto_background import SmoothBrucknerBackground

from ...model.PatternModel import PatternModel
from ...model.util.PeakShapes import gaussian

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, "../data")


@pytest.fixture
def pattern_model():
    return PatternModel()


def test_set_pattern(pattern_model: PatternModel):
    x = np.linspace(0.1, 15, 100)
    y = np.sin(x)
    pattern_model.set_pattern(x, y, "hoho")
    assert pattern_model.get_pattern().x == approx(x)
    assert pattern_model.get_pattern().y == approx(y)
    assert pattern_model.get_pattern().name == "hoho"


def test_load_pattern(pattern_model: PatternModel):
    pattern_model.load_pattern(os.path.join(data_path, "pattern_001.xy"))
    assert pattern_model.get_pattern().name == "pattern_001"
    assert len(pattern_model.get_pattern().x) > 101
    assert len(pattern_model.get_pattern().y) > 101


def test_auto_background_subtraction(pattern_model: PatternModel):
    x = np.linspace(0, 24, 2500)
    y = np.zeros(x.shape)

    peaks = [
        [10, 3, 0.1],
        [12, 4, 0.1],
        [12, 6, 0.1],
    ]
    for peak in peaks:
        y += gaussian(x, peak[0], peak[1], peak[2])
    y_bkg = x * 0.4 + 5.0
    y_measurement = y + y_bkg

    pattern_model.set_pattern(x, y_measurement)

    auto_background_subtraction_parameters = [2, 50, 50]
    pattern_model.set_auto_background_subtraction(
        auto_background_subtraction_parameters
    )

    x_spec, y_spec = pattern_model.pattern.data

    assert np.sum(y_spec - y) == approx(0, abs=1e-9)


def test_auto_background_subtraction_with_out_of_range_roi(pattern_model: PatternModel):
    x = np.linspace(0, 24, 2500)
    y = np.zeros(x.shape)
    x_step = x[1] - x[0]
    x_end = x[-1]

    pattern_model.set_pattern(x, y)

    auto_background_subtraction_parameters = [2, 50, 50]
    pattern_model.set_auto_background_subtraction(
        auto_background_subtraction_parameters, roi=[25, 26]
    )

    assert pattern_model.pattern.auto_bkg_roi == [
        x_end - 1.5 * x_step,
        x_end + x_step / 2,
    ]

    pattern_model.set_auto_background_subtraction(
        auto_background_subtraction_parameters, roi=[50, 30]
    )
    assert pattern_model.pattern.auto_bkg_roi == [
        x_end - 1.5 * x_step,
        x_end + x_step / 2,
    ]

    pattern_model.set_auto_background_subtraction(
        auto_background_subtraction_parameters, roi=[23, 30]
    )
    assert pattern_model.pattern.auto_bkg_roi == [23, x_end + x_step / 2]

    pattern_model.set_auto_background_subtraction(
        auto_background_subtraction_parameters, roi=[-10, 23]
    )
    assert pattern_model.pattern.auto_bkg_roi == [x[0] - x_step / 2, 23]

    pattern_model.set_auto_background_subtraction(
        auto_background_subtraction_parameters, roi=[-10, -3]
    )
    assert pattern_model.pattern.auto_bkg_roi == [
        x[0] - x_step / 2,
        x[0] + 1.5 * x_step,
    ]
