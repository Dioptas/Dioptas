import os
from functools import partial

import numpy as np
from PIL import Image
from qtpy import QtWidgets, QtCore

from ...widgets.UtilityWidgets import open_file_dialog, open_files_dialog, save_file_dialog
# imports for type hinting in PyCharm -- DO NOT DELETE
from ...widgets.integration import IntegrationWidget
from ...model.DioptasModel import DioptasModel
from ...model.util.HelperModule import get_partial_index, get_partial_value


class ScanController(object):
    """
    The ImageController manages the Image actions in the Integration Window. It connects the file actions, as
    well as interaction with the image_view.
    """

    def __init__(self, widget, dioptas_model):
        """
        :param widget: Reference to IntegrationView
        :param dioptas_model: Reference to DioptasModel object

        :type widget: IntegrationWidget
        :type dioptas_model: DioptasModel
        """
        self.widget = widget
        self.model = dioptas_model

        self.create_signals()
        self.create_mouse_behavior()


    def create_signals(self):

        """
        Creates all the connections of the GUI elements.
        """
        self.widget.scan_widget.load_files_btn.clicked.connect(self.load_img_files)
        self.widget.scan_widget.integrate_btn.clicked.connect(self.integrate)
        self.widget.scan_widget.save_btn.clicked.connect(self.save_data)
        self.widget.scan_widget.load_proc_btn.clicked.connect(self.load_proc_data)

        self.widget.scan_widget.img_view.img_view_box.sigRangeChanged.connect(self.update_axes_range)

    def create_mouse_behavior(self):
        """
        Creates the signal connections of mouse interactions
        """

        self.widget.scan_widget.img_view.mouse_left_clicked.connect(self.img_mouse_click)

    def load_img_files(self):
        filenames = open_files_dialog(self.widget, "Load image data file(s)",
                                      self.model.working_directories['image'])

        self.model.scan_model.set_image_files(filenames)

    def load_proc_data(self):
        filename = open_file_dialog(self.widget, "Load image data file(s)",
                                    self.model.working_directories['image'])

        self.model.scan_model.load_proc_data(filename)
        img = self.model.scan_model.data
        self.widget.scan_widget.img_view.plot_image(img, True)
        self.widget.scan_widget.img_view.auto_level()

    def save_data(self):
        filename = save_file_dialog(self.widget, "Save Image.",
                                    os.path.join(self.model.working_directories['image']),
                                    ('Image (*.png);;Data (*.tiff);;Text (*.txt)'))

        self.model.scan_model.save_proc_data(filename)

    def img_mouse_click(self, x, y):

        img_data = self.model.scan_model.data
        if 0 < x < img_data.shape[1] - 1 and 0 < y < img_data.shape[0] - 1:
            self.model.current_configuration.auto_integrate_pattern = False
            self.model.scan_model.load_image(int(y))
            self.model.current_configuration.auto_integrate_pattern = True
            pattern_x = self.model.scan_model.binning
            pattern_y = img_data[int(y)]
            self.model.pattern_model.set_pattern(pattern_x, pattern_y)

    def update_axes_range(self):
        self.update_x_axis()
        self.update_azimuth_axis()

    def update_x_axis(self):
        if self.model.scan_model.binning is None:
            return

        data_img_item = self.widget.scan_widget.img_view.data_img_item
        cake_tth = self.model.scan_model.binning

        width = data_img_item.viewRect().width()
        left = data_img_item.viewRect().left()
        bound = data_img_item.boundingRect().width()

        h_scale = (np.max(cake_tth) - np.min(cake_tth)) / bound
        h_shift = np.min(cake_tth)
        min_tth = h_scale * left + h_shift
        max_tth = h_scale * (left + width) + h_shift

        if self.model.current_configuration.integration_unit == '2th_deg':
            self.widget.scan_widget.img_view.bottom_axis_cake.setRange(min_tth, max_tth)
        elif self.model.current_configuration.integration_unit == 'q_A^-1':
            self.widget.scan_widget.img_view.bottom_axis_cake.setRange(
                self.convert_x_value(min_tth, '2th_deg', 'q_A^-1'),
                self.convert_x_value(max_tth, '2th_deg', 'q_A^-1'))

    def convert_x_value(self, value, previous_unit, new_unit):
        wavelength = self.model.calibration_model.wavelength
        if previous_unit == '2th_deg':
            tth = value
        elif previous_unit == 'q_A^-1':
            tth = np.arcsin(
                value * 1e10 * wavelength / (4 * np.pi)) * 360 / np.pi
        elif previous_unit == 'd_A':
            tth = 2 * np.arcsin(wavelength / (2 * value * 1e-10)) * 180 / np.pi
        else:
            tth = 0

        if new_unit == '2th_deg':
            res = tth
        elif new_unit == 'q_A^-1':
            res = 4 * np.pi * \
                  np.sin(tth / 360 * np.pi) / \
                  wavelength / 1e10
        elif new_unit == 'd_A':
            res = wavelength / (2 * np.sin(tth / 360 * np.pi)) * 1e10
        else:
            res = 0
        return res

    def update_azimuth_axis(self):

        if self.model.scan_model.data is None:
            return

        data_img_item = self.widget.scan_widget.img_view.data_img_item
        img_data = self.model.scan_model.data

        height = data_img_item.viewRect().height()
        bottom = data_img_item.viewRect().top()
        bound = data_img_item.boundingRect().height()

        v_scale = img_data.shape[0] / bound
        min_azi = v_scale * bottom
        max_azi = v_scale * (bottom + height)

        self.widget.scan_widget.img_view.left_axis_cake.setRange(min_azi, max_azi)

    def integrate(self):

        self.model.img_model.blockSignals(True)
        self.model.scan_model.integrate_raw_data()
        self.model.img_model.blockSignals(False)
        img = self.model.scan_model.data
        self.widget.scan_widget.img_view.plot_image(img, True)
        self.widget.scan_widget.img_view.auto_level()
