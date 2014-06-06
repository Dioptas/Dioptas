# -*- coding: utf8 -*-
# Py2DeX - GUI program for fast processing of 2D X-ray data
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
from UiFiles.IntegrationUI import Ui_xrs_integration_widget
from ImgView import IntegrationImgView
from SpectrumView import SpectrumView
import numpy as np
import pyqtgraph as pg


class IntegrationView(QtGui.QWidget, Ui_xrs_integration_widget):
    def __init__(self):
        super(IntegrationView, self).__init__(None)
        self.setupUi(self)
        self.horizontal_splitter.setStretchFactor(0, 1)
        self.horizontal_splitter.setStretchFactor(1, 1)
        self.horizontal_splitter.setSizes([300, 200])
        self.vertical_splitter.setStretchFactor(0, 0)
        self.vertical_splitter.setStretchFactor(1, 1)
        self.vertical_splitter.setSizes([100, 700])
        self.img_view = IntegrationImgView(self.img_pg_layout, orientation='horizontal')
        self.spectrum_view = SpectrumView(self.spectrum_pg_layout)
        self.set_validator()

    def set_validator(self):
        self.phase_pressure_step_txt.setValidator(QtGui.QDoubleValidator())
        self.phase_temperature_step_txt.setValidator(QtGui.QDoubleValidator())
        self.overlay_scale_step_txt.setValidator(QtGui.QDoubleValidator())
        self.overlay_offset_step_txt.setValidator(QtGui.QDoubleValidator())
        self.phase_pressure_step_txt.setValidator(QtGui.QDoubleValidator())
        self.phase_temperature_step_txt.setValidator(QtGui.QDoubleValidator())

    def switch_to_cake(self):
        self.img_view.img_view_box.setAspectLocked(False)
        self.img_view.activate_vertical_line()

    def switch_to_img(self):
        self.img_view.img_view_box.setAspectLocked(True)
        self.img_view.deactivate_vertical_line()
