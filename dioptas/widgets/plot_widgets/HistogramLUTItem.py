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

import pathlib
from collections import OrderedDict
from typing import Optional

from qtpy import QtCore, QtGui, QtWidgets
from pyqtgraph.graphicsItems.GraphicsWidget import GraphicsWidget
from pyqtgraph.graphicsItems.ViewBox import *
from pyqtgraph.graphicsItems.GradientEditorItem import *
from pyqtgraph.graphicsItems.LinearRegionItem import *
from pyqtgraph.graphicsItems.PlotDataItem import *
import pyqtgraph.graphicsItems.GradientEditorItem
from pyqtgraph.Point import Point
import pyqtgraph.functions as fn
import pyqtgraph as pg
import numpy as np
from .ColormapPopup import ColormapPopup
from .NormalizedImageItem import NormalizedImageItem
from ..CustomWidgets import FlatButton
from ... import icons_path, style_path

__all__ = ["HistogramLUTItem"]

# add grey_inverse to the list of color gradients:
pyqtgraph.graphicsItems.GradientEditorItem.Gradients["grey_inverse"] = {
    "ticks": [(0.0, (255, 255, 255, 255)), (1.0, (0, 0, 0, 255))],
    "mode": "rgb",
}

pyqtgraph.graphicsItems.GradientEditorItem.Gradients["jet"] = {
    "ticks": [
        (0.0, (0, 0, 128, 255)),
        (0.1, (0, 0, 255, 255)),
        (0.4, (0, 255, 255, 255)),
        (0.5, (0, 255, 0, 255)),
        (0.6, (255, 255, 0, 255)),
        (0.9, (255, 0, 0, 255)),
        (1.0, (128, 0, 0, 255)),
    ],
    "mode": "rgb",
}

# set the error handling for numpy
np.seterr(divide="ignore", invalid="ignore")


class HistogramLUTItem(GraphicsWidget):
    """
    This is a graphicsWidget which provides controls for adjusting the display of an image.
    Includes:

    - Image histogram
    - Movable region over histogram to select black/white levels
    - Gradient editor to define color lookup table for single-channel images
    """

    sigLookupTableChanged = QtCore.Signal(object)
    sigLevelsChanged = QtCore.Signal(object)
    sigLevelChangeFinished = QtCore.Signal(object)

    def __init__(
            self, image=None, fillHistogram=False, orientation="horizontal", autoLevel=None
    ):
        """
        If *image* (ImageItem) is provided, then the control will be automatically linked to the image and changes to the control will be immediately reflected in the image's appearance.
        By default, the histogram is rendered with a fill. For performance, set *fillHistogram* = False.
        """
        GraphicsWidget.__init__(self)
        self.lut = None
        self.imageItem = None
        self.first_image = True
        self.percentageLevel = False
        self.orientation = orientation
        self.autoLevel = autoLevel
        self._img_data = None

        self.layout = QtWidgets.QGraphicsGridLayout()
        self.setLayout(self.layout)
        self.layout.setContentsMargins(1, 1, 1, 1)
        self.layout.setSpacing(0)

        self.vb = ViewBox()

        self.gradient = GradientEditorItem()
        self.gradient.loadPreset("grey")

        self._normalizationLabel = pg.LabelItem("")

        configurationButton = FlatButton()
        configurationButton.setWidth(30)
        configurationButton.setHeight(30)
        configurationButton.setIcon(
            QtGui.QIcon(str(pathlib.Path(icons_path) / "settings.png"))
        )
        configurationButton.setToolTip("Configure colormap")
        configurationButton.clicked.connect(self._configurationButtonClicked)

        proxy = QtWidgets.QGraphicsProxyWidget()
        proxy.setWidget(configurationButton)

        if orientation == "horizontal":
            self.vb.setMouseEnabled(x=True, y=False)
            self.vb.setMaximumHeight(30)
            self.vb.setMinimumHeight(45)
            self.gradient.setOrientation("top")
            self.region = LogarithmRegionItem([0, 1], LinearRegionItem.Vertical)
            self.layout.addItem(self.vb, 1, 0)
            self.layout.addItem(self.gradient, 0, 0)
            self.layout.addItem(self._normalizationLabel, 1, 1)
            self.layout.addItem(proxy, 0, 1)
            self.gradient.setFlag(self.gradient.ItemStacksBehindParent)
            self.vb.setFlag(self.gradient.ItemStacksBehindParent)
        elif orientation == "vertical":
            self.vb.setMouseEnabled(x=False, y=True)
            self.vb.setMaximumWidth(30)
            self.vb.setMinimumWidth(45)
            self.gradient.setOrientation("right")
            self.region = LogarithmRegionItem([0, 1], LinearRegionItem.Horizontal)
            self.layout.addItem(self.vb, 0, 0)
            self.layout.addItem(self.gradient, 0, 1)
            self.layout.addItem(self._normalizationLabel, 1, 0)
            self.layout.addItem(proxy, 1, 1)

        self.gradient.setFlag(self.gradient.ItemStacksBehindParent)
        self.vb.setFlag(self.gradient.ItemStacksBehindParent)
        self.region.setZValue(1000)
        self.vb.addItem(self.region)
        self.vb.setMenuEnabled(False)

        # self.grid = GridItem()
        # self.vb.addItem(self.grid)

        self.gradient.sigGradientChanged.connect(self.gradientChanged)
        self.region.sigRegionChanged.connect(self.regionChanging)
        self.region.sigRegionChangeFinished.connect(self.regionChanged)

        self.vb.sigRangeChanged.connect(self.viewRangeChanged)
        self.plot = PlotDataItem()
        self.vb.autoRange()
        self.fillHistogram(fillHistogram)
        self.plot.setPen(pg.mkPen(color=(50, 150, 50), size=3))

        self.vb.addItem(self.plot)
        self.autoHistogramRange()

        if image is not None:
            self.setImageItem(image)
            # self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)

        self.vb.mouseClickEvent = self.empty_function
        self.vb.mouseDragEvent = self.empty_function
        self.vb.mouseDoubleClickEvent = self.empty_function
        self.vb.wheelEvent = self.empty_function

    def fillHistogram(self, fill=True, level=0.0, color=(100, 100, 200)):
        if fill:
            self.plot.setFillLevel(level)
            self.plot.setFillBrush(color)
        else:
            self.plot.setFillLevel(None)

            # def sizeHint(self, *args):
            # return QtCore.QSizeF(115, 200)

    def paint(self, p, *args):
        pen = self.region.lines[0].pen
        rgn = self.getLevels()
        if self.orientation == "horizontal":
            p1 = self.vb.mapFromViewToItem(
                self, Point(rgn[0], self.vb.viewRect().center().y())
            )
            p2 = self.vb.mapFromViewToItem(
                self, Point(rgn[1], self.vb.viewRect().center().y())
            )
            gradRect = self.gradient.mapRectToParent(self.gradient.gradRect.rect())
            for pen in [fn.mkPen("k", width=3), pen]:
                p.setPen(pen)
                p.drawLine(p1, gradRect.bottomLeft())
                p.drawLine(p2, gradRect.bottomRight())
                p.drawLine(gradRect.bottomLeft(), gradRect.topLeft())
                p.drawLine(gradRect.bottomRight(), gradRect.topRight())

        elif self.orientation == "vertical":
            p1 = self.vb.mapFromViewToItem(
                self, Point(self.vb.viewRect().center().x(), rgn[0])
            )
            p2 = self.vb.mapFromViewToItem(
                self, Point(self.vb.viewRect().center().x(), rgn[1])
            )
            gradRect = self.gradient.mapRectToParent(self.gradient.gradRect.rect())
            for pen in [fn.mkPen("k", width=3), pen]:
                p.setPen(pen)
                p.drawLine(p1, gradRect.bottomLeft())
                p.drawLine(p2, gradRect.topLeft())
                p.drawLine(gradRect.topLeft(), gradRect.topRight())
                p.drawLine(gradRect.bottomLeft(), gradRect.bottomRight())

    def setHistogramRange(self, mn, mx, padding=0.1):
        """Set the Y range on the histogram plot. This disables auto-scaling."""
        self.vb.enableAutoRange(self.vb.YAxis, False)
        if self.orientation == "horizontal":
            self.vb.setXRange(mn, mx, padding)
        elif self.orientation == "vertical":
            self.vb.setYrange(mn, mx, padding)
            # mn -= d*padding
            # mx += d*padding
            # self.range = [mn,mx]
            # self.updateRange()
            # self.vb.setMouseEnabled(False, True)
            # self.region.setBounds([mn,mx])

    def autoHistogramRange(self):
        """Enable auto-scaling on the histogram plot."""
        self.vb.enableAutoRange(self.vb.XAxis, True)
        self.vb.enableAutoRange(self.vb.YAxis, True)
        # self.range = None
        # self.updateRange()
        # self.vb.setMouseEnabled(False, False)

        # def updateRange(self):
        # self.vb.autoRange()
        # if self.range is not None:
        # self.vb.setYRange(*self.range)
        # vr = self.vb.viewRect()

        # self.region.setBounds([vr.top(), vr.bottom()])

    def setImageItem(self, img):
        self.imageItem = img
        self._updateNormalizationLabel(self.getNormalization())
        img.sigImageChanged.connect(self.imageChanged)
        img.setLookupTable(self.getLookupTable)
        self.regionChanged()
        self.imageChanged()

    def activate(self):
        # we should make sure we are not double connected
        # disconnect does not throw an error if the signal is not connected
        self.imageItem.sigImageChanged.disconnect(self.imageChanged)
        self.imageItem.sigImageChanged.connect(self.imageChanged)
        self.imageItem.setLookupTable(self.getLookupTable)

    def deactivate(self):
        self.imageItem.sigImageChanged.disconnect(self.imageChanged)
        self.imageItem.setLookupTable(None)

    def gradientChanged(self):
        if self.imageItem is not None:
            if self.gradient.isLookupTrivial():
                self.imageItem.setLookupTable(None)  # lambda x: x.astype(np.uint8))
            else:
                self.imageItem.setLookupTable(
                    self.getLookupTable
                )  ## send function pointer, not the result

        self.lut = None
        # if self.imageItem is not None:
        # self.imageItem.setLookupTable(self.gradient.getLookupTable(512))
        self.sigLookupTableChanged.emit(self)

    def getLookupTable(self, img=None, n=None, alpha=None):
        if n is None:
            if img.dtype == np.uint8:
                n = 256
            else:
                n = 512
        if self.lut is None:
            self.lut = self.gradient.getLookupTable(n, alpha=alpha)
        return self.lut

    def regionChanged(self):
        self.sigLevelChangeFinished.emit(self)

    def regionChanging(self):
        if self.imageItem is not None:
            self.imageItem.setLevels(np.exp(self.region.getRegion()))
        self.sigLevelsChanged.emit(self)
        self.update()

    def imageChanged(self, autoRange=False, img_data=None):
        self._img_data = None

        if img_data is None:
            img_data = self.imageItem.getData(copy=False)
            if img_data is None:
                return

        left_edges_nonzero, log_hist_nonzero = get_histogram_data(img_data)
        if log_hist_nonzero is None:
            return

        if self.orientation == "horizontal":
            self.plot.setData(left_edges_nonzero, log_hist_nonzero)
        elif self.orientation == "vertical":
            self.plot.setData(log_hist_nonzero, left_edges_nonzero)

    def getImageData(self, copy: bool = True) -> Optional[np.ndarray]:
        """Returns currently displayed image data

        :param copy: False to return internal array, do not modify!
        """
        if isinstance(self.imageItem, NormalizedImageItem):
            return self.imageItem.getData(copy=copy)
        if self._img_data is not None:
            return np.array(self._img_data, copy=copy)
        return None

    def getLevels(self):
        return self.region.getRegion()

    def getExpLevels(self):
        rgn = self.getLevels()
        return np.exp(rgn[0]), np.exp(rgn[1])

    def setLevels(self, mn, mx):
        self.region.setRegion([mn, mx])
        if self.imageItem is not None:
            self.imageItem.setLevels(np.exp(self.region.getRegion()))

    def getNormalization(self) -> str:
        """Returns the current image normalization"""
        if isinstance(self.imageItem, NormalizedImageItem):
            return self.imageItem.getNormalization()
        return "linear"

    def setNormalization(self, normalization: str):
        """Set image current normalization

        This has effect only if the associated image item is a NormalizedImageItem.
        """
        if isinstance(self.imageItem, NormalizedImageItem):
            self.imageItem.setNormalization(normalization)
        self._updateNormalizationLabel(normalization)

    def empty_function(self, *args):
        pass

    def _configurationButtonClicked(self):
        widget = ColormapPopup(parent=self.scene().views()[0])

        widget.setCurrentGradient(self.gradient.saveState())
        widget.setCurrentNormalization(self.getNormalization())
        widget.setRange(*self.getExpLevels())
        widget.setData(data=self.getImageData(copy=False), copy=False)
        widget.sigCurrentGradientChanged.connect(self._configurationGradientChanged)
        widget.sigCurrentNormalizationChanged.connect(self._normalizationChanged)

        def rangeChanged(minimum, maximum):
            self.setLevels(minimum, maximum)
            # Update displayed range since it can differ from the provided one
            widget.setRange(*self.getExpLevels())

        widget.sigRangeChanged.connect(rangeChanged)
        button = self.sender()
        if self.orientation == "horizontal":
            position = button.mapToGlobal(QtCore.QPoint(button.width() + 5, 0))
        else:  # vertical
            widget.adjustSize()  # For retrieving dialog size
            position = button.mapToGlobal(
                QtCore.QPoint(button.width() + 5, button.height())
            ) - QtCore.QPoint(0, widget.frameGeometry().height())
        widget.move(position)
        widget.show()

    def _configurationGradientChanged(self, gradient: dict):
        self.gradient.restoreState(gradient)
        self.gradientChanged()

    def _updateNormalizationLabel(self, normalization: str):
        shortname = NormalizedImageItem.getNormalizationShortname(normalization)
        description = NormalizedImageItem.getNormalizationDescription(
            normalization
        ).capitalize()
        self._normalizationLabel.setText(f"<small>{shortname}</small>")
        self._normalizationLabel.setToolTip(f"{description} colormap normalization")

    def _normalizationChanged(self, normalization: str):
        self._updateNormalizationLabel(normalization)
        if isinstance(self.imageItem, NormalizedImageItem):
            self.imageItem.setNormalization(normalization)
            sender = self.sender()
            if isinstance(sender, ColormapPopup):
                sender.setData(data=self.getImageData(copy=False), copy=False)


class LogarithmRegionItem(LinearRegionItem):
    def __contains__(
            self, values=[0, 1], orientation=None, brush=None, movable=True, bounds=None
    ):
        super(LogarithmRegionItem, self).__init__(
            values, orientation, brush, movable, bounds
        )

    def getRegion(self):
        """Return the values at the edges of the region."""
        # if self.orientation[0] == 'h':
        # r = (self.bounds.top(), self.bounds.bottom())
        # else:
        # r = (self.bounds.left(), self.bounds.right())
        r = [(self.lines[0].value()), (self.lines[1].value())]
        return (min(r), max(r))

    def setRegion(self, rgn):
        """Set the values for the edges of the region.

        ==============   ==============================================
        **Arguments:**
        rgn              A list or tuple of the lower and upper values.
        ==============   ==============================================
        """

        if rgn[0] <= 0:
            rgn[0] = 1
        if rgn[1] <= 0:
            rgn[1] = 1
        rgn = np.log(np.array(rgn))
        if self.lines[0].value() == rgn[0] and self.lines[1].value() == rgn[1]:
            return
        self.blockLineSignal = True
        self.lines[0].setValue(rgn[0])
        self.blockLineSignal = False
        self.lines[1].setValue(rgn[1])
        # self.blockLineSignal = False
        try:  # needed due to changes in the pyqtgraph API
            self.lineMoved(0)
        except TypeError:
            self.lineMoved()
        self.lineMoveFinished()


histogram_cache = OrderedDict()


def get_histogram_data(img_data: np.ndarray) -> tuple:
    """calculates the histogram data necessary for the histogram LUt item"""
    if img_data is None:
        return None, None

    ar_hash = hash(img_data[::13, ::17].tobytes())

    if ar_hash in histogram_cache:
        return histogram_cache[ar_hash]
    else:
        log_data = np.log(img_data)
        log_data = log_data[np.isfinite(log_data)]
        if log_data.size == 0:
            return None, None

        hist, bin_edges = np.histogram(log_data, bins=1500)

        mask_nonzero = hist > 0
        left_edges_nonzero = bin_edges[:-1][mask_nonzero]
        hist_nonzero = hist[mask_nonzero]

        log_hist_nonzero = np.log(hist_nonzero)

        histogram_cache[ar_hash] = (left_edges_nonzero, log_hist_nonzero)
        histogram_cache.move_to_end(ar_hash)
        if len(histogram_cache) > 100:  # keep only 100 histograms in cache
            histogram_cache.popitem(last=False)
        return left_edges_nonzero, log_hist_nonzero
