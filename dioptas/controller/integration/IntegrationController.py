# SPDX-License-Identifier: MIT

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


class IntegrationController:
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
