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

from ...CustomWidgets import LabelAlignRight, FlatButton, VerticalSpacerItem, HorizontalLine, HorizontalSpacerItem
from ..CustomWidgets import BrowseFileWidget


class ImageWidget(QtWidgets.QWidget):
    def __init__(self):
        super(ImageWidget, self).__init__()

        self._create_widgets()
        self._create_layout()
        self._style_widgets()

    def _create_widgets(self):
        self.file_widget = BrowseFileWidget(files='Image', checkbox_text='autoprocess')
        self.file_info_btn = FlatButton('File Info')
        self.move_btn = FlatButton('Position')
        self.map_2D_btn = FlatButton('2D Map')
        self.batch_btn = FlatButton('Batch view')

        self.batch_mode_widget = QtWidgets.QWidget()
        self.batch_mode_lbl = LabelAlignRight("Batch Mode:")
        self.batch_mode_integrate_rb = QtWidgets.QRadioButton("integrate")
        self.batch_mode_add_rb = QtWidgets.QRadioButton("add")
        self.batch_mode_image_save_rb = QtWidgets.QRadioButton("image save")

    def _create_layout(self):
        self._layout = QtWidgets.QVBoxLayout()
        self._layout.setContentsMargins(5, 0, 5, 5)
        self._layout.setSpacing(5)

        self._layout.addWidget(self.file_widget)

        self._batch_layout = QtWidgets.QHBoxLayout()
        self._batch_layout.addWidget(self.batch_mode_lbl)
        self._batch_layout.addWidget(self.batch_mode_integrate_rb)
        self._batch_layout.addWidget(self.batch_mode_add_rb)
        self._batch_layout.addWidget(self.batch_mode_image_save_rb)
        self._batch_layout.addItem(HorizontalSpacerItem())
        self._batch_layout.addWidget(self.batch_btn)
        self._batch_layout.addItem(HorizontalSpacerItem())
        self.batch_mode_widget.setLayout(self._batch_layout)
        self._layout.addWidget(self.batch_mode_widget)

        self._layout.addWidget(HorizontalLine())

        self._file_info_layout = QtWidgets.QHBoxLayout()
        self._file_info_layout.addWidget(self.file_info_btn)
        self._file_info_layout.addWidget(self.move_btn)
        self._file_info_layout.addWidget(self.map_2D_btn)
        self._file_info_layout.addSpacerItem(HorizontalSpacerItem())

        self._layout.addLayout(self._file_info_layout)
        self._layout.addSpacerItem(VerticalSpacerItem())

        self.setLayout(self._layout)

    def _style_widgets(self):
        self._batch_layout.setContentsMargins(0, 0, 0, 0)
        self.batch_mode_integrate_rb.setChecked(True)
