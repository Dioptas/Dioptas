"""Numerical and lifecycle coverage for live map window prefix sums."""
from unittest.mock import patch

import numpy as np
import pytest

from dioptas.model import map_reduction
from dioptas.model.Configuration import Configuration
from dioptas.model.MapModel import MapPointInfo


@pytest.mark.parametrize("reduction", ["sum", "mean"])
@pytest.mark.parametrize("dtype", [np.float32, np.float64, np.int32])
@pytest.mark.parametrize("order", ["ascending", "descending", "unordered"])
def test_cached_windows_match_direct_sample_selection(reduction, dtype, order):
    x = np.array([1, 2, 2, 3, 4, 5, 6], dtype=float)
    y = np.array([[2, 3, -4, 5, 8, 1, -2], [3, 9, 1, 0, -1, 7, 4]], dtype=dtype)
    indices = {
        "ascending": np.arange(len(x)),
        "descending": np.arange(len(x))[::-1],
        "unordered": np.array([1, 4, 0, 6, 2, 5, 3]),
    }[order]
    x, y = x[indices], y[:, indices]
    cache = map_reduction.WindowSumCache(y)
    for low, high in [(0, 7), (2, 5), (1, 2), (1.5, 2.5), (0, 1.5), (5.5, 7), (8, 9)]:
        selected = (x > low) & (x < high)
        expected = np.full(len(y), np.nan)
        if selected.any():
            expected = y[:, selected].astype(float).sum(axis=1)
            if reduction == "mean":
                expected /= selected.sum()
        np.testing.assert_allclose(cache.reduce(x, (low, high), reduction), expected)


@pytest.mark.parametrize("reduction", ["sum", "mean"])
def test_nonfinite_and_overflow_do_not_poison_unrelated_windows(reduction):
    x = np.arange(6, dtype=float)
    y = np.array([
        [np.nan, 1, 2, 3, 4, 5],
        [np.inf, 1, 2, 3, -np.inf, 5],
        [1, 2, -np.inf, 3, 4, np.nan],
        [1e308, 1e308, 2, 3, 4, 5],
        [1, 2, 3, 4, 5, 6],
    ])
    cache = map_reduction.WindowSumCache(y)
    for window in [(-1, 6), (0, 4), (1, 4), (2, 5), (3, 6), (8, 9)]:
        with np.errstate(invalid="ignore", over="ignore"):
            expected = map_reduction.reduce_window(x, y, window, reduction)
        np.testing.assert_allclose(cache.reduce(x, window, reduction), expected)


@pytest.mark.parametrize("reduction", ["sum", "mean"])
def test_small_windows_after_large_peaks_retain_counts(reduction):
    x = np.arange(5, dtype=float)
    y = np.array([[1e20, 1, 2, 3, 4], [1e20, 1e8, 2e8, 3e8, 4e8]])
    cache = map_reduction.WindowSumCache(y)
    np.testing.assert_array_equal(
        cache.reduce(x, (0, 5), reduction),
        [10, 1e9] if reduction == "sum" else [2.5, 2.5e8],
    )


def test_empty_channel_matrix():
    cache = map_reduction.WindowSumCache(np.empty((3, 0)))
    assert np.isnan(cache.reduce([], (0, 1))).all()


@pytest.mark.parametrize("reduction", ["sum", "mean"])
def test_fractional_signed_patterns_across_intensity_scales(reduction):
    x = np.linspace(0, 20, 1024)
    y = np.random.default_rng(17).normal(size=(32, len(x)))
    y *= np.logspace(-6, 6, len(y))[:, None]
    cache = map_reduction.WindowSumCache(y)
    for window in [(0, 20), (3, 6), (10, 10.03), (19, 20)]:
        np.testing.assert_allclose(cache.reduce(x, window, reduction),
            map_reduction.reduce_window(x, y, window, reduction),
            rtol=1e-10, atol=1e-15)


def make_model():
    m = Configuration().map_model
    x = np.arange(8, dtype=float)
    y = np.arange(1, 25, dtype=float).reshape(3, 8)
    infos = [MapPointInfo("") for _ in y]
    m.set_integration_results(x, y, infos, [], pattern_unit="q_A^-1")
    m.set_window((1, 6))
    return m


def test_one_prefix_cache_shared_across_windows_expressions_and_layout():
    with patch.object(map_reduction.np, "cumsum", wraps=np.cumsum) as cumsum:
        m = make_model()
        cache = m._window_sum_cache
        m.set_window((2, 7))
        second = m.add_roi(window=(0, 5))
        second.reduction = "mean"
        m.set_expression("Ratio", "A/B")
        m.active_layer = "Ratio"
        np.testing.assert_allclose(m.window_intensities, [22/3.5, 54/11.5, 86/19.5])
        m.set_dimension((2, 2))
        m.snake = True
        second.color = "#123456"
        assert m._window_sum_cache is cache
        assert cumsum.call_count == 1


@pytest.mark.parametrize("in_place", [False, True])
def test_publishing_changed_patterns_discards_cache_even_at_same_shape(in_place):
    m = make_model()
    original = m._window_sum_cache
    y = m.pattern_intensities if in_place else m.pattern_intensities.copy()
    y *= 3
    m.set_integration_results(m.pattern_x, y, m.point_infos, m.filepaths,
                              m.pattern_unit, keep_layout=True)
    assert m._window_sum_cache is not original
    np.testing.assert_array_equal(m.window_intensities, [54, 150, 246])
    m._reset()
    assert m._window_sum_cache is None
    assert m._layer_cache == {}


@pytest.mark.parametrize("reduction,background", [
    ("sum", True), ("mean", True), ("max", False),
    ("area", False), ("center", False), ("width", False),
])
def test_other_reductions_remain_on_direct_path(reduction, background):
    m = make_model()
    roi = m.get_roi("A")
    m._suspend_rebuild = True
    roi.reduction, roi.subtract_background = reduction, background
    m._suspend_rebuild = False
    m._patterns_changed()
    m._roi_changed()
    assert m._window_sum_cache is None
    expected = map_reduction.reduce_window(m.pattern_x, m.pattern_intensities,
        (roi.x_min, roi.x_max), reduction, background)
    np.testing.assert_allclose(m.window_intensities, expected)
