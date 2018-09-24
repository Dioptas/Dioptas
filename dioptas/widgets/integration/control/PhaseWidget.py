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

from ...CustomWidgets import FlatButton, DoubleSpinBoxAlignRight, VerticalSpacerItem, NoRectDelegate, \
    HorizontalSpacerItem, ListTableWidget, VerticalLine, DoubleMultiplySpinBoxAlignRight


class PhaseWidget(QtWidgets.QWidget):

    color_btn_clicked = QtCore.Signal(int, QtWidgets.QWidget)
    show_cb_state_changed = QtCore.Signal(int, bool)

    def __init__(self):
        super(PhaseWidget, self).__init__()

        self._layout = QtWidgets.QVBoxLayout()

        self.button_widget = QtWidgets.QWidget(self)
        self.button_widget.setObjectName('phase_control_button_widget')
        self._button_layout = QtWidgets.QHBoxLayout()
        self._button_layout.setContentsMargins(0, 0, 0, 0)
        self._button_layout.setSpacing(6)

        self.add_btn = FlatButton('Add')
        self.edit_btn = FlatButton('Edit')
        self.delete_btn = FlatButton('Delete')
        self.clear_btn = FlatButton('Clear')
        self.save_list_btn = FlatButton('Save List')
        self.load_list_btn = FlatButton('Load List')

        self._button_layout.addWidget(self.add_btn)
        self._button_layout.addWidget(self.edit_btn)
        self._button_layout.addWidget(self.delete_btn)
        self._button_layout.addWidget(self.clear_btn)
        self._button_layout.addWidget(VerticalLine())
        self._button_layout.addSpacerItem(HorizontalSpacerItem())
        self._button_layout.addWidget(VerticalLine())
        self._button_layout.addWidget(self.save_list_btn)
        self._button_layout.addWidget(self.load_list_btn)
        self.button_widget.setLayout(self._button_layout)
        self._layout.addWidget(self.button_widget)

        self.parameter_widget = QtWidgets.QWidget()

        self._parameter_layout = QtWidgets.QGridLayout()
        self.pressure_sb = DoubleSpinBoxAlignRight()
        self.temperature_sb = DoubleSpinBoxAlignRight()
        self.pressure_step_msb = DoubleMultiplySpinBoxAlignRight()
        self.temperature_step_msb = DoubleMultiplySpinBoxAlignRight()
        self.apply_to_all_cb = QtWidgets.QCheckBox('Apply to all phases')
        self.show_in_pattern_cb = QtWidgets.QCheckBox('Show in Pattern')

        self._parameter_layout.addWidget(QtWidgets.QLabel('Parameter'), 0, 1)
        self._parameter_layout.addWidget(QtWidgets.QLabel('Step'), 0, 3)
        self._parameter_layout.addWidget(QtWidgets.QLabel('P:'), 1, 0)
        self._parameter_layout.addWidget(QtWidgets.QLabel('T:'), 2, 0)
        self._parameter_layout.addWidget(QtWidgets.QLabel('GPa'), 1, 2)
        self._parameter_layout.addWidget(QtWidgets.QLabel('K'), 2, 2)

        self._parameter_layout.addWidget(self.pressure_sb, 1, 1)
        self._parameter_layout.addWidget(self.pressure_step_msb, 1, 3)
        self._parameter_layout.addWidget(self.temperature_sb, 2, 1)
        self._parameter_layout.addWidget(self.temperature_step_msb, 2, 3)

        self._parameter_layout.addWidget(self.apply_to_all_cb, 3, 0, 1, 5)
        self._parameter_layout.addWidget(self.show_in_pattern_cb, 4, 0, 1, 5)
        self._parameter_layout.addItem(VerticalSpacerItem(), 5, 0)
        self.parameter_widget.setLayout(self._parameter_layout)

        self._body_layout = QtWidgets.QHBoxLayout()
        self.phase_tw = ListTableWidget(columns=5)
        self._body_layout.addWidget(self.phase_tw, 10)
        self._body_layout.addWidget(self.parameter_widget, 0)

        self._layout.addLayout(self._body_layout)

        self.setLayout(self._layout)
        self.style_widgets()

        self.phase_show_cbs = []
        self.phase_color_btns = []
        self.show_parameter_in_pattern = True
        header_view = QtWidgets.QHeaderView(QtCore.Qt.Horizontal, self.phase_tw)
        self.phase_tw.setHorizontalHeader(header_view)
        header_view.setResizeMode(2, QtWidgets.QHeaderView.Stretch)
        header_view.setResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        header_view.setResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)
        header_view.hide()
        self.phase_tw.setItemDelegate(NoRectDelegate())

    def style_widgets(self):
        self.phase_tw.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.MinimumExpanding)
        self.parameter_widget.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        self.phase_tw.setMinimumHeight(130)

        self.temperature_step_msb.setMaximumWidth(60)
        self.pressure_step_msb.setMaximumWidth(60)
        self.pressure_sb.setMinimumWidth(100)

        self.pressure_sb.setMaximum(9999999)
        self.pressure_sb.setMinimum(-9999999)
        self.pressure_sb.setValue(0)

        self.pressure_step_msb.setMaximum(1000.0)
        self.pressure_step_msb.setMinimum(0.01)
        self.pressure_step_msb.setValue(0.5)

        self.temperature_sb.setMaximum(99999999)
        self.temperature_sb.setMinimum(0)
        self.temperature_sb.setValue(298)

        self.temperature_step_msb.setMaximum(1000.0)
        self.temperature_step_msb.setMinimum(1.0)
        self.temperature_step_msb.setValue(100.0)

        self.setStyleSheet("""
            #phase_control_button_widget QPushButton {
                min-width: 95;
            }
        """)

        self.apply_to_all_cb.setChecked(True)
        self.show_in_pattern_cb.setChecked(True)

    # ###############################################################################################
    # Now comes all the phase tw stuff
    ################################################################################################

    def add_phase(self, name, color):
        current_rows = self.phase_tw.rowCount()
        self.phase_tw.setRowCount(current_rows + 1)
        self.phase_tw.blockSignals(True)

        show_cb = QtWidgets.QCheckBox()
        show_cb.setChecked(True)
        show_cb.stateChanged.connect(partial(self.phase_show_cb_changed, show_cb))
        show_cb.setStyleSheet("background-color: transparent")
        self.phase_tw.setCellWidget(current_rows, 0, show_cb)
        self.phase_show_cbs.append(show_cb)

        color_button = FlatButton()
        color_button.setStyleSheet("background-color: " + color)
        color_button.clicked.connect(partial(self.phase_color_btn_click, color_button))
        self.phase_tw.setCellWidget(current_rows, 1, color_button)
        self.phase_color_btns.append(color_button)

        name_item = QtWidgets.QTableWidgetItem(name)
        name_item.setFlags(name_item.flags() & ~QtCore.Qt.ItemIsEditable)
        name_item.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.phase_tw.setItem(current_rows, 2, name_item)

        pressure_item = QtWidgets.QTableWidgetItem('0 GPa')
        pressure_item.setFlags(pressure_item.flags() & ~QtCore.Qt.ItemIsEditable)
        pressure_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.phase_tw.setItem(current_rows, 3, pressure_item)

        temperature_item = QtWidgets.QTableWidgetItem('298 K')
        temperature_item.setFlags(temperature_item.flags() & ~QtCore.Qt.ItemIsEditable)
        temperature_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.phase_tw.setItem(current_rows, 4, temperature_item)

        self.phase_tw.setColumnWidth(0, 20)
        self.phase_tw.setColumnWidth(1, 25)
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

        if self.phase_tw.rowCount() > ind:
            self.select_phase(ind)
        else:
            self.select_phase(self.phase_tw.rowCount() - 1)

    def rename_phase(self, ind, name):
        name_item = self.phase_tw.item(ind, 2)
        name_item.setText(name)

    def set_phase_temperature(self, ind, T):
        temperature_item = self.phase_tw.item(ind, 4)
        try:
            temperature_item.setText("{0:.2f} K".format(T))
        except ValueError:
            temperature_item.setText("{0} K".format(T))

    def get_phase_temperature(self, ind):
        temperature_item = self.phase_tw.item(ind, 4)
        try:
            temperature = float(str(temperature_item.text()).split()[0])
        except:
            temperature = None
        return temperature

    def set_phase_pressure(self, ind, P):
        pressure_item = self.phase_tw.item(ind, 3)
        try:
            pressure_item.setText("{0:.2f} GPa".format(P))
        except ValueError:
            pressure_item.setText("{0} GPa".format(P))

    def get_phase_pressure(self, ind):
        pressure_item = self.phase_tw.item(ind, 3)
        pressure = float(str(pressure_item.text()).split()[0])
        return pressure

    def phase_color_btn_click(self, button):
        self.color_btn_clicked.emit(self.phase_color_btns.index(button), button)

    def phase_show_cb_changed(self, checkbox):
        self.show_cb_state_changed.emit(self.phase_show_cbs.index(checkbox), checkbox.isChecked())

    def phase_show_cb_set_checked(self, ind, state):
        checkbox = self.phase_show_cbs[ind]
        checkbox.setChecked(state)

    def phase_show_cb_is_checked(self, ind):
        checkbox = self.phase_show_cbs[ind]
        return checkbox.isChecked()
