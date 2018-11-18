# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2017  Clemens Prescher (clemens.prescher@gmail.com)
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

from qtpy import QtWidgets, QtCore, QtGui

from .ImageWidget import ImageWidget
from .PatternWidget import PatternWidget
from .OverlayWidget import OverlayWidget
from .PhaseWidget import PhaseWidget
from .CorrectionsWidget import CorrectionsWidget
from .BackgroundWidget import BackgroundWidget
from .OptionsWidget import OptionsWidget


class IntegrationControlWidget(QtWidgets.QWidget):
    def __init__(self):
        super(IntegrationControlWidget, self).__init__()

        self._layout = QtWidgets.QHBoxLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(5)

        self.tab_widget_1 = QtWidgets.QTabWidget()
        self.tab_widget_2 = QtWidgets.QTabWidget()

        self.img_control_widget = ImageWidget()
        self.pattern_control_widget = PatternWidget()
        self.overlay_control_widget = OverlayWidget()
        self.phase_control_widget = PhaseWidget()
        self.corrections_control_widget = CorrectionsWidget()
        self.background_control_widget = BackgroundWidget()
        self.integration_options_widget = OptionsWidget()

        self.horizontal_splitter = QtWidgets.QSplitter()
        self.horizontal_splitter.setOrientation(QtCore.Qt.Horizontal)

        self.horizontal_splitter.addWidget(self.tab_widget_1)
        self.horizontal_splitter.addWidget(self.tab_widget_2)

        self.vertical_splitter = QtWidgets.QSplitter()
        self.vertical_splitter.setOrientation(QtCore.Qt.Vertical)

        self.vertical_splitter.addWidget(self.horizontal_splitter)

        self._layout.addWidget(self.vertical_splitter)
        self.setLayout(self._layout)

        self.current_layout = None

        self.orientation = QtCore.Qt.Horizontal # other value is QtCore.Qt.Horizontal

        self.tab_widget_1.addTab(self.img_control_widget, 'Image')
        self.tab_widget_1.addTab(self.pattern_control_widget, 'Pattern')
        self.tab_widget_1.addTab(self.overlay_control_widget, 'Overlay')
        self.tab_widget_1.addTab(self.phase_control_widget, 'Phase')
        self.tab_widget_1.addTab(self.corrections_control_widget, 'Cor')
        self.tab_widget_1.addTab(self.background_control_widget, 'Bkg')
        self.tab_widget_1.addTab(self.integration_options_widget, 'X')

        self.horizontal_layout_2()

    def horizontal_layout_1(self):
        self.current_layout = 1

        self.tab_widget_2.hide()

        self.tab_widget_1.insertTab(2, self.overlay_control_widget, 'Overlay')
        self.tab_widget_1.insertTab(3, self.phase_control_widget, 'Phase')

        self.overlay_control_widget.overlay_header_btn.hide()
        self.phase_control_widget.phase_header_btn.hide()

    def horizontal_layout_2(self):
        self.current_layout = 2

        self.tab_widget_2.show()

        self.tab_widget_2.addTab(self.overlay_control_widget, 'Overlay')
        self.tab_widget_2.addTab(self.phase_control_widget, 'Phase')

        self.overlay_control_widget.overlay_header_btn.hide()
        self.phase_control_widget.phase_header_btn.hide()

    def horizontal_layout_3(self):
        self.current_layout = 3
        self.tab_widget_2.hide()

        self.horizontal_splitter.addWidget(self.overlay_control_widget)
        self.horizontal_splitter.addWidget(self.phase_control_widget)

        self.overlay_control_widget.show()
        self.phase_control_widget.show()

        self.overlay_control_widget.overlay_header_btn.show()
        self.phase_control_widget.phase_header_btn.show()

    def vertical_layout(self):
        self.tab_widget_2.hide()
        self.vertical_splitter.addWidget(self.overlay_control_widget)
        self.vertical_splitter.addWidget(self.phase_control_widget)

        self.overlay_control_widget.overlay_header_btn.show()
        self.phase_control_widget.phase_header_btn.show()

    def update_layout(self):
        if self.orientation == QtCore.Qt.Horizontal:
            if self.width() < 700:
                if self.current_layout != 1:
                    self.horizontal_layout_1()
            elif self.width() > 1400:
                if self.current_layout != 3:
                    self.horizontal_layout_3()
            else:
                if self.current_layout != 2:
                    self.horizontal_layout_2()
        elif self.orientation == QtCore.Qt.Vertical:
            self.vertical_layout()

    def resizeEvent(self, a0: QtGui.QResizeEvent):
        self.update_layout()
        super(IntegrationControlWidget, self).resizeEvent(a0)

    def setOrientation(self, a0):
        """
        Sets the orientation of the control widgets
        :param a0: either QtCore.Qt.Horizontal or QtCore.Qt.Vertical
        """
        self.orientation = a0
        self.update_layout()


