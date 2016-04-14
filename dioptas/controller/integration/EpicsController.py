# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
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

from PyQt4 import QtCore, QtGui
try:
    import epics
except ImportError:
    epics = None

from .econfig import epics_config
import numpy as np

from widgets.integration import IntegrationWidget
from model.ImgModel import ImgModel


class EpicsController(object):

    def __init__(self, widget, img_model):
        """
        :param widget: Reference to IntegrationWidget
        :param img_model: Reference to ImgModel object

        :type widget: IntegrationWidget
        :type img_model: ImgModel
        """

        self.widget = widget
        self.img_model = img_model

        self.move_widget = widget.move_widget

        # Create timer
        self.epics_update_timer = QtCore.QTimer(self.widget)
        self.epics_update_timer.timeout.connect(self.connect_epics)

        # read epics_config
        self.hor_motor_name = epics_config['sample_position_x']
        self.ver_motor_name = epics_config['sample_position_y']
        self.focus_motor_name = epics_config['sample_position_z']
        self.omega_motor_name = epics_config['sample_position_omega']

        self.connect_signals()

    def connect_signals(self):
        self.img_model.img_changed.connect(self.update_image_position)

        self.widget.move_widget_btn.clicked.connect(self.widget.move_widget.raise_widget)
        self.widget.move_widget.connect_epics_btn.clicked.connect(self.connect_epics)
        self.widget.move_widget.move_btn.clicked.connect(self.move_stage)
        self.widget.move_widget.motors_setup_btn.clicked.connect(self.open_motors_setup_widget)

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

        self.widget.hor_lbl.setText(str(hor))
        self.widget.ver_lbl.setText(str(ver))
        self.widget.focus_lbl.setText(str(focus))
        self.widget.omega_lbl.setText(str(omega))

    def update_image_position(self):
        try:
            self.move_widget.img_hor_lbl.setText(self.img_model.motors_info['Horizontal'])
            self.move_widget.img_ver_lbl.setText(self.img_model.motors_info['Vertical'])
            self.move_widget.img_focus_lbl.setText(self.img_model.motors_info['Focus'])
            self.move_widget.img_omega_lbl.setText(self.img_model.motors_info['Omega'])
        except KeyError:
            self.move_widget.img_hor_lbl.setText("")
            self.move_widget.img_ver_lbl.setText("")
            self.move_widget.img_focus_lbl.setText("")
            self.move_widget.img_omega_lbl.setText("")

    def move_stage(self):

        hor_pos = float(self.move_widget.img_hor_lbl.text())
        ver_pos = float(self.move_widget.img_ver_lbl.text())
        focus_pos = float(self.move_widget.img_focus_lbl.text())
        omega_pos =float(self.widget.img_omega_lbl.text())

        if self.check_sample_point_distances(hor_pos, ver_pos, focus_pos):
            if self.move_widget.move_hor_cb.isChecked():
                epics.caput(self.hor_motor_name + '.VAL', hor_pos)
            if self.move_widget.widget.move_ver_cb.isChecked():
                epics.caput(self.ver_motor_name + '.VAL', ver_pos)
            if self.move_widget.move_focus_cb.isChecked():
                epics.caput(self.focus_motor_name + '.VAL', focus_pos)
            if self.move_widget.move_omega_cb.isChecked():
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
        self.move_widget.motors_setup_widget.setGeometry(400, 680, 280, 180)
        self.move_widget.motors_setup_widget.hor_motor_txt.setText(self.hor_motor_name)
        self.move_widget.motors_setup_widget.ver_motor_txt.setText(self.ver_motor_name)
        self.move_widget.motors_setup_widget.focus_motor_txt.setText(self.focus_motor_name)
        self.move_widget.motors_setup_widget.omega_motor_txt.setText(self.omega_motor_name)
        self.move_widget.motors_setup_widget.show()
        self.move_widget.motors_setup_widget.set_motor_names_btn.clicked.connect(self.get_motors)
        self.move_widget.motors_setup_widget.reread_config_btn.clicked.connect(self.get_motors)

    def get_motors(self):
        self.hor_motor_name, self.ver_motor_name, self.focus_motor_name, self.omega_motor_name = \
            self.move_widget.motors_setup_widget.return_motor_names()
        self.connect_epics()

    def closeEvent(self, QCloseEvent):
        print('hm')
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

    def check_sample_point_distances(self, pos_x, pos_y, pos_z):
        cur_x = float(epics.caget(self.hor_motor_name + '.RBV', as_string=True))
        cur_y = float(epics.caget(self.ver_motor_name + '.RBV', as_string=True))
        cur_z = float(epics.caget(self.focus_motor_name + '.RBV', as_string=True))

        largest_distance = np.sqrt((float(pos_x) - cur_x) ** 2 + (float(pos_y) - cur_y) ** 2 + (float(pos_z) - cur_z) ** 2)

        if largest_distance > 0.2:
            reply = self.show_continue_abort_message_box(
                'Current and image positions are far away from each other. Are you sure, you want to move?')
            if reply == QtGui.QMessageBox.Abort:
                return False

        return True

