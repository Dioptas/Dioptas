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

from qtpy import QtWidgets, QtCore
from pyqtgraph import GraphicsLayoutWidget
from dioptas.widgets.plot_widgets import PatternWidget
from dioptas.widgets.plot_widgets.ImgWidget import IntegrationImgWidget

from .integration.CustomWidgets import MouseUnitCurrentAndClickedWidget


class MapWidget(QtWidgets.QWidget):
    """
    Defines the main structure of the Map widget, which is separated into several Parts
    """

    def __init__(self, *args, **kwargs):
        super(MapWidget, self).__init__(*args, **kwargs)

        self.create_widgets()
        self.create_layout()

    def create_widgets(self):
        self.map_pg_layout = GraphicsLayoutWidget()
        self.map_plot_widget = IntegrationImgWidget(
            self.map_pg_layout, orientation="horizontal"
        )

        self.img_pg_layout = GraphicsLayoutWidget()
        self.img_plot_widget = IntegrationImgWidget(
            self.img_pg_layout, orientation="horizontal"
        )
        self.map_plot_control_widget = (
            MapPlotControlWidget()
        )  # widget below the map image

        self.pattern_pg_layout = GraphicsLayoutWidget()
        self.pattern_plot_widget = PatternWidget(self.pattern_pg_layout)
        self.pattern_plot_widget.show_map_interactive_roi()

        self.pattern_footer_widget = PatternFooterWidget()
        self.pattern_widget = QtWidgets.QWidget()

        self.control_widget = MapControlWidget()

    def create_layout(self):
        self._outer_layout = TightHBoxLayout()
        self._left_layout = TightVBoxLayout()
        self._right_layout = TightVBoxLayout()
        self._upper_right_layout = TightHBoxLayout()

        self._left_widget = QtWidgets.QWidget()
        self._left_widget.setLayout(self._left_layout)
        self._left_layout.addWidget(self.map_pg_layout)
        self._left_layout.addWidget(self.map_plot_control_widget)

        self.upper_right_splitter = QtWidgets.QSplitter()
        self.upper_right_splitter.setOrientation(QtCore.Qt.Horizontal)
        self.upper_right_splitter.addWidget(self.img_pg_layout)
        self.upper_right_splitter.addWidget(self.control_widget)

        self._lower_right_layout = TightVBoxLayout()
        self._lower_right_layout.addWidget(self.pattern_pg_layout)
        self._lower_right_layout.addWidget(self.pattern_footer_widget)
        self.pattern_widget.setLayout(self._lower_right_layout)

        self.vertical_splitter = QtWidgets.QSplitter(self)
        self.vertical_splitter.setOrientation(QtCore.Qt.Vertical)
        self.vertical_splitter.addWidget(self.upper_right_splitter)
        self.vertical_splitter.addWidget(self.pattern_widget)

        self.horizontal_splitter = QtWidgets.QSplitter()
        self.horizontal_splitter.setOrientation(QtCore.Qt.Horizontal)
        self.horizontal_splitter.addWidget(self._left_widget)
        self.horizontal_splitter.addWidget(self.vertical_splitter)

        self._outer_layout.addWidget(self.horizontal_splitter)

        self.setLayout(self._outer_layout)


class TightHBoxLayout(QtWidgets.QHBoxLayout):
    def __init__(self, *args, **kwargs):
        super(TightHBoxLayout, self).__init__(*args, **kwargs)
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(0)


class TightVBoxLayout(QtWidgets.QVBoxLayout):
    def __init__(self, *args, **kwargs):
        super(TightVBoxLayout, self).__init__(*args, **kwargs)
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(0)


class MapControlWidget(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super(MapControlWidget, self).__init__(*args, **kwargs)

        self.create_widgets()
        self.create_layout()
        self.style_widgets()

    def create_widgets(self):
        self.load_btn = QtWidgets.QPushButton("Load")
        self.file_list = QtWidgets.QListWidget()

    def create_layout(self):
        self._outer_layout = TightVBoxLayout()
        self._outer_layout.setContentsMargins(0, 0, 0, 0)
        self._outer_layout.setSpacing(5)

        self._outer_layout.addWidget(self.load_btn)
        self._outer_layout.addWidget(self.file_list)

        self.setLayout(self._outer_layout)

    def style_widgets(self):
        pass


class MapPlotControlWidget(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super(MapPlotControlWidget, self).__init__(*args, **kwargs)

        self.create_widgets()
        self.create_layout()
        self.style_widgets()

    def create_widgets(self):
        self.map_dimension_cb = QtWidgets.QComboBox()
        self.mouse_x_label = QtWidgets.QLabel("X: ")
        self.mouse_y_label = QtWidgets.QLabel("Y: ")
        self.mouse_int_label = QtWidgets.QLabel("I: ")
        self.filename_label = QtWidgets.QLabel("")

    def create_layout(self):
        self._outer_layout = TightHBoxLayout()

        self._left_layout = TightVBoxLayout()
        self._mouse_pos_layout = TightHBoxLayout()
        self._mouse_pos_layout.addWidget(self.mouse_x_label)
        self._mouse_pos_layout.addWidget(self.mouse_y_label)
        self._mouse_pos_layout.addWidget(self.mouse_int_label)
        self._left_layout.addLayout(self._mouse_pos_layout)
        self._left_layout.addWidget(self.filename_label)
        self._outer_layout.addWidget(QtWidgets.QLabel("Dim: "))
        self._outer_layout.addWidget(self.map_dimension_cb)
        self._outer_layout.addStretch(1)
        self._outer_layout.addLayout(self._left_layout)
        self.setLayout(self._outer_layout)

    def style_widgets(self):
        self._outer_layout.setContentsMargins(6, 3, 0, 0)
        self.mouse_x_label.setFixedWidth(50)
        self.mouse_y_label.setFixedWidth(50)
        self.mouse_int_label.setMinimumWidth(80)
        self.setMinimumHeight(30)


class PatternFooterWidget(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super(PatternFooterWidget, self).__init__(*args, **kwargs)

        self.create_widgets()
        self.create_layout()
        self.style_widgets()

    def create_widgets(self):
        self.mouse_unit_widget = MouseUnitCurrentAndClickedWidget()

    def create_layout(self):
        self._outer_layout = TightHBoxLayout()
        self._outer_layout.addWidget(self.mouse_unit_widget)
        self._outer_layout.addStretch(1)
        self.setLayout(self._outer_layout)

    def style_widgets(self):
        self._outer_layout.setContentsMargins(6, 3, 6, 0)
        self.setMinimumHeight(30)
