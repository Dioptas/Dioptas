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

from ...CustomWidgets import NumberTextField, LabelAlignRight, SpinBoxAlignRight, FlatButton, \
    CheckableFlatButton, DoubleSpinBoxAlignRight, HorizontalSpacerItem, \
    DoubleMultiplySpinBoxAlignRight, SaveIconButton


class BackgroundWidget(QtWidgets.QWidget):
    def __init__(self):
        super(BackgroundWidget, self).__init__()

        self._layout = QtWidgets.QHBoxLayout()
        self._layout.setContentsMargins(5, 5 , 5, 5)
        self._layout.setSpacing(5)

        self.image_background_gb = QtWidgets.QGroupBox('Image Background', self)
        self._image_background_gb_layout = QtWidgets.QGridLayout(self.image_background_gb)
        self._image_background_gb_layout.setContentsMargins(5, 8, 5, 7)
        self._image_background_gb_layout.setSpacing(5)

        self.load_image_btn = QtWidgets.QPushButton('Load')
        self.filename_lbl = QtWidgets.QLabel('None')
        self.remove_image_btn = QtWidgets.QPushButton('Remove')
        self.scale_sb = DoubleSpinBoxAlignRight()
        self.offset_sb = DoubleSpinBoxAlignRight()

        self.scale_step_msb = DoubleMultiplySpinBoxAlignRight()
        self.offset_step_msb = DoubleMultiplySpinBoxAlignRight()

        self._image_background_gb_layout.addWidget(self.load_image_btn, 0, 0)
        self._image_background_gb_layout.addWidget(self.remove_image_btn, 1, 0)
        self._image_background_gb_layout.addWidget(self.filename_lbl, 0, 1, 1, 8)
        self._image_background_gb_layout.addWidget(LabelAlignRight('Scale:'), 1, 1)
        self._image_background_gb_layout.addWidget(self.scale_sb, 1, 2)
        self._image_background_gb_layout.addWidget(self.scale_step_msb, 1, 3)
        self._image_background_gb_layout.addItem(HorizontalSpacerItem(), 1, 4)
        self._image_background_gb_layout.addWidget(LabelAlignRight('Offset:'), 2, 1)
        self._image_background_gb_layout.addWidget(self.offset_sb, 2, 2)
        self._image_background_gb_layout.addWidget(self.offset_step_msb, 2, 3)
        self._image_background_gb_layout.addItem(HorizontalSpacerItem(), 2, 4)

        self.image_background_gb.setLayout(self._image_background_gb_layout)

        self.setLayout(self._layout)

        self.pattern_background_gb = QtWidgets.QGroupBox('Pattern Background')
        self._pattern_bkg_layout = QtWidgets.QGridLayout()
        self._pattern_bkg_layout.setContentsMargins(5, 8, 5, 7)
        self._pattern_bkg_layout.setSpacing(5)

        self.smooth_with_sb = DoubleSpinBoxAlignRight()
        self.iterations_sb = SpinBoxAlignRight()
        self.poly_order_sb = SpinBoxAlignRight()
        self.x_range_min_txt = NumberTextField('0')
        self.x_range_max_txt = NumberTextField('50')
        self.inspect_btn = CheckableFlatButton('Inspect')
        self.save_btn = SaveIconButton()
        self.as_overlay = QtWidgets.QPushButton('As Overlay')

        self._pattern_bkg_layout.addWidget(LabelAlignRight('Smooth Width:'), 0, 0)
        self._pattern_bkg_layout.addWidget(self.smooth_with_sb, 0, 1)
        self._pattern_bkg_layout.addWidget(LabelAlignRight('Iterations:'), 0, 2)
        self._pattern_bkg_layout.addWidget(self.iterations_sb, 0, 3)
        self._pattern_bkg_layout.addItem(HorizontalSpacerItem(), 0, 4)
        self._pattern_bkg_layout.addWidget(LabelAlignRight('Order:'), 0, 5)
        self._pattern_bkg_layout.addWidget(self.poly_order_sb, 0, 6)

        self._pattern_bkg_layout.addWidget(LabelAlignRight('X-Range:'), 1, 0)
        self._range_layout = QtWidgets.QHBoxLayout()
        self._range_layout.addWidget(self.x_range_min_txt)
        self._range_layout.addWidget(QtWidgets.QLabel('-'))
        self._range_layout.addWidget(self.x_range_max_txt)
        self._range_layout.addItem(HorizontalSpacerItem())
        self._pattern_bkg_layout.addLayout(self._range_layout, 1, 1, 1, 3)
        self._button_layout = QtWidgets.QHBoxLayout()
        self._button_layout.addStretch(1)
        self._button_layout.addWidget(self.inspect_btn)
        self._button_layout.addWidget(self.as_overlay)
        self._button_layout.addWidget(self.save_btn)
        self._pattern_bkg_layout.addLayout(self._button_layout, 2, 0, 1, 7)

        self.pattern_background_gb.setLayout(self._pattern_bkg_layout)

        self._left_layout = QtWidgets.QVBoxLayout()
        self._left_layout.addWidget(self.image_background_gb)
        self._left_layout.addWidget(self.pattern_background_gb)
        self._left_layout.addStretch(1)
        self._layout.addLayout(self._left_layout)
        self._layout.addStretch(1)

        self.setLayout(self._layout)
        self.style_widgets()

    def style_widgets(self):
        self.style_image_background_widgets()
        self.style_pattern_background_widgets()

    def style_image_background_widgets(self):
        self.scale_sb.setMinimum(-9999999)
        self.scale_sb.setMaximum(9999999)
        self.scale_sb.setValue(1)
        self.scale_sb.setSingleStep(0.01)

        self.pattern_background_gb.setCheckable(True)
        self.pattern_background_gb.setChecked(False)

        self.scale_step_msb.setMaximum(10.0)
        self.scale_step_msb.setMinimum(0.01)
        self.scale_step_msb.setValue(0.01)

        self.offset_step_msb.setMaximum(100000.0)
        self.offset_step_msb.setMinimum(0.01)
        self.offset_step_msb.setValue(100.0)

        self.offset_sb.setMaximum(999999998)
        self.offset_sb.setMinimum(-99999999)

        self.setStyleSheet("""
            QSpinBox,  QDoubleSpinBox,QLineEdit {
                min-width: 50px;
                max-width: 50px;
            } 
        """)

    def style_pattern_background_widgets(self):
        self.smooth_with_sb.setValue(0.100)
        self.smooth_with_sb.setMinimum(0)
        self.smooth_with_sb.setMaximum(10000000)
        self.smooth_with_sb.setSingleStep(0.005)
        self.smooth_with_sb.setDecimals(3)
        self.smooth_with_sb.setMaximumWidth(100)

        self.iterations_sb.setMaximum(99999)
        self.iterations_sb.setMinimum(1)
        self.iterations_sb.setValue(150)
        self.poly_order_sb.setMaximum(999999)
        self.poly_order_sb.setMinimum(1)
        self.poly_order_sb.setValue(50)
        self.poly_order_sb.setToolTip('Set the Polynomial order')

        self.x_range_min_txt.setMaximumWidth(70)
        self.x_range_max_txt.setMaximumWidth(70)

        self.inspect_btn.setMaximumHeight(150)

        self.save_btn.setToolTip("Save generated background pattern")
        self.save_btn.setIconSize(QtCore.QSize(13, 13))
        self.save_btn.setMaximumWidth(25)

    def get_bkg_pattern_parameters(self):
        smooth_width = float(self.smooth_with_sb.value())
        iterations = int(self.iterations_sb.value())
        polynomial_order = int(self.poly_order_sb.value())
        return smooth_width, iterations, polynomial_order

    def set_bkg_pattern_parameters(self, bkg_pattern_parameters):
        self.smooth_with_sb.blockSignals(True)
        self.iterations_sb.blockSignals(True)
        self.poly_order_sb.blockSignals(True)

        self.smooth_with_sb.setValue(bkg_pattern_parameters[0])
        self.iterations_sb.setValue(bkg_pattern_parameters[1])
        self.poly_order_sb.setValue(bkg_pattern_parameters[2])

        self.smooth_with_sb.blockSignals(False)
        self.iterations_sb.blockSignals(False)
        self.poly_order_sb.blockSignals(False)

    def get_bkg_pattern_roi(self):
        x_min = float(str(self.x_range_min_txt.text()))
        x_max = float(str(self.x_range_max_txt.text()))
        return x_min, x_max

    def set_bkg_pattern_roi(self, roi):
        self.x_range_min_txt.blockSignals(True)
        self.x_range_max_txt.blockSignals(True)

        self.x_range_min_txt.setText('{:.3f}'.format(roi[0]))
        self.x_range_max_txt.setText('{:.3f}'.format(roi[1]))

        self.x_range_min_txt.blockSignals(False)
        self.x_range_max_txt.blockSignals(False)
