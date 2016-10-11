# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
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

from qtpy import QtWidgets

from .ConfigurationWidget import ConfigurationWidget
from .CalibrationWidget import CalibrationWidget
from .MaskWidget import MaskWidget
from .integration import IntegrationWidget

widget_path = os.path.dirname(__file__)


class MainWidget(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super(MainWidget, self).__init__(*args, **kwargs)

        self._layout = QtWidgets.QVBoxLayout()
        self._layout.setContentsMargins(10, 2, 2, 2)
        self._layout.setSpacing(6)

        self.configuration_widget = ConfigurationWidget(self)
        self._layout.addWidget(self.configuration_widget)

        self.tabWidget = QtWidgets.QTabWidget()
        self.tabWidget.setTabPosition(QtWidgets.QTabWidget.West)
        self.tabWidget.setCurrentIndex(0)

        self.calibration_widget = CalibrationWidget(self)
        self.mask_widget = MaskWidget(self)
        self.integration_widget = IntegrationWidget(self)

        self.tabWidget.addTab(self.calibration_widget, 'Calibration')
        self.tabWidget.addTab(self.mask_widget, 'Mask')
        self.tabWidget.addTab(self.integration_widget, 'Integration')

        self._layout.addWidget(self.tabWidget)
        self.setLayout(self._layout)

        self.set_system_dependent_stylesheet()
        self.set_stylesheet()

    def set_stylesheet(self):
        file = open(os.path.join(widget_path, "stylesheet.qss"))
        stylesheet = file.read()
        self.setStyleSheet(stylesheet)
        file.close()

    def set_system_dependent_stylesheet(self):
        from sys import platform
        if platform == "darwin":
            self.tabWidget.setStyleSheet(
                    "QDoubleSpinBox, QSpinBox {padding-right: -8px;}")
        else:
            self.tabWidget.setStyleSheet(
                    "QDoubleSpinBox, QSpinBox {padding-right: -3px;}")
