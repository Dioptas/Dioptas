import numpy as np

from ...model.util.calc import trim_trailing_zeros


def test_trim_trailing_zeros():
    x = np.linspace(0, 20)
    y = np.ones_like(x)
    y[-10:] = 0

    x_trim, y_trim = trim_trailing_zeros(x, y)

    assert len(y_trim) == len(y) - 10
    assert len(x_trim) == len(y) - 10
