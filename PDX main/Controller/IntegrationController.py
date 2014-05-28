from StdSuites.Standard_Suite import _3c_
# -*- coding: utf8 -*-
__author__ = 'Clemens Prescher'
import sys
import os

from PyQt4 import QtGui, QtCore
from Views.IntegrationView import IntegrationView
from Data.ImgData import ImgData
from Data.MaskData import MaskData
from Data.CalibrationData import CalibrationData
from Data.SpectrumData import SpectrumData
from Data.HelperModule import get_base_name
import pyqtgraph as pg
import time
## Switch to using white background and black foreground
pg.setConfigOption('useOpenGL', False)
pg.setConfigOption('leftButtonPan', False)
pg.setConfigOption('background', 'k')
pg.setConfigOption('foreground', 'w')
pg.setConfigOption('antialias', True)
import pyFAI.units
import numpy as np

from Controller.OverlayController import IntegrationOverlayController
from Controller.ImageController import IntegrationImageController
from Controller.SpectrumController import IntegrationSpectrumController


class IntegrationController(object):
    def __init__(self, view=None, img_data=None, mask_data=None, calibration_data=None, spectrum_data=None):

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

        self.create_sub_controller()

        self.view.setWindowState(self.view.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
        self.view.activateWindow()
        self.view.raise_()


    def create_sub_controller(self):
        self.spectrum_controller = IntegrationSpectrumController(self.view, self.img_data, self.mask_data,
                                                                 self.calibration_data, self.spectrum_data)
        self.file_controller = IntegrationImageController(self.view, self.img_data,
                                                          self.mask_data, self.calibration_data)
        self.overlay_controller = IntegrationOverlayController(self.view, self.spectrum_data)


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    controller = IntegrationController()
    controller.file_controller.load_file_btn_click('../ExampleData/Mg2SiO4_ambient_001.tif')
    controller.spectrum_controller._working_dir = '../ExampleData/spectra'
    controller.mask_data.set_dimension(controller.img_data.get_img_data().shape)
    controller.overlay_controller.add_overlay('../ExampleData/spectra/Mg2SiO4_ambient_005.xy')
    controller.calibration_data.load('../ExampleData/calibration.poni')
    controller.file_controller.load_file_btn_click('../ExampleData/Mg2SiO4_ambient_001.tif')
    app.exec_()