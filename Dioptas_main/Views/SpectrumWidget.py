# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2014  Clemens Prescher (clemens.prescher@gmail.com)
# GSECARS, University of Chicago
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.
#
#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <http://www.gnu.org/licenses/>.
from __future__ import absolute_import, print_function


__author__ = 'Clemens Prescher'

import pyqtgraph as pg
from .ExLegendItem import LegendItem
import numpy as np
from Data.HelperModule import calculate_color
from PyQt4 import QtCore, QtGui
from pyqtgraph.exporters.ImageExporter import ImageExporter
from pyqtgraph.exporters.SVGExporter import SVGExporter

# TODO refactoring of the 3 lists: overlays, overlay_names, overlay_show, should probably a class, making it more readable

class SpectrumWidget(QtCore.QObject):
    mouse_moved = QtCore.pyqtSignal(float, float)
    mouse_left_clicked = QtCore.pyqtSignal(float, float)
    range_changed = QtCore.pyqtSignal(list)

    def __init__(self, pg_layout):
        super(SpectrumWidget, self).__init__()
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
        self.spectrum_plot = self.pg_layout.addPlot(labels={'left': 'Intensity', 'bottom': '2 Theta'})
        self.spectrum_plot.setLabel('bottom', u'2θ', u'°')
        self.view_box = self.spectrum_plot.vb
        self.legend = LegendItem(horSpacing=20, box=False, verSpacing=-3)
        self.phases_legend = LegendItem(horSpacing=20, box=False, verSpacing=-3)

    def create_main_plot(self):
        self.plot_item = pg.PlotDataItem(np.linspace(0, 10), np.sin(np.linspace(10, 3)),
                                         pen=pg.mkPen(color=(255, 255, 255), width=2))
        self.spectrum_plot.addItem(self.plot_item)
        self.legend.addItem(self.plot_item, '')
        self.plot_name = ''
        self.legend.setParentItem(self.spectrum_plot.vb)
        self.legend.anchor(itemPos=(1, 0), parentPos=(1, 0), offset=(-10, -10))
        self.phases_legend.setParentItem(self.spectrum_plot.vb)
        self.phases_legend.anchor(itemPos=(0, 0), parentPos=(0, 0), offset=(0, -10))

    def create_pos_line(self):
        self.pos_line = pg.InfiniteLine(pen=pg.mkPen(color=(0, 255, 0), width=1.5))
        self.spectrum_plot.addItem(self.pos_line)

    def set_pos_line(self, x):
        self.pos_line.setPos(x)

    def get_pos_line(self):
        return self.pos_line.value()

    def plot_data(self, x, y, name=None):
        self.plot_item.setData(x, y)
        if name is not None:
            self.legend.legendItems[0][1].setText(name)
            self.plot_name = name
        self.update_graph_limits()
        self.legend.updateSize()

    def update_graph_limits(self):
        x_range = list(self.plot_item.dataBounds(0))
        y_range = list(self.plot_item.dataBounds(1))
        for ind, overlay in enumerate(self.overlays):
            if self.overlay_show[ind]:
                x_range_overlay = overlay.dataBounds(0)
                y_range_overlay = overlay.dataBounds(0)
                if x_range_overlay[0] < x_range[0]:
                    x_range[0] = x_range_overlay[0]
                if x_range_overlay[1] > x_range[1]:
                    x_range[1] = x_range_overlay[1]

                if y_range_overlay[0] < y_range[0]:
                    y_range[0] = y_range_overlay[0]
                if y_range_overlay[1] > y_range[1]:
                    y_range[1] = y_range_overlay[1]

        diff = x_range[1] - x_range[0]
        x_range = [x_range[0] - 0.02 * diff,
                   x_range[1] + 0.02 * diff]
        diff = y_range[1] - y_range[0]
        y_range = [y_range[0] - 0.02 * diff,
                   y_range[1] + 0.02 * diff]

        self.view_box.setLimits(xMin=x_range[0], xMax=x_range[1],
                                minXRange=x_range[0], maxXRange=x_range[1])
        # yMin=y_range[0], yMax=y_range[1],
        # minYRange=y_range[0], maxYRange=y_range[1],)

    def add_overlay(self, spectrum, show=True):
        x, y = spectrum.data
        color = calculate_color(len(self.overlays) + 1)
        self.overlays.append(pg.PlotDataItem(x, y, pen=pg.mkPen(color=color, width=1.5)))
        self.overlay_names.append(spectrum.name)
        self.overlay_show.append(True)
        if show:
            self.spectrum_plot.addItem(self.overlays[-1])
            self.legend.addItem(self.overlays[-1], spectrum.name)
            self.update_graph_limits()

        return color

    def del_overlay(self, ind):
        self.spectrum_plot.removeItem(self.overlays[ind])
        self.legend.removeItem(self.overlays[ind])
        self.overlays.remove(self.overlays[ind])
        self.overlay_names.remove(self.overlay_names[ind])
        self.overlay_show.remove(self.overlay_show[ind])

        self.update_phase_visibility()
        self.update_graph_limits()

    def hide_overlay(self, ind):
        self.spectrum_plot.removeItem(self.overlays[ind])
        self.legend.hideItem(ind + 1)
        self.overlay_show[ind] = False

        self.update_phase_visibility()
        self.update_graph_limits()

    def show_overlay(self, ind):
        self.spectrum_plot.addItem(self.overlays[ind])
        self.legend.showItem(ind + 1)
        self.overlay_show[ind] = True

        self.update_phase_visibility()
        self.update_graph_limits()

    def update_overlay(self, spectrum, ind):
        x, y = spectrum.data
        self.overlays[ind].setData(x, y)
        if self._auto_range:
            self.view_box.autoRange()
            self.view_box.enableAutoRange()

    def get_overlay_color(self, ind):
        pass

    def set_overlay_color(self, ind, color):
        self.overlays[ind].setPen(pg.mkPen(color=color, width=1.5))
        self.legend.setItemColor(ind + 1, color)

    def rename_overlay(self, ind, name):
        self.legend.renameItem(ind + 1, name)


    def add_phase(self, name, positions, intensities, baseline):
        self.phases.append(PhasePlot(self.spectrum_plot, self.phases_legend, positions, intensities, name, baseline))
        return self.phases[-1].color

    # def update_phase(self, ind, positions, intensities, name=None, baseline=0):
    #     self.phases[ind].create_items(positions, intensities, name, baseline)

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

    def update_phase_line_visibilities(self):
        x_range = self.plot_item.dataBounds(0)
        for phase in self.phases:
            phase.update_visibilities(x_range)

    def del_phase(self, ind):
        self.phases[ind].remove()
        del self.phases[ind]

    def update_phase_visibility(self):
        for phase in self.phases:
            if phase.visible:
                phase.show()
            else:
                phase.hide()

    def plot_vertical_lines(self, positions, name=None):
        if len(self.phases_vlines) > 0:
            self.phases_vlines[0].set_data(positions, name)
        else:
            self.phases_vlines.append(PhaseLinesPlot(self.spectrum_plot, positions))

    def save_png(self, filename):
        exporter = ImageExporter(self.spectrum_plot)
        exporter.export(filename)

    def save_svg(self, filename):
        self.invert_color()
        exporter = SVGExporter(self.spectrum_plot)
        exporter.export(filename)
        self.norm_color()

    def _invert_color(self):
        self.spectrum_plot.getAxis('bottom').setPen('k')
        self.spectrum_plot.getAxis('left').setPen('k')
        self.plot_item.setPen('k')
        self.legend.legendItems[0][1].setAttr('color', '000')
        self.legend.legendItems[0][1].setText(self.legend.legendItems[0][1].text)

    def _norm_color(self):
        self.spectrum_plot.getAxis('bottom').setPen('w')
        self.spectrum_plot.getAxis('left').setPen('w')
        self.plot_item.setPen('w')
        self.legend.legendItems[0][1].setAttr('color', 'FFF')
        self.legend.legendItems[0][1].setText(self.legend.legendItems[0][1].text)

    def mouseMoved(self, pos):
        pos = self.plot_item.mapFromScene(pos)
        self.mouse_moved.emit(pos.x(), pos.y())

    def modify_mouse_behavior(self):
        #different mouse handlers
        self.view_box.setMouseMode(self.view_box.RectMode)

        self.pg_layout.scene().sigMouseMoved.connect(self.mouseMoved)
        self.view_box.mouseClickEvent = self.myMouseClickEvent
        self.view_box.mouseDragEvent = self.myMouseDragEvent
        self.view_box.mouseDoubleClickEvent = self.myMouseDoubleClickEvent
        self.view_box.wheelEvent = self.myWheelEvent

        #create sigranged changed timer for right click drag
        #if not using the timer the signals are fired too often and
        #the computer becomes slow...
        self.range_changed_timer = QtCore.QTimer()
        self.range_changed_timer.timeout.connect(self.emit_sig_range_changed)
        self.range_changed_timer.setInterval(30)
        self.last_view_range= np.array(self.view_box.viewRange())

    def myMouseClickEvent(self, ev):
        if ev.button() == QtCore.Qt.RightButton or \
                (ev.button() == QtCore.Qt.LeftButton and \
                             ev.modifiers() & QtCore.Qt.ControlModifier):
            view_range = np.array(self.view_box.viewRange()) * 2
            curve_data = self.plot_item.getData()
            x_range = np.max(curve_data[0]) - np.min(curve_data[0])
            if (view_range[0][1] - view_range[0][0]) > x_range:
                self._auto_range = True
                self.view_box.autoRange()
                self.view_box.enableAutoRange()
            else:
                self._auto_range = False
                self.view_box.scaleBy(2)
            self.view_box.sigRangeChangedManually.emit(self.view_box.state['mouseEnabled'])
        elif ev.button() == QtCore.Qt.LeftButton:
            pos = self.view_box.mapFromScene(ev.pos())
            pos = self.plot_item.mapFromScene(2 * ev.pos() - pos)
            x = pos.x()
            y = pos.y()
            self.mouse_left_clicked.emit(x, y)

    def myMouseDoubleClickEvent(self, ev):
        if (ev.button() == QtCore.Qt.RightButton) or (ev.button() == QtCore.Qt.LeftButton and
                                                      ev.modifiers() & QtCore.Qt.ControlModifier):
            self.view_box.autoRange()
            self.view_box.enableAutoRange()
            self._auto_range = True
            self.view_box.sigRangeChangedManually.emit(self.view_box.state['mouseEnabled'])

    def myMouseDragEvent(self, ev, axis=None):
        #most of this code is copied behavior mouse drag from the original code
        ev.accept()
        pos = ev.pos()
        lastPos = ev.lastPos()
        dif = pos - lastPos
        dif *= -1

        if ev.button() == QtCore.Qt.RightButton or \
                (ev.button() == QtCore.Qt.LeftButton and
                         ev.modifiers() & QtCore.Qt.ControlModifier):
            #determine the amount of translation
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
            if ev.isFinish():  ## This is the final move in the drag; change the view scale now
                #print "finish"
                self.view_box.rbScaleBox.hide()
                #ax = QtCore.QRectF(Point(self.pressPos), Point(self.mousePos))
                ax = QtCore.QRectF(pg.Point(ev.buttonDownPos(ev.button())), pg.Point(pos))
                ax = self.view_box.childGroup.mapRectFromParent(ax)
                self.view_box.showAxRect(ax)
                self.view_box.axHistoryPointer += 1
                self.view_box.axHistory = self.view_box.axHistory[:self.view_box.axHistoryPointer] + [ax]
                self.view_box.sigRangeChangedManually.emit(self.view_box.state['mouseEnabled'])
            else:
                ## update shape of scale box
                self.view_box.updateScaleBox(ev.buttonDownPos(), ev.pos())

    def emit_sig_range_changed(self):
        new_view_range = np.array(self.view_box.viewRange())
        if not np.array_equal(self.last_view_range, new_view_range):
            self.view_box.sigRangeChangedManually.emit(self.view_box.state['mouseEnabled'])
            self.last_view_range = new_view_range

    def myWheelEvent(self, ev, axis=None, *args):
        if ev.delta() > 0:
            pg.ViewBox.wheelEvent(self.view_box, ev, axis)

            self._auto_range = False
            # axis_range = self.spectrum_plot.viewRange()
            # self.range_changed.emit(axis_range)
        else:
            view_range = np.array(self.view_box.viewRange())
            curve_data = self.plot_item.getData()
            x_range = np.max(curve_data[0]) - np.min(curve_data[0])
            y_range = np.max(curve_data[1]) - np.min(curve_data[1])
            if (view_range[0][1] - view_range[0][0]) > x_range and \
                            (view_range[1][1] - view_range[1][0]) > y_range:
                self.view_box.autoRange()
                self.view_box.enableAutoRange()
                self._auto_range = True
            else:
                self._auto_range = False
                pg.ViewBox.wheelEvent(self.view_box, ev)
        self.view_box.sigRangeChangedManually.emit(self.view_box.state['mouseEnabled'])


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
        #remove all old lines
        for item in self.line_items:
            self.plot_item.removeItem(item)

        #create new ones on each Position:
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
        self.index = PhasePlot.num_phases
        self.color = calculate_color(self.index + 9)
        self.pen = pg.mkPen(color=self.color, width=1.3, style=QtCore.Qt.DashLine)
        self.ref_legend_line = pg.PlotDataItem(pen=self.pen)
        self.name = ''
        PhasePlot.num_phases += 1
        self.create_items(positions, intensities, name, baseline)

    def create_items(self, positions, intensities, name=None, baseline=0):
        #create new ones on each Position:
        self.line_items = []

        for ind, position in enumerate(positions):
            self.line_items.append(pg.PlotDataItem(x=[position, position],
                                                   y=[baseline, intensities[ind]],
                                                   pen=self.pen))
            self.line_visible.append(True)
            self.plot_item.addItem(self.line_items[ind])

        if name is not None:
            try:
                self.legend_item.addItem(self.ref_legend_line, name)
                self.name = name
            except IndexError:
                pass

    def update_intensities(self, positions, intensities, baseline=0):
        if self.visible:
            for ind, intensity in enumerate(intensities):
                self.line_items[ind].setData(y=[baseline, intensity],
                                             x=[positions[ind], positions[ind]])

    def update_visibilities(self, spectrum_range):
        if self.visible:
            for ind, line_item in enumerate(self.line_items):
                data = line_item.getData()
                position = data[0][0]
                if position >= spectrum_range[0] and position <= spectrum_range[1]:
                    if not self.line_visible[ind]:
                        self.plot_item.addItem(line_item)
                        self.line_visible[ind] = True
                else:
                    if self.line_visible[ind]:
                        self.plot_item.removeItem(line_item)
                        self.line_visible[ind] = False

    def set_color(self, color):
        for line_item in self.line_items:
            line_item.setPen(pg.mkPen(color=color, width=1.3, style=QtCore.Qt.DashLine))
        self.ref_legend_line.setPen(pg.mkPen(color=color, width=1.3, style=QtCore.Qt.DashLine))


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
        for item in self.line_items:
            self.plot_item.removeItem(item)