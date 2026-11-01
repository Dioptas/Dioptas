"""Display-only ranges follow Qt without loading GUI modules in the runtime."""
import numpy as np
import pytest
from dioptas.desktop.display import image_levels


@pytest.mark.parametrize("mode", ["percentile", "minmax", "mean3std"])
@pytest.mark.parametrize("filter_gaps", [False, True])
def test_auto_ranges_match_current_qt(mode, filter_gaps):
    from dioptas.widgets.plot_widgets.utils import AutoLevel
    data = np.arange(400, dtype=float).reshape(20, 20)
    data[:, 4:7] = -1
    data[0, 0], data[1, 1] = 100000, np.nan
    before = data.copy()
    qt = AutoLevel()
    qt.mode = "2.5percentile" if mode == "percentile" else mode
    qt.filter_dummy = filter_gaps
    np.testing.assert_allclose(image_levels(data, mode, 2.5, filter_gaps), qt.get_range(data))
    np.testing.assert_array_equal(data, before)


def test_constant_and_nonfinite_images_have_safe_display_ranges():
    assert image_levels(np.full((8,8), 7)) == [7,8]
    assert image_levels(np.full((8,8), np.nan)) is None
    with pytest.raises(ValueError):
        image_levels(np.ones((8,8)), mode="unknown")
