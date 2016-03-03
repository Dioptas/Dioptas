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
import os
import time
import datetime
from CustomWidgets import FlatButton
from econfig import epics_config

try:
    import epics
except ImportError:
    epics = None

widget_path = os.path.dirname(__file__)


class CifConversionParametersDialog(QtGui.QDialog):
    """
    Dialog which is asking for Intensity Cutoff and minimum d-spacing when loading cif files.
    """

    def __init__(self, parent):
        super(CifConversionParametersDialog, self).__init__()

        self._parent = parent
        self._create_widgets()
        self._layout_widgets()
        self._style_widgets()

        self._connect_widgets()

    def _create_widgets(self):
        """
        Creates all necessary widgets.
        """
        self.int_cutoff_lbl = QtGui.QLabel("Intensity Cutoff:")
        self.min_d_spacing_lbl = QtGui.QLabel("Minimum d-spacing:")

        self.int_cutoff_txt = QtGui.QLineEdit("0.5")
        self.int_cutoff_txt.setToolTip("Reflections with lower Intensity won't be considered.")
        self.min_d_spacing_txt = QtGui.QLineEdit("0.5")
        self.min_d_spacing_txt.setToolTip("Reflections with smaller d_spacing won't be considered.")

        self.int_cutoff_unit_lbl = QtGui.QLabel("%")
        self.min_d_spacing_unit_lbl = QtGui.QLabel("A")

        self.ok_btn = FlatButton("OK")

    def _layout_widgets(self):
        """
        Layouts the widgets into a gridlayout
        """
        self._layout = QtGui.QGridLayout()
        self._layout.addWidget(self.int_cutoff_lbl, 0, 0)
        self._layout.addWidget(self.int_cutoff_txt, 0, 1)
        self._layout.addWidget(self.int_cutoff_unit_lbl, 0, 2)
        self._layout.addWidget(self.min_d_spacing_lbl, 1, 0)
        self._layout.addWidget(self.min_d_spacing_txt, 1, 1)
        self._layout.addWidget(self.min_d_spacing_unit_lbl, 1, 2)
        self._layout.addWidget(self.ok_btn, 2, 1, 1, 2)

        self.setLayout(self._layout)

    def _style_widgets(self):
        """
        Makes everything pretty and set Double validators for the line edits.
        """
        self.int_cutoff_lbl.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.int_cutoff_txt.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.int_cutoff_txt.setMaximumWidth(40)
        self.min_d_spacing_lbl.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.min_d_spacing_txt.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.min_d_spacing_txt.setMaximumWidth(40)

        self.int_cutoff_txt.setValidator(QtGui.QDoubleValidator())
        self.min_d_spacing_txt.setValidator(QtGui.QDoubleValidator())

        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)

        file = open(os.path.join(widget_path, "stylesheet.qss"))
        stylesheet = file.read()
        self.setStyleSheet(stylesheet)
        file.close()

    def _connect_widgets(self):
        """
        Connecting actions to slots.
        """
        self.ok_btn.clicked.connect(self.accept)

    @property
    def int_cutoff(self):
        """
        Returns the intensity cutoff selected in the dialog.
        """
        return float(str(self.int_cutoff_txt.text()))

    @property
    def min_d_spacing(self):
        """
        Returns the minimum d-spacing selected in the dialog.
        """
        return float(str(self.min_d_spacing_txt.text()))

    def exec_(self):
        """
        Overwriting the dialog exec_ function to center the widget in the parent window before execution.
        """
        parent_center = self._parent.window().mapToGlobal(self._parent.window().rect().center())
        self.move(parent_center.x() - 101, parent_center.y() - 48)
        super(CifConversionParametersDialog, self).exec_()


class FileInfoWidget(QtGui.QWidget):
    def __init__(self, parent=None):
        super(FileInfoWidget, self).__init__(parent)
        self.setWindowTitle("File Info")

        self.text_lbl = QtGui.QLabel()
        self.text_lbl.setWordWrap(True)

        self._layout = QtGui.QVBoxLayout()
        self._layout.setContentsMargins(5, 5, 5, 5)
        self._layout.addWidget(self.text_lbl)
        self._layout.setSizeConstraint(QtGui.QLayout.SetFixedSize)

        self.setStyleSheet(
            """
            QWidget{
                background: rgb(0,0,0);
            }
            QLabel{
                color: #00DD00;
            }"""
        )
        self.setLayout(self._layout)
        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowCloseButtonHint |
                            QtCore.Qt.CustomizeWindowHint | QtCore.Qt.MSWindowsFixedSizeDialogHint |
                            QtCore.Qt.X11BypassWindowManagerHint)
        self.setAttribute(QtCore.Qt.WA_MacAlwaysShowToolWindow)

    def raise_widget(self):
        self.show()
        self.setWindowState(self.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
        self.activateWindow()
        self.raise_()

class MoveStageWidget(QtGui.QWidget):
    def __init__(self, parent=None):
        super(MoveStageWidget, self).__init__(parent)
        self.setWindowTitle("Move")
        self.setGeometry(400, 400, 370, 180)
        self.connect_epics_btn = QtGui.QPushButton('Refresh', self)
        self.connect_epics_btn.move(5,155)

        self.move_btn = QtGui.QPushButton(self)
        self.move_btn.setText('Move motors')
        self.move_btn.move(250, 155)

        self.img_pos_label = QtGui.QLabel(self)
        self.img_pos_label.move(200,5)
        self.img_pos_label.setText('Image motor postions:')

        self.img_hor_label = QtGui.QLabel(self)
        self.img_hor_label.move(200,35)
        self.img_ver_label = QtGui.QLabel(self)
        self.img_ver_label.move(200,65)
        self.img_focus_label = QtGui.QLabel(self)
        self.img_focus_label.move(200,95)
        self.img_hor_label.setText("Hor: " )
        self.img_ver_label.setText("Ver:  " )
        self.img_focus_label.setText("Focus: ")
        self.img_omega_label = QtGui.QLabel(self)
        self.img_omega_label.setText("Omega: ")
        self.img_omega_label.move(200,125)


        self.img_hor_lbl = QtGui.QLabel(self)
        self.img_hor_lbl.move(250,35)
        self.img_ver_lbl = QtGui.QLabel(self)
        self.img_ver_lbl.move(250,65)
        self.img_focus_lbl = QtGui.QLabel(self)
        self.img_focus_lbl.move(250,95)
        self.img_omega_lbl = QtGui.QLabel(self)
        self.img_omega_lbl.move(250,125)


        self.cur_pos_label = QtGui.QLabel(self)
        self.cur_pos_label.move(5,5)
        self.cur_pos_label.setText('Current motor positions:')
        self.hor_label = QtGui.QLabel(self)
        self.hor_label.move(5,35)
        self.ver_label = QtGui.QLabel(self)
        self.ver_label.move(5,65)
        self.focus_label = QtGui.QLabel(self)
        self.focus_label.move(5,95)
        self.hor_label.setText("Hor:                          " )
        self.ver_label.setText("Ver:                          " )
        self.focus_label.setText("Focus:                      ")
        self.omega_label = QtGui.QLabel(self)
        self.omega_label.move(5,125)
        self.omega_label.setText("Omega:                       ")


        self.move_hor_cb = QtGui.QCheckBox(self)
        self.move_hor_cb.move(330,35)
        self.move_hor_cb.setChecked(True)
        self.move_ver_cb = QtGui.QCheckBox(self)
        self.move_ver_cb.move(330,65)
        self.move_ver_cb.setChecked(True)
        self.move_focus_cb = QtGui.QCheckBox(self)
        self.move_focus_cb.move(330,95)
        self.move_omega_cb = QtGui.QCheckBox(self)
        self.move_omega_cb.move(330,125)

        self.file_creation_date = 'March 03, 2016 14:01:36'


        self.connect_buttons()


        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowCloseButtonHint |
                            QtCore.Qt.CustomizeWindowHint | QtCore.Qt.MSWindowsFixedSizeDialogHint |
                            QtCore.Qt.X11BypassWindowManagerHint)
        self.setAttribute(QtCore.Qt.WA_MacAlwaysShowToolWindow)

    def raise_widget(self):
        self.show()
        self.setWindowState(self.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
        self.activateWindow()
        self.connect_epics()
        self.epics_update_timer = QtCore.QTimer(self)
        self.epics_update_timer.timeout.connect(self.connect_epics)
        self.epics_update_timer.start(1000)
        self.raise_()

    def connect_buttons(self):
        self.connect_epics_btn.clicked.connect(self.connect_epics)
        self.move_btn.clicked.connect(self.move_stage)

    def connect_epics(self):

        ver = epics.caget(epics_config['sample_position_y'], as_string=True)
        hor = epics.caget(epics_config['sample_position_x'], as_string=True)
        focus = epics.caget(epics_config['sample_position_z'], as_string=True)
        omega = epics.caget(epics_config['sample_position_omega'], as_string=True)
        self.hor_label.setText('Hor:      ' + str(hor))
        self.ver_label.setText('Ver:      ' + str(ver))
        self.focus_label.setText('Focus:   ' + str(focus))
        self.omega_label.setText('Omega: ' + str(omega))

    def checktime(self):
        file_date = datetime.datetime.strptime(self.file_creation_date, "%B %d, %Y %H:%M:%S")
        now = datetime.datetime.strptime(time.strftime("%B %d, %Y %H:%M:%S", time.localtime()), "%B %d, %Y %H:%M:%S")

        if (now - file_date).total_seconds() > 36000:
            reply = self.show_continue_abort_message_box('This file was created more than 10 hours ago. Are you sure, you want to move motors?')
            if reply == QtGui.QMessageBox.Abort:
                return False
        return True

    def move_stage(self):
        if self.checktime():
            if self.move_hor_cb.isChecked():
                hor_value = self.img_hor_lbl.text()
                hor_pos = '%.3f' % float(hor_value)
                epics.caput(epics_config['sample_position_x'], hor_pos)
            if self.move_ver_cb.isChecked():
                ver_value = self.img_ver_lbl.text()
                ver_pos = '%.3f' % float(ver_value)
                epics.caput(epics_config['sample_position_y'], ver_pos)
            if self.move_focus_cb.isChecked():
                focus_value = self.img_focus_lbl.text()
                focus_pos = '%.3f' % float(focus_value)
                epics.caput(epics_config['sample_position_z'], focus_pos)
            if self.move_omega_cb.isChecked():
                if self.check_conditions() is False:
                    self.show_error_message_box('If you want to rotate the stage, please move mirrors and microscope in the right positions!')
                    return
                else:
                    omega_value = self.img_omega_lbl.text()
                    omega_pos = '%.3f' % float(omega_value)
                    epics.caput(epics_config['sample_position_omega'], omega_pos)

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

if __name__ == '__main__':
    app = QtGui.QApplication([])
    widget = CifConversionParametersDialog(None)
    widget.show()
    widget.raise_()
    app.exec_()
