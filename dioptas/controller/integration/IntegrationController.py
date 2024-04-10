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

import pyqtgraph as pg

from dioptas.controller.integration.overlay.OverlayInPatternController import OverlayInPatternController

from .BackgroundController import BackgroundController
from .CorrectionController import CorrectionController
from .ImageController import ImageController
from .overlay.OverlayController import OverlayController
from .PatternController import PatternController
from dioptas.controller.integration.phase.PhaseController import PhaseController
from .OptionsController import OptionsController
from .BatchController import BatchController

# imports for type hinting in PyCharm -- DO NOT DELETE
from ...widgets.integration import IntegrationWidget
from ...model.DioptasModel import DioptasModel

pg.setConfigOption('useOpenGL', False)
pg.setConfigOption('leftButtonPan', False)
pg.setConfigOption('background', 'k')
pg.setConfigOption('foreground', 'w')
pg.setConfigOption('antialias', True)


class IntegrationController(object):
    """
    This controller hosts all the Subcontroller of the integration tab.
    """

    def __init__(self, widget: IntegrationWidget, dioptas_model: DioptasModel):
        """
        :param widget: Reference to an IntegrationWidget
        :param dioptas_model: Reference to a DioptasModel object

        :type widget: IntegrationWidget
        :type dioptas_model: DioptasModel
        """
        self.widget = widget
        self.model = dioptas_model

        self.create_sub_controller()

    def create_sub_controller(self):
        """
        Creates the sub controller with the appropriate data.
        """
        self.pattern_controller = PatternController(self.widget, self.model)
        self.image_controller = ImageController(self.widget, self.model)
        self.overlay_controller = OverlayController(self.widget, self.model)
        self.overlay_in_pattern_controller = OverlayInPatternController(self.widget.pattern_widget, self.model.overlay_model)
        self.phase_controller = PhaseController(self.widget, self.model)
        self.background_controller = BackgroundController(self.widget, self.model)
        self.correction_controller = CorrectionController(self.widget, self.model)
        self.options_controller = OptionsController(self.widget, self.model)
        self.batch_controller = BatchController(self.widget, self.model)
