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

    sigLookupTableChanged = QtCore.Signal(object)
    sigLevelsChanged = QtCore.Signal(object)
    sigLevelChangeFinished = QtCore.Signal(object)

    def __init__(self, image=None, fillHistogram=True):
        """
        If *image* (ImageItem) is provided, then the control will be automatically linked to the image and changes to the control will be immediately reflected in the image's appearance.
        By default, the histogram is rendered with a fill. For performance, set *fillHistogram* = False.
        """
        GraphicsWidget.__init__(self)
        self.lut = None
        self.imageItem = None
        self.first_image = True
        self.percentageLevel = False

        self.layout = QtGui.QGraphicsGridLayout()
        self.setLayout(self.layout)
        self.layout.setContentsMargins(1, 1, 1, 1)
        self.layout.setSpacing(0)
        self.vb = ViewBox()
        self.vb.setMaximumHeight(30)
        self.vb.setMinimumHeight(45)
        self.vb.setMouseEnabled(x=True, y=False)
        self.gradient = GradientEditorItem()
        self.gradient.setOrientation('top')
        self.gradient.loadPreset('grey')
        self.region = LinearRegionItem([0, 1], LinearRegionItem.Vertical)
        self.region.setZValue(1000)
        self.vb.addItem(self.region)
        self.layout.addItem(self.vb, 1, 0)
        self.layout.addItem(self.gradient, 0, 0)
        self.range = None
        self.gradient.setFlag(self.gradient.ItemStacksBehindParent)
        self.vb.setFlag(self.gradient.ItemStacksBehindParent)

        #self.grid = GridItem()
        #self.vb.addItem(self.grid)

        self.gradient.sigGradientChanged.connect(self.gradientChanged)
        self.region.sigRegionChanged.connect(self.regionChanging)
        self.region.sigRegionChangeFinished.connect(self.regionChanged)
        self.vb.sigRangeChanged.connect(self.viewRangeChanged)
        self.plot = PlotDataItem()
        self.fillHistogram(fillHistogram)

        self.vb.addItem(self.plot)
        self.autoHistogramRange()

        if image is not None:
            self.setImageItem(image)
            #self.setSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Expanding)

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
        p1 = self.vb.mapFromViewToItem(self, Point(rgn[0], self.vb.viewRect().center().y()))
        p2 = self.vb.mapFromViewToItem(self, Point(rgn[1], self.vb.viewRect().center().y()))
        gradRect = self.gradient.mapRectToParent(self.gradient.gradRect.rect())
        for pen in [fn.mkPen('k', width=3), pen]:
            p.setPen(pen)
            p.drawLine(p1, gradRect.bottomLeft())
            p.drawLine(p2, gradRect.bottomRight())
            p.drawLine(gradRect.bottomLeft(), gradRect.topLeft())
            p.drawLine(gradRect.bottomRight(), gradRect.topRight())
            #p.drawRect(self.boundingRect())


    def setHistogramRange(self, mn, mx, padding=0.1):
        """Set the Y range on the histogram plot. This disables auto-scaling."""
        self.vb.enableAutoRange(self.vb.YAxis, False)
        self.vb.setXRange(mn, mx, padding)
        #mn -= d*padding
        #mx += d*padding
        #self.range = [mn,mx]
        #self.updateRange()
        #self.vb.setMouseEnabled(False, True)
        #self.region.setBounds([mn,mx])

    def autoHistogramRange(self):
        """Enable auto-scaling on the histogram plot."""
        self.vb.enableAutoRange(self.vb.XYAxes)
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
        self.imageChanged(autoLevel=True)
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
            self.imageItem.setLevels(self.region.getRegion())
        self.sigLevelsChanged.emit(self)
        self.update()

    def imageChanged(self, autoLevel=False, autoRange=False):
        prof = debug.Profiler('HistogramLUTItem.imageChanged', disabled=True)
        h = np.array(self.imageItem.getHistogram())
        prof.mark('get histogram')
        if h[0] is None:
            return
        h[1, :] = np.log(h[1, :])
        self.plot.setData(*h)

        self.hist_x_range = np.max(h[0, :]) - np.min(h[0, :])
        if self.percentageLevel:
            if self.first_image:
                self.region.setRegion([h[0, 0], h[0, -1]])
                self.old_hist_x_range = self.hist_x_range
                self.first_image = False
            else:
                region_fraction = np.array(self.region.getRegion()) / self.old_hist_x_range
                self.region.setRegion(region_fraction * self.hist_x_range)
                self.old_hist_x_range = self.hist_x_range

        self.vb.setRange(yRange=[0, 1.1 * np.max(h[1, :])],
                         xRange=[0, np.max([self.region.getRegion()[1],
                                           np.max(h[0, :])])])

        prof.mark('set plot')
        if autoLevel:
            mn = h[0][0]
            mx = h[-1][0]
            self.region.setRegion([mn, mx])
            prof.mark('set region')
        prof.finish()

    def getLevels(self):
        return self.region.getRegion()

    def setLevels(self, mn, mx):
        self.region.setRegion([mn, mx])
