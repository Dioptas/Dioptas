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

from functools import partial
import os

from qtpy import QtWidgets, QtCore, QtGui

from ...CustomWidgets import LabelAlignRight, FlatButton, CheckableFlatButton, DoubleSpinBoxAlignRight, \
    VerticalSpacerItem, HorizontalSpacerItem, ListTableWidget, DoubleMultiplySpinBoxAlignRight, HorizontalLine
from ...CustomWidgets import NoRectDelegate
from .... import icons_path


class OverlayWidget(QtWidgets.QWidget):
    color_btn_clicked = QtCore.Signal(int, QtWidgets.QWidget)
    show_cb_state_changed = QtCore.Signal(int, bool)
    name_changed = QtCore.Signal(int, str)
    scale_sb_value_changed = QtCore.Signal(int, float)
    offset_sb_value_changed = QtCore.Signal(int, float)

    def __init__(self):
        super(OverlayWidget, self).__init__()

        self._layout = QtWidgets.QHBoxLayout()
        self._layout.setContentsMargins(5, 5, 5, 5)
        self._layout.setSpacing(5)

        self.button_widget = QtWidgets.QWidget(self)
        self.button_widget.setObjectName('overlay_control_widget')
        self._button_layout = QtWidgets.QVBoxLayout(self.button_widget)
        self._button_layout.setContentsMargins(0, 0, 0, 0)
        self._button_layout.setSpacing(6)

        self.add_btn = FlatButton()
        self.delete_btn = FlatButton()
        self.clear_btn = FlatButton()
        self.move_up_btn = FlatButton()
        self.move_down_btn = FlatButton()

        self._button_layout.addWidget(self.add_btn)
        self._button_layout.addWidget(self.delete_btn)
        self._button_layout.addWidget(HorizontalLine())
        self._button_layout.addWidget(HorizontalLine())
        self._button_layout.addSpacerItem(VerticalSpacerItem())
        self._button_layout.addWidget(self.clear_btn)
        self._button_layout.addSpacerItem(VerticalSpacerItem())
        self._button_layout.addWidget(HorizontalLine())
        self._button_layout.addWidget(HorizontalLine())
        self._button_layout.addWidget(self.move_up_btn)
        self._button_layout.addWidget(self.move_down_btn)
        self._layout.addWidget(self.button_widget)

        self.parameter_widget = QtWidgets.QWidget(self)
        self._parameter_layout = QtWidgets.QVBoxLayout()
        self._parameter_layout.setContentsMargins(0, 0, 0, 0)
        self._parameter_layout.setSpacing(5)

        self.scale_step_msb = DoubleMultiplySpinBoxAlignRight()
        self.offset_step_msb = DoubleMultiplySpinBoxAlignRight()

        self._step_gb = QtWidgets.QWidget()
        self._step_layout = QtWidgets.QVBoxLayout()
        self._step_layout.setContentsMargins(0, 0, 0, 0)
        self._step_layout.setSpacing(4)
        self._step_layout.addWidget(QtWidgets.QLabel('Scale Step'))
        self._step_layout.addWidget(self.scale_step_msb)
        self._step_layout.addWidget(QtWidgets.QLabel('Offset Step'))
        self._step_layout.addWidget(self.offset_step_msb)
        self._step_gb.setLayout(self._step_layout)
        self._parameter_layout.addWidget(self._step_gb)
        self._parameter_layout.addWidget(HorizontalLine())

        self._waterfall_gb = QtWidgets.QWidget()
        self.waterfall_separation_msb = DoubleMultiplySpinBoxAlignRight()
        self.waterfall_btn = QtWidgets.QPushButton('Waterfall')
        self.waterfall_reset_btn = QtWidgets.QPushButton('Reset')

        self._waterfall_layout = QtWidgets.QVBoxLayout()
        self._waterfall_layout.setContentsMargins(0, 0, 0, 0)
        self._waterfall_layout.setSpacing(4)
        self._waterfall_layout.addWidget(self.waterfall_btn)
        self._waterfall_layout.addWidget(self.waterfall_separation_msb)
        self._waterfall_layout.addWidget(self.waterfall_reset_btn)
        self._waterfall_gb.setLayout(self._waterfall_layout)
        self._parameter_layout.addWidget(self._waterfall_gb)
        self._parameter_layout.addWidget(HorizontalLine())

        self._parameter_layout.addItem(VerticalSpacerItem())

        self.set_as_bkg_btn = QtWidgets.QPushButton('As Bkg')
        self.set_as_bkg_btn.setCheckable(True)
        self._background_layout = QtWidgets.QHBoxLayout()
        self._background_layout.setContentsMargins(0, 0, 0, 0)
        self._background_layout.addSpacerItem(HorizontalSpacerItem())
        self._background_layout.addWidget(self.set_as_bkg_btn)
        self._parameter_layout.addLayout(self._background_layout)

        self.parameter_widget.setLayout(self._parameter_layout)

        self.overlay_tw = ListTableWidget(columns=5)
        self.overlay_tw.setObjectName('overlay_table_widget')
        self.overlay_tw.setHorizontalHeaderLabels(['', '', 'Name', 'Scale', 'Offset'])
        self.overlay_tw.horizontalHeader().setVisible(True)
        self.overlay_tw.horizontalHeader().setStretchLastSection(False)
        self.overlay_tw.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        self.overlay_tw.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        self.overlay_tw.horizontalHeader().setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)

        self.overlay_tw.setColumnWidth(0, 20)
        self.overlay_tw.setColumnWidth(1, 25)
        self.overlay_tw.cellChanged.connect(self.label_editingFinished)
        self.overlay_tw.setItemDelegate(NoRectDelegate())

        self._layout.addWidget(self.overlay_tw, 10)
        self._layout.addWidget(self.parameter_widget, 0)

        # label for alternative view:
        self.overlay_header_btn = QtWidgets.QPushButton('Overlay')
        self.overlay_header_btn.setObjectName('overlay_header_btn')
        self.overlay_header_btn.setEnabled(False)
        self.overlay_header_btn.setVisible(False)
        self._main_layout = QtWidgets.QVBoxLayout()
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)
        self._header_layout = QtWidgets.QHBoxLayout()
        self._header_layout.addWidget(self.overlay_header_btn)
        self._header_layout.addStretch()
        self._main_layout.addLayout(self._header_layout)
        self._main_layout.addLayout(self._layout)
        self.setLayout(self._main_layout)
        self.style_widgets()
        self.add_tooltips()

        self.show_cbs = []
        self.color_btns = []
        self.scale_sbs = []
        self.offset_sbs = []

    def style_widgets(self):
        icon_size = QtCore.QSize(17, 17)
        self.clear_btn.setIcon(QtGui.QIcon(os.path.join(icons_path, 'reset_dark.ico')))
        self.clear_btn.setIconSize(icon_size)

        self.add_btn.setIcon(QtGui.QIcon(os.path.join(icons_path, 'open.ico')))
        self.add_btn.setIconSize(icon_size)

        self.delete_btn.setIcon(QtGui.QIcon(os.path.join(icons_path, 'delete.png')))
        self.delete_btn.setIconSize(QtCore.QSize(12, 14))

        self.move_up_btn.setIcon(QtGui.QIcon(os.path.join(icons_path, 'arrow_up.ico')))
        self.move_up_btn.setIconSize(icon_size)

        self.move_down_btn.setIcon(QtGui.QIcon(os.path.join(icons_path, 'arrow_down.ico')))
        self.move_down_btn.setIconSize(icon_size)

        def modify_btn_to_icon_size(btn):
            button_height = 25
            button_width = 25
            btn.setFixedSize(button_width, button_height)

        modify_btn_to_icon_size(self.add_btn)
        modify_btn_to_icon_size(self.delete_btn)
        modify_btn_to_icon_size(self.clear_btn)
        modify_btn_to_icon_size(self.move_up_btn)
        modify_btn_to_icon_size(self.move_down_btn)

        step_txt_width = 70
        self.scale_step_msb.setFixedWidth(step_txt_width)
        self.offset_step_msb.setFixedWidth(step_txt_width)
        self.waterfall_separation_msb.setFixedWidth(step_txt_width)

        self.scale_step_msb.setMaximum(10.0)
        self.scale_step_msb.setMinimum(0.01)
        self.scale_step_msb.setValue(0.01)

        self.offset_step_msb.setMaximum(100000.0)
        self.offset_step_msb.setMinimum(0.01)
        self.offset_step_msb.setValue(100.0)

        self.waterfall_separation_msb.setMaximum(100000.0)
        self.waterfall_separation_msb.setMinimum(0.01)
        self.waterfall_separation_msb.setValue(100.0)

        self.set_as_bkg_btn.setStyleSheet('font-size: 11px')
        self.waterfall_btn.setFixedWidth(step_txt_width)
        self.waterfall_reset_btn.setFixedWidth(step_txt_width)
        self.set_as_bkg_btn.setFixedWidth(step_txt_width)

        self.overlay_header_btn.setStyleSheet("border-radius: 0px")

    def add_tooltips(self):
        self.add_btn.setToolTip('Loads Overlay(s) from file(s)')
        self.delete_btn.setToolTip('Removes currently selected overlay')
        self.clear_btn.setToolTip('Removes all overlays')
        self.set_as_bkg_btn.setToolTip('Set selected overlay as background')
        self.waterfall_reset_btn.setToolTip('Reset waterfall separation')
        self.waterfall_btn.setToolTip('Apply waterfall separation')

    def add_overlay(self, name, color):
        current_rows = self.overlay_tw.rowCount()
        self.overlay_tw.setRowCount(current_rows + 1)
        self.overlay_tw.blockSignals(True)

        show_cb = QtWidgets.QCheckBox()
        show_cb.setChecked(True)
        show_cb.stateChanged.connect(partial(self.show_cb_changed, show_cb))
        show_cb.setStyleSheet("background-color: transparent")
        self.overlay_tw.setCellWidget(current_rows, 0, show_cb)
        self.show_cbs.append(show_cb)

        color_button = FlatButton()
        color_button.setStyleSheet("background-color: " + color)
        color_button.clicked.connect(partial(self.color_btn_click, color_button))
        self.overlay_tw.setCellWidget(current_rows, 1, color_button)
        self.color_btns.append(color_button)

        name_item = QtWidgets.QTableWidgetItem(name)
        name_item.setFlags(name_item.flags() & ~QtCore.Qt.ItemIsEditable)
        self.overlay_tw.setItem(current_rows, 2, QtWidgets.QTableWidgetItem(name))

        scale_sb = DoubleSpinBoxAlignRight()
        scale_sb.setMinimum(-9999999)
        scale_sb.setMaximum(9999999)
        scale_sb.setValue(1)
        scale_sb.setSingleStep(self.scale_step_msb.value())
        scale_sb.valueChanged.connect(partial(self.scale_sb_callback, scale_sb))
        self.overlay_tw.setCellWidget(current_rows, 3, scale_sb)
        self.scale_sbs.append(scale_sb)

        offset_sb = DoubleSpinBoxAlignRight()
        offset_sb.setMinimum(-9999999)
        offset_sb.setMaximum(9999999)
        offset_sb.setValue(0)
        offset_sb.setSingleStep(self.offset_step_msb.value())
        offset_sb.valueChanged.connect(partial(self.offset_sb_callback, offset_sb))
        self.overlay_tw.setCellWidget(current_rows, 4, offset_sb)
        self.offset_sbs.append(offset_sb)

        self.overlay_tw.setColumnWidth(0, 20)
        self.overlay_tw.setColumnWidth(1, 25)
        self.overlay_tw.setRowHeight(current_rows, 25)

        self.overlay_tw.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        self.overlay_tw.horizontalHeader().setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)

        self.select_overlay(current_rows)
        self.overlay_tw.blockSignals(False)

    def select_overlay(self, ind):
        if self.overlay_tw.rowCount() > 0:
            self.overlay_tw.selectRow(ind)

    def get_selected_overlay_row(self):
        selected = self.overlay_tw.selectionModel().selectedRows()
        try:
            row = selected[0].row()
        except IndexError:
            row = -1
        return row

    def remove_overlay(self, ind):
        self.overlay_tw.blockSignals(True)
        self.overlay_tw.removeRow(ind)
        self.overlay_tw.blockSignals(False)
        del self.show_cbs[ind]
        del self.color_btns[ind]
        del self.offset_sbs[ind]
        del self.scale_sbs[ind]

        if self.overlay_tw.rowCount() > ind:
            self.select_overlay(ind)
        else:
            self.select_overlay(self.overlay_tw.rowCount() - 1)

    def move_overlay_up(self, ind):
        new_ind = ind - 1
        self.overlay_tw.blockSignals(True)
        self.overlay_tw.insertRow(new_ind)
        self.overlay_tw.setCellWidget(new_ind, 0, self.overlay_tw.cellWidget(ind + 1, 0))
        self.overlay_tw.setCellWidget(new_ind, 1, self.overlay_tw.cellWidget(ind + 1, 1))
        self.overlay_tw.setCellWidget(new_ind, 3, self.overlay_tw.cellWidget(ind + 1, 3))
        self.overlay_tw.setCellWidget(new_ind, 4, self.overlay_tw.cellWidget(ind + 1, 4))
        self.overlay_tw.setItem(new_ind, 2, self.overlay_tw.takeItem(ind + 1, 2))
        self.overlay_tw.setCurrentCell(new_ind, 2)
        self.overlay_tw.removeRow(ind + 1)
        self.overlay_tw.setRowHeight(new_ind, 25)
        self.overlay_tw.blockSignals(False)

        self.color_btns.insert(new_ind, self.color_btns.pop(ind))
        self.show_cbs.insert(new_ind, self.show_cbs.pop(ind))
        self.scale_sbs.insert(new_ind, self.scale_sbs.pop(ind))
        self.offset_sbs.insert(new_ind, self.offset_sbs.pop(ind))

    def move_overlay_down(self, ind):
        new_ind = ind + 2
        self.overlay_tw.blockSignals(True)
        self.overlay_tw.insertRow(new_ind)
        self.overlay_tw.setCellWidget(new_ind, 0, self.overlay_tw.cellWidget(ind, 0))
        self.overlay_tw.setCellWidget(new_ind, 1, self.overlay_tw.cellWidget(ind, 1))
        self.overlay_tw.setCellWidget(new_ind, 3, self.overlay_tw.cellWidget(ind, 3))
        self.overlay_tw.setCellWidget(new_ind, 4, self.overlay_tw.cellWidget(ind, 4))
        self.overlay_tw.setItem(new_ind, 2, self.overlay_tw.takeItem(ind, 2))
        self.overlay_tw.setCurrentCell(new_ind, 2)
        self.overlay_tw.setRowHeight(new_ind, 25)
        self.overlay_tw.removeRow(ind)
        self.overlay_tw.blockSignals(False)

        self.color_btns.insert(ind + 1, self.color_btns.pop(ind))
        self.show_cbs.insert(ind + 1, self.show_cbs.pop(ind))
        self.scale_sbs.insert(ind + 1, self.scale_sbs.pop(ind))
        self.offset_sbs.insert(ind + 1, self.offset_sbs.pop(ind))

    def color_btn_click(self, button):
        self.color_btn_clicked.emit(self.color_btns.index(button), button)

    def show_cb_changed(self, checkbox):
        self.show_cb_state_changed.emit(self.show_cbs.index(checkbox), checkbox.isChecked())

    def show_cb_set_checked(self, ind, state):
        checkbox = self.show_cbs[ind]
        checkbox.setChecked(state)

    def show_cb_is_checked(self, ind):
        checkbox = self.show_cbs[ind]
        return checkbox.isChecked()

    def label_editingFinished(self, row, col):
        label_item = self.overlay_tw.item(row, col)
        self.name_changed.emit(row, str(label_item.text()))

    def scale_sb_callback(self, scale_sb):
        self.scale_sb_value_changed.emit(self.scale_sbs.index(scale_sb), scale_sb.value())

    def offset_sb_callback(self, offset_sb):
        self.offset_sb_value_changed.emit(self.offset_sbs.index(offset_sb), offset_sb.value())
