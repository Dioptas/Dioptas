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
from pyqtgraph import GraphicsLayoutWidget

from ...plot_widgets import PatternWidget
from ...CustomWidgets import LabelAlignRight, FlatButton, CheckableFlatButton, HorizontalSpacerItem, VerticalSpacerItem


class IntegrationPatternWidget(QtWidgets.QWidget):
    def __init__(self):
        super(IntegrationPatternWidget, self).__init__()

        self.frame = QtWidgets.QFrame()
        self.frame.setObjectName('pattern_frame')

        self._frame_layout = QtWidgets.QVBoxLayout()
        self._frame_layout.setContentsMargins(0, 0, 6, 0)

        self._top_control_layout = QtWidgets.QHBoxLayout()
        self._top_control_layout.setContentsMargins(8, 8, 0, 0)

        self.save_image_btn = FlatButton('Save Image')
        self.save_pattern_btn = FlatButton('Save Pattern')
        self.as_overlay_btn = FlatButton('As Overlay')
        self.as_bkg_btn = FlatButton('As Bkg')
        self.load_calibration_btn = FlatButton('Load Calibration')
        self.calibration_lbl = LabelAlignRight('None')

        self._top_control_layout.addWidget(self.save_image_btn)
        self._top_control_layout.addWidget(self.save_pattern_btn)
        self._top_control_layout.addWidget(self.as_overlay_btn)
        self._top_control_layout.addWidget(self.as_bkg_btn)
        self._top_control_layout.addSpacerItem(HorizontalSpacerItem())
        self._top_control_layout.addWidget(self.load_calibration_btn)
        self._top_control_layout.addWidget(self.calibration_lbl)

        self._frame_layout.addLayout(self._top_control_layout)

        self.right_control_widget = QtWidgets.QWidget()
        self.right_control_widget.setObjectName('pattern_right_control_widget')
        self._right_control_layout = QtWidgets.QVBoxLayout()
        self._right_control_layout.setContentsMargins(0, 0, 0, 6)
        self._right_control_layout.setSpacing(4)

        self.tth_btn = CheckableFlatButton(u"2θ")
        self.q_btn = CheckableFlatButton('Q')
        self.d_btn = CheckableFlatButton('d')
        self.unit_btn_group = QtWidgets.QButtonGroup()
        self.unit_btn_group.addButton(self.tth_btn)
        self.unit_btn_group.addButton(self.q_btn)
        self.unit_btn_group.addButton(self.d_btn)
        self.background_btn = CheckableFlatButton('bg')
        self.background_inspect_btn = CheckableFlatButton('I')
        self.antialias_btn = CheckableFlatButton('AA')
        self.auto_range_btn = CheckableFlatButton('A')

        self._right_control_layout.addWidget(self.tth_btn)
        self._right_control_layout.addWidget(self.q_btn)
        self._right_control_layout.addWidget(self.d_btn)
        self._right_control_layout.addSpacerItem(VerticalSpacerItem())
        self._right_control_layout.addWidget(self.background_btn)
        self._right_control_layout.addWidget(self.background_inspect_btn)
        self._right_control_layout.addSpacerItem(VerticalSpacerItem())
        self._right_control_layout.addWidget(self.antialias_btn)
        self._right_control_layout.addSpacerItem(VerticalSpacerItem())
        self._right_control_layout.addWidget(self.auto_range_btn)

        self.right_control_widget.setLayout(self._right_control_layout)

        self._central_layout = QtWidgets.QHBoxLayout()
        self._central_layout.setSpacing(0)

        self.pattern_pg_layout = GraphicsLayoutWidget()
        self.pattern_view = PatternWidget(self.pattern_pg_layout)
        self.pattern_pg_layout.ci.layout.setContentsMargins(5, 0, 0, 5)

        self._central_layout.addWidget(self.pattern_pg_layout)
        self._central_layout.addWidget(self.right_control_widget)
        self._frame_layout.addLayout(self._central_layout)

        self.frame.setLayout(self._frame_layout)

        self._layout = QtWidgets.QVBoxLayout()
        self._layout.addWidget(self.frame)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self._layout)

        self.style_widgets()

    def style_widgets(self):
        self.tth_btn.setChecked(True)
        self.antialias_btn.setChecked(True)
        self.auto_range_btn.setChecked(True)

        self.setStyleSheet("""
            #pattern_frame, #pattern_right_control_widget, QLabel {
                background: black;
                color: yellow;
            }
            #pattern_right_control_widget QPushButton{
                padding: 0px;
	            padding-right: 1px;
	            border-radius: 3px;
            }
	    """)

        right_controls_button_width = 25
        self.tth_btn.setMaximumWidth(right_controls_button_width)
        self.q_btn.setMaximumWidth(right_controls_button_width)
        self.d_btn.setMaximumWidth(right_controls_button_width)
        self.background_btn.setMaximumWidth(right_controls_button_width)
        self.background_inspect_btn.setMaximumWidth(right_controls_button_width)
        self.antialias_btn.setMaximumWidth(right_controls_button_width)
        self.auto_range_btn.setMaximumWidth(right_controls_button_width)


class IntegrationStatusWidget(QtWidgets.QWidget):
    def __init__(self):
        super(IntegrationStatusWidget, self).__init__()

        self._layout = QtWidgets.QHBoxLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)

        self.mouse_pos_widget = MouseCurrentAndClickedWidget(CLICKED_COLOR)
        self.mouse_unit_widget = MouseUnitCurrentAndClickedWidget(CLICKED_COLOR)
        self.bkg_name_lbl = LabelAlignRight('')
        self.change_gui_view_btn = QtWidgets.QPushButton('Change View')

        self._layout.addWidget(self.change_gui_view_btn)
        self._layout.addWidget(self.mouse_pos_widget)
        self._layout.addSpacerItem(HorizontalSpacerItem())
        self._layout.addWidget(self.mouse_unit_widget)
        self._layout.addSpacerItem(HorizontalSpacerItem())
        self._layout.addWidget(self.bkg_name_lbl)

        self.setLayout(self._layout)
