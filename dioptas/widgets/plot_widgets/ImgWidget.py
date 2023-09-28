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

from __future__ import absolute_import

import pyqtgraph as pg
from pyqtgraph import ViewBox
from pyqtgraph.exporters.ImageExporter import ImageExporter

import numpy as np
from skimage.measure import find_contours
from qtpy import QtCore, QtWidgets, QtGui

from .HistogramLUTItem import HistogramLUTItem
from .NormalizedImageItem import NormalizedImageItem
from .PatternWidget import ModifiedLinearRegionItem
from . import utils


class ImgWidget(QtCore.QObject):
    mouse_moved = QtCore.Signal(float, float)
    mouse_left_clicked = QtCore.Signal(float, float)
    mouse_left_double_clicked = QtCore.Signal(float, float)

    def __init__(self, pg_layout, orientation='vertical'):
        super(ImgWidget, self).__init__()
        self.pg_layout = pg_layout

        self.create_graphics()
        self.set_orientation(orientation)
        self.create_scatter_plot()
        self.modify_mouse_behavior()

        self.img_data = None
        self.mask_data = None

        self._max_range = True

    def create_graphics(self):
        self.img_view_box = self.pg_layout.addViewBox(row=1, col=1)  # type: ViewBox

        self.data_img_item = NormalizedImageItem()
        self.img_view_box.addItem(self.data_img_item)

        self.img_histogram_LUT_horizontal = HistogramLUTItem(self.data_img_item)
        self.pg_layout.addItem(self.img_histogram_LUT_horizontal, row=0, col=1)
        self.img_histogram_LUT_vertical = HistogramLUTItem(self.data_img_item, orientation='vertical')
        self.pg_layout.addItem(self.img_histogram_LUT_vertical, row=1, col=2)

    def create_mouse_click_item(self):
        self.mouse_click_item = pg.ScatterPlotItem()
        self.mouse_click_item.setSymbol('+')
        self.mouse_click_item.setSize(15)
        self.mouse_click_item.addPoints([0], [0])
        self.mouse_left_clicked.connect(self.set_mouse_click_position)
        self.activate_mouse_click_item()

    def set_mouse_click_position(self, x, y):
        self.mouse_click_item.setData([x], [y])

    def activate_mouse_click_item(self):
        if not self.mouse_click_item in self.img_view_box.addedItems:
            self.img_view_box.addItem(self.mouse_click_item)
            self.mouse_click_item.setVisible(True)  # oddly this is needed for the line to be displayed correctly

    def deactivate_mouse_click_item(self):
        if self.mouse_click_item in self.img_view_box.addedItems:
            self.img_view_box.removeItem(self.mouse_click_item)

    def set_orientation(self, orientation):
        if orientation == 'horizontal':
            self.img_histogram_LUT_vertical.hide()
            self.img_histogram_LUT_horizontal.show()
            self.img_histogram_LUT_vertical.gradient = self.img_histogram_LUT_horizontal.gradient
        elif orientation == 'vertical':
            self.img_histogram_LUT_horizontal.hide()
            self.img_histogram_LUT_vertical.show()
            self.img_histogram_LUT_horizontal.gradient = self.img_histogram_LUT_vertical.gradient
        self.orientation = orientation

    def create_scatter_plot(self):
        self.img_scatter_plot_item = pg.ScatterPlotItem(pen=pg.mkPen('w'), brush=pg.mkBrush('r'))
        self.img_view_box.addItem(self.img_scatter_plot_item)

    def plot_image(self, img_data, auto_level=False):
        self.img_data = img_data
        self.data_img_item.setImage(img_data.T, auto_level)
        if auto_level:
            self.auto_level()
        self.auto_range_rescale()

    def save_img(self, filename):
        exporter = ImageExporter(self.img_view_box)
        exporter.parameters()['width'] = 2048
        exporter.export(filename)

    def set_range(self, x_range, y_range):
        img_bounds = self.img_view_box.childrenBoundingRect()
        if x_range[0] <= img_bounds.left() and \
                x_range[1] >= img_bounds.right() and \
                y_range[0] <= img_bounds.bottom() and \
                y_range[1] >= img_bounds.top():
            self.img_view_box.autoRange()
            self._max_range = True
            return
        self.img_view_box.setRange(xRange=x_range, yRange=y_range)
        self._max_range = False

    def auto_range_rescale(self):
        if self._max_range:
            self.auto_range()
            return

        view_x_range, view_y_range = self.img_view_box.viewRange()
        if view_x_range[1] > self.img_data.shape[0] and \
                view_y_range[1] > self.img_data.shape[1]:
            self.auto_range()

    def auto_level(self):
        hist_x, hist_y = self.img_histogram_LUT_horizontal.hist_x, self.img_histogram_LUT_horizontal.hist_y
        min_level, max_level = utils.auto_level(hist_x, hist_y)
        self.img_histogram_LUT_vertical.setLevels(min_level, max_level)
        self.img_histogram_LUT_horizontal.setLevels(min_level, max_level)

    def add_scatter_data(self, x, y):
        self.img_scatter_plot_item.addPoints(x=y, y=x)

    def clear_scatter_plot(self):
        self.img_scatter_plot_item.setData(x=None, y=None)

    def remove_last_scatter_points(self, num_points):
        data_x, data_y = self.img_scatter_plot_item.getData()
        if not data_x.size == 0:
            data_x = data_x[:-num_points]
            data_y = data_y[:-num_points]
            self.img_scatter_plot_item.setData(data_x, data_y)

    def hide_scatter_plot(self):
        self.img_scatter_plot_item.hide()

    def show_scatter_plot(self):
        self.img_scatter_plot_item.show()

    def mouseMoved(self, pos):
        pos = self.data_img_item.mapFromScene(pos)
        self.mouse_moved.emit(pos.x(), pos.y())

    def modify_mouse_behavior(self):
        # different mouse handlers
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
                    self.auto_range()
                else:
                    self.img_view_box.scaleBy((2, 2))

        elif ev.button() == QtCore.Qt.LeftButton:
            pos = self.img_view_box.mapFromScene(ev.pos())
            pos = self.img_scatter_plot_item.mapFromScene(2 * ev.pos() - pos)
            self.mouse_left_clicked.emit(pos.x(), pos.y())

    def myMouseDoubleClickEvent(self, ev):
        if ev.button() == QtCore.Qt.RightButton:
            self.auto_range()
        if ev.button() == QtCore.Qt.LeftButton:
            pos = self.img_view_box.mapFromScene(ev.pos())
            pos = self.img_scatter_plot_item.mapFromScene(2 * ev.pos() - pos)
            self.mouse_left_double_clicked.emit(pos.x(), pos.y())

    def myMouseDragEvent(self, ev, axis=None):
        # most of this code is copied behavior of left click mouse drag from the original code
        ev.accept()
        pos = ev.pos()
        lastPos = ev.lastPos()
        dif = pos - lastPos
        dif *= -1
        ## Ignore axes if mouse is disabled
        mouseEnabled = np.array(self.img_view_box.state['mouseEnabled'], dtype=float)
        mask = mouseEnabled.copy()
        if axis is not None:
            mask[1 - axis] = 0.0

        if ev.button() == QtCore.Qt.RightButton or \
                (ev.button() == QtCore.Qt.LeftButton and \
                 ev.modifiers() & QtCore.Qt.ControlModifier):
            # determine the amount of translation
            tr = dif * mask
            tr = self.img_view_box.mapToView(tr) - self.img_view_box.mapToView(pg.Point(0, 0))
            x = tr.x()
            y = tr.y()

            self.img_view_box.translateBy(x=x, y=y)
            self.img_view_box.sigRangeChangedManually.emit(self.img_view_box.state['mouseEnabled'])
        else:
            if ev.isFinish():  ## This is the final move in the drag; change the view scale now
                # print "finish"
                self.img_view_box.rbScaleBox.hide()
                # ax = QtCore.QRectF(Point(self.pressPos), Point(self.mousePos))
                ax = QtCore.QRectF(pg.Point(ev.buttonDownPos(ev.button())), pg.Point(pos))
                ax = self.img_view_box.childGroup.mapRectFromParent(ax)
                self.img_view_box.showAxRect(ax)
                self.img_view_box.axHistoryPointer += 1
                self.img_view_box.axHistory = self.img_view_box.axHistory[:self.img_view_box.axHistoryPointer] + [ax]
                self._max_range = False
            else:
                ## update shape of scale box
                self.img_view_box.updateScaleBox(ev.buttonDownPos(), ev.pos())

    def myWheelEvent(self, ev):
        self._max_range = False
        if ev.delta() > 0:
            pg.ViewBox.wheelEvent(self.img_view_box, ev)
        else:
            view_range = np.array(self.img_view_box.viewRange())
            if self.img_data is not None:
                if (view_range[0][1] - view_range[0][0]) > self.img_data.shape[1] and \
                        (view_range[1][1] - view_range[1][0]) > self.img_data.shape[0]:
                    self.auto_range()
                else:
                    pg.ViewBox.wheelEvent(self.img_view_box, ev)
            else:
                pg.ViewBox.wheelEvent(self.img_view_box, ev)

    def auto_range(self):
        self.img_view_box.autoRange()
        self._max_range = True

    def img_view_rect(self):
        """
        :rtype: QtCore.QRectF
        """
        return self.img_view_box.viewRect()

    def img_bounding_rect(self):
        """
        :rtype: QtCore.QRectF
        """
        return self.data_img_item.boundingRect()


class CalibrationCakeWidget(ImgWidget):
    def __init__(self, pg_layout, orientation='vertical'):
        super(CalibrationCakeWidget, self).__init__(pg_layout, orientation)
        self.img_view_box.setAspectLocked(False)
        self.create_vertical_line()
        self.mouse_left_clicked.connect(self.set_vertical_line_pos)

    def create_vertical_line(self):
        self.vertical_line = pg.InfiniteLine(angle=90, pen=pg.mkPen(color=(0, 255, 0), width=2))
        self.activate_vertical_line()

    def activate_vertical_line(self):
        if not self.vertical_line in self.img_view_box.addedItems:
            self.img_view_box.addItem(self.vertical_line)
            self.vertical_line.setVisible(True)  # oddly this is needed for the line to be displayed correctly

    def deactivate_vertical_line(self):
        if self.vertical_line in self.img_view_box.addedItems:
            self.img_view_box.removeItem(self.vertical_line)

    def set_vertical_line_pos(self, x, _):
        self.vertical_line.setValue(x)


class MaskImgWidget(ImgWidget):
    def __init__(self, pg_layout, orientation='vertical'):
        super(MaskImgWidget, self).__init__(pg_layout, orientation)
        self.mask_img_item = pg.ImageItem()
        self.img_view_box.addItem(self.mask_img_item)
        self.img_view_box.setAspectLocked(True)
        self.set_mask_color()
        self.mask_preview_fill_color = QtGui.QColor(255, 0, 0, 150)

    def activate_mask(self):
        if not self.mask_img_item in self.img_view_box.addedItems:
            self.img_view_box.addItem(self.mask_img_item)

    def deactivate_mask(self):
        if self.mask_img_item in self.img_view_box.addedItems:
            self.img_view_box.removeItem(self.mask_img_item)

    def plot_mask(self, mask_data):
        self.mask_data = np.int16(mask_data)
        self.mask_img_item.setImage(self.mask_data.T, autoRange=True, autoHistogramRange=True,
                                    autoLevels=True)

    def create_color_map(self, color):
        steps = np.array([0, 1])
        colors = np.array([[0, 0, 0, 0], color], dtype=np.ubyte)
        color_map = pg.ColorMap(steps, colors)
        return color_map.getLookupTable(0.0, 1.0, 256, True)

    def set_mask_color(self, color=None):
        if not color: color = [255, 0, 0, 255]
        self.mask_img_item.setLookupTable(self.create_color_map(color))

    def draw_circle(self, x=0, y=0):
        circle = MyCircle(x, y, 0, self.mask_preview_fill_color)
        self.img_view_box.addItem(circle)
        return circle

    def draw_rectangle(self, x, y):
        rect = MyRectangle(x, y, 0, 0, self.mask_preview_fill_color)
        self.img_view_box.addItem(rect)
        return rect

    def draw_point(self, radius=0):
        point = MyPoint(radius, self.mask_preview_fill_color)
        self.img_view_box.addItem(point)
        return point

    def draw_polygon(self, x, y):
        polygon = MyPolygon(x, y, self.mask_preview_fill_color)
        self.img_view_box.addItem(polygon)
        return polygon

    def draw_arc(self, x, y):
        arc = MyArc(x, y, self.mask_preview_fill_color)
        self.img_view_box.addItem(arc)
        return arc


class IntegrationImgWidget(MaskImgWidget):
    def __init__(self, pg_layout, orientation='vertical'):
        super(IntegrationImgWidget, self).__init__(pg_layout, orientation)
        self.create_circle_plot_items()
        self.create_mouse_click_item()
        self.create_roi_item()
        self.img_view_box.setAspectLocked(True)

    def create_circle_plot_items(self):
        # creates several PlotDataItems as line items, to be filled with the current clicked position
        # this needs to be several because the lines can be interrupted by the edges of the image, otherwise
        # they would always create straight line around the image
        self.circle_plot_items = []
        self.circle_plot_items.append(pg.PlotDataItem(pen=pg.mkPen(color=(0, 255, 0, 255), width=1.1)))
        self.circle_plot_items.append(pg.PlotDataItem(pen=pg.mkPen(color=(0, 255, 0, 255), width=1.1)))
        self.circle_plot_items.append(pg.PlotDataItem(pen=pg.mkPen(color=(0, 255, 0, 255), width=1.1)))
        self.circle_plot_items.append(pg.PlotDataItem(pen=pg.mkPen(color=(0, 255, 0, 255), width=1.1)))
        self.circle_plot_items.append(pg.PlotDataItem(pen=pg.mkPen(color=(0, 255, 0, 255), width=1.1)))
        for plot_item in self.circle_plot_items:
            self.img_view_box.addItem(plot_item)

    def set_circle_line(self, tth, cur_tth):
        """
        sets the circle plot items to a specfic two theta (tth) value
        :param tth: array of twotheta for the image
        :param cur_tth: two theta value for the line
        """
        tth_ind = find_contours(tth, cur_tth)

        # delete old graphs
        for plot_item in self.circle_plot_items:
            plot_item.setData(x=[], y=[])

        for plot_ind, tth in enumerate(tth_ind):
            x_plot = tth[:, 1] + 0.5
            y_plot = tth[:, 0] + 0.5
            self.circle_plot_items[plot_ind].setData(x=x_plot, y=y_plot)

    def activate_circle_scatter(self):
        for plot_item in self.circle_plot_items:
            if not plot_item in self.img_view_box.addedItems:
                self.img_view_box.addItem(plot_item)

    def deactivate_circle_scatter(self):
        for plot_item in self.circle_plot_items:
            if plot_item in self.img_view_box.addedItems:
                self.img_view_box.removeItem(plot_item)

    def create_roi_item(self):
        self.roi = MyROI([20, 20], [500, 500], pen=pg.mkPen(color=(0, 255, 0), size=2))
        self.roi.handlePen = QtGui.QPen(QtGui.QColor(0, 255, 0))
        self.roi.addScaleHandle([1, 1], [0, 0])
        self.roi.addScaleHandle([0, 1], [1, 0])
        self.roi.addScaleHandle([1, 0], [0, 1])
        self.roi.addScaleHandle([0, 0], [1, 1])

        self.roi_shade = RoiShade(self.img_view_box, self.roi)

    def activate_roi(self):
        if not self.roi in self.img_view_box.addedItems:
            self.img_view_box.addItem(self.roi)
            self.roi_shade.activate_rects()
            self.roi.blockSignals(False)

    def update_roi_shade_limits(self, img_shape):
        self.roi_shade.img_shape = img_shape
        self.roi_shade.update_rects()

    def deactivate_roi(self):
        if self.roi in self.img_view_box.addedItems:
            self.img_view_box.removeItem(self.roi)
            self.roi_shade.deactivate_rects()
            self.roi.blockSignals(True)


class IntegrationCakeWidget(CalibrationCakeWidget):
    def __init__(self, pg_layout, orientation='vertical'):
        super(IntegrationCakeWidget, self).__init__(pg_layout, orientation)
        self.img_view_box.setAspectLocked(False)
        self.create_mouse_click_item()
        self.add_cake_axes()
        self.move_image()
        self.add_cake_integral()
        self.modify_cake_integral_plot_mouse_behavior()
        self.arange_layout()
        self.phases = []  # type: list[CakePhasePlot]

    def add_cake_axes(self):
        self.left_axis_cake = pg.AxisItem('left')
        self.bottom_axis_cake = pg.AxisItem('bottom')
        self.bottom_axis_cake.setLabel(u'2θ', u'°')
        self.left_axis_cake.setLabel(u'Azimuth', u'°')

        self.pg_layout.addItem(self.bottom_axis_cake, row=2, col=2)
        self.pg_layout.addItem(self.left_axis_cake, row=1, col=0)

    def move_image(self):
        cake_image = self.pg_layout.getItem(1, 1)
        self.pg_layout.removeItem(cake_image)
        cake_lut = self.pg_layout.getItem(0, 1)
        self.pg_layout.removeItem(cake_lut)
        self.pg_layout.removeItem(self.pg_layout.getItem(1, 2))
        self.pg_layout.addItem(cake_image, 1, 2)
        self.pg_layout.addItem(cake_lut, 0, 2)

    def add_cake_integral(self):
        self.cake_integral_item = pg.PlotDataItem([], [], pen=pg.mkPen(color='#FFF', width=1.5))
        self.cake_integral_plot = self.pg_layout.addPlot(row=1, col=1, rowspan=2, colspan=1,
                                                         labels={'bottom': 'Intensity'})
        self.cake_integral_plot.hideAxis('left')
        self.cake_integral_plot.addItem(self.cake_integral_item)
        self.cake_integral_plot.enableAutoRange(False)
        self.cake_integral_plot.buttonsHidden = True

        self.cake_integral_plot.setYLink(self.img_view_box)

    def arange_layout(self):
        # self.pg_layout.ci.setSpacing(0)
        self.pg_layout.ci.layout.setColumnStretchFactor(0, 1)
        self.pg_layout.ci.layout.setColumnStretchFactor(1, 3)
        self.pg_layout.ci.layout.setColumnStretchFactor(2, 14)

    def modify_cake_integral_plot_mouse_behavior(self):
        self.cake_integral_plot.vb.mouseClickEvent = self.empty_function
        self.cake_integral_plot.vb.mouseDragEvent = self.empty_function
        self.cake_integral_plot.vb.mouseDoubleClickEvent = self.empty_function
        self.cake_integral_plot.vb.wheelEvent = self.empty_function

    def empty_function(self, *_, **__):
        return

    def plot_cake_integral(self, x, y):
        y[np.where(y <= 0)] = np.nan  # remove 0 values to be able to plot
        self.cake_integral_item.setData(y, x)

    def add_cake_phase(self, positions, intensities, color):
        self.phases.append(CakePhasePlot(self.img_view_box, positions, intensities, color))

    def del_cake_phase(self, ind):
        self.phases[ind].remove()
        del self.phases[ind]

    def set_cake_phase_color(self, ind, color):
        self.phases[ind].update_pen(color)

    def hide_cake_phase(self, ind):
        self.phases[ind].hide()

    def hide_all_cake_phases(self):
        for phase in self.phases:
            phase.hide()

    def show_cake_phase(self, ind):
        self.phases[ind].show()

    def show_all_visible_cake_phases(self, phase_show_cbs):
        for ind, phase in enumerate(self.phases):
            if phase_show_cbs[ind].isChecked():
                phase.show()

    def update_phase_line_visibilities(self, x_range):
        for phase in self.phases:
            phase.update_visibilities(x_range)

    def update_phase_line_visibility(self, ind, x_range):
        self.phases[ind].update_visibilities(x_range)

    def update_phase_intensities(self, ind, positions, intensities):
        if len(self.phases):
            self.phases[ind].update_lines(positions, intensities)


class IntegrationBatchWidget(IntegrationCakeWidget):
    """
    Class describe a widget for 2D image (Theta vs ImageNumber) of batch integration window.

    """

    def __init__(self, pg_layout, orientation='vertical'):
        super(IntegrationBatchWidget, self).__init__(pg_layout, orientation)
        self.create_horizontal_line()
        self.mouse_left_clicked.connect(self.set_horizontal_line_pos)
        self.linear_region_item = ModifiedLinearRegionItem([5, 20], pg.LinearRegionItem.Vertical, movable=False)
        self.x_bin_range = [0, None]  # Range of shown bins
        self.pg_layout.removeItem(self.pg_layout.getItem(1, 2)) # remove the right LUT

    def plot_image(self, img_data, auto_level=False, x_bin_range=[0, None]):
        self.x_bin_range = x_bin_range
        super().plot_image(img_data, auto_level)

    def show_linear_region(self):
        self.img_view_box.addItem(self.linear_region_item)

    def set_linear_region(self, x_min, x_max):
        self.linear_region_item.blockSignals(True)
        self.linear_region_item.setRegion((x_min, x_max))
        self.linear_region_item.blockSignals(False)

    def get_linear_region(self):
        return self.linear_region_item.getRegion()

    def hide_linear_region(self):
        self.img_view_box.removeItem(self.linear_region_item)

    def move_image(self):
        pass

    def add_cake_integral(self):
        pass

    def modify_cake_integral_plot_mouse_behavior(self):
        pass

    def create_horizontal_line(self):
        self.horizontal_line = pg.InfiniteLine(angle=0, pen=pg.mkPen(color=(0, 255, 0), width=2))
        self.activate_horizontal_line()

    def activate_horizontal_line(self):
        if not self.horizontal_line in self.img_view_box.addedItems:
            self.img_view_box.addItem(self.horizontal_line)
            self.horizontal_line.setVisible(True)  # oddly this is needed for the line to be displayed correctly

    def deactivate_horizontal_line(self):
        if self.horizontal_line in self.img_view_box.addedItems:
            self.img_view_box.removeItem(self.horizontal_line)

    def set_horizontal_line_pos(self, x, y):
        self.horizontal_line.setValue(y)

    def draw_rectangle(self, x, y):
        rect = MyRectangle(x, y, 0, 0, QtGui.QColor(255, 0, 0, 150))
        rect.setPen(QtGui.QPen(QtGui.QColor(255, 0, 0, 0), 0.1))
        self.img_view_box.addItem(rect)
        return rect

    def save_img(self, filename):
        self.horizontal_line.hide()
        self.vertical_line.hide()
        self.mouse_click_item.hide()
        self.pg_layout.removeItem(self.img_histogram_LUT_horizontal)

        QtWidgets.QApplication.processEvents()
        exporter = ImageExporter(self.pg_layout.scene())
        exporter.parameters()['width'] = 2048
        exporter.export(filename)

        self.horizontal_line.show()
        self.vertical_line.show()
        self.mouse_click_item.show()
        self.pg_layout.addItem(self.img_histogram_LUT_horizontal, row=0, col=1)

    def add_cake_axes(self):
        """
        Describe axis of 2D plot
        """
        self.left_axis_cake = pg.AxisItem('left')
        self.bottom_axis_cake = pg.AxisItem('bottom')
        self.bottom_axis_cake.setLabel(u'2θ', u'°')
        self.left_axis_cake.setLabel(u'Image number', u'')

        self.pg_layout.addItem(self.bottom_axis_cake, 2, 1)
        self.pg_layout.addItem(self.left_axis_cake, 1, 0)


class CakePhasePlot(object):
    def __init__(self, plot_item, positions, intensities, color):
        self.plot_item = plot_item
        self.visible = True
        self.line_items = []  # type: list[pg.InfiniteLine]
        self.line_visible = []
        self.pattern_x_range = []

        self.color = color
        self.line_width = 1

        self.positions = positions
        self.intensities = intensities

        self._create_items()
        self.update_pen()

    def _create_items(self):
        for ind, position in enumerate(self.positions):
            self.line_items.append(pg.InfiniteLine(pos=position, angle=90))
            self.line_visible.append(True)
            self.plot_item.addItem(self.line_items[ind])

    def add_line(self):
        self.line_items.append(pg.InfiniteLine(angle=90))
        self.line_visible.append(True)
        self.plot_item.blockSignals(True)
        self.plot_item.addItem(self.line_items[-1])
        self.plot_item.blockSignals(False)

    def delete_line(self, ind=-1):
        self.plot_item.removeItem(self.line_items[ind])
        del self.line_items[ind]
        del self.line_visible[ind]

    def clear_lines(self):
        for _ in range(len(self.line_items)):
            self.delete_line()

    def update_lines(self, positions, intensities):
        """
        Updates the line positions and intensities (alpha and thickness, using set_color).
        It also determines which lines are actually visibile in the cake (using update_visibilties).
        :param positions: line positions
        :param intensities: line intensities
        """
        self.positions = positions
        self.intensities = intensities
        self.update_visibilities()

        for ind, intensity in enumerate(intensities):
            self.line_items[ind].setValue(positions[ind])

        if len(self.intensities):
            self.update_pen()

    def update_visibilities(self):
        """
        Checks the number of lines visible (length of intensities and positions) in comparison to the number of lines
        from the jcpds (line_items). Then determines only shows the lines actually visible.
        """
        self.line_visible[:len(self.intensities)] = [True] * len(self.intensities)
        self.line_visible[len(self.intensities):] = [False] * (len(self.line_items) - len(self.intensities))

        if self.visible:
            for ind, line_item in enumerate(self.line_items):
                if not self.line_visible[ind] and line_item in self.plot_item.scene().items():
                    self.plot_item.removeItem(line_item)
                if self.line_visible[ind] and line_item not in self.plot_item.scene().items():
                    self.plot_item.addItem(line_item)

    def update_pen(self, color=None):
        """
        Updates the pen of all lines based on the intensity for each line. The higher the intensity the thicker and the
        more opaque is the line.
        :param color: A tuple with (r,g,b), where the values should from 0 to 255. If None, the current object color is
                      used.
        :type color: tuple
        """
        if color is not None:
            self.color = color

        if not len(self.intensities):
            return

        intensities = np.array(self.intensities)
        line_scaling = intensities / np.max(intensities)
        line_alphas = (line_scaling * 0.4 + 0.3) * 255
        line_widths = self.line_width + 3 * line_scaling

        for ind, line_item in enumerate(intensities):
            color = list(self.color) + [line_alphas[ind]]
            pen = pg.mkPen(color=color, width=line_widths[ind], style=QtCore.Qt.SolidLine)
            self.line_items[ind].setPen(pen)

    def hide(self):
        if self.visible:
            self.visible = False
            for ind, line_item in enumerate(self.line_items):
                if self.line_visible[ind]:
                    self.plot_item.removeItem(line_item)

    def show(self):
        if not self.visible:
            self.visible = True
            for ind, line_item in enumerate(self.line_items):
                if self.line_visible[ind]:
                    self.plot_item.addItem(line_item)

    def remove(self):
        for ind, item in enumerate(self.line_items):
            if self.line_visible[ind]:
                self.plot_item.removeItem(item)


mask_pen = QtGui.QPen(QtGui.QColor(255, 255, 255), 0.5)


class MyPolygon(QtWidgets.QGraphicsPolygonItem):
    def __init__(self, x, y, fill_color):
        QtWidgets.QGraphicsPolygonItem.__init__(self)
        self.setPen(mask_pen)
        self.setBrush(QtGui.QBrush(fill_color))

        self.vertices = []
        self.vertices.append(QtCore.QPointF(x, y))

    def set_size(self, x, y):
        temp_points = list(self.vertices)

        temp_points.append(QtCore.QPointF(x, y))
        self.setPolygon(QtGui.QPolygonF(temp_points))

    def add_point(self, x, y):
        self.vertices.append(QtCore.QPointF(x, y))
        self.setPolygon(QtGui.QPolygonF(self.vertices))


class MyArc(QtWidgets.QGraphicsPolygonItem):
    def __init__(self, x, y, fill_color):
        QtWidgets.QGraphicsPolygonItem.__init__(self)
        self.setPen(mask_pen)
        self.setBrush(QtGui.QBrush(fill_color))
        self.arc_center = QtCore.QPointF(0, 0)
        self.arc_radius = 1
        self.phi_range = []
        self.vertices = []
        self.vertices.append(QtCore.QPointF(x, y))

    def set_size(self, x, y):
        temp_points = list(self.vertices)
        temp_points.append(QtCore.QPointF(x, y))
        self.setPolygon(QtGui.QPolygonF(temp_points))

    def preview_arc(self, arc_points):
        self.setPolygon(QtGui.QPolygonF(arc_points))

    def add_point(self, x, y):
        self.vertices.append(QtCore.QPointF(x, y))


class MyCircle(QtWidgets.QGraphicsEllipseItem):
    def __init__(self, x, y, radius, fill_color):
        QtWidgets.QGraphicsEllipseItem.__init__(self, x - radius, y - radius, radius * 2, radius * 2)
        self.radius = radius
        self.setPen(mask_pen)
        self.setBrush(QtGui.QBrush(fill_color))

        self.center_x = x
        self.center_y = y

    def set_size(self, x, y):
        self.radius = np.sqrt((x - self.center_x) ** 2 + (y - self.center_y) ** 2)
        self.setRect(self.center_x - self.radius, self.center_y - self.radius, self.radius * 2, self.radius * 2)

    def set_position(self, x, y):
        self.setRect(x - self.radius, y - self.radius, self.radius * 2, self.radius * 2)


class MyPoint(QtWidgets.QGraphicsEllipseItem):
    def __init__(self, radius, fill_color):
        QtWidgets.QGraphicsEllipseItem.__init__(self, 0, 0, radius * 2, radius * 2)
        self.setPen(mask_pen)
        self.setBrush(QtGui.QBrush(fill_color))
        self.radius = radius
        self.x = 0
        self.y = 0

    def set_position(self, x, y):
        self.x = x
        self.y = y
        self.setRect(x - self.radius, y - self.radius, self.radius * 2, self.radius * 2)

    def set_radius(self, radius):
        self.radius = radius
        self.set_position(self.x, self.y)
        return self.radius

    def inc_size(self, step):
        self.radius = self.radius + step
        self.set_position(self.x, self.y)
        return self.radius


class MyRectangle(QtWidgets.QGraphicsRectItem):
    def __init__(self, x, y, width, height, fill_color):
        QtWidgets.QGraphicsRectItem.__init__(self, x, y + height, width, height)
        self.setPen(mask_pen)
        self.setBrush(QtGui.QBrush(fill_color))

        self.initial_x = x
        self.initial_y = y

    def set_size(self, x, y):
        width = x - self.initial_x
        height = y - self.initial_y
        self.setRect(self.initial_x, self.initial_y + height, width, -height)


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

    def getRoiLimits(self):
        rect = self.parentBounds()
        x1 = np.round(rect.top())
        x2 = np.round(rect.top() + rect.height())
        y1 = np.round(rect.left())
        y2 = np.round(rect.left() + rect.width())
        return x1, x2, y1, y2

    def setRoiLimits(self, pos, size):
        self.setPos(pos)
        self.setSize(size)


class RoiShade(object):
    def __init__(self, view_box, roi, img_shape=(2048, 2048)):
        self.view_box = view_box
        self.img_shape = img_shape
        self.roi = roi
        self.active = False
        self.create_rect()

    def create_rect(self):
        color = QtGui.QColor(0, 0, 0, 100)
        self.left_rect = QtWidgets.QGraphicsRectItem()
        self.left_rect.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 0)))
        self.left_rect.setBrush(QtGui.QBrush(color))
        self.right_rect = QtWidgets.QGraphicsRectItem()
        self.right_rect.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 0)))
        self.right_rect.setBrush(QtGui.QBrush(color))

        self.top_rect = QtWidgets.QGraphicsRectItem()
        self.top_rect.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 0)))
        self.top_rect.setBrush(QtGui.QBrush(color))
        self.bottom_rect = QtWidgets.QGraphicsRectItem()
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
