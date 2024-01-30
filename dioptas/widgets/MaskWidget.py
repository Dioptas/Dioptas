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

from qtpy import QtWidgets
from pyqtgraph import GraphicsLayoutWidget

from .plot_widgets import MaskImgWidget

from .CustomWidgets import NumberTextField, LabelAlignRight, SpinBoxAlignRight, HorizontalSpacerItem, \
    CheckableFlatButton, FlatButton, VerticalSpacerItem, HorizontalLine


class MaskWidget(QtWidgets.QWidget):
    """
    Defines the main structure of the mask widget, which is separated into two parts.
    Mask Display Widget - shows the image and pattern
    Mask Control Widget - shows all the controls on the right side of the widget
    """

    def __init__(self, *args, **kwargs):
        super(MaskWidget, self).__init__(*args, **kwargs)
        self._layout = QtWidgets.QHBoxLayout()
        self.create_display_widget()
        self.create_control_widget()

        self._layout.addWidget(self._display_widget)
        self._layout.addWidget(self._control_widget)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(6)

        self.style_widgets()
        self.setLayout(self._layout)

    def create_display_widget(self):
        self._display_widget = QtWidgets.QWidget(self)
        self._display_layout = QtWidgets.QVBoxLayout()
        self._display_layout.setContentsMargins(0, 0, 0, 0)
        self.img_layout_widget = GraphicsLayoutWidget()
        self.img_widget = MaskImgWidget(self.img_layout_widget)

        self._display_layout.addWidget(self.img_layout_widget)

        self._status_layout = QtWidgets.QHBoxLayout()
        self._status_layout.addSpacerItem(HorizontalSpacerItem())

        self.pos_lbl = LabelAlignRight('')
        self._status_layout.addWidget(self.pos_lbl)
        self._display_layout.addLayout(self._status_layout)

        self._display_widget.setLayout(self._display_layout)

    def create_control_widget(self):
        self._control_widget = QtWidgets.QWidget(self)
        self._control_layout = QtWidgets.QVBoxLayout(self._control_widget)
        self._control_layout.setSpacing(6)

        self._rb_layout = QtWidgets.QHBoxLayout()
        self.mask_rb = QtWidgets.QRadioButton('mask')
        self.unmask_rb = QtWidgets.QRadioButton('unmask')
        self._rb_layout.addWidget(self.mask_rb)
        self._rb_layout.addWidget(self.unmask_rb)
        self._control_layout.addLayout(self._rb_layout)

        self._control_layout.addWidget(HorizontalLine())

        self._geometry_layout = QtWidgets.QGridLayout()
        self.circle_btn = CheckableFlatButton('Circle')
        self.rectangle_btn = CheckableFlatButton('Rectangle')
        self.point_btn = CheckableFlatButton('Point')
        self.point_size_sb = SpinBoxAlignRight()
        self.polygon_btn = CheckableFlatButton('Polygon')
        self.arc_btn = CheckableFlatButton('Arc')
        self._geometry_layout.addWidget(self.circle_btn, 0, 0)
        self._geometry_layout.addWidget(self.rectangle_btn, 0, 1)
        self._geometry_layout.addWidget(self.point_btn, 1, 0)
        self._geometry_layout.addWidget(self.point_size_sb, 1, 1)
        self._geometry_layout.addWidget(self.polygon_btn, 2, 0)
        self._geometry_layout.addWidget(self.arc_btn, 2, 1)
        self._control_layout.addLayout(self._geometry_layout)

        self._control_layout.addWidget(HorizontalLine())

        self._threshold_layout = QtWidgets.QGridLayout()
        self.above_thresh_btn = FlatButton('Above Thresh')
        self.below_thresh_btn = FlatButton('Below Thresh')
        self.above_thresh_txt = NumberTextField('')
        self.below_thresh_txt = NumberTextField('')
        self._threshold_layout.addWidget(self.above_thresh_btn, 0, 0)
        self._threshold_layout.addWidget(self.above_thresh_txt, 0, 1)
        self._threshold_layout.addWidget(self.below_thresh_btn, 1, 0)
        self._threshold_layout.addWidget(self.below_thresh_txt, 1, 1)
        self._control_layout.addLayout(self._threshold_layout)

        self._control_layout.addWidget(HorizontalLine())

        self._action_layout = QtWidgets.QGridLayout()
        self.grow_btn = FlatButton('Grow')
        self.shrink_btn = FlatButton('Shrink')
        self.invert_mask_btn = FlatButton('Invert')
        self.clear_mask_btn = FlatButton('Clear')
        self.undo_btn = FlatButton('Undo')
        self.redo_btn = FlatButton('Redo')
        self._action_layout.addWidget(self.grow_btn, 0, 0)
        self._action_layout.addWidget(self.shrink_btn, 0, 1)
        self._action_layout.addWidget(self.invert_mask_btn, 1, 0)
        self._action_layout.addWidget(self.clear_mask_btn, 1, 1)
        self._action_layout.addWidget(self.undo_btn, 2, 0)
        self._action_layout.addWidget(self.redo_btn, 2, 1)
        self._control_layout.addLayout(self._action_layout)

        self._control_layout.addWidget(HorizontalLine())

        self.cosmic_btn = FlatButton('Cosmic Removal')
        self._control_layout.addWidget(self.cosmic_btn)

        self._control_layout.addWidget(HorizontalLine())

        self._visibility_widget = QtWidgets.QWidget()
        self._visibility_layout = QtWidgets.QHBoxLayout()
        self.fill_rb = QtWidgets.QRadioButton('Fill')
        self.transparent_rb = QtWidgets.QRadioButton('Transparent')
        self._visibility_layout.addWidget(self.fill_rb)
        self._visibility_layout.addWidget(self.transparent_rb)
        self._visibility_widget.setLayout(self._visibility_layout)
        self._control_layout.addWidget(self._visibility_widget)

        self._control_layout.addSpacerItem(VerticalSpacerItem())

        self._file_layout = QtWidgets.QGridLayout()
        self.save_mask_btn = FlatButton('Save Mask')
        self.load_mask_btn = FlatButton('Load Mask')
        self.add_mask_btn = FlatButton('Add Mask')
        self._file_layout.addWidget(self.save_mask_btn, 0, 0, 1, 2)
        self._file_layout.addWidget(self.load_mask_btn, 1, 0)
        self._file_layout.addWidget(self.add_mask_btn, 1, 1)
        self._control_layout.addLayout(self._file_layout)

        self._control_widget.setLayout(self._control_layout)

    def style_widgets(self):
        self.mask_rb.setChecked(True)
        self.fill_rb.setChecked(True)
        self.point_size_sb.setValue(20)

        self._control_widget.setMinimumWidth(200)
        self._control_widget.setMaximumWidth(200)
