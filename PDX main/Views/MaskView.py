# -*- coding: utf8 -*-
#     Py2DeX - GUI program for fast processing of 2D X-ray data
#     Copyright (C) 2014  Clemens Prescher (clemens.prescher@gmail.com)
#     GSECARS, University of Chicago
#
#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.
#
#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <http://www.gnu.org/licenses/>.

__author__ = 'Clemens Prescher'

import os
from PyQt4 import QtGui, QtCore
from UiFiles.MaskUI import Ui_xrs_mask_widget
from ImgView import MaskImgView
import numpy as np
import pyqtgraph as pg


class MaskView(QtGui.QWidget, Ui_xrs_mask_widget):
    def __init__(self):
        super(MaskView, self).__init__(None)
        self.setupUi(self)
        #self.splitter.setStretchFactor(0, 1)
        self.img_view = MaskImgView(self.img_pg_layout)
        self.img_view.add_mouse_move_observer(self.show_img_mouse_position)
        self.set_validator()

    def set_validator(self):
        self.above_thresh_txt.setValidator(QtGui.QIntValidator())
        self.below_thresh_txt.setValidator(QtGui.QIntValidator())


    def show_img_mouse_position(self, x, y):
        try:
            if x > 0 and y > 0:
                str = "x: %8.1f   y: %8.1f   I: %6.f" % (x, y, self.img_view.img_data.T[np.floor(x), np.floor(y)])
            else:
                str = "x: %.1f y: %.1f" % (x, y)
        except (IndexError, AttributeError):
            str = "x: %.1f y: %.1f" % (x, y)
        self.pos_lbl.setText(str)