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
from widgets.IntegrationView import IntegrationView
from model.ImgModel import ImgModel
from model.MaskModel import MaskModel
from model.CalibrationModel import CalibrationModel
from model.SpectrumModel import SpectrumModel
from model.PhaseModel import PhaseModel


class IntegrationController(object):
    """
    This controller hosts all the Subcontroller of the integration tab.
    """

    def __init__(self, working_dir, view, img_data, mask_data=None, calibration_data=None, spectrum_data=None,
                 phase_data=None):
        """
        :param working_dir: dictionary of working directories
        :param view: Reference to an IntegrationView
        :param img_data: reference to ImgData object
        :param mask_data: reference to MaskData object
        :param calibration_data: reference to CalibrationData object
        :param spectrum_data: reference to SpectrumData object
        :param phase_data: reference to PhaseData object

        :type view: IntegrationView
        :type img_data: ImgModel
        :type mask_data: MaskModel
        :type calibration_data: CalibrationModel
        :type spectrum_data: SpectrumModel
        :type phase_data: PhaseModel
        """
        self.working_dir = working_dir
        self.view = view
        self.img_data = img_data
        self.mask_data = mask_data
        self.calibration_data = calibration_data
        self.spectrum_data = spectrum_data
        self.phase_data = phase_data

        self.create_sub_controller()

        self.view.setWindowState(self.view.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
        self.view.activateWindow()
        self.view.raise_()


    def create_sub_controller(self):
        """
        Creates the sub controller with the appropriate data.
        """
        self.spectrum_controller = SpectrumController(self.working_dir, self.view, self.img_data,
                                                                 self.mask_data,
                                                                 self.calibration_data, self.spectrum_data)
        self.image_controller = ImageController(self.working_dir, self.view, self.img_data,
                                                           self.mask_data, self.spectrum_data,
                                                           self.calibration_data)

        self.overlay_controller = OverlayController(self.working_dir, self.view, self.spectrum_data)

        self.phase_controller = PhaseController(self.working_dir, self.view, self.calibration_data,
                                                           self.spectrum_data, self.phase_data)

        self.background_controller = BackgroundController(self.working_dir, self.view,
                                                                     self.img_data, self.spectrum_data)


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    controller = IntegrationController({'calibration': '', 'mask': '', 'image': '', 'spectrum': '', 'overlay': '',
                                        'phase': ''})
    controller.image_controller.load_file('../ExampleData/Mg2SiO4_ambient_001.tif')
    controller.spectrum_controller._working_dir = '../ExampleData/spectra'
    controller.mask_data.set_dimension(controller.img_data.get_img_data().shape)
    controller.overlay_controller.add_overlay_btn_click_callback('../ExampleData/spectra/Mg2SiO4_ambient_005.xy')
    controller.calibration_data.load('../ExampleData/LaB6_p49_001.poni')
    controller.image_controller.load_file('../ExampleData/Mg2SiO4_ambient_001.tif')
    app.exec_()