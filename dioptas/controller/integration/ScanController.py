from glob import glob
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
        self.widget.scan_widget.change_view_btn.clicked.connect(self.change_view)

        self.widget.img_filename_txt.editingFinished.connect(self.filename_txt_changed)
        self.widget.img_directory_txt.editingFinished.connect(self.directory_txt_changed)
        self.widget.img_directory_btn.clicked.connect(self.directory_txt_changed)

        self.widget.scan_widget.img_view.img_view_box.sigRangeChanged.connect(self.update_axes_range)

    def create_mouse_behavior(self):
        """
        Creates the signal connections of mouse interactions
        """

        self.widget.scan_widget.img_view.mouse_left_clicked.connect(self.img_mouse_click)

    def change_view(self):
        if self.widget.scan_widget.view_mode == 0:
            self.widget.scan_widget.view_mode = 1
            self.widget.scan_widget.img_pg_layout.hide()
            self.widget.scan_widget.surf_pg_layout.show()
            self.widget.scan_widget.change_view_btn.setText("Show in 2D")
        else:
            self.widget.scan_widget.view_mode = 0
            self.widget.scan_widget.surf_pg_layout.hide()
            self.widget.scan_widget.img_pg_layout.show()
            self.widget.scan_widget.change_view_btn.setText("Show in 3D")

    def filename_txt_changed(self):
        current_filenames = self.model.scan_model.files
        current_directory = self.model.working_directories['image']

        print(current_directory)
        img_filename_txt = str(self.widget.img_filename_txt.text())
        new_filenames = []
        for t in img_filename_txt.split():
            print(os.path.join(current_directory, t))
            new_filenames += glob(os.path.join(current_directory, t))

        print(new_filenames, current_filenames)
        if len(new_filenames) > 0:
            try:
                self.model.scan_model.set_image_files(new_filenames)
            except TypeError:
                basenames = [os.path.basename(f) for f in current_filenames]
                self.widget.img_filename_txt.setText(' '.join(basenames))
        else:
            basenames = [os.path.basename(f) for f in current_filenames]
            self.widget.img_filename_txt.setText(' '.join(basenames))

    def directory_txt_changed(self):
        new_directory = str(self.widget.img_directory_txt.text())
        print("Process new directory ", new_directory)
        current_filenames = self.model.scan_model.files
        if current_filenames is None:
            return
        filenames = [os.path.basename(f) for f in current_filenames]
        new_filenames = [os.path.join(new_directory, f) for f in filenames]
        self.model.scan_model.set_image_files(new_filenames)

    def load_img_files(self):
        filenames = open_files_dialog(self.widget, "Load image data file(s)",
                                      self.model.working_directories['image'])
        self.widget.img_directory_txt.setText(os.path.dirname(filenames[0]))
        self.model.working_directories['image'] = os.path.dirname(filenames[0])

        basenames = [os.path.basename(f) for f in filenames]
        self.widget.img_filename_txt.setText(' '.join(basenames))
        self.model.img_model.blockSignals(True)
        self.model.scan_model.set_image_files(filenames)
        self.model.img_model.blockSignals(False)

    def load_proc_data(self):
        filename = open_file_dialog(self.widget, "Load image data file(s)",
                                    self.model.working_directories['image'])

        self.model.scan_model.load_proc_data(filename)
        self.widget.calibration_lbl.setText(
            self.model.calibration_model.calibration_name)
        img = self.model.scan_model.data
        self.widget.scan_widget.img_view.plot_image(img, True)
        self.widget.scan_widget.surf_view.plot_surf(img)
        self.widget.scan_widget.img_view.auto_level()

    def save_data(self):
        filename = save_file_dialog(self.widget, "Save Image.",
                                    os.path.join(self.model.working_directories['image']),
                                    ('Image (*.png);;Data (*.tiff);;Text (*.txt)'))

        self.model.scan_model.save_proc_data(filename)

    def img_mouse_click(self, x, y):

        img_data = self.model.scan_model.data
        if img_data is None:
            return
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
        if not self.model.calibration_model.is_calibrated:
            self.widget.show_error_msg("Can not integrate multiple images without calibration.")
            return
        if self.model.scan_model.n_img is None or self.model.scan_model.n_img < 1:
            self.widget.show_error_msg("No images loaded for integration")
            return

        self.model.img_model.blockSignals(True)
        self.model.blockSignals(True)
        progress_dialog = self.widget.get_progress_dialog("Integrating multiple images.", "Abort Integration",
                                                          self.model.scan_model.n_img)
        self.model.scan_model.integrate_raw_data(progress_dialog)
        progress_dialog.close()
        self.model.img_model.blockSignals(False)
        self.model.blockSignals(False)
        img = self.model.scan_model.data
        self.widget.scan_widget.img_view.plot_image(img, True)
        self.widget.scan_widget.img_view.auto_level()
