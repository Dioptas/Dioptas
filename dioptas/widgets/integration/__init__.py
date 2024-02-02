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

CLICKED_COLOR = '#00DD00'

from qtpy import QtWidgets, QtCore

from ..UtilityWidgets import FileInfoWidget
from ..EpicsWidgets import MoveStageWidget
from .BatchWidget import BatchWidget

from .CustomWidgets import MouseCurrentAndClickedWidget, MouseUnitCurrentAndClickedWidget
from .control import IntegrationControlWidget
from .display.ImgWidget import IntegrationImgDisplayWidget
from .display.PatternWidget import IntegrationPatternWidget
from .display.StatusWidget import IntegrationStatusWidget


class IntegrationWidget(QtWidgets.QWidget):
    """
    Defines the main structure of the integration widget, which is separated into four parts.
    Integration Image Widget - displaying the image, mask and/or cake
    Integration Control Widget - Handling all the interaction with overlays, phases etc.
    Integration Pattern Widget - showing the integrated pattern
    Integration Status Widget - showing the current mouse position and current background filename
    """

    def __init__(self, *args, **kwargs):
        super(IntegrationWidget, self).__init__(*args, **kwargs)

        self.integration_image_widget = IntegrationImgDisplayWidget()
        self.integration_control_widget = IntegrationControlWidget()
        self.integration_pattern_widget = IntegrationPatternWidget()
        self.integration_status_widget = IntegrationStatusWidget()

        self._layout = QtWidgets.QVBoxLayout()
        self._layout.setSpacing(0)
        self._layout.setContentsMargins(0, 0, 0, 0)

        self.vertical_splitter = QtWidgets.QSplitter(self)
        self.vertical_splitter.setOrientation(QtCore.Qt.Vertical)
        self.vertical_splitter.addWidget(self.integration_control_widget)
        self.vertical_splitter.addWidget(self.integration_pattern_widget)
        self.vertical_splitter.setStretchFactor(0, 1)
        self.vertical_splitter.setStretchFactor(1, 10)

        self.vertical_splitter_left = QtWidgets.QSplitter(self)
        self.vertical_splitter_left.setOrientation(QtCore.Qt.Vertical)
        self.vertical_splitter_left.addWidget(self.integration_image_widget)

        self.horizontal_splitter = QtWidgets.QSplitter()
        self.horizontal_splitter.setOrientation(QtCore.Qt.Horizontal)
        self.horizontal_splitter.addWidget(self.vertical_splitter_left)
        self.horizontal_splitter.addWidget(self.vertical_splitter)
        # self.horizontal_splitter.addWidget(self.vertical_splitter)

        self._layout.addWidget(self.horizontal_splitter, 10)
        self._layout.addWidget(self.integration_status_widget, 0)
        self.setLayout(self._layout)

        self.create_shortcuts()

        self.bkg_image_scale_sb.setKeyboardTracking(False)
        self.bkg_image_offset_sb.setKeyboardTracking(False)

        self.qa_bkg_pattern_inspect_btn.setVisible(False)

        self.mask_transparent_cb.setVisible(False)

        self.file_info_widget = FileInfoWidget(self)
        self.move_widget = MoveStageWidget(self)
        # self.map_2D_widget = Map2DWidget(self)
        self.batch_widget = BatchWidget(self)

        self.img_frame_size = QtCore.QSize(400, 500)
        self.img_frame_position = QtCore.QPoint(0, 0)

        self.img_mode = 'Image'

    def create_shortcuts(self):
        img_control_widget = self.integration_control_widget.img_control_widget.file_widget
        self.image_control_widget = img_control_widget
        self.load_img_btn = img_control_widget.load_btn
        self.autoprocess_cb = img_control_widget.file_cb
        self.img_step_file_widget = img_control_widget.step_file_widget
        self.img_step_series_widget = img_control_widget.step_series_widget
        self.img_filename_txt = img_control_widget.file_txt
        self.img_directory_txt = img_control_widget.directory_txt
        self.img_directory_btn = img_control_widget.directory_btn
        self.file_info_btn = self.integration_control_widget.img_control_widget.file_info_btn
        self.move_btn = self.integration_control_widget.img_control_widget.move_btn
        self.move_widget_btn = self.integration_control_widget.img_control_widget.move_btn
        self.img_batch_mode_integrate_rb = self.integration_control_widget.img_control_widget.batch_mode_integrate_rb
        self.img_batch_mode_add_rb = self.integration_control_widget.img_control_widget.batch_mode_add_rb
        self.img_batch_mode_image_save_rb = self.integration_control_widget.img_control_widget.batch_mode_image_save_rb

        pattern_file_widget = self.integration_control_widget.pattern_control_widget.file_widget
        self.pattern_load_btn = pattern_file_widget.load_btn
        self.pattern_autocreate_cb = pattern_file_widget.file_cb
        self.pattern_previous_btn = pattern_file_widget.step_file_widget.previous_btn
        self.pattern_next_btn = pattern_file_widget.step_file_widget.next_btn
        self.pattern_browse_step_txt = pattern_file_widget.step_file_widget.step_txt
        self.pattern_browse_by_name_rb = pattern_file_widget.step_file_widget.browse_by_name_rb
        self.pattern_browse_by_time_rb = pattern_file_widget.step_file_widget.browse_by_time_rb
        self.pattern_filename_txt = pattern_file_widget.file_txt
        self.pattern_directory_txt = pattern_file_widget.directory_txt
        self.pattern_directory_btn = pattern_file_widget.directory_btn
        self.pattern_header_xy_cb = self.integration_control_widget.pattern_control_widget.xy_cb
        self.pattern_header_chi_cb = self.integration_control_widget.pattern_control_widget.chi_cb
        self.pattern_header_dat_cb = self.integration_control_widget.pattern_control_widget.dat_cb
        self.pattern_header_fxye_cb = self.integration_control_widget.pattern_control_widget.fxye_cb
        self.pattern_headers = []
        self.pattern_headers.append(self.pattern_header_xy_cb)
        self.pattern_headers.append(self.pattern_header_chi_cb)
        self.pattern_headers.append(self.pattern_header_dat_cb)
        self.pattern_headers.append(self.pattern_header_fxye_cb)

        phase_control_widget = self.integration_control_widget.phase_control_widget
        self.phase_widget = phase_control_widget
        self.phase_add_btn = phase_control_widget.add_btn
        self.phase_edit_btn = phase_control_widget.edit_btn
        self.phase_del_btn = phase_control_widget.delete_btn
        self.phase_clear_btn = phase_control_widget.clear_btn
        self.phase_save_list_btn = phase_control_widget.save_list_btn
        self.phase_load_list_btn = phase_control_widget.load_list_btn
        self.phase_tw = phase_control_widget.phase_tw
        self.phase_pressure_step_msb = phase_control_widget.pressure_step_msb
        self.phase_temperature_step_msb = phase_control_widget.temperature_step_msb
        self.phase_apply_to_all_cb = phase_control_widget.apply_to_all_cb

        overlay_control_widget = self.integration_control_widget.overlay_control_widget
        self.overlay_widget = overlay_control_widget
        self.overlay_add_btn = overlay_control_widget.add_btn
        self.overlay_del_btn = overlay_control_widget.delete_btn
        self.overlay_clear_btn = overlay_control_widget.clear_btn
        self.overlay_move_up_btn = overlay_control_widget.move_up_btn
        self.overlay_move_down_btn = overlay_control_widget.move_down_btn
        self.overlay_tw = overlay_control_widget.overlay_tw
        self.overlay_scale_step_msb = overlay_control_widget.scale_step_msb
        self.overlay_offset_step_msb = overlay_control_widget.offset_step_msb
        self.waterfall_separation_msb = overlay_control_widget.waterfall_separation_msb
        self.waterfall_btn = overlay_control_widget.waterfall_btn
        self.reset_waterfall_btn = overlay_control_widget.waterfall_reset_btn
        self.overlay_set_as_bkg_btn = overlay_control_widget.set_as_bkg_btn

        corrections_control_widget = self.integration_control_widget.corrections_control_widget
        self.cbn_groupbox = corrections_control_widget.cbn_seat_gb
        self.cbn_param_tw = corrections_control_widget.cbn_param_tw
        self.cbn_plot_btn = corrections_control_widget.cbn_seat_plot_btn
        self.oiadac_groupbox = corrections_control_widget.oiadac_gb
        self.oiadac_param_tw = corrections_control_widget.oiadac_param_tw
        self.oiadac_plot_btn = corrections_control_widget.oiadac_plot_btn
        self.transfer_gb = corrections_control_widget.transfer_gb
        self.transfer_load_original_btn = corrections_control_widget.transfer_load_original_btn
        self.transfer_load_response_btn = corrections_control_widget.transfer_load_response_btn
        self.transfer_plot_btn = corrections_control_widget.transfer_plot_btn
        self.transfer_original_filename_lbl = corrections_control_widget.transfer_original_filename_lbl
        self.transfer_response_filename_lbl = corrections_control_widget.transfer_response_filename_lbl

        background_control_widget = self.integration_control_widget.background_control_widget
        self.bkg_image_load_btn = background_control_widget.load_image_btn
        self.bkg_image_filename_lbl = background_control_widget.filename_lbl
        self.bkg_image_delete_btn = background_control_widget.remove_image_btn
        self.bkg_image_scale_sb = background_control_widget.scale_sb
        self.bkg_image_scale_step_msb = background_control_widget.scale_step_msb
        self.bkg_image_offset_sb = background_control_widget.offset_sb
        self.bkg_image_offset_step_msb = background_control_widget.offset_step_msb
        self.bkg_pattern_gb = background_control_widget.pattern_background_gb
        self.bkg_pattern_smooth_width_sb = background_control_widget.smooth_with_sb
        self.bkg_pattern_iterations_sb = background_control_widget.iterations_sb
        self.bkg_pattern_poly_order_sb = background_control_widget.poly_order_sb
        self.bkg_pattern_x_min_txt = background_control_widget.x_range_min_txt
        self.bkg_pattern_x_max_txt = background_control_widget.x_range_max_txt
        self.bkg_pattern_inspect_btn = background_control_widget.inspect_btn
        self.bkg_pattern_save_btn = background_control_widget.save_btn
        self.bkg_pattern_as_overlay_btn = background_control_widget.as_overlay

        options_control_widget = self.integration_control_widget.integration_options_widget
        self.bin_count_txt = options_control_widget.bin_count_txt
        self.automatic_binning_cb = options_control_widget.bin_count_cb
        self.correct_solid_angle_cb = options_control_widget.correct_solid_angle_cb
        self.supersampling_sb = options_control_widget.supersampling_sb
        self.oned_full_range_btn = options_control_widget.oned_full_toggle_btn
        self.oned_azimuth_min_txt = options_control_widget.oned_azimuth_min_txt
        self.oned_azimuth_max_txt = options_control_widget.oned_azimuth_max_txt

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
        self.set_wavelnegth_btn = pattern_widget.set_wavelength_btn
        self.wavelength_lbl = pattern_widget.wavelength_lbl
        self.qa_bkg_pattern_btn = pattern_widget.background_btn
        self.qa_bkg_pattern_inspect_btn = pattern_widget.background_inspect_btn
        self.antialias_btn = pattern_widget.antialias_btn
        self.pattern_auto_range_btn = pattern_widget.auto_range_btn
        self.pattern_widget = pattern_widget.pattern_view

        image_widget = self.integration_image_widget
        self.qa_save_img_btn = image_widget.save_image_btn
        self.img_frame = image_widget
        self.img_roi_btn = image_widget.roi_btn
        self.img_mode_btn = image_widget.mode_btn
        self.img_mask_btn = image_widget.mask_btn
        self.img_phases_btn = image_widget.phases_btn
        self.cake_shift_azimuth_sl = image_widget.cake_shift_azimuth_sl
        self.mask_transparent_cb = image_widget.transparent_cb
        self.img_autoscale_btn = image_widget.autoscale_btn
        self.img_dock_btn = image_widget.undock_btn
        self.img_widget = image_widget.img_view
        self.cake_widget = image_widget.cake_view
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
        self.change_view_btn = self.integration_status_widget.change_view_btn

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
            self.vertical_splitter_left_state = self.vertical_splitter_left.saveState()

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
            self.img_frame.setParent(self.vertical_splitter_left)

            self.vertical_splitter_left.insertWidget(1, self.img_frame)
            # self.horizontal_splitter.addWidget(self.vertical_splitter)

            # restore the previously used size when image was undocked
            self.horizontal_splitter.restoreState(self.horizontal_splitter_state)
            self.vertical_splitter_left.restoreState(self.vertical_splitter_left_state)

    def get_progress_dialog(self, message, abort_text, num_points):
        progress_dialog = QtWidgets.QProgressDialog(message, abort_text, 0,
                                                    num_points, self)
        progress_dialog.setWindowModality(QtCore.Qt.WindowModal)
        progress_dialog.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        progress_dialog.move(
            int(self.pattern_widget.pg_layout.x() + self.pattern_widget.pg_layout.size().width() / 2.0 -
                progress_dialog.size().width() / 2.0),
            int(self.pattern_widget.pg_layout.y() + self.pattern_widget.pg_layout.size().height() / 2.0 -
                progress_dialog.size().height() / 2.0))
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
