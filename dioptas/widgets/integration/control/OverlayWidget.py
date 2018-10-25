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

from functools import partial

from qtpy import QtWidgets, QtCore

from ...CustomWidgets import LabelAlignRight, FlatButton, CheckableFlatButton, DoubleSpinBoxAlignRight, \
    VerticalSpacerItem, HorizontalSpacerItem, ListTableWidget, DoubleMultiplySpinBoxAlignRight
from ...CustomWidgets import NoRectDelegate


class OverlayWidget(QtWidgets.QWidget):
    color_btn_clicked = QtCore.Signal(int, QtWidgets.QWidget)
    show_cb_state_changed = QtCore.Signal(int, bool)
    name_changed = QtCore.Signal(int, str)

    def __init__(self):
        super(OverlayWidget, self).__init__()

        self._layout = QtWidgets.QVBoxLayout()

        self.overlay_lbl = QtWidgets.QLabel('Overlays')
        self._layout.addWidget(self.overlay_lbl)

        self.button_widget = QtWidgets.QWidget(self)
        self.button_widget.setObjectName('overlay_control_widget')
        self._button_layout = QtWidgets.QHBoxLayout(self.button_widget)
        self._button_layout.setContentsMargins(0, 0, 0, 0)
        self._button_layout.setSpacing(6)

        self.add_btn = FlatButton('Add')
        self.delete_btn = FlatButton('Delete')
        self.clear_btn = FlatButton('Clear')
        self.move_up_btn = FlatButton('Move Up')
        self.move_down_btn = FlatButton('Move Down')

        self._button_layout.addWidget(self.add_btn)
        self._button_layout.addWidget(self.delete_btn)
        self._button_layout.addWidget(self.clear_btn)
        self._button_layout.addWidget(self.move_up_btn)
        self._button_layout.addWidget(self.move_down_btn)
        self._button_layout.addSpacerItem(HorizontalSpacerItem())
        self._layout.addWidget(self.button_widget)

        self.parameter_widget = QtWidgets.QWidget(self)
        self._parameter_layout = QtWidgets.QGridLayout(self.parameter_widget)
        self._parameter_layout.setSpacing(6)

        self.scale_sb = DoubleSpinBoxAlignRight()
        self.offset_sb = DoubleSpinBoxAlignRight()
        self.scale_step_msb = DoubleMultiplySpinBoxAlignRight()
        self.offset_step_msb = DoubleMultiplySpinBoxAlignRight()
        self.waterfall_separation_msb = DoubleMultiplySpinBoxAlignRight()
        self.waterfall_btn = FlatButton('Waterfall')
        self.waterfall_reset_btn = FlatButton('Reset')
        self.set_as_bkg_btn = CheckableFlatButton('Set as Background')

        self._parameter_layout.addWidget(QtWidgets.QLabel('Step'), 0, 2)
        self._parameter_layout.addWidget(LabelAlignRight('Scale:'), 1, 0)
        self._parameter_layout.addWidget(LabelAlignRight('Offset:'), 2, 0)

        self._parameter_layout.addWidget(self.scale_sb, 1, 1)
        self._parameter_layout.addWidget(self.scale_step_msb, 1, 2)
        self._parameter_layout.addWidget(self.offset_sb, 2, 1)
        self._parameter_layout.addWidget(self.offset_step_msb, 2, 2)

        self._parameter_layout.addItem(VerticalSpacerItem(), 3, 0, 1, 3)

        self._waterfall_layout = QtWidgets.QHBoxLayout()
        self._waterfall_layout.addWidget(self.waterfall_btn)
        self._waterfall_layout.addWidget(self.waterfall_separation_msb)
        self._waterfall_layout.addWidget(self.waterfall_reset_btn)
        self._parameter_layout.addLayout(self._waterfall_layout, 4, 0, 1, 3)
        self._parameter_layout.addItem(VerticalSpacerItem(), 5, 0, 1, 3)

        self._background_layout = QtWidgets.QHBoxLayout()
        self._background_layout.addSpacerItem(HorizontalSpacerItem())
        self._background_layout.addWidget(self.set_as_bkg_btn)
        self._parameter_layout.addLayout(self._background_layout, 6, 0, 1, 3)
        self.parameter_widget.setLayout(self._parameter_layout)

        self._body_layout = QtWidgets.QHBoxLayout()
        self.overlay_tw = ListTableWidget(columns=3)
        self._body_layout.addWidget(self.overlay_tw, 10)
        self._body_layout.addWidget(self.parameter_widget, 0)

        self._layout.addLayout(self._body_layout)

        self.setLayout(self._layout)
        self.style_widgets()

        self.overlay_tw.cellChanged.connect(self.label_editingFinished)
        self.overlay_tw.setItemDelegate(NoRectDelegate())
        self.show_cbs = []
        self.color_btns = []

    def style_widgets(self):
        self.overlay_lbl.setVisible(False)
        step_txt_width = 70
        self.scale_step_msb.setMaximumWidth(step_txt_width)
        self.scale_step_msb.setMinimumWidth(step_txt_width)
        self.offset_step_msb.setMaximumWidth(step_txt_width)
        self.waterfall_separation_msb.setMaximumWidth(step_txt_width)

        self.scale_sb.setMinimum(-9999999)
        self.scale_sb.setMaximum(9999999)
        self.scale_sb.setValue(1)
        self.scale_sb.setSingleStep(0.01)

        self.offset_sb.setMaximum(999999998)
        self.offset_sb.setMinimum(-99999999)
        self.offset_sb.setSingleStep(100)

        self.scale_step_msb.setMaximum(10.0)
        self.scale_step_msb.setMinimum(0.01)
        self.scale_step_msb.setValue(0.01)

        self.offset_step_msb.setMaximum(100000.0)
        self.offset_step_msb.setMinimum(0.01)
        self.offset_step_msb.setValue(100.0)

        self.waterfall_separation_msb.setMaximum(100000.0)
        self.waterfall_separation_msb.setMinimum(0.01)
        self.waterfall_separation_msb.setValue(100.0)

        self.setStyleSheet("""
            #overlay_control_widget QPushButton {
                min-width: 95;
            }
            QSpinBox {
                min-width: 110;
                max-width: 110;
            }
        """)

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

        self.overlay_tw.setColumnWidth(0, 20)
        self.overlay_tw.setColumnWidth(1, 25)
        self.overlay_tw.setRowHeight(current_rows, 25)
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
        self.overlay_tw.setItem(new_ind, 2, self.overlay_tw.takeItem(ind + 1, 2))
        self.overlay_tw.setCurrentCell(new_ind, 2)
        self.overlay_tw.removeRow(ind + 1)
        self.overlay_tw.setRowHeight(new_ind, 25)
        self.overlay_tw.blockSignals(False)

        self.color_btns.insert(new_ind, self.color_btns.pop(ind))
        self.show_cbs.insert(new_ind, self.show_cbs.pop(ind))

    def move_overlay_down(self, ind):
        new_ind = ind + 2
        self.overlay_tw.blockSignals(True)
        self.overlay_tw.insertRow(new_ind)
        self.overlay_tw.setCellWidget(new_ind, 0, self.overlay_tw.cellWidget(ind, 0))
        self.overlay_tw.setCellWidget(new_ind, 1, self.overlay_tw.cellWidget(ind, 1))
        self.overlay_tw.setItem(new_ind, 2, self.overlay_tw.takeItem(ind, 2))
        self.overlay_tw.setCurrentCell(new_ind, 2)
        self.overlay_tw.setRowHeight(new_ind, 25)
        self.overlay_tw.removeRow(ind)
        self.overlay_tw.blockSignals(False)

        self.color_btns.insert(ind + 1, self.color_btns.pop(ind))
        self.show_cbs.insert(ind + 1, self.show_cbs.pop(ind))

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
