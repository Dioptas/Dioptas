# SPDX-License-Identifier: MIT
"""Tests for the ImgWidget mouse coordinate handling"""

import numpy as np
import pytest
from pyqtgraph import GraphicsLayoutWidget
from qtpy.QtCore import QPointF, Qt
from qtpy.QtTest import QTest

from dioptas.widgets.plot_widgets.ImgWidget import (
    CalibrationCakeWidget,
    ImgWidget,
    IntegrationBatchWidget,
    IntegrationCakeWidget,
    IntegrationImgWidget,
    MaskImgWidget,
)
from dioptas.widgets.plot_widgets import utils


@pytest.fixture
def img_widget(qapp, qWidgetFactory):
    layout_widget = qWidgetFactory(GraphicsLayoutWidget)
    widget = ImgWidget(layout_widget)
    widget.plot_image(
        np.arange(100, dtype=np.float32).reshape(10, 10), auto_level=True
    )
    qapp.processEvents()
    yield widget
    qapp.processEvents()


def _moved_position(qapp, img_widget, data_x, data_y):
    """Emits a mouse move over the given data coordinate and returns what
    the widget reports for it."""
    reported = []
    img_widget.mouse_moved.connect(lambda x, y: reported.append((x, y)))
    scene_pos = img_widget.img_view_box.mapViewToScene(QPointF(data_x, data_y))
    img_widget.mouseMoved(scene_pos)
    qapp.processEvents()
    return reported[-1]


def test_mouse_moved_reports_data_coordinates(qapp, img_widget):
    x, y = _moved_position(qapp, img_widget, 3.5, 6.5)
    assert x == pytest.approx(3.5, abs=1e-6)
    assert y == pytest.approx(6.5, abs=1e-6)


def test_mouse_moved_reports_data_coordinates_when_smoothed(qapp, img_widget):
    # smoothing upscales the image item and gives it a compensating transform,
    # which must not leak into the reported coordinates
    img_widget.data_img_item.setSmoothFactor(5)
    qapp.processEvents()

    x, y = _moved_position(qapp, img_widget, 3.5, 6.5)
    assert x == pytest.approx(3.5, abs=1e-6)
    assert y == pytest.approx(6.5, abs=1e-6)


def test_plot_image_uses_dioptas_auto_level_only(qapp, qWidgetFactory, monkeypatch):
    layout_widget = qWidgetFactory(GraphicsLayoutWidget)
    widget = ImgWidget(layout_widget)
    calls = []
    original_set_image = widget.data_img_item.setImage

    def record_set_image(image=None, **kwargs):
        if image is not None:
            calls.append(kwargs)
        return original_set_image(image, **kwargs)

    monkeypatch.setattr(widget.data_img_item, "setImage", record_set_image)
    widget.plot_image(np.arange(100).reshape(10, 10), auto_level=True)

    assert calls == [{"autoLevels": False}]


@pytest.mark.parametrize("orientation", ["horizontal", "vertical"])
@pytest.mark.parametrize("widget_class", [
    ImgWidget, MaskImgWidget, IntegrationImgWidget, CalibrationCakeWidget,
    IntegrationCakeWidget, IntegrationBatchWidget,
])
def test_autoscale_button_resets_intensity_without_changing_zoom(
    qapp, qWidgetFactory, orientation, widget_class,
):
    layout_widget = qWidgetFactory(GraphicsLayoutWidget)
    widget = widget_class(layout_widget, orientation=orientation)
    image = np.arange(1, 101, dtype=np.float32).reshape(10, 10)
    widget.plot_image(image)
    histogram = getattr(widget, "img_histogram_LUT_" + orientation)
    histogram.setLevels(20, 30)
    widget.img_view_box.setRange(xRange=(2, 6), yRange=(3, 7), padding=0)
    qapp.processEvents()
    view_range = np.array(widget.img_view_box.viewRange())

    QTest.mouseClick(histogram.autoscale_btn, Qt.LeftButton)

    expected = utils.auto_level.get_range(image)
    assert widget.data_img_item.getLevels() == pytest.approx(expected)
    assert widget.img_histogram_LUT_horizontal.getExpLevels() == pytest.approx(expected)
    assert widget.img_histogram_LUT_vertical.getExpLevels() == pytest.approx(expected)
    np.testing.assert_allclose(widget.img_view_box.viewRange(), view_range)
    np.testing.assert_array_equal(image, np.arange(1, 101).reshape(10, 10))


@pytest.mark.parametrize("image", [
    None, np.empty((0, 0)), np.full((3, 3), np.nan),
])
def test_autoscale_button_without_valid_data(qapp, qWidgetFactory, image):
    layout_widget = qWidgetFactory(GraphicsLayoutWidget)
    widget = ImgWidget(layout_widget)
    QTest.mouseClick(widget.img_histogram_LUT_vertical.autoscale_btn, Qt.LeftButton)
    widget.plot_image(np.arange(1, 101).reshape(10, 10), auto_level=True)
    if image is not None:
        widget.plot_image(image)
    else:
        widget.data_img_item.clear()
    levels = widget.data_img_item.getLevels()

    QTest.mouseClick(widget.img_histogram_LUT_vertical.autoscale_btn, Qt.LeftButton)

    np.testing.assert_array_equal(widget.data_img_item.getLevels(), levels)


def test_autoscale_button_preserves_signed_map_range(qapp, qWidgetFactory):
    layout_widget = qWidgetFactory(GraphicsLayoutWidget)
    widget = IntegrationImgWidget(layout_widget, orientation="horizontal")
    image = np.arange(-100, 0, dtype=float).reshape(10, 10)
    widget.plot_image(image)
    widget.data_img_item.setLevels([1, 10])

    QTest.mouseClick(widget.img_histogram_LUT_horizontal.autoscale_btn, Qt.LeftButton)

    assert widget.data_img_item.getLevels() == pytest.approx(utils.auto_level.get_range(image))


def test_mask_plot_uses_binary_storage_and_fixed_levels(qapp, qWidgetFactory):
    layout_widget = qWidgetFactory(GraphicsLayoutWidget)
    widget = MaskImgWidget(layout_widget)
    mask = np.zeros((10, 10), dtype=bool)
    mask[2:4, 5:8] = True

    widget.plot_mask(mask)

    assert widget.mask_data.dtype == np.int8
    assert tuple(widget.mask_img_item.getLevels()) == (0, 1)


def test_calibration_cake_has_physical_axes(qapp, qWidgetFactory):
    layout_widget = qWidgetFactory(GraphicsLayoutWidget)
    widget = CalibrationCakeWidget(layout_widget)
    widget.plot_image(np.zeros((4, 5), dtype=np.int32))
    widget.set_cake_coordinates(
        np.linspace(14.0, 46.0, 5),
        np.linspace(-135.0, 135.0, 4),
    )
    widget.img_view_box.setRange(xRange=(0, 5), yRange=(0, 4), padding=0)
    qapp.processEvents()

    assert widget.bottom_axis_cake.labelText == "2θ"
    assert widget.bottom_axis_cake.labelUnits == "°"
    assert widget.left_axis_cake.labelText == "Azimuth"
    assert widget.left_axis_cake.labelUnits == "°"
    assert widget.bottom_axis_cake.range == pytest.approx([10.0, 50.0])
    assert widget.left_axis_cake.range == pytest.approx([-180.0, 180.0])

    widget.img_view_box.setRange(xRange=(1, 3), yRange=(1, 3), padding=0)
    qapp.processEvents()

    assert widget.bottom_axis_cake.range == pytest.approx([18.0, 34.0])
    assert widget.left_axis_cake.range == pytest.approx([-90.0, 90.0])
