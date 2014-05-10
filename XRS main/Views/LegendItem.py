from pyqtgraph.graphicsItems.GraphicsWidget import GraphicsWidget
from pyqtgraph.graphicsItems.LabelItem import LabelItem
from pyqtgraph.Qt import QtGui, QtCore
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

    """

    def __init__(self, size=None, offset=None, h_spacing=10, v_spacing=0, box=True):
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
        ==============  ===============================================================

        """

        GraphicsWidget.__init__(self)
        GraphicsWidgetAnchor.__init__(self)
        self.setFlag(self.ItemIgnoresTransformations)
        self.layout = QtGui.QGraphicsGridLayout()
        self.layout.setVerticalSpacing(v_spacing)
        self.layout.setHorizontalSpacing(h_spacing)
        self.setLayout(self.layout)
        self.legend_items = []
        self.plot_items = []
        self.size = size
        self.offset = offset
        self.h_spacing = h_spacing
        self.v_spacing = v_spacing
        self.box = box
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
        label = LabelItem(name)
        if isinstance(item, ItemSample):
            sample = item
        else:
            sample = ItemSample(item)

        self.legend_items.append((sample, label))
        self.plot_items.append(item)
        self.layout.addItem(sample, self.numItems, 0)
        self.layout.addItem(label, self.numItems, 1)
        self.numItems += 1
        self.updateSize()

    # def removeItem(self, name):
    #     """
    #     Removes one item from the legend.
    #
    #     ==============  ========================================================
    #     **Arguments:**
    #     title           The title displayed for this item.
    #     ==============  ========================================================
    #     """
    #     # Thanks, Ulrich!
    #     # cycle for a match
    #     for sample, label in self.legend_items:
    #         if label.text == name:  # hit
    #             self.legend_items.remove( (sample, label) )    # remove from itemlist
    #             self.layout.removeItem(sample)          # remove from layout
    #             sample.close()                          # remove from drawing
    #             self.layout.removeItem(label)
    #             label.close()
    #             self.updateSize()                       # redraq box

    def removeItem(self, plotItem):
        for ind, item in enumerate(self.plot_items):
            if item == plotItem:
                sample, label = self.legend_items[ind]
                self.plot_items.remove(item)
                self.layout.removeItem(sample)
                sample.close()
                self.layout.removeItem(label)
                label.close()
                self.legend_items.remove((sample, label))
                self.updateSize()

    def updateSize(self):
        if self.size is not None:
            return

        height = 0
        width = 0
        #print("-------")

        self.setGeometry(0, 0, 0, 0)  #needed to let h_spacing parameter work
        for sample, label in self.legend_items:
            height += max(sample.height(), label.height())
            width = max(width, sample.width() + label.width())

        self.setGeometry(0, 0, width + 35 + self.h_spacing, height)

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
        return QtCore.QRectF(0, 0, 15, 15)

    def paint(self, p, *args):
        #p.setRenderHint(p.Antialiasing)  # only if the data is antialiased.
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


