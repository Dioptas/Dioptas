# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2014  Clemens Prescher (clemens.prescher@gmail.com)
# GSECARS, University of Chicago
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


__author__ = 'Clemens Prescher'
import sys

from PyQt4 import QtGui, QtCore
import pyqtgraph as pg


pg.setConfigOption('useOpenGL', False)
pg.setConfigOption('leftButtonPan', False)
pg.setConfigOption('background', 'k')
pg.setConfigOption('foreground', 'w')
pg.setConfigOption('antialias', True)

from .OverlayController import OverlayController
from .ImageController import ImageController
from .SpectrumController import SpectrumController
from .PhaseController import PhaseController
from .BackgroundController import BackgroundController

# imports for type hinting in PyCharm -- DO NOT DELETE
from widgets.IntegrationWidget import IntegrationWidget
from model.ImgModel import ImgModel
from model.MaskModel import MaskModel
from model.CalibrationModel import CalibrationModel
from model.SpectrumModel import SpectrumModel
from model.PhaseModel import PhaseModel


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
        :type spectrum_model: SpectrumModel
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
        self.spectrum_controller = SpectrumController(self.working_dir, self.widget, self.img_model,
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
