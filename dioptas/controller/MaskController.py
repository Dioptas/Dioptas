# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2015  Clemens Prescher (clemens.prescher@gmail.com)
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

import sys
import os

from qtpy import QtWidgets, QtCore

import numpy as np

from ..widgets.UtilityWidgets import open_file_dialog, save_file_dialog

# imports for type hinting in PyCharm -- DO NOT DELETE
from ..widgets.MaskWidget import MaskWidget
from ..model.DioptasModel import DioptasModel


class MaskController(object):
    def __init__(self, working_dir, widget, dioptas_model):
        """
        :param working_dir: Dictionary of working directories
        :param widget: Reference to a MaskView object
        :type widget: MaskWidget
        :param dioptas_model: Reference to an DioptasModel object
        :type dioptas_model: DioptasModel
        """
        self.working_dir = working_dir
        self.widget = widget
        self.model = dioptas_model

        self.state = None
        self.clicks = 0
        self.create_signals()

        self.rect = None
        self.circle = None
        self.polygon = None
        self.point = None

    def create_signals(self):
        self.widget.img_widget.mouse_left_clicked.connect(self.process_click)

        self.model.img_changed.connect(self.update_mask_dimension)

        self.widget.circle_btn.clicked.connect(self.activate_circle_btn)
        self.widget.rectangle_btn.clicked.connect(self.activate_rectangle_btn)
        self.widget.polygon_btn.clicked.connect(self.activate_polygon_btn)
        self.widget.point_btn.clicked.connect(self.activate_point_btn)
        self.widget.undo_btn.clicked.connect(self.undo_btn_click)
        self.widget.redo_btn.clicked.connect(self.redo_btn_click)
        self.widget.below_thresh_btn.clicked.connect(self.below_thresh_btn_click)
        self.widget.above_thresh_btn.clicked.connect(self.above_thresh_btn_click)
        self.widget.cosmic_btn.clicked.connect(self.cosmic_btn_click)
        self.widget.grow_btn.clicked.connect(self.grow_btn_click)
        self.widget.shrink_btn.clicked.connect(self.shrink_btn_click)
        self.widget.invert_mask_btn.clicked.connect(self.invert_mask_btn_click)
        self.widget.clear_mask_btn.clicked.connect(self.clear_mask_btn_click)
        self.widget.save_mask_btn.clicked.connect(self.save_mask_btn_click)
        self.widget.load_mask_btn.clicked.connect(self.load_mask_btn_click)
        self.widget.add_mask_btn.clicked.connect(self.add_mask_btn_click)
        self.widget.mask_rb.clicked.connect(self.mask_rb_click)
        self.widget.unmask_rb.clicked.connect(self.unmask_rb_click)
        self.widget.fill_rb.clicked.connect(self.fill_rb_click)
        self.widget.transparent_rb.clicked.connect(self.transparent_rb_click)

        self.widget.point_size_sb.valueChanged.connect(self.set_point_size)
        self.widget.img_widget.mouse_moved.connect(self.show_img_mouse_position)

        self.widget.keyPressEvent = self.key_press_event

    def update_mask_dimension(self):
        self.model.mask_model.set_dimension(self.model.img_model._img_data.shape)

    def uncheck_all_btn(self, except_btn=None):
        btns = [self.widget.circle_btn, self.widget.rectangle_btn, self.widget.polygon_btn, \
                self.widget.point_btn]
        for btn in btns:
            if btn is not except_btn:
                if btn.isChecked():
                    btn.toggle()
        # if not except_btn.isChecked() and except_btn is not None:
        #     except_btn.toggle()

        shapes = [self.rect, self.circle, self.polygon]
        for shape in shapes:
            if shape is not None:
                self.widget.img_widget.img_view_box.removeItem(shape)
                self.widget.img_widget.mouse_moved.disconnect(shape.set_size)

        try:
            self.widget.img_widget.mouse_moved.disconnect(self.point.set_position)
            self.widget.img_widget.img_view_box.removeItem(self.point)
            self.point = None
        except AttributeError:
            pass

    def activate_circle_btn(self):
        if self.widget.circle_btn.isChecked():
            self.state = 'circle'
            self.clicks = 0
            self.uncheck_all_btn(except_btn=self.widget.circle_btn)
        else:
            self.state = None
            self.clicks = 0
            self.uncheck_all_btn()

    def activate_rectangle_btn(self):
        if self.widget.rectangle_btn.isChecked():
            self.state = 'rectangle'
            self.clicks = 0
            self.uncheck_all_btn(except_btn=self.widget.rectangle_btn)
        else:
            self.state = None
            self.uncheck_all_btn()

    def activate_polygon_btn(self):
        if self.widget.polygon_btn.isChecked():
            self.state = 'polygon'
            self.clicks = 0
            self.uncheck_all_btn(except_btn=self.widget.polygon_btn)
        else:
            self.state = None
            self.uncheck_all_btn()

    def activate_point_btn(self):
        if self.widget.point_btn.isChecked():
            self.state = 'point'
            self.clicks = 0
            self.uncheck_all_btn(except_btn=self.widget.point_btn)
            self.point = self.widget.img_widget.draw_point(self.widget.point_size_sb.value())
            self.widget.img_widget.mouse_moved.connect(self.point.set_position)
        else:
            self.state = 'None'
            self.uncheck_all_btn()

    def undo_btn_click(self):
        self.model.mask_model.undo()
        self.plot_mask()

    def redo_btn_click(self):
        self.model.mask_model.redo()
        self.plot_mask()

    def plot_image(self):
        self.widget.img_widget.plot_image(self.model.img_data, False)
        self.widget.img_widget.auto_range()

    def process_click(self, x, y):
        x, y = int(x), int(y)
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
            self.circle = self.widget.img_widget.draw_circle(x, y)
            self.widget.img_widget.mouse_moved.connect(self.circle.set_size)
        elif self.clicks == 1:
            self.clicks = 0
            self.model.mask_model.mask_QGraphicsEllipseItem(self.circle)
            self.widget.img_widget.img_view_box.removeItem(self.circle)
            self.plot_mask()
            self.widget.img_widget.mouse_moved.disconnect(self.circle.set_size)
            self.circle = None

    def draw_rectangle(self, x, y):
        if self.clicks == 0:
            self.clicks += 1
            self.rect = self.widget.img_widget.draw_rectangle(x, y)
            self.widget.img_widget.mouse_moved.connect(self.rect.set_size)
        elif self.clicks == 1:
            self.clicks = 0
            self.model.mask_model.mask_QGraphicsRectItem(self.rect)
            self.widget.img_widget.img_view_box.removeItem(self.rect)
            self.plot_mask()
            self.widget.img_widget.mouse_moved.disconnect(self.rect.set_size)
            self.rect = None

    def draw_point(self, x, y):
        radius = self.widget.point_size_sb.value()
        if radius <= 0:
            # filter point with no radius
            return
        self.model.mask_model.mask_ellipse(x, y, radius, radius)
        self.plot_mask()

    def set_point_size(self, radius):
        try:
            self.point.set_radius(radius)
        except AttributeError:
            pass

    def draw_polygon(self, x, y):
        if self.clicks == 0:
            self.clicks += 1
            self.polygon = self.widget.img_widget.draw_polygon(x, y)
            self.widget.img_widget.mouse_moved.connect(self.polygon.set_size)
            self.widget.img_widget.mouse_left_double_clicked.connect(self.finish_polygon)
        elif self.clicks == 1:
            self.polygon.set_size(x, y)
            self.polygon.add_point(x, y)

    def finish_polygon(self, x, y):
        self.widget.img_widget.mouse_moved.disconnect(self.polygon.set_size)
        self.widget.img_widget.mouse_left_double_clicked.disconnect(self.finish_polygon)
        self.polygon.add_point(x, y)
        self.clicks = 0
        self.model.mask_model.mask_QGraphicsPolygonItem(self.polygon)
        self.plot_mask()
        self.widget.img_widget.img_view_box.removeItem(self.polygon)
        self.polygon = None

    def below_thresh_btn_click(self):
        thresh = np.float64(self.widget.below_thresh_txt.text())
        self.model.mask_model.mask_below_threshold(self.model.img_data, thresh)
        self.plot_mask()

    def above_thresh_btn_click(self):
        thresh = np.float64(self.widget.above_thresh_txt.text())
        self.model.mask_model.mask_above_threshold(self.model.img_data, thresh)
        self.plot_mask()

    def grow_btn_click(self):
        self.model.mask_model.grow()
        self.plot_mask()

    def shrink_btn_click(self):
        self.model.mask_model.shrink()
        self.plot_mask()

    def invert_mask_btn_click(self):
        self.model.mask_model.invert_mask()
        self.plot_mask()

    def clear_mask_btn_click(self):
        self.model.mask_model.clear_mask()
        self.plot_mask()

    def cosmic_btn_click(self):
        self.model.mask_model.remove_cosmic(self.model.img_data)
        self.plot_mask()

    def save_mask_btn_click(self):
        img_filename, _ = os.path.splitext(os.path.basename(self.model.img_model.filename))
        filename = save_file_dialog(self.widget, "Save mask data",
                                    os.path.join(self.working_dir['mask'],
                                                 img_filename + '.mask'),
                                    filter='Mask (*.mask)')

        if filename is not '':
            self.working_dir['mask'] = os.path.dirname(filename)
            self.model.mask_model.save_mask(filename)

    def load_mask_btn_click(self):
        filename = open_file_dialog(self.widget, caption="Load mask data",
                                    directory=self.working_dir['mask'], filter='*.mask')

        if filename is not '':
            self.working_dir['mask'] = os.path.dirname(filename)
            if self.model.mask_model.load_mask(filename):
                self.plot_mask()
            else:
                QtWidgets.QMessageBox.critical(self.widget, 'Error',
                                               'Image data and mask data in selected file do not have '
                                               'the same shape. Mask could not be loaded.')

    def add_mask_btn_click(self):
        filename = open_file_dialog(self.widget, caption="Add mask data",
                                    directory=self.working_dir['mask'], filter='*.mask')

        if filename is not '':
            self.working_dir['mask'] = os.path.dirname(filename)
            if self.model.mask_model.add_mask(filename):
                self.plot_mask()
            else:
                QtWidgets.QMessageBox.critical(self.widget, 'Error',
                                               'Image data and mask data in selected file do not have '
                                               'the same shape. Mask could not be added.')

    def plot_mask(self):
        self.widget.img_widget.plot_mask(self.model.mask_model.get_img())

    def key_press_event(self, ev):
        if self.state == "point":
            if ev.text() == 'q':
                self.widget.point_size_sb.setValue(self.widget.point_size_sb.value() + 1)
            if ev.text() == 'w':
                self.widget.point_size_sb.setValue(self.widget.point_size_sb.value() - 1)

        if ev.modifiers() == QtCore.Qt.ControlModifier:
            if ev.key() == 90:  # for pressing z
                self.undo_btn_click()
            elif ev.key() == 89:  # for pressing y
                self.redo_btn_click()
            elif ev.key() == 83:  # for pressing s
                self.save_mask_btn_click()
            elif ev.key == 79:  # for pressing o
                self.load_mask_btn_click()
            elif ev.key == 65:  # for pressing a
                self.add_mask_btn_click()

    def mask_rb_click(self):
        self.model.mask_model.set_mode(True)

    def unmask_rb_click(self):
        self.model.mask_model.set_mode(False)

    def fill_rb_click(self):
        self.widget.img_widget.set_color([255, 0, 0, 255])
        self.plot_mask()

    #
    def transparent_rb_click(self):
        self.widget.img_widget.set_color([255, 0, 0, 100])
        self.plot_mask()

    def show_img_mouse_position(self, x, y):
        try:
            if x > 0 and y > 0:
                str = "x: %8.1f   y: %8.1f   I: %6.f" % (
                    x, y, self.widget.img_widget.img_data.T[np.floor(x), np.floor(y)])
            else:
                str = "x: %.1f y: %.1f" % (x, y)
        except (IndexError, AttributeError):
            str = "x: %.1f y: %.1f" % (x, y)
        self.widget.pos_lbl.setText(str)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    controller = MaskController()
    app.exec_()
