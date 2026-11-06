# SPDX-License-Identifier: MIT

import numpy as np
import pytest

from ...widgets.plot_widgets.HistogramLUTItem import get_histogram_data
from ...widgets.plot_widgets.NormalizedImageItem import NormalizedImageItem


def test_histogram_of_uint8_image():
    """np.log of uint8 data yields float16, whose precision cannot resolve
    1500 histogram bins — the data has to be upcast before taking the log."""
    rng = np.random.default_rng(42)
    img_data = rng.integers(0, 256, size=(100, 120), dtype=np.uint8)

    left_edges, log_hist = get_histogram_data(img_data)

    assert left_edges is not None
    assert np.all(np.isfinite(left_edges))
    assert np.all(np.isfinite(log_hist))


def test_histogram_of_float_image():
    rng = np.random.default_rng(43)
    img_data = rng.random((100, 120)).astype(np.float32) * 1e6

    left_edges, log_hist = get_histogram_data(img_data)

    assert left_edges is not None
    assert np.all(np.isfinite(left_edges))


@pytest.mark.parametrize("dtype", [np.uint16, np.uint32, np.int32])
def test_repeated_integer_counts_match_full_pixel_histogram(dtype):
    rng = np.random.default_rng(44)
    image = rng.integers(0, 600, size=(600, 700)).astype(dtype)
    image[1, 1] = np.iinfo(dtype).max
    if np.dtype(dtype).kind == "i":
        image[2, 2] = -50
    expected_image = image.astype(np.float32) if image.dtype.itemsize < 4 else image
    with np.errstate(divide="ignore", invalid="ignore"):
        logs = np.log(expected_image)
    counts, edges = np.histogram(logs[np.isfinite(logs)], bins=1500)
    actual_edges, actual_counts = get_histogram_data(image)
    np.testing.assert_array_equal(actual_edges, edges[:-1][counts > 0])
    np.testing.assert_array_equal(actual_counts, np.log(counts[counts > 0]))


def test_histogram_cache_refreshes_an_in_place_pixel_edit(qapp):
    item = NormalizedImageItem()
    data = np.ones((30, 40), dtype=np.uint32)
    item.setImage(data)
    first = item.getRawHistogram(get_histogram_data)
    assert item.getRawHistogram(get_histogram_data) is first
    # This pixel was outside the old sparse hash and used to give stale data.
    data[1, 1] = 100
    item.setImage(data)
    refreshed = item.getRawHistogram(get_histogram_data)
    assert refreshed is not first
    expected = get_histogram_data(data)
    np.testing.assert_array_equal(refreshed[0], expected[0])
    np.testing.assert_array_equal(refreshed[1], expected[1])
