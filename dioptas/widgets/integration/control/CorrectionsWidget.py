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

from qtpy import QtWidgets, QtCore

from ...CustomWidgets import NumberTextField, LabelAlignRight, CheckableFlatButton, VerticalSpacerItem, \
    HorizontalSpacerItem, ListTableWidget


class CorrectionsWidget(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super(CorrectionsWidget, self).__init__(*args, **kwargs)

        self._layout = QtWidgets.QVBoxLayout()

        self.create_cbn_correction_widgets()
        self.create_cbn_correction_layout()

        self.create_oiadac_widgets()
        self.create_oiadac_layout()

        vert_layout_1 = QtWidgets.QHBoxLayout()
        vert_layout_1.addWidget(self.cbn_seat_gb)
        vert_layout_1.addSpacerItem(HorizontalSpacerItem())
        self._layout.addLayout(vert_layout_1)
        self._layout.addWidget(self.oiadac_gb)
        self._layout.addSpacerItem(VerticalSpacerItem())

        self.setLayout(self._layout)
        self.style_widgets()

    def create_cbn_correction_widgets(self):
        self.cbn_seat_gb = QtWidgets.QGroupBox('cBN Seat Correction')

        self.cbn_seat_plot_btn = CheckableFlatButton('Plot')

        self.cbn_param_tw = ListTableWidget()
        self.cbn_param_tw.setColumnCount(3)

        self.cbn_param_tw.horizontalHeader().setResizeMode(1, QtWidgets.QHeaderView.Stretch)
        self.cbn_param_tw.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)

        cbn_parameters = [
            ['Anvil thickness', 2.3, 'mm'],
            ['Seat thickness', 5.3, 'mm'],
            ['Inner seat radius', 0.4, 'mm'],
            ['Outer seat radius', 1.95, 'mm'],
            ['Cell tilt', 0.0, u'°'],
            ['Cell tilt rotation', 0, u'°'],
            ['Center offset', 0, 'mm'],
            ['Center offset rotation', 0, u'°'],
            ['Anvil absorption length', 13.7, 'mm'],
            ['Seat absorption length', 12, 'mm'],
        ]

        for cbn_parameter in cbn_parameters:
            self.add_cbn_param_to_tw(*cbn_parameter)

    def add_cbn_param_to_tw(self, name, value, unit):
        self.cbn_param_tw.blockSignals(True)
        new_row_ind = int(self.cbn_param_tw.rowCount())
        self.cbn_param_tw.setRowCount(new_row_ind + 1)

        name_item = QtWidgets.QTableWidgetItem(name+':')
        name_item.setFlags(name_item.flags() & ~QtCore.Qt.ItemIsEditable)
        name_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.cbn_param_tw.setItem(new_row_ind, 0, name_item)

        value_item = NumberTextField('{:g}'.format(value))
        self.cbn_param_tw.setCellWidget(new_row_ind, 1, value_item)

        unit_item = QtWidgets.QTableWidgetItem(unit)
        unit_item.setFlags(name_item.flags() & ~QtCore.Qt.ItemIsEditable)
        unit_item.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.cbn_param_tw.setItem(new_row_ind, 2, unit_item)

        self.cbn_param_tw.resizeColumnToContents(0)
        self.cbn_param_tw.resizeColumnToContents(2)

        self.cbn_param_tw.blockSignals(False)

    def create_cbn_correction_layout(self):
        self._cbn_seat_layout = QtWidgets.QHBoxLayout()
        self._cbn_seat_layout.setSpacing(6)

        self._cbn_seat_layout.addWidget(self.cbn_param_tw)

        self._cbn_seat_right_layout = QtWidgets.QVBoxLayout()
        self._cbn_seat_right_layout.addWidget(self.cbn_seat_plot_btn)
        self._cbn_seat_right_layout.addSpacerItem(VerticalSpacerItem())
        self._cbn_seat_layout.addLayout(self._cbn_seat_right_layout)

        self.cbn_seat_gb.setLayout(self._cbn_seat_layout)

    def create_oiadac_widgets(self):
        self.oiadac_gb = QtWidgets.QGroupBox('Oblique Incidence Angle Detector Absorption Correction')
        self.detector_thickness_txt = NumberTextField('40')
        self.detector_absorption_length_txt = NumberTextField('465.5')
        self.oiadac_plot_btn = CheckableFlatButton('Plot')

    def create_oiadac_layout(self):
        self._oiadac_layout = QtWidgets.QHBoxLayout()
        self._oiadac_layout.addWidget(LabelAlignRight('Det. Thickness:'))
        self._oiadac_layout.addWidget(self.detector_thickness_txt)
        self._oiadac_layout.addWidget(QtWidgets.QLabel('mm'))
        self._oiadac_layout.addSpacing(10)
        self._oiadac_layout.addWidget(LabelAlignRight('Abs. Length:'))
        self._oiadac_layout.addWidget(self.detector_absorption_length_txt)
        self._oiadac_layout.addWidget(QtWidgets.QLabel('um'))
        self._oiadac_layout.addWidget(self.oiadac_plot_btn)
        self._oiadac_layout.addSpacerItem(HorizontalSpacerItem())

        self.oiadac_gb.setLayout(self._oiadac_layout)

    def style_widgets(self):
        self.cbn_seat_gb.setCheckable(True)
        self.cbn_seat_gb.setChecked(False)

        self.cbn_param_tw.setMaximumWidth(260)
        self.cbn_param_tw.setMinimumWidth(260)

        self.setStyleSheet("""
                    QLineEdit {
                        min-width: 50 px;
                        min-height: 26 px;
                        max-height: 26 px;
                    }
                    
                    QPushButton {
                        min-width: 50 px;
                        max-width: 60 px;
                        min-height: 30 px;
                        max-width: 30 px;
                    }
               """)

        self.oiadac_gb.setCheckable(True)
        self.oiadac_gb.setChecked(False)
        self.detector_thickness_txt.setMinimumWidth(60)
        self.detector_thickness_txt.setMaximumWidth(60)
        self.detector_absorption_length_txt.setMinimumWidth(60)
        self.detector_absorption_length_txt.setMaximumWidth(60)
