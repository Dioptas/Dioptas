from datetime import time

__author__ = 'Clemens Prescher'

import pyqtgraph as pg
import numpy as np
from PyQt4 import QtCore, QtGui
from HorHistogramLUTItem import HorHistogramLUTItem
import matplotlib.pyplot as plt
import time


class ImgView(object):
    def __init__(self, pg_layout, orientation='vertical'):
        self.pg_layout = pg_layout
        self.orientation = orientation

        self.create_graphics()
        self.create_scatter_plot()
        self.modify_mouse_behavior()

        self.mouse_move_observer = []
        self.left_click_observer = []
        self.left_double_click_observer = []
        self.img_data = None
        self.mask_data = None

    def create_graphics(self):
        #create basic image view


        #self.img_histogram_LUT = pg.HistogramLUTItem(self.data_img_item)
        if self.orientation == 'horizontal':

            self.img_view_box = self.pg_layout.addViewBox(1, 0)
            #create the item handling the Data img
            self.data_img_item = pg.ImageItem()
            self.img_view_box.addItem(self.data_img_item)
            self.img_histogram_LUT = HorHistogramLUTItem(self.data_img_item)
            self.pg_layout.addItem(self.img_histogram_LUT, 0, 0)

        elif self.orientation == 'vertical':
            self.img_view_box = self.pg_layout.addViewBox(0, 0)
            #create the item handling the Data img
            self.data_img_item = pg.ImageItem()
            self.img_view_box.addItem(self.data_img_item)
            self.img_histogram_LUT = pg.HistogramLUTItem(self.data_img_item)
            self.img_histogram_LUT.axis.hide()
            self.pg_layout.addItem(self.img_histogram_LUT, 0, 1)

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
        ind = np.where(np.cumsum(hist_y) < (0.995 * np.sum(hist_y)))
        self.img_histogram_LUT.setLevels(np.min(np.min(self.img_data)), hist_x[ind[0][-1]])

    def add_scatter_data(self, x, y):
        self.img_scatter_plot_item.addPoints(x=y, y=x)

    def clear_scatter_plot(self):
        self.img_scatter_plot_item.setData(x=None, y=None)

    def add_left_click_observer(self, function):
        self.left_click_observer.append(function)

    def del_left_click_observer(self, function):
        try:
            self.left_click_observer.remove(function)
        except ValueError:
            pass

    def add_left_double_click_observer(self, function):
        self.left_double_click_observer.append(function)

    def del_left_double_click_observer(self, function):
        try:
            self.left_double_click_observer.remove(function)
        except ValueError:
            pass


    def add_mouse_move_observer(self, function):
        self.mouse_move_observer.append(function)

    def del_mouse_move_observer(self, function):
        try:
            self.mouse_move_observer.remove(function)
        except ValueError:
            pass

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
            if self.img_data is not None:
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
        if ev.button() == QtCore.Qt.LeftButton:
            pos = self.img_view_box.mapFromScene(ev.pos())
            pos = self.img_scatter_plot_item.mapFromScene(2 * ev.pos() - pos)
            for function in self.left_double_click_observer:
                function(pos.x(), pos.y())

    def myMouseDragEvent(self, ev, axis=None):
        #most of this code is copied behavior of left click mouse drag from the original code
        ev.accept()
        pos = ev.pos()
        lastPos = ev.lastPos()
        dif = pos - lastPos
        dif *= -1
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
            if self.img_data is not None:
                if (view_range[0][1] - view_range[0][0]) > self.img_data.shape[1] and \
                                (view_range[1][1] - view_range[1][0]) > self.img_data.shape[0]:
                    self.img_view_box.autoRange()
                else:
                    pg.ViewBox.wheelEvent(self.img_view_box, ev)
            else:
                pg.ViewBox.wheelEvent(self.img_view_box, ev)


class CalibrationCakeView(ImgView):
    def __init__(self, pg_layout, orientation='vertical'):
        super(CalibrationCakeView, self).__init__(pg_layout, orientation)
        self.img_view_box.setAspectLocked(False)
        self._cross_activated = False
        self.create_cross()
        self.add_left_click_observer(self.set_cross)

    def create_cross(self):
        self.vertical_line = pg.InfiniteLine(angle=0, pen=pg.mkPen(color=(255, 0, 0), width=2))
        self.horizontal_line = pg.InfiniteLine(angle=90, pen=pg.mkPen(color=(255, 0, 0), width=2))
        self.activate_cross()

    def activate_cross(self):
        if not self._cross_activated:
            self.img_view_box.addItem(self.vertical_line)
            self.img_view_box.addItem(self.horizontal_line)
            self._cross_activated = True

    def deactivate_cross(self):
        if self._cross_activated:
            self.img_view_box.removeItem(self.vertical_line)
            self.img_view_box.removeItem(self.horizontal_line)
            self._cross_activated = False

    def set_cross(self, x, y):
        self.vertical_line.setValue(x)
        self.horizontal_line.setValue(y)


class MaskImgView(ImgView):
    def __init__(self, pg_layout, orientation='vertical'):
        super(MaskImgView, self).__init__(pg_layout, orientation)
        self.mask_img_item = pg.ImageItem()
        self.img_view_box.addItem(self.mask_img_item)
        self.set_color()

    def plot_mask(self, mask_data):
        self.mask_data = np.int16(mask_data)
        self.mask_img_item.setImage(self.mask_data.T, autoRange=True, autoHistogramRange=True,
                                    autoLevels=True)

    def create_color_map(self, color):
        steps = np.array([0, 1])
        colors = np.array([[0, 0, 0, 0], color], dtype=np.ubyte)
        color_map = pg.ColorMap(steps, colors)
        return color_map.getLookupTable(0.0, 1.0, 256, True)

    def set_color(self, color=None):
        if not color: color = [255, 0, 0, 255]
        self.mask_img_item.setLookupTable(self.create_color_map(color))

    def draw_circle(self, x=0, y=0):
        circle = MyCircle(x, y, 0)
        self.img_view_box.addItem(circle)
        return circle

    def draw_rectangle(self, x, y):
        rect = MyRectangle(x, y, 0, 0)
        self.img_view_box.addItem(rect)
        return rect

    def draw_point(self, radius=0):
        point = MyPoint(radius)
        self.img_view_box.addItem(point)
        return point

    def draw_polygon(self, x, y):
        polygon = MyPolygon(x, y)
        self.img_view_box.addItem(polygon)
        return polygon


from Tools import marchingsquares


class IntegrationImgView(MaskImgView, CalibrationCakeView):
    def __init__(self, pg_layout, orientation='vertical'):
        super(IntegrationImgView, self).__init__(pg_layout, orientation)
        self.deactivate_cross()
        self.create_circle_scatter_item()
        self.img_view_box.setAspectLocked(True)

    def create_circle_scatter_item(self):
        self.circle_plot_item = pg.ScatterPlotItem(pen=pg.mkPen(color='g', width=2), size=0.5, brush=pg.mkBrush('g'))
        self.img_view_box.addItem(self.circle_plot_item)

    def set_circle_scatter_tth(self, tth, level):
        data = marchingsquares.isocontour(tth, level)
        self.circle_plot_item.setData(x=data[:, 0], y=data[:, 1])

    def activate_circle_scatter(self):
        self.img_view_box.addItem(self.circle_plot_item)

    def deactivate_circle_scatter(self):
        self.img_view_box.removeItem(self.circle_plot_item)


class MyPolygon(QtGui.QGraphicsPolygonItem):
    def __init__(self, x, y):
        QtGui.QGraphicsPolygonItem.__init__(self)
        self.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255)))
        self.setBrush(QtGui.QBrush(QtGui.QColor(255, 0, 0, 150)))

        self.vertices = []
        self.vertices.append(QtCore.QPoint(y, x))

    def set_size(self, x, y):
        temp_points = list(self.vertices)
        temp_points.append(QtCore.QPointF(x, y))
        self.setPolygon(QtGui.QPolygonF(temp_points))

    def add_point(self, y, x):
        self.vertices.append(QtCore.QPointF(x, y))
        self.setPolygon(QtGui.QPolygonF(self.vertices))


class MyCircle(QtGui.QGraphicsEllipseItem):
    def __init__(self, x, y, radius):
        QtGui.QGraphicsEllipseItem.__init__(self, y - radius, x - radius, radius * 2, radius * 2)
        self.radius = radius
        self.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255)))
        self.setBrush(QtGui.QBrush(QtGui.QColor(255, 0, 0, 150)))
        self.center_x = x
        self.center_y = y

    def set_size(self, y, x):
        self.radius = np.sqrt((y - self.center_y) ** 2 + (x - self.center_x) ** 2)
        self.setRect(self.center_y - self.radius, self.center_x - self.radius, self.radius * 2, self.radius * 2)

    def set_position(self, y, x):
        self.setRect(y - self.radius, x - self.radius, self.radius * 2, self.radius * 2)


class MyPoint(QtGui.QGraphicsEllipseItem):
    def __init__(self, radius):
        QtGui.QGraphicsEllipseItem.__init__(self, 0, 0, radius * 2, radius * 2)
        self.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255)))
        self.setBrush(QtGui.QBrush(QtGui.QColor(255, 0, 0, 150)))
        self.radius = radius
        self.x = 0
        self.y = 0

    def set_position(self, y, x):
        self.x = x
        self.y = y
        self.setRect(y - self.radius, x - self.radius, self.radius * 2, self.radius * 2)

    def set_radius(self, radius):
        self.radius = radius
        self.set_position(self.y, self.x)
        return self.radius

    def inc_size(self, step):
        self.radius = self.radius + step
        self.set_position(self.y, self.x)
        return self.radius


class MyRectangle(QtGui.QGraphicsRectItem):
    def __init__(self, x, y, width, height):
        QtGui.QGraphicsRectItem.__init__(self, y, x - height, width, height)
        self.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255)))
        self.setBrush(QtGui.QBrush(QtGui.QColor(255, 0, 0, 150)))

        self.initial_x = x
        self.initial_y = y

    def set_size(self, y, x):
        height = x - self.initial_x
        width = y - self.initial_y
        self.setRect(self.initial_y, self.initial_x + height, width, -height)






