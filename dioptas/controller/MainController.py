# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2015  Clemens Prescher (clemens.prescher@gmail.com)
# Institute for Geology and Mineralogy, University of Cologne
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
from sys import platform as _platform
from qtpy import QtWidgets, QtCore

import xml.etree.cElementTree as ET

from ..widgets.MainWidget import MainWidget
from ..model.DioptasModel import DioptasModel
from ..widgets.UtilityWidgets import save_file_dialog, open_file_dialog

from . import CalibrationController
from .integration import IntegrationController
from .MaskController import MaskController
from .ConfigurationController import ConfigurationController

from dioptas import __version__


class MainController(object):
    """
    Creates a the main controller for Dioptas. Creates all the data objects and connects them with the other controllers
    """

    def __init__(self, use_settings=True):
        self.use_settings = use_settings

        self.widget = MainWidget()

        # create data

        self.settings_directory = os.path.join(os.path.expanduser("~"), '.Dioptas')
        self.working_directories = {'calibration': '', 'mask': '', 'image': '', 'pattern': '', 'overlay': '',
                                    'phase': ''}

        self.model = DioptasModel(self.working_directories)

        if use_settings:
            self.load_settings()

        self.calibration_controller = CalibrationController(self.working_directories,
                                                            self.widget.calibration_widget,
                                                            self.model)
        self.mask_controller = MaskController(self.working_directories,
                                              self.widget.mask_widget,
                                              self.model)
        self.integration_controller = IntegrationController(self.working_directories,
                                                            self.widget.integration_widget,
                                                            self.model)

        self.configuration_controller = ConfigurationController(
            configuration_widget=self.widget.configuration_widget,
            dioptas_model=self.model,
            controllers=[
                self.calibration_controller,
                self.mask_controller,
                self.integration_controller,
                self
            ]
        )

        self.create_signals()
        self.update_title()

        self.current_tab_index = 0

    def show_window(self):
        """
        Displays the main window on the screen and makes it active.
        """
        self.widget.show()

        if _platform == "darwin":
            self.widget.setWindowState(self.widget.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
            self.widget.activateWindow()
            self.widget.raise_()

    def create_signals(self):
        """
        Creates subscriptions for changing tabs and also newly loaded files which will update the title of the main
                window.
        """
        self.widget.tabWidget.currentChanged.connect(self.tab_changed)
        self.widget.closeEvent = self.close_event
        self.widget.show_configuration_menu_btn.toggled.connect(self.widget.configuration_widget.setVisible)

        self.widget.calibration_mode_btn.toggled.connect(self.widget.calibration_widget.setVisible)
        self.widget.mask_mode_btn.toggled.connect(self.widget.mask_widget.setVisible)
        self.widget.integration_mode_btn.toggled.connect(self.widget.integration_widget.setVisible)

        self.widget.mode_btn_group.buttonToggled.connect(self.tab_changed)

        self.model.img_changed.connect(self.update_title)
        self.model.pattern_changed.connect(self.update_title)

        self.widget.save_btn.clicked.connect(self.save_btn_clicked)
        self.widget.load_btn.clicked.connect(self.load_btn_clicked)

    def tab_changed(self):
        """
        Function which is called when a tab has been selected (calibration, mask, or integration). Performs
        needed initialization tasks.
        :param ind: index for the tab selected (2 - integration, 1 = mask, 0 - calibration)
        :return:
        """
        if self.widget.calibration_mode_btn.isChecked():
            ind = 0
        elif self.widget.mask_mode_btn.isChecked():
            ind = 1
        elif self.widget.integration_mode_btn.isChecked():
            ind = 2
        else:
            return

        old_index = self.current_tab_index
        self.current_tab_index = ind

        # get the old view range
        old_view_range = None
        old_hist_levels = None
        if old_index == 0:  # calibration tab
            old_view_range = self.widget.calibration_widget.img_widget.img_view_box.targetRange()
            old_hist_levels = self.widget.calibration_widget.img_widget.img_histogram_LUT.getExpLevels()
        elif old_index == 1:  # mask tab
            old_view_range = self.widget.mask_widget.img_widget.img_view_box.targetRange()
            old_hist_levels = self.widget.mask_widget.img_widget.img_histogram_LUT.getExpLevels()
        elif old_index == 2:
            old_view_range = self.widget.integration_widget.img_widget.img_view_box.targetRange()
            old_hist_levels = self.widget.integration_widget.img_widget.img_histogram_LUT.getExpLevels()

        # update the GUI
        if ind == 2:  # integration tab
            self.model.mask_model.set_supersampling()
            self.integration_controller.image_controller.plot_mask()
            self.integration_controller.widget.calibration_lbl.setText(self.model.calibration_model.calibration_name)
            self.integration_controller.image_controller._auto_scale = False

            if self.integration_controller.image_controller.img_mode == "Image":
                self.integration_controller.image_controller.plot_img()

            if self.model.use_mask:
                self.model.current_configuration.integrate_image_1d()
                if self.model.current_configuration.auto_integrate_cake:
                    self.model.current_configuration.integrate_image_2d()
            else:
                self.model.pattern_changed.emit()
            self.widget.integration_widget.img_widget.set_range(x_range=old_view_range[0], y_range=old_view_range[1])
            self.widget.integration_widget.img_widget.img_histogram_LUT.setLevels(*old_hist_levels)
        elif ind == 1:  # mask tab
            self.mask_controller.plot_mask()
            self.mask_controller.plot_image()
            self.widget.mask_widget.img_widget.set_range(x_range=old_view_range[0], y_range=old_view_range[1])
            self.widget.mask_widget.img_widget.img_histogram_LUT.setLevels(*old_hist_levels)
        elif ind == 0:  # calibration tab
            self.calibration_controller.plot_mask()
            try:
                self.calibration_controller.update_calibration_parameter_in_view()
            except (TypeError, AttributeError):
                pass
            self.widget.calibration_widget.img_widget.set_range(x_range=old_view_range[0], y_range=old_view_range[1])
            self.widget.calibration_widget.img_widget.img_histogram_LUT.setLevels(*old_hist_levels)

    def update_title(self):
        """
        Updates the title bar of the main window. The title bar will always show the current version of Dioptas, the
        image or pattern filenames loaded and the current calibration name.
        """
        img_filename = os.path.basename(self.model.img_model.filename)
        pattern_filename = os.path.basename(self.model.pattern.filename)
        calibration_name = self.model.calibration_model.calibration_name
        str = 'Dioptas ' + __version__
        if img_filename is '' and pattern_filename is '':
            self.widget.setWindowTitle(str + u' - © 2017 C. Prescher')
            self.widget.integration_widget.img_frame.setWindowTitle(str + u' - © 2017 C. Prescher')
            return

        if img_filename is not '' or pattern_filename is not '':
            str += ' - ['
        if img_filename is not '':
            str += img_filename
        elif img_filename is '' and pattern_filename is not '':
            str += pattern_filename
        if not img_filename == pattern_filename:
            str += ', ' + pattern_filename
        if calibration_name is not None:
            str += ', calibration: ' + calibration_name
        str += ']'
        str += u' - © 2017 C. Prescher'
        self.widget.setWindowTitle(str)
        self.widget.integration_widget.img_frame.setWindowTitle(str)

    def load_settings(self):
        """
        Loads previously saved Dioptas settings.
        """
        if os.path.exists(self.settings_directory):
            self.load_directories()
            self.load_xml_settings()

    def load_directories(self):
        """
        Loads previously used Dioptas directory paths.
        """
        working_directories_path = os.path.join(self.settings_directory, 'working_directories.csv')
        if os.path.exists(working_directories_path):
            reader = csv.reader(open(working_directories_path, 'r'))
            for x in reader:
                if len(x) > 1:
                    self.working_directories[x[0]] = x[1]

    def load_xml_settings(self):
        """
        Loads previously used Dioptas settings. Currently this is only the calibration.
        :return:
        """
        xml_settings_path = os.path.join(self.settings_directory, "settings.xml")
        if os.path.exists(xml_settings_path):
            tree = ET.parse(xml_settings_path)
            root = tree.getroot()
            filenames = root.find("filenames")
            calibration_path = filenames.find("calibration").text
            if os.path.exists(str(calibration_path)):
                self.model.calibration_model.load(calibration_path)

    def save_settings(self):
        """
        Saves current settings of Dioptas in the users directory.
        """
        if not os.path.exists(self.settings_directory):
            os.mkdir(self.settings_directory)
        self.save_directories()
        self.save_xml_settings()

    def save_directories(self):
        """
        Currently used working directories for images, , etc. are saved as csv file in the users directory for
        reuse when Dioptas is started again
        """

        working_directories_path = os.path.join(self.settings_directory, 'working_directories.csv')
        writer = csv.writer(open(working_directories_path, 'w'))
        for key, value in list(self.working_directories.items()):
            writer.writerow([key, value])

    def save_xml_settings(self):
        """
        Currently used settings of Dioptas are saved in to an xml file in the users directory for reuse when Dioptas is
        started again. Right now this is only saving the calibration filename.
        """
        root = ET.Element("DioptasSettings")
        filenames = ET.SubElement(root, "filenames")
        calibration_filename = ET.SubElement(filenames, "calibration")
        calibration_filename.text = self.model.calibration_model.filename
        tree = ET.ElementTree(root)
        tree.write(os.path.join(self.settings_directory, "settings.xml"))

    def close_event(self, ev):
        """
        Intervention of the Dioptas close event to save settings before closing the Program.
        """
        if self.use_settings:
            self.save_settings()
        QtWidgets.QApplication.closeAllWindows()
        ev.accept()


    def save_btn_clicked(self):
        try:
            default_file_name = self.model.working_directories['image'] + 'config.hdf5'
        except TypeError:
            default_file_name = '.'
        filename = save_file_dialog(self.widget, "Save Current Configuration", default_file_name,
                                    filter='Config (*.hdf5)')

        if filename is not None and filename !='':
            self.model.save(filename)

    def load_btn_clicked(self):
        try:
            default_file_name = self.model.working_directories['image'] + 'config.hdf5'
        except TypeError:
            default_file_name = '.'
        filename = open_file_dialog(self.widget, "Load a Configuration", default_file_name, filter='Config (*.hdf5)')
        if filename is not None and filename !='':
            self.model.load(filename)
