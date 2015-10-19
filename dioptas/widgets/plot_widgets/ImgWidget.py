# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2014  Clemens Prescher (clemens.prescher@gmail.com)
# GSECARS, University of Chicago
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

from __future__ import absolute_import


__author__ = 'Clemens Prescher'

import pyqtgraph as pg
from pyqtgraph.exporters.ImageExporter import ImageExporter
import numpy as np
from PyQt4 import QtCore, QtGui

from .HistogramLUTItem import HistogramLUTItem


class ImgWidget(QtCore.QObject):
    mouse_moved = QtCore.pyqtSignal(float, float)
    mouse_left_clicked = QtCore.pyqtSignal(float, float)
    mouse_left_double_clicked = QtCore.pyqtSignal(float, float)

    def __init__(self, pg_layout, orientation='vertical'):
        super(ImgWidget, self).__init__()
        self.pg_layout = pg_layout
        self.orientation = orientation

        self.create_graphics()
        self.create_scatter_plot()
        self.modify_mouse_behavior()

        self.img_data = None
        self.mask_data = None

    def create_graphics(self):
        #self.img_histogram_LUT = pg.HistogramLUTItem(self.data_img_item)
        if self.orientation == 'horizontal':

            self.img_view_box = self.pg_layout.addViewBox(1, 0)
            #create the item handling the Data img
            self.data_img_item = pg.ImageItem()
            self.img_view_box.addItem(self.data_img_item)
            self.img_histogram_LUT = HistogramLUTItem(self.data_img_item)
            self.pg_layout.addItem(self.img_histogram_LUT, 0, 0)

        elif self.orientation == 'vertical':
            self.img_view_box = self.pg_layout.addViewBox(0, 0)
            #create the item handling the Data img
            self.data_img_item = pg.ImageItem()
            self.img_view_box.addItem(self.data_img_item)
            self.img_histogram_LUT = HistogramLUTItem(self.data_img_item, orientation='vertical')
            # self.img_histogram_LUT.axis.hide()
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

    def save_img(self, filename):
        exporter = ImageExporter(self.img_view_box)
        exporter.parameters()['width'] = 2048
        exporter.export(filename)

    def set_range(self, x_range, y_range):
        img_bounds = self.img_view_box.childrenBoundingRect()
        if x_range[0]<=img_bounds.left() and \
            x_range[1]>=img_bounds.right() and \
            y_range[0]<=img_bounds.bottom() and \
            y_range[1]>=img_bounds.top():
            self.img_view_box.autoRange()
            return
        self.img_view_box.setRange(xRange=x_range, yRange=y_range)



    def auto_range(self):
        hist_x, hist_y = self.img_histogram_LUT.hist_x, self.img_histogram_LUT.hist_y

        hist_y_cumsum = np.cumsum(hist_y)
        hist_y_sum = np.sum(hist_y)

        max_ind = np.where(hist_y_cumsum < (0.996 * hist_y_sum))
        min_ind = np.where(hist_y_cumsum > (0.05 * hist_y_sum))

        min_level = hist_x[min_ind[0][1]]

        if len(max_ind[0]):
            max_level = hist_x[max_ind[0][-1]]
        else:
            max_level = 0.5 * np.max(hist_x)

        self.img_histogram_LUT.setLevels(min_level, max_level)

    def add_scatter_data(self, x, y):
        self.img_scatter_plot_item.addPoints(x=y, y=x)

    def clear_scatter_plot(self):
        self.img_scatter_plot_item.setData(x=None, y=None)

    def hide_scatter_plot(self):
        self.img_scatter_plot_item.hide()

    def show_scatter_plot(self):
        self.img_scatter_plot_item.show()

    def mouseMoved(self, pos):
        pos = self.data_img_item.mapFromScene(pos)
        self.mouse_moved.emit(pos.x(), pos.y())

    def modify_mouse_behavior(self):
        #different mouse handlers
        self.img_view_box.setMouseMode(self.img_view_box.RectMode)

        self.pg_layout.scene().sigMouseMoved.connect(self.mouseMoved)
        self.img_view_box.mouseClickEvent = self.myMouseClickEvent
        self.img_view_box.mouseDragEvent = self.myMouseDragEvent
        self.img_view_box.mouseDoubleClickEvent = self.myMouseDoubleClickEvent
        self.img_view_box.wheelEvent = self.myWheelEvent

    def myMouseClickEvent(self, ev):
        if ev.button() == QtCore.Qt.RightButton or \
                (ev.button() == QtCore.Qt.LeftButton and
                         ev.modifiers() & QtCore.Qt.ControlModifier):
            view_range = np.array(self.img_view_box.viewRange()) * 2
            if self.img_data is not None:
                if (view_range[0][1] - view_range[0][0]) > self.img_data.shape[1] and \
                                (view_range[1][1] - view_range[1][0]) > self.img_data.shape[0]:
                    self.img_view_box.autoRange()
                else:
                    self.img_view_box.scaleBy(2)

        elif ev.button() == QtCore.Qt.LeftButton:
            pos = self.img_view_box.mapFromScene(ev.pos())
            pos = self.img_scatter_plot_item.mapFromScene(2 * ev.pos() - pos)
            y = pos.x()
            x = pos.y()
            self.mouse_left_clicked.emit(x, y)

    def myMouseDoubleClickEvent(self, ev):
        if ev.button() == QtCore.Qt.RightButton:
            self.img_view_box.autoRange()
        if ev.button() == QtCore.Qt.LeftButton:
            pos = self.img_view_box.mapFromScene(ev.pos())
            pos = self.img_scatter_plot_item.mapFromScene(2 * ev.pos() - pos)
            self.mouse_left_double_clicked.emit(pos.x(), pos.y())

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

        if ev.button() == QtCore.Qt.RightButton or \
                (ev.button() == QtCore.Qt.LeftButton and \
                             ev.modifiers() & QtCore.Qt.ControlModifier):
            #determine the amount of translation
            tr = dif * mask
            tr = self.img_view_box.mapToView(tr) - self.img_view_box.mapToView(pg.Point(0, 0))
            x = tr.x()
            y = tr.y()

            self.img_view_box.translateBy(x=x, y=y)
            self.img_view_box.sigRangeChangedManually.emit(self.img_view_box.state['mouseEnabled'])
        else:
            if ev.isFinish():  ## This is the final move in the drag; change the view scale now
                #print "finish"
                self.img_view_box.rbScaleBox.hide()
                #ax = QtCore.QRectF(Point(self.pressPos), Point(self.mousePos))
                ax = QtCore.QRectF(pg.Point(ev.buttonDownPos(ev.button())), pg.Point(pos))
                ax = self.img_view_box.childGroup.mapRectFromParent(ax)
                self.img_view_box.showAxRect(ax)
                self.img_view_box.axHistoryPointer += 1
                self.img_view_box.axHistory = self.img_view_box.axHistory[:self.img_view_box.axHistoryPointer] + [ax]
            else:
                ## update shape of scale box
                self.img_view_box.updateScaleBox(ev.buttonDownPos(), ev.pos())

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


class CalibrationCakeWidget(ImgWidget):
    def __init__(self, pg_layout, orientation='vertical'):
        super(CalibrationCakeWidget, self).__init__(pg_layout, orientation)
        self.img_view_box.setAspectLocked(False)
        self._vertical_line_activated = False
        self.create_vertical_line()
        self.mouse_left_clicked.connect(self.set_vertical_line_pos)

    def create_vertical_line(self):
        self.vertical_line = pg.InfiniteLine(angle=90, pen=pg.mkPen(color=(0, 255, 0), width=2))
        self.activate_vertical_line()

    def activate_vertical_line(self):
        if not self._vertical_line_activated:
            self.img_view_box.addItem(self.vertical_line)
            self._vertical_line_activated = True

    def deactivate_vertical_line(self):
        if self._vertical_line_activated:
            self.img_view_box.removeItem(self.vertical_line)
            self._vertical_line_activated = False

    def set_vertical_line_pos(self, x, y):
        self.vertical_line.setValue(y)


class MaskImgWidget(ImgWidget):
    def __init__(self, pg_layout, orientation='vertical'):
        super(MaskImgWidget, self).__init__(pg_layout, orientation)
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


from pyFAI import marchingsquares


class IntegrationImgView(MaskImgWidget, CalibrationCakeWidget):
    def __init__(self, pg_layout, orientation='vertical'):
        super(IntegrationImgView, self).__init__(pg_layout, orientation)
        self.deactivate_vertical_line()
        self.create_circle_scatter_item()
        self.create_roi_item()
        self.img_view_box.setAspectLocked(True)

    def create_circle_scatter_item(self):
        self.circle_plot_item = pg.ScatterPlotItem(pen=pg.mkPen(color=(0, 255, 0, 255), width=1.1), size=0.4,
                                                   brush=pg.mkBrush('g'))
        self.img_view_box.addItem(self.circle_plot_item)

    def set_circle_scatter_tth(self, tth, level):
        data = marchingsquares.isocontour(tth, level)
        self.circle_plot_item.setData(x=data[:, 0], y=data[:, 1])

    def activate_circle_scatter(self):
        self.img_view_box.addItem(self.circle_plot_item)

    def deactivate_circle_scatter(self):
        self.img_view_box.removeItem(self.circle_plot_item)

    def create_roi_item(self):
        self.roi = MyROI([20, 20], [500, 500], pen=pg.mkPen(color=(0, 255, 0), size=2))
        self.roi.handlePen = QtGui.QPen(QtGui.QColor(0, 255, 0))
        self.roi.addScaleHandle([1, 1], [0, 0])
        self.roi.addScaleHandle([0, 1], [1, 0])
        self.roi.addScaleHandle([1, 0], [0, 1])
        self.roi.addScaleHandle([0, 0], [1, 1])

        self.roi_shade = RoiShade(self.img_view_box, self.roi)

    def activate_roi(self):
        self.img_view_box.addItem(self.roi)
        self.roi_shade.activate_rects()
        self.roi.blockSignals(False)

    def deactivate_roi(self):
        self.img_view_box.removeItem(self.roi)
        self.roi_shade.deactivate_rects()
        self.roi.blockSignals(True)


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


class MyROI(pg.ROI):
    def __init__(self, pos, size, pen, img_shape=(2048, 2048)):
        super(MyROI, self).__init__(pos, size, pen=pen)
        self.img_shape = img_shape
        self.base_mask = np.ones(img_shape)
        self.roi_mask = np.copy(self.base_mask)
        self.last_state = None

    def setMouseHover(self, hover):
        ## Inform the ROI that the mouse is(not) hovering over it
        if self.mouseHovering == hover:
            return
        self.mouseHovering = hover
        if hover:
            self.currentPen = pg.mkPen(255, 120, 0)
        else:
            self.currentPen = self.pen
        self.update()

    def getIndexLimits(self, img_shape):
        rect = self.parentBounds()
        x1 = np.round(rect.top())
        if x1 < 0:
            x1 = 0
        x2 = np.round(rect.top() + rect.height())
        if x2 > img_shape[0]:
            x2 = img_shape[0]
        y1 = np.round(rect.left())
        if y1 < 0:
            y1 = 0
        y2 = np.round(rect.left() + rect.width())
        if y2 > img_shape[1]:
            y2 = img_shape[1]
        return x1, x2, y1, y2

    def getRoiMask(self, img_shape):
        if not np.array_equal(np.array(img_shape), np.array(self.img_shape)):
            self.base_mask = np.ones(img_shape)
        if self.getState() == self.last_state:
            return self.roi_mask
        else:
            x1, x2, y1, y2 = self.getIndexLimits(img_shape)
            self.roi_mask = np.copy(self.base_mask)
            self.roi_mask[x1:x2, y1:y2] = 0
            self.last_state = self.getState()
            return self.roi_mask


class RoiShade(object):
    def __init__(self, view_box, roi, img_shape=(2048, 2048)):
        self.view_box = view_box
        self.img_shape = img_shape
        self.roi = roi
        self.active = False
        self.create_rect()


    def create_rect(self):
        color = QtGui.QColor(0, 0, 0, 100)
        self.left_rect = QtGui.QGraphicsRectItem()
        self.left_rect.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 0)))
        self.left_rect.setBrush(QtGui.QBrush(color))
        self.right_rect = QtGui.QGraphicsRectItem()
        self.right_rect.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 0)))
        self.right_rect.setBrush(QtGui.QBrush(color))

        self.top_rect = QtGui.QGraphicsRectItem()
        self.top_rect.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 0)))
        self.top_rect.setBrush(QtGui.QBrush(color))
        self.bottom_rect = QtGui.QGraphicsRectItem()
        self.bottom_rect.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 0)))
        self.bottom_rect.setBrush(QtGui.QBrush(color))


    def update_rects(self):
        roi_rect = self.roi.parentBounds()
        self.left_rect.setRect(0, 0, roi_rect.left(), self.img_shape[0])
        self.right_rect.setRect(roi_rect.right(), 0, self.img_shape[1] - roi_rect.right(), self.img_shape[0])
        self.top_rect.setRect(roi_rect.left(), roi_rect.bottom(), roi_rect.width(),
                              self.img_shape[0] - roi_rect.bottom())
        self.bottom_rect.setRect(roi_rect.left(), 0, roi_rect.width(), roi_rect.top())

    def activate_rects(self):
        if not self.active:
            self.roi.sigRegionChanged.connect(self.update_rects)
            self.view_box.addItem(self.left_rect)
            self.view_box.addItem(self.right_rect)
            self.view_box.addItem(self.top_rect)
            self.view_box.addItem(self.bottom_rect)
            self.active = True

    def deactivate_rects(self):
        if self.active:
            self.roi.sigRegionChanged.disconnect(self.update_rects)
            self.view_box.removeItem(self.left_rect)
            self.view_box.removeItem(self.right_rect)
            self.view_box.removeItem(self.top_rect)
            self.view_box.removeItem(self.bottom_rect)
            self.active = False





