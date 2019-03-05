# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
# Principal author: Clemens Prescher (clemens.prescher@gmail.com)
# Copyright (C) 2014-2019 GSECARS, University of Chicago, USA
# Copyright (C) 2015-2018 Institute for Geology and Mineralogy, University of Cologne, Germany
# Copyright (C) 2019 DESY, Hamburg, Germany
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

from ...CustomWidgets import FlatButton, DoubleSpinBoxAlignRight, VerticalSpacerItem, NoRectDelegate, \
    ListTableWidget, HorizontalLine, DoubleMultiplySpinBoxAlignRight

from .... import icons_path


class PhaseWidget(QtWidgets.QWidget):
    color_btn_clicked = QtCore.Signal(int, QtWidgets.QWidget)
    show_cb_state_changed = QtCore.Signal(int, bool)

    pressure_sb_value_changed = QtCore.Signal(int, float)
    temperature_sb_value_changed = QtCore.Signal(int, float)

    def __init__(self):
        super(PhaseWidget, self).__init__()

        self._layout = QtWidgets.QHBoxLayout()
        self._layout.setContentsMargins(5, 5, 5, 5)

        self.add_btn = FlatButton()
        self.edit_btn = FlatButton()
        self.delete_btn = FlatButton()
        self.clear_btn = FlatButton()
        self.save_list_btn = FlatButton('Save List')
        self.load_list_btn = FlatButton('Load List')

        self.button_widget = QtWidgets.QWidget(self)
        self.button_widget.setObjectName('phase_control_button_widget')
        self._button_layout = QtWidgets.QVBoxLayout()
        self._button_layout.setContentsMargins(0, 0, 0, 0)
        self._button_layout.setSpacing(6)

        self._button_layout.addWidget(self.add_btn)
        self._button_layout.addWidget(self.edit_btn)
        self._button_layout.addWidget(HorizontalLine())
        self._button_layout.addWidget(HorizontalLine())
        self._button_layout.addWidget(self.delete_btn)
        self._button_layout.addWidget(HorizontalLine())
        self._button_layout.addWidget(HorizontalLine())
        self._button_layout.addWidget(self.clear_btn)
        self._button_layout.addSpacerItem(VerticalSpacerItem())
        self.button_widget.setLayout(self._button_layout)
        self._layout.addWidget(self.button_widget)

        self.parameter_widget = QtWidgets.QWidget()

        self._parameter_layout = QtWidgets.QVBoxLayout()
        self._parameter_layout.setContentsMargins(0, 0, 0, 0)
        self._parameter_layout.setSpacing(4)

        self.pressure_step_msb = DoubleMultiplySpinBoxAlignRight()
        self.temperature_step_msb = DoubleMultiplySpinBoxAlignRight()
        self.apply_to_all_cb = QtWidgets.QCheckBox('apply to all')

        self._parameter_layout.addWidget(QtWidgets.QLabel('P step'))
        self._parameter_layout.addWidget(self.pressure_step_msb)
        self._parameter_layout.addWidget(QtWidgets.QLabel('T Step'))
        self._parameter_layout.addWidget(self.temperature_step_msb)
        self._parameter_layout.addWidget(self.apply_to_all_cb)
        self._parameter_layout.addWidget(HorizontalLine())
        self._parameter_layout.addItem(VerticalSpacerItem())
        self._parameter_layout.addWidget(self.save_list_btn)
        self._parameter_layout.addWidget(self.load_list_btn)

        self.parameter_widget.setLayout(self._parameter_layout)

        self._body_layout = QtWidgets.QHBoxLayout()

        self.phase_tw = ListTableWidget(columns=5)
        self.phase_tw.setObjectName('phase_table_widget')
        self.phase_tw.setHorizontalHeaderLabels(['', '', 'Name', 'P (GPa)', 'T (K)'])
        self.phase_tw.horizontalHeader().setVisible(True)
        self.phase_tw.horizontalHeader().setStretchLastSection(False)
        self.phase_tw.setColumnWidth(0, 20)
        self.phase_tw.setColumnWidth(1, 25)
        self.phase_tw.horizontalHeader().setResizeMode(2, QtWidgets.QHeaderView.Stretch)
        self.phase_tw.horizontalHeader().setResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        self.phase_tw.horizontalHeader().setResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)
        self.phase_tw.setItemDelegate(NoRectDelegate())
        self._body_layout.addWidget(self.phase_tw, 10)
        self._body_layout.addWidget(self.parameter_widget, 0)

        self._layout.addLayout(self._body_layout)

        # label for alternative view:
        self.phase_header_btn = FlatButton('Phase')
        self.phase_header_btn.setEnabled(False)
        self.phase_header_btn.setVisible(False)
        self._main_layout = QtWidgets.QVBoxLayout()
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.addWidget(self.phase_header_btn)
        self._main_layout.addLayout(self._layout)
        self.setLayout(self._main_layout)
        self.style_widgets()
        self.add_tooltips()

        self.phase_show_cbs = []
        self.phase_color_btns = []
        self.pressure_sbs = []
        self.temperature_sbs = []

        self.show_parameter_in_pattern = True

    def style_widgets(self):
        icon_size = QtCore.QSize(17, 17)

        self.add_btn.setIcon(QtGui.QIcon(os.path.join(icons_path, 'open.ico')))
        self.add_btn.setIconSize(icon_size)

        self.edit_btn.setIcon(QtGui.QIcon(os.path.join(icons_path, 'edit.png')))
        self.edit_btn.setIconSize(QtCore.QSize(14, 14))

        self.delete_btn.setIcon(QtGui.QIcon(os.path.join(icons_path, 'delete.png')))
        self.delete_btn.setIconSize(QtCore.QSize(12, 14))

        self.clear_btn.setIcon(QtGui.QIcon(os.path.join(icons_path, 'reset_dark.ico')))
        self.clear_btn.setIconSize(icon_size)

        def modify_btn_to_icon_size(btn):
            button_height = 25
            button_width = 25
            btn.setMinimumHeight(button_height)
            btn.setMaximumHeight(button_height)
            btn.setMinimumWidth(button_width)
            btn.setMaximumWidth(button_width)

        modify_btn_to_icon_size(self.add_btn)
        modify_btn_to_icon_size(self.delete_btn)
        modify_btn_to_icon_size(self.clear_btn)
        modify_btn_to_icon_size(self.edit_btn)

        self.phase_tw.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.MinimumExpanding)
        self.parameter_widget.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)

        step_txt_width = 70

        self.pressure_step_msb.setMinimumWidth(step_txt_width)
        self.pressure_step_msb.setMaximumWidth(step_txt_width)
        self.temperature_step_msb.setMinimumWidth(step_txt_width)
        self.temperature_step_msb.setMaximumWidth(step_txt_width)

        self.temperature_step_msb.setMaximum(1000.0)
        self.temperature_step_msb.setMinimum(1.0)
        self.temperature_step_msb.setValue(100.0)

        self.pressure_step_msb.setValue(1)

        self.phase_header_btn.setStyleSheet("border-radius: 0px")

        self.apply_to_all_cb.setChecked(True)

    def add_tooltips(self):
        self.add_btn.setToolTip('Loads Phase(s) from jcpds or cif file(s)')
        self.edit_btn.setToolTip('Edit selected Phase')
        self.delete_btn.setToolTip('Removes currently selected phase')
        self.clear_btn.setToolTip('Removes all phases')
        self.apply_to_all_cb.setToolTip('Whether individual changes in P or T\nare applied to all other phases')
        self.pressure_step_msb.setToolTip('Sets the step for the pressure spinboxes')
        self.temperature_step_msb.setToolTip('Sets the step for the temperature spinboxes')

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

        pressure_sb = DoubleSpinBoxAlignRight()
        pressure_sb.setMinimum(-9999999)
        pressure_sb.setMaximum(9999999)
        pressure_sb.setValue(0)
        pressure_sb.setSingleStep(self.pressure_step_msb.value())
        pressure_sb.valueChanged.connect(partial(self.pressure_sb_callback, pressure_sb))
        self.phase_tw.setCellWidget(current_rows, 3, pressure_sb)
        self.pressure_sbs.append(pressure_sb)

        temperature_sb = DoubleSpinBoxAlignRight()
        temperature_sb.setMinimum(-9999999)
        temperature_sb.setMaximum(9999999)
        temperature_sb.setValue(300)
        temperature_sb.setSingleStep(self.temperature_step_msb.value())
        temperature_sb.valueChanged.connect(partial(self.temperature_sb_callback, temperature_sb))
        self.phase_tw.setCellWidget(current_rows, 4, temperature_sb)
        self.temperature_sbs.append(temperature_sb)

        self.phase_tw.setColumnWidth(0, 20)
        self.phase_tw.setColumnWidth(1, 25)
        self.phase_tw.setRowHeight(current_rows, 25)
        self.select_phase(current_rows)
        self.phase_tw.blockSignals(False)

        self.phase_tw.horizontalHeader().setResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        self.phase_tw.horizontalHeader().setResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)

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
        del self.temperature_sbs[ind]
        del self.pressure_sbs[ind]

        if self.phase_tw.rowCount() > ind:
            self.select_phase(ind)
        else:
            self.select_phase(self.phase_tw.rowCount() - 1)

    def rename_phase(self, ind, name):
        name_item = self.phase_tw.item(ind, 2)
        name_item.setText(name)

    def set_phase_temperature(self, ind, temperature):
        pass
        self.temperature_sbs[ind].blockSignals(True)
        self.temperature_sbs[ind].setValue(temperature)
        self.temperature_sbs[ind].blockSignals(False)

    def get_phase_temperature(self, ind):
        return self.temperature_sbs[ind].value()

    def set_phase_pressure(self, ind, pressure):
        self.pressure_sbs[ind].blockSignals(True)
        self.pressure_sbs[ind].setValue(pressure)
        self.pressure_sbs[ind].blockSignals(False)

    def get_phase_pressure(self, ind):
        return self.pressure_sbs[ind].value()

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

    def pressure_sb_callback(self, pressure_sb):
        self.pressure_sb_value_changed.emit(self.pressure_sbs.index(pressure_sb), pressure_sb.value())

    def temperature_sb_callback(self, temperature_sb):
        self.temperature_sb_value_changed.emit(self.temperature_sbs.index(temperature_sb), temperature_sb.value())
