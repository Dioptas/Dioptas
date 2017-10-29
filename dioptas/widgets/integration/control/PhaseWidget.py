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

from qtpy import QtWidgets

from ...CustomWidgets import FlatButton, DoubleSpinBoxAlignRight, VerticalSpacerItem, HorizontalLine, \
    HorizontalSpacerItem, ListTableWidget, VerticalLine, DoubleMultiplySpinBoxAlignRight


class PhaseWidget(QtWidgets.QWidget):
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
