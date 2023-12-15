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

from pyqtgraph.graphicsItems.GraphicsWidget import GraphicsWidget
from pyqtgraph.graphicsItems.LabelItem import LabelItem
from qtpy import QtWidgets, QtCore, QtGui
from pyqtgraph import functions as fn
from pyqtgraph.Point import Point
from pyqtgraph.graphicsItems.ScatterPlotItem import ScatterPlotItem, drawSymbol
from pyqtgraph.graphicsItems.PlotDataItem import PlotDataItem
from pyqtgraph.graphicsItems.GraphicsWidgetAnchor import GraphicsWidgetAnchor

__all__ = ['LegendItem']


class LegendItem(GraphicsWidget, GraphicsWidgetAnchor):
    """
    Displays a legend used for describing the contents of a plot.
    LegendItems are most commonly created by calling PlotItem.addLegend().

    Note that this item should not be added directly to a PlotItem. Instead,
    Make it a direct descendant of the PlotItem::

        legend.setParentItem(plotItem)

    Codebase was copied from original pyqtgraph legenditem code. It had to be included here,
    because the Pull request for additional features needed has not been worked through yet.

    """

    def __init__(self, size=None, offset=None, horSpacing=25, verSpacing=0, box=True, labelAlignment='center',
                 showLines=True):
        """
        ==============  ===============================================================
        **Arguments:**
        size            Specifies the fixed size (width, height) of the legend. If
                        this argument is omitted, the legend will autimatically resize
                        to fit its contents.
        offset          Specifies the offset position relative to the legend's parent.
                        Positive values offset from the left or top; negative values
                        offset from the right or bottom. If offset is None, the
                        legend must be anchored manually by calling anchor() or
                        positioned by calling setPos().
        horSpacing      Specifies the spacing between the line symbol and the label.
        verSpacing      Specifies the spacing between individual entries of the legend
                        vertically. (Can also be negative to have them really close)
        box             Specifies if the Legend should will be drawn with a rectangle
                        around it.
        labelAlignment  Specifies the alignment of the label texts. Possible values are
                        "center", "left" or "right".
        showLines       Specifies whether or not the lines should be shown in the legend.
                        If value is "False" it will only show the labels with the corresponding
                        text color.
        ==============  ===============================================================

        """

        GraphicsWidget.__init__(self)
        GraphicsWidgetAnchor.__init__(self)
        self.setFlag(self.ItemIgnoresTransformations)
        self.layout = QtWidgets.QGraphicsGridLayout()
        self.layout.setVerticalSpacing(verSpacing)
        self.layout.setHorizontalSpacing(horSpacing)
        self._horSpacing = horSpacing
        self._verSpacing = verSpacing
        self.setLayout(self.layout)
        self.legendItems = []
        self.plotItems = []
        self.hiddenFlag = []
        self.size = size
        self.offset = offset
        self.box = box
        self.label_alignment = labelAlignment
        self.showLines = showLines
        # A numItems variable needs to be introduced, because chaining removeItem and addItem function in random order,
        # will otherwise lead to writing in the same layout row. Idea here is to always insert LabelItems on larger
        # and larger layout row numbers. The GraphicsGridlayout item will not care about empty rows.
        self.numItems = 0
        if size is not None:
            self.setGeometry(QtCore.QRectF(0, 0, self.size[0], self.size[1]))

    def setParentItem(self, p):
        ret = GraphicsWidget.setParentItem(self, p)
        if self.offset is not None:
            offset = Point(self.offset)
            anchorx = 1 if offset[0] <= 0 else 0
            anchory = 1 if offset[1] <= 0 else 0
            anchor = (anchorx, anchory)
            self.anchor(itemPos=anchor, parentPos=anchor, offset=offset)
        return ret

    def addItem(self, item, name):
        """
        Add a new entry to the legend.

        ==============  ========================================================
        **Arguments:**
        item            A PlotDataItem from which the line and point style
                        of the item will be determined or an instance of
                        ItemSample (or a subclass), allowing the item display
                        to be customized.
        title           The title to display for this item. Simple HTML allowed.
        ==============  ========================================================
        """

        # get item color
        pen = fn.mkPen(item.opts['pen'])
        color = pen.color()
        color_str = color.name()

        # create label with same color
        label = LabelItem()
        label.setAttr('color', color_str)
        label.setAttr('justify', self.label_alignment)
        label.setText(name)

        if isinstance(item, ItemSample):
            sample = item
        else:
            sample = ItemSample(item)

        self.legendItems.append((sample, label))
        self.hiddenFlag.append(False)
        self.plotItems.append(item)
        if self.showLines:
            self.layout.addItem(sample, self.numItems, 0)
        self.layout.addItem(label, self.numItems, 1)
        self.numItems += 1
        self.updateSize()

    def removeItem(self, name):
        """
        Removes one item from the legend.

        ==============  ========================================================
        **Arguments:**
        name            Either the name displayed for this item or the originally
                        added item object.
        ==============  ========================================================
        """
        # Thanks, Ulrich!
        # cycle for a match
        ind = 0
        for sample, label in self.legendItems:
            if label.text == name:  # hit
                self.legendItems.remove((sample, label))  # remove from itemlist
                if not self.hiddenFlag[ind]:
                    if self.showLines:
                        self.layout.removeItem(sample)  # remove from layout
                    self.layout.removeItem(label)
                    sample.close()  # remove from drawing
                    label.close()
                self.updateSize()  # redraq box
                del self.hiddenFlag[ind]
                return
            ind += 1

        for ind, item in enumerate(self.plotItems):
            if item == name:
                sample, label = self.legendItems[ind]
                self.plotItems.remove(item)

                if not self.hiddenFlag[ind]:
                    if self.showLines:
                        self.layout.removeItem(sample)
                    self.layout.removeItem(label)
                sample.close()
                label.close()
                self.legendItems.remove((sample, label))
                self.updateSize()
                del self.hiddenFlag[ind]

    def hideItem(self, ind):
        sample_item, label_item = self.legendItems[ind]
        if not self.hiddenFlag[ind]:
            if self.showLines:
                self.layout.removeItem(sample_item)
                sample_item.hide()
            self.layout.removeItem(label_item)
            label_item.hide()
        self.hiddenFlag[ind] = True
        self.updateSize()

    def showItem(self, ind):
        sample_item, label_item = self.legendItems[ind]
        if self.hiddenFlag[ind]:
            if self.showLines:
                self.layout.addItem(sample_item, ind, 0)
                sample_item.show()
            self.layout.addItem(label_item, ind, 1)
            label_item.show()
        self.hiddenFlag[ind] = False
        self.updateSize()

    def setItemColor(self, ind, color):
        sample_item, label_item = self.legendItems[ind]
        label_item.setAttr('color', color)
        label_item.setText(label_item.text)

    def renameItem(self, ind, name):
        sample_item, label_item = self.legendItems[ind]
        label_item.setText(name)
        self.updateSize()

    def updateSize(self):
        if self.size is not None:
            return
        # we only need to set geometry to 0, as now the horizontal and vertical spacing is set in
        # __init__.
        self.setGeometry(0, 0, 0, 0)

    def boundingRect(self):
        return QtCore.QRectF(0, 0, self.width(), self.height())

    def paint(self, p, *args):
        if self.box:
            p.setPen(fn.mkPen(255, 255, 255, 100))
            p.setBrush(fn.mkBrush(100, 100, 100, 50))
            p.drawRect(self.boundingRect())

    def hoverEvent(self, ev):
        ev.acceptDrags(QtCore.Qt.LeftButton)

    def mouseDragEvent(self, ev):
        if ev.button() == QtCore.Qt.LeftButton:
            dpos = ev.pos() - ev.lastPos()
            self.autoAnchor(self.pos() + dpos)


class ItemSample(GraphicsWidget):
    """ Class responsible for drawing a single item in a LegendItem (sans label).

    This may be subclassed to draw custom graphics in a Legend.
    """

    ## Todo: make this more generic; let each item decide how it should be represented.
    def __init__(self, item):
        GraphicsWidget.__init__(self)
        self.item = item

    def boundingRect(self):
        return QtCore.QRectF(0, 0, 20, 20)

    def paint(self, p, *args):
        # p.setRenderHint(p.Antialiasing)  # only if the data is antialiased.
        opts = self.item.opts

        if opts.get('fillLevel', None) is not None and opts.get('fillBrush', None) is not None:
            p.setBrush(fn.mkBrush(opts['fillBrush']))
            p.setPen(fn.mkPen(None))
            p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(2, 18), QtCore.QPointF(18, 2), QtCore.QPointF(18, 18)]))

        if not isinstance(self.item, ScatterPlotItem):
            p.setPen(fn.mkPen(opts['pen']))
            p.drawLine(2, 18, 18, 2)

        symbol = opts.get('symbol', None)
        if symbol is not None:
            if isinstance(self.item, PlotDataItem):
                opts = self.item.scatter.opts

            pen = fn.mkPen(opts['pen'])
            brush = fn.mkBrush(opts['brush'])
            size = opts['size']

            p.translate(10, 10)
            path = drawSymbol(p, symbol, size, pen, brush)
