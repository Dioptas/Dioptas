# -*- coding: utf8 -*-
# Py2DeX - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2014  Clemens Prescher (clemens.prescher@gmail.com)
#     GSECARS, University of Chicago
#
#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.
#
#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
GraphicsWidget displaying an image histogram along with gradient editor. Can be used to adjust the appearance of images.
"""

from pyqtgraph.Qt import QtGui, QtCore
import pyqtgraph.functions as fn
from pyqtgraph.graphicsItems.GraphicsWidget import GraphicsWidget
from pyqtgraph.graphicsItems.ViewBox import *
from pyqtgraph.graphicsItems.GradientEditorItem import *
from pyqtgraph.graphicsItems.LinearRegionItem import *
from pyqtgraph.graphicsItems.PlotDataItem import *
from pyqtgraph.graphicsItems.AxisItem import *
from pyqtgraph.graphicsItems.GridItem import *
from pyqtgraph.Point import Point
import pyqtgraph.functions as fn
import pyqtgraph as pg
import numpy as np
import pyqtgraph.debug as debug


__all__ = ['HistogramLUTItem']


class HorHistogramLUTItem(GraphicsWidget):
    """
    This is a graphicsWidget which provides controls for adjusting the display of an image.
    Includes:

    - Image histogram 
    - Movable region over histogram to select black/white levels
    - Gradient editor to define color lookup table for single-channel images
    """

    sigLookupTableChanged = QtCore.pyqtSignal(object)
    sigLevelsChanged = QtCore.pyqtSignal(object)
    sigLevelChangeFinished = QtCore.pyqtSignal(object)

    def __init__(self, image=None, fillHistogram=False, orientation='horizontal'):
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
        self.range = None

        self.layout = QtGui.QGraphicsGridLayout()
        self.setLayout(self.layout)
        self.layout.setContentsMargins(1, 1, 1, 1)
        self.layout.setSpacing(0)

        self.vb = ViewBox()

        self.gradient = GradientEditorItem()
        self.gradient.loadPreset('grey')

        if orientation == 'horizontal':
            self.vb.setMouseEnabled(x=True, y=False)
            self.vb.setMaximumHeight(30)
            self.vb.setMinimumHeight(45)
            self.gradient.setOrientation('top')
            self.region = LogarithmRegionItem([0, 1], LinearRegionItem.Vertical)
            self.layout.addItem(self.vb, 1, 0)
            self.layout.addItem(self.gradient, 0, 0)
            self.gradient.setFlag(self.gradient.ItemStacksBehindParent)
            self.vb.setFlag(self.gradient.ItemStacksBehindParent)
        elif orientation == 'vertical':
            self.vb.setMouseEnabled(x=False, y=True)
            self.vb.setMaximumWidth(30)
            self.vb.setMinimumWidth(45)
            self.gradient.setOrientation('right')
            self.region = LogarithmRegionItem([0, 1], LinearRegionItem.Horizontal)
            self.layout.addItem(self.vb, 0, 0)
            self.layout.addItem(self.gradient, 0, 1)

        self.gradient.setFlag(self.gradient.ItemStacksBehindParent)
        self.vb.setFlag(self.gradient.ItemStacksBehindParent)
        self.region.setZValue(1000)
        self.vb.addItem(self.region)
        self.vb.setMenuEnabled(False)


        #self.grid = GridItem()
        #self.vb.addItem(self.grid)

        self.gradient.sigGradientChanged.connect(self.gradientChanged)
        self.region.sigRegionChanged.connect(self.regionChanging)
        self.region.sigRegionChangeFinished.connect(self.regionChanged)

        self.vb.sigRangeChanged.connect(self.viewRangeChanged)
        self.plot = PlotDataItem()
        if self.orientation == 'horizontal':
            self.plot.setLogMode(yMode=True, xMode=False)
        elif self.orientation == 'vertical':
            self.plot.setLogMode(yMode=False, xMode=True)
            self.vb.invertX(True)
        self.vb.autoRange()
        self.fillHistogram(fillHistogram)
        self.plot.setPen(pg.mkPen(color=(50, 150, 50), size=3))

        self.vb.addItem(self.plot)
        self.autoHistogramRange()

        if image is not None:
            self.setImageItem(image)
            #self.setSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Expanding)

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

            #def sizeHint(self, *args):
            #return QtCore.QSizeF(115, 200)

    def paint(self, p, *args):
        pen = self.region.lines[0].pen
        rgn = self.getLevels()
        if self.orientation == 'horizontal':
            p1 = self.vb.mapFromViewToItem(self, Point(rgn[0], self.vb.viewRect().center().y()))
            p2 = self.vb.mapFromViewToItem(self, Point(rgn[1], self.vb.viewRect().center().y()))
            gradRect = self.gradient.mapRectToParent(self.gradient.gradRect.rect())
            for pen in [fn.mkPen('k', width=3), pen]:
                p.setPen(pen)
                p.drawLine(p1, gradRect.bottomLeft())
                p.drawLine(p2, gradRect.bottomRight())
                p.drawLine(gradRect.bottomLeft(), gradRect.topLeft())
                p.drawLine(gradRect.bottomRight(), gradRect.topRight())

        elif self.orientation == 'vertical':
            p1 = self.vb.mapFromViewToItem(self, Point(self.vb.viewRect().center().x(), rgn[0]))
            p2 = self.vb.mapFromViewToItem(self, Point(self.vb.viewRect().center().x(), rgn[1]))
            gradRect = self.gradient.mapRectToParent(self.gradient.gradRect.rect())
            for pen in [fn.mkPen('k', width=3), pen]:
                p.setPen(pen)
                p.drawLine(p1, gradRect.bottomLeft())
                p.drawLine(p2, gradRect.topLeft())
                p.drawLine(gradRect.topLeft(), gradRect.topRight())
                p.drawLine(gradRect.bottomLeft(), gradRect.bottomRight())


    def setHistogramRange(self, mn, mx, padding=0.1):
        """Set the Y range on the histogram plot. This disables auto-scaling."""
        self.vb.enableAutoRange(self.vb.YAxis, False)
        if self.orientation == 'horizontal':
            self.vb.setXRange(mn, mx, padding)
        elif self.orientation == 'vertical':
            self.vb.setYrange(mn, mx, padding)
            #mn -= d*padding
            #mx += d*padding
            #self.range = [mn,mx]
            #self.updateRange()
            #self.vb.setMouseEnabled(False, True)
            #self.region.setBounds([mn,mx])

    def autoHistogramRange(self):
        """Enable auto-scaling on the histogram plot."""
        self.vb.enableAutoRange(self.vb.XAxis, True)
        self.vb.enableAutoRange(self.vb.YAxis, True)
        #self.range = None
        #self.updateRange()
        #self.vb.setMouseEnabled(False, False)

        #def updateRange(self):
        #self.vb.autoRange()
        #if self.range is not None:
        #self.vb.setYRange(*self.range)
        #vr = self.vb.viewRect()

        #self.region.setBounds([vr.top(), vr.bottom()])

    def setImageItem(self, img):
        self.imageItem = img
        img.sigImageChanged.connect(self.imageChanged)
        img.setLookupTable(self.getLookupTable)  ## send function pointer, not the result
        #self.gradientChanged()
        self.regionChanged()
        self.imageChanged()
        #self.vb.autoRange()

    def viewRangeChanged(self):
        self.update()

    def gradientChanged(self):
        if self.imageItem is not None:
            if self.gradient.isLookupTrivial():
                self.imageItem.setLookupTable(None)  #lambda x: x.astype(np.uint8))
            else:
                self.imageItem.setLookupTable(self.getLookupTable)  ## send function pointer, not the result

        self.lut = None
        #if self.imageItem is not None:
        #self.imageItem.setLookupTable(self.gradient.getLookupTable(512))
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
        #if self.imageItem is not None:
        #self.imageItem.setLevels(self.region.getRegion())
        self.sigLevelChangeFinished.emit(self)
        #self.update()

    def regionChanging(self):
        if self.imageItem is not None:
            self.imageItem.setLevels(np.exp(self.region.getRegion()))
        self.sigLevelsChanged.emit(self)
        self.update()

    def imageChanged(self, autoRange=False):
        prof = debug.Profiler('HistogramLUTItem.imageChanged', disabled=True)
        h = list(self.imageItem.getHistogram(bins=1000))

        prof.mark('get histogram')
        if h[0] is None:
            return

        h[1][1:] = np.log(h[1][1:])
        h[0][1:] = np.log(h[0][1:])

        h[0][0] = 0
        h[1][0] = h[1][1]
        if self.orientation == 'horizontal':
            self.plot.setData(h[0], h[1])
        elif self.orientation == 'vertical':
            self.plot.setData(h[1], h[0])

        self.hist_x_range = np.max(h[0]) - np.min(h[0])
        # if self.percentageLevel:
        # if self.first_image:
        #         self.region.setRegion([h[0, 0], h[0, -1]])
        #         self.old_hist_x_range = self.hist_x_range
        #         self.first_image = False
        #     else:
        #         region_fraction = np.array(self.region.getRegion()) / self.old_hist_x_range
        #         self.region.setRegion(region_fraction * self.hist_x_range)
        #         self.old_hist_x_range = self.hist_x_range
        #
        #         #self.vb.setRange(yRange=[0, 1.2 * np.max(h[1])])

    def getLevels(self):
        return self.region.getRegion()

    def setLevels(self, mn, mx):
        self.region.setRegion([mn, mx])

    def empty_function(self, *args):
        pass


class LogarithmRegionItem(LinearRegionItem):
    def __contains__(self, values=[0, 1], orientation=None, brush=None, movable=True, bounds=None):
        super(LogarithmRegionItem, self).__init__(values, orientation, brush, movable, bounds)

    def getRegion(self):
        """Return the values at the edges of the region."""
        # if self.orientation[0] == 'h':
        #r = (self.bounds.top(), self.bounds.bottom())
        #else:
        #r = (self.bounds.left(), self.bounds.right())
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
        self.lineMoved()
        self.lineMoveFinished()