# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2014  Clemens Prescher (clemens.prescher@gmail.com)
# GSECARS, University of Chicago
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

from __future__ import absolute_import

__author__ = 'Clemens Prescher'

from PyQt4 import QtGui


from .UiFiles.MaskUI import Ui_xrs_mask_widget
from .ImgWidget import MaskImgWidget


class MaskWidget(QtGui.QWidget, Ui_xrs_mask_widget):
    def __init__(self):
        super(MaskWidget, self).__init__(None)
        self.setupUi(self)
        #self.splitter.setStretchFactor(0, 1)
        self.img_view = MaskImgWidget(self.img_pg_layout)
        self.set_validator()

    def set_validator(self):
        self.above_thresh_txt.setValidator(QtGui.QIntValidator())
        self.below_thresh_txt.setValidator(QtGui.QIntValidator())
