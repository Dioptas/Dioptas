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

CLICKED_COLOR = '#00DD00'

from functools import partial

from qtpy import QtWidgets, QtCore

from ..UtilityWidgets import FileInfoWidget
from ..EpicsWidgets import MoveStageWidget
from ..CustomWidgets import NoRectDelegate, FlatButton

from .CustomWidgets import MouseCurrentAndClickedWidget, MouseUnitCurrentAndClickedWidget
from .ControlWidgets import IntegrationControlWidget
from .IntegrationWidgets import IntegrationImgDisplayWidget, IntegrationPatternWidget, IntegrationStatusWidget


class IntegrationWidget(QtWidgets.QWidget):
    """
    Defines the main structure of the integration widget, which is separated into four parts.
    Integration Image Widget - displaying the image, mask and/or cake
    Integration Control Widget - Handling all the interaction with overlays, phases etc.
    Integration Patter Widget - showing the integrated pattern
    Integration Status Widget - showing the current mouse position and current background filename
    """

    overlay_color_btn_clicked = QtCore.Signal(int, QtWidgets.QWidget)
    overlay_show_cb_state_changed = QtCore.Signal(int, bool)
    overlay_name_changed = QtCore.Signal(int, str)
    phase_color_btn_clicked = QtCore.Signal(int, QtWidgets.QWidget)
    phase_show_cb_state_changed = QtCore.Signal(int, bool)

    def __init__(self, *args, **kwargs):
        super(IntegrationWidget, self).__init__(*args, **kwargs)

        self.integration_image_widget = IntegrationImgDisplayWidget()
        self.integration_control_widget = IntegrationControlWidget()
        self.integration_pattern_widget = IntegrationPatternWidget()
        self.integration_status_widget = IntegrationStatusWidget()

        self._layout = QtWidgets.QVBoxLayout()
        self._layout.setSpacing(6)
        self._layout.setContentsMargins(0, 0, 0, 0)

        self.vertical_splitter = QtWidgets.QSplitter(self)
        self.vertical_splitter.setOrientation(QtCore.Qt.Vertical)
        self.vertical_splitter.addWidget(self.integration_control_widget)
        self.vertical_splitter.addWidget(self.integration_pattern_widget)
        self.vertical_splitter.setStretchFactor(1, 99999)

        self.vertical_splitter_left = QtWidgets.QSplitter(self)
        self.vertical_splitter_left.setOrientation(QtCore.Qt.Vertical)
        self.vertical_splitter_left.addWidget(self.integration_image_widget)

        self.horizontal_splitter = QtWidgets.QSplitter()
        self.horizontal_splitter.setOrientation(QtCore.Qt.Horizontal)
        self.horizontal_splitter.addWidget(self.vertical_splitter_left)
        self.horizontal_splitter.addWidget(self.vertical_splitter)
        self._layout.addWidget(self.horizontal_splitter, 10)
        self._layout.addWidget(self.integration_status_widget, 0)
        self.setLayout(self._layout)

        self.create_shortcuts()

        self.overlay_tw.cellChanged.connect(self.overlay_label_editingFinished)
        self.overlay_show_cbs = []
        self.overlay_color_btns = []
        self.overlay_tw.setItemDelegate(NoRectDelegate())

        self.phase_show_cbs = []
        self.phase_color_btns = []
        self.show_parameter_in_pattern = True
        header_view = QtWidgets.QHeaderView(QtCore.Qt.Horizontal, self.phase_tw)
        self.phase_tw.setHorizontalHeader(header_view)
        header_view.setResizeMode(2, QtWidgets.QHeaderView.Stretch)
        header_view.setResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        header_view.setResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)
        header_view.hide()
        self.phase_tw.setItemDelegate(NoRectDelegate())

        self.bkg_image_scale_sb.setKeyboardTracking(False)
        self.bkg_image_offset_sb.setKeyboardTracking(False)

        self.qa_bkg_pattern_inspect_btn.setVisible(False)

        self.mask_transparent_cb.setVisible(False)

        self.file_info_widget = FileInfoWidget(self)
        self.move_widget = MoveStageWidget(self)

        self.img_frame_size = QtCore.QSize(400, 500)
        self.img_frame_position = QtCore.QPoint(0, 0)

        self.alternative_gui_view = False

    def create_shortcuts(self):
        img_file_widget = self.integration_control_widget.img_control_widget.file_widget
        self.load_img_btn = img_file_widget.load_btn
        self.autoprocess_cb = img_file_widget.file_cb
        self.prev_img_btn = img_file_widget.previous_btn
        self.next_img_btn = img_file_widget.next_btn
        self.image_browse_step_txt = img_file_widget.step_txt
        self.img_browse_by_name_rb = img_file_widget.browse_by_name_rb
        self.img_browse_by_time_rb = img_file_widget.browse_by_time_rb
        self.img_filename_txt = img_file_widget.file_txt
        self.img_directory_txt = img_file_widget.directory_txt
        self.img_directory_btn = img_file_widget.directory_btn
        self.file_info_btn = self.integration_control_widget.img_control_widget.file_info_btn
        self.move_widget_btn = self.integration_control_widget.img_control_widget.move_btn
        self.img_batch_mode_integrate_rb = self.integration_control_widget.img_control_widget.batch_mode_integrate_rb
        self.img_batch_mode_add_rb = self.integration_control_widget.img_control_widget.batch_mode_add_rb
        self.img_batch_mode_image_save_rb = self.integration_control_widget.img_control_widget.batch_mode_image_save_rb

        pattern_file_widget = self.integration_control_widget.pattern_control_widget.file_widget
        self.pattern_load_btn = pattern_file_widget.load_btn
        self.pattern_autocreate_cb = pattern_file_widget.file_cb
        self.pattern_previous_btn = pattern_file_widget.previous_btn
        self.pattern_next_btn = pattern_file_widget.next_btn
        self.pattern_browse_step_txt = pattern_file_widget.step_txt
        self.pattern_browse_by_name_rb = pattern_file_widget.browse_by_name_rb
        self.pattern_browse_by_time_rb = pattern_file_widget.browse_by_time_rb
        self.pattern_filename_txt = pattern_file_widget.file_txt
        self.pattern_directory_txt = pattern_file_widget.directory_txt
        self.pattern_directory_btn = pattern_file_widget.directory_btn
        self.pattern_header_xy_cb = self.integration_control_widget.pattern_control_widget.xy_cb
        self.pattern_header_chi_cb = self.integration_control_widget.pattern_control_widget.chi_cb
        self.pattern_header_dat_cb = self.integration_control_widget.pattern_control_widget.dat_cb
        self.pattern_header_fxye_cb = self.integration_control_widget.pattern_control_widget.fxye_cb

        phase_control_widget = self.integration_control_widget.phase_control_widget
        self.phase_add_btn = phase_control_widget.add_btn
        self.phase_edit_btn = phase_control_widget.edit_btn
        self.phase_del_btn = phase_control_widget.delete_btn
        self.phase_clear_btn = phase_control_widget.clear_btn
        self.phase_save_list_btn = phase_control_widget.save_list_btn
        self.phase_load_list_btn = phase_control_widget.load_list_btn
        self.phase_tw = phase_control_widget.phase_tw
        self.phase_pressure_sb = phase_control_widget.pressure_sb
        self.phase_pressure_step_txt = phase_control_widget.pressure_step_txt
        self.phase_temperature_sb = phase_control_widget.temperature_sb
        self.phase_temperature_step_txt = phase_control_widget.temperature_step_txt
        self.phase_apply_to_all_cb = phase_control_widget.apply_to_all_cb
        self.phase_show_parameter_in_pattern_cb = phase_control_widget.show_in_pattern_cb

        overlay_control_widget = self.integration_control_widget.overlay_control_widget
        self.overlay_add_btn = overlay_control_widget.add_btn
        self.overlay_del_btn = overlay_control_widget.delete_btn
        self.overlay_clear_btn = overlay_control_widget.clear_btn
        self.overlay_tw = overlay_control_widget.overlay_tw
        self.overlay_scale_sb = overlay_control_widget.scale_sb
        self.overlay_scale_step_txt = overlay_control_widget.scale_step_txt
        self.overlay_offset_sb = overlay_control_widget.offset_sb
        self.overlay_offset_step_txt = overlay_control_widget.offset_step_txt
        self.waterfall_separation_txt = overlay_control_widget.waterfall_separation_txt
        self.waterfall_btn = overlay_control_widget.waterfall_btn
        self.reset_waterfall_btn = overlay_control_widget.waterfall_reset_btn
        self.overlay_set_as_bkg_btn = overlay_control_widget.set_as_background_btn

        corrections_control_widget = self.integration_control_widget.corrections_control_widget
        self.cbn_groupbox = corrections_control_widget.cbn_seat_gb
        self.cbn_diamond_thickness_txt = corrections_control_widget.anvil_thickness_txt
        self.cbn_seat_thickness_txt = corrections_control_widget.seat_thickness_txt
        self.cbn_inner_seat_radius_txt = corrections_control_widget.seat_inner_radius_txt
        self.cbn_outer_seat_radius_txt = corrections_control_widget.seat_outer_radius_txt
        self.cbn_cell_tilt_txt = corrections_control_widget.cell_tilt_txt
        self.cbn_tilt_rotation_txt = corrections_control_widget.cell_tilt_rotation_txt
        self.cbn_center_offset_txt = corrections_control_widget.center_offset_txt
        self.cbn_center_offset_angle_txt = corrections_control_widget.center_offset_angle_txt
        self.cbn_anvil_al_txt = corrections_control_widget.anvil_absorption_length_txt
        self.cbn_seat_al_txt = corrections_control_widget.seat_absorption_length_txt
        self.cbn_plot_correction_btn = corrections_control_widget.cbn_seat_plot_btn
        self.oiadac_groupbox = corrections_control_widget.oiadac_gb
        self.oiadac_thickness_txt = corrections_control_widget.detector_thickness_txt
        self.oiadac_abs_length_txt = corrections_control_widget.detector_absorption_length_txt
        self.oiadac_plot_btn = corrections_control_widget.oiadac_plot_btn

        background_control_widget = self.integration_control_widget.background_control_widget
        self.bkg_image_load_btn = background_control_widget.load_image_btn
        self.bkg_image_filename_lbl = background_control_widget.filename_lbl
        self.bkg_image_delete_btn = background_control_widget.remove_image_btn
        self.bkg_image_scale_sb = background_control_widget.scale_sb
        self.bkg_image_scale_step_txt = background_control_widget.scale_step_txt
        self.bkg_image_offset_sb = background_control_widget.offset_sb
        self.bkg_image_offset_step_txt = background_control_widget.offset_step_txt
        self.bkg_pattern_gb = background_control_widget.pattern_background_gb
        self.bkg_pattern_smooth_width_sb = background_control_widget.smooth_with_sb
        self.bkg_pattern_iterations_sb = background_control_widget.iterations_sb
        self.bkg_pattern_poly_order_sb = background_control_widget.poly_order_sb
        self.bkg_pattern_x_min_txt = background_control_widget.x_range_min_txt
        self.bkg_pattern_x_max_txt = background_control_widget.x_range_max_txt
        self.bkg_pattern_inspect_btn = background_control_widget.inspect_btn

        options_control_widget = self.integration_control_widget.integration_options_widget
        self.bin_count_txt = options_control_widget.bin_count_txt
        self.automatic_binning_cb = options_control_widget.bin_count_cb
        self.supersampling_sb = options_control_widget.supersampling_sb

        self.mouse_x_lbl = self.integration_status_widget.mouse_pos_widget.cur_pos_widget.x_pos_lbl
        self.mouse_y_lbl = self.integration_status_widget.mouse_pos_widget.cur_pos_widget.y_pos_lbl
        self.mouse_int_lbl = self.integration_status_widget.mouse_pos_widget.cur_pos_widget.int_lbl
        self.click_x_lbl = self.integration_status_widget.mouse_pos_widget.clicked_pos_widget.x_pos_lbl
        self.click_y_lbl = self.integration_status_widget.mouse_pos_widget.clicked_pos_widget.y_pos_lbl
        self.click_int_lbl = self.integration_status_widget.mouse_pos_widget.clicked_pos_widget.int_lbl
        self.mouse_tth_lbl = self.integration_status_widget.mouse_unit_widget.cur_unit_widget.tth_lbl
        self.mouse_q_lbl = self.integration_status_widget.mouse_unit_widget.cur_unit_widget.q_lbl
        self.mouse_d_lbl = self.integration_status_widget.mouse_unit_widget.cur_unit_widget.d_lbl
        self.mouse_azi_lbl = self.integration_status_widget.mouse_unit_widget.cur_unit_widget.azi_lbl
        self.click_tth_lbl = self.integration_status_widget.mouse_unit_widget.clicked_unit_widget.tth_lbl
        self.click_q_lbl = self.integration_status_widget.mouse_unit_widget.clicked_unit_widget.q_lbl
        self.click_d_lbl = self.integration_status_widget.mouse_unit_widget.clicked_unit_widget.d_lbl
        self.click_azi_lbl = self.integration_status_widget.mouse_unit_widget.clicked_unit_widget.azi_lbl
        self.bkg_name_lbl = self.integration_status_widget.bkg_name_lbl

        pattern_widget = self.integration_pattern_widget
        self.qa_save_img_btn = pattern_widget.save_image_btn
        self.qa_save_pattern_btn = pattern_widget.save_pattern_btn
        self.qa_set_as_overlay_btn = pattern_widget.as_overlay_btn
        self.qa_set_as_background_btn = pattern_widget.as_bkg_btn
        self.load_calibration_btn = pattern_widget.load_calibration_btn
        self.calibration_lbl = pattern_widget.calibration_lbl
        self.pattern_tth_btn = pattern_widget.tth_btn
        self.pattern_q_btn = pattern_widget.q_btn
        self.pattern_d_btn = pattern_widget.d_btn
        self.qa_bkg_pattern_btn = pattern_widget.background_btn
        self.qa_bkg_pattern_inspect_btn = pattern_widget.background_inspect_btn
        self.antialias_btn = pattern_widget.antialias_btn
        self.pattern_auto_range_btn = pattern_widget.auto_range_btn
        self.pattern_widget = pattern_widget.pattern_view

        image_widget = self.integration_image_widget
        self.img_frame = image_widget
        self.img_roi_btn = image_widget.roi_btn
        self.img_mode_btn = image_widget.mode_btn
        self.img_mask_btn = image_widget.mask_btn
        self.cake_shift_azimuth_sl = image_widget.cake_shift_azimuth_sl
        self.mask_transparent_cb = image_widget.transparent_cb
        self.img_autoscale_btn = image_widget.autoscale_btn
        self.img_dock_btn = image_widget.undock_btn
        self.img_widget = image_widget.img_view
        self.img_show_background_subtracted_btn = image_widget.show_background_subtracted_img_btn

        self.frame_img_positions_widget = self.integration_image_widget.position_and_unit_widget
        self.tabWidget = self.integration_control_widget
        self.img_widget_mouse_x_lbl = self.integration_image_widget.mouse_pos_widget.cur_pos_widget.x_pos_lbl
        self.img_widget_mouse_y_lbl = self.integration_image_widget.mouse_pos_widget.cur_pos_widget.y_pos_lbl
        self.img_widget_mouse_int_lbl = self.integration_image_widget.mouse_pos_widget.cur_pos_widget.int_lbl
        self.img_widget_click_x_lbl = self.integration_image_widget.mouse_pos_widget.clicked_pos_widget.x_pos_lbl
        self.img_widget_click_y_lbl = self.integration_image_widget.mouse_pos_widget.clicked_pos_widget.y_pos_lbl
        self.img_widget_click_int_lbl = self.integration_image_widget.mouse_pos_widget.clicked_pos_widget.int_lbl
        self.img_widget_mouse_tth_lbl = self.integration_image_widget.mouse_unit_widget.cur_unit_widget.tth_lbl
        self.img_widget_mouse_q_lbl = self.integration_image_widget.mouse_unit_widget.cur_unit_widget.q_lbl
        self.img_widget_mouse_d_lbl = self.integration_image_widget.mouse_unit_widget.cur_unit_widget.d_lbl
        self.img_widget_mouse_azi_lbl = self.integration_image_widget.mouse_unit_widget.cur_unit_widget.azi_lbl
        self.img_widget_click_tth_lbl = self.integration_image_widget.mouse_unit_widget.clicked_unit_widget.tth_lbl
        self.img_widget_click_q_lbl = self.integration_image_widget.mouse_unit_widget.clicked_unit_widget.q_lbl
        self.img_widget_click_d_lbl = self.integration_image_widget.mouse_unit_widget.clicked_unit_widget.d_lbl
        self.img_widget_click_azi_lbl = self.integration_image_widget.mouse_unit_widget.clicked_unit_widget.azi_lbl

        self.footer_img_mouse_position_widget = self.integration_status_widget.mouse_pos_widget
        self.change_gui_view_btn = self.integration_status_widget.change_gui_view_btn

    def switch_to_cake(self):
        self.img_widget.img_view_box.setAspectLocked(False)
        self.img_widget.activate_vertical_line()

    def switch_to_img(self):
        self.img_widget.img_view_box.setAspectLocked(True)
        self.img_widget.deactivate_vertical_line()

    def dock_img(self, bool_value):
        if not bool_value:
            self.img_dock_btn.setText('Dock')

            # save current splitter state
            self.horizontal_splitter_state = self.horizontal_splitter.saveState()

            # splitter_handle = self.horizontal_splitter.handle(1)
            # splitter_handle.setEnabled(False)

            self.img_frame.setParent(self)
            self.img_frame.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.CustomizeWindowHint | \
                                          QtCore.Qt.WindowMinimizeButtonHint | QtCore.Qt.WindowMaximizeButtonHint)
            self.frame_img_positions_widget.show()
            self.img_frame.resize(self.img_frame_size)
            self.img_frame.move(self.img_frame_position)
            self.footer_img_mouse_position_widget.hide()
            self.img_frame.show()
        elif bool_value:
            self.img_dock_btn.setText('Undock')

            # save the current position and size of the img_frame to be able to restore it later
            self.img_frame_size = self.img_frame.size()
            self.img_frame_position = self.img_frame.pos()

            # reassign visibilities of mouse position and click labels
            self.footer_img_mouse_position_widget.show()
            self.frame_img_positions_widget.hide()

            # remove all widgets/frames from horizontal splitter to be able to arrange them in the correct order
            self.img_frame.setParent(self.horizontal_splitter)

            self.horizontal_splitter.addWidget(self.img_frame)
            self.horizontal_splitter.addWidget(self.vertical_splitter)

            # restore the previously used size when image was undocked
            self.horizontal_splitter.restoreState(self.horizontal_splitter_state)

    def get_progress_dialog(self, message, abort_text, num_points):
        progress_dialog = QtWidgets.QProgressDialog(message, abort_text, 0,
                                                    num_points, self)
        progress_dialog.setWindowModality(QtCore.Qt.WindowModal)
        progress_dialog.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        progress_dialog.move(
            self.pattern_widget.pg_layout.x() + self.pattern_widget.pg_layout.size().width() / 2.0 - \
            progress_dialog.size().width() / 2.0,
            self.pattern_widget.pg_layout.y() + self.pattern_widget.pg_layout.size().height() / 2.0 -
            progress_dialog.size().height() / 2.0)
        progress_dialog.show()
        return progress_dialog

    def show_error_msg(self, msg):
        msg_box = QtWidgets.QMessageBox(self)
        msg_box.setWindowFlags(QtCore.Qt.Tool)
        msg_box.setText(msg)
        msg_box.setIcon(QtWidgets.QMessageBox.Critical)
        msg_box.setWindowTitle('Error')
        msg_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
        msg_box.setDefaultButton(QtWidgets.QMessageBox.Ok)
        msg_box.exec_()

    # ###############################################################################################
    # Now comes all the overlay tw stuff
    ################################################################################################

    def add_overlay(self, name, color):
        current_rows = self.overlay_tw.rowCount()
        self.overlay_tw.setRowCount(current_rows + 1)
        self.overlay_tw.blockSignals(True)

        show_cb = QtWidgets.QCheckBox()
        show_cb.setChecked(True)
        show_cb.stateChanged.connect(partial(self.overlay_show_cb_changed, show_cb))
        show_cb.setStyleSheet("background-color: transparent")
        self.overlay_tw.setCellWidget(current_rows, 0, show_cb)
        self.overlay_show_cbs.append(show_cb)

        color_button = FlatButton()
        color_button.setStyleSheet("background-color: " + color)
        color_button.clicked.connect(partial(self.overlay_color_btn_click, color_button))
        self.overlay_tw.setCellWidget(current_rows, 1, color_button)
        self.overlay_color_btns.append(color_button)

        name_item = QtWidgets.QTableWidgetItem(name)
        name_item.setFlags(name_item.flags() & ~QtCore.Qt.ItemIsEditable)
        self.overlay_tw.setItem(current_rows, 2, QtWidgets.QTableWidgetItem(name))

        self.overlay_tw.setColumnWidth(0, 20)
        self.overlay_tw.setColumnWidth(1, 25)
        self.overlay_tw.setRowHeight(current_rows, 25)
        self.select_overlay(current_rows)
        self.overlay_tw.blockSignals(False)

    def select_overlay(self, ind):
        if self.overlay_tw.rowCount() > 0:
            self.overlay_tw.selectRow(ind)

    def get_selected_overlay_row(self):
        selected = self.overlay_tw.selectionModel().selectedRows()
        try:
            row = selected[0].row()
        except IndexError:
            row = -1
        return row

    def remove_overlay(self, ind):
        self.overlay_tw.blockSignals(True)
        self.overlay_tw.removeRow(ind)
        self.overlay_tw.blockSignals(False)
        del self.overlay_show_cbs[ind]
        del self.overlay_color_btns[ind]

        if self.overlay_tw.rowCount() > ind:
            self.select_overlay(ind)
        else:
            self.select_overlay(self.overlay_tw.rowCount() - 1)

    def overlay_color_btn_click(self, button):
        self.overlay_color_btn_clicked.emit(self.overlay_color_btns.index(button), button)

    def overlay_show_cb_changed(self, checkbox):
        self.overlay_show_cb_state_changed.emit(self.overlay_show_cbs.index(checkbox), checkbox.isChecked())

    def overlay_show_cb_set_checked(self, ind, state):
        checkbox = self.overlay_show_cbs[ind]
        checkbox.setChecked(state)

    def overlay_show_cb_is_checked(self, ind):
        checkbox = self.overlay_show_cbs[ind]
        return checkbox.isChecked()

    def overlay_label_editingFinished(self, row, col):
        label_item = self.overlay_tw.item(row, col)
        self.overlay_name_changed.emit(row, str(label_item.text()))

    # ###############################################################################################
    # Now comes all the phase tw stuff
    ################################################################################################

    def add_phase(self, name, color):
        current_rows = self.phase_tw.rowCount()
        self.phase_tw.setRowCount(current_rows + 1)
        self.phase_tw.blockSignals(True)

        show_cb = QtWidgets.QCheckBox()
        show_cb.setChecked(True)
        show_cb.stateChanged.connect(partial(self.phase_show_cb_changed, show_cb))
        show_cb.setStyleSheet("background-color: transparent")
        self.phase_tw.setCellWidget(current_rows, 0, show_cb)
        self.phase_show_cbs.append(show_cb)

        color_button = FlatButton()
        color_button.setStyleSheet("background-color: " + color)
        color_button.clicked.connect(partial(self.phase_color_btn_click, color_button))
        self.phase_tw.setCellWidget(current_rows, 1, color_button)
        self.phase_color_btns.append(color_button)

        name_item = QtWidgets.QTableWidgetItem(name)
        name_item.setFlags(name_item.flags() & ~QtCore.Qt.ItemIsEditable)
        name_item.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.phase_tw.setItem(current_rows, 2, name_item)

        pressure_item = QtWidgets.QTableWidgetItem('0 GPa')
        pressure_item.setFlags(pressure_item.flags() & ~QtCore.Qt.ItemIsEditable)
        pressure_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.phase_tw.setItem(current_rows, 3, pressure_item)

        temperature_item = QtWidgets.QTableWidgetItem('298 K')
        temperature_item.setFlags(temperature_item.flags() & ~QtCore.Qt.ItemIsEditable)
        temperature_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.phase_tw.setItem(current_rows, 4, temperature_item)

        self.phase_tw.setColumnWidth(0, 20)
        self.phase_tw.setColumnWidth(1, 25)
        self.phase_tw.setRowHeight(current_rows, 25)
        self.select_phase(current_rows)
        self.phase_tw.blockSignals(False)

    def select_phase(self, ind):
        self.phase_tw.selectRow(ind)

    def get_selected_phase_row(self):
        selected = self.phase_tw.selectionModel().selectedRows()
        try:
            row = selected[0].row()
        except IndexError:
            row = -1
        return row

    def get_phase(self):
        pass

    def del_phase(self, ind):
        self.phase_tw.blockSignals(True)
        self.phase_tw.removeRow(ind)
        self.phase_tw.blockSignals(False)
        del self.phase_show_cbs[ind]
        del self.phase_color_btns[ind]

        if self.phase_tw.rowCount() > ind:
            self.select_phase(ind)
        else:
            self.select_phase(self.phase_tw.rowCount() - 1)

    def rename_phase(self, ind, name):
        self.pattern_widget.rename_phase(ind, name)
        name_item = self.phase_tw.item(ind, 2)
        name_item.setText(name)

    def set_phase_temperature(self, ind, T):
        temperature_item = self.phase_tw.item(ind, 4)
        try:
            temperature_item.setText("{0:.2f} K".format(T))
        except ValueError:
            temperature_item.setText("{0} K".format(T))
        self.update_phase_parameters_in_legend(ind)

    def get_phase_temperature(self, ind):
        temperature_item = self.phase_tw.item(ind, 4)
        try:
            temperature = float(str(temperature_item.text()).split()[0])
        except:
            temperature = None
        return temperature

    def set_phase_pressure(self, ind, P):
        pressure_item = self.phase_tw.item(ind, 3)
        try:
            pressure_item.setText("{0:.2f} GPa".format(P))
        except ValueError:
            pressure_item.setText("{0} GPa".format(P))
        self.update_phase_parameters_in_legend(ind)

    def get_phase_pressure(self, ind):
        pressure_item = self.phase_tw.item(ind, 3)
        pressure = float(str(pressure_item.text()).split()[0])
        return pressure

    def update_phase_parameters_in_legend(self, ind):
        pressure = self.get_phase_pressure(ind)
        temperature = self.get_phase_temperature(ind)

        name_str = str(self.phase_tw.item(ind, 2).text())
        parameter_str = ''

        if self.show_parameter_in_pattern:
            if pressure != 0:
                parameter_str += '{:0.2f} GPa '.format(pressure)
            if temperature != 0 and temperature != 298 and temperature is not None:
                parameter_str += '{:0.2f} K '.format(temperature)

        self.pattern_widget.rename_phase(ind, parameter_str + name_str)

    def phase_color_btn_click(self, button):
        self.phase_color_btn_clicked.emit(self.phase_color_btns.index(button), button)

    def phase_show_cb_changed(self, checkbox):
        self.phase_show_cb_state_changed.emit(self.phase_show_cbs.index(checkbox), checkbox.isChecked())

    def phase_show_cb_set_checked(self, ind, state):
        checkbox = self.phase_show_cbs[ind]
        checkbox.setChecked(state)

    def phase_show_cb_is_checked(self, ind):
        checkbox = self.phase_show_cbs[ind]
        return checkbox.isChecked()

    def get_bkg_pattern_parameters(self):
        smooth_width = float(self.bkg_pattern_smooth_width_sb.value())
        iterations = int(self.bkg_pattern_iterations_sb.value())
        polynomial_order = int(self.bkg_pattern_poly_order_sb.value())
        return smooth_width, iterations, polynomial_order

    def set_bkg_pattern_parameters(self, bkg_pattern_parameters):
        self.bkg_pattern_smooth_width_sb.blockSignals(True)
        self.bkg_pattern_iterations_sb.blockSignals(True)
        self.bkg_pattern_poly_order_sb.blockSignals(True)

        self.bkg_pattern_smooth_width_sb.setValue(bkg_pattern_parameters[0])
        self.bkg_pattern_iterations_sb.setValue(bkg_pattern_parameters[1])
        self.bkg_pattern_poly_order_sb.setValue(bkg_pattern_parameters[2])

        self.bkg_pattern_smooth_width_sb.blockSignals(False)
        self.bkg_pattern_iterations_sb.blockSignals(False)
        self.bkg_pattern_poly_order_sb.blockSignals(False)

    def get_bkg_pattern_roi(self):
        x_min = float(str(self.bkg_pattern_x_min_txt.text()))
        x_max = float(str(self.bkg_pattern_x_max_txt.text()))
        return x_min, x_max

    def set_bkg_pattern_roi(self, roi):
        self.bkg_pattern_x_max_txt.blockSignals(True)
        self.bkg_pattern_x_min_txt.blockSignals(True)

        self.bkg_pattern_x_min_txt.setText('{:.3f}'.format(roi[0]))
        self.bkg_pattern_x_max_txt.setText('{:.3f}'.format(roi[1]))

        self.bkg_pattern_x_max_txt.blockSignals(False)
        self.bkg_pattern_x_min_txt.blockSignals(False)
