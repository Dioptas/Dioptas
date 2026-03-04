# SPDX-License-Identifier: MIT
"""Test AutoLevel computation"""
import numpy as np
import pytest

from dioptas.widgets.plot_widgets.utils import AutoLevel


def test_default_mode():
    auto_level = AutoLevel()
    data = np.arange(1001).reshape(1, -1)
    range_ = auto_level.get_range(data)
    # Default uses 0.4th / 99.6th percentile
    assert range_ == (4.0, 996.0)


@pytest.mark.parametrize(
    "data",
    [np.array([[1, 2, 3]]), np.array([[np.inf, 3, 1, np.nan, -np.inf]])],
)
def test_minmax_mode(data):
    auto_level = AutoLevel()
    auto_level.mode = "minmax"
    data = np.array(data)
    range_ = auto_level.get_range(data)
    assert range_ == (1, 3)


def test_mean3std_mode():
    auto_level = AutoLevel()
    auto_level.filter_dummy = False
    auto_level.mode = "mean3std"
    data = np.ones(1000) * 100
    data[0:2] = 1, 1000
    data.shape = 1, -1
    range_ = auto_level.get_range(data)
    mean, std = np.mean(data), np.std(data)
    assert range_ == (mean - 3 * std, mean + 3 * std)


def test_mean3std_mode_clipped_to_minmax():
    auto_level = AutoLevel()
    auto_level.mode = "mean3std"
    data = np.array([[1, 2, 3, np.inf, np.nan, -np.inf]])
    range_ = auto_level.get_range(data)
    assert range_ == (1, 3)


@pytest.mark.parametrize(
    "mode",
    ["1percentile", "1.percentile", "1.000percentile"],
)
def test_percentil_mode(mode):
    auto_level = AutoLevel()
    auto_level.mode = mode
    data = np.arange(101).reshape(1, -1)
    range_ = auto_level.get_range(data)
    assert range_ == (1, 99)


def test_none_data():
    auto_level = AutoLevel()
    range_ = auto_level.get_range(None)
    assert range_ is None


def test_no_finite_data():
    auto_level = AutoLevel()
    data = np.array([[np.inf, np.nan, -np.inf]])
    range_ = auto_level.get_range(data)
    assert range_ is None


def test_unsupported_autoscale_mode():
    auto_level = AutoLevel()
    auto_level.mode = "unsupported"
    data = np.array([[1, 2, 3]])
    with pytest.raises(ValueError):
        range_ = auto_level.get_range(data)


def test_filter_dummy():
    auto_level = AutoLevel()
    auto_level.mode = "minmax"
    auto_level.filter_dummy = True
    data = np.array([
        [ 0,  1,  2,  3,  4],
        [-1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1],
        [ 4,  3,  2,  1,  0],
    ])
    range_ = auto_level.get_range(data)
    assert range_ == (0, 4)

    range_ = auto_level.get_range(np.transpose(data))
    assert range_ == (0, 4)
