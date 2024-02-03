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

from qtpy import QtWidgets, QtCore

from ...CustomWidgets import (
    HorizontalSpacerItem,
    MenuTabWidget,
    NumberTextField,
    ListTableWidget,
    CheckableButton,
    CheckableFlatButton,
    VerticalSpacerItem,
)


class CorrectionsWidget(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super(CorrectionsWidget, self).__init__(*args, **kwargs)

        self._layout = QtWidgets.QHBoxLayout()
        self._layout.setContentsMargins(0, 5, 0, 0)

        self.create_cbn_correction_widgets()
        self.create_cbn_correction_layout()

        self.create_oiadac_widgets()
        self.create_oiadac_layout()

        self.create_transfer_widgets()
        self.create_transfer_layout()

        self.setLayout(self._layout)

        self.menu_tab_widget = MenuTabWidget()
        self.menu_tab_widget.add_menu_button("cBN Seat", self.cbn_seat_gb)
        self.menu_tab_widget.add_menu_button("Inc. Abs.", self.oiadac_gb)
        self.menu_tab_widget.add_menu_button("Transfer", self.transfer_gb)
        self.menu_tab_widget.select_tab(0)

        self._layout.addWidget(self.menu_tab_widget)

        self.style_widgets()

    def create_cbn_correction_widgets(self):
        self.cbn_seat_gb = QtWidgets.QGroupBox("cBN Seat Correction")
        self.cbn_seat_plot_btn = CheckableButton("Plot")

        self.cbn_param_tw = ListTableWidget()
        self.cbn_param_tw.setColumnCount(3)

        self.cbn_param_tw.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.Stretch
        )
        self.cbn_param_tw.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)

        cbn_parameters = [
            ["Anvil thickness", 2.3, "mm"],
            ["Seat thickness", 5.3, "mm"],
            ["Inner seat radius", 0.4, "mm"],
            ["Outer seat radius", 1.95, "mm"],
            ["Cell tilt", 0.0, "°"],
            ["Cell tilt rotation", 0, "°"],
            ["Center offset", 0, "mm"],
            ["Center offset rotation", 0, "°"],
            ["Anvil absorption length", 13.7, "mm"],
            ["Seat absorption length", 12, "mm"],
        ]

        for cbn_parameter in cbn_parameters:
            self.add_param_to_tw(self.cbn_param_tw, *cbn_parameter)

    @staticmethod
    def add_param_to_tw(tw, name, value, unit):
        tw.blockSignals(True)
        new_row_ind = int(tw.rowCount())
        tw.setRowCount(new_row_ind + 1)

        name_item = QtWidgets.QTableWidgetItem(name + ":")
        name_item.setFlags(name_item.flags() & ~QtCore.Qt.ItemIsEditable)
        name_item.setTextAlignment(int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter))
        tw.setItem(new_row_ind, 0, name_item)

        value_item = NumberTextField("{:g}".format(value))
        tw.setCellWidget(new_row_ind, 1, value_item)

        unit_item = QtWidgets.QTableWidgetItem(unit)
        unit_item.setFlags(name_item.flags() & ~QtCore.Qt.ItemIsEditable)
        unit_item.setTextAlignment(int(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter))
        tw.setItem(new_row_ind, 2, unit_item)

        tw.resizeColumnToContents(0)
        tw.resizeColumnToContents(2)

        tw.blockSignals(False)

    def create_cbn_correction_layout(self):
        self._cbn_seat_layout = QtWidgets.QHBoxLayout()
        self._cbn_seat_layout.setSpacing(5)

        self._cbn_seat_layout.addWidget(self.cbn_param_tw)

        self._cbn_seat_right_layout = QtWidgets.QVBoxLayout()
        self._cbn_seat_right_layout.addWidget(self.cbn_seat_plot_btn)
        self._cbn_seat_right_layout.addStretch()
        self._cbn_seat_layout.addLayout(self._cbn_seat_right_layout)

        self.cbn_seat_gb.setLayout(self._cbn_seat_layout)

    def create_oiadac_widgets(self):
        self.oiadac_gb = QtWidgets.QGroupBox("Detector Incidence Absorption Correction")

        self.oiadac_param_tw = ListTableWidget()
        self.oiadac_param_tw.setColumnCount(3)

        self.oiadac_param_tw.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.Stretch
        )
        self.oiadac_param_tw.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)

        self.detector_thickness_txt = NumberTextField("40")
        self.detector_absorption_length_txt = NumberTextField("465.5")

        oiadac_parameters = [
            ["Detector thickness", 40, "mm"],
            ["Detector absorption length", 465.5, "um"],
        ]

        for param in oiadac_parameters:
            self.add_param_to_tw(self.oiadac_param_tw, *param)

        self.oiadac_plot_btn = CheckableButton("Plot")

    def create_oiadac_layout(self):
        self._oiadac_layout = QtWidgets.QHBoxLayout()
        self._oiadac_layout.setSpacing(5)

        self._oiadac_layout.addWidget(self.oiadac_param_tw)

        self._oiadac_right_layout = QtWidgets.QVBoxLayout()
        self._oiadac_right_layout.addWidget(self.oiadac_plot_btn)
        self._oiadac_right_layout.addStretch()
        self._oiadac_layout.addLayout(self._oiadac_right_layout)

        self.oiadac_gb.setLayout(self._oiadac_layout)

    def create_transfer_widgets(self):
        self.transfer_gb = QtWidgets.QGroupBox("Transfer Correction")
        self.transfer_load_original_btn = QtWidgets.QPushButton("Load Original")
        self.transfer_load_response_btn = QtWidgets.QPushButton("Load Response")
        self.transfer_original_filename_lbl = QtWidgets.QLabel("None")
        self.transfer_response_filename_lbl = QtWidgets.QLabel("None")
        self.transfer_plot_btn = CheckableButton("Plot")

    def create_transfer_layout(self):
        self._transfer_layout = QtWidgets.QGridLayout()
        self._transfer_layout.setSpacing(5)
        self._transfer_layout.addWidget(self.transfer_load_original_btn, 0, 0)
        self._transfer_layout.addWidget(self.transfer_load_response_btn, 1, 0)
        self._transfer_layout.addWidget(self.transfer_original_filename_lbl, 0, 1)
        self._transfer_layout.addWidget(self.transfer_response_filename_lbl, 1, 1)
        self._transfer_layout.addWidget(self.transfer_plot_btn, 0, 2)
        self._transfer_layout.setColumnStretch(0, 0)
        self._transfer_layout.setColumnStretch(1, 1)
        self._transfer_layout.setColumnStretch(2, 0)
        self._transfer_layout.setRowStretch(0, 0)
        self._transfer_layout.setRowStretch(1, 0)
        self._transfer_layout.setRowStretch(2, 1)
        self.transfer_gb.setLayout(self._transfer_layout)

    def style_widgets(self):
        self.cbn_seat_gb.setCheckable(True)
        self.cbn_seat_gb.setChecked(False)
        self.oiadac_gb.setCheckable(True)
        self.oiadac_gb.setChecked(False)
        self.transfer_gb.setCheckable(True)
        self.transfer_gb.setChecked(False)

        self.setStyleSheet(
            """
                    QLineEdit {
                        min-width: 50 px;
                        min-height: 26 px;
                        max-height: 26 px;
                    }
                    """
        )
