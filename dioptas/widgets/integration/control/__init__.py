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

from qtpy import QtWidgets

from .ImageWidget import ImageWidget
from .PatternWidget import PatternWidget
from .OverlayWidget import OverlayWidget
from .PhaseWidget import PhaseWidget
from .CorrectionsWidget import CorrectionsWidget
from .BackgroundWidget import BackgroundWidget
from .OptionsWidget import OptionsWidget


class IntegrationControlWidget(QtWidgets.QTabWidget):
    def __init__(self):
        super(IntegrationControlWidget, self).__init__()

        self.img_control_widget = ImageWidget()
        self.pattern_control_widget = PatternWidget()
        self.overlay_control_widget = OverlayWidget()
        self.phase_control_widget = PhaseWidget()
        self.corrections_control_widget = CorrectionsWidget()
        self.background_control_widget = BackgroundWidget()
        self.integration_options_widget = OptionsWidget()

        self.addTab(self.img_control_widget, 'Image')
        self.addTab(self.pattern_control_widget, 'Pattern')
        self.addTab(self.overlay_control_widget, 'Overlay')
        self.addTab(self.phase_control_widget, 'Phase')
        #self.addTab(self.corrections_control_widget, 'Cor')
        self.addTab(self.background_control_widget, 'Bkg')
        self.addTab(self.integration_options_widget, 'X')

        self.style_widgets()

    def style_widgets(self):
        self.setStyleSheet("""
        QTableWidget QPushButton {
            margin: 5px;
        }

        QTableWidget QPushButton::pressed{
            margin-top: 7px;
            margin-left: 7px;
        }

        QTableWidget {
            selection-background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1, stop:0 rgba(177,80,0,255), stop:1 rgba(255,120,0,255));
            selection-color: #F1F1F1;
        }
        """)

