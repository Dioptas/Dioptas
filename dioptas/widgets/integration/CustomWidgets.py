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

from qtpy import QtWidgets, QtGui, QtCore

from ..CustomWidgets import LabelAlignRight, FlatButton, CleanLooksComboBox


class MouseCurrentAndClickedWidget(QtWidgets.QWidget):
    def __init__(self, clicked_color):
        super(MouseCurrentAndClickedWidget, self).__init__()

        self._layout = QtWidgets.QVBoxLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)
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
        self._layout.setContentsMargins(0, 0, 0, 0)
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
        self._layout.setContentsMargins(0, 5, 5, 0)
        self._layout.setVerticalSpacing(3)
        self._layout.setHorizontalSpacing(3)

        self.load_btn = QtWidgets.QPushButton('Load {}(s)'.format(files))
        self.file_cb = QtWidgets.QCheckBox(checkbox_text)

        self._load_layout = QtWidgets.QVBoxLayout()
        self._load_layout.setContentsMargins(0, 0, 0, 0)
        self._load_layout.setSpacing(3)
        self._load_layout.addWidget(self.load_btn)
        self._load_layout.addWidget(self.file_cb)

        self._layout.addLayout(self._load_layout, 0, 0, 2, 1)

        self.directory_txt = QtWidgets.QLineEdit('')
        self.directory_btn = QtWidgets.QPushButton('...')
        self.file_txt = QtWidgets.QLineEdit('')

        self.step_file_widget = StepFileWidget()
        self._layout.addWidget(self.step_file_widget, 0, 1, 2, 2)
        self.step_series_widget = StepFrameWidget()
        self._layout.addWidget(self.step_series_widget, 0, 3, 2, 2)

        self.step_series_widget.setVisible(False)

        self._layout.addWidget(self.file_txt, 2, 0, 1, 5)
        self._directory_layout = QtWidgets.QHBoxLayout()
        self._directory_layout.addWidget(self.directory_txt)
        self._directory_layout.addWidget(self.directory_btn)
        self._directory_layout.setSpacing(3)
        self._layout.addLayout(self._directory_layout, 3, 0, 1, 5)

        self.sources_widget = QtWidgets.QWidget()
        self.sources_cb = CleanLooksComboBox()
        self._sources_layout = QtWidgets.QHBoxLayout()
        self._sources_layout.setContentsMargins(0, 0, 0, 0)
        self._sources_layout.addWidget(LabelAlignRight('Source:'))
        self._sources_layout.addWidget(self.sources_cb)
        self.sources_widget.setLayout(self._sources_layout)
        self._layout.addWidget(self.sources_widget, 4, 0, 1, 5)

        self.setLayout(self._layout)

        self.style_widgets()

    def style_widgets(self):
        self.load_btn.setMaximumWidth(120)
        self.load_btn.setMinimumWidth(120)
        self.load_btn.setFixedHeight(25)

        small_btn_width = 25 
        self.directory_btn.setFixedSize(small_btn_width, small_btn_width)
        self.sources_widget.hide()


class StepWidget(QtWidgets.QWidget):
    """Widget with buttons to step a number up and down and a Spinbox with the step size"""
    iteration_name = ''

    def __init__(self):
        super(StepWidget, self).__init__()
        self.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Maximum)

        self._layout = QtWidgets.QGridLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(3)
        self.init_navigator()

        self.setLayout(self._layout)
        self.style_widgets()

    def init_navigator(self):
        self.next_btn = QtWidgets.QPushButton('>')
        self.next_btn.setToolTip('Loads next {}'.format(self.iteration_name))
        self.previous_btn = QtWidgets.QPushButton('<')
        self.previous_btn.setToolTip(('Loads previous {}'.format(self.iteration_name)))
        self.step_txt = QtWidgets.QSpinBox()
        self.step_txt.setValue(1)
        self.step_txt.setRange(1, 10000)
        self.step_txt.setToolTip('Step size')

        self._layout.addWidget(self.previous_btn, 0, 0)
        self._layout.addWidget(self.next_btn, 0, 1)
        self._step_layout = QtWidgets.QHBoxLayout()
        self._step_layout.addWidget(LabelAlignRight('Step:'))
        self._step_layout.addWidget(self.step_txt)
        self._layout.addLayout(self._step_layout, 1, 0, 1, 2)
        

    def style_widgets(self):
        self.step_txt.setMaximumWidth(53)
        self.step_txt.setFixedHeight(25)

        small_btn_width = 40 
        small_btn_height = 25
        btns = [self.next_btn, self.previous_btn]
        for btn in btns:
            btn.setFixedHeight(small_btn_height)
            btn.setFixedWidth(small_btn_width)


class StepFileWidget(StepWidget):
    iteration_name = 'file'

    def __init__(self):
        super(StepFileWidget, self).__init__()
        self.browse_by_name_rb = QtWidgets.QRadioButton('By Name')
        self.browse_by_name_rb.setChecked(True)
        self.browse_by_time_rb = QtWidgets.QRadioButton('By Time')

        self._layout.addWidget(self.browse_by_name_rb, 0, 2)
        self._layout.addWidget(self.browse_by_time_rb, 1, 2)


class StepFrameWidget(StepWidget):
    iteration_name = 'frame'

    def __init__(self):
        super(StepFrameWidget, self).__init__()
        self.pos_txt = QtWidgets.QLineEdit()
        self.pos_validator = QtGui.QIntValidator(1, 1)
        self.pos_txt.setValidator(self.pos_validator)
        self.pos_txt.setToolTip('Currently loaded frame')
        self.pos_label = QtWidgets.QLabel('Frame:')
        self.pos_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignBottom)

        self._pos_layout = QtWidgets.QVBoxLayout()
        self._pos_layout.addWidget(self.pos_label)
        self._pos_layout.addWidget(self.pos_txt)
        self._layout.addLayout(self._pos_layout, 0, 2, 2, 2)

        self.pos_txt.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Maximum)
