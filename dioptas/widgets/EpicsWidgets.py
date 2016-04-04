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
import numpy as np

try:
    import epics
except ImportError:
    epics = None

from .CustomWidgets import FlatButton, LabelAlignRight
from .econfig import epics_config



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

        # Create timer

        self.epics_update_timer = QtCore.QTimer(self)
        self.epics_update_timer.timeout.connect(self.connect_epics)

        # read epics_config
        self.hor_motor_name = epics_config['sample_position_x']
        self.ver_motor_name = epics_config['sample_position_y']
        self.focus_motor_name = epics_config['sample_position_z']
        self.omega_motor_name = epics_config['sample_position_omega']

        self.setLayout(grid)
        self.connect_buttons()

        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.MSWindowsFixedSizeDialogHint)

        self.setAttribute(QtCore.Qt.WA_MacAlwaysShowToolWindow)

    def raise_widget(self):
        self.show()
        self.setWindowState(self.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
        self.activateWindow()
        self.raise_()

    def connect_buttons(self):
        self.connect_epics_btn.clicked.connect(self.connect_epics)
        self.move_btn.clicked.connect(self.move_stage)
        self.motors_setup_btn.clicked.connect(self.open_motors_setup_widget)

    def connect_epics(self):
        hor = epics.caget(self.hor_motor_name + '.RBV', as_string=True)
        ver = epics.caget(self.ver_motor_name + '.RBV', as_string=True)
        focus = epics.caget(self.focus_motor_name + '.RBV', as_string=True)
        omega = epics.caget(self.omega_motor_name + '.RBV', as_string=True)

        if ver is not None and hor is not None and focus is not None and omega is not None:
            self.epics_update_timer.start(1000)
        else:
            if self.epics_update_timer.isActive():
                self.epics_update_timer.stop()

        self.hor_label.setText('Hor:        ' + str(hor))
        self.ver_label.setText('Ver:        ' + str(ver))
        self.focus_label.setText('Focus:     ' + str(focus))
        self.omega_label.setText('Omega:   ' + str(omega))

    def move_stage(self):

        hor_value = self.img_hor_lbl.text()
        hor_pos = '%.3f' % float(hor_value)
        ver_value = self.img_ver_lbl.text()
        ver_pos = '%.3f' % float(ver_value)
        focus_value = self.img_focus_lbl.text()
        focus_pos = '%.3f' % float(focus_value)
        omega_value = self.img_omega_lbl.text()
        omega_pos = '%.3f' % float(omega_value)

        if self.check_sample_point_distances(hor_pos, ver_pos, focus_pos):
            if self.move_hor_cb.isChecked():
                epics.caput(self.hor_motor_name + '.VAL', hor_pos)
            if self.move_ver_cb.isChecked():
                epics.caput(self.ver_motor_name + '.VAL', ver_pos)
            if self.move_focus_cb.isChecked():
                epics.caput(self.focus_motor_name + '.VAL', focus_pos)
            if self.move_omega_cb.isChecked():
                if self.check_conditions() is False:
                    self.show_error_message_box(
                        'If you want to rotate the stage, please move mirrors and microscope in the right positions!')
                    return
                elif float(omega_pos) > -45.0 or float(omega_pos) < -135.0:
                    self.show_error_message_box('Requested omega angle is not within the limits')
                    return
                else:
                    epics.caput(self.omega_motor_name + '.VAL', omega_pos)

    def open_motors_setup_widget(self):
        self.motors_setup_widget.setGeometry(400, 680, 280, 180)
        self.motors_setup_widget.hor_motor_txt.setText(self.hor_motor_name)
        self.motors_setup_widget.ver_motor_txt.setText(self.ver_motor_name)
        self.motors_setup_widget.focus_motor_txt.setText(self.focus_motor_name)
        self.motors_setup_widget.omega_motor_txt.setText(self.omega_motor_name)
        self.motors_setup_widget.show()
        self.motors_setup_widget.set_motor_names_btn.clicked.connect(self.get_motors)
        self.motors_setup_widget.reread_config_btn.clicked.connect(self.get_motors)

    def get_motors(self):
        self.hor_motor_name, self.ver_motor_name, self.focus_motor_name, self.omega_motor_name = \
            self.motors_setup_widget.return_motor_names()
        self.connect_epics()

    def closeEvent(self, QCloseEvent):
        self.epics_update_timer.stop()

    @staticmethod
    def check_conditions():
        if int(epics.caget('13IDD:m24.RBV')) > -105:
            return False
        elif int(epics.caget('13IDD:m23.RBV')) > -105:
            return False
        elif int(epics.caget('13IDD:m67.RBV')) > -65:
            return False
        return True

    @staticmethod
    def show_error_message_box(msg):
        msg_box = QtGui.QMessageBox()
        msg_box.setWindowFlags(QtCore.Qt.Tool)
        msg_box.setText(msg)
        msg_box.setIcon(QtGui.QMessageBox.Critical)
        msg_box.setWindowTitle('Error')
        msg_box.setStandardButtons(QtGui.QMessageBox.Ok)
        msg_box.setDefaultButton(QtGui.QMessageBox.Ok)
        msg_box.exec_()

    @staticmethod
    def show_continue_abort_message_box(msg):
        msg_box = QtGui.QMessageBox()
        msg_box.setWindowFlags(QtCore.Qt.Tool)
        msg_box.setText("<p align='center' style='font-size:20px' >{}</p>".format(msg))
        msg_box.setIcon(QtGui.QMessageBox.Critical)
        msg_box.setWindowTitle('Continue?')
        msg_box.setStandardButtons(QtGui.QMessageBox.Yes | QtGui.QMessageBox.Abort)
        msg_box.setDefaultButton(QtGui.QMessageBox.Abort)
        msg_box.exec_()
        return msg_box.result()

    def check_sample_point_distances(self, posx, posy, posz):
        curx = float(epics.caget(self.hor_motor_name + '.RBV', as_string=True))
        cury = float(epics.caget(self.ver_motor_name + '.RBV', as_string=True))
        curz = float(epics.caget(self.focus_motor_name + '.RBV', as_string=True))

        largest_distance = np.sqrt((float(posx) - curx) ** 2 + (float(posy) - cury) ** 2 + (float(posz) - curz) ** 2)

        if largest_distance > 0.2:
            reply = self.show_continue_abort_message_box(
                'Current and image positions are far away from each other. Are you sure, you want to move?')
            if reply == QtGui.QMessageBox.Abort:
                return False

        return True


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


