# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2014  Clemens Prescher (clemens.prescher@gmail.com)
# GSECARS, University of Chicago
#
#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.
#
#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <http://www.gnu.org/licenses/>.


__author__ = 'Clemens Prescher'
import sys

from PyQt4 import QtGui, QtCore
from Views.IntegrationView import IntegrationView
from Data.ImgData import ImgData
from Data.MaskData import MaskData
from Data.CalibrationData import CalibrationData
from Data.SpectrumData import SpectrumData
from Data.PhaseData import PhaseData
import pyqtgraph as pg
# # Switch to using white background and black foreground
pg.setConfigOption('useOpenGL', False)
pg.setConfigOption('leftButtonPan', False)
pg.setConfigOption('background', 'k')
pg.setConfigOption('foreground', 'w')
pg.setConfigOption('antialias', True)

from Controller.IntegrationOverlayController import IntegrationOverlayController
from Controller.IntegrationImageController import IntegrationImageController
from Controller.IntegrationSpectrumController import IntegrationSpectrumController
from Controller.IntegrationPhaseController import IntegrationPhaseController


class IntegrationController(object):
    """
    This controller hosts all the Subcontroller of the integration tab.
    """

    def __init__(self, working_dir, view=None, img_data=None, mask_data=None, calibration_data=None, spectrum_data=None,
                 phase_data=None):
        self.working_dir = working_dir
        if view == None:
            self.view = IntegrationView()
        else:
            self.view = view

        if img_data == None:
            self.img_data = ImgData()
        else:
            self.img_data = img_data

        if mask_data == None:
            self.mask_data = MaskData()
        else:
            self.mask_data = mask_data

        if calibration_data == None:
            self.calibration_data = CalibrationData(self.img_data)
        else:
            self.calibration_data = calibration_data

        if spectrum_data == None:
            self.spectrum_data = SpectrumData()
        else:
            self.spectrum_data = spectrum_data

        if phase_data == None:
            self.phase_data = PhaseData()
        else:
            self.phase_data = phase_data

        self.create_sub_controller()

        self.view.setWindowState(self.view.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
        self.view.activateWindow()
        self.view.raise_()


    def create_sub_controller(self):
        """
        Creates the sub controller with the appropriate data.
        """
        self.spectrum_controller = IntegrationSpectrumController(self.working_dir, self.view, self.img_data,
                                                                 self.mask_data,
                                                                 self.calibration_data, self.spectrum_data)
        self.image_controller = IntegrationImageController(self.working_dir, self.view, self.img_data,
                                                           self.mask_data, self.calibration_data)
        self.overlay_controller = IntegrationOverlayController(self.working_dir, self.view, self.spectrum_data)

        self.phase_controller = IntegrationPhaseController(self.working_dir, self.view, self.calibration_data,
                                                           self.spectrum_data, self.phase_data)


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    controller = IntegrationController({'calibration': '', 'mask': '', 'image': '', 'spectrum': '', 'overlay': '',
                                'phase': ''})
    controller.image_controller.load_file('../ExampleData/Mg2SiO4_ambient_001.tif')
    controller.spectrum_controller._working_dir = '../ExampleData/spectra'
    controller.mask_data.set_dimension(controller.img_data.get_img_data().shape)
    controller.overlay_controller.add_overlay('../ExampleData/spectra/Mg2SiO4_ambient_005.xy')
    controller.calibration_data.load('../ExampleData/LaB6_p49_001.poni')
    controller.image_controller.load_file('../ExampleData/Mg2SiO4_ambient_001.tif')
    app.exec_()