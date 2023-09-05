# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
# Principal author: Clemens Prescher (clemens.prescher@gmail.com)
# Copyright (C) 2014-2019 GSECARS, University of Chicago, USA
# Copyright (C) 2015-2018 Institute for Geology and Mineralogy, University of Cologne, Germany
# Copyright (C) 2019-2020 DESY, Hamburg, Germany
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
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
