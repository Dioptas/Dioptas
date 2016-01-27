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

import pyqtgraph as pg

from .BackgroundController import BackgroundController
from .ImageController import ImageController
from .OverlayController import OverlayController
from .PatternController import PatternController
from .PhaseController import PhaseController

# imports for type hinting in PyCharm -- DO NOT DELETE
from widgets.integration import IntegrationWidget
from model.ImgModel import ImgModel
from model.MaskModel import MaskModel
from model.CalibrationModel import CalibrationModel
from model.PatternModel import PatternModel
from model.PhaseModel import PhaseModel

pg.setConfigOption('useOpenGL', False)
pg.setConfigOption('leftButtonPan', False)
pg.setConfigOption('background', 'k')
pg.setConfigOption('foreground', 'w')
pg.setConfigOption('antialias', True)


class IntegrationController(object):
    """
    This controller hosts all the Subcontroller of the integration tab.
    """

    def __init__(self, working_dir, widget, img_model, mask_model=None, calibration_model=None, spectrum_model=None,
                 phase_model=None):
        """
        :param working_dir: dictionary of working directories
        :param widget: Reference to an IntegrationWidget
        :param img_model: reference to ImgModel object
        :param mask_model: reference to MaskModel object
        :param calibration_model: reference to CalibrationModel object
        :param spectrum_model: reference to SpectrumModel object
        :param phase_model: reference to PhaseModel object

        :type widget: IntegrationWidget
        :type img_model: ImgModel
        :type mask_model: MaskModel
        :type calibration_model: CalibrationModel
        :type spectrum_model: PatternModel
        :type phase_model: PhaseModel
        """
        self.working_dir = working_dir
        self.widget = widget
        self.img_model = img_model
        self.mask_model = mask_model
        self.calibration_model = calibration_model
        self.spectrum_model = spectrum_model
        self.phase_model = phase_model

        self.create_sub_controller()

    def create_sub_controller(self):
        """
        Creates the sub controller with the appropriate data.
        """
        self.spectrum_controller = PatternController(self.working_dir, self.widget, self.img_model,
                                                     self.mask_model,
                                                     self.calibration_model, self.spectrum_model)
        self.image_controller = ImageController(self.working_dir, self.widget, self.img_model,
                                                self.mask_model, self.spectrum_model,
                                                self.calibration_model)

        self.overlay_controller = OverlayController(self.working_dir, self.widget, self.spectrum_model)

        self.phase_controller = PhaseController(self.working_dir, self.widget, self.calibration_model,
                                                self.spectrum_model, self.phase_model)

        self.background_controller = BackgroundController(self.working_dir, self.widget,
                                                          self.img_model, self.spectrum_model)
