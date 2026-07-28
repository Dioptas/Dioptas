# SPDX-License-Identifier: MIT

import pyqtgraph as pg

from dioptas.controller.integration.overlay.OverlayInPatternController import OverlayInPatternController

from .BackgroundController import BackgroundController
from .MapRoiInPatternController import MapRoiInPatternController
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
        self.map_roi_controller = MapRoiInPatternController(
            self.widget.pattern_widget, self.model
        )

        self.model.view.events.map_docked.connect(self._update_map_roi_wanted)
        self._update_map_roi_wanted()

    def _update_map_roi_wanted(self, *_args):
        """Shows the map window region only while the map is on screen.

        Dragging it changes what the map displays, so it would be a puzzling
        thing to find in the pattern otherwise. Here that means the map is
        undocked into its own window, next to the integration view.
        """
        self.map_roi_controller.set_wanted(not self.model.view.map_docked)
