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

from ...CustomWidgets import NumberTextField, LabelAlignRight, CheckableFlatButton, VerticalSpacerItem, \
    HorizontalSpacerItem


class CorrectionsWidget(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super(CorrectionsWidget, self).__init__(*args, **kwargs)

        self._layout = QtWidgets.QVBoxLayout()

        self.cbn_seat_gb = QtWidgets.QGroupBox('cBN Seat Correction')
        self._cbn_seat_layout = QtWidgets.QGridLayout(self)
        self._cbn_seat_layout.setSpacing(6)

        self.anvil_thickness_txt = NumberTextField('2.3')
        self.seat_thickness_txt = NumberTextField('5.3')
        self.seat_inner_radius_txt = NumberTextField('0.4')
        self.seat_outer_radius_txt = NumberTextField('1.95')
        self.cell_tilt_txt = NumberTextField('0.0')
        self.cell_tilt_rotation_txt = NumberTextField('0.0')
        self.center_offset_txt = NumberTextField('0.0')
        self.center_offset_angle_txt = NumberTextField('0.0')
        self.anvil_absorption_length_txt = NumberTextField('13.7')
        self.seat_absorption_length_txt = NumberTextField('21.1')

        self.cbn_seat_plot_btn = CheckableFlatButton('Plot')

        self._cbn_seat_layout.addWidget(LabelAlignRight('Anvil d:'), 0, 0)
        self._cbn_seat_layout.addWidget(LabelAlignRight('Seat r1:'), 0, 4)
        self._cbn_seat_layout.addWidget(LabelAlignRight('Cell Tilt:'), 0, 8)
        self._cbn_seat_layout.addWidget(LabelAlignRight('Offset:'), 0, 12)
        self._cbn_seat_layout.addWidget(LabelAlignRight('Anvil AL:'), 0, 16)

        self._cbn_seat_layout.addWidget(LabelAlignRight('Seat d:'), 1, 0)
        self._cbn_seat_layout.addWidget(LabelAlignRight('Seat r2:'), 1, 4)
        self._cbn_seat_layout.addWidget(LabelAlignRight('Tilt Rot:'), 1, 8)
        self._cbn_seat_layout.addWidget(LabelAlignRight(u"Offs. 2θ  :"), 1, 12)
        self._cbn_seat_layout.addWidget(LabelAlignRight('Seat AL:'), 1, 16)

        self._cbn_seat_layout.addWidget(QtWidgets.QLabel('mm'), 0, 2)
        self._cbn_seat_layout.addWidget(QtWidgets.QLabel('mm'), 0, 6)
        self._cbn_seat_layout.addWidget(QtWidgets.QLabel('mm'), 0, 14)
        self._cbn_seat_layout.addWidget(QtWidgets.QLabel('mm'), 1, 2)
        self._cbn_seat_layout.addWidget(QtWidgets.QLabel('mm'), 1, 6)
        self._cbn_seat_layout.addWidget(QtWidgets.QLabel(u'°'), 0, 10)
        self._cbn_seat_layout.addWidget(QtWidgets.QLabel(u'°'), 1, 10)
        self._cbn_seat_layout.addWidget(QtWidgets.QLabel(u'°'), 1, 14)

        self._cbn_seat_layout.addItem(HorizontalSpacerItem(3), 0, 3)
        self._cbn_seat_layout.addItem(HorizontalSpacerItem(3), 0, 7)
        self._cbn_seat_layout.addItem(HorizontalSpacerItem(3), 0, 11)
        self._cbn_seat_layout.addItem(HorizontalSpacerItem(3), 0, 15)

        self._cbn_seat_layout.addWidget(self.anvil_thickness_txt, 0, 1)
        self._cbn_seat_layout.addWidget(self.seat_thickness_txt, 1, 1)
        self._cbn_seat_layout.addWidget(self.seat_inner_radius_txt, 0, 5)
        self._cbn_seat_layout.addWidget(self.seat_outer_radius_txt, 1, 5)
        self._cbn_seat_layout.addWidget(self.cell_tilt_txt, 0, 9)
        self._cbn_seat_layout.addWidget(self.cell_tilt_rotation_txt, 1, 9)
        self._cbn_seat_layout.addWidget(self.center_offset_txt, 0, 13)
        self._cbn_seat_layout.addWidget(self.center_offset_angle_txt, 1, 13)
        self._cbn_seat_layout.addWidget(self.anvil_absorption_length_txt, 0, 17)
        self._cbn_seat_layout.addWidget(self.seat_absorption_length_txt, 1, 17)

        self._cbn_seat_layout.addWidget(self.cbn_seat_plot_btn, 0, 18, 2, 1)

        self.cbn_seat_gb.setLayout(self._cbn_seat_layout)

        self.oiadac_gb = QtWidgets.QGroupBox('Oblique Incidence Angle Detector Absorption Correction')
        self._oiadac_layout = QtWidgets.QHBoxLayout()

        self.detector_thickness_txt = NumberTextField('40')
        self.detector_absorption_length_txt = NumberTextField('465.5')
        self.oiadac_plot_btn = CheckableFlatButton('Plot')

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

        self._layout.addWidget(self.cbn_seat_gb)
        self._layout.addWidget(self.oiadac_gb)
        self._layout.addSpacerItem(VerticalSpacerItem())

        self.setLayout(self._layout)
        self.style_widgets()

    def style_widgets(self):
        self.cbn_seat_gb.setCheckable(True)
        self.cbn_seat_gb.setChecked(False)

        self.setStyleSheet("""
            QLineEdit {
                min-width: 50 px;
                max-width: 60 px;
            }
        """)

        self.cbn_seat_plot_btn.setMaximumHeight(150)
        self.oiadac_plot_btn.setMaximumHeight(150)
        self.oiadac_gb.setCheckable(True)
        self.oiadac_gb.setChecked(False)
        self.detector_thickness_txt.setMinimumWidth(60)
        self.detector_thickness_txt.setMaximumWidth(60)
        self.detector_absorption_length_txt.setMinimumWidth(60)
        self.detector_absorption_length_txt.setMaximumWidth(60)
