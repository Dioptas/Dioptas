# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
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

import os
from PyQt4 import QtGui, QtCore
from UiFiles.IntegrationUI import Ui_xrs_integration_widget
from ImgView import IntegrationImgView
from SpectrumView import SpectrumView
from functools import partial
import numpy as np
import pyqtgraph as pg


class IntegrationView(QtGui.QWidget, Ui_xrs_integration_widget):
    overlay_color_btn_clicked = QtCore.pyqtSignal(int, basestring, QtGui.QWidget)

    def __init__(self):
        super(IntegrationView, self).__init__()
        self.setupUi(self)
        self.horizontal_splitter.setStretchFactor(0, 1)
        self.horizontal_splitter.setStretchFactor(1, 1)
        self.horizontal_splitter.setSizes([300, 200])
        self.vertical_splitter.setStretchFactor(0, 0)
        self.vertical_splitter.setStretchFactor(1, 1)
        self.vertical_splitter.setSizes([100, 700])
        self.img_view = IntegrationImgView(self.img_pg_layout, orientation='horizontal')
        self.img_pg_layout.ci.layout.setContentsMargins(10, 10, 10, 5)
        self.img_pg_layout.ci.layout.setSpacing(5)
        self.spectrum_view = SpectrumView(self.spectrum_pg_layout)
        self.spectrum_pg_layout.ci.layout.setContentsMargins(10, 10, 0, 10)
        self.set_validator()

    def set_validator(self):
        self.phase_pressure_step_txt.setValidator(QtGui.QDoubleValidator())
        self.phase_temperature_step_txt.setValidator(QtGui.QDoubleValidator())
        self.overlay_scale_step_txt.setValidator(QtGui.QDoubleValidator())
        self.overlay_offset_step_txt.setValidator(QtGui.QDoubleValidator())
        self.phase_pressure_step_txt.setValidator(QtGui.QDoubleValidator())
        self.phase_temperature_step_txt.setValidator(QtGui.QDoubleValidator())

    def switch_to_cake(self):
        self.img_view.img_view_box.setAspectLocked(False)
        self.img_view.activate_vertical_line()

    def switch_to_img(self):
        self.img_view.img_view_box.setAspectLocked(True)
        self.img_view.deactivate_vertical_line()

    def add_overlay(self, name, color):
        current_rows = self.overlay_tw.rowCount()
        self.overlay_tw.setRowCount(current_rows+1)
        name_item = QtGui.QTableWidgetItem(name)
        name_item.setFlags(name_item.flags() & ~QtCore.Qt.ItemIsEditable)
        self.overlay_tw.setItem(current_rows,1, QtGui.QTableWidgetItem(name))

        color_button = QtGui.QPushButton()
        color_button.setStyleSheet("background-color: " +color)
        color_button.clicked.connect(partial(self.overlay_color_btn_click, current_rows, color, color_button))
        self.overlay_tw.setCellWidget(current_rows,0, color_button)
        self.overlay_tw.setColumnWidth(0, 25)
        self.overlay_tw.setRowHeight(current_rows, 25)
        self.select_overlay(current_rows)

    def select_overlay(self, ind):
        self.overlay_tw.selectRow(ind)

    def get_selected_overlay_row(self):
        selected = self.overlay_tw.selectionModel().selectedRows()
        try:
            row = selected[0].row()
        except IndexError:
            row = -1
        return row

    def get_overlay(self):
        pass

    def del_overlay(self, ind):
        self.overlay_tw.removeRow(ind)
        if self.overlay_tw.rowCount()>ind:
            self.select_overlay(ind)
        else:
            self.select_overlay(self.overlay_tw.rowCount()-1)

    def overlay_color_btn_click(self, ind, current_color, button):
        self.overlay_color_btn_clicked.emit(ind, current_color, button)

