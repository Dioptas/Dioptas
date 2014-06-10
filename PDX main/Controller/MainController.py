# Py2DeX - GUI program for fast processing of 2D X-ray data
#     Copyright (C) 2014  Clemens Prescher (clemens.prescher@gmail.com)
#     GSECARS, University of Chicago
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
#     along with this program.  If not, see <http://www.gnu.org/licenses/>.__author__ = 'Clemens Prescher'

import sys
import os

import pyqtgraph as pg
import csv

from PySide import QtGui, QtCore
from Views.MainView import MainView

from Data.ImgData import ImgData
from Data.MaskData import MaskData
from Data.SpectrumData import SpectrumData
from Data.CalibrationData import CalibrationData
from Data.PhaseData import PhaseData

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
        self.phase_data = PhaseData()

        self.load_directories()
        #create controller
        self.calibration_controller = CalibrationController(self.working_dir,
                                                            self.view.calibration_widget,
                                                            self.img_data,
                                                            self.calibration_data)
        self.mask_controller = MaskController(self.working_dir,
                                              self.view.mask_widget,
                                              self.img_data,
                                              self.mask_data)
        self.integration_controller = IntegrationController(self.working_dir,
                                                            self.view.integration_widget,
                                                            self.img_data,
                                                            self.mask_data,
                                                            self.calibration_data,
                                                            self.spectrum_data,
                                                            self.phase_data)

        self.create_signals()
        self.raise_window()

    def raise_window(self):
        self.view.show()
        self.view.setWindowState(self.view.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
        self.view.activateWindow()
        self.view.raise_()

    def create_signals(self):
        self.view.tabWidget.currentChanged.connect(self.tab_changed)
        self.view.closeEvent = self.close_event

    def tab_changed(self, ind):
        if ind == 2:
            self.integration_controller.image_controller.plot_mask()
            self.integration_controller.view.calibration_lbl.setText(self.calibration_data.calibration_name)
            self.img_data.notify()
        elif ind == 1:
            self.mask_controller.plot_mask()
            self.mask_controller.plot_image()
        elif ind == 0:
            try:
                self.calibration_controller.update_calibration_parameter()
            except TypeError:
                pass

    def load_directories(self):
        if os.path.exists('working_directories.csv'):
            reader = csv.reader(open('working_directories.csv', 'rb'))
            self.working_dir = dict(x for x in reader)
        else:
            self.working_dir = {'calibration': '', 'mask': '', 'image': '', 'spectrum': '', 'overlay': '',
                                'phase': ''}

    def save_directories(self):
        writer = csv.writer(open('working_directories.csv', 'wb'))
        for key, value in self.working_dir.items():
            writer.writerow([key, value])

    def close_event(self, _):
        self.save_directories()


