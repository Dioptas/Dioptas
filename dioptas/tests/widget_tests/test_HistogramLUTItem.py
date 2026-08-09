# SPDX-License-Identifier: MIT

import numpy as np

from ...widgets.plot_widgets.HistogramLUTItem import get_histogram_data


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
