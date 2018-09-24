# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2017  Clemens Prescher (clemens.prescher@gmail.com)
# Institute for Geology and Mineralogy, University of Cologne
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

from __future__ import absolute_import, print_function

import pyqtgraph as pg
import numpy as np
from qtpy import QtCore
from pyqtgraph.exporters.ImageExporter import ImageExporter
from pyqtgraph.exporters.SVGExporter import SVGExporter

from .ExLegendItem import LegendItem
from ...model.util.HelperModule import calculate_color


class PatternWidget(QtCore.QObject):
    mouse_moved = QtCore.Signal(float, float)
    mouse_left_clicked = QtCore.Signal(float, float)
    range_changed = QtCore.Signal(list)
    auto_range_status_changed = QtCore.Signal(bool)

    def __init__(self, pg_layout):
        super(PatternWidget, self).__init__()
        self.pg_layout = pg_layout
        self.create_graphics()
        self.create_main_plot()
        self.create_pos_line()
        self.modify_mouse_behavior()
        self._auto_range = True
        self.phases = []
        self.phases_vlines = []
        self.overlays = []
        self.overlay_names = []
        self.overlay_show = []

    def create_graphics(self):
        self.pattern_plot = self.pg_layout.addPlot(labels={'left': 'Intensity', 'bottom': '2 Theta'})
        self.pattern_plot.setLabel('bottom', u'2θ', u'°')
        self.pattern_plot.enableAutoRange(False)
        self.pattern_plot.buttonsHidden = True
        self.view_box = self.pattern_plot.vb
        self.legend = LegendItem(horSpacing=20, box=False, verSpacing=-3, labelAlignment='right', showLines=False)
        self.phases_legend = LegendItem(horSpacing=20, box=False, verSpacing=-3, labelAlignment='left', showLines=False)

    def create_main_plot(self):
        self.plot_item = pg.PlotDataItem(np.linspace(0, 10), np.sin(np.linspace(10, 3)),
                                         pen=pg.mkPen(color=(255, 255, 255), width=2))
        self.pattern_plot.addItem(self.plot_item)
        self.bkg_item = pg.PlotDataItem([], [],
                                        pen=pg.mkPen(color=(255, 0, 0), width=2, style=QtCore.Qt.DashLine))
        self.pattern_plot.addItem(self.bkg_item)
        self.legend.addItem(self.plot_item, '')
        self.plot_name = ''
        self.legend.setParentItem(self.pattern_plot.vb)
        self.legend.anchor(itemPos=(1, 0), parentPos=(1, 0), offset=(-10, -10))
        self.phases_legend.setParentItem(self.pattern_plot.vb)
        self.phases_legend.anchor(itemPos=(0, 0), parentPos=(0, 0), offset=(0, -10))

        self.linear_region_item = ModifiedLinearRegionItem([5, 20], pg.LinearRegionItem.Vertical, movable=False)
        # self.linear_region_item.mouseDragEvent = empty_function

    @property
    def auto_range(self):
        return self._auto_range

    @auto_range.setter
    def auto_range(self, value):
        if self._auto_range is not value:
            self._auto_range = value
            self.auto_range_status_changed.emit(value)
        if self._auto_range is True:
            self.update_graph_range()

    def create_pos_line(self):
        self.pos_line = pg.InfiniteLine(pen=pg.mkPen(color=(0, 255, 0), width=1.5, style=QtCore.Qt.DashLine))
        self.pattern_plot.addItem(self.pos_line)

    def deactivate_pos_line(self):
        self.pattern_plot.removeItem(self.pos_line)

    def set_pos_line(self, x):
        self.pos_line.setPos(x)

    def get_pos_line(self):
        return self.pos_line.value()

    def plot_data(self, x, y, name=None):
        self.plot_item.setData(x, y)
        if name is not None:
            self.legend.legendItems[0][1].setText(name)
            self.plot_name = name
        self.legend.updateSize()
        self.update_graph_range()

    def plot_bkg(self, x, y):
        self.bkg_item.setData(x, y)

    def update_graph_range(self):
        x_range = list(self.plot_item.dataBounds(0))
        y_range = list(self.plot_item.dataBounds(1))

        for ind, overlay in enumerate(self.overlays):
            if self.overlay_show[ind]:
                x_range_overlay = overlay.dataBounds(0)
                y_range_overlay = overlay.dataBounds(1)
                if x_range_overlay[0] < x_range[0]:
                    x_range[0] = x_range_overlay[0]
                if x_range_overlay[1] > x_range[1]:
                    x_range[1] = x_range_overlay[1]
                if y_range_overlay[0] < y_range[0]:
                    y_range[0] = y_range_overlay[0]
                if y_range_overlay[1] > y_range[1]:
                    y_range[1] = y_range_overlay[1]

        if x_range[1] is not None and x_range[0] is not None:
            padding = self.view_box.suggestPadding(0)
            diff = x_range[1] - x_range[0]
            x_range = [x_range[0] - padding * diff,
                       x_range[1] + padding * diff]

            self.view_box.setLimits(xMin=x_range[0], xMax=x_range[1])

            if self.auto_range:
                self.view_box.setRange(xRange=x_range, padding=0)

        if y_range[1] is not None and y_range[0] is not None:
            padding = self.view_box.suggestPadding(1)
            diff = y_range[1] - y_range[0]
            y_range = [y_range[0] - padding * diff,
                       y_range[1] + padding * diff]

            self.view_box.setLimits(yMin=y_range[0], yMax=y_range[1])

            if self.auto_range:
                self.view_box.setRange(yRange=y_range, padding=0)
        self.emit_sig_range_changed()

    def add_overlay(self, pattern, show=True):
        x, y = pattern.data
        color = calculate_color(len(self.overlays) + 1)
        self.overlays.append(pg.PlotDataItem(x, y, pen=pg.mkPen(color=color, width=1.5)))
        self.overlay_names.append(pattern.name)
        self.overlay_show.append(True)
        if show:
            self.pattern_plot.addItem(self.overlays[-1])
            self.legend.addItem(self.overlays[-1], pattern.name)
            self.update_graph_range()
        return color

    def remove_overlay(self, ind):
        self.pattern_plot.removeItem(self.overlays[ind])
        self.legend.removeItem(self.overlays[ind])
        self.overlays.remove(self.overlays[ind])
        self.overlay_names.remove(self.overlay_names[ind])
        self.overlay_show.remove(self.overlay_show[ind])
        self.update_graph_range()

    def hide_overlay(self, ind):
        self.pattern_plot.removeItem(self.overlays[ind])
        self.legend.hideItem(ind + 1)
        self.overlay_show[ind] = False
        self.update_graph_range()

    def show_overlay(self, ind):
        self.pattern_plot.addItem(self.overlays[ind])
        self.legend.showItem(ind + 1)
        self.overlay_show[ind] = True
        self.update_graph_range()

    def update_overlay(self, pattern, ind):
        x, y = pattern.data
        self.overlays[ind].setData(x, y)
        self.update_graph_range()

    def set_overlay_color(self, ind, color):
        self.overlays[ind].setPen(pg.mkPen(color=color, width=1.5))
        self.legend.setItemColor(ind + 1, color)

    def rename_overlay(self, ind, name):
        self.legend.renameItem(ind + 1, name)

    def move_overlay_up(self, ind):
        new_ind = ind - 1
        self.overlays.insert(new_ind, self.overlays.pop(ind))
        self.overlay_names.insert(new_ind, self.overlay_names.pop(ind))
        self.overlay_show.insert(new_ind, self.overlay_show.pop(ind))

        color = self.legend.legendItems[ind + 1][1].opts['color']
        label = self.legend.legendItems[ind + 1][1].text
        self.legend.legendItems[ind + 1][1].setAttr('color', self.legend.legendItems[new_ind + 1][1].opts['color'])
        self.legend.legendItems[ind + 1][1].setText(self.legend.legendItems[new_ind + 1][1].text)
        self.legend.legendItems[new_ind + 1][1].setAttr('color', color)
        self.legend.legendItems[new_ind + 1][1].setText(label)

    def move_overlay_down(self, cur_ind):
        self.overlays.insert(cur_ind + 1, self.overlays.pop(cur_ind))
        self.overlay_names.insert(cur_ind + 1, self.overlay_names.pop(cur_ind))
        self.overlay_show.insert(cur_ind + 1, self.overlay_show.pop(cur_ind))

        color = self.legend.legendItems[cur_ind + 1][1].opts['color']
        label = self.legend.legendItems[cur_ind + 1][1].text
        self.legend.legendItems[cur_ind + 1][1].setAttr('color', self.legend.legendItems[cur_ind + 2][1].opts['color'])
        self.legend.legendItems[cur_ind + 1][1].setText(self.legend.legendItems[cur_ind + 2][1].text)
        self.legend.legendItems[cur_ind + 2][1].setAttr('color', color)
        self.legend.legendItems[cur_ind + 2][1].setText(label)

    def set_antialias(self, value):
        for overlay in self.overlays:
            overlay.opts['antialias'] = value
            overlay.updateItems()

    def add_phase(self, name, positions, intensities, baseline):
        self.phases.append(PhasePlot(self.pattern_plot, self.phases_legend, positions, intensities, name, baseline))
        return self.phases[-1].color

    def set_phase_color(self, ind, color):
        self.phases[ind].set_color(color)
        self.phases_legend.setItemColor(ind, color)

    def hide_phase(self, ind):
        self.phases[ind].hide()
        self.phases_legend.hideItem(ind)

    def show_phase(self, ind):
        self.phases[ind].show()
        self.phases_legend.showItem(ind)

    def rename_phase(self, ind, name):
        self.phases_legend.renameItem(ind, name)

    def update_phase_intensities(self, ind, positions, intensities, baseline=0):
        if len(self.phases):
            self.phases[ind].update_intensities(positions, intensities, baseline)

    def update_phase_line_visibility(self, ind):
        x_range = self.plot_item.dataBounds(0)
        self.phases[ind].update_visibilities(x_range)

    def update_phase_line_visibilities(self):
        x_range = self.plot_item.dataBounds(0)
        for phase in self.phases:
            phase.update_visibilities(x_range)

    def del_phase(self, ind):
        self.phases[ind].remove()
        del self.phases[ind]

    def plot_vertical_lines(self, positions, name=None):
        if len(self.phases_vlines) > 0:
            self.phases_vlines[0].set_data(positions, name)
        else:
            self.phases_vlines.append(PhaseLinesPlot(self.pattern_plot, positions,
                                                     pen=pg.mkPen(color=(200, 50, 50), style=QtCore.Qt.SolidLine)))

    def show_linear_region(self):
        self.pattern_plot.addItem(self.linear_region_item)

    def set_linear_region(self, x_min, x_max):
        self.linear_region_item.setRegion((x_min, x_max))

    def get_linear_region(self):
        return self.linear_region_item.getRegion()

    def hide_linear_region(self):
        self.pattern_plot.removeItem(self.linear_region_item)

    def save_png(self, filename):
        exporter = ImageExporter(self.pattern_plot)
        exporter.export(filename)

    def save_svg(self, filename):
        self._invert_color()
        previous_label = None
        if self.pattern_plot.getAxis('bottom').labelText == u'2θ':
            previous_label = (u'2θ', '°')
            self.pattern_plot.setLabel('bottom', '2th_deg', '')
        exporter = SVGExporter(self.pattern_plot)
        exporter.export(filename)
        self._norm_color()
        if previous_label is not None:
            self.pattern_plot.setLabel('bottom', previous_label[0], previous_label[1])

    def _invert_color(self):
        self.pattern_plot.getAxis('bottom').setPen('k')
        self.pattern_plot.getAxis('left').setPen('k')
        self.plot_item.setPen('k')
        self.legend.legendItems[0][1].setAttr('color', '000')
        self.legend.legendItems[0][1].setText(self.legend.legendItems[0][1].text)

    def _norm_color(self):
        self.pattern_plot.getAxis('bottom').setPen('w')
        self.pattern_plot.getAxis('left').setPen('w')
        self.plot_item.setPen('w')
        self.legend.legendItems[0][1].setAttr('color', 'FFF')
        self.legend.legendItems[0][1].setText(self.legend.legendItems[0][1].text)

    def mouseMoved(self, pos):
        pos = self.plot_item.mapFromScene(pos)
        self.mouse_moved.emit(pos.x(), pos.y())

    def modify_mouse_behavior(self):
        # different mouse handlers
        self.view_box.setMouseMode(self.view_box.RectMode)

        self.pg_layout.scene().sigMouseMoved.connect(self.mouseMoved)
        self.view_box.mouseClickEvent = self.myMouseClickEvent
        self.view_box.mouseDragEvent = self.myMouseDragEvent
        self.view_box.mouseDoubleClickEvent = self.myMouseDoubleClickEvent
        self.view_box.wheelEvent = self.myWheelEvent

        # create sigranged changed timer for right click drag
        # if not using the timer the signals are fired too often and
        # the computer becomes slow...
        self.range_changed_timer = QtCore.QTimer()
        self.range_changed_timer.timeout.connect(self.emit_sig_range_changed)
        self.range_changed_timer.setInterval(30)
        self.last_view_range = np.array(self.view_box.viewRange())

    def myMouseClickEvent(self, ev):
        if ev.button() == QtCore.Qt.RightButton or \
                (ev.button() == QtCore.Qt.LeftButton and
                         ev.modifiers() & QtCore.Qt.ControlModifier):
            view_range = np.array(self.view_box.viewRange()) * 2
            curve_data = self.plot_item.getData()
            x_range = np.max(curve_data[0]) - np.min(curve_data[0])
            if (view_range[0][1] - view_range[0][0]) > x_range:
                self.auto_range = True
            else:
                self.auto_range = False
                self.view_box.scaleBy(2)
            self.emit_sig_range_changed()
        elif ev.button() == QtCore.Qt.LeftButton:
            pos = self.view_box.mapFromScene(ev.pos())
            pos = self.plot_item.mapFromScene(2 * ev.pos() - pos)
            x = pos.x()
            y = pos.y()
            self.mouse_left_clicked.emit(x, y)

    def myMouseDoubleClickEvent(self, ev):
        if (ev.button() == QtCore.Qt.RightButton) or (ev.button() == QtCore.Qt.LeftButton and
                                                              ev.modifiers() & QtCore.Qt.ControlModifier):
            self.auto_range = True
            self.emit_sig_range_changed()

    def myMouseDragEvent(self, ev, axis=None):
        # most of this code is copied behavior mouse drag from the original code
        ev.accept()
        pos = ev.pos()
        lastPos = ev.lastPos()
        dif = pos - lastPos
        dif *= -1

        if ev.button() == QtCore.Qt.RightButton or \
                (ev.button() == QtCore.Qt.LeftButton and
                         ev.modifiers() & QtCore.Qt.ControlModifier):
            # determine the amount of translation
            tr = dif
            tr = self.view_box.mapToView(tr) - self.view_box.mapToView(pg.Point(0, 0))
            x = tr.x()
            y = tr.y()
            self.view_box.translateBy(x=x, y=y)
            if ev.start:
                self.range_changed_timer.start()
            if ev.isFinish():
                self.range_changed_timer.stop()
                self.emit_sig_range_changed()
        else:
            if ev.isFinish():  # This is the final move in the drag; change the view scale now
                self.auto_range = False
                self.view_box.rbScaleBox.hide()
                ax = QtCore.QRectF(pg.Point(ev.buttonDownPos(ev.button())), pg.Point(pos))
                ax = self.view_box.childGroup.mapRectFromParent(ax)
                self.view_box.showAxRect(ax)
                self.view_box.axHistoryPointer += 1
                self.view_box.axHistory = self.view_box.axHistory[:self.view_box.axHistoryPointer] + [ax]
                self.emit_sig_range_changed()
            else:
                # update shape of scale box
                self.view_box.updateScaleBox(ev.buttonDownPos(), ev.pos())

    def emit_sig_range_changed(self):
        new_view_range = np.array(self.view_box.viewRange())
        if not np.array_equal(self.last_view_range, new_view_range):
            self.view_box.sigRangeChangedManually.emit(self.view_box.state['mouseEnabled'])
            self.last_view_range = new_view_range

    def myWheelEvent(self, ev, axis=None, *args):
        if ev.delta() > 0:
            pg.ViewBox.wheelEvent(self.view_box, ev, axis)

            self.auto_range = False
            # axis_range = self.pattern_plot.viewRange()
            # self.range_changed.emit(axis_range)
            self.emit_sig_range_changed()
        else:
            if self.auto_range is not True:
                view_range = np.array(self.view_box.viewRange())
                curve_data = self.plot_item.getData()
                x_range = np.max(curve_data[0]) - np.min(curve_data[0])
                y_range = np.max(curve_data[1]) - np.min(curve_data[1])
                if (view_range[0][1] - view_range[0][0]) >= x_range and \
                                (view_range[1][1] - view_range[1][0]) >= y_range:
                    self.auto_range = True
                else:
                    self.auto_range = False
                    pg.ViewBox.wheelEvent(self.view_box, ev)
            self.emit_sig_range_changed()


class PhaseLinesPlot(object):
    def __init__(self, plot_item, positions=None, name='Dummy',
                 pen=pg.mkPen(color=(120, 120, 120), style=QtCore.Qt.DashLine)):
        self.plot_item = plot_item
        self.peak_positions = []
        self.line_items = []
        self.pen = pen
        self.name = name

        if positions is not None:
            self.set_data(positions, name)

    def set_data(self, positions, name):
        # remove all old lines
        for item in self.line_items:
            self.plot_item.removeItem(item)

        # create new ones on each Position:
        self.line_items = []
        self.peak_positions = positions
        for ind, position in enumerate(positions):
            self.line_items.append(pg.InfiniteLine(pen=self.pen))
            self.line_items[ind].setValue(position)
            self.plot_item.addItem(self.line_items[ind])


class PhasePlot(object):
    num_phases = 0

    def __init__(self, plot_item, legend_item, positions, intensities, name=None, baseline=0):
        self.plot_item = plot_item
        self.legend_item = legend_item
        self.visible = True
        self.line_items = []
        self.line_visible = []
        self.pattern_x_range = []
        self.index = PhasePlot.num_phases
        self.color = calculate_color(self.index + 9)
        self.pen = pg.mkPen(color=self.color, width=0.9, style=QtCore.Qt.SolidLine)
        self.ref_legend_line = pg.PlotDataItem(pen=self.pen)
        self.name = ''
        PhasePlot.num_phases += 1
        self.create_items(positions, intensities, name, baseline)

    def create_items(self, positions, intensities, name=None, baseline=0):
        # create new ones on each Position:
        self.line_items = []

        for ind, position in enumerate(positions):
            self.line_items.append(pg.PlotDataItem(x=[position, position],
                                                   y=[baseline, intensities[ind]],
                                                   pen=self.pen,
                                                   antialias=False))
            self.line_visible.append(True)
            self.plot_item.addItem(self.line_items[ind])

        if name is not None:
            try:
                self.legend_item.addItem(self.ref_legend_line, name)
                self.name = name
            except IndexError:
                pass

    def add_line(self):
        self.line_items.append(pg.PlotDataItem(x=[0, 0],
                                               y=[0, 0],
                                               pen=self.pen, antialias=False))
        self.line_visible.append(True)
        self.plot_item.blockSignals(True)
        self.plot_item.addItem(self.line_items[-1])
        self.plot_item.blockSignals(False)

    def remove_line(self, ind=-1):
        self.plot_item.removeItem(self.line_items[ind])
        del self.line_items[ind]
        del self.line_visible[ind]

    def clear_lines(self):
        for dummy_ind in range(len(self.line_items)):
            self.remove_line()

    def update_intensities(self, positions, intensities, baseline=0):
        if self.visible:
            for ind, intensity in enumerate(intensities):
                self.line_items[ind].setData(y=[baseline, intensity],
                                             x=[positions[ind], positions[ind]])

    def update_visibilities(self, pattern_range):
        if self.visible:
            for ind, line_item in enumerate(self.line_items):
                data = line_item.getData()
                position = data[0][0]
                if position >= pattern_range[0] and position <= pattern_range[1]:
                    if not self.line_visible[ind]:
                        self.plot_item.addItem(line_item)
                        self.line_visible[ind] = True
                else:
                    if self.line_visible[ind]:
                        self.plot_item.removeItem(line_item)
                        self.line_visible[ind] = False

    def set_color(self, color):
        self.pen = pg.mkPen(color=color, width=1.3, style=QtCore.Qt.SolidLine)
        for line_item in self.line_items:
            line_item.setPen(self.pen)
        self.ref_legend_line.setPen(self.pen)

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
        try:
            self.legend_item.removeItem(self.ref_legend_line)
        except IndexError:
            print('this phase had now lines in the appropriate region')
        for ind, item in enumerate(self.line_items):
            if self.line_visible[ind]:
                self.plot_item.removeItem(item)


class ModifiedLinearRegionItem(pg.LinearRegionItem):
    def __init__(self, *args, **kwargs):
        super(ModifiedLinearRegionItem, self).__init__()

    def mouseDragEvent(self, ev):
        return

    def hoverEvent(self, ev):
        return
