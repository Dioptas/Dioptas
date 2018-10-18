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

from ...CustomWidgets import IntegerTextField, NumberTextField, LabelAlignRight, SpinBoxAlignRight, VerticalSpacerItem, \
    HorizontalSpacerItem


class OptionsWidget(QtWidgets.QWidget):
    def __init__(self):
        super(OptionsWidget, self).__init__()

        self.create_integration_gb()
        self.create_cake_gb()

        self.style_integration_widgets()
        self.style_cake_widgets()

        self._layout = QtWidgets.QVBoxLayout()
        self._integration_layout = QtWidgets.QHBoxLayout()
        self._integration_layout.addWidget(self.integration_gb)
        self._integration_layout.addWidget(self.cake_gb)
        self._integration_layout.addSpacerItem(HorizontalSpacerItem())

        self._layout.addLayout(self._integration_layout)
        self._layout.addItem(VerticalSpacerItem())

        self.setLayout(self._layout)

    def create_integration_gb(self):
        self.integration_gb = QtWidgets.QGroupBox('1D integration')
        self._integration_gb_layout = QtWidgets.QGridLayout()

        self.bin_count_txt = IntegerTextField('0')
        self.bin_count_cb = QtWidgets.QCheckBox('auto')
        self.supersampling_sb = SpinBoxAlignRight()
        self.correct_solid_angle_cb = QtWidgets.QCheckBox('correct Solid Angle')
        self.correct_solid_angle_cb.setChecked(True)

        self._integration_gb_layout.addWidget(LabelAlignRight('Radial bins:'), 0, 0)
        self._integration_gb_layout.addWidget(LabelAlignRight('Supersampling:'), 1, 0)

        self._integration_gb_layout.addWidget(self.bin_count_txt, 0, 1)
        self._integration_gb_layout.addWidget(self.bin_count_cb, 0, 2)
        self._integration_gb_layout.addWidget(self.supersampling_sb, 1, 1)
        self._integration_gb_layout.addWidget(self.correct_solid_angle_cb, 2, 1, 1, 2)

        self.integration_gb.setLayout(self._integration_gb_layout)

    def create_cake_gb(self):
        self.cake_gb = QtWidgets.QGroupBox('2D (Cake-) integration')
        self._cake_gb_layout = QtWidgets.QGridLayout()
        self._cake_azimuth_points_sb = SpinBoxAlignRight()
        self._cake_azimuth_min_txt = NumberTextField('-180')
        self._cake_azimuth_max_txt = NumberTextField('180')

        self._cake_gb_layout.addWidget(LabelAlignRight('Azimuth bins:'), 0, 0)
        self._cake_gb_layout.addWidget(self._cake_azimuth_points_sb, 0, 1)
        self._cake_gb_layout.addWidget(LabelAlignRight('Azimuth range:'), 1, 0)
        self._azi_range_layout = QtWidgets.QHBoxLayout()
        self._azi_range_layout.addWidget(self._cake_azimuth_min_txt)
        self._azi_range_separater_lbl = LabelAlignRight('-')
        self._azi_range_layout.addWidget(self._azi_range_separater_lbl)
        self._azi_range_layout.addWidget(self._cake_azimuth_max_txt)
        self._cake_gb_layout.addLayout(self._azi_range_layout, 1, 1)
        self.cake_gb.setLayout(self._cake_gb_layout)

    def style_integration_widgets(self):
        max_width = 110
        self.bin_count_txt.setMaximumWidth(max_width)
        self.supersampling_sb.setMaximumWidth(max_width)

        self.supersampling_sb.setMinimum(1)
        self.supersampling_sb.setMaximum(20)
        self.supersampling_sb.setSingleStep(1)

        self.bin_count_txt.setEnabled(False)
        self.bin_count_cb.setChecked(True)

    def style_cake_widgets(self):
        self._cake_azimuth_points_sb.setMaximumWidth(85)
        self._cake_azimuth_points_sb.setMinimum(1)
        self._cake_azimuth_points_sb.setSingleStep(1)

        self._cake_azimuth_max_txt.setMaximumWidth(35)
        self._cake_azimuth_min_txt.setMaximumWidth(35)
        self._azi_range_separater_lbl.setMaximumWidth(5)



