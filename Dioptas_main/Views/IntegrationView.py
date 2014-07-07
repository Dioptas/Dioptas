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
    overlay_color_btn_clicked = QtCore.pyqtSignal(int, QtGui.QWidget)
    overlay_show_cb_state_changed = QtCore.pyqtSignal(int, bool)
    overlay_name_changed = QtCore.pyqtSignal(int, basestring)
    phase_color_btn_clicked = QtCore.pyqtSignal(int, QtGui.QWidget)
    phase_show_cb_state_changed = QtCore.pyqtSignal(int, bool)
    phase_name_changed = QtCore.pyqtSignal(int, basestring)

    def __init__(self):
        super(IntegrationView, self).__init__()
        self.setupUi(self)
        self.horizontal_splitter.setStretchFactor(5, 0)
        self.horizontal_splitter.setSizes([500, 200])
        self.vertical_splitter.setStretchFactor(0, 0)
        self.vertical_splitter.setStretchFactor(1, 1)
        self.vertical_splitter.setSizes([100, 700])
        self.img_view = IntegrationImgView(self.img_pg_layout, orientation='horizontal')
        self.img_pg_layout.ci.layout.setContentsMargins(10, 10, 10, 5)
        self.img_pg_layout.ci.layout.setSpacing(5)
        self.spectrum_view = SpectrumView(self.spectrum_pg_layout)
        self.spectrum_pg_layout.ci.layout.setContentsMargins(10, 10, 0, 10)
        self.set_validator()

        self.overlay_tw.cellChanged.connect(self.overlay_label_editingFinished)
        self.overlay_show_cbs = []
        self.overlay_color_btns = []

        self.phase_tw.cellChanged.connect(self.phase_label_editingFinished)
        self.phase_show_cbs = []
        self.phase_color_btns = []
        header_view = QtGui.QHeaderView(QtCore.Qt.Horizontal, self.phase_tw)
        self.phase_tw.setHorizontalHeader(header_view)
        header_view.setResizeMode(2, QtGui.QHeaderView.Stretch)
        header_view.setResizeMode(3, QtGui.QHeaderView.ResizeToContents)
        header_view.setResizeMode(4, QtGui.QHeaderView.ResizeToContents)
        header_view.hide()


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
        self.overlay_tw.blockSignals(True)

        show_cb = QtGui.QCheckBox()
        show_cb.setChecked(True)
        show_cb.stateChanged.connect(partial(self.overlay_show_cb_changed, show_cb))
        show_cb.setStyleSheet("background-color: transparent")
        self.overlay_tw.setCellWidget(current_rows, 0, show_cb)
        self.overlay_show_cbs.append(show_cb)

        color_button = QtGui.QPushButton()
        color_button.setStyleSheet("background-color: " +color)
        color_button.clicked.connect(partial(self.overlay_color_btn_click, color_button))
        self.overlay_tw.setCellWidget(current_rows,1, color_button)
        self.overlay_color_btns.append(color_button)

        name_item = QtGui.QTableWidgetItem(name)
        name_item.setFlags(name_item.flags() & ~QtCore.Qt.ItemIsEditable)
        self.overlay_tw.setItem(current_rows,2, QtGui.QTableWidgetItem(name))


        self.overlay_tw.setColumnWidth(0, 20)
        self.overlay_tw.setColumnWidth(1, 25)
        self.overlay_tw.setRowHeight(current_rows, 25)
        self.select_overlay(current_rows)
        self.overlay_tw.blockSignals(False)

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
        self.overlay_tw.blockSignals(True)
        self.overlay_tw.removeRow(ind)
        self.overlay_tw.blockSignals(False)
        del self.overlay_show_cbs[ind]
        del self.overlay_color_btns[ind]

        if self.overlay_tw.rowCount()>ind:
            self.select_overlay(ind)
        else:
            self.select_overlay(self.overlay_tw.rowCount()-1)

    def overlay_color_btn_click(self, button):
        self.overlay_color_btn_clicked.emit(self.overlay_color_btns.index(button), button)

    def overlay_show_cb_changed(self, checkbox):
        self.overlay_show_cb_state_changed.emit(self.overlay_show_cbs.index(checkbox), checkbox.isChecked())

    def overlay_show_cb_set_checked(self, ind, state):
        checkbox = self.overlay_show_cbs[ind]
        checkbox.setChecked(state)

    def overlay_show_cb_is_checked(self, ind):
        checkbox = self.overlay_show_cbs[ind]
        return checkbox.isChecked()

    def overlay_label_editingFinished(self, row, col):
        label_item = self.overlay_tw.item(row, col)
        self.overlay_name_changed.emit(row, str(label_item.text()))

    ################################################################################################
    # Now comes all the phase tw stuff
    ################################################################################################

    def add_phase(self, name, color):
        current_rows = self.phase_tw.rowCount()
        self.phase_tw.setRowCount(current_rows+1)
        self.phase_tw.blockSignals(True)

        show_cb = QtGui.QCheckBox()
        show_cb.setChecked(True)
        show_cb.stateChanged.connect(partial(self.phase_show_cb_changed, show_cb))
        show_cb.setStyleSheet("background-color: transparent")
        self.phase_tw.setCellWidget(current_rows, 0, show_cb)
        self.phase_show_cbs.append(show_cb)

        color_button = QtGui.QPushButton()
        color_button.setStyleSheet("background-color: " +color)
        color_button.clicked.connect(partial(self.phase_color_btn_click, color_button))
        self.phase_tw.setCellWidget(current_rows,1, color_button)
        self.phase_color_btns.append(color_button)

        self.phase_tw.setItem(current_rows,2, QtGui.QTableWidgetItem(name))

        pressure_item = QtGui.QTableWidgetItem('0 GPa')
        pressure_item.setFlags(pressure_item.flags() & ~QtCore.Qt.ItemIsEditable)
        pressure_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.phase_tw.setItem(current_rows,3, pressure_item)

        temperature_item = QtGui.QTableWidgetItem('300 K')
        temperature_item.setFlags(temperature_item.flags() & ~QtCore.Qt.ItemIsEditable)
        temperature_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.phase_tw.setItem(current_rows,4, temperature_item)

        self.phase_tw.setColumnWidth(0, 20)
        self.phase_tw.setColumnWidth(1, 25)
        # self.phase_tw.setColumnWidth(3, 85)
        # self.phase_tw.setColumnWidth(4, 85)
        self.phase_tw.setRowHeight(current_rows, 25)
        self.select_phase(current_rows)
        self.phase_tw.blockSignals(False)

    def select_phase(self, ind):
        self.phase_tw.selectRow(ind)

    def get_selected_phase_row(self):
        selected = self.phase_tw.selectionModel().selectedRows()
        try:
            row = selected[0].row()
        except IndexError:
            row = -1
        return row

    def get_phase(self):
        pass

    def del_phase(self, ind):
        self.phase_tw.blockSignals(True)
        self.phase_tw.removeRow(ind)
        self.phase_tw.blockSignals(False)
        del self.phase_show_cbs[ind]
        del self.phase_color_btns[ind]

        if self.phase_tw.rowCount()>ind:
            self.select_phase(ind)
        else:
            self.select_phase(self.phase_tw.rowCount()-1)

    def set_phase_tw_temperature(self, ind, T):
        temperature_item = self.phase_tw.item(ind, 4)
        temperature_item.setText("{0} K".format(T))

    def get_phase_tw_temperature(self, ind):
        temperature_item = self.phase_tw.item(ind, 4)
        try:
            temperature = float(str(temperature_item.text()).split()[0])
        except:
            temperature = np.NaN
        return temperature

    def set_phase_tw_pressure(self, ind, P):
        pressure_item = self.phase_tw.item(ind, 3)
        pressure_item.setText("{0} GPa".format(P))

    def get_phase_tw_pressure(self, ind):
        pressure_item = self.phase_tw.item(ind, 3)
        pressure = float(str(pressure_item.text()).split()[0])
        return pressure

    def phase_color_btn_click(self, button):
        self.phase_color_btn_clicked.emit(self.phase_color_btns.index(button), button)

    def phase_show_cb_changed(self, checkbox):
        self.phase_show_cb_state_changed.emit(self.phase_show_cbs.index(checkbox), checkbox.isChecked())

    def phase_show_cb_set_checked(self, ind, state):
        checkbox = self.phase_show_cbs[ind]
        checkbox.setChecked(state)

    def phase_show_cb_is_checked(self, ind):
        checkbox = self.phase_show_cbs[ind]
        return checkbox.isChecked()

    def phase_label_editingFinished(self, row, col):
        if col == 2:
            label_item = self.phase_tw.item(row, col)
            self.phase_name_changed.emit(row, str(label_item.text()))

