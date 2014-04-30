__author__ = 'Clemens Prescher'

import sys
import os

import pyqtgraph as pg

pg.setConfigOption('useOpenGL', False)
pg.setConfigOption('leftButtonPan', False)
pg.setConfigOption('background', 'k')
pg.setConfigOption('foreground', 'w')
pg.setConfigOption('antialias', True)
from PyQt4 import QtGui, QtCore
from Views.XrsMaskView import XrsMaskView
from Data.XrsImgData import XrsImgData
from Data.XrsMaskData import XrsMaskData
from Data.XrsCalibrationData import XrsCalibrationData

import numpy as np


class XrsMaskController(object):
    def __init__(self):
        self.view = XrsMaskView()
        self.img_data = XrsImgData()
        self.mask_data = XrsMaskData()

        self.view.img_view.add_left_click_observer(self.process_click)

        self.state = 'polygon'
        self.clicks = 0

        self.load_image()
        self.create_signals()

        self.rect = None
        self.circle = None
        self.polygon = None

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
        self.view.connect(self.view.point_size_sb, QtCore.SIGNAL('valueChanged(int)'), self.set_point_size)

    def uncheck_all_btn(self, except_btn=None):
        btns = [self.view.circle_btn, self.view.rectangle_btn, self.view.polygon_btn, \
                self.view.point_btn]
        for btn in btns:
            if btn is not except_btn:
                if btn.isChecked():
                    btn.toggle()
        if not except_btn.isChecked() and except_btn is not None:
            except_btn.toggle()

        shapes = [self.rect, self.circle, self.polygon]
        for shape in shapes:
            if shape is not None:
                self.view.img_view.img_view_box.removeItem(shape)
                self.view.img_view.del_mouse_move_observer(shape.set_size)

        try:
            self.view.img_view.del_mouse_move_observer(self.point.set_position)
            self.view.img_view.img_view_box.removeItem(self.point)
            self.point = None
        except AttributeError:
            pass


    def activate_circle_btn(self):
        self.state = 'circle'
        self.clicks = 0
        self.uncheck_all_btn(except_btn=self.view.circle_btn)

    def activate_rectangle_btn(self):
        self.state = 'rectangle'
        self.clicks = 0
        self.uncheck_all_btn(except_btn=self.view.rectangle_btn)

    def activate_polygon_btn(self):
        self.state = 'polygon'
        self.clicks = 0
        self.uncheck_all_btn(except_btn=self.view.polygon_btn)

    def activate_point_btn(self):
        self.state = 'point'
        self.clicks = 0
        self.uncheck_all_btn(except_btn=self.view.point_btn)
        self.point = self.view.img_view.draw_point(self.view.point_size_sb.value())
        self.view.img_view.add_mouse_move_observer(self.point.set_position)

    def undo_btn_click(self):
        self.mask_data.undo()
        self.view.img_view.plot_mask(self.mask_data.get_img())

    def redo_btn_click(self):
        self.mask_data.redo()
        self.view.img_view.plot_mask(self.mask_data.get_img())

    def load_image(self):
        self.img_data.load_file('../ExampleData/LaB6_WOS_30keV_005.tif')

        self.mask_data.set_dimension(self.img_data.get_img_data().shape)

        self.view.img_view.plot_image(self.img_data.get_img_data(), False)
        self.view.img_view.auto_range()
        self.view.img_view.plot_mask(self.mask_data.get_img())

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
            self.view.img_view.add_mouse_move_observer(self.circle.set_size)
        elif self.clicks == 1:
            self.clicks = 0
            self.mask_data.mask_QGraphicsEllipseItem(self.circle)
            self.view.img_view.img_view_box.removeItem(self.circle)
            self.view.img_view.plot_mask(self.mask_data.get_img())
            self.view.img_view.del_mouse_move_observer(self.circle.set_size)
            self.circle = None

    def draw_rectangle(self, x, y):
        if self.clicks == 0:
            self.clicks += 1
            self.rect = self.view.img_view.draw_rectangle(x, y)
            self.view.img_view.add_mouse_move_observer(self.rect.set_size)
        elif self.clicks == 1:
            self.clicks = 0
            self.mask_data.mask_QGraphicsRectItem(self.rect)
            self.view.img_view.img_view_box.removeItem(self.rect)
            self.view.img_view.plot_mask(self.mask_data.get_img())
            self.view.img_view.del_mouse_move_observer(self.rect.set_size)
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
            self.view.img_view.add_mouse_move_observer(self.polygon.set_size)
            self.view.img_view.add_left_double_click_observer(self.finish_polygon)
        elif self.clicks == 1:
            self.polygon.set_size(x, y)
            self.polygon.add_point(x, y)

    def finish_polygon(self, x, y):
        self.view.img_view.del_mouse_move_observer(self.polygon.set_size)
        self.view.img_view.del_left_double_click_observer(self.finish_polygon)
        self.polygon.add_point(y, x)
        self.clicks = 0
        self.mask_data.mask_QGraphicsPolygonItem(self.polygon)
        self.view.img_view.plot_mask(self.mask_data.get_img())
        self.view.img_view.img_view_box.removeItem(self.polygon)
        self.polygon = None



if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    controller = XrsMaskController()
    app.exec_()