# -*- coding: utf-8 -*-
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

"""
Is the basic controller for the XrsMaskView and XrsMaskData.
Connects all the Gui elements with XrsMaskData...
"""
#TODO add the possibility to define an arc and mask around it
#TODO Dialog showing all the hidden possibilities, like mouse behavior and also shortcuts


__author__ = 'Clemens Prescher'

import sys
import os

import pyqtgraph as pg

from PyQt4 import QtGui, QtCore
from Views.MaskView import MaskView
from Data.ImgData import ImgData
from Data.MaskData import MaskData

import numpy as np


class MaskController(object):
    def __init__(self, working_dir, view=None, imgData=None, maskData=None):
        self.working_dir = working_dir
        if view == None:
            self.view = MaskView()
        else:
            self.view = view

        if imgData == None:
            self.img_data = ImgData()
        else:
            self.img_data = imgData

        if maskData == None:
            self.mask_data = MaskData()
        else:
            self.mask_data = maskData

        self.view.img_view.mouse_left_clicked.connect(self.process_click)

        self.state = None
        self.clicks = 0
        self.create_signals()

        self.rect = None
        self.circle = None
        self.polygon = None
        self.point = None

        self.img_data.subscribe(self.update_mask_dimension)

        self.raise_window()

    def raise_window(self):
        self.view.show()
        self.view.setWindowState(self.view.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
        self.view.activateWindow()
        self.view.raise_()

    def connect_click_function(self, emitter, function):
        self.view.connect(emitter, QtCore.SIGNAL('clicked()'), function)

    def create_signals(self):
        self.connect_click_function(self.view.circle_btn, self.activate_circle_btn)
        self.connect_click_function(self.view.rectangle_btn, self.activate_rectangle_btn)
        self.connect_click_function(self.view.polygon_btn, self.activate_polygon_btn)
        self.connect_click_function(self.view.point_btn, self.activate_point_btn)
        self.connect_click_function(self.view.undo_btn, self.undo_btn_click)
        self.connect_click_function(self.view.redo_btn, self.redo_btn_click)
        self.connect_click_function(self.view.below_thresh_btn, self.below_thresh_btn_click)
        self.connect_click_function(self.view.above_thresh_btn, self.above_thresh_btn_click)
        self.connect_click_function(self.view.cosmic_btn, self.cosmic_btn_click)
        self.connect_click_function(self.view.invert_mask_btn, self.invert_mask_btn_click)
        self.connect_click_function(self.view.clear_mask_btn, self.clear_mask_btn_click)
        self.connect_click_function(self.view.save_mask_btn, self.save_mask_btn_click)
        self.connect_click_function(self.view.load_mask_btn, self.load_mask_btn_click)
        self.connect_click_function(self.view.add_mask_btn, self.add_mask_btn_click)
        self.connect_click_function(self.view.mask_rb, self.mask_rb_click)
        self.connect_click_function(self.view.unmask_rb, self.unmask_rb_click)
        self.connect_click_function(self.view.fill_rb, self.fill_rb_click)
        self.connect_click_function(self.view.transparent_rb, self.transparent_rb_click)
        self.view.connect(self.view.point_size_sb, QtCore.SIGNAL('valueChanged(int)'), self.set_point_size)

        self.view.img_view.mouse_moved.connect(self.show_img_mouse_position)

        self.view.keyPressEvent = self.key_press_event


    def update_mask_dimension(self):
        self.mask_data.set_dimension(self.img_data.img_data.shape)

    def uncheck_all_btn(self, except_btn=None):
        btns = [self.view.circle_btn, self.view.rectangle_btn, self.view.polygon_btn, \
                self.view.point_btn]
        for btn in btns:
            if btn is not except_btn:
                if btn.isChecked():
                    btn.toggle()
        # if not except_btn.isChecked() and except_btn is not None:
        #     except_btn.toggle()

        shapes = [self.rect, self.circle, self.polygon]
        for shape in shapes:
            if shape is not None:
                self.view.img_view.img_view_box.removeItem(shape)
                self.view.img_view.mouse_moved.disconnect(shape.set_size)

        try:
            self.view.img_view.mouse_moved.disconnect(self.point.set_position)
            self.view.img_view.img_view_box.removeItem(self.point)
            self.point = None
        except AttributeError:
            pass


    def activate_circle_btn(self):
        if self.view.circle_btn.isChecked():
            self.state = 'circle'
            self.clicks = 0
            self.uncheck_all_btn(except_btn=self.view.circle_btn)
        else:
            print('hmm')
            self.state = None
            self.clicks = 0
            self.uncheck_all_btn()

    def activate_rectangle_btn(self):
        if self.view.rectangle_btn.isChecked():
            self.state = 'rectangle'
            self.clicks = 0
            self.uncheck_all_btn(except_btn=self.view.rectangle_btn)
        else:
            self.state = None
            self.uncheck_all_btn()

    def activate_polygon_btn(self):
        if self.view.polygon_btn.isChecked():
            self.state = 'polygon'
            self.clicks = 0
            self.uncheck_all_btn(except_btn=self.view.polygon_btn)
        else:
            self.state = None
            self.uncheck_all_btn()

    def activate_point_btn(self):
        if self.view.point_btn.isChecked():
            self.state = 'point'
            self.clicks = 0
            self.uncheck_all_btn(except_btn=self.view.point_btn)
            self.point = self.view.img_view.draw_point(self.view.point_size_sb.value())
            self.view.img_view.mouse_moved.connect(self.point.set_position)
        else:
            self.state = 'None'
            self.uncheck_all_btn()

    def undo_btn_click(self):
        self.mask_data.undo()
        self.view.img_view.plot_mask(self.mask_data.get_img())

    def redo_btn_click(self):
        self.mask_data.redo()
        self.view.img_view.plot_mask(self.mask_data.get_img())

    def plot_image(self):
        self.view.img_view.plot_image(self.img_data.get_img_data(), False)
        self.view.img_view.auto_range()

    def process_click(self, x, y):
        if self.state == 'circle':
            self.draw_circle(x, y)
        elif self.state == 'rectangle':
            self.draw_rectangle(x, y)
        elif self.state == 'point':
            self.draw_point(x, y)
        elif self.state == 'polygon':
            self.draw_polygon(x, y)

    def draw_circle(self, x, y):
        if self.clicks == 0:
            self.clicks += 1
            self.circle = self.view.img_view.draw_circle(x, y)
            self.view.img_view.mouse_moved.connect(self.circle.set_size)
        elif self.clicks == 1:
            self.clicks = 0
            self.mask_data.mask_QGraphicsEllipseItem(self.circle)
            self.view.img_view.img_view_box.removeItem(self.circle)
            self.view.img_view.plot_mask(self.mask_data.get_img())
            self.view.img_view.mouse_moved.disconnect(self.circle.set_size)
            self.circle = None

    def draw_rectangle(self, x, y):
        if self.clicks == 0:
            self.clicks += 1
            self.rect = self.view.img_view.draw_rectangle(x, y)
            self.view.img_view.mouse_moved.connect(self.rect.set_size)
        elif self.clicks == 1:
            self.clicks = 0
            self.mask_data.mask_QGraphicsRectItem(self.rect)
            self.view.img_view.img_view_box.removeItem(self.rect)
            self.view.img_view.plot_mask(self.mask_data.get_img())
            self.view.img_view.mouse_moved.disconnect(self.rect.set_size)
            self.rect = None

    def draw_point(self, x, y):
        radius = self.view.point_size_sb.value()
        self.mask_data.mask_ellipse(y, x, radius, radius)
        self.view.img_view.plot_mask(self.mask_data.get_img())

    def set_point_size(self, radius):
        try:
            self.point.set_radius(radius)
        except AttributeError:
            pass

    def draw_polygon(self, x, y):
        if self.clicks == 0:
            self.clicks += 1
            self.polygon = self.view.img_view.draw_polygon(x, y)
            self.view.img_view.mouse_moved.connect(self.polygon.set_size)
            self.view.img_view.mouse_left_double_clicked.connect(self.finish_polygon)
        elif self.clicks == 1:
            self.polygon.set_size(x, y)
            self.polygon.add_point(x, y)

    def finish_polygon(self, x, y):
        self.view.img_view.mouse_moved.disconnect(self.polygon.set_size)
        self.view.img_view.mouse_left_double_clicked.disconnect(self.finish_polygon)
        self.polygon.add_point(y, x)
        self.clicks = 0
        self.mask_data.mask_QGraphicsPolygonItem(self.polygon)
        self.view.img_view.plot_mask(self.mask_data.get_img())
        self.view.img_view.img_view_box.removeItem(self.polygon)
        self.polygon = None


    def below_thresh_btn_click(self):
        thresh = np.float64(self.view.below_thresh_txt.text())
        self.mask_data.mask_below_threshold(self.img_data.get_img_data(), thresh)
        self.view.img_view.plot_mask(self.mask_data.get_img())

    def above_thresh_btn_click(self):
        thresh = np.float64(self.view.above_thresh_txt.text())
        self.mask_data.mask_above_threshold(self.img_data.get_img_data(), thresh)
        self.view.img_view.plot_mask(self.mask_data.get_img())

    def invert_mask_btn_click(self):
        self.mask_data.invert_mask()
        self.view.img_view.plot_mask(self.mask_data.get_img())

    def clear_mask_btn_click(self):
        self.mask_data.clear_mask()
        self.view.img_view.plot_mask(self.mask_data.get_img())

    def cosmic_btn_click(self):
        self.mask_data.remove_cosmic(self.img_data.get_img_data())
        self.view.img_view.plot_mask(self.mask_data.get_img())

    def save_mask_btn_click(self, filename=None):
        if filename is None:
            filename = str(QtGui.QFileDialog.getSaveFileName(self.view, caption="Save mask data",
                                                             directory=self.working_dir['mask'], filter='*.mask'))

        if filename is not '':
            self.working_dir['mask'] = os.path.dirname(filename)
            np.savetxt(filename, self.mask_data.get_mask(), fmt="%d")

    def load_mask_btn_click(self, filename=None):
        if filename is None:
            filename = str(QtGui.QFileDialog.getOpenFileName(self.view, caption="Load mask data",
                                                             directory=self.working_dir['mask'], filter='*.mask'))

        if filename is not '':
            self.working_dir['mask'] = os.path.dirname(filename)
            mask_data = np.loadtxt(filename)
            if self.img_data.get_img_data().shape == mask_data.shape:
                self.mask_data.set_mask(np.loadtxt(filename))
                self.plot_mask()
            else:
                QtGui.QMessageBox.critical(self.view, 'Error', 'Image data and mask data in selected file do not have '
                                                               'the same shape. Mask could not be loaded.')

    def add_mask_btn_click(self, filename=None):
        if filename is None:
            filename = str(QtGui.QFileDialog.getOpenFileName(self.view, caption="Add mask data",
                                                             directory=self.working_dir['mask'], filter='*.mask'))

        if filename is not '':
            self.working_dir['mask'] = os.path.dirname(filename)
            mask_data = np.loadtxt(filename)
            if self.mask_data.get_mask().shape == mask_data.shape:
                self.mask_data.add_mask(np.loadtxt(filename))
                self.plot_mask()
            else:
                QtGui.QMessageBox.critical(self.view, 'Error', 'Image data and mask data in selected file do not have '
                                                               'the same shape. Mask could not be added.')

    def plot_mask(self):
        self.view.img_view.plot_mask(self.mask_data.get_mask())

    def key_press_event(self, ev):
        if self.state == "point":
            if ev.text() == 'q':
                self.view.point_size_sb.setValue(self.view.point_size_sb.value() + 1)
            if ev.text() == 'w':
                self.view.point_size_sb.setValue(self.view.point_size_sb.value() - 1)

        if ev.modifiers() == QtCore.Qt.ControlModifier:
            if ev.key() == 90:  #for pressing z
                self.undo_btn_click()
            elif ev.key() == 89:  #for pressing y
                self.redo_btn_click()
            elif ev.key() == 83:  #for pressing s
                self.save_mask_btn_click()
            elif ev.key == 79:  #for pressing o
                self.load_mask_btn_click()
            elif ev.key == 65:
                self.add_mask_btn_click()


    def mask_rb_click(self):
        self.mask_data.set_mode(True)

    def unmask_rb_click(self):
        self.mask_data.set_mode(False)

    def fill_rb_click(self):
        self.view.img_view.set_color([255, 0, 0, 255])
        self.plot_mask()

    #
    def transparent_rb_click(self):
        self.view.img_view.set_color([255, 0, 0, 100])
        self.plot_mask()


    def show_img_mouse_position(self, x, y):
        try:
            if x > 0 and y > 0:
                str = "x: %8.1f   y: %8.1f   I: %6.f" % (x, y, self.view.img_view.img_data.T[np.floor(x), np.floor(y)])
            else:
                str = "x: %.1f y: %.1f" % (x, y)
        except (IndexError, AttributeError):
            str = "x: %.1f y: %.1f" % (x, y)
        self.view.pos_lbl.setText(str)


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    controller = MaskController()
    app.exec_()