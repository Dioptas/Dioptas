# -*- coding: utf8 -*-
# Py2DeX - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2014  Clemens Prescher (clemens.prescher@gmail.com)
#     GSECARS, University of Chicago
#
#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.
#
#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <http://www.gnu.org/licenses/>.

__author__ = 'Clemens Prescher'

import pyqtgraph as pg
from Views.ExLegendItem import LegendItem
import numpy as np
from Data.HelperModule import calculate_color
from PyQt4 import QtCore, QtGui

# TODO refactoring of the 3 lists: overlays, overlay_names, overlay_show, should probably a class, making it more readable

class SpectrumView(QtCore.QObject):
    mouse_moved = QtCore.pyqtSignal(float, float)
    mouse_left_clicked = QtCore.pyqtSignal(float, float)
    range_changed = QtCore.pyqtSignal(list)

    def __init__(self, pg_layout):
        super(SpectrumView, self).__init__()
        self.pg_layout = pg_layout
        self.create_graphics()
        self.create_main_plot()
        self.create_pos_line()
        self.modify_mouse_behavior()
        self.phases = []
        self.overlays = []
        self.overlay_names = []
        self.overlay_show = []

    def create_graphics(self):
        self.spectrum_plot = self.pg_layout.addPlot(labels={'left': 'Intensity', 'bottom': '2 Theta'})
        self.spectrum_plot.setLabel('bottom', u'2θ', u'°')
        self.view_box = self.spectrum_plot.vb
        self.legend = LegendItem(horSpacing=20, box=False)
        self.phases_legend = LegendItem(horSpacing=20, box=False)


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

    def plot_data(self, x, y, name=None):
        self.plot_item.setData(x, y)
        if name is not None:
            self.legend.legendItems[0][1].setText(name)
            self.plot_name = name

    def add_overlay(self, spectrum, show=True):
        x, y = spectrum.data
        color = calculate_color(len(self.overlays) + 1)
        self.overlays.append(pg.PlotDataItem(x, y, pen=pg.mkPen(color=color, width=1.5)))
        self.overlay_names.append(spectrum.name)
        self.overlay_show.append(True)
        if show:
            self.spectrum_plot.addItem(self.overlays[-1])
            self.legend.addItem(self.overlays[-1], spectrum.name)

    def del_overlay(self, ind):
        self.spectrum_plot.removeItem(self.overlays[ind])
        self.legend.removeItem(self.overlays[ind])
        self.overlays.remove(self.overlays[ind])
        self.overlay_names.remove(self.overlay_names[ind])
        self.overlay_show.remove(self.overlay_show[ind])

    def hide_overlay(self, ind):
        self.spectrum_plot.removeItem(self.overlays[ind])
        self.legend.removeItem(self.overlays[ind])
        self.overlay_show[ind] = False

    def show_overlay(self, ind):
        self.spectrum_plot.addItem(self.overlays[ind])
        self.legend.addItem(self.overlays[ind], self.overlay_names[ind])
        self.overlay_show[ind] = True

    def update_overlay(self, spectrum, ind):
        x, y = spectrum.data
        self.overlays[ind].setData(x, y)

    def add_phase(self, name, positions, intensities, baseline):
        self.phases.append(PhasePlot(self.spectrum_plot, self.phases_legend, positions, intensities, name, baseline))

    def update_phase(self, ind, positions, intensities, name=None, baseline=0):
        self.phases[ind].create_items(positions, intensities, name, baseline)

    def update_phase_intensities(self, ind, positions, intensities, baseline=0):
        if len(self.phases):
            self.phases[ind].update_intensities(positions, intensities, baseline)

    def del_phase(self, ind):
        self.phases[ind].remove()
        self.phases.remove(self.phases[ind])

    def plot_vertical_lines(self, positions, phase_index=0, name=None):
        if len(self.phases) <= phase_index:
            self.phases.append(PhaseLinesPlot(self.spectrum_plot, positions))
        else:
            self.phases[phase_index].set_data(positions, name)

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


    def myMouseClickEvent(self, ev):
        if ev.button() == QtCore.Qt.RightButton:
            view_range = np.array(self.view_box.viewRange()) * 2
            curve_data = self.plot_item.getData()
            x_range = np.max(curve_data[0]) - np.min(curve_data[0])
            y_range = np.max(curve_data[1]) - np.min(curve_data[1])
            if (view_range[0][1] - view_range[0][0]) > x_range and \
                            (view_range[1][1] - view_range[1][0]) > y_range:
                self.view_box.autoRange()
                self.view_box.enableAutoRange()
            else:
                self.view_box.scaleBy(2)
            self.view_box.sigRangeChangedManually.emit(self.view_box.state['mouseEnabled'])
        if ev.button() == QtCore.Qt.LeftButton:
            pos = self.view_box.mapFromScene(ev.pos())
            pos = self.plot_item.mapFromScene(2 * ev.pos() - pos)
            x = pos.x()
            y = pos.y()
            self.mouse_left_clicked.emit(x, y)


    def myMouseDoubleClickEvent(self, ev):
        if ev.button() == QtCore.Qt.RightButton:
            self.view_box.autoRange()
            self.view_box.enableAutoRange()
            self.view_box.sigRangeChangedManually.emit(self.view_box.state['mouseEnabled'])


    def myMouseDragEvent(self, ev, axis=None):
        #most of this code is copied behavior of left click mouse drag from the original code
        ev.accept()
        pos = ev.pos()
        lastPos = ev.lastPos()
        dif = pos - lastPos
        dif *= -1

        if ev.button() == QtCore.Qt.RightButton:
            #determine the amount of translation
            tr = dif
            tr = self.view_box.mapToView(tr) - self.view_box.mapToView(pg.Point(0, 0))
            x = tr.x()
            y = tr.y()

            self.view_box.translateBy(x=x, y=y)
        else:
            pg.ViewBox.mouseDragEvent(self.view_box, ev)

        self.view_box.sigRangeChangedManually.emit(self.view_box.state['mouseEnabled'])


    def myWheelEvent(self, ev):
        if ev.delta() > 0:
            pg.ViewBox.wheelEvent(self.view_box, ev)
            axis_range = self.spectrum_plot.viewRange()
            QtGui.QApplication.processEvents()
            self.range_changed.emit(axis_range)
        else:
            view_range = np.array(self.view_box.viewRange())
            curve_data = self.plot_item.getData()
            x_range = np.max(curve_data[0]) - np.min(curve_data[0])
            y_range = np.max(curve_data[1]) - np.min(curve_data[1])
            if (view_range[0][1] - view_range[0][0]) > x_range and \
                            (view_range[1][1] - view_range[1][0]) > y_range:
                self.view_box.autoRange()
            else:
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
        self.line_items = []
        self.index = PhasePlot.num_phases
        self.pen = pg.mkPen(color=calculate_color(self.index + 12), width=1.3, style=QtCore.Qt.DashLine)
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
            self.plot_item.addItem(self.line_items[ind])

        if name is not None:
            try:
                self.legend_item.addItem(self.ref_legend_line, name)
                self.name = name
            except IndexError:
                pass

    def update_intensities(self, positions, intensities, baseline=0):
        for ind, intensity in enumerate(intensities):
            self.line_items[ind].setData(y=[baseline, intensity],
                                         x=[positions[ind], positions[ind]])

    def remove(self):
        try:
            self.legend_item.removeItem(self.ref_legend_line)
        except IndexError:
            print 'this phase had now lines in the appropriate region'
        for item in self.line_items:
            self.plot_item.removeItem(item)