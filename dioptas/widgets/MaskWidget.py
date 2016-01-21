# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
# Copyright (C) 2015  Clemens Prescher (clemens.prescher@gmail.com)
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

import os

from PyQt4 import QtGui, QtCore
from pyqtgraph import GraphicsLayoutWidget

from widgets.plot_widgets import MaskImgWidget

from widgets.CustomWidgets import NumberTextField, LabelAlignRight, SpinBoxAlignRight, \
    HorizontalSpacerItem, CheckableFlatButton, FlatButton, VerticalSpacerItem, HorizontalLine


class MaskWidget(QtGui.QWidget):
    """
    Defines the main structure of the mask widget, which is separated into two parts.
    Mask Display Widget - shows the image and pattern
    Mask Control Widget - shows all the controls on the right side of the widget
    """

    def __init__(self, *args, **kwargs):
        super(MaskWidget, self).__init__()
        self.create_display_widget()
        self.create_control_widget()

        self._layout = QtGui.QHBoxLayout()
        self._layout.addWidget(self._display_widget)
        self._layout.addWidget(self._control_widget)
        self.setLayout(self._layout)

        self.style_widgets()

    def create_display_widget(self):
        self._display_widget = QtGui.QWidget()
        self._display_layout = QtGui.QVBoxLayout()
        self.img_layout_widget = GraphicsLayoutWidget()
        self.img_view = MaskImgWidget(self.img_layout_widget)

        self._display_layout.addWidget(self.img_layout_widget)

        self._status_layout = QtGui.QHBoxLayout()
        self._status_layout.addSpacerItem(HorizontalSpacerItem())

        self.pos_lbl = LabelAlignRight('')
        self._status_layout.addWidget(self.pos_lbl)
        self._display_layout.addLayout(self._status_layout)

        self._display_widget.setLayout(self._display_layout)

    def create_control_widget(self):
        self._control_widget = QtGui.QWidget()
        self._control_layout = QtGui.QVBoxLayout()

        self._rb_layout = QtGui.QHBoxLayout()
        self.mask_rb = QtGui.QRadioButton('mask')
        self.unmask_rb = QtGui.QRadioButton('unmask')
        self._rb_layout.addWidget(self.mask_rb)
        self._rb_layout.addWidget(self.unmask_rb)
        self._control_layout.addLayout(self._rb_layout)

        self._control_layout.addWidget(HorizontalLine())

        self._geometry_layout = QtGui.QGridLayout()
        self.circle_btn = CheckableFlatButton('Circle')
        self.rectangle_btn = CheckableFlatButton('Rectangle')
        self.point_btn = CheckableFlatButton('Point')
        self.point_size_sb = SpinBoxAlignRight()
        self.polygon_btn = CheckableFlatButton('Polygon')
        self._geometry_layout.addWidget(self.circle_btn, 0, 0)
        self._geometry_layout.addWidget(self.rectangle_btn, 0, 1)
        self._geometry_layout.addWidget(self.point_btn, 1, 0)
        self._geometry_layout.addWidget(self.point_size_sb, 1, 1)
        self._geometry_layout.addWidget(self.polygon_btn, 2, 0, 1, 2)
        self._control_layout.addLayout(self._geometry_layout)

        self._control_layout.addWidget(HorizontalLine())

        self._threshold_layout = QtGui.QGridLayout()
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

        self._action_layout = QtGui.QGridLayout()
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

        self._visibility_widget = QtGui.QWidget()
        self._visibility_layout = QtGui.QHBoxLayout()
        self.fill_rb = QtGui.QRadioButton('Fill')
        self.transparent_rb = QtGui.QRadioButton('Transparent')
        self._visibility_layout.addWidget(self.fill_rb)
        self._visibility_layout.addWidget(self.transparent_rb)
        self._visibility_widget.setLayout(self._visibility_layout)
        self._control_layout.addWidget(self._visibility_widget)

        self._control_layout.addSpacerItem(VerticalSpacerItem())

        self._file_layout = QtGui.QGridLayout()
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


if __name__ == '__main__':
    app = QtGui.QApplication([])
    widget = MaskWidget()
    widget.show()
    # widget.setWindowState(widget.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
    # widget.activateWindow()
    # widget.raise_()
    app.exec_()
