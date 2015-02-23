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
import xml.etree.cElementTree as ET

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

__VERSION__ = '0.2.4d'


class MainController(object):
    """
    Creates a the main controller for Dioptas. Loads all the data objects and connects them with the other controllers
    """

    def __init__(self, use_settings=True):
        self.use_settings = use_settings

        self.view = MainView()
        #create data
        self.img_data = ImgData()
        self.calibration_data = CalibrationData(self.img_data)
        self.mask_data = MaskData()
        self.spectrum_data = SpectrumData()
        self.phase_data = PhaseData()

        self.settings_directory = os.path.join(os.path.expanduser("~"), '.Dioptas')
        self.working_directories = {'calibration': '', 'mask': '', 'image': '', 'spectrum': '', 'overlay': '',
                                'phase': ''}


        if use_settings:
            self.load_settings()
        #create controller
        self.calibration_controller = CalibrationController(self.working_directories,
                                                            self.view.calibration_widget,
                                                            self.img_data,
                                                            self.mask_data,
                                                            self.calibration_data)
        self.mask_controller = MaskController(self.working_directories,
                                              self.view.mask_widget,
                                              self.img_data,
                                              self.mask_data)
        self.integration_controller = IntegrationController(self.working_directories,
                                                            self.view.integration_widget,
                                                            self.img_data,
                                                            self.mask_data,
                                                            self.calibration_data,
                                                            self.spectrum_data,
                                                            self.phase_data)
        self.create_signals()
        self.set_title()

    def show_window(self):
        self.view.show()
        self.view.setWindowState(self.view.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
        self.view.activateWindow()
        self.view.raise_()

    def create_signals(self):
        self.view.tabWidget.currentChanged.connect(self.tab_changed)
        self.view.closeEvent = self.close_event
        self.img_data.subscribe(self.set_title)
        self.spectrum_data.spectrum_changed.connect(self.set_title)

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
        if os.path.exists(self.settings_directory):
            self.load_directories()
            self.load_xml_settings()

    def load_directories(self):
        working_directories_path = os.path.join(self.settings_directory, 'working_directories.csv')
        if os.path.exists(working_directories_path):
            reader = csv.reader(open(working_directories_path, 'r'))
            self.working_directories = dict(x for x in reader)


    def load_xml_settings(self):
        xml_settings_path = os.path.join(self.settings_directory, "settings.xml")
        if os.path.exists(xml_settings_path):
            tree = ET.parse(xml_settings_path)
            root = tree.getroot()
            filenames = root.find("filenames")
            calibration_path=filenames.find("calibration").text
            if os.path.exists(str(calibration_path)):
                self.calibration_data.load(calibration_path)

    def save_settings(self):
        if not os.path.exists(self.settings_directory):
            os.mkdir(self.settings_directory)
        self.save_directories()
        self.save_xml_settings()

    def save_directories(self):
        working_directories_path = os.path.join(self.settings_directory, 'working_directories.csv')
        writer = csv.writer(open(working_directories_path, 'w'))
        for key, value in list(self.working_directories.items()):
            writer.writerow([key, value])
            writer.writerow([key, value])

    def save_xml_settings(self):
        root = ET.Element("DioptasSettings")
        filenames = ET.SubElement(root, "filenames")
        calibration_filename = ET.SubElement(filenames, "calibration")
        calibration_filename.text = self.calibration_data.filename
        tree = ET.ElementTree(root)
        tree.write(os.path.join(self.settings_directory, "settings.xml"))

    def close_event(self, _):
        if self.use_settings:
            self.save_settings()
        QtGui.QApplication.closeAllWindows()
        QtGui.QApplication.quit()
