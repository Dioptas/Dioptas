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

from qtpy import QtWidgets, QtGui

from .ConfigurationWidget import ConfigurationWidget
from .CalibrationWidget import CalibrationWidget
from .MaskWidget import MaskWidget
from .integration import IntegrationWidget
from .CustomWidgets import RotatedCheckableFlatButton, VerticalSpacerItem, CheckableFlatButton

widget_path = os.path.dirname(__file__)


class MainWidget(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super(MainWidget, self).__init__(*args, **kwargs)

        self._outer_layout = QtWidgets.QHBoxLayout()
        self._outer_layout.setContentsMargins(10, 7, 7, 7)
        self._outer_layout.setSpacing(0)

        self._mode_layout = QtWidgets.QVBoxLayout()
        self._mode_layout.setContentsMargins(0, 0, 0, 0)
        self._mode_layout.setSpacing(0)

        self.show_configuration_menu_btn = CheckableFlatButton('C')

        self.mode_btn_group = QtWidgets.QButtonGroup()
        self.calibration_mode_btn = RotatedCheckableFlatButton('Calibration', self)
        self.calibration_mode_btn.setObjectName('calibration_mode_btn')
        self.calibration_mode_btn.setChecked(True)
        self.mask_mode_btn = RotatedCheckableFlatButton('Mask', self)
        self.mask_mode_btn.setObjectName('mask_mode_btn')
        self.integration_mode_btn = RotatedCheckableFlatButton('Integration', self)
        self.integration_mode_btn.setObjectName('integration_mode_btn')

        self.mode_btn_group.addButton(self.calibration_mode_btn)
        self.mode_btn_group.addButton(self.mask_mode_btn)
        self.mode_btn_group.addButton(self.integration_mode_btn)

        self._mode_layout.addWidget(self.show_configuration_menu_btn)
        self._mode_layout.addSpacerItem(VerticalSpacerItem())
        self._mode_layout.addWidget(self.calibration_mode_btn)
        self._mode_layout.addWidget(self.mask_mode_btn)
        self._mode_layout.addWidget(self.integration_mode_btn)
        self._mode_layout.addSpacerItem(VerticalSpacerItem())

        self._outer_layout.addLayout(self._mode_layout)

        self._inner_layout = QtWidgets.QVBoxLayout()
        self._inner_layout.setContentsMargins(0, 0, 0, 0)
        self._inner_layout.setSpacing(0)

        self.configuration_widget = ConfigurationWidget(self)
        self.configuration_widget.setVisible(False)
        self._inner_layout.addWidget(self.configuration_widget)

        self.tabWidget = QtWidgets.QTabWidget()
        self.tabWidget.setTabPosition(QtWidgets.QTabWidget.West)
        self.tabWidget.setCurrentIndex(0)

        self.main_frame = QtWidgets.QFrame(self)
        self.main_frame.setObjectName("main_frame")
        self._layout_main_frame = QtWidgets.QVBoxLayout()
        self._layout_main_frame.setContentsMargins(6, 10, 6, 6)
        self._layout_main_frame.setSpacing(0)
        self.main_frame.setLayout(self._layout_main_frame)

        self.calibration_widget = CalibrationWidget(self)
        self.mask_widget = MaskWidget(self)
        self.integration_widget = IntegrationWidget(self)

        # self.tabWidget.addTab(self.calibration_widget, 'Calibration')
        # self.tabWidget.addTab(self.mask_widget, 'Mask')
        # self.tabWidget.addTab(self.integration_widget, 'Integration')

        # self._inner_layout.addWidget(self.tabWidget)

        self._layout_main_frame.addWidget(self.calibration_widget)
        self._layout_main_frame.addWidget(self.mask_widget)
        self._layout_main_frame.addWidget(self.integration_widget)

        self.mask_widget.setVisible(False)
        self.integration_widget.setVisible(False)

        self._inner_layout.addWidget(self.main_frame)

        self._outer_layout.addLayout(self._inner_layout)

        self.setLayout(self._outer_layout)

        self.set_system_dependent_stylesheet()
        self.set_stylesheet()

        self.style_widgets()

        self.setWindowIcon(QtGui.QIcon(os.path.join(widget_path, 'icns/icon.svg')))

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

    def style_widgets(self):

        mode_btn_width = 27
        mode_btn_height = 130
        self.calibration_mode_btn.setMaximumWidth(mode_btn_width)
        self.mask_mode_btn.setMaximumWidth(mode_btn_width)
        self.integration_mode_btn.setMaximumWidth(mode_btn_width)

        self.calibration_mode_btn.setMinimumHeight(mode_btn_height)
        self.mask_mode_btn.setMinimumHeight(mode_btn_height)
        self.integration_mode_btn.setMinimumHeight(mode_btn_height)

        self.show_configuration_menu_btn.setMinimumWidth(25)
        self.show_configuration_menu_btn.setMaximumWidth(25)
        self.show_configuration_menu_btn.setMinimumHeight(25)
