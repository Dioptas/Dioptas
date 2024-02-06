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

from ...CustomWidgets import LabelAlignRight, HorizontalSpacerItem
from ..CustomWidgets import MouseCurrentAndClickedWidget, MouseUnitCurrentAndClickedWidget
from .. import CLICKED_COLOR


class IntegrationStatusWidget(QtWidgets.QWidget):
    def __init__(self):
        super(IntegrationStatusWidget, self).__init__()

        self._layout = QtWidgets.QHBoxLayout()
        self._layout.setContentsMargins(6, 3, 6, 0)
        self._layout.setSpacing(6)

        self.mouse_pos_widget = MouseCurrentAndClickedWidget(CLICKED_COLOR)
        self.mouse_unit_widget = MouseUnitCurrentAndClickedWidget(CLICKED_COLOR)
        self.bkg_name_lbl = LabelAlignRight('')
        self.change_view_btn = QtWidgets.QPushButton('Change View')

        self._layout.addWidget(self.change_view_btn)
        self._layout.addWidget(self.mouse_pos_widget)
        self._layout.addSpacerItem(HorizontalSpacerItem())
        self._layout.addWidget(self.mouse_unit_widget)
        self._layout.addSpacerItem(HorizontalSpacerItem())
        self._layout.addWidget(self.bkg_name_lbl)

        self.setLayout(self._layout)
