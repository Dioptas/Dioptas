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

from qtpy import QtCore, QtWidgets

from .CustomWidgets import FlatButton, LabelAlignRight


class MoveStageWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(MoveStageWidget, self).__init__(parent)
        self.setWindowTitle("Move")
        self.setGeometry(400, 400, 280, 180)

        self.motors_setup_widget = MotorsSetup(self)

        # create buttons
        self.connect_epics_btn = FlatButton('Connect Epics', self)
        self.move_btn = FlatButton('Move motors', self)
        self.motors_setup_btn = FlatButton('Setup', self)

        # create labels
        self.img_hor_lbl = QtWidgets.QLabel(self)
        self.img_ver_lbl = QtWidgets.QLabel(self)
        self.img_focus_lbl = QtWidgets.QLabel(self)
        self.img_omega_lbl = QtWidgets.QLabel(self)
        self.img_omega_lbl.setStyleSheet('color: yellow')
        self.img_hor_lbl.setStyleSheet('color: yellow')
        self.img_ver_lbl.setStyleSheet('color: yellow')
        self.img_focus_lbl.setStyleSheet('color: yellow')

        self.hor_lbl = QtWidgets.QLabel(self)
        self.ver_lbl = QtWidgets.QLabel(self)
        self.focus_lbl = QtWidgets.QLabel(self)
        self.omega_lbl = QtWidgets.QLabel(self)

        # Create checkboxes
        self.move_hor_cb = QtWidgets.QCheckBox(self)
        self.move_ver_cb = QtWidgets.QCheckBox(self)
        self.move_focus_cb = QtWidgets.QCheckBox(self)
        self.move_omega_cb = QtWidgets.QCheckBox(self)

        # Create grid layout
        grid_layout = QtWidgets.QGridLayout()
        grid_layout.setVerticalSpacing(10)
        grid_layout.setHorizontalSpacing(20)
        grid_layout.addWidget(LabelAlignRight("Current Position:"), 0, 0, 1, 2)
        grid_layout.addWidget(LabelAlignRight("Image Position:"), 0, 2)
        grid_layout.addWidget(LabelAlignRight("Move?"), 0, 3)

        grid_layout.addWidget(LabelAlignRight('Hor:'), 1, 0)
        grid_layout.addWidget(self.hor_lbl, 1, 1)
        grid_layout.addWidget(self.img_hor_lbl, 1, 2)
        grid_layout.addWidget(self.move_hor_cb, 1, 3)

        grid_layout.addWidget(LabelAlignRight("Ver:"), 2, 0)
        grid_layout.addWidget(self.ver_lbl, 2, 1)
        grid_layout.addWidget(self.img_ver_lbl, 2, 2)
        grid_layout.addWidget(self.move_ver_cb, 2, 3)

        grid_layout.addWidget(LabelAlignRight("Focus:"), 3, 0)
        grid_layout.addWidget(self.focus_lbl, 3, 1)
        grid_layout.addWidget(self.img_focus_lbl, 3, 2)
        grid_layout.addWidget(self.move_focus_cb, 3, 3)

        grid_layout.addWidget(LabelAlignRight("Omega:"), 4, 0)
        grid_layout.addWidget(self.omega_lbl, 4, 1)
        grid_layout.addWidget(self.img_omega_lbl, 4, 2)
        grid_layout.addWidget(self.move_omega_cb, 4, 3)

        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addWidget(self.connect_epics_btn)
        btn_layout.addWidget(self.move_btn)
        btn_layout.addWidget(self.motors_setup_btn)

        self._main_layout = QtWidgets.QVBoxLayout()
        self._main_layout.addLayout(grid_layout)
        self._main_layout.addLayout(btn_layout)

        self.setLayout(self._main_layout)

        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.MSWindowsFixedSizeDialogHint)
        self.setAttribute(QtCore.Qt.WA_MacAlwaysShowToolWindow)

    def raise_widget(self):
        self.show()
        self.setWindowState(self.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
        self.activateWindow()
        self.raise_()


class MotorsSetup(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(MotorsSetup, self).__init__(parent)

        self.setWindowTitle("Motors setup")

        self.hor_lbl = LabelAlignRight('Hor:', self)
        self.ver_lbl = LabelAlignRight('Ver:', self)
        self.focus_lbl = LabelAlignRight('Focus:', self)
        self.omega_lbl = LabelAlignRight('Omega:', self)

        self.hor_motor_txt = QtWidgets.QLineEdit(self)
        self.ver_motor_txt = QtWidgets.QLineEdit(self)
        self.focus_motor_txt = QtWidgets.QLineEdit(self)
        self.omega_motor_txt = QtWidgets.QLineEdit(self)

        self.set_motor_names_btn = QtWidgets.QPushButton('Set', self)
        self.reread_config_btn = QtWidgets.QPushButton('Default config', self)

        grid = QtWidgets.QGridLayout()
        grid.setVerticalSpacing(10)
        grid.setHorizontalSpacing(10)

        grid.addWidget(self.hor_lbl, 1, 0)
        grid.addWidget(self.ver_lbl, 2, 0)
        grid.addWidget(self.focus_lbl, 3, 0)
        grid.addWidget(self.omega_lbl, 4, 0)
        grid.addWidget(self.hor_motor_txt, 1, 1)
        grid.addWidget(self.ver_motor_txt, 2, 1)
        grid.addWidget(self.focus_motor_txt, 3, 1)
        grid.addWidget(self.omega_motor_txt, 4, 1)
        grid.addWidget(self.set_motor_names_btn, 5, 1)
        grid.addWidget(self.reread_config_btn, 5, 0)

        self.setLayout(grid)
        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.MSWindowsFixedSizeDialogHint)
        self.setAttribute(QtCore.Qt.WA_MacAlwaysShowToolWindow)

    def raise_widget(self):
        self.show()
        self.setWindowState(self.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
        self.activateWindow()
        self.raise_()

    def return_motor_names(self):
        return str(self.hor_motor_txt.text()), str(self.ver_motor_txt.text()), str(self.focus_motor_txt.text()), str(
            self.omega_motor_txt.text())
