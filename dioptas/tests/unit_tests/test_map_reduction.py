# SPDX-License-Identifier: MIT

import numpy as np
import pytest

from dioptas.model import map_reduction


X = np.linspace(5.0, 15.0, 501)


def gaussian(center, fwhm=0.5, amplitude=100.0, background=0.0, slope=0.0):
    sigma = fwhm / (2 * np.sqrt(2 * np.log(2)))
    peak = amplitude * np.exp(-0.5 * ((X - center) / sigma) ** 2)
    return peak + background + slope * (X - X[0])


def test_sum_counts_everything_in_the_window():
    intensities = np.vstack([np.ones_like(X), 2 * np.ones_like(X)])
    result = map_reduction.reduce_window(X, intensities, (9, 11), "sum")
    n = len(map_reduction.window_indices(X, (9, 11)))
    np.testing.assert_allclose(result, [n, 2 * n])


def test_mean_and_max():
    intensities = np.vstack([gaussian(10.0)])
    assert map_reduction.reduce_window(
        X, intensities, (9, 11), "max"
    )[0] == pytest.approx(100.0, rel=1e-3)
    assert map_reduction.reduce_window(X, intensities, (9, 11), "mean")[0] > 0


def test_area_is_blind_to_a_sloping_background():
    """The point of the peak-area reduction: two points with the same peak on
    very different backgrounds must map to the same value."""
    flat = gaussian(10.0, fwhm=0.5, background=0.0)
    on_a_ramp = gaussian(10.0, fwhm=0.5, background=500.0, slope=30.0)
    intensities = np.vstack([flat, on_a_ramp])

    areas = map_reduction.reduce_window(X, intensities, (9, 11), "area")
    assert areas[0] == pytest.approx(areas[1], rel=1e-3)

    # a plain sum, by contrast, is dominated by the background
    sums = map_reduction.reduce_window(X, intensities, (9, 11), "sum")
    assert sums[1] > 10 * sums[0]


def test_center_tracks_the_peak_position():
    """A shifting peak position is what makes a strain map."""
    intensities = np.vstack(
        [gaussian(c, fwhm=0.4, background=200.0) for c in (9.8, 10.0, 10.2)]
    )
    centers = map_reduction.reduce_window(X, intensities, (9, 11), "center")
    np.testing.assert_allclose(centers, [9.8, 10.0, 10.2], atol=0.01)


def test_center_survives_a_sloping_background():
    sloped = gaussian(10.0, fwhm=0.4, background=100.0, slope=40.0)
    center = map_reduction.reduce_window(X, np.vstack([sloped]), (9, 11), "center")
    assert center[0] == pytest.approx(10.0, abs=0.02)


def test_width_recovers_the_fwhm():
    intensities = np.vstack(
        [gaussian(10.0, fwhm=f, background=50.0) for f in (0.3, 0.6, 1.0)]
    )
    widths = map_reduction.reduce_window(X, intensities, (8, 12), "width")
    np.testing.assert_allclose(widths, [0.3, 0.6, 1.0], rtol=0.03)


def test_width_is_nan_when_the_peak_runs_off_the_window():
    # a monotonic ramp never comes back down to half maximum
    ramp = np.vstack([X.copy()])
    widths = map_reduction.reduce_window(X, ramp, (9, 11), "width")
    assert np.isnan(widths[0])


def test_reductions_work_on_a_descending_axis():
    """d spacing runs the other way round; nothing may depend on the order."""
    x_descending = X[::-1]
    intensities = np.vstack([gaussian(10.0, fwhm=0.5, background=100.0)[::-1]])

    area = map_reduction.reduce_window(x_descending, intensities, (9, 11), "area")
    center = map_reduction.reduce_window(x_descending, intensities, (9, 11), "center")
    width = map_reduction.reduce_window(x_descending, intensities, (8, 12), "width")

    assert area[0] > 0
    assert center[0] == pytest.approx(10.0, abs=0.02)
    assert width[0] == pytest.approx(0.5, rel=0.05)


def test_empty_window_gives_nan():
    intensities = np.vstack([np.ones_like(X), np.ones_like(X)])
    result = map_reduction.reduce_window(X, intensities, (100, 200), "sum")
    assert np.all(np.isnan(result))


def test_explicit_background_subtraction_on_a_sum():
    flat = gaussian(10.0, fwhm=0.5, background=1000.0)
    plain = map_reduction.reduce_window(X, np.vstack([flat]), (9, 11), "sum")
    subtracted = map_reduction.reduce_window(
        X, np.vstack([flat]), (9, 11), "sum", subtract_background=True
    )
    assert subtracted[0] < plain[0] / 10


def test_unknown_reduction_is_rejected():
    with pytest.raises(ValueError):
        map_reduction.reduce_window(X, np.vstack([X]), (9, 11), "nonsense")