# Py2DeX - GUI program for fast processing of 2D X-ray data
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
#     along with this program.  If not, see <http://www.gnu.org/licenses/>.__author__ = 'Clemens Prescher'


import os

import csv

from PyQt4 import QtGui, QtCore
from Views.MainView import MainView

from Data.ImgData import ImgData
from Data.MaskData import MaskData
from Data.SpectrumData import SpectrumData
from Data.CalibrationData import CalibrationData
from Data.PhaseData import PhaseData

from .CalibrationController import CalibrationController
from .IntegrationController import IntegrationController
from .MaskController import MaskController

__VERSION__ = '0.1'

import time


class MainController(object):
    def __init__(self, app):
        self.splash_img = QtGui.QPixmap("UiFiles/splash.png")
        self.splash_screen = QtGui.QSplashScreen(self.splash_img, QtCore.Qt.WindowStaysOnTopHint)
        self.splash_screen.show()
        app.processEvents()
        time.sleep(1)
        app.processEvents()

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
                                                            self.mask_data,
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
        self.set_title()
        self.raise_window()
        self.splash_screen.finish(self.view)

    def raise_window(self):
        self.view.show()
        self.view.setWindowState(self.view.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
        self.view.activateWindow()
        self.view.raise_()

    def create_signals(self):
        self.view.tabWidget.currentChanged.connect(self.tab_changed)
        self.view.closeEvent = self.close_event
        self.img_data.subscribe(self.set_title)
        self.spectrum_data.subscribe(self.set_title)

    def tab_changed(self, ind):
        if ind == 2:
            self.integration_controller.image_controller.plot_mask()
            self.integration_controller.view.calibration_lbl.setText(self.calibration_data.calibration_name)
            auto_scale_previous = self.integration_controller.image_controller._auto_scale
            self.integration_controller.image_controller._auto_scale = False
            self.integration_controller.spectrum_controller.image_changed()
            self.integration_controller.image_controller._auto_scale = auto_scale_previous
        elif ind == 1:
            self.mask_controller.plot_mask()
            self.mask_controller.plot_image()
        elif ind == 0:
            self.calibration_controller.plot_mask()
            try:
                self.calibration_controller.update_calibration_parameter()
            except TypeError:
                pass

    def set_title(self):
        img_filename = os.path.basename(self.img_data.filename)
        spec_filename = os.path.basename(self.spectrum_data.spectrum_filename)
        calibration_name = self.calibration_data.calibration_name
        str = 'Dioptas v' + __VERSION__
        if img_filename is '' and spec_filename is '':
            self.view.setWindowTitle(str)
            return

        if img_filename is not '' or spec_filename is not '':
            str += ' - ['
        if img_filename is not '':
            str += img_filename
        elif img_filename is '' and spec_filename is not '':
            str += spec_filename
        if not img_filename == spec_filename:
            str += ', ' + spec_filename
        if calibration_name is not None:
            str += ', calibration: ' + calibration_name
        str += ']'
        self.view.setWindowTitle(str)

    def load_directories(self):
        if os.path.exists('working_directories.csv'):
            reader = csv.reader(open('working_directories.csv', 'r'))
            self.working_dir = dict(x for x in reader)
        else:
            self.working_dir = {'calibration': '', 'mask': '', 'image': '', 'spectrum': '', 'overlay': '',
                                'phase': ''}

    def save_directories(self):
        writer = csv.writer(open('working_directories.csv', 'w'))
        for key, value in list(self.working_dir.items()):
            writer.writerow([key, value])


    def close_event(self, _):
        self.save_directories()


