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

from ...CustomWidgets import VerticalSpacerItem, HorizontalLine, HorizontalSpacerItem
from ..CustomWidgets import BrowseFileWidget


class PatternWidget(QtWidgets.QWidget):
    def __init__(self):
        super(PatternWidget, self).__init__()

        self._layout = QtWidgets.QVBoxLayout()
        self._layout.setContentsMargins(5, 0, 5, 5)
        self._layout.setSpacing(5)

        self.file_widget = BrowseFileWidget(files='Pattern', checkbox_text='autocreate')

        self._layout.addWidget(self.file_widget)
        self._layout.addWidget(HorizontalLine())

        self.pattern_types_gc = QtWidgets.QGroupBox('Pattern data types')
        self.xy_cb = QtWidgets.QCheckBox('.xy')
        self.xy_cb.setChecked(True)
        self.chi_cb = QtWidgets.QCheckBox('.chi')
        self.dat_cb = QtWidgets.QCheckBox('.dat')
        self.fxye_cb = QtWidgets.QCheckBox('.fxye')
        self._pattern_types_gb_layout = QtWidgets.QHBoxLayout()
        self._pattern_types_gb_layout.addWidget(self.xy_cb)
        self._pattern_types_gb_layout.addWidget(self.chi_cb)
        self._pattern_types_gb_layout.addWidget(self.dat_cb)
        self._pattern_types_gb_layout.addWidget(self.fxye_cb)
        self.pattern_types_gc.setLayout(self._pattern_types_gb_layout)

        self._pattern_types_layout = QtWidgets.QHBoxLayout()
        self._pattern_types_layout.addWidget(self.pattern_types_gc)
        self._pattern_types_layout.addSpacerItem(HorizontalSpacerItem())

        self._layout.addLayout(self._pattern_types_layout)

        self._layout.addItem(VerticalSpacerItem())

        self.setLayout(self._layout)