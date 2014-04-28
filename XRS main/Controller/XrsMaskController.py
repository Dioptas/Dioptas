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
from Data.XrsCalibrationData import XrsCalibrationData

import numpy as np


class XrsMaskController(object):
    def __init__(self):
        self.view = XrsMaskView()
        self.data = XrsImgData()

        self.view.img_view.add_left_click_observer(self.process_click)

        self.state = 'ellipse'
        self.clicks = 0

        self.plot_image()
        self.create_signals()

        self.create_mask_data()
        self.raise_window()

    def raise_window(self):
        self.view.show()
        self.view.setWindowState(self.view.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
        self.view.activateWindow()
        self.view.raise_()

    def create_signals(self):
        self.connect_click_function(self.view.circle_btn, self.activate_circle_btn)
        self.connect_click_function(self.view.ellipse_btn, self.activate_ellipse_btn)
        self.connect_click_function(self.view.rectangle_btn, self.activate_rectangle_btn)
        self.connect_click_function(self.view.polygon_btn, self.activate_polygon_btn)
        self.connect_click_function(self.view.point_btn, self.activate_point_btn)

    def create_mask_data(self):
        self

    def uncheck_all_btn(self, except_btn=None):
        btns = [self.view.circle_btn, self.view.ellipse_btn, self.view.rectangle_btn, self.view.polygon_btn, \
                self.view.point_btn]
        for btn in btns:
            if btn is not except_btn:
                if btn.isChecked():
                    btn.toggle()
        if not except_btn.isChecked() and except_btn is not None:
            except_btn.toggle()

    def activate_circle_btn(self):
        self.state = 'circle'
        self.clicks = 0
        self.uncheck_all_btn(except_btn=self.view.circle_btn)

    def activate_ellipse_btn(self):
        self.state = 'ellipse'
        self.clicks = 0
        self.uncheck_all_btn(except_btn=self.view.ellipse_btn)

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

    def connect_click_function(self, emitter, function):
        self.view.connect(emitter, QtCore.SIGNAL('clicked()'), function)

    def plot_image(self):
        self.data.load_file('../ExampleData/LaB6_WOS_30keV_005.tif')
        self.view.img_view.plot_image(self.data.get_img_data(), False)
        self.view.img_view.auto_range()

    def process_click(self, x, y):
        if self.state == 'circle':
            self.draw_circle(x,y)
        elif self.state == 'rectangle':
            self.draw_rectangle(x,y)
        elif self.state == 'ellipse':
            self.draw_ellipse(x,y)

    def draw_circle(self,x,y):
        if self.clicks == 0:
            self.clicks += 1
            self.circle = self.view.img_view.draw_circle(x,y)
            self.view.img_view.add_mouse_move_observer(self.circle.set_size)
        elif self.clicks == 1:
            self.clicks = 0
            self.view.img_view.del_mouse_move_observer(self.circle.set_size)

    def draw_ellipse(self,x,y):
        if self.clicks == 0:
            self.clicks += 1
            self.ellipse = self.view.img_view.draw_ellipse(x,y)
            self.view.img_view.add_mouse_move_observer(self.ellipse.set_size)
        elif self.clicks == 1:
            self.clicks += 1
            self.view.img_view.del_mouse_move_observer(self.ellipse.set_size)
            self.view.img_view.add_mouse_move_observer(self.ellipse.set_size2)
        elif self.clicks == 2:
            self.clicks += 0
            self.view.img_view.del_mouse_move_observer(self.ellipse.set_size2)

    def draw_rectangle(self, x, y):
        if self.clicks == 0:
            self.clicks += 1
            self.rect = self.view.img_view.draw_rectangle(x,y)
            self.view.img_view.add_mouse_move_observer(self.rect.set_size)
        elif self.clicks == 1:
            self.clicks = 0
            self.view.img_view.del_mouse_move_observer(self.rect.set_size)







if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    controller = XrsMaskController()
    app.exec_()