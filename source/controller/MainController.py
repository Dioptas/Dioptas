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

from widgets.MainWidget import MainWidget
from model.ImgModel import ImgModel
from model.MaskModel import MaskModel
from model.SpectrumModel import SpectrumModel
from model.CalibrationModel import CalibrationModel
from model.PhaseModel import PhaseModel
from . import CalibrationController
from .integration import IntegrationController
from .MaskController import MaskController

from . import versioneer

versioneer.VCS = 'git'
versioneer.versionfile_source = ''
versioneer.versionfile_build = ''
versioneer.tag_prefix = ''
versioneer.parentdir_prefix = ''

def get_version():
    version = versioneer.get_version()
    if version not in __name__:
        write_version_file(version)
        return version
    else:
        import _version
        return _version.__version__

def write_version_file(version_str):
    path = os.path.dirname(__file__)
    with open(os.path.join(path, '_version.py'), 'w') as f:
        f.write('__version__="{}"'.format(version_str))

__version__ = get_version()

class MainController(object):
    """
    Creates a the main controller for Dioptas. Loads all the data objects and connects them with the other controllers
    """

    def __init__(self, use_settings=True):
        self.use_settings = use_settings

        self.widget = MainWidget()
        #create data
        self.img_model = ImgModel()
        self.calibration_model = CalibrationModel(self.img_model)
        self.mask_model = MaskModel()
        self.spectrum_model = SpectrumModel()
        self.phase_model = PhaseModel()

        self.settings_directory = os.path.join(os.path.expanduser("~"), '.Dioptas')
        self.working_directories = {'calibration': '', 'mask': '', 'image': '', 'spectrum': '', 'overlay': '',
                                'phase': ''}


        if use_settings:
            self.load_settings()
        #create controller
        self.calibration_controller = CalibrationController(self.working_directories,
                                                            self.widget.calibration_widget,
                                                            self.img_model,
                                                            self.mask_model,
                                                            self.calibration_model)
        self.mask_controller = MaskController(self.working_directories,
                                              self.widget.mask_widget,
                                              self.img_model,
                                              self.mask_model)
        self.integration_controller = IntegrationController(self.working_directories,
                                                            self.widget.integration_widget,
                                                            self.img_model,
                                                            self.mask_model,
                                                            self.calibration_model,
                                                            self.spectrum_model,
                                                            self.phase_model)
        self.create_signals()
        self.set_title()

    def show_window(self):
        self.widget.show()
        self.widget.setWindowState(self.widget.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
        self.widget.activateWindow()
        self.widget.raise_()

    def create_signals(self):
        self.widget.tabWidget.currentChanged.connect(self.tab_changed)
        self.widget.closeEvent = self.close_event
        self.img_model.subscribe(self.set_title)
        self.spectrum_model.spectrum_changed.connect(self.set_title)

    def tab_changed(self, ind):
        if ind == 2:
            self.mask_model.set_supersampling()
            self.integration_controller.image_controller.plot_mask()
            self.integration_controller.widget.calibration_lbl.setText(self.calibration_model.calibration_name)
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
        img_filename = os.path.basename(self.img_model.filename)
        spec_filename = os.path.basename(self.spectrum_model.spectrum_filename)
        calibration_name = self.calibration_model.calibration_name
        str = 'Dioptas ' + __version__
        if img_filename is '' and spec_filename is '':
            self.widget.setWindowTitle(str + u' - © 2015 C. Prescher')
            self.widget.integration_widget.img_frame.setWindowTitle(str + u' - © 2015 C. Prescher')
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
        str += u' - © 2015 C. Prescher'
        self.widget.setWindowTitle(str)
        self.widget.integration_widget.img_frame.setWindowTitle(str)

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
                self.calibration_model.load(calibration_path)

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
        calibration_filename.text = self.calibration_model.filename
        tree = ET.ElementTree(root)
        tree.write(os.path.join(self.settings_directory, "settings.xml"))

    def close_event(self, _):
        if self.use_settings:
            self.save_settings()
        QtGui.QApplication.closeAllWindows()
        QtGui.QApplication.quit()
