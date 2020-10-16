from glob import glob
import os
from functools import partial

import numpy as np
from PIL import Image
from qtpy import QtWidgets, QtCore, QtGui

from ...widgets.UtilityWidgets import open_file_dialog, open_files_dialog, save_file_dialog
# imports for type hinting in PyCharm -- DO NOT DELETE
from ...widgets.integration import IntegrationWidget
from ...model.DioptasModel import DioptasModel
from ...model.util.HelperModule import get_partial_index, get_partial_value


class ScanController(object):
    """
    The class manages the Image actions in the batch integration Window. It connects the file actions, as
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

        self.clicks = 0
        self.rect = None

        self.create_signals()
        self.create_mouse_behavior()

        self.integration_unit = '2th_deg'

    def create_signals(self):
        """
        Creates all the connections of the GUI elements.
        """
        self.widget.scan_widget.load_btn.clicked.connect(self.load_img_files)
        self.widget.scan_widget.integrate_btn.clicked.connect(self.integrate)
        self.widget.scan_widget.save_btn.clicked.connect(self.save_data)
        self.widget.scan_widget.view_3d_btn.clicked.connect(self.change_view)
        self.widget.scan_widget.waterfall_btn.clicked.connect(self.waterfall_mode)
        self.widget.scan_widget.scale_log_btn.clicked.connect(self.change_scale)
        self.widget.scan_widget.background_btn.clicked.connect(self.subtract_background)
        self.widget.scan_widget.calc_bkg_btn.clicked.connect(self.extract_background)
        self.widget.scan_widget.phases_btn.clicked.connect(self.toggle_show_phases)

        # unit callbacks
        self.widget.scan_widget.tth_btn.clicked.connect(self.set_unit_tth)
        self.widget.scan_widget.q_btn.clicked.connect(self.set_unit_q)
        self.widget.scan_widget.d_btn.clicked.connect(self.set_unit_d)
        self.widget.pattern_q_btn.clicked.connect(self.set_unit_q)
        self.widget.pattern_tth_btn.clicked.connect(self.set_unit_tth)
        self.widget.pattern_d_btn.clicked.connect(self.set_unit_d)

        self.widget.img_filename_txt.editingFinished.connect(self.filename_txt_changed)
        self.widget.img_directory_txt.editingFinished.connect(self.directory_txt_changed)
        self.widget.img_directory_btn.clicked.connect(self.directory_txt_changed)

        self.widget.scan_widget.step_series_widget.next_btn.clicked.connect(self.load_next_img)
        self.widget.scan_widget.step_series_widget.previous_btn.clicked.connect(self.load_prev_img)
        self.widget.scan_widget.step_series_widget.pos_txt.editingFinished.connect(self.load_given_img)

        self.widget.scan_widget.img_view.img_view_box.sigRangeChanged.connect(self.update_axes_range)
        self.model.configuration_selected.connect(self.update_gui)

    def create_mouse_behavior(self):
        """
        Creates the signal connections of mouse interactions
        """
        self.widget.scan_widget.img_view.mouse_moved.connect(self.show_img_mouse_position)
        self.widget.scan_widget.img_view.mouse_left_clicked.connect(self.img_mouse_click)

        self.widget.pattern_widget.mouse_left_clicked.connect(self.pattern_left_click)

    def pattern_left_click(self, x, y):
        """
        Update position of vertical line

        :param x: Position of vertical line on pattern plot in current_configuration units
        """
        x = self.convert_x_value(x, self.model.current_configuration.integration_unit, '2th_deg')
        data_img_item = self.widget.scan_widget.img_view.data_img_item
        cake_tth = self.model.scan_model.binning
        if cake_tth is None:
            return
        bound = data_img_item.boundingRect().width()
        h_scale = (np.max(cake_tth) - np.min(cake_tth)) / bound
        h_shift = np.min(cake_tth)
        pos = (x - h_shift)/h_scale

        self.widget.scan_widget.img_view.vertical_line.setValue(pos)

    def set_unit_tth(self):
        """
        Set 2th_deg unit on batch plot

        Corresponding buttons on batch and pattern widgets are checked.
        """
        previous_unit = self.integration_unit
        self.widget.scan_widget.tth_btn.setChecked(True)
        self.widget.pattern_tth_btn.setChecked(True)
        if previous_unit == '2th_deg':
            return
        self.integration_unit = '2th_deg'

        self.model.current_configuration.integration_unit = '2th_deg'
        self.widget.scan_widget.img_view.bottom_axis_cake.setLabel(u'2θ', '°')
        self.widget.scan_widget.img_view.img_view_box.invertX(False)
        if self.model.calibration_model.is_calibrated:
            self.update_x_axis()

    def set_unit_q(self):
        """
        Set q_A^-1 unit on batch plot

        Corresponding buttons on batch and pattern widgets are checked.
        """
        previous_unit = self.integration_unit
        self.widget.scan_widget.q_btn.setChecked(True)
        self.widget.pattern_q_btn.setChecked(True)
        if previous_unit == 'q_A^-1':
            return
        self.integration_unit = "q_A^-1"

        self.model.current_configuration.integration_unit = "q_A^-1"
        self.widget.scan_widget.img_view.img_view_box.invertX(False)
        self.widget.scan_widget.img_view.bottom_axis_cake.setLabel('Q', 'A<sup>-1</sup>')
        if self.model.calibration_model.is_calibrated:
            self.update_x_axis()

    def set_unit_d(self):
        """
        Set d_A unit on batch plot

        Corresponding buttons on batch and pattern widgets are checked.
        """
        previous_unit = self.integration_unit
        self.widget.scan_widget.d_btn.setChecked(True)
        self.widget.pattern_d_btn.setChecked(True)
        if previous_unit == 'd_A':
            return
        self.integration_unit = 'd_A'

        self.model.current_configuration.integration_unit = 'd_A'
        self.widget.scan_widget.img_view.bottom_axis_cake.setLabel('d', 'A')
        self.widget.scan_widget.img_view.img_view_box.invertX(True)
        if self.model.calibration_model.is_calibrated:
            self.update_x_axis()

    def toggle_show_phases(self):
        """
        Show and hide phases
        """
        if str(self.widget.scan_widget.phases_btn.text()) == 'Show Phases':
            self.widget.scan_widget.img_view.show_all_visible_cake_phases(
                self.widget.phase_widget.phase_show_cbs)
            self.widget.scan_widget.phases_btn.setText('Hide Phases')
            self.model.enabled_phases_in_cake.emit()
        elif str(self.widget.scan_widget.phases_btn.text()) == 'Hide Phases':
            self.widget.scan_widget.img_view.hide_all_cake_phases()
            self.widget.scan_widget.phases_btn.setText('Show Phases')

    def subtract_background(self):
        """
        Toddle background subtraction in batch image
        """
        data = self.model.scan_model.data
        bkg = self.model.scan_model.bkg
        if data is None or bkg is None or data.shape != bkg.shape:
            return
        if self.widget.scan_widget.background_btn.isChecked():
            self.widget.scan_widget.img_view.plot_image(data-bkg, True)
        else:
            self.widget.scan_widget.img_view.plot_image(data, True)

    def extract_background(self):
        """
        Extract background from batch data
        """
        progress_dialog = self.widget.get_progress_dialog("Integrating multiple images.", "Abort Integration",
                                                          self.model.scan_model.n_img)

        parameters = self.widget.integration_control_widget.background_control_widget.get_bkg_pattern_parameters()
        self.model.scan_model.extract_background(parameters, progress_dialog)
        progress_dialog.close()

    def change_scale(self):
        """
        Change scale between log and linear
        """
        img = self.model.scan_model.data
        if img is None:
            return
        if self.widget.scan_widget.change_scale_btn.isChecked():
            self.widget.scan_widget.img_view.plot_image(np.log10(img), True)
            self.widget.scan_widget.surf_view.plot_surf(np.log10(img))
            self.widget.scan_widget.img_view.auto_level()
        else:
            self.widget.scan_widget.img_view.plot_image(img, True)
            self.widget.scan_widget.surf_view.plot_surf(img)
            self.widget.scan_widget.img_view.auto_level()

    def waterfall_mode(self):
        """
        Set/unset widget in waterfall mode
        """
        if self.widget.scan_widget.waterfall_btn.isChecked():
            self.widget.scan_widget.img_view.vertical_line.setVisible(False)
            self.widget.scan_widget.img_view.horizontal_line.setVisible(False)
        else:
            if self.rect is not None:
                self.widget.scan_widget.img_view.img_view_box.removeItem(self.rect)
            self.widget.scan_widget.img_view.vertical_line.setVisible(True)
            self.widget.scan_widget.img_view.horizontal_line.setVisible(True)

    def load_next_img(self):
        """
        Load next image in the batch
        """
        step = int(str(self.widget.scan_widget.step_series_widget.step_txt.text()))
        pos = int(str(self.widget.scan_widget.step_series_widget.pos_txt.text()))
        x = self.widget.scan_widget.img_view.vertical_line.getXPos()
        y = pos + step
        self.widget.scan_widget.img_view.horizontal_line.setValue(y)
        self.load_single_image(x, y)

    def load_prev_img(self):
        """
        Load previous image in the batch
        """
        step = int(str(self.widget.scan_widget.step_series_widget.step_txt.text()))
        pos = int(str(self.widget.scan_widget.step_series_widget.pos_txt.text()))
        x = self.widget.scan_widget.img_view.vertical_line.getXPos()
        y = pos - step
        self.widget.scan_widget.img_view.horizontal_line.setValue(y)
        self.load_single_image(x, y)

    def load_given_img(self):
        """
        Load image given in the text box
        """
        pos = int(str(self.widget.scan_widget.step_series_widget.pos_txt.text()))
        x = self.widget.scan_widget.img_view.vertical_line.getXPos()
        self.widget.scan_widget.img_view.horizontal_line.setValue(pos)
        self.load_single_image(x, pos)

    def show_img_mouse_position(self, x, y):
        """
        Show position of the mouse with respect of the heatmap

        Show image number, position in diffraction pattern and intensity
        """
        img = self.model.scan_model.data
        binning = self.model.scan_model.binning
        if img is None or x > img.shape[1] or x < 0 or y > img.shape[0] or y < 0:
            return
        scale = (binning[-1] - binning[0]) / binning.shape[0]
        tth = x * scale + binning[0]
        z = img[int(y), int(x)]

        self.widget.scan_widget.mouse_pos_widget.cur_pos_widget.x_pos_lbl.setText(f'Img: {int(y):.0f}')
        self.widget.scan_widget.mouse_pos_widget.cur_pos_widget.y_pos_lbl.setText(f'2θ:{tth:.1f}')
        self.widget.scan_widget.mouse_pos_widget.cur_pos_widget.int_lbl.setText(f'{z:.1f}')

    def change_view(self):
        """
        Change between 2D and 3D view
        """
        if self.widget.scan_widget.view_mode == 0:
            self.widget.scan_widget.view_mode = 1
            self.widget.scan_widget.img_pg_layout.hide()
            self.widget.scan_widget.surf_pg_layout.show()
            self.widget.scan_widget.change_view_btn.setText("2D")
        else:
            self.widget.scan_widget.view_mode = 0
            self.widget.scan_widget.surf_pg_layout.hide()
            self.widget.scan_widget.img_pg_layout.show()
            self.widget.scan_widget.change_view_btn.setText("3D")

    def filename_txt_changed(self):
        """
        Set image files of the batch base on filename given in the text box
        """
        current_filenames = self.model.scan_model.files
        current_directory = self.model.working_directories['image']

        img_filename_txt = str(self.widget.img_filename_txt.text())
        new_filenames = []
        for t in img_filename_txt.split():
            print(os.path.join(current_directory, t))
            new_filenames += glob(os.path.join(current_directory, t))

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
        """
        Change directory name for image files of the batch
        """
        new_directory = str(self.widget.img_directory_txt.text())
        current_filenames = self.model.scan_model.files
        if current_filenames is None:
            return
        filenames = [os.path.basename(f) for f in current_filenames]
        new_filenames = [os.path.join(new_directory, f) for f in filenames]
        self.model.scan_model.set_image_files(new_filenames)

    def load_img_files(self):
        """
        Set image files of the batch, base on files given in the dialog window
        """
        filenames = open_files_dialog(self.widget, "Load image data file(s)",
                                      self.model.working_directories['image'],
                                      ('Raw data (*.nxs *tif *tiff);;'
                                       'Proc data (*.nxs)')
                                      )

        name, ext = os.path.splitext(filenames[0])
        if ext == '.h5':
            self.load_proc_data(filenames[0])
        else:
            self.widget.img_directory_txt.setText(os.path.dirname(filenames[0]))
            self.model.working_directories['image'] = os.path.dirname(filenames[0])

            basenames = [os.path.basename(f) for f in filenames]
            self.widget.img_filename_txt.setText(' '.join(basenames))
            self.model.img_model.blockSignals(True)
            self.model.scan_model.reset_data()
            self.model.scan_model.set_image_files(filenames)
            self.model.img_model.blockSignals(False)

            n_img_all = self.model.scan_model.n_img_all
            files = self.model.scan_model.files
            file_map = self.model.scan_model.file_map
            self.widget.scan_widget.step_series_widget.pos_validator.setRange(0, n_img_all - 1)
            self.widget.scan_widget.step_series_widget.pos_label.setText(f"Frame(-/{n_img_all}):")

            for i, file in enumerate(files):
                self.widget.scan_widget.tree_model.appendRow(QtGui.QStandardItem(f"{file}"))
                self.widget.scan_widget.tree_model.setItem(i, 1, QtGui.QStandardItem(f"{file_map[i+1]-file_map[i]}"))

            #self.widget.scan_widget.img_view.plot_image(data, True)
            #self.update_axes_range()

    def load_proc_data(self, filename):
        """
        Load processed data (diffraction patterns and metadata)
        """
        self.model.scan_model.load_proc_data(filename)
        self.widget.calibration_lbl.setText(
            self.model.calibration_model.calibration_name)
        img = self.model.scan_model.data
        self.widget.scan_widget.img_view.plot_image(img, True)
        #self.widget.scan_widget.surf_view.plot_surf(img)
        self.widget.scan_widget.img_view.auto_level()

        n_img = self.model.scan_model.n_img
        n_img_all = self.model.scan_model.n_img_all
        self.widget.scan_widget.step_series_widget.pos_validator.setRange(0, n_img - 1)
        self.widget.scan_widget.step_series_widget.pos_label.setText(f"Frame({n_img}/{n_img_all}):")

    def save_data(self):
        """
        Save diffraction patterns and metadata
        """
        filename = save_file_dialog(self.widget, "Save Image.",
                                    os.path.join(self.model.working_directories['image']),
                                    ('Image (*.png);;Single file ascii (*csv);;'
                                     'Multifile ascii (*.xy *.chi *.dat);;'
                                     'GSAS (*.fxye);;Data (*nxs)'))

        name, ext = os.path.splitext(filename)
        if filename is not '':
            if ext == '.png':
                if self.widget.scan_widget.view_mode == 0:
                    QtWidgets.QApplication.processEvents()
                    self.widget.scan_widget.img_view.save_img(filename)
            elif ext == '.nxs':
                self.model.scan_model.save_proc_data(filename)
            elif ext == '.csv':
                self.model.scan_model.save_as_csv(filename)
            else:
                self.model.img_model.blockSignals(True)
                img_data = self.model.scan_model.data
                pattern_x = self.model.scan_model.binning
                for y in range(img_data.shape[0]):
                    pattern_y = img_data[int(y)]
                    self.model.pattern_model.set_pattern(pattern_x, pattern_y)
                    self.model.current_configuration.save_pattern(f"{name}_{y}.{ext}", subtract_background=True)
                self.model.img_model.blockSignals(False)

    def img_mouse_click(self, x, y):
        """
        Process mouse click
        """
        if self.widget.scan_widget.waterfall_btn.isChecked():
            self.process_waterfall(x, y)
        else:
            self.load_single_image(x, y)

    def process_waterfall(self, x, y):
        """
        Create waterfall plot based on selected rectangle in the heatmap
        """
        if self.clicks == 0:
            self.clicks += 1
            if self.rect is not None:
                self.widget.scan_widget.img_view.img_view_box.removeItem(self.rect)
            self.rect = self.widget.scan_widget.img_view.draw_rectangle(x, y)
            self.widget.scan_widget.img_view.mouse_moved.connect(self.rect.set_size)
        elif self.clicks == 1:
            self.clicks = 0
            self.widget.scan_widget.img_view.mouse_moved.disconnect(self.rect.set_size)
            # create waterfall plot
            data = self.model.scan_model.data
            binning = self.model.scan_model.binning
            rect = self.rect.rect()
            y1, y2 = sorted((int(rect.top()), int(rect.top() - rect.height())))
            x1, x2 = sorted((int(rect.left()), int(rect.left() - rect.width())))
            step = int(str(self.widget.scan_widget.step_series_widget.step_txt.text()))
            for i in range(y1, y2, step):
                self.model.overlay_model.add_overlay(binning[x1:x2], data[i, x1:x2])

    def load_single_image(self, x, y):
        """
        Load single image and draw lines on the heatmap plot based on given x and y
        """
        img = self.model.scan_model.data
        binning = self.model.scan_model.binning
        if img is None or x > img.shape[1] or x < 0 or y > img.shape[0] or y < 0:
            return
        scale = (binning[-1] - binning[0]) / binning.shape[0]
        tth = x * scale + binning[0]
        z = img[int(y), int(x)]

        self.widget.scan_widget.mouse_pos_widget.clicked_pos_widget.x_pos_lbl.setText(f'Img: {int(y):.0f}')
        self.widget.scan_widget.mouse_pos_widget.clicked_pos_widget.y_pos_lbl.setText(f'2θ:{tth:.1f}')
        self.widget.scan_widget.mouse_pos_widget.clicked_pos_widget.int_lbl.setText(f'I: {z:.1f}')
        self.widget.scan_widget.step_series_widget.pos_txt.setText(str(int(y)))

        self.model.current_configuration.auto_integrate_pattern = False
        self.model.scan_model.load_image(int(y))
        self.model.current_configuration.auto_integrate_pattern = True

        x0 = self.convert_x_value(binning[0], '2th_deg', self.model.current_configuration.integration_unit)
        x1 = self.convert_x_value(binning[-1], '2th_deg', self.model.current_configuration.integration_unit)
        self.model.pattern_model.set_pattern(np.linspace(x0, x1, binning.shape[0]), img[int(y)])

    def update_axes_range(self):
        """
        Update axis of the 2D image
        """
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
        elif self.model.current_configuration.integration_unit == 'd_A':
            self.widget.scan_widget.img_view.bottom_axis_cake.setRange(
                self.convert_x_value(max_tth, '2th_deg', 'd_A'),
                self.convert_x_value(min_tth, '2th_deg', 'd_A'))

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
        """
        Integrate images in the batch
        """
        if not self.model.calibration_model.is_calibrated:
            self.widget.show_error_msg("Can not integrate multiple images without calibration.")
            return
        if self.model.scan_model.n_img_all is None or self.model.scan_model.n_img_all < 1:
            self.widget.show_error_msg("No images loaded for integration")
            return

        if not self.widget.automatic_binning_cb.isChecked():
            num_points = int(str(self.widget.bin_count_txt.text()))
        else:
            num_points = None

        step = int(str(self.widget.scan_widget.step_series_widget.step_txt.text()))

        self.model.img_model.blockSignals(True)
        self.model.blockSignals(True)
        progress_dialog = self.widget.get_progress_dialog("Integrating multiple images.", "Abort Integration",
                                                          self.model.scan_model.n_img_all)
        self.model.scan_model.integrate_raw_data(progress_dialog, num_points, step)
        progress_dialog.close()
        self.model.img_model.blockSignals(False)
        self.model.blockSignals(False)
        img = self.model.scan_model.data
        n_img = self.model.scan_model.n_img
        n_img_all = self.model.scan_model.n_img_all
        self.widget.scan_widget.step_series_widget.pos_label.setText(f"Frame({n_img}/{n_img_all}):")

        self.widget.scan_widget.img_view.plot_image(img, True)
        self.widget.scan_widget.surf_view.plot_surf(img)
        self.widget.scan_widget.img_view.auto_level()

    def update_gui(self):
        if self.model.current_configuration.integration_unit == '2th_deg':
            self.widget.scan_widget.tth_btn.setChecked(True)
            self.set_unit_tth()
        elif self.model.current_configuration.integration_unit == 'd_A':
            self.widget.scan_widget.d_btn.setChecked(True)
            self.set_unit_d()
        elif self.model.current_configuration.integration_unit == 'q_A^-1':
            self.widget.scan_widget.q_btn.setChecked(True)
            self.set_unit_q()
