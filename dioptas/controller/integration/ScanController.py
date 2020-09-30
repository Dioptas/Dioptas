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

        self.widget.scan_widget.img_view.img_view_box.sigRangeChanged.connect(self.update_scan_azimuth_axis)

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
        print(x, y)
        if 0 < x < img_data.shape[1] - 1 and 0 < y < img_data.shape[0] - 1:
            self.model.current_configuration.auto_integrate_pattern = False
            self.model.scan_model.load_image(int(y))
            self.model.current_configuration.auto_integrate_pattern = True
            pattern_x = self.model.scan_model.binning
            pattern_y = img_data[int(y)]
            self.model.pattern_model.set_pattern(pattern_x, pattern_y)

    def update_scan_azimuth_axis(self):
        data_img_item = self.widget.scan_widget.img_view.data_img_item
        cake_azi = self.model.cake_azi
        #ToDo Fix it.
        if cake_azi is None:
            cake_azi = [0, 1]

        height = data_img_item.viewRect().height()
        bottom = data_img_item.viewRect().top()
        v_scale = (cake_azi[-1] - cake_azi[0]) / data_img_item.boundingRect().height()
        v_shift = np.min(cake_azi[0])
        min_azi = v_scale * bottom + v_shift
        max_azi = v_scale * (bottom + height) + v_shift

        self.widget.scan_widget.img_view.left_axis_cake.setRange(min_azi, max_azi)

    def integrate(self):

        self.model.img_model.blockSignals(True)
        self.model.scan_model.integrate_raw_data()
        self.model.img_model.blockSignals(False)
        img = self.model.scan_model.data
        self.widget.scan_widget.img_view.plot_image(img, True)
        self.widget.scan_widget.img_view.auto_level()
