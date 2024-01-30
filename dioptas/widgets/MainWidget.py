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
from .MapWidget import MapWidget
from .CustomWidgets import (
    VerticalSpacerItem,
    CheckableFlatButton,
    FlatButton,
    VerticalLine,
    HorizontalLine
)

from .. import style_path, icons_path


class MainWidget(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super(MainWidget, self).__init__(*args, **kwargs)

        self._create_layouts()

        self.setLayout(self._outer_layout)

        self._create_menu()
        self._create_mode_menu()

        self._left_layout.addLayout(self._menu_layout)
        self._left_layout.addLayout(self._mode_layout)

        self._outer_layout.addLayout(self._left_layout)
        self._outer_layout.addWidget(VerticalLine())
        self._outer_layout.addLayout(self._content_layout)

        self.configuration_widget = ConfigurationWidget(self)
        self.configuration_widget.setVisible(False)
        self._content_layout.addWidget(self.configuration_widget)

        self.tabWidget = QtWidgets.QTabWidget()
        self.tabWidget.setTabPosition(QtWidgets.QTabWidget.West)
        self.tabWidget.setCurrentIndex(0)

        self._create_main_frame()

        self._style_layouts()
        self.style_widgets()
        self.add_menu_popup()
        self.add_tooltips()

        self._content_layout.addWidget(self.main_frame)
        self.setWindowIcon(QtGui.QIcon(os.path.join(icons_path, "icon.svg")))

    def _style_layouts(self):
        self._outer_layout.setContentsMargins(0, 0, 0, 0)
        self._outer_layout.setStretchFactor(self._left_layout, 0)
        self._outer_layout.setStretchFactor(self._content_layout, 100)
        self._outer_layout.setSpacing(0)
        self._mode_layout.setContentsMargins(0, 0, 0, 0)
        self._mode_layout.setSpacing(0)
        self._content_layout.setSpacing(0)
        self._content_layout.setContentsMargins(0, 6, 0, 0)
        self._left_layout.setContentsMargins(0, 0, 0, 0)
        self._left_layout.setSpacing(6)

    def _create_layouts(self):
        self._outer_layout = QtWidgets.QHBoxLayout()
        self._left_layout = QtWidgets.QVBoxLayout()
        self._content_layout = QtWidgets.QVBoxLayout()
        self._mode_layout = QtWidgets.QVBoxLayout()

    def _create_mode_menu(self):
        self.mode_btn_group = QtWidgets.QButtonGroup()
        self.calibration_mode_btn = CheckableFlatButton("Calib", self)
        self.calibration_mode_btn.setObjectName("calibration_mode_btn")
        self.calibration_mode_btn.setChecked(True)
        self.mask_mode_btn = CheckableFlatButton("Mask", self)
        self.mask_mode_btn.setObjectName("mask_mode_btn")
        self.integration_mode_btn = CheckableFlatButton("Int", self)
        self.integration_mode_btn.setObjectName("integration_mode_btn")
        self.map_mode_btn = CheckableFlatButton("Map", self)
        self.map_mode_btn.setObjectName("map_mode_btn")

        self.mode_btn_group.addButton(self.calibration_mode_btn)
        self.mode_btn_group.addButton(self.mask_mode_btn)
        self.mode_btn_group.addButton(self.integration_mode_btn)
        self.mode_btn_group.addButton(self.map_mode_btn)

        self._mode_layout.addWidget(self.calibration_mode_btn)
        self._mode_layout.addWidget(HorizontalLine())
        self._mode_layout.addWidget(self.mask_mode_btn)
        self._mode_layout.addWidget(HorizontalLine())
        self._mode_layout.addWidget(self.integration_mode_btn)
        self._mode_layout.addWidget(HorizontalLine())
        self._mode_layout.addWidget(self.map_mode_btn)
        self._mode_layout.addSpacerItem(VerticalSpacerItem())

    def _create_menu(self):
        self.menu_btn = QtWidgets.QPushButton("...")
        self.menu_btn.setObjectName("menu_btn")

        self.show_configuration_menu_btn = CheckableFlatButton("C")

        self._menu_layout = QtWidgets.QHBoxLayout()
        self._menu_layout.setContentsMargins(6, 6, 3, 0)
        self._menu_layout.setSpacing(12)

        self._menu_layout.addWidget(self.menu_btn)
        self._menu_layout.addWidget(self.show_configuration_menu_btn)

        self.save_btn = FlatButton("Save Project", self)
        self.load_btn = FlatButton("Open Project", self)
        self.reset_btn = FlatButton("Reset Project", self)

    def _create_main_frame(self):
        self.main_frame = QtWidgets.QWidget(self)
        self._layout_main_frame = QtWidgets.QVBoxLayout()
        self._layout_main_frame.setContentsMargins(0, 10, 6, 6)
        self._layout_main_frame.setSpacing(0)
        self.main_frame.setLayout(self._layout_main_frame)

        self.calibration_widget = CalibrationWidget(self)
        self.mask_widget = MaskWidget(self)
        self.integration_widget = IntegrationWidget(self)
        self.map_widget = MapWidget(self)

        self._layout_main_frame.addWidget(self.calibration_widget)
        self._layout_main_frame.addWidget(self.mask_widget)
        self._layout_main_frame.addWidget(self.integration_widget)
        self._layout_main_frame.addWidget(self.map_widget)

        self.mask_widget.setVisible(False)
        self.integration_widget.setVisible(False)
        self.map_widget.setVisible(False)

        self._content_layout.addWidget(self.main_frame)

        self.style_widgets()
        self.add_tooltips()

        self.setWindowIcon(QtGui.QIcon(os.path.join(icons_path, 'icon.svg')))

    def style_widgets(self):
        self._style_mode_btns()
        self._style_menu_btn()

        button_height = 24
        button_width = 24
        adjust_height_btns = [
            self.show_configuration_menu_btn,
        ]
        for btn in adjust_height_btns:
            btn.setHeight(button_height)
            btn.setWidth(button_width)

    def _style_menu_btn(self):
        self.menu_btn.setFixedWidth(30)
        self.menu_btn.setFixedHeight(30)

    def _style_mode_btns(self):
        mode_btn_width = 75
        mode_btn_height = 75
        mode_btns = [
            self.calibration_mode_btn,
            self.mask_mode_btn,
            self.integration_mode_btn,
            self.map_mode_btn
        ]
        for btn in mode_btns:
            # btn.setCheckable(True)
            btn.setFixedWidth(mode_btn_width)
            btn.setFixedHeight(mode_btn_height)

    def add_menu_popup(self):
        self.menu_btn.clicked.connect(self.show_menu_popup)
        self.show_menu_popup()

    def show_menu_popup(self):
        widget = MenuPopup(self, [self.load_btn, self.save_btn, self.reset_btn])
        btn = self.menu_btn
        widget.adjustSize()
        position = self.mapToGlobal(QtCore.QPoint(btn.x() + btn.width() + 3, btn.y()))
        widget.move(position)
        widget.show()

    def add_tooltips(self):
        self.menu_btn.setToolTip("Project Menu")
        self.show_configuration_menu_btn.setToolTip("Show Configurations")
        self.calibration_mode_btn.setToolTip("Calibration Mode")
        self.mask_mode_btn.setToolTip("Mask Mode")
        self.integration_mode_btn.setToolTip("Integration Mode")



class MenuPopup(QtWidgets.QFrame):
    def __init__(self, parent=None, menu_items=None):
        super(MenuPopup, self).__init__(parent)
        self.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.setFrameShadow(QtWidgets.QFrame.Raised)
        self.setLineWidth(1)
        self.setMidLineWidth(0)
        self.setObjectName("MenuPopup")
        self.setWindowFlags(QtCore.Qt.Popup | QtCore.Qt.FramelessWindowHint)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.setWindowOpacity(0.9)
        self.setFixedWidth(150)
        self._layout = QtWidgets.QVBoxLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self.setLayout(self._layout)

        self.create_menu(menu_items)

    def create_menu(self, menu_items):
        for item in menu_items:
            self._layout.addWidget(item)
