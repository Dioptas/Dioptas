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

__VERSION__ = '0.2.3'


class MainController(object):
    """
    Creates a the main controller for Dioptas. Loads all the data objects and connects them with the other controllers
    """

    def __init__(self):
        self.view = MainView()
        #create data
        self.img_data = ImgData()
        self.calibration_data = CalibrationData(self.img_data)
        self.mask_data = MaskData()
        self.spectrum_data = SpectrumData()
        self.phase_data = PhaseData()

        self.load_settings()
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
        self.raise_window(self.view)
        self.img_data.notify()

    @staticmethod
    def raise_window(widget):
        widget.show()
        widget.setWindowState(widget.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
        widget.activateWindow()
        widget.raise_()

    def create_signals(self):
        self.view.tabWidget.currentChanged.connect(self.tab_changed)
        self.view.closeEvent = self.close_event
        self.img_data.subscribe(self.set_title)
        self.spectrum_data.subscribe(self.set_title)

    def tab_changed(self, ind):
        if ind == 2:
            self.mask_data.set_supersampling()
            self.integration_controller.image_controller.plot_mask()
            self.integration_controller.view.calibration_lbl.setText(self.calibration_data.calibration_name)
            auto_scale_previous = self.integration_controller.image_controller._auto_scale
            self.integration_controller.image_controller._auto_scale = False
            self.integration_controller.spectrum_controller.image_changed()
            self.integration_controller.image_controller.update_img()
            self.integration_controller.image_controller._auto_scale = auto_scale_previous
        elif ind == 1:
            self.mask_controller.plot_mask()
            self.mask_controller.plot_image()
        elif ind == 0:
            self.calibration_controller.plot_mask()
            try:
                self.calibration_controller.update_calibration_parameter_in_view()
            except (TypeError, AttributeError):
                pass

    def set_title(self):
        img_filename = os.path.basename(self.img_data.filename)
        spec_filename = os.path.basename(self.spectrum_data.spectrum_filename)
        calibration_name = self.calibration_data.calibration_name
        str = 'Dioptas ' + __VERSION__
        if img_filename is '' and spec_filename is '':
            self.view.setWindowTitle(str + u' - © 2014 C. Prescher')
            self.view.integration_widget.img_frame.setWindowTitle(str + u' - © 2014 C. Prescher')
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
        str += u' - © 2014 C. Prescher'
        self.view.setWindowTitle(str)
        self.view.integration_widget.img_frame.setWindowTitle(str)

    def load_settings(self):
        # self.load_data()
        self.load_directories()
        # self.load_filenames()

    def load_directories(self):
        directory_path = os.path.join(os.path.expanduser("~"), '.Dioptas')
        working_directories_path = os.path.join(directory_path, 'working_directories.csv')
        if os.path.exists(working_directories_path):
            reader = csv.reader(open(working_directories_path, 'r'))
            self.working_dir = dict(x for x in reader)
        else:
            self.working_dir = {'calibration': '', 'mask': '', 'image': '', 'spectrum': '', 'overlay': '',
                                'phase': ''}

    def load_filenames(self):
        directory_path = os.path.join(os.path.expanduser("~"), '.Dioptas')
        filenames_path = os.path.join(directory_path, 'filenames.csv')
        if os.path.exists(filenames_path):
            reader = csv.reader(open(filenames_path, 'r'))
            filenames = dict(x for x in reader)
            self.img_data.filename = filenames['img_data']
            self.img_data.file_name_iterator.update_filename(os.path.join(self.working_dir['image'],
                                                                          filenames['img_data']))
            self.mask_data.filename = filenames['mask_data']
            self.calibration_data.calibration_name = filenames['calibration_data']
            self.spectrum_data.spectrum_filename = filenames['spectrum_data']

    def load_data(self):
        directory_path = os.path.join(os.path.expanduser("~"), '.Dioptas')
        data_path = os.path.join(directory_path, 'Data')

        img_data_path = os.path.join(data_path, "img_data.tif")
        mask_data_path = os.path.join(data_path, "mask_data.mask")
        calibration_data_path = os.path.join(data_path, "calibration.poni")
        spectrum_data_path = os.path.join(data_path, "spectrum.xy")

        if os.path.exists(img_data_path):
            self.img_data.load(img_data_path)
        if os.path.exists(mask_data_path):
            self.mask_data.load_mask(mask_data_path)
        if os.path.exists(calibration_data_path):
            self.calibration_data.load(calibration_data_path)
        if os.path.exists(spectrum_data_path):
            self.spectrum_data.load_spectrum(spectrum_data_path)

    def save_settings(self):
        self.save_directories()
        self.save_filenames()
        self.save_data()

    def save_directories(self):
        directory_path = os.path.join(os.path.expanduser("~"), '.Dioptas')
        if not os.path.exists(directory_path):
            os.mkdir(directory_path)

        working_directories_path = os.path.join(directory_path, 'working_directories.csv')
        writer = csv.writer(open(working_directories_path, 'w'))
        for key, value in list(self.working_dir.items()):
            writer.writerow([key, value])

    def save_filenames(self):
        directory_path = os.path.join(os.path.expanduser("~"), '.Dioptas')
        filenames_path = os.path.join(directory_path, 'filenames.csv')
        writer = csv.writer(open(filenames_path, 'w'))

        filenames = {'img_data': self.img_data.filename,
                     'mask_data': self.mask_data.filename,
                     'spectrum_data': self.spectrum_data.spectrum_filename,
                     'calibration_data': self.calibration_data.calibration_name}

        for key, value in list(filenames.items()):
            writer.writerow([key, value])

    def save_data(self):
        directory_path = os.path.join(os.path.expanduser("~"), '.Dioptas')
        data_path = os.path.join(directory_path, 'Data')
        if not os.path.exists(data_path):
            os.mkdir(data_path)

        self.img_data.save(os.path.join(data_path, "img_data.tif"))
        self.mask_data.save_mask(os.path.join(data_path, "mask_data.mask"))
        self.calibration_data.save(os.path.join(data_path, "calibration.poni"))
        self.spectrum_data.save_spectrum(os.path.join(data_path, "spectrum.xy"))



    def close_event(self, _):
        self.save_settings()
        QtGui.QApplication.closeAllWindows()
        QtGui.QApplication.quit()


