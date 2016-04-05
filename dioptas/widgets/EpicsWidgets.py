# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
# Copyright (C) 2016  Clemens Prescher (clemens.prescher@gmail.com)
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

from PyQt4 import QtCore, QtGui

from .CustomWidgets import FlatButton, LabelAlignRight


class MoveStageWidget(QtGui.QWidget):
    def __init__(self, parent=None):
        super(MoveStageWidget, self).__init__(parent)
        self.setWindowTitle("Move")
        self.setGeometry(400, 400, 280, 180)

        self.motors_setup_widget = MotorsSetup(self)

        # create buttons
        self.connect_epics_btn = FlatButton('Connect Epics', self)
        self.move_btn = FlatButton('Move motors', self)
        self.motors_setup_btn = FlatButton('Setup', self)

        # Create labels
        self.img_pos_label = QtGui.QLabel(self)
        self.img_pos_label.setText('Image postions:')

        self.move_lbl = QtGui.QLabel(self)
        self.move_lbl.setText('Move:')

        self.img_hor_lbl = QtGui.QLabel(self)
        self.img_ver_lbl = QtGui.QLabel(self)
        self.img_focus_lbl = QtGui.QLabel(self)
        self.img_omega_lbl = QtGui.QLabel(self)
        self.img_omega_lbl.setStyleSheet('color: yellow')
        self.img_hor_lbl.setStyleSheet('color: yellow')
        self.img_ver_lbl.setStyleSheet('color: yellow')
        self.img_focus_lbl.setStyleSheet('color: yellow')

        self.cur_pos_label = QtGui.QLabel(self)
        self.cur_pos_label.setText('Current positions:')
        self.hor_label = QtGui.QLabel(self)
        self.ver_label = QtGui.QLabel(self)
        self.focus_label = QtGui.QLabel(self)
        self.hor_label.setText("Hor:")
        self.ver_label.setText("Ver:")
        self.focus_label.setText("Focus:")
        self.omega_label = QtGui.QLabel(self)
        self.omega_label.setText("Omega:")

        # Create checkboxes

        self.move_hor_cb = QtGui.QCheckBox(self)
        self.move_ver_cb = QtGui.QCheckBox(self)
        self.move_focus_cb = QtGui.QCheckBox(self)
        self.move_omega_cb = QtGui.QCheckBox(self)

        # Create grid

        grid = QtGui.QGridLayout()
        grid.setVerticalSpacing(10)
        grid.setHorizontalSpacing(20)
        grid.addWidget(self.cur_pos_label, 1, 0, 1, 1)
        grid.addWidget(self.hor_label, 2, 0)
        grid.addWidget(self.ver_label, 3, 0)
        grid.addWidget(self.focus_label, 4, 0)
        grid.addWidget(self.omega_label, 5, 0)
        grid.addWidget(self.connect_epics_btn, 6, 0, 1, 1)
        grid.addWidget(self.move_lbl, 1, 2)
        grid.addWidget(self.img_pos_label, 1, 1)
        grid.addWidget(self.move_btn, 6, 1, 1, 1)
        grid.addWidget(self.img_hor_lbl, 2, 1)
        grid.addWidget(self.img_ver_lbl, 3, 1)
        grid.addWidget(self.img_focus_lbl, 4, 1)
        grid.addWidget(self.img_omega_lbl, 5, 1)
        grid.addWidget(self.move_hor_cb, 2, 2)
        grid.addWidget(self.move_ver_cb, 3, 2)
        grid.addWidget(self.move_focus_cb, 4, 2)
        grid.addWidget(self.move_omega_cb, 5, 2)
        grid.addWidget(self.motors_setup_btn, 6, 2)

        self.setLayout(grid)

        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.MSWindowsFixedSizeDialogHint)
        self.setAttribute(QtCore.Qt.WA_MacAlwaysShowToolWindow)

    def raise_widget(self):
        self.show()
        self.setWindowState(self.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
        self.activateWindow()
        self.raise_()


class MotorsSetup(QtGui.QWidget):
    def __init__(self, parent=None):
        super(MotorsSetup, self).__init__(parent)

        self.setWindowTitle("Motors setup")

        self.hor_lbl = LabelAlignRight('Hor:', self)
        self.ver_lbl = LabelAlignRight('Ver:', self)
        self.focus_lbl = LabelAlignRight('Focus:', self)
        self.omega_lbl = LabelAlignRight('Omega:', self)

        self.hor_motor_txt = QtGui.QLineEdit(self)
        self.ver_motor_txt = QtGui.QLineEdit(self)
        self.focus_motor_txt = QtGui.QLineEdit(self)
        self.omega_motor_txt = QtGui.QLineEdit(self)

        self.set_motor_names_btn = QtGui.QPushButton('Set', self)
        self.reread_config_btn = QtGui.QPushButton('Default config', self)

        grid = QtGui.QGridLayout()
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

        self.reread_config_btn.clicked.connect(self.reread_config)

        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.MSWindowsFixedSizeDialogHint)
        self.setAttribute(QtCore.Qt.WA_MacAlwaysShowToolWindow)
        self.setWindowState(self.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
        self.activateWindow()

    def return_motor_names(self):
        return str(self.hor_motor_txt.text()), str(self.ver_motor_txt.text()), str(self.focus_motor_txt.text()), str(
            self.omega_motor_txt.text())

    def reread_config(self):
        self.hor_motor_txt.setText(epics_config['sample_position_x'])
        self.ver_motor_txt.setText(epics_config['sample_position_y'])
        self.focus_motor_txt.setText(epics_config['sample_position_z'])
        self.omega_motor_txt.setText(epics_config['sample_position_omega'])


