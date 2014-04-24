__author__ = 'Clemens Prescher'

import pyqtgraph as pg
import numpy as np
from PyQt4 import QtCore, QtGui


class ImgView(object):
    def __init__(self, pg_layout):
        self.pg_layout = pg_layout

        self.create_graphics()
        self.create_scatter_plot()
        self.modify_mouse_behavior()

        self.mouse_move_observer = []
        self.left_click_observer = []

    def create_graphics(self):
        #create basic image view
        self.img_view_box = self.pg_layout.addViewBox()

        #create the item handling the Data img
        self.data_img_item = pg.ImageItem()
        self.img_view_box.addItem(self.data_img_item)

        #creating the histogram with colorbar-chooser
        self.img_histogram_LUT = pg.HistogramLUTItem(self.data_img_item)
        self.img_histogram_LUT.axis.hide()
        self.pg_layout.addItem(self.img_histogram_LUT)


        self.img_view_box.setAspectLocked()

    def create_scatter_plot(self):
        self.img_scatter_plot_item = pg.ScatterPlotItem(pen=pg.mkPen('w'), brush=pg.mkBrush('r'))
        self.img_view_box.addItem(self.img_scatter_plot_item)

    def plot_image(self, img_data, autoRange=False):
        self.img_data = img_data
        self.data_img_item.setImage(img_data.T, autoRange)
        if autoRange:
            self.auto_range()

    def auto_range(self):
        hist_x, hist_y = self.data_img_item.getHistogram()
        ind = np.where(np.cumsum(hist_y)<(0.995*np.sum(hist_y)))
        self.img_histogram_LUT.setLevels(np.min(np.min(self.img_data)), hist_x[ind[0][-1]])

    def add_scatter_data(self, x, y):
        self.img_scatter_plot_item.addPoints(x=y, y=x)

    def clear_scatter_plot(self):
        self.img_scatter_plot_item.setData(x=None, y=None)

    def add_left_click_observer(self, function):
        self.left_click_observer.append(function)

    def add_mouse_move_observer(self, function):
        self.mouse_move_observer.append(function)


    def mouseMoved(self, pos):
        pos = self.data_img_item.mapFromScene(pos)
        for function in self.mouse_move_observer:
            function(pos.x(), pos.y())

    def modify_mouse_behavior(self):
        #different mouse handlers
        self.img_view_box.setMouseMode(self.img_view_box.RectMode)

        self.pg_layout.scene().sigMouseMoved.connect(self.mouseMoved)
        self.img_view_box.mouseClickEvent = self.myMouseClickEvent
        self.img_view_box.mouseDragEvent = self.myMouseDragEvent
        self.img_view_box.mouseDoubleClickEvent = self.myMouseDoubleClickEvent
        self.img_view_box.wheelEvent = self.myWheelEvent


    def myMouseClickEvent(self, ev):
        if ev.button() == QtCore.Qt.RightButton:
            view_range = np.array(self.img_view_box.viewRange()) * 2
            if (view_range[0][1] - view_range[0][0]) > self.img_data.shape[1] and \
                            (view_range[1][1] - view_range[1][0]) > self.img_data.shape[0]:
                self.img_view_box.autoRange()
            else:
                self.img_view_box.scaleBy(2)
        if ev.button() == QtCore.Qt.LeftButton:
            pos = self.img_view_box.mapFromScene(ev.pos())
            pos = self.img_scatter_plot_item.mapFromScene(2 * ev.pos() - pos)
            y = pos.x()
            x = pos.y()
            for function in self.left_click_observer:
                function(x, y)

    def myMouseDoubleClickEvent(self, ev):
        if ev.button() == QtCore.Qt.RightButton:
            self.img_view_box.autoRange()

    def myMouseDragEvent(self, ev, axis=None):
        #most of this code is copied behavior of left click mouse drag from the original code
        ev.accept()
        pos = ev.pos()
        lastPos = ev.lastPos()
        dif = pos - lastPos
        dif = dif * -1
        ## Ignore axes if mouse is disabled
        mouseEnabled = np.array(self.img_view_box.state['mouseEnabled'], dtype=np.float)
        mask = mouseEnabled.copy()
        if axis is not None:
            mask[1 - axis] = 0.0

        if ev.button() == QtCore.Qt.RightButton:
            #determine the amount of translation
            tr = dif * mask
            tr = self.img_view_box.mapToView(tr) - self.img_view_box.mapToView(pg.Point(0, 0))
            x = tr.x()
            y = tr.y()

            self.img_view_box.translateBy(x=x, y=y)
            self.img_view_box.sigRangeChangedManually.emit(self.img_view_box.state['mouseEnabled'])
        else:
            pg.ViewBox.mouseDragEvent(self.img_view_box, ev)

    def myWheelEvent(self, ev):
        if ev.delta() > 0:
            pg.ViewBox.wheelEvent(self.img_view_box, ev)
        else:
            view_range = np.array(self.img_view_box.viewRange())
            if (view_range[0][1] - view_range[0][0]) > self.img_data.shape[1] and \
                            (view_range[1][1] - view_range[1][0]) > self.img_data.shape[0]:
                self.img_view_box.autoRange()
            else:
                pg.ViewBox.wheelEvent(self.img_view_box, ev)


class CalibrationCakeView(ImgView):
    def __init__(self, pg_layout):
        super(CalibrationCakeView, self).__init__(pg_layout)
        self.img_view_box.setAspectLocked(False)
        self.create_cross()
        self.add_left_click_observer(self.set_cross)

    def create_cross(self):
        self.vertical_line = pg.InfiniteLine(angle=0, pen=pg.mkPen(color=(255,0,0), width=2))
        self.horizontal_line = pg.InfiniteLine(angle=90, pen=pg.mkPen(color=(255,0,0), width=2))

        self.img_view_box.addItem(self.vertical_line)
        self.img_view_box.addItem(self.horizontal_line)

    def set_cross(self, x, y):
        self.vertical_line.setValue(x)
        self.horizontal_line.setValue(y)



