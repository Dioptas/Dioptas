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
    IntegerTextField,
    MenuTabWidget,
    NumberTextField,
    LabelAlignRight,
    SpinBoxAlignRight,
    ConservativeSpinBox,
    CheckableFlatButton,
    SaveIconButton,
)


class OptionsWidget(QtWidgets.QWidget):
    def __init__(self):
        super(OptionsWidget, self).__init__()

        self.create_integration_gb()
        self.create_cake_gb()

        self.style_integration_widgets()
        self.style_cake_widgets()
        self.set_tooltips()

        self._layout = QtWidgets.QHBoxLayout()
        self._layout.setContentsMargins(0, 5, 0, 0)
        self._layout.setSpacing(0)

        self._tab_widget = MenuTabWidget()
        self._tab_widget.add_tab("1D Integration", self.integration_gb)
        self._tab_widget.add_tab("2D Integration", self.cake_gb)

        self._layout.addWidget(self._tab_widget)

        self.setLayout(self._layout)
        self.set_stylesheet()

    def create_integration_gb(self):
        self.integration_gb = QtWidgets.QGroupBox("1D integration")
        self._integration_gb_layout = QtWidgets.QGridLayout()
        self._integration_gb_layout.setContentsMargins(5, 8, 5, 7)
        self._integration_gb_layout.setSpacing(5)
        self.oned_azimuth_min_txt = NumberTextField("-180")
        self.oned_azimuth_max_txt = NumberTextField("180")
        self.oned_full_toggle_btn = CheckableFlatButton("Full")

        self.bin_count_txt = IntegerTextField("0")
        self.bin_count_cb = QtWidgets.QCheckBox("auto")
        self.supersampling_sb = SpinBoxAlignRight()
        self.correct_solid_angle_cb = QtWidgets.QCheckBox("correct Solid Angle")
        self.correct_solid_angle_cb.setChecked(True)

        self._integration_gb_layout.addWidget(LabelAlignRight("Radial bins:"), 0, 0)

        self._integration_gb_layout.addWidget(self.bin_count_txt, 0, 1)
        self._integration_gb_layout.addWidget(self.bin_count_cb, 0, 2)
        self._integration_gb_layout.addWidget(LabelAlignRight("Azimuth range:"), 1, 0)
        self._oned_azi_range_layout = QtWidgets.QHBoxLayout()
        self._oned_azi_range_layout.setContentsMargins(0, 0, 0, 0)
        self._oned_azi_range_layout.setSpacing(5)
        self._oned_azi_range_layout.addWidget(self.oned_azimuth_min_txt)
        self._oned_azi_range_layout.addWidget(LabelAlignRight("-"))
        self._oned_azi_range_layout.addWidget(self.oned_azimuth_max_txt)
        self._integration_gb_layout.addLayout(self._oned_azi_range_layout, 1, 1, 1, 2)
        self._integration_gb_layout.addWidget(self.oned_full_toggle_btn, 1, 3)
        self._integration_gb_layout.addWidget(self.correct_solid_angle_cb, 2, 1)
        self._integration_gb_layout.addWidget(LabelAlignRight("Supersampling:"), 3, 0)
        self._integration_gb_layout.addWidget(self.supersampling_sb, 3, 1)

        self._integration_gb_layout.setRowStretch(0, 0)
        self._integration_gb_layout.setRowStretch(1, 0)
        self._integration_gb_layout.setRowStretch(2, 0)
        self._integration_gb_layout.setRowStretch(5, 1)
        self._integration_gb_layout.setColumnStretch(0, 0)
        self._integration_gb_layout.setColumnStretch(1, 0)
        self._integration_gb_layout.setColumnStretch(2, 0)
        self._integration_gb_layout.setColumnStretch(3, 0)
        self._integration_gb_layout.setColumnStretch(4, 1)

        self.integration_gb.setLayout(self._integration_gb_layout)

    def create_cake_gb(self):
        self.cake_gb = QtWidgets.QGroupBox("2D (Cake-) integration")
        self._cake_gb_layout = QtWidgets.QGridLayout()
        self._cake_gb_layout.setContentsMargins(5, 8, 5, 7)
        self._cake_gb_layout.setSpacing(5)

        self.cake_azimuth_points_sb = ConservativeSpinBox()
        self.cake_azimuth_min_txt = NumberTextField("-180")
        self.cake_azimuth_max_txt = NumberTextField("180")
        self.cake_full_toggle_btn = CheckableFlatButton("Full")
        self.cake_integral_width_sb = ConservativeSpinBox()
        self.cake_save_integral_btn = SaveIconButton()

        self._cake_gb_layout.addWidget(LabelAlignRight("Azimuth bins:"), 0, 0)
        self._cake_gb_layout.addWidget(self.cake_azimuth_points_sb, 0, 1)
        self._cake_gb_layout.addWidget(LabelAlignRight("Azimuth range:"), 1, 0)
        self._azi_range_layout = QtWidgets.QHBoxLayout()
        self._azi_range_layout.setContentsMargins(0, 0, 0, 0)
        self._azi_range_layout.setSpacing(5)
        self._azi_range_layout.addWidget(self.cake_azimuth_min_txt)
        self._azi_range_layout.addWidget(LabelAlignRight("-"))
        self._azi_range_layout.addWidget(self.cake_azimuth_max_txt)
        self._cake_gb_layout.addLayout(self._azi_range_layout, 1, 1, 1, 2)
        self._cake_gb_layout.addWidget(self.cake_full_toggle_btn, 1, 3)
        self._cake_gb_layout.addWidget(LabelAlignRight("Integral Width:"), 2, 0)
        self._cake_gb_layout.addWidget(self.cake_integral_width_sb, 2, 1)
        self._cake_gb_layout.addWidget(self.cake_save_integral_btn, 2, 2)

        self._cake_gb_layout.setRowStretch(0, 0)
        self._cake_gb_layout.setRowStretch(1, 0)
        self._cake_gb_layout.setRowStretch(2, 0)
        self._cake_gb_layout.setRowStretch(3, 1)
        self._cake_gb_layout.setColumnStretch(0, 0)
        self._cake_gb_layout.setColumnStretch(1, 0)
        self._cake_gb_layout.setColumnStretch(2, 0)
        self._cake_gb_layout.setColumnStretch(3, 0)
        self._cake_gb_layout.setColumnStretch(4, 1)

        self.cake_gb.setLayout(self._cake_gb_layout)

    def style_integration_widgets(self):
        self.supersampling_sb.setMinimum(1)
        self.supersampling_sb.setMaximum(20)
        self.supersampling_sb.setSingleStep(1)

        self.bin_count_txt.setEnabled(False)
        self.bin_count_cb.setChecked(True)

        self.oned_full_toggle_btn.setChecked(True)
        self.oned_azimuth_min_txt.setDisabled(True)
        self.oned_azimuth_max_txt.setDisabled(True)

    def style_cake_widgets(self):
        self.cake_azimuth_points_sb.setMinimum(1)
        self.cake_azimuth_points_sb.setMaximum(10000)
        self.cake_azimuth_points_sb.setSingleStep(100)

        self.cake_full_toggle_btn.setChecked(True)
        self.cake_azimuth_min_txt.setDisabled(True)
        self.cake_azimuth_max_txt.setDisabled(True)

        self.cake_integral_width_sb.setMinimum(1)
        self.cake_integral_width_sb.setSingleStep(1)
        self.cake_integral_width_sb.setMaximum(1000000)
        button_width = 25
        button_height = 25
        self.cake_save_integral_btn.setIconSize(QtCore.QSize(15, 15))
        self.cake_save_integral_btn.setWidth(button_width)
        self.cake_save_integral_btn.setHeight(button_height)

    def set_tooltips(self):
        self.cake_full_toggle_btn.setToolTip("Set to full available range")
        self.oned_full_toggle_btn.setToolTip("Set to full available range")
        self.cake_save_integral_btn.setToolTip(
            "Save the tth integral next to the cake image"
        )
        self.cake_integral_width_sb.setToolTip(
            "Sets the width used for the integral plot\nnext to the cake image."
        )

    def set_stylesheet(self):
        self.setStyleSheet(
            """
            QSpinBox, QDoubleSpinBox, QLineEdit {
                width: 60px;
            } 
            """
        )
