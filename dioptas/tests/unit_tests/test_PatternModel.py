# SPDX-License-Identifier: MIT

import pytest
from pytest import approx
import os
import numpy as np
from xypattern import Pattern
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


def test_save_xye_uses_stored_errors(pattern_model: PatternModel, tmp_path):
    x = np.array([1.0, 2.0, 3.0])
    y = np.array([10.0, 20.0, 30.0])
    errors = np.array([0.1, 0.2, 0.3])
    pattern_model.set_pattern(x, y, errors=errors)

    filename = tmp_path / "pattern.xye"
    pattern_model.save_pattern(str(filename))

    np.testing.assert_allclose(np.loadtxt(filename), np.column_stack((x, y, errors)))


def test_save_fxye_uses_stored_errors(pattern_model: PatternModel, tmp_path):
    x = np.array([1.0, 2.0, 3.0])
    y = np.array([10.0, 20.0, 30.0])
    errors = np.array([0.1, 0.2, 0.3])
    pattern_model.set_pattern(x, y, errors=errors)

    filename = tmp_path / "pattern.fxye"
    pattern_model.save_pattern(
        str(filename), "BANK NUM_POINTS MIN_X_VAL STEP_X_VAL FXYE"
    )

    saved = np.loadtxt(filename, skiprows=1)
    np.testing.assert_allclose(saved[:, 0], 100 * x)
    np.testing.assert_allclose(saved[:, 1], y)
    np.testing.assert_allclose(saved[:, 2], errors)


def test_save_xye_aligns_errors_with_auto_background_roi(
    pattern_model: PatternModel, tmp_path
):
    x = np.linspace(0.0, 24.0, 250)
    y = x * 0.4 + 5.0 + gaussian(x, 10, 3, 0.2)
    errors = np.linspace(0.1, 1.0, len(x))
    pattern_model.set_pattern(x, y, errors=errors)
    pattern_model.set_auto_background_subtraction([2, 10, 5], roi=[5, 15])

    filename = tmp_path / "pattern.xye"
    pattern_model.save_pattern(str(filename), subtract_background=True)

    saved = np.loadtxt(filename)
    selected = (5 < x) & (x < 15)
    np.testing.assert_allclose(saved[:, 0], x[selected])
    np.testing.assert_allclose(saved[:, 2], errors[selected])


def test_save_fxye_aligns_errors_with_shorter_background(
    pattern_model: PatternModel, tmp_path
):
    x = np.linspace(0.0, 24.0, 100)
    y = x + 10
    errors = np.linspace(0.1, 1.0, len(x))
    pattern_model.set_pattern(x, y, errors=errors)
    pattern_model.background_pattern = Pattern(x[20:80], np.ones(60))

    filename = tmp_path / "pattern.fxye"
    pattern_model.save_pattern(
        str(filename),
        "BANK NUM_POINTS MIN_X_VAL STEP_X_VAL FXYE",
        subtract_background=True,
    )

    saved = np.loadtxt(filename, skiprows=1)
    np.testing.assert_allclose(saved[:, 0], 100 * x[20:80], rtol=1e-5)
    np.testing.assert_allclose(saved[:, 2], errors[20:80], rtol=1e-5)


def test_setting_pattern_without_errors_clears_old_errors(pattern_model: PatternModel):
    x = np.array([1.0, 2.0])
    pattern_model.set_pattern(x, x, errors=np.array([0.1, 0.2]))
    pattern_model.set_pattern(x, x)
    assert pattern_model.errors is None


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


def test_load_chi_pattern(pattern_model: PatternModel):
    """Loading a .chi file should skip the first 4 header rows."""
    pattern_model.load_pattern(os.path.join(data_path, "pattern_001.chi"))
    assert pattern_model.get_pattern().name == "pattern_001"
    assert len(pattern_model.get_pattern().x) > 0
    assert len(pattern_model.get_pattern().y) > 0


def test_save_auto_background_as_pattern(pattern_model: PatternModel, tmp_path):
    """Saving the auto background pattern should create a valid file."""
    x = np.linspace(0, 24, 2500)
    y = x * 0.4 + 5.0 + gaussian(x, 10, 3, 0.1)
    pattern_model.set_pattern(x, y)
    pattern_model.set_auto_background_subtraction([2, 50, 50])

    save_path = str(tmp_path / "auto_bkg.xy")
    pattern_model.save_auto_background_as_pattern(save_path, header="")
    assert os.path.exists(save_path)

    saved = np.loadtxt(save_path)
    assert saved.shape[0] > 0
    assert saved.shape[1] == 2


def test_load_next_file(pattern_model: PatternModel):
    """Loading next file should advance from pattern_001 to pattern_002."""
    pattern_model.load_pattern(os.path.join(data_path, "pattern_001.xy"))
    assert pattern_model.get_pattern().name == "pattern_001"

    result = pattern_model.load_next_file()
    assert result is True
    assert pattern_model.get_pattern().name == "pattern_002"


def test_load_next_file_returns_false_at_end(pattern_model: PatternModel):
    """Loading next file should return False when there is no next file."""
    pattern_model.load_pattern(os.path.join(data_path, "pattern_002.xy"))
    result = pattern_model.load_next_file()
    assert result is False


def test_load_previous_file(pattern_model: PatternModel):
    """Loading previous file should go back from pattern_002 to pattern_001."""
    pattern_model.load_pattern(os.path.join(data_path, "pattern_002.xy"))
    assert pattern_model.get_pattern().name == "pattern_002"

    result = pattern_model.load_previous_file()
    assert result is True
    assert pattern_model.get_pattern().name == "pattern_001"


def test_load_previous_file_returns_false_at_start(pattern_model: PatternModel):
    """Loading previous file should return False when there is no previous file."""
    pattern_model.load_pattern(os.path.join(data_path, "pattern_001.xy"))
    result = pattern_model.load_previous_file()
    assert result is False


def test_set_file_iteration_mode_number(pattern_model: PatternModel):
    """Setting file iteration mode to 'number' should update the mode."""
    pattern_model.set_file_iteration_mode("number")
    assert pattern_model.file_iteration_mode == "number"
    assert pattern_model.file_name_iterator.create_timed_file_list is False


def test_set_file_iteration_mode_time(pattern_model: PatternModel):
    """Setting file iteration mode to 'time' should update the mode and rebuild file list."""
    pattern_model.load_pattern(os.path.join(data_path, "pattern_001.xy"))
    pattern_model.set_file_iteration_mode("time")
    assert pattern_model.file_iteration_mode == "time"
    assert pattern_model.file_name_iterator.create_timed_file_list is True


def test_background_pattern_setter(pattern_model: PatternModel):
    """Setting a background pattern should apply it to the internal pattern."""
    x = np.linspace(0, 10, 100)
    y = np.ones(100) * 10
    pattern_model.set_pattern(x, y)

    bkg = Pattern(x, np.ones(100) * 3)
    pattern_model.background_pattern = bkg

    assert pattern_model.background_pattern is bkg
    assert pattern_model.pattern.background_pattern is bkg
    _, y_subtracted = pattern_model.pattern.data
    assert y_subtracted == approx(np.ones(100) * 7)


def test_background_pattern_setter_clear(pattern_model: PatternModel):
    """Setting the background pattern to None should clear it."""
    x = np.linspace(0, 10, 100)
    y = np.ones(100) * 10
    pattern_model.set_pattern(x, y)

    bkg = Pattern(x, np.ones(100) * 3)
    pattern_model.background_pattern = bkg
    assert pattern_model.background_pattern is not None

    pattern_model.background_pattern = None
    assert pattern_model.background_pattern is None
    assert pattern_model.pattern.background_pattern is None
    _, y_data = pattern_model.pattern.data
    assert y_data == approx(np.ones(100) * 10)


def test_auto_background_params_are_canonical():
    """Direct auto-background params writes reach the pattern computation."""
    import numpy as np
    from dioptas.model.PatternModel import PatternModel

    pattern_model = PatternModel()
    pattern_model.set_pattern(np.linspace(1, 20, 200), np.ones(200) * 5)

    pattern_model.params.auto_bkg_smoothing = 0.2
    pattern_model.params.auto_bkg_iterations = 30
    pattern_model.params.auto_bkg_poly_order = 20
    pattern_model.params.auto_bkg_enabled = True

    auto_bkg = pattern_model.pattern.auto_bkg
    assert auto_bkg is not None
    assert auto_bkg.smooth_width == 0.2
    assert auto_bkg.iterations == 30
    assert auto_bkg.cheb_order == 20

    pattern_model.params.auto_bkg_enabled = False
    assert pattern_model.pattern.auto_bkg is None


def test_set_auto_background_subtraction_populates_params():
    import numpy as np
    from dioptas.model.PatternModel import PatternModel

    pattern_model = PatternModel()
    pattern_model.set_pattern(np.linspace(1, 20, 200), np.ones(200) * 5)
    pattern_model.set_auto_background_subtraction([0.5, 40, 25], roi=[3.0, 15.0])

    params = pattern_model.params
    assert params.auto_bkg_enabled is True
    assert params.auto_bkg_smoothing == 0.5
    assert params.auto_bkg_iterations == 40
    assert params.auto_bkg_poly_order == 25
    assert params.auto_bkg_roi == [3.0, 15.0]

    # user-supplied roi outside the data range is clamped at the API boundary
    pattern_model.set_auto_background_subtraction([0.5, 40, 25], roi=[-100.0, 500.0])
    assert params.auto_bkg_roi[0] >= 1.0 - 1.0
    assert params.auto_bkg_roi[1] <= 20.0 + 1.0

    pattern_model.unset_auto_background_subtraction()
    assert params.auto_bkg_enabled is False
