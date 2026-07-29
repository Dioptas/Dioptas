# SPDX-License-Identifier: MIT

import os
import numpy as np
from math import cos, sin

import fabio
import pytest

from ...model.MaskModel import MaskModel
from ...model.util.point import Point

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')


@pytest.fixture
def mask_model():
    mask_model = MaskModel()
    mask_model.set_dimension((10, 10))
    return mask_model


def test_growing_masks(mask_model):
    mask_model._mask_data[4, 4] = 1
    mask_model._mask_data[0, 0] = 1
    mask_model._mask_data[0, 9] = 1
    mask_model._mask_data[9, 9] = 1
    mask_model._mask_data[9, 0] = 1

    mask_model.grow()

    # tests corners
    assert mask_model._mask_data[0, 1] == 1
    assert mask_model._mask_data[1, 1] == 1
    assert mask_model._mask_data[1, 0] == 1

    assert mask_model._mask_data[0, 8] == 1
    assert mask_model._mask_data[1, 8] == 1
    assert mask_model._mask_data[1, 9] == 1

    assert mask_model._mask_data[8, 0] == 1
    assert mask_model._mask_data[8, 1] == 1
    assert mask_model._mask_data[9, 1] == 1

    assert mask_model._mask_data[8, 8] == 1
    assert mask_model._mask_data[8, 9] == 1
    assert mask_model._mask_data[9, 8] == 1

    # tests center
    assert mask_model._mask_data[3, 3] == 1
    assert mask_model._mask_data[4, 3] == 1
    assert mask_model._mask_data[5, 3] == 1

    assert mask_model._mask_data[3, 5] == 1
    assert mask_model._mask_data[4, 5] == 1
    assert mask_model._mask_data[5, 5] == 1

    assert mask_model._mask_data[3, 4] == 1
    assert mask_model._mask_data[5, 4] == 1


def test_shrink_mask(mask_model):
    mask_model._mask_data[4, 4] = 1
    mask_model._mask_data[0, 0] = 1
    mask_model._mask_data[0, 9] = 1
    mask_model._mask_data[9, 9] = 1
    mask_model._mask_data[9, 0] = 1

    before_mask = np.copy(mask_model._mask_data)
    mask_model.grow()
    mask_model.shrink()

    assert np.array_equal(before_mask, mask_model._mask_data)

    mask_model.clear_mask()

    mask_model._mask_data[4, 4] = 1
    mask_model._mask_data[5, 4] = 1
    mask_model._mask_data[5, 5] = 1
    mask_model._mask_data[4, 5] = 1
    mask_model.shrink()

    assert np.sum(mask_model._mask_data) == 0


def test_threshold_mask_mode(mask_model):
    """Threshold masking should respect the mask/unmask mode."""
    img_data = np.zeros((10, 10))
    img_data[0:5, :] = 10  # top half bright
    img_data[5:10, :] = 1  # bottom half dim

    # mask mode (default): mask_below_threshold should set matching pixels to True
    mask_model.set_mode(True)
    mask_model.mask_below_threshold(img_data, 5)
    assert np.all(mask_model._mask_data[5:10, :])  # dim pixels masked
    assert not np.any(mask_model._mask_data[0:5, :])  # bright pixels not masked

    # unmask mode: mask_below_threshold should set matching pixels to False
    mask_model.set_mode(False)
    mask_model.mask_below_threshold(img_data, 5)
    assert not np.any(mask_model._mask_data[5:10, :])  # dim pixels unmasked
    assert not np.any(mask_model._mask_data[0:5, :])  # bright pixels unchanged


def test_threshold_above_mask_mode(mask_model):
    """mask_above_threshold should respect the mask/unmask mode."""
    img_data = np.zeros((10, 10))
    img_data[0:5, :] = 10
    img_data[5:10, :] = 1

    # mask mode: mask pixels above threshold
    mask_model.set_mode(True)
    mask_model.mask_above_threshold(img_data, 5)
    assert np.all(mask_model._mask_data[0:5, :])  # bright pixels masked
    assert not np.any(mask_model._mask_data[5:10, :])  # dim pixels not masked

    # unmask mode: unmask pixels above threshold
    mask_model.set_mode(False)
    mask_model.mask_above_threshold(img_data, 5)
    assert not np.any(mask_model._mask_data[0:5, :])  # bright pixels unmasked
    assert not np.any(mask_model._mask_data[5:10, :])  # dim pixels unchanged


@pytest.mark.parametrize("flipud", [False, True])
@pytest.mark.parametrize("extension", [".mask", ".npy", ".edf"])
def test_saving_and_loading(mask_model, tmp_path, extension, flipud):
    mask_model.mask_ellipse(1024, 1024, 100, 100)
    mask_model.set_dimension((2048, 2048))

    mask_array = np.copy(mask_model.get_img())

    filename = os.path.join(tmp_path, f"dummy{extension}")

    mask_model.save_mask(filename, flipud)
    mask_model.load_mask(filename, flipud)

    assert np.array_equal(mask_array, mask_model.get_img())

    mask_model.load_mask(filename, not flipud)
    assert np.array_equal(mask_array, np.flipud(mask_model.get_img()))


def test_use_roi(mask_model):
    mask_model.roi = [0, 2, 0, 2]

    assert np.array_equal(mask_model.get_mask()[0:3, 0:3],
                          np.array([[0, 0, 1],
                                    [0, 0, 1],
                                    [1, 1, 1]]))


@pytest.mark.parametrize("extension", [".mask", ".npy", ".edf"])
def test_save_mask(mask_model, tmp_path, extension):
    mask_model.mask_below_threshold(np.zeros(shape=(10, 10)), 1)
    filename = os.path.join(tmp_path, f"test_save{extension}")
    mask_model.save_mask(filename)

    assert os.path.exists(filename)


def test_find_center_of_circle_from_three_points(mask_model):
    x0 = 2.0
    y0 = 3.5
    r = 1.2
    phi1 = 0.1
    phi2 = 1.3
    phi3 = 6.0
    p1 = Point(x0 + r * cos(phi1), y0 + r * sin(phi1))
    p2 = Point(x0 + r * cos(phi2), y0 + r * sin(phi2))
    p3 = Point(x0 + r * cos(phi3), y0 + r * sin(phi3))
    mask_model.find_center_of_circle_from_three_points(p1, p2, p3)
    assert pytest.approx(x0) == mask_model.center_for_arc.x()
    assert pytest.approx(y0) == mask_model.center_for_arc.y()


def test_find_center_of_circle_from_three_points_collinear(mask_model):
    p1 = Point(0.0, 0.0)
    p2 = Point(1.0, 1.0)
    p3 = Point(2.0, 2.0)
    assert mask_model.find_center_of_circle_from_three_points(p1, p2, p3) is None


def test_find_radius_of_circle_from_center_and_point(mask_model):
    x0 = 2.0
    y0 = 3.5
    p0 = Point(x0, y0)
    r = 1.2
    phi1 = 0.1
    p1 = Point(x0 + r * cos(phi1), y0 + r * sin(phi1))
    rcalc = mask_model.find_radius_of_circle_from_center_and_point(p0, p1)
    assert r == rcalc


def test_find_n_points_on_arc_from_three_points(mask_model):
    n = 50
    x0 = 2.0
    y0 = 3.5
    p0 = Point(x0, y0)
    r = 1.2
    width = 0

    phi1 = 0.1
    phi2 = 1.3
    phi3 = -0.2
    p1 = Point(x0 + r * cos(phi1), y0 + r * sin(phi1))
    p2 = Point(x0 + r * cos(phi2), y0 + r * sin(phi2))
    p3 = Point(x0 + r * cos(phi3), y0 + r * sin(phi3))

    n_angles = mask_model.find_n_angles_on_arc_from_three_points_around_p0(p0, p1, p2, p3, n)
    n_points = mask_model.calc_arc_points_from_angles(p0, r, width, n_angles)
    for p in n_points:
        rcalc = mask_model.find_radius_of_circle_from_center_and_point(p0, p)
        assert r == pytest.approx(rcalc, abs=1e-6)


def test_roi_mask_with_negative_clamping():
    """roi_mask should clamp negative x1/y1 to 0."""
    mask_model = MaskModel(mask_dimension=(100, 100))
    mask_model.roi = [-5, 50, -10, 60]
    roi = mask_model.roi_mask
    assert roi is not None
    # The region [0:50, 0:60] should be 0 (inside ROI), rest should be 1
    assert roi[0, 0] == 0
    assert roi[49, 59] == 0
    assert roi[50, 60] == 1
    assert roi[99, 99] == 1


def test_roi_mask_returns_none_when_no_roi():
    """roi_mask should return None when roi is not set."""
    mask_model = MaskModel(mask_dimension=(100, 100))
    assert mask_model.roi_mask is None


class _MockRect:
    """Minimal mock for QRectF-like objects."""
    def __init__(self, x, y, w, h):
        self._x, self._y, self._w, self._h = x, y, w, h

    def top(self):
        return self._y

    def left(self):
        return self._x

    def height(self):
        return self._h

    def width(self):
        return self._w

    def center(self):
        return Point(self._x + self._w / 2, self._y + self._h / 2)


class _MockRectItem:
    def __init__(self, x, y, w, h):
        self._rect = _MockRect(x, y, w, h)

    def rect(self):
        return self._rect


class _MockEllipseItem:
    def __init__(self, x, y, w, h):
        self._rect = _MockRect(x, y, w, h)

    def rect(self):
        return self._rect


class _MockPolygonItem:
    def __init__(self, points):
        self.vertices = points


def test_mask_QGraphicsRectItem():
    mask_model = MaskModel(mask_dimension=(100, 100))
    item = _MockRectItem(10, 20, 30, 40)
    mask_model.mask_QGraphicsRectItem(item)
    # rect masks from (top, left) = (20, 10) with (height, width) = (40, 30)
    assert mask_model._mask_data[20, 10]
    assert mask_model._mask_data[59, 39]
    assert not mask_model._mask_data[0, 0]


def test_mask_QGraphicsPolygonItem():
    mask_model = MaskModel(mask_dimension=(100, 100))
    # Triangle covering a known region
    points = [Point(10, 10), Point(10, 30), Point(30, 10)]
    item = _MockPolygonItem(points)
    mask_model.mask_QGraphicsPolygonItem(item)
    # Center of triangle should be masked
    assert mask_model._mask_data[15, 15]
    # Far corner should not be masked
    assert not mask_model._mask_data[90, 90]


def test_mask_QGraphicsEllipseItem():
    mask_model = MaskModel(mask_dimension=(100, 100))
    # Ellipse bounding rect at (20, 30) with width=40, height=20
    item = _MockEllipseItem(20, 30, 40, 20)
    mask_model.mask_QGraphicsEllipseItem(item)
    # Center of ellipse (cx=40, cy=40) should be masked
    assert mask_model._mask_data[40, 40]
    assert not mask_model._mask_data[0, 0]


def test_mask_rect_negative_width_height():
    """mask_rect with negative width/height should swap indices."""
    mask_model = MaskModel(mask_dimension=(100, 100))
    # Negative width and height: effectively masks rect from (20,30) to (50,60)
    mask_model.mask_rect(50, 60, -30, -30)
    assert mask_model._mask_data[25, 35]
    assert not mask_model._mask_data[0, 0]


def test_mask_rect_boundary_clamping():
    """mask_rect should clamp negative start indices to 0."""
    mask_model = MaskModel(mask_dimension=(100, 100))
    mask_model.mask_rect(-5, -5, 20, 20)
    assert mask_model._mask_data[0, 0]
    assert mask_model._mask_data[14, 14]


def test_mask_polygon():
    """mask_polygon should mask interior pixels of a polygon."""
    mask_model = MaskModel(mask_dimension=(100, 100))
    x = np.array([10, 10, 50, 50], dtype=float)
    y = np.array([10, 50, 50, 10], dtype=float)
    mask_model.mask_polygon(x, y)
    assert mask_model._mask_data[30, 30]
    assert not mask_model._mask_data[0, 0]
    assert not mask_model._mask_data[99, 99]


def test_invert_mask():
    """invert_mask should flip all mask values."""
    mask_model = MaskModel(mask_dimension=(100, 100))
    assert np.sum(mask_model._mask_data) == 0
    mask_model.invert_mask()
    assert np.all(mask_model._mask_data)
    mask_model.invert_mask()
    assert not np.any(mask_model._mask_data)


def test_remove_cosmic():
    """remove_cosmic should detect bright pixel spikes."""
    mask_model = MaskModel(mask_dimension=(100, 100))
    img = np.random.normal(100, 5, (100, 100)).astype(np.float64)
    # Insert a cosmic ray (extreme bright pixel)
    img[50, 50] = 100000
    mask_model.remove_cosmic(img)
    assert mask_model._mask_data[50, 50]


def test_save_mask_npy(tmp_path):
    mask_model = MaskModel(mask_dimension=(50, 50))
    mask_model._mask_data[10:20, 10:20] = True
    filename = str(tmp_path / "mask.npy")
    mask_model.save_mask(filename)
    loaded = np.load(filename)
    assert np.array_equal(loaded, np.int8(mask_model.get_img()))


def test_save_mask_tif(tmp_path):
    mask_model = MaskModel(mask_dimension=(50, 50))
    mask_model._mask_data[10:20, 10:20] = True
    filename = str(tmp_path / "mask.tif")
    mask_model.save_mask(filename)
    assert os.path.exists(filename)


def test_read_mask_file_edf(tmp_path):
    """read_mask_file should load .edf format."""
    mask_data = np.zeros((50, 50), dtype=np.int8)
    mask_data[10:20, 10:20] = 1
    filename = str(tmp_path / "mask.edf")
    fabio.edfimage.EdfImage(mask_data).write(filename)
    loaded = MaskModel.read_mask_file(filename)
    assert np.array_equal(loaded, mask_data)


def test_load_mask_dimension_mismatch(tmp_path):
    """load_mask should return False when dimensions don't match."""
    mask_model = MaskModel(mask_dimension=(100, 100))
    # Save a mask with different dimensions
    small_mask = np.zeros((50, 50), dtype=np.int8)
    filename = str(tmp_path / "small_mask.npy")
    np.save(filename, small_mask)
    result = mask_model.load_mask(filename)
    assert result is False


def test_load_mask_matching_dimensions(tmp_path):
    """load_mask should return True and load data when dimensions match."""
    mask_model = MaskModel(mask_dimension=(50, 50))
    mask_data = np.zeros((50, 50), dtype=np.int8)
    mask_data[5:15, 5:15] = 1
    filename = str(tmp_path / "mask.npy")
    np.save(filename, mask_data)
    result = mask_model.load_mask(filename)
    assert result is True
    assert np.sum(mask_model._mask_data) == 100


def test_add_mask(tmp_path):
    """add_mask should combine loaded mask with current mask."""
    mask_model = MaskModel(mask_dimension=(50, 50))
    mask_model._mask_data[0:10, 0:10] = True  # existing mask

    additional = np.zeros((50, 50), dtype=np.int8)
    additional[40:50, 40:50] = 1
    filename = str(tmp_path / "add.npy")
    np.save(filename, additional)

    result = mask_model.add_mask(filename)
    assert result is True
    assert mask_model._mask_data[5, 5]    # original region
    assert mask_model._mask_data[45, 45]  # added region


def test_add_mask_dimension_mismatch(tmp_path):
    """add_mask should return False when dimensions don't match."""
    mask_model = MaskModel(mask_dimension=(100, 100))
    small = np.zeros((50, 50), dtype=np.int8)
    filename = str(tmp_path / "small.npy")
    np.save(filename, small)
    result = mask_model.add_mask(filename)
    assert result is False


def test_find_n_angles_on_arc_equal_angles_returns_none(mask_model):
    """When all three points are at the same angle, should return None."""
    p0 = Point(0.0, 0.0)
    pa = Point(1.0, 0.0)
    pb = Point(1.0, 0.0)
    pc = Point(1.0, 0.0)
    result = mask_model.find_n_angles_on_arc_from_three_points_around_p0(
        p0, pa, pb, pc, 10
    )
    assert result is None


def test_set_mask_updates_dimension():
    """Regression test: set_mask must update mask_dimension so that a
    subsequent set_dimension call with the same shape does not reset the mask.
    This reproduces a bug where loading a .dio project file would set mask data
    via set_mask without updating mask_dimension, causing the mask to be
    cleared the first time an image correction was enabled."""
    mask_model = MaskModel(mask_dimension=(2048, 2048))

    # Simulate loading mask from a .dio file with a different image size
    mask_data = np.zeros((1043, 981), dtype=bool)
    mask_data[100:200, 300:400] = True
    mask_model.set_mask(mask_data)

    assert mask_model.mask_dimension == (1043, 981)
    assert np.sum(mask_model.get_img()) == 100 * 100

    # Simulate what update_mask_dimension does when img_changed fires
    mask_model.set_dimension((1043, 981))

    # Mask must be preserved — not reset to zeros
    assert np.sum(mask_model.get_img()) == 100 * 100

