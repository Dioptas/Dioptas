# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
# Principal author: Clemens Prescher (clemens.prescher@gmail.com)
# Copyright (C) 2014-2019 GSECARS, University of Chicago, USA
# Copyright (C) 2015-2018 Institute for Geology and Mineralogy, University of Cologne, Germany
# Copyright (C) 2019-2020 DESY, Hamburg, Germany
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

from glob import glob
import os

import numpy as np
import h5py
from qtpy import QtWidgets, QtCore
from pyqtgraph import makeQImage

from ...model.util.HelperModule import get_partial_value, get_partial_index
from ...widgets.UtilityWidgets import open_files_dialog, save_file_dialog
from ...widgets.integration.BatchWidget import open_gl
# imports for type hinting in PyCharm -- DO NOT DELETE
from ...widgets.integration import IntegrationWidget
from ...model.DioptasModel import DioptasModel


class BatchController(object):
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
        self.scale = np.array

        self.create_signals()
        self.create_mouse_behavior()

        self.min_val = {'lin': 0, 'sqrt': 0.1, 'log': 0.1, 'current': 0}
        self.size_threshold = 500000

    def create_signals(self):
        """
        Creates all the connections of the GUI elements.
        """
        self.widget.integration_control_widget.img_control_widget.batch_btn.clicked.connect(self.show_batch_frame)
        self.widget.batch_widget.closeEvent = self.close_batch_frame

        self.widget.batch_widget.file_control_widget.load_btn.clicked.connect(self.load_data)
        self.widget.batch_widget.file_control_widget.load_previous_folder_btn.clicked.connect(self.load_previous_folder)
        self.widget.batch_widget.file_control_widget.load_next_folder_btn.clicked.connect(self.load_next_folder)
        self.widget.batch_widget.file_control_widget.save_btn.clicked.connect(self.save_data)

        self.widget.batch_widget.control_widget.integrate_btn.clicked.connect(self.integrate)
        self.widget.batch_widget.control_widget.waterfall_btn.clicked.connect(self.waterfall_mode)
        self.widget.batch_widget.control_widget.phases_btn.clicked.connect(self.toggle_show_phases)
        self.widget.batch_widget.mode_widget.view_f_btn.clicked.connect(self.change_view)
        self.widget.batch_widget.mode_widget.view_2d_btn.clicked.connect(self.change_view)
        self.widget.batch_widget.options_widget.scale_log_btn.mouseReleaseEvent = self.change_scale_log
        self.widget.batch_widget.options_widget.scale_lin_btn.mouseReleaseEvent = self.change_scale_lin
        self.widget.batch_widget.options_widget.scale_sqrt_btn.mouseReleaseEvent = self.change_scale_sqrt
        self.widget.batch_widget.options_widget.background_btn.clicked.connect(self.subtract_background)
        self.widget.batch_widget.options_widget.bkg_cut_btn.clicked.connect(lambda: self.plot_batch())
        self.widget.batch_widget.control_widget.calc_bkg_btn.clicked.connect(self.extract_background)
        self.widget.batch_widget.control_widget.autoscale_btn.clicked.connect(self.img_autoscale_btn_clicked)
        self.widget.batch_widget.control_widget.normalize_btn.clicked.connect(self.normalize_btn_clicked)

        # set unit of x axis
        self.widget.batch_widget.options_widget.tth_btn.clicked.connect(self.set_unit_tth)
        self.widget.batch_widget.options_widget.q_btn.clicked.connect(self.set_unit_q)
        self.widget.batch_widget.options_widget.d_btn.clicked.connect(self.set_unit_d)
        self.widget.pattern_q_btn.clicked.connect(self.set_unit_q)
        self.widget.pattern_tth_btn.clicked.connect(self.set_unit_tth)
        self.widget.pattern_d_btn.clicked.connect(self.set_unit_d)

        # work with filenames
        self.widget.img_directory_txt.editingFinished.connect(self.directory_txt_changed)
        self.widget.img_directory_btn.clicked.connect(self.directory_txt_changed)

        # image navigation
        self.widget.batch_widget.position_widget.step_raw_widget.switch_frame.connect(self.switch_frame)
        self.widget.batch_widget.position_widget.step_series_widget.switch_frame.connect(self.switch_frame)
        self.widget.batch_widget.position_widget.step_series_widget.start_txt.valueChanged.connect(self.set_range_img)
        self.widget.batch_widget.position_widget.step_series_widget.stop_txt.valueChanged.connect(self.set_range_img)
        self.widget.batch_widget.position_widget.step_series_widget.step_txt.valueChanged.connect(self.process_step)

        # Surface widget signals
        if open_gl:
            self.widget.batch_widget.mode_widget.view_3d_btn.clicked.connect(self.change_view)
            surface_navigation_widget = self.widget.batch_widget.surface_widget.control_widget
            surface_navigation_widget.view3d_f_btn.clicked.connect(self.set_3d_view_f)
            surface_navigation_widget.view3d_s_btn.clicked.connect(self.set_3d_view_s)
            surface_navigation_widget.view3d_t_btn.clicked.connect(self.set_3d_view_t)
            surface_navigation_widget.view3d_i_btn.clicked.connect(self.set_3d_view_i)
            surface_navigation_widget.scale_x_btn.clicked.connect(self.pressed_button_x)
            surface_navigation_widget.scale_y_btn.clicked.connect(self.pressed_button_y)
            surface_navigation_widget.scale_z_btn.clicked.connect(self.pressed_button_z)
            surface_navigation_widget.scale_s_btn.clicked.connect(self.pressed_button_s)
            surface_navigation_widget.trim_h_btn.clicked.connect(self.pressed_button_h)
            surface_navigation_widget.trim_l_btn.clicked.connect(self.pressed_button_l)
            surface_navigation_widget.move_g_btn.clicked.connect(self.pressed_button_g)
            surface_navigation_widget.move_m_btn.mouseReleaseEvent = self.pressed_button_m
            surface_navigation_widget.m_color_btn.sigColorChanged.connect(self.set_marker_color)

        self.widget.batch_widget.stack_plot_widget.img_view.img_view_box.sigRangeChanged.connect(self.update_axes_range)
        self.model.configuration_selected.connect(self.update_gui)

    def create_mouse_behavior(self):
        """
        Creates the signal connections of mouse interactions
        """
        self.widget.batch_widget.stack_plot_widget.img_view.mouse_moved.connect(self.show_img_mouse_position)
        self.widget.batch_widget.stack_plot_widget.img_view.mouse_left_clicked.connect(self.img_mouse_click)

        self.model.clicked_tth_changed.connect(self.update_vertical_line_pos)

        # 3D
        if open_gl:
            self.widget.batch_widget.surface_widget.pg_layout.wheelEvent = self.wheel_event_3d
            self.widget.batch_widget.surface_widget.pg_layout.keyPressEvent = self.key_pressed_3d

    def show_batch_frame(self):
        self.widget.batch_widget.raise_widget()

    def close_batch_frame(self, event):
        self.widget.batch_widget.hide()
        event.ignore()

    def set_3d_view_f(self):
        pg_layout = self.widget.batch_widget.surface_widget.surface_view.pg_layout
        pg_layout.opts['azimuth'] = 0
        pg_layout.opts['elevation'] = 0
        pg_layout.opts['distance'] = 3
        self.plot_batch()

    def set_3d_view_t(self):
        pg_layout = self.widget.batch_widget.surface_widget.surface_view.pg_layout
        pg_layout.opts['azimuth'] = 0
        pg_layout.opts['elevation'] = 90
        pg_layout.opts['distance'] = 3
        self.plot_batch()

    def set_3d_view_s(self):
        pg_layout = self.widget.batch_widget.surface_widget.surface_view.pg_layout
        pg_layout.opts['azimuth'] = 90
        pg_layout.opts['elevation'] = 0
        pg_layout.opts['distance'] = 3
        self.plot_batch()

    def set_3d_view_i(self):
        pg_layout = self.widget.batch_widget.surface_widget.surface_view.pg_layout
        pg_layout.opts['azimuth'] = 45
        pg_layout.opts['elevation'] = 30
        pg_layout.opts['distance'] = 3
        self.plot_batch()

    def pressed_button_x(self):
        self.key_pressed_3d(None, pressed_key=88)

    def pressed_button_y(self):
        self.key_pressed_3d(None, pressed_key=89)

    def pressed_button_z(self):
        self.key_pressed_3d(None, pressed_key=90)

    def pressed_button_1(self):
        self.key_pressed_3d(None, pressed_key=49)

    def pressed_button_2(self):
        self.key_pressed_3d(None, pressed_key=50)

    def pressed_button_3(self):
        self.key_pressed_3d(None, pressed_key=51)

    def pressed_button_h(self):
        self.key_pressed_3d(None, pressed_key=72)

    def pressed_button_l(self):
        self.key_pressed_3d(None, pressed_key=76)

    def pressed_button_g(self):
        self.key_pressed_3d(None, pressed_key=71)

    def pressed_button_m(self, ev):
        if ev.button() & QtCore.Qt.RightButton:
            val, ok = QtWidgets.QInputDialog.getInt(self.widget.integration_image_widget, 'Edit marker size',
                                                    'marker size:', min=0, max=25,
                                                    value=self.widget.batch_widget.surface_widget.surface_view.marker_size)
            if ok:
                self.widget.batch_widget.surface_widget.surface_view.marker_size = val
        self.key_pressed_3d(None, pressed_key=77)

    def pressed_button_s(self):
        self.key_pressed_3d(None, pressed_key=83)

    def set_marker_color(self):
        color = self.widget.batch_widget.surface_widget.control_widget.m_color_btn.color(mode='float')
        self.widget.batch_widget.surface_widget.surface_view.marker_color = color[:3]
        self.plot_batch()

    def key_pressed_3d(self, ev, pressed_key=None):
        navigation_widget = self.widget.batch_widget.surface_widget.control_widget
        if pressed_key is None:
            pressed_key = ev.key()
        if pressed_key == 49:
            self.widget.batch_widget.scale_lin_btn.setChecked(True)
            self.scale = np.array
        if pressed_key == 50:
            self.widget.batch_widget.scale_sqrt_btn.setChecked(True)
            self.scale = np.sqrt
        if pressed_key == 51:
            self.widget.batch_widget.scale_log_btn.setChecked(True)
            self.scale = np.log10
        if pressed_key == 66:
            if self.widget.batch_widget.options_widget.background_btn.isChecked():
                self.widget.batch_widget.options_widget.background_btn.setChecked(False)
            else:
                self.widget.batch_widget.options_widget.background_btn.setChecked(True)
        if pressed_key == 72:
            navigation_widget.trim_h_btn.setChecked(True)
        if pressed_key == 76:
            navigation_widget.trim_l_btn.setChecked(True)
        if pressed_key == 88:
            navigation_widget.scale_x_btn.setChecked(True)
        if pressed_key == 89:
            navigation_widget.scale_y_btn.setChecked(True)
        if pressed_key == 90:
            navigation_widget.scale_z_btn.setChecked(True)
        if pressed_key == 83:
            navigation_widget.scale_s_btn.setChecked(True)
        if pressed_key == 71:
            navigation_widget.move_g_btn.setChecked(True)
        if pressed_key == 77:
            navigation_widget.move_m_btn.setChecked(True)
        if pressed_key == 70:
            self.widget.batch_widget.view3d_f_btn.setChecked(True)
            self.set_3d_view_f()
        if pressed_key == 82:
            self.widget.batch_widget.view3d_s_btn.setChecked(True)
            self.set_3d_view_s()
        if pressed_key == 84:
            self.widget.batch_widget.view3d_t_btn.setChecked(True)
            self.set_3d_view_t()
        if pressed_key == 73:
            self.widget.batch_widget.view3d_i_btn.setChecked(True)
            self.set_3d_view_i()
        if pressed_key in [72, 76, 88, 89, 90, 71, 77, 83]:
            self.widget.batch_widget.surface_widget.surface_view.pressed_key = pressed_key

        self.plot_batch()

    def wheel_event_3d(self, ev):

        data = self.model.batch_model.data
        binning = self.model.batch_model.binning

        layout = self.widget.batch_widget.surface_widget.pg_layout
        pressed_key = self.widget.batch_widget.surface_widget.surface_view.pressed_key
        show_range = self.widget.batch_widget.surface_widget.surface_view.show_range
        show_scale = self.widget.batch_widget.surface_widget.surface_view.show_scale
        surf_view = self.widget.batch_widget.surface_widget.surface_view

        delta = ev.angleDelta().x()
        if delta == 0:
            delta = ev.angleDelta().y()
        diff = delta / 10000

        if pressed_key == 72:
            if 1 > show_range[1] + diff > show_range[0]:
                show_range[1] += diff
        elif pressed_key == 76:
            if 0 < show_range[0] + diff < show_range[1]:
                show_range[0] += diff
        elif pressed_key == 88:
            show_scale[0] += diff
        elif pressed_key == 89:
            show_scale[1] += diff
        elif pressed_key == 90:
            show_scale[2] += diff
        elif pressed_key == 71:
            start = int(str(self.widget.batch_widget.position_widget.step_series_widget.start_txt.text()))
            stop = int(str(self.widget.batch_widget.position_widget.step_series_widget.stop_txt.text()))
            surf_view.g_translate = min(stop, max(start, surf_view.g_translate + int(diff * data.shape[0] * 4)))
            y = int(surf_view.g_translate)
            self.widget.batch_widget.position_widget.mouse_pos_widget.cur_pos_widget.x_pos_lbl.setText(
                f'Img: {int(y):.0f}')
            self.load_single_image(int(surf_view.marker), y)
        elif pressed_key == 77:
            if 0 <= surf_view.marker + int(diff * data.shape[1]) < data.shape[1]:
                surf_view.marker += int(diff * data.shape[1])
                tth = binning[int(surf_view.marker)]
                self.widget.batch_widget.position_widget.mouse_pos_widget.cur_pos_widget.y_pos_lbl.setText(
                    f'2θ:{tth:.1f}')
                self.widget.pattern_widget.set_pos_line(tth)
        else:
            if ev.modifiers() == QtCore.Qt.ControlModifier:
                layout.opts['fov'] *= 0.999 ** delta
            else:
                layout.opts['distance'] *= 0.999 ** delta
            layout.update()

        self.plot_batch()

    def update_vertical_line_pos(self, tth):
        if self.model.batch_model.binning is None:
            return

        start_x, stop_x = self.widget.batch_widget.stack_plot_widget.img_view.x_bin_range
        binning = self.model.batch_model.binning[start_x: stop_x]
        pos = get_partial_index(binning, tth)

        if pos is None:
            self.widget.batch_widget.stack_plot_widget.img_view.deactivate_vertical_line()
            return

        self.widget.batch_widget.stack_plot_widget.img_view.activate_vertical_line()
        self.widget.batch_widget.stack_plot_widget.img_view.vertical_line.setValue(pos)

    def set_unit_tth(self):
        """
        Set 2th_deg unit on batch plot

        Corresponding buttons on batch and pattern widgets are checked.
        """
        self.widget.batch_widget.options_widget.tth_btn.setChecked(True)
        self.widget.integration_pattern_widget.tth_btn.setChecked(True)
        self.model.current_configuration.integration_unit = '2th_deg'
        self.widget.batch_widget.stack_plot_widget.img_view.bottom_axis_cake.setLabel(u'2θ', '°')
        self.widget.batch_widget.stack_plot_widget.img_view.img_view_box.invertX(False)
        self.update_x_axis()
        if not self.model.calibration_model.is_calibrated:
            x = self.widget.batch_widget.stack_plot_widget.img_view.vertical_line.getXPos()
            y = self.widget.batch_widget.position_widget.step_series_widget.slider.value()
            self.plot_pattern(int(x), int(y))

    def set_unit_q(self):
        """
        Set q_A^-1 unit on batch plot

        Corresponding buttons on batch and pattern widgets are checked.
        """
        self.widget.batch_widget.options_widget.q_btn.setChecked(True)
        self.widget.integration_pattern_widget.q_btn.setChecked(True)
        self.model.current_configuration.integration_unit = "q_A^-1"
        self.widget.batch_widget.stack_plot_widget.img_view.img_view_box.invertX(False)
        self.widget.batch_widget.stack_plot_widget.img_view.bottom_axis_cake.setLabel('Q', 'A<sup>-1</sup>')
        self.update_x_axis()
        if not self.model.calibration_model.is_calibrated:
            x = self.widget.batch_widget.stack_plot_widget.img_view.vertical_line.getXPos()
            y = self.widget.batch_widget.position_widget.step_series_widget.slider.value()
            self.plot_pattern(int(x), int(y))

    def set_unit_d(self):
        """
        Set d_A unit on batch plot

        Corresponding buttons on batch and pattern widgets are checked.
        """
        self.widget.batch_widget.options_widget.d_btn.setChecked(True)
        self.widget.integration_pattern_widget.d_btn.setChecked(True)
        self.model.current_configuration.integration_unit = 'd_A'
        self.widget.batch_widget.stack_plot_widget.img_view.bottom_axis_cake.setLabel('d', 'A')
        self.update_x_axis()
        if not self.model.calibration_model.is_calibrated:
            x = self.widget.batch_widget.stack_plot_widget.img_view.vertical_line.getXPos()
            y = self.widget.batch_widget.position_widget.step_series_widget.slider.value()
            self.plot_pattern(int(x), int(y))

    def toggle_show_phases(self):
        """
        Show and hide phases
        """
        if self.widget.batch_widget.control_widget.phases_btn.isChecked():
            self.widget.batch_widget.stack_plot_widget.img_view.show_all_visible_cake_phases(
                self.widget.phase_widget.phase_show_cbs)
            self.widget.batch_widget.control_widget.phases_btn.setText('Hide Phases')
        else:
            self.widget.batch_widget.stack_plot_widget.img_view.hide_all_cake_phases()
            self.widget.batch_widget.control_widget.phases_btn.setText('Show Phases')

    def subtract_background(self):
        """
        Toddle background subtraction in batch image
        """
        data = self.model.batch_model.data
        bkg = self.model.batch_model.bkg
        if data is None:
            return

        if bkg is None:
            self.widget.show_error_msg("Background is not yet calculated. Calculate background.")
            self.widget.batch_widget.options_widget.background_btn.setChecked(False)
            return

        if data.shape != bkg.shape:
            self.widget.show_error_msg(f"Shape of data {data.shape} and background {bkg.shape} are different."
                                       "Recalculate background.")
            self.widget.batch_widget.options_widget.background_btn.setChecked(False)
            return

        self.plot_batch()

    def extract_background(self):
        """
        Extract background from batch data
        """
        if self.model.batch_model.n_img is None:
            return
        progress_dialog = self.create_progress_dialog("Integrating multiple images.", "Abort Integration",
                                                      self.model.batch_model.n_img)

        def callback_fn(current_index):
            if progress_dialog.wasCanceled():
                return False
            progress_dialog.setValue(current_index)
            QtWidgets.QApplication.processEvents()
            return ~progress_dialog.wasCanceled()

        parameters = self.widget.integration_control_widget.background_control_widget.get_bkg_pattern_parameters()
        self.model.batch_model.extract_background(parameters, callback_fn)
        progress_dialog.close()

    def set_hard_minimum(self, ev, scale):
        if ev.button() == QtCore.Qt.RightButton:
            val, ok = QtWidgets.QInputDialog.getDouble(self.widget.integration_image_widget, 'Edit minimal value',
                                                       'value:', decimals=3,
                                                       value=self.min_val[scale])
            if ok:
                self.min_val[scale] = val
        self.min_val['current'] = self.min_val[scale]

    def change_scale_log(self, ev):
        """
        Change scale to log. Edit hard minimum of image value
        """
        self.widget.batch_widget.options_widget.scale_log_btn.setChecked(True)
        self.set_hard_minimum(ev, 'log')
        self.scale = np.log10
        self.plot_batch()

    def change_scale_lin(self, ev):
        """
        Change scale to linear. Edit hard minimum of image value
        """
        self.widget.batch_widget.options_widget.scale_lin_btn.setChecked(True)
        self.set_hard_minimum(ev, 'lin')
        self.scale = np.array
        self.plot_batch()

    def change_scale_sqrt(self, ev):
        """
        Change scale to square root. Edit hard minimum of image value
        """
        self.widget.batch_widget.options_widget.scale_sqrt_btn.setChecked(True)
        self.set_hard_minimum(ev, 'sqrt')
        self.scale = np.sqrt
        self.plot_batch()

    def process_step(self):
        """
        Re-draw waterfall plot if step value get changed.
        """
        if self.widget.batch_widget.control_widget.waterfall_btn.isChecked():
            self.plot_waterfall()
        if self.widget.batch_widget.mode_widget.view_3d_btn.isChecked():
            self.plot_batch()

    def waterfall_mode(self):
        """
        Set/unset widget in waterfall mode
        """
        if self.widget.batch_widget.control_widget.waterfall_btn.isChecked():
            self.widget.batch_widget.stack_plot_widget.img_view.vertical_line.setVisible(False)
            self.widget.batch_widget.stack_plot_widget.img_view.horizontal_line.setVisible(False)
        else:
            if self.rect is not None:
                self.widget.batch_widget.stack_plot_widget.img_view.img_view_box.removeItem(self.rect)
            self.widget.batch_widget.stack_plot_widget.img_view.vertical_line.setVisible(True)
            self.widget.batch_widget.stack_plot_widget.img_view.horizontal_line.setVisible(True)

    def set_range_img(self):
        """
        Set start and stop value in the navigation widget
        """
        start = int(str(self.widget.batch_widget.position_widget.step_series_widget.start_txt.text()))
        stop = int(str(self.widget.batch_widget.position_widget.step_series_widget.stop_txt.text()))
        n_img_all = self.model.batch_model.n_img_all
        if n_img_all is None or stop < 0:
            return

        start = min(start, n_img_all, stop)
        stop = min(max(start, stop), n_img_all)

        self.widget.batch_widget.position_widget.step_series_widget.slider.setRange(start, stop)
        self.widget.batch_widget.position_widget.step_series_widget.pos_validator.setRange(start, stop)
        self.plot_batch()

    def switch_frame(self, y):
        x = self.widget.batch_widget.stack_plot_widget.img_view.vertical_line.getXPos()
        self.load_single_image(x, y)
        if self.widget.batch_widget.mode_widget.view_3d_btn.isChecked():
            self.widget.batch_widget.surface_widget.surface_view.g_translate = y
            self.plot_batch()

    def show_img_mouse_position(self, x, y):
        """
        Show position of the mouse with respect of the heatmap

        Show image number, position in diffraction pattern and intensity
        """
        img = self.model.batch_model.data
        binning = self.model.batch_model.binning
        y += int(str(self.widget.batch_widget.position_widget.step_series_widget.start_txt.text()))

        if img is None or x > img.shape[1] or x < 0 or y > img.shape[0] or y < 0:
            return
        scale = (binning[-1] - binning[0]) / binning.shape[0]
        tth = x * scale + binning[0]

        bkg = self.model.batch_model.bkg
        if self.widget.batch_widget.options_widget.background_btn.isChecked() and bkg is not None:
            z = img[int(y), int(x)] - bkg[int(y), int(x)]
        else:
            z = img[int(y), int(x)]

        self.widget.batch_widget.position_widget.mouse_pos_widget.cur_pos_widget.x_pos_lbl.setText(f'Img: {int(y):.0f}')
        self.widget.batch_widget.position_widget.mouse_pos_widget.cur_pos_widget.y_pos_lbl.setText(f'2θ: {tth:.1f}')
        self.widget.batch_widget.position_widget.mouse_pos_widget.cur_pos_widget.int_lbl.setText(f'I: {z:.1f}')

    def change_view(self):
        """
        Change between 2D, 3D and file views
        """
        if self.widget.batch_widget.mode_widget.view_f_btn.isChecked():
            self.widget.batch_widget.activate_files_view()
            n_img_all = self.model.batch_model.n_img_all
            if n_img_all is not None:
                self.set_navigation_raw((0, n_img_all - 1))

        elif self.widget.batch_widget.mode_widget.view_3d_btn.isChecked():
            n_img = self.model.batch_model.n_img
            if n_img is None:
                self.widget.batch_widget.mode_widget.view_f_btn.setChecked(True)
                return
            self.set_navigation_range((0, n_img - 1))
            self.widget.batch_widget.activate_surface_view()
            self.plot_batch()
        else:
            n_img = self.model.batch_model.n_img
            if n_img is None:
                self.widget.batch_widget.mode_widget.view_f_btn.setChecked(True)
                return
            self.set_navigation_range((0, n_img - 1))
            self.widget.batch_widget.activate_stack_plot()

            self.plot_batch()

    def filename_txt_changed(self):
        """
        Set image files of the batch base on filename given in the text box
        """
        current_filenames = self.model.batch_model.files
        if current_filenames is None:
            return
        current_directory = self.model.working_directories['image']

        img_filename_txt = str(self.widget.img_filename_txt.text())
        new_filenames = []
        for t in img_filename_txt.split():
            new_filenames += glob(os.path.join(current_directory, t))

        if len(new_filenames) > 0:
            try:
                self.load_raw_data(new_filenames)
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
        filenames = self.model.batch_model.files
        if filenames is None:
            return
        new_filenames = [os.path.join(new_directory, os.path.basename(f)) for f in filenames]
        self.load_raw_data(new_filenames)

    def load_data(self):
        """
        Set image files of the batch, base on files given in the dialog window
        """
        start_dir = self.model.working_directories.get('batch', os.path.expanduser("~"))
        filenames = open_files_dialog(self.widget, "Load image data file(s)",
                                      start_dir,
                                      ('Raw data (*.nxs *.tif *.tiff *.h5);;'
                                       'Proc data (*.nxs)')
                                      )
        if len(filenames) == 0:
            return
        else:
            self._load_data(filenames)

    def _load_data(self, filenames):
        self.model.working_directories['batch'] = os.path.dirname(filenames[0])
        self.widget.batch_widget.file_control_widget.folder_lbl.setText(os.path.dirname(filenames[0]))
        self.reset_view()
        if self.is_proc(filenames[0]):
            self.model.batch_model.reset_data()
            self.load_proc_data(filenames[0])
            self.load_raw_data(self.model.batch_model.files)
            self.widget.batch_widget.mode_widget.view_2d_btn.setChecked(True)
            self.change_view()
            self.plot_batch()
            self.widget.batch_widget.stack_plot_widget.img_view.auto_range()
        else:
            self.widget.img_directory_txt.setText(os.path.dirname(filenames[0]))
            self.model.batch_model.reset_data()
            self.load_raw_data(filenames)
            self.widget.batch_widget.mode_widget.view_f_btn.setChecked(True)
            self.change_view()

        self.load_single_image(1, 0)
        self.integrate()

    def load_previous_folder(self):
        filenames = self.model.batch_model.get_previous_folder_filenames()
        if len(filenames) > 0:
            self._load_data(filenames)

    def load_next_folder(self):
        filenames = self.model.batch_model.get_next_folder_filenames()
        if len(filenames) > 0:
            self._load_data(filenames)

    def reset_view(self):
        """
        Set few view buttons to un-checked.
        This brings batch-widget to initial state
        """
        self.widget.batch_widget.options_widget.background_btn.setChecked(False)
        self.widget.batch_widget.control_widget.waterfall_btn.setChecked(False)
        self.widget.batch_widget.control_widget.phases_btn.setChecked(False)

        self.waterfall_mode()
        self.toggle_show_phases()

    def is_proc(self, filename):
        """
        Check if file contains processed data
        """
        if os.path.splitext(filename)[1] == '.nxs':
            data_file = h5py.File(filename, "r")
            if 'processed' in data_file:
                return True
            # ToDo Check for old format. To be removed
            if 'data' in data_file:
                return True
        return False

    def load_raw_data(self, filenames):
        """
        Load metadata for raw data

        Following information is loaded:
            filenames, number of images in each file
        """

        self.model.img_model.blockSignals(True)
        try:
            self.model.batch_model.set_image_files(filenames)
        except IOError:
            try:
                dir_name = self.model.working_directories['image']
                filenames = [os.path.join(dir_name, os.path.basename(f)) for f in filenames]
                self.model.batch_model.set_image_files(filenames)
            except IOError:
                print("Raw images are not found")

        self.model.img_model.blockSignals(False)
        files = self.model.batch_model.files
        file_map = self.model.batch_model.file_map

        if files is not None:
            if len(file_map) == len(files):
                file_map = np.hstack((file_map, self.model.batch_model.data.shape[0]))
            images = [(file_map[i + 1] - file_map[i]) for i in range(len(files))]
            self.widget.batch_widget.file_view_widget.set_raw_files(files, images)

        self.show_metadata_info()

        n_img = self.model.batch_model.n_img
        n_img_all = self.model.batch_model.n_img_all
        self.widget.batch_widget.position_widget.step_series_widget.pos_label.setText(f"Frame({n_img}/{n_img_all}):")
        self.widget.batch_widget.position_widget.step_raw_widget.pos_label.setText(f"Frame({n_img}/{n_img_all}):")

    def show_metadata_info(self):
        """
        Show calibration file and mask file in the file view
        """
        self.widget.batch_widget.file_view_widget.set_cal_file(self.model.batch_model.used_calibration)
        self.widget.batch_widget.file_view_widget.set_mask_file(self.model.batch_model.used_mask)

    def load_proc_data(self, filename):
        """
        Load processed data (diffraction patterns and metadata)
        """
        self.model.batch_model.load_proc_data(filename)
        self.widget.calibration_lbl.setText(
            self.model.calibration_model.calibration_name)

    def plot_batch(self, start=None, stop=None):
        """
        Plot batch of diffraction patters taking into account scale abd background subtraction
        """
        data = self.model.batch_model.data
        bkg = self.model.batch_model.bkg
        if data is None:
            return
        if self.widget.batch_widget.options_widget.background_btn.isChecked() and bkg is not None:
            data = data - bkg
        if self.min_val.get('current', None) is not None:
            data[data < self.min_val['current']] = self.min_val['current']
        data = self.scale(data)

        start_x, stop_x = self._get_x_range()
        if stop is None:
            stop = int(str(self.widget.batch_widget.position_widget.step_series_widget.stop_txt.text()))
        if start is None:
            start = int(str(self.widget.batch_widget.position_widget.step_series_widget.start_txt.text()))

        if self.widget.batch_widget.mode_widget.view_2d_btn.isChecked():
            self.widget.batch_widget.stack_plot_widget.img_view.plot_image(data[start:stop + 1, start_x:stop_x], True,
                                                                           [start_x, stop_x])
            self.update_axes_range()
            self.update_linear_region()

        if self.widget.batch_widget.mode_widget.view_3d_btn.isChecked():
            step = int(str(self.widget.batch_widget.position_widget.step_series_widget.step_txt.text()))
            step_min = max(1, int(data[start:stop + 1].size / self.size_threshold))
            if step < step_min:
                step = step_min
                self.widget.batch_widget.position_widget.step_series_widget.step_txt.setValue(step)
            self.widget.batch_widget.surface_widget.surface_view.plot_surface(data[start:stop + 1:step, start_x:stop_x],
                                                                              start, step)
            self.update_3d_axis(data[start:stop + 1:step, start_x:stop_x])

        self.model.enabled_phases_in_cake.emit()

    def _get_x_range(self):
        """
        Return bin-x range of the batch plot
        """
        if self.model.batch_model.data is None:
            return 0, 0
        start_x = 0
        stop_x = self.model.batch_model.data.shape[1]
        if self.widget.batch_widget.options_widget.bkg_cut_btn.isChecked():
            bkg_roi = self.model.pattern_model.pattern.auto_background_subtraction_roi
            if bkg_roi is not None:
                bkg_roi = self.convert_x_value(np.array(bkg_roi), self.model.current_configuration.integration_unit,
                                               '2th_deg')
                binning = self.model.batch_model.binning
                scale = (binning[-1] - binning[0]) / binning.shape[0]
                start_x = (bkg_roi[0] - binning[0]) / scale
                stop_x = (bkg_roi[1] - binning[0]) / scale
        return int(start_x), int(stop_x)

    def update_linear_region(self):
        """
        Update linear region of 2D-view to background roi
        """
        bkg_roi = self.model.pattern_model.pattern.auto_background_subtraction_roi
        if self.model.batch_model.binning is not None and bkg_roi is not None:
            bkg_roi = self.convert_x_value(np.array(bkg_roi), self.model.current_configuration.integration_unit,
                                           '2th_deg')
            start_x, stop_x = self.widget.batch_widget.stack_plot_widget.img_view.x_bin_range
            binning = self.model.batch_model.binning[start_x: stop_x]
            scale = (binning[-1] - binning[0]) / binning.shape[0]
            x_min_bin = (bkg_roi[0] - binning[0]) / scale
            x_max_bin = (bkg_roi[1] - binning[0]) / scale
            self.widget.batch_widget.stack_plot_widget.img_view.set_linear_region(x_min_bin, x_max_bin)

    def save_data(self):
        """
        Save diffraction patterns and metadata
        """
        filename = save_file_dialog(self.widget, "Save Image.",
                                    directory=os.path.join(
                                        self.model.working_directories.get('batch', os.path.expanduser("~"))),
                                    filter=('Image (*.png);;Single file ascii (*.csv);;'
                                            'Multifile Data (*.xy);;'
                                            'Multifile Data (*.chi);;'
                                            'Multifile Data (*.dat);;'
                                            'Multifile GSAS (*.fxye);;'
                                            'Single file Data (*.nxs)')
                                    )

        name, ext = os.path.splitext(filename)
        if filename != '':
            if ext == '.png':
                if self.widget.batch_widget.mode_widget.view_2d_btn.isChecked():
                    self.widget.batch_widget.stack_plot_widget.img_view.save_img(filename)
                if self.widget.batch_widget.mode_widget.view_3d_btn.isChecked():
                    d = self.widget.batch_widget.surface_widget.surface_view.pg_layout.renderToArray((1000, 1000))
                    makeQImage(d).save(filename)
            elif ext == '.nxs':
                self.model.batch_model.save_proc_data(filename)
            elif ext == '.csv':
                self.model.batch_model.save_as_csv(filename)
            else:
                self.model.img_model.blockSignals(True)
                img_data = self.model.batch_model.data
                pattern_x = self.model.batch_model.binning
                for y in range(img_data.shape[0]):
                    pattern_y = img_data[int(y)]
                    self.model.pattern_model.set_pattern(pattern_x, pattern_y)
                    self.model.current_configuration.save_pattern(f"{name}_{y:03d}{ext}")

                    if self.model.pattern_model.pattern.auto_background_subtraction:
                        bkg_directory = os.path.join(os.path.dirname(filename), 'bkg_subtracted')
                        if not os.path.exists(bkg_directory):
                            os.mkdir(bkg_directory)
                        bkg_subtracted_name = os.path.join(bkg_directory, os.path.basename(name))

                        self.model.pattern_model.pattern.recalculate_pattern()
                        self.model.current_configuration.save_pattern(f"{bkg_subtracted_name}_{y:03d}{ext}",
                                                                      subtract_background=True)
                self.model.img_model.blockSignals(False)

    def img_mouse_click(self, x, y):
        """
        Process mouse click
        """
        y += int(str(self.widget.batch_widget.position_widget.step_series_widget.start_txt.text()))
        if self.widget.batch_widget.control_widget.waterfall_btn.isChecked():
            self.process_waterfall(x, y)
        else:

            start_x, stop_x = self.widget.batch_widget.stack_plot_widget.img_view.x_bin_range
            binning = self.model.batch_model.binning[start_x: stop_x]
            tth = get_partial_value(binning, x - 0.5)
            if tth is not None:
                self.model.clicked_tth_changed.emit(tth)
                self.load_single_image(x, y)

    def img_autoscale_btn_clicked(self):
        self.widget.batch_widget.stack_plot_widget.img_view.auto_level()

    def normalize_btn_clicked(self):
        self.model.batch_model.normalize()
        self.plot_batch()

    def process_waterfall(self, x, y):
        """
        Create waterfall plot based on selected rectangle in the heatmap
        """
        # show overlay widget
        self.widget.integration_control_widget.tab_widget_1.setCurrentWidget(
            self.widget.integration_control_widget.overlay_control_widget
        )
        self.widget.integration_control_widget.tab_widget_2.setCurrentWidget(
            self.widget.integration_control_widget.overlay_control_widget
        )

        if self.clicks == 0:
            self.clicks += 1
            if self.rect is not None:
                self.widget.batch_widget.stack_plot_widget.img_view.img_view_box.removeItem(self.rect)
            start = int(str(self.widget.batch_widget.position_widget.step_series_widget.start_txt.text()))
            self.rect = self.widget.batch_widget.stack_plot_widget.img_view.draw_rectangle(x, y - start)
            self.widget.batch_widget.stack_plot_widget.img_view.mouse_moved.connect(self.rect.set_size)
            self.plot_pattern(int(x), int(y))
        elif self.clicks == 1:
            self.clicks = 0
            self.widget.batch_widget.stack_plot_widget.img_view.mouse_moved.disconnect(self.rect.set_size)
            self.plot_waterfall()

    def plot_waterfall(self):
        """
        Create waterfall plot based on position and size of rectangle
        """
        data = self.model.batch_model.data
        start_x, stop_x = self._get_x_range()
        start = int(str(self.widget.batch_widget.position_widget.step_series_widget.start_txt.text()))
        binning = self.model.batch_model.binning
        bkg = self.model.batch_model.bkg
        if data is None:
            return
        if self.widget.batch_widget.options_widget.background_btn.isChecked():
            data = data - bkg

        rect = self.rect.rect()
        y1, y2 = sorted((int(rect.top()), int(rect.bottom())))
        x1, x2 = sorted((int(rect.left()), int(rect.right())))
        y1 += start
        y2 += start
        x1 += start_x
        x2 += start_x

        y1 = max(y1, 0)
        y2 = min(y2, data.shape[0])
        x1 = max(x1, start_x)
        x2 = min(x2, stop_x)

        step = int(str(self.widget.batch_widget.position_widget.step_series_widget.step_txt.text()))
        self.model.overlay_model.reset()
        new_binning = self.convert_x_value(binning[x1:x2], '2th_deg', self.model.current_configuration.integration_unit)
        for i in range(y1, y2, step):
            f_name, pos = self.model.batch_model.get_image_info(i)
            f_name = os.path.basename(f_name)
            self.model.overlay_model.add_overlay(new_binning, data[i, x1:x2], f'{f_name}, {pos}')
        separation = self.widget.integration_control_widget.overlay_control_widget.waterfall_separation_msb.value()
        self.model.overlay_model.overlay_waterfall(separation)

    def load_single_image(self, x, y):
        """
        Plot raw image, diffraction pattern and draw lines on the heatmap plot based on given x and y
        """
        img = self.model.batch_model.data
        if img is None:
            return
        x = min(max(x, 0), img.shape[1])
        y = min(max(y, 0), img.shape[0] - 1)
        self.widget.batch_widget.position_widget.step_series_widget.slider.setValue(int(y))
        self.widget.batch_widget.position_widget.step_series_widget.pos_txt.setText(str(int(y)))
        self.plot_image(int(y))
        self.plot_pattern(int(x), int(y))
        start = int(str(self.widget.batch_widget.position_widget.step_series_widget.start_txt.text()))
        self.widget.batch_widget.stack_plot_widget.img_view.horizontal_line.setValue(y - start)

    def plot_pattern(self, x, y):
        """
        Plot diffraction pattern using proc data
        """
        img = self.model.batch_model.data
        binning = self.model.batch_model.binning
        if img is None or x > img.shape[1] - 1 or x < 0 or y > img.shape[0] - 1 or y < 0:
            return
        scale = (binning[-1] - binning[0]) / binning.shape[0]
        tth = x * scale + binning[0]
        z = img[y, x]

        self.widget.batch_widget.position_widget.mouse_pos_widget.clicked_pos_widget.y_pos_lbl.setText(f'2θ: {tth:.1f}')
        self.widget.batch_widget.position_widget.mouse_pos_widget.clicked_pos_widget.int_lbl.setText(f'I: {z:.1f}')
        new_binning = self.convert_x_value(binning, '2th_deg', self.model.current_configuration.integration_unit)
        self.model.pattern_model.set_pattern(new_binning, img[y])

    def plot_image(self, y):
        """
        Plot single raw image from the batch

        :param y: Number of raw image in the batch
        """
        y = int(y)
        self.model.current_configuration.auto_integrate_pattern = False
        self.model.batch_model.load_image(y, self.widget.batch_widget.mode_widget.view_f_btn.isChecked())
        f_name, pos = self.model.batch_model.get_image_info(y,
                                                            self.widget.batch_widget.mode_widget.view_f_btn.isChecked())
        self.widget.batch_widget.setWindowTitle(f"Batch widget. {f_name} - {pos}")
        self.model.current_configuration.auto_integrate_pattern = True
        self.widget.batch_widget.position_widget.mouse_pos_widget.clicked_pos_widget.x_pos_lbl.setText(f'Img: {y:.0f}')

    def update_axes_range(self):
        """
        Update axis of the 2D image
        """
        self.update_x_axis()
        self.update_y_axis()

    def update_3d_axis(self, data):
        """
        Update axis and grid in 3D view
        """
        if self.model.batch_model.binning is None:
            return

        surf_view = self.widget.batch_widget.surface_widget.surface_view
        start_x, stop_x = self.widget.batch_widget.stack_plot_widget.img_view.x_bin_range
        binning = self.model.batch_model.binning[start_x: stop_x]

        size = surf_view.pg_layout.pixelSize(np.array([0, 0, 0]))
        space = round(size * binning.shape[0] * 0.3, 2)
        ticks = np.round(np.arange(binning[0], binning[-1], space), 2)
        if ticks.shape[0] < 2:
            ticks = np.array([binning[0], binning[-1]])
        # surf_view.axis.set_tick_values(yticks=np.round(np.arange(binning[0], binning[-1], space), 2))
        surf_view.back_grid.setSpacing(np.nanmax(data) / 8., data.shape[1] / (ticks.shape[0] - 1), 1)
        surf_view.base_grid.setSpacing(1, data.shape[1] / (ticks.shape[0] - 1), 1)

    def update_x_axis(self):
        if self.model.batch_model.binning is None:
            return

        img_view_rect = self.widget.batch_widget.stack_plot_widget.img_view.img_view_rect()
        start_x, stop_x = self.widget.batch_widget.stack_plot_widget.img_view.x_bin_range
        binning = self.model.batch_model.binning[start_x: stop_x]

        width = img_view_rect.width()
        left = img_view_rect.left()

        h_scale = (np.max(binning) - np.min(binning)) / binning.shape[0]
        h_shift = binning[0]
        min_tth = h_scale * left + h_shift
        max_tth = h_scale * (left + width) + h_shift

        if self.model.current_configuration.integration_unit == 'q_A^-1':
            ticks = [self.get_ticks(max_tth, min_tth, 'q_A^-1', '2th_deg')]
        elif self.model.current_configuration.integration_unit == 'd_A':
            ticks = [self.get_ticks(min_tth, max_tth, 'd_A', '2th_deg')]
        else:
            ticks = None

        self.widget.batch_widget.stack_plot_widget.img_view.bottom_axis_cake.setRange(min_tth, max_tth)
        self.widget.batch_widget.stack_plot_widget.img_view.bottom_axis_cake.setTicks(ticks)

    def get_ticks(self, min_val, max_val, ticks_unit, base_unit, n_ticks=8):
        """
        Calculate ticks for x axis in case of non-linear scale
        """
        max_d = self.convert_x_value(max_val, base_unit, ticks_unit)
        min_d = self.convert_x_value(min_val, base_unit, ticks_unit)
        step = (max_d - min_d) / n_ticks
        x_d = min_d
        ticks = []
        while x_d > max_d:
            x_d = round(x_d + step, abs(round(np.log10(abs(step)))) + 1)
            x_tth = self.convert_x_value(x_d, ticks_unit, base_unit)
            ticks.append((x_tth, f"{x_d}"))
        return ticks

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

    def update_y_axis(self):
        """
        Update y-axis of the batch plot
        """
        if self.model.batch_model.data is None:
            return

        y = self.widget.batch_widget.position_widget.step_series_widget.slider.value()
        start, stop, step = self.widget.batch_widget.position_widget.step_series_widget.get_image_range()
        self.widget.batch_widget.stack_plot_widget.img_view.horizontal_line.setValue(y - start)

        img_view_box = self.widget.batch_widget.stack_plot_widget.img_view.img_view_box
        data_img_item = self.widget.batch_widget.stack_plot_widget.img_view.data_img_item
        img_data = self.model.batch_model.data[start:stop + 1]

        height = img_view_box.viewRect().height()
        bottom = img_view_box.viewRect().top()
        bound = data_img_item.boundingRect().height()

        if bound == 0:
            return
        v_scale = img_data.shape[0] / bound
        min_y = v_scale * bottom + start
        max_y = v_scale * (bottom + height) + start

        self.widget.batch_widget.stack_plot_widget.img_view.left_axis_cake.setRange(min_y, max_y)

    def integrate(self):
        """
        Integrate images in the batch
        """
        if not self.model.calibration_model.is_calibrated:
            self.widget.show_error_msg("Can not integrate multiple images without calibration.")
            return
        if not self.model.batch_model.raw_available or self.model.batch_model.n_img_all < 1:
            self.widget.show_error_msg("No images loaded for integration")
            return

        if not self.widget.automatic_binning_cb.isChecked():
            num_points = int(str(self.widget.bin_count_txt.text()))
        else:
            num_points = None

        if self.widget.batch_widget.mode_widget.view_f_btn.isChecked():
            start, stop, step = self.widget.batch_widget.position_widget.step_raw_widget.get_image_range()
        else:
            start, stop, step = self.widget.batch_widget.position_widget.step_series_widget.get_image_range()

        self.model.img_model.blockSignals(True)
        n_int = (stop - start) / step
        progress_dialog = self.create_progress_dialog("Integrating multiple images.", "Abort Integration", n_int)

        def callback_fn(current_index):
            if progress_dialog.wasCanceled():
                return False
            progress_dialog.setValue(current_index)
            QtWidgets.QApplication.processEvents()
            return ~progress_dialog.wasCanceled()

        self.model.batch_model.integrate_raw_data(num_points, start, stop + 1, step,
                                                  self.widget.batch_widget.mode_widget.view_f_btn.isChecked(),
                                                  callback_fn=callback_fn,
                                                  use_mask=self.model.use_mask)

        progress_dialog.close()
        self.show_metadata_info()

        self.model.img_model.blockSignals(False)
        n_img = self.model.batch_model.n_img
        n_img_all = self.model.batch_model.n_img_all
        self.widget.batch_widget.position_widget.step_series_widget.pos_label.setText(f"Frame({n_img}/{n_img_all}):")
        self.widget.batch_widget.position_widget.step_raw_widget.pos_label.setText(f"Frame({n_img}/{n_img_all}):")
        self.widget.batch_widget.position_widget.step_series_widget.stop_txt.setValue(n_img - 1)
        self.widget.batch_widget.position_widget.step_series_widget.start_txt.setValue(0)
        self.widget.batch_widget.mode_widget.view_2d_btn.setChecked(True)
        self.reset_view()
        self.change_view()
        self.widget.batch_widget.stack_plot_widget.img_view.auto_range()

    def create_progress_dialog(self, text_str, abort_str, end_value):
        progress_dialog = QtWidgets.QProgressDialog(text_str, abort_str, 0, int(end_value),
                                                    self.widget.batch_widget)
        # progress_dialog.setParent(self.widget.batch_widget)

        progress_dialog.move(int(self.widget.batch_widget.x() + self.widget.batch_widget.size().width() / 2.0 -
                                 progress_dialog.size().width() / 2.0),
                             int(self.widget.batch_widget.y() + self.widget.batch_widget.size().height() / 2.0 -
                                 progress_dialog.size().height() / 2.0))

        progress_dialog.setWindowTitle('   ')
        progress_dialog.setWindowModality(QtCore.Qt.WindowModal)
        progress_dialog.setWindowFlags(
            QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.Window | QtCore.Qt.FramelessWindowHint)
        progress_dialog.show()
        QtWidgets.QApplication.processEvents()
        return progress_dialog

    def set_navigation_raw(self, raw_range=(0, 0)):
        self.widget.batch_widget.position_widget.step_raw_widget.start_txt.setRange(*raw_range)
        self.widget.batch_widget.position_widget.step_raw_widget.stop_txt.setRange(*raw_range)
        self.widget.batch_widget.position_widget.step_raw_widget.stop_txt.setValue(raw_range[1])
        self.widget.batch_widget.position_widget.step_raw_widget.slider.setRange(*raw_range)
        self.widget.batch_widget.position_widget.step_raw_widget.pos_validator.setRange(*raw_range)

    def set_navigation_range(self, all_range):
        """
        Set start and stop positions as well as range of navigation widget
        """
        self.widget.batch_widget.position_widget.step_series_widget.start_txt.setRange(*all_range)
        self.widget.batch_widget.position_widget.step_series_widget.stop_txt.setRange(*all_range)

        self.widget.batch_widget.position_widget.step_series_widget.slider.setRange(*all_range)
        self.widget.batch_widget.position_widget.step_series_widget.pos_validator.setRange(*all_range)

        self.widget.batch_widget.position_widget.step_series_widget.start_txt.setValue(all_range[0])
        self.widget.batch_widget.position_widget.step_series_widget.stop_txt.setValue(all_range[1])

    def update_gui(self):
        """
        Apply integration unit from current_configuration
        """
        if self.model.current_configuration.integration_unit == '2th_deg':
            self.widget.batch_widget.options_widget.tth_btn.setChecked(True)
            self.set_unit_tth()
        elif self.model.current_configuration.integration_unit == 'd_A':
            self.widget.batch_widget.options_widget.d_btn.setChecked(True)
            self.set_unit_d()
        elif self.model.current_configuration.integration_unit == 'q_A^-1':
            self.widget.batch_widget.options_widget.q_btn.setChecked(True)
            self.set_unit_q()
