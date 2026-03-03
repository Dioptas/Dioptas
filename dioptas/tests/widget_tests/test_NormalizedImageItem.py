# SPDX-License-Identifier: MIT
"""Test NormalizedImageItem pyqtgraph's GraphicObject"""

import numpy as np

import pytest
from pyqtgraph import GraphicsLayoutWidget
from qtpy import QtCore
from qtpy.QtTest import QSignalSpy, QTest

from dioptas.widgets.plot_widgets.NormalizedImageItem import NormalizedImageItem

NORMALIZATIONS = tuple(NormalizedImageItem._NORMALIZATIONS.keys())


@pytest.fixture
def normalizedImageItem(qapp, qWidgetFactory):
    """Fixture providing a NormalizedImageItem displayed in a GraphicsLayoutWidget"""
    widget = qWidgetFactory(GraphicsLayoutWidget)
    viewbox = widget.addViewBox(row=1, col=1)

    item = NormalizedImageItem()
    viewbox.addItem(item)

    yield item
    qapp.processEvents()


def testDefaultItem(normalizedImageItem):
    """Test NormalizedImageItem default values"""
    normalization = normalizedImageItem.getNormalization()
    assert normalization == "linear"
    data = normalizedImageItem.getData(copy=False)
    assert data is None
    levels = normalizedImageItem.getLevels()
    assert levels is None


@pytest.mark.parametrize("normalization", NORMALIZATIONS)
def testSetLevels(normalizedImageItem, normalization):
    """Test setLevels with different normalizations"""
    normalizedImageItem.setNormalization(normalization)
    assert normalizedImageItem.getNormalization() == normalization
    assert normalizedImageItem.getLevels() is None

    normalizedImageItem.setLevels((1, 10))
    levels = normalizedImageItem.getLevels()
    assert np.allclose(levels, (1, 10))


@pytest.mark.parametrize("normalization", NORMALIZATIONS)
def testSetImage(qapp, normalizedImageItem, normalization):
    """Test setImage with different normalizations"""
    normalizedImageItem.setNormalization(normalization)

    ref_image = np.arange(10000, dtype=np.float32).reshape(100, 100)
    min_max = ref_image.min(), ref_image.max()

    normalizedImageItem.setImage(ref_image)
    qapp.processEvents()

    data = normalizedImageItem.getData(copy=False)
    assert np.array_equal(ref_image, data)

    levels = normalizedImageItem.getLevels()
    assert np.allclose(levels, min_max)

    assert normalizedImageItem.quickMinMax() == min_max
