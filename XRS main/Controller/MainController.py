__author__ = 'Clemens Prescher'

import sys
import os

import pyqtgraph as pg

from PyQt4 import QtGui, QtCore
from Views.MainView import MainView

from Data.ImgData import ImgData
from Data.MaskData import MaskData
from Data.SpectrumData import SpectrumData
from Data.CalibrationData import CalibrationData

from Controller.CalibrationController import CalibrationController
from Controller.IntegrationController import IntegrationController
from Controller.MaskController import MaskController

import numpy as np


class MainController(object):
    def __init__(self):
        self.view = MainView()

        #create data
        self.img_data = ImgData()
        self.calibration_data = CalibrationData(self.img_data)
        self.mask_data = MaskData()
        self.spectrum_data = SpectrumData()

        #create controller
        self.calibration_controller = CalibrationController(self.view.calibration_widget,
                                                            self.img_data,
                                                            self.calibration_data)
        self.mask_controller = MaskController(self.view.mask_widget,
                                              self.img_data,
                                              self.mask_data)
        self.integration_controller = IntegrationController(self.view.integration_widget,
                                                            self.img_data,
                                                            self.mask_data,
                                                            self.calibration_data,
                                                            self.spectrum_data)

        self.create_signals()
        self.raise_window()

    def raise_window(self):
        self.view.show()
        self.view.setWindowState(self.view.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
        self.view.activateWindow()
        self.view.raise_()

    def create_signals(self):
        self.view.tabWidget.currentChanged.connect(self.tab_changed)

    def tab_changed(self, ind):
        if ind == 2:
            self.integration_controller.file_controller.plot_mask()
            self.img_data.notify()
        elif ind == 1:
            self.mask_controller.plot_mask()
            self.mask_controller.plot_image()

