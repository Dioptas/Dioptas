# SPDX-License-Identifier: MIT
"""Tests for the ImgWidget mouse coordinate handling"""

import numpy as np
import pytest
from pyqtgraph import GraphicsLayoutWidget
from qtpy.QtCore import QPointF

from dioptas.widgets.plot_widgets.ImgWidget import ImgWidget


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
