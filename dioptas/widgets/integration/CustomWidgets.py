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

from PyQt5 import QtWidgets, QtGui

from ..CustomWidgets import LabelAlignRight, FlatButton


class MouseCurrentAndClickedWidget(QtWidgets.QWidget):
    def __init__(self, clicked_color):
        super(MouseCurrentAndClickedWidget, self).__init__()

        self._layout = QtWidgets.QVBoxLayout()
        self._layout.setSpacing(0)

        self.cur_pos_widget = MousePositionWidget()
        self.clicked_pos_widget = MousePositionWidget(clicked_color)

        self._layout.addWidget(self.cur_pos_widget)
        self._layout.addWidget(self.clicked_pos_widget)

        self.setLayout(self._layout)


class MousePositionWidget(QtWidgets.QWidget):
    def __init__(self, color=None):
        super(MousePositionWidget, self).__init__()

        self._layout = QtWidgets.QHBoxLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)

        self.x_pos_lbl = QtWidgets.QLabel('X:')
        self.y_pos_lbl = QtWidgets.QLabel('Y:')
        self.int_lbl = QtWidgets.QLabel('I:')

        self._layout.addWidget(self.x_pos_lbl)
        self._layout.addWidget(self.y_pos_lbl)
        self._layout.addWidget(self.int_lbl)

        self.setLayout(self._layout)
        self.style_widgets(color)

    def style_widgets(self, color):
        main_style_str = """
            QLabel {
                min-width: 70px;
            }
        """
        self.setStyleSheet(main_style_str)

        if color is not None:
            style_str = 'color: {};'.format(color)
            self.x_pos_lbl.setStyleSheet(style_str)
            self.y_pos_lbl.setStyleSheet(style_str)
            self.int_lbl.setStyleSheet(style_str)


class MouseUnitCurrentAndClickedWidget(QtWidgets.QWidget):
    def __init__(self, clicked_color):
        super(MouseUnitCurrentAndClickedWidget, self).__init__()
        self._layout = QtWidgets.QVBoxLayout()
        self._layout.setSpacing(0)

        self.cur_unit_widget = MouseUnitWidget()
        self.clicked_unit_widget = MouseUnitWidget(clicked_color)

        self._layout.addWidget(self.cur_unit_widget)
        self._layout.addWidget(self.clicked_unit_widget)

        self.setLayout(self._layout)


class MouseUnitWidget(QtWidgets.QWidget):
    def __init__(self, color=None):
        super(MouseUnitWidget, self).__init__()

        self._layout = QtWidgets.QHBoxLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)

        self.tth_lbl = QtWidgets.QLabel(u"2θ:")
        self.q_lbl = QtWidgets.QLabel('Q:')
        self.d_lbl = QtWidgets.QLabel('d:')
        self.azi_lbl = QtWidgets.QLabel('X:')

        self._layout.addWidget(self.tth_lbl)
        self._layout.addWidget(self.q_lbl)
        self._layout.addWidget(self.d_lbl)
        self._layout.addWidget(self.azi_lbl)

        self.setLayout(self._layout)
        self.style_widgets(color)

    def style_widgets(self, color):
        main_style_str = """
            QLabel {
                min-width: 70px;
            }
        """
        self.setStyleSheet(main_style_str)

        if color is not None:
            style_str = 'color: {};'.format(color)
            self.tth_lbl.setStyleSheet(style_str)
            self.d_lbl.setStyleSheet(style_str)
            self.q_lbl.setStyleSheet(style_str)
            self.azi_lbl.setStyleSheet(style_str)


class BrowseFileWidget(QtWidgets.QWidget):
    def __init__(self, files, checkbox_text):
        super(BrowseFileWidget, self).__init__()

        self._layout = QtWidgets.QGridLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setVerticalSpacing(6)
        self._layout.setHorizontalSpacing(12)

        self.load_btn = FlatButton('Load {}(s)'.format(files))
        self.file_cb = QtWidgets.QCheckBox(checkbox_text)
        self.next_btn = FlatButton('>')
        self.previous_btn = FlatButton('<')
        self.step_txt = QtWidgets.QLineEdit('1')
        self.step_txt.setValidator(QtGui.QIntValidator())
        self.browse_by_name_rb = QtWidgets.QRadioButton('By Name')
        self.browse_by_name_rb.setChecked(True)
        self.browse_by_time_rb = QtWidgets.QRadioButton('By Time')
        self.directory_txt = QtWidgets.QLineEdit('')
        self.directory_btn = FlatButton('...')
        self.file_txt = QtWidgets.QLineEdit('')

        self._layout.addWidget(self.load_btn, 0, 0)
        self._layout.addWidget(self.file_cb, 1, 0)

        self._layout.addWidget(self.previous_btn, 0, 1)
        self._layout.addWidget(self.next_btn, 0, 2)
        self._step_layout = QtWidgets.QHBoxLayout()
        self._step_layout.addWidget(LabelAlignRight('Step:'))
        self._step_layout.addWidget(self.step_txt)
        self._layout.addLayout(self._step_layout, 1, 1, 1, 2)

        self._layout.addWidget(self.browse_by_name_rb, 0, 3)
        self._layout.addWidget(self.browse_by_time_rb, 1, 3)

        self._layout.addWidget(self.file_txt, 0, 4, 1, 2)
        self._layout.addWidget(self.directory_txt, 1, 4)
        self._layout.addWidget(self.directory_btn, 1, 5)

        self.setLayout(self._layout)

        self.style_widgets()

    def style_widgets(self):
        self.load_btn.setMaximumWidth(120)
        self.load_btn.setMinimumWidth(120)
        small_btn_width = 35

        self.next_btn.setMaximumWidth(small_btn_width)
        self.previous_btn.setMaximumWidth(small_btn_width)
        self.directory_btn.setMaximumWidth(small_btn_width)
        self.next_btn.setMinimumWidth(small_btn_width)
        self.previous_btn.setMinimumWidth(small_btn_width)
        self.directory_btn.setMinimumWidth(small_btn_width)

        self.step_txt.setMaximumWidth(30)

        self.setStyleSheet("""
        QPushButton {
            min-height: 22 px;
        }
        """)
