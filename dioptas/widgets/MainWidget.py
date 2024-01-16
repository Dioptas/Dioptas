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

import os

from qtpy import QtWidgets, QtGui, QtCore

from .ConfigurationWidget import ConfigurationWidget
from .CalibrationWidget import CalibrationWidget
from .MaskWidget import MaskWidget
from .integration import IntegrationWidget
from .CustomWidgets import RotatedCheckableFlatButton, VerticalSpacerItem, CheckableFlatButton, FlatButton, \
    SaveIconButton, OpenIconButton, ResetIconButton

from .. import style_path, icons_path


class MainWidget(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super(MainWidget, self).__init__(*args, **kwargs)

        self._outer_layout = QtWidgets.QHBoxLayout()
        self._outer_layout.setContentsMargins(0, 7, 7, 7)
        self._outer_layout.setSpacing(0)

        self._left_layout = QtWidgets.QVBoxLayout()
        self._left_layout.setContentsMargins(0, 0, 0, 0)
        self._left_layout.setSpacing(7)

        self._menu_layout = QtWidgets.QVBoxLayout()
        self._menu_layout.setContentsMargins(5, 0, 3, 0)
        self._menu_layout.setSpacing(5)

        self._mode_layout = QtWidgets.QVBoxLayout()
        self._mode_layout.setContentsMargins(10, 0, 0, 0)
        self._mode_layout.setSpacing(0)

        self.show_configuration_menu_btn = CheckableFlatButton('C')
        self.save_btn = SaveIconButton()
        self.load_btn = OpenIconButton()
        self.reset_btn = ResetIconButton()

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

        self._menu_layout.addWidget(self.show_configuration_menu_btn)
        self._menu_layout.addSpacerItem(
            QtWidgets.QSpacerItem(15, 15, QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed))
        self._menu_layout.addWidget(self.load_btn)
        self._menu_layout.addWidget(self.save_btn)
        self._menu_layout.addSpacerItem(
            QtWidgets.QSpacerItem(10, 10, QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed))
        self._menu_layout.addWidget(self.reset_btn)

        self._mode_layout.addWidget(self.calibration_mode_btn)
        self._mode_layout.addWidget(self.mask_mode_btn)
        self._mode_layout.addWidget(self.integration_mode_btn)

        self._left_layout.addLayout(self._menu_layout)
        self._left_layout.addSpacerItem(VerticalSpacerItem())
        self._left_layout.addLayout(self._mode_layout)
        self._left_layout.addSpacerItem(VerticalSpacerItem())
        self._left_layout.setStretch(1, 9)
        self._left_layout.setStretch(3, 18)

        self._outer_layout.addLayout(self._left_layout)

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
        self._layout_main_frame = QtWidgets.QVBoxLayout()
        self._layout_main_frame.setContentsMargins(6, 10, 6, 6)
        self._layout_main_frame.setSpacing(0)
        self.main_frame.setLayout(self._layout_main_frame)

        self.calibration_widget = CalibrationWidget(self)
        self.mask_widget = MaskWidget(self)
        self.integration_widget = IntegrationWidget(self)

        self._layout_main_frame.addWidget(self.calibration_widget)
        self._layout_main_frame.addWidget(self.mask_widget)
        self._layout_main_frame.addWidget(self.integration_widget)

        self.mask_widget.setVisible(False)
        self.integration_widget.setVisible(False)

        self._inner_layout.addWidget(self.main_frame)
        self._outer_layout.addLayout(self._inner_layout)
        self.setLayout(self._outer_layout)

        # self.set_system_dependent_stylesheet()
        # self.set_stylesheet()
        self.style_widgets()
        self.add_tooltips()

        self.setWindowIcon(QtGui.QIcon(os.path.join(icons_path, 'icon.svg')))

    def set_stylesheet(self):
        file = open(os.path.join(style_path, "stylesheet.qss"))
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

        button_height = 30
        button_width = 30
        adjust_height_btns = [self.show_configuration_menu_btn, self.save_btn, self.load_btn, self.reset_btn]
        for btn in adjust_height_btns:
            btn.setHeight(button_height)
            btn.setWidth(button_width)

        adjust_icon_size_btns = adjust_height_btns[1:]
        icon_size = QtCore.QSize(20, 20)
        for btn in adjust_icon_size_btns:
            btn.setIconSize(icon_size)

    def add_tooltips(self):
        self.load_btn.setToolTip('Open Project')
        self.save_btn.setToolTip('Save Project')
        self.reset_btn.setToolTip('Reset Project')
