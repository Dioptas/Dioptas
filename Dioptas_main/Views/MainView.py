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

import sys
from PyQt4 import QtGui


from .UiFiles.MainUI import Ui_mainView

from .MaskView import MaskView
from .IntegrationView import IntegrationView
from .CalibrationView import CalibrationView


class MainView(QtGui.QWidget, Ui_mainView):
    def __init__(self):
        super(MainView, self).__init__(None)
        self.setupUi(self)

        self.calibration_widget = CalibrationView()
        self.mask_widget = MaskView()
        self.integration_widget = IntegrationView()

        self.calibration_layout = QtGui.QHBoxLayout()
        self.calibration_layout.setContentsMargins(0, 0, 0, 0)
        self.calibration_tab.setLayout(self.calibration_layout)
        self.calibration_layout.addWidget(self.calibration_widget)

        self.mask_layout = QtGui.QHBoxLayout()
        self.mask_layout.setContentsMargins(0, 0, 0, 0)
        self.mask_tab.setLayout(self.mask_layout)
        self.mask_layout.addWidget(self.mask_widget)

        self.integration_layout = QtGui.QHBoxLayout()
        self.integration_layout.setContentsMargins(0, 0, 0, 0)
        self.integration_tab.setLayout(self.integration_layout)
        self.integration_layout.addWidget(self.integration_widget)


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    view = MainView()
    view.show()
    app.exec_()