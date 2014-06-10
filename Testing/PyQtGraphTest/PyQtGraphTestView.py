__author__ = 'Doomgoroth'

from PyQt4 import QtGui, QtCore
import pyqtgraph as pg
import numpy as np

from PyQtGraphTest_UI import Ui_Form


class PyQtGraphView(QtGui.QWidget, Ui_Form):
    def __init__(self):
        super(PyQtGraphView, self).__init__(None)
        self.setupUi(self)
        self.create_img_view()
        self.connect_mouse_movement()

    def create_img_view(self):
        self.img_view_box = self.pg_layout.addViewBox(0, 1)
        self.img_view_box.setAspectLocked(True)

        self.img_item = pg.ImageItem()
        self.img_view_box.addItem(self.img_item)

        self.left_axis = pg.AxisItem('left', linkView=self.img_view_box)
        self.pg_layout.addItem(self.left_axis, 0, 0)

        self.bot_axis = pg.AxisItem('bottom', linkView=self.img_view_box)
        self.pg_layout.addItem(self.bot_axis, 1, 0, 1, 2)

        self.img_item_left = pg.ImageItem()
        self.img_view_box.addItem(self.img_item_left)

        self.img_plot_item = pg.PlotCurveItem(pen='r')

        self.img_view_box.addItem(self.img_plot_item)

        self.img_histogram_LUT = pg.HistogramLUTItem(self.img_item)
        self.img_histogram_LUT.axis.hide()
        self.pg_layout.addItem(self.img_histogram_LUT, 0, 2)
        self.changeView()

        x = np.linspace(0, 1024)
        y = x
        self.img_plot_item.setData(x=x, y=x)


    def changeView(self):
        def myMouseClickEvent(ev):
            if ev.button() == QtCore.Qt.RightButton:
                self.img_view_box.scaleBy(3)
                print self.img_view_box.viewRange()

        def myMouseDoubleClickEvent(ev):
            if ev.button() == QtCore.Qt.RightButton:
                self.img_view_box.autoRange()

        def myMouseDragEvent(ev):
            if ev.button() == QtCore.Qt.RightButton:
                self.img_view_box.translateBy(ev.pos().x(), ev.pos().y())
            else:
                pg.ViewBox.mouseDragEvent(self.img_view_box, ev)

        self.img_view_box.setMouseMode(self.img_view_box.RectMode)
        self.img_view_box.mouseClickEvent = myMouseClickEvent
        self.img_view_box.mouseDragEvent = myMouseDragEvent
        self.img_view_box.mouseDoubleClickEvent = myMouseDoubleClickEvent

    def connect_mouse_movement(self):
        def mouseMoved(pos):
            pos = self.img_item.mapFromScene(pos)
            try:
                if pos.x() > 0 and pos.y() > 0:
                    str = "x: %.1f y: %.1f I: %.0f" % (pos.x(), pos.y(),
                                                       self.img_data[np.round(pos.x()), np.round(pos.y())])
                else:
                    str = "x: %.1f y: %.1f" % (pos.x(), pos.y())
            except IndexError:
                str = "x: %.1f y: %.1f" % (pos.x(), pos.y())

            self.pos_lbl.setText(str)

        self.pg_layout.scene().sigMouseMoved.connect(mouseMoved)


    def plot_image_right(self, img_data, autoRange=False, autoHistogramRange=False, autoLevels=False):
        self.img_item.setImage(img_data, autoRange=autoRange, autoHistogramRange=autoHistogramRange,
                               autoLevels=autoLevels)
        self.img_data = img_data

    def plot_image_left(self, img_data, autoRange=False, autoHistogramRange=False, autoLevels=False):
        img_data[1024:, :] = 0

        self.img_item_left.setImage(img_data, autoRange=autoRange, autoHistogramRange=autoHistogramRange,
                                    autoLevels=autoLevels)
        self.img_item_left.setLookupTable(self.create_color_map())
        # self.img_item_left.setLevels([0,1])

    def create_color_map(self):
        steps = np.array([0, 1])
        colors = np.array([[0, 0, 0, 0], [255, 0, 0, 255]], dtype=np.ubyte)
        color_map = pg.ColorMap(steps, colors)
        return color_map.getLookupTable(0.0, 1.0, 256, True)


