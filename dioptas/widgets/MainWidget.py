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

import sys
from PyQt4 import QtGui

from .UiFiles.MainUI import Ui_mainView

from .MaskWidget import MaskWidget
from .IntegrationWidget import IntegrationWidget
# from .IntegrationWidgetNew import IntegrationWidget
from .CalibrationWidget import CalibrationWidget


class MainWidget(QtGui.QWidget, Ui_mainView):
    def __init__(self):
        super(MainWidget, self).__init__(None)
        self.setupUi(self)

        self.calibration_widget = CalibrationWidget()
        self.mask_widget = MaskWidget()
        self.integration_widget = IntegrationWidget()

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

        self.set_system_dependent_stylesheet()

    def set_system_dependent_stylesheet(self):
        from sys import platform
        if platform == "darwin":
            self.tabWidget.setStyleSheet(
                    "QDoubleSpinBox, QSpinBox {padding-right: -8px;}")
        else:
            self.tabWidget.setStyleSheet(
                    "QDoubleSpinBox, QSpinBox {padding-right: -3px;}")


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    view = MainWidget()
    view.show()
    app.exec_()
