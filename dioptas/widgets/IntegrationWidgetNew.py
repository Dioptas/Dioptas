# -*- coding: utf8 -*-

import os
from functools import partial

from PyQt4 import QtGui, QtCore
from pyqtgraph import GraphicsLayoutWidget

from widgets.plot_widgets.ImgWidget import IntegrationImgView
from widgets.plot_widgets import SpectrumWidget

from widgets.FileInfoWidget import FileInfoWidget

from widgets.CustomWidgets import NumberTextField, IntegerTextField, LabelAlignRight, SpinBoxAlignRight, \
    DoubleSpinBoxAlignRight, FlatButton, CheckableFlatButton, HorizontalSpacerItem, VerticalSpacerItem, \
    NoRectDelegate

clicked_color = '#00DD00'
widget_path = os.path.dirname(__file__)


class IntegrationWidget(QtGui.QWidget):
    """
    Defines the main structure of the integration widget, which is separated into four parts.
    Integration Image Widget - displaying the image, mask and/or cake
    Integration Control Widget - Handling all the interaction with overlays, phases etc.
    Integration Patter Widget - showing the integrated pattern
    Integration Status Widget - showing the current mouse position and current background filename
    """

    overlay_color_btn_clicked = QtCore.pyqtSignal(int, QtGui.QWidget)
    overlay_show_cb_state_changed = QtCore.pyqtSignal(int, bool)
    overlay_name_changed = QtCore.pyqtSignal(int, str)
    phase_color_btn_clicked = QtCore.pyqtSignal(int, QtGui.QWidget)
    phase_show_cb_state_changed = QtCore.pyqtSignal(int, bool)

    def __init__(self, *args, **kwargs):
        super(IntegrationWidget, self).__init__(*args, **kwargs)

        self.integration_image_widget = IntegrationImgWidget()
        self.integration_control_widget = IntegrationControlWidget()
        self.integration_pattern_widget = IntegrationPatternWidget()
        self.integration_status_widget = IntegrationStatusWidget()

        self._layout = QtGui.QVBoxLayout()
        self._layout.setSpacing(6)
        self._layout.setContentsMargins(6, 0, 6, 0)

        self._vertical_splitter = QtGui.QSplitter()
        self._vertical_splitter.setOrientation(QtCore.Qt.Vertical)
        self._vertical_splitter.addWidget(self.integration_control_widget)
        self._vertical_splitter.addWidget(self.integration_pattern_widget)

        self._horizontal_splitter = QtGui.QSplitter()
        self._horizontal_splitter.setOrientation(QtCore.Qt.Horizontal)
        self._horizontal_splitter.addWidget(self.integration_image_widget)
        self._horizontal_splitter.addWidget(self._vertical_splitter)
        self._layout.addWidget(self._horizontal_splitter, 10)
        self._layout.addWidget(self.integration_status_widget, 0)
        self.setLayout(self._layout)

        self.create_shortcuts()

        self.overlay_tw.cellChanged.connect(self.overlay_label_editingFinished)
        self.overlay_show_cbs = []
        self.overlay_color_btns = []
        self.overlay_tw.setItemDelegate(NoRectDelegate())

        self.phase_show_cbs = []
        self.phase_color_btns = []
        self.show_parameter_in_spectrum = True
        header_view = QtGui.QHeaderView(QtCore.Qt.Horizontal, self.phase_tw)
        self.phase_tw.setHorizontalHeader(header_view)
        header_view.setResizeMode(2, QtGui.QHeaderView.Stretch)
        header_view.setResizeMode(3, QtGui.QHeaderView.ResizeToContents)
        header_view.setResizeMode(4, QtGui.QHeaderView.ResizeToContents)
        header_view.hide()
        self.phase_tw.setItemDelegate(NoRectDelegate())

        self.bkg_image_scale_sb.setKeyboardTracking(False)
        self.bkg_image_offset_sb.setKeyboardTracking(False)

        self.qa_bkg_spectrum_inspect_btn.setVisible(False)

        self.mask_transparent_cb.setVisible(False)

        self.file_info_widget = FileInfoWidget(self)

        self.set_stylesheet()

    def set_stylesheet(self):
        file = open(os.path.join(widget_path, "stylesheet.qss"))
        stylesheet = file.read()
        self.setStyleSheet(stylesheet)
        file.close()

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

        pattern_file_widget = self.integration_control_widget.pattern_control_widget.file_widget
        self.spec_load_btn = pattern_file_widget.load_btn
        self.spec_autocreate_cb = pattern_file_widget.file_cb
        self.spec_previous_btn = pattern_file_widget.previous_btn
        self.spec_next_btn = pattern_file_widget.next_btn
        self.spec_browse_step_txt = pattern_file_widget.step_txt
        self.spec_browse_by_name_rb = pattern_file_widget.browse_by_name_rb
        self.spec_browse_by_time_rb = pattern_file_widget.browse_by_time_rb
        self.spec_filename_txt = pattern_file_widget.file_txt
        self.spec_directory_txt = pattern_file_widget.directory_txt
        self.spec_directory_btn = pattern_file_widget.directory_btn
        self.spectrum_header_xy_cb = self.integration_control_widget.pattern_control_widget.xy_cb
        self.spectrum_header_chi_cb = self.integration_control_widget.pattern_control_widget.chi_cb
        self.spectrum_header_dat_cb = self.integration_control_widget.pattern_control_widget.dat_cb

        phase_control_widget = self.integration_control_widget.phase_control_widget
        self.phase_add_btn = phase_control_widget.add_btn
        self.phase_edit_btn = phase_control_widget.edit_btn
        self.phase_del_btn = phase_control_widget.delete_btn
        self.phase_clear_btn = phase_control_widget.clear_btn
        self.phase_tw = phase_control_widget.phase_tw
        self.phase_pressure_sb = phase_control_widget.pressure_sb
        self.phase_pressure_step_txt = phase_control_widget.pressure_step_txt
        self.phase_temperature_sb = phase_control_widget.temperature_sb
        self.phase_temperature_step_txt = phase_control_widget.temperature_step_txt
        self.phase_apply_to_all_cb = phase_control_widget.apply_to_all_cb
        self.phase_show_parameter_in_spectrum_cb = phase_control_widget.show_in_spectrum_cb

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
        self.bkg_spectrum_gb = background_control_widget.pattern_background_gb
        self.bkg_spectrum_smooth_width_sb = background_control_widget.smooth_with_sb
        self.bkg_spectrum_iterations_sb = background_control_widget.iterations_sb
        self.bkg_spectrum_poly_order_sb = background_control_widget.poly_order_sb
        self.bkg_spectrum_x_min_txt = background_control_widget.x_range_min_txt
        self.bkg_spectrum_x_max_txt = background_control_widget.x_range_max_txt
        self.bkg_spectrum_inspect_btn = background_control_widget.inspect_btn

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
        self.qa_save_spectrum_btn = pattern_widget.save_pattern_btn
        self.qa_set_as_overlay_btn = pattern_widget.as_overlay_btn
        self.qa_set_as_background_btn = pattern_widget.as_bkg_btn
        self.load_calibration_btn = pattern_widget.load_calibration_btn
        self.calibration_lbl = pattern_widget.calibration_lbl
        self.spec_tth_btn = pattern_widget.tth_btn
        self.spec_q_btn = pattern_widget.q_btn
        self.spec_d_btn = pattern_widget.d_btn
        self.qa_bkg_spectrum_btn = pattern_widget.background_btn
        self.qa_bkg_spectrum_inspect_btn = pattern_widget.background_inspect_btn
        self.antialias_btn = pattern_widget.antialias_btn
        self.spec_auto_range_btn = pattern_widget.auto_range_btn
        self.spectrum_view = pattern_widget.spectrum_view

        image_widget = self.integration_image_widget
        self.img_frame = image_widget.frame
        self.img_roi_btn = image_widget.roi_btn
        self.img_mode_btn = image_widget.mode_btn
        self.img_mask_btn = image_widget.mask_btn
        self.mask_transparent_cb = image_widget.transparent_cb
        self.img_autoscale_btn = image_widget.autoscale_btn
        self.img_dock_btn = image_widget.undock_btn
        self.img_view = image_widget.img_view

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

    def switch_to_cake(self):
        self.img_view.img_view_box.setAspectLocked(False)
        self.img_view.activate_vertical_line()

    def switch_to_img(self):
        self.img_view.img_view_box.setAspectLocked(True)
        self.img_view.deactivate_vertical_line()

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
            self.vertical_splitter.setParent(self)

            self.img_frame.setParent(self.horizontal_splitter)
            self.horizontal_splitter.addWidget(self.img_frame)

            self.vertical_splitter.setParent(self.horizontal_splitter)
            self.horizontal_splitter.addWidget(self.vertical_splitter)

            # restore the previously used size when image was undocked
            self.horizontal_splitter.restoreState(self.horizontal_splitter_state)

    def get_progress_dialog(self, msg, title, num_points):
        progress_dialog = QtGui.QProgressDialog("Integrating multiple files.", "Abort Integration", 0,
                                                num_points, self)
        progress_dialog.setWindowModality(QtCore.Qt.WindowModal)
        progress_dialog.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        progress_dialog.move(
                self.spectrum_view.pg_layout.x() + self.spectrum_view.pg_layout.size().width() / 2.0 - \
                progress_dialog.size().width() / 2.0,
                self.spectrum_view.pg_layout.y() + self.spectrum_view.pg_layout.size().height() / 2.0 -
                progress_dialog.size().height() / 2.0)
        progress_dialog.show()
        return progress_dialog

    def show_error_msg(self, msg):
        msg_box = QtGui.QMessageBox(self)
        msg_box.setWindowFlags(QtCore.Qt.Tool)
        msg_box.setText(msg)
        msg_box.setIcon(QtGui.QMessageBox.Critical)
        msg_box.setWindowTitle('Error')
        msg_box.setStandardButtons(QtGui.QMessageBox.Ok)
        msg_box.setDefaultButton(QtGui.QMessageBox.Ok)
        msg_box.exec_()

    # ###############################################################################################
    # Now comes all the overlay tw stuff
    ################################################################################################

    def add_overlay(self, name, color):
        current_rows = self.overlay_tw.rowCount()
        self.overlay_tw.setRowCount(current_rows + 1)
        self.overlay_tw.blockSignals(True)

        show_cb = QtGui.QCheckBox()
        show_cb.setChecked(True)
        show_cb.stateChanged.connect(partial(self.overlay_show_cb_changed, show_cb))
        show_cb.setStyleSheet("background-color: transparent")
        self.overlay_tw.setCellWidget(current_rows, 0, show_cb)
        self.overlay_show_cbs.append(show_cb)

        color_button = QtGui.QPushButton()
        color_button.setStyleSheet("background-color: " + color)
        color_button.clicked.connect(partial(self.overlay_color_btn_click, color_button))
        self.overlay_tw.setCellWidget(current_rows, 1, color_button)
        self.overlay_color_btns.append(color_button)

        name_item = QtGui.QTableWidgetItem(name)
        name_item.setFlags(name_item.flags() & ~QtCore.Qt.ItemIsEditable)
        self.overlay_tw.setItem(current_rows, 2, QtGui.QTableWidgetItem(name))

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

        show_cb = QtGui.QCheckBox()
        show_cb.setChecked(True)
        show_cb.stateChanged.connect(partial(self.phase_show_cb_changed, show_cb))
        show_cb.setStyleSheet("background-color: transparent")
        self.phase_tw.setCellWidget(current_rows, 0, show_cb)
        self.phase_show_cbs.append(show_cb)

        color_button = QtGui.QPushButton()
        color_button.setStyleSheet("background-color: " + color)
        color_button.clicked.connect(partial(self.phase_color_btn_click, color_button))
        self.phase_tw.setCellWidget(current_rows, 1, color_button)
        self.phase_color_btns.append(color_button)

        name_item = QtGui.QTableWidgetItem(name)
        name_item.setFlags(name_item.flags() & ~QtCore.Qt.ItemIsEditable)
        name_item.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.phase_tw.setItem(current_rows, 2, name_item)

        pressure_item = QtGui.QTableWidgetItem('0 GPa')
        pressure_item.setFlags(pressure_item.flags() & ~QtCore.Qt.ItemIsEditable)
        pressure_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.phase_tw.setItem(current_rows, 3, pressure_item)

        temperature_item = QtGui.QTableWidgetItem('298 K')
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
        self.spectrum_view.rename_phase(ind, name)
        name_item = self.phase_tw.item(ind, 2)
        name_item.setText(name)

    def set_phase_temperature(self, ind, T):
        temperature_item = self.phase_tw.item(ind, 4)
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

        if self.show_parameter_in_spectrum:
            if pressure > 0:
                parameter_str += '{0} GPa '.format(pressure)
            if temperature != 0 and temperature != 298 and temperature is not None:
                parameter_str += '{0} K '.format(temperature)

        self.spectrum_view.rename_phase(ind, parameter_str + name_str)

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

    def get_bkg_spectrum_parameters(self):
        smooth_width = float(self.bkg_spectrum_smooth_width_sb.value())
        iterations = int(self.bkg_spectrum_iterations_sb.value())
        polynomial_order = int(self.bkg_spectrum_poly_order_sb.value())
        return smooth_width, iterations, polynomial_order

    def get_bkg_spectrum_roi(self):
        x_min = float(str(self.bkg_spectrum_x_min_txt.text()))
        x_max = float(str(self.bkg_spectrum_x_max_txt.text()))
        return x_min, x_max


class IntegrationImgWidget(QtGui.QWidget):
    def __init__(self):
        super(IntegrationImgWidget, self).__init__()

        self.frame = QtGui.QFrame()
        self.frame.setObjectName('img_frame')

        self._frame_layout = QtGui.QVBoxLayout()
        self._frame_layout.setContentsMargins(0, 0, 0, 0)
        self._frame_layout.setSpacing(0)

        self.img_pg_layout = GraphicsLayoutWidget()
        self.img_view = IntegrationImgView(self.img_pg_layout, orientation='horizontal')
        self._frame_layout.addWidget(self.img_pg_layout)

        self._mouse_position_layout = QtGui.QHBoxLayout()
        self._mouse_position_layout.setContentsMargins(0,0,0,0)

        self.mouse_pos_widget = MouseCurrentAndClickedWidget()
        self.mouse_unit_widget = MouseUnitCurrentAndClickedWidget()

        self._mouse_position_layout.addWidget(self.mouse_pos_widget)
        self._mouse_position_layout.addSpacerItem(HorizontalSpacerItem())
        self._mouse_position_layout.addWidget(self.mouse_unit_widget)

        self._frame_layout.addLayout(self._mouse_position_layout)

        self._control_layout = QtGui.QHBoxLayout()
        self._control_layout.setContentsMargins(6, 6, 6, 6)
        self._control_layout.setSpacing(6)

        self.roi_btn = CheckableFlatButton('ROI')
        self.mode_btn = FlatButton('Cake')
        self.mask_btn = CheckableFlatButton('Mask')
        self.transparent_cb = QtGui.QCheckBox('trans')
        self.autoscale_btn = CheckableFlatButton('AutoScale')
        self.undock_btn = FlatButton('Undock')

        self._control_layout.addWidget(self.roi_btn)
        self._control_layout.addWidget(self.mode_btn)
        self._control_layout.addWidget(self.mask_btn)
        self._control_layout.addWidget(self.transparent_cb)
        self._control_layout.addSpacerItem(HorizontalSpacerItem())
        self._control_layout.addWidget(self.autoscale_btn)
        self._control_layout.addWidget(self.undock_btn)

        self._frame_layout.addLayout(self._control_layout)
        self.frame.setLayout(self._frame_layout)

        self._layout = QtGui.QVBoxLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._layout.addWidget(self.frame)

        self.setLayout(self._layout)

        self.setStyleSheet('#img_frame, QLabel {background: black;}')


class IntegrationControlWidget(QtGui.QTabWidget):
    def __init__(self):
        super(IntegrationControlWidget, self).__init__()

        self.img_control_widget = ImageControlWidget()
        self.pattern_control_widget = PatternControlWidget()
        self.phase_control_widget = PhaseControlWidget()
        self.overlay_control_widget = OverlayControlWidget()
        self.corrections_control_widget = CorrectionsControlWidget()
        self.background_control_widget = BackgroundControlWidget()
        self.integration_options_widget = OptionsWidget()

        self.addTab(self.img_control_widget, 'Image')
        self.addTab(self.pattern_control_widget, 'Pattern')
        self.addTab(self.phase_control_widget, 'Phase')
        self.addTab(self.overlay_control_widget, 'Overlay')
        self.addTab(self.corrections_control_widget, 'Cor')
        self.addTab(self.background_control_widget, 'Bkg')
        self.addTab(self.integration_options_widget, 'X')


class ImageControlWidget(QtGui.QWidget):
    def __init__(self):
        super(ImageControlWidget, self).__init__()

        self._layout = QtGui.QVBoxLayout()

        self.file_widget = BrowseFileWidget(files='Image', checkbox_text='autoprocess')
        self.file_info_btn = FlatButton('File Info')

        self._layout.addWidget(self.file_widget)

        self._file_info_layout = QtGui.QHBoxLayout()
        self._file_info_layout.addWidget(self.file_info_btn)
        self._file_info_layout.addSpacerItem(HorizontalSpacerItem())
        self._layout.addLayout(self._file_info_layout)
        self._layout.addSpacerItem(VerticalSpacerItem())

        self.setLayout(self._layout)


class PatternControlWidget(QtGui.QWidget):
    def __init__(self):
        super(PatternControlWidget, self).__init__()

        self._layout = QtGui.QGridLayout()

        self.file_widget = BrowseFileWidget(files='Pattern', checkbox_text='autocreate')

        self.xy_cb = QtGui.QCheckBox('.xy')
        self.xy_cb.setChecked(True)
        self.chi_cb = QtGui.QCheckBox('.chi')
        self.dat_cb = QtGui.QCheckBox('.dat')

        self._layout.addWidget(self.file_widget, 0, 0, 1, 2)

        self.pattern_types_gc = QtGui.QGroupBox('Pattern data types')
        self._pattern_layout = QtGui.QHBoxLayout()
        self._pattern_layout.addWidget(self.xy_cb)
        self._pattern_layout.addWidget(self.chi_cb)
        self._pattern_layout.addWidget(self.dat_cb)
        self.pattern_types_gc.setLayout(self._pattern_layout)
        self._layout.addWidget(self.pattern_types_gc, 1, 0)

        self._layout.addItem(VerticalSpacerItem(), 2, 0)

        self.setLayout(self._layout)


class PhaseControlWidget(QtGui.QWidget):
    def __init__(self):
        super(PhaseControlWidget, self).__init__()

        self._layout = QtGui.QVBoxLayout()

        self._control_layout = QtGui.QHBoxLayout()
        self.add_btn = FlatButton('Add')
        self.edit_btn = FlatButton('Edit')
        self.delete_btn = FlatButton('Delete')
        self.clear_btn = FlatButton('Clear')

        self._control_layout.addWidget(self.add_btn)
        self._control_layout.addWidget(self.edit_btn)
        self._control_layout.addWidget(self.delete_btn)
        self._control_layout.addWidget(self.clear_btn)
        self._control_layout.addSpacerItem(HorizontalSpacerItem())
        self._layout.addLayout(self._control_layout)

        self.parameter_widget = QtGui.QWidget()
        self._parameter_layout = QtGui.QGridLayout()
        self.pressure_sb = DoubleSpinBoxAlignRight()
        self.temperature_sb = DoubleSpinBoxAlignRight()
        self.pressure_step_txt = NumberTextField('0.5')
        self.temperature_step_txt = NumberTextField('100')
        self.apply_to_all_cb = QtGui.QCheckBox('Apply to all phases')
        self.show_in_spectrum_cb = QtGui.QCheckBox('Show in Spectrum')

        self._parameter_layout.addWidget(QtGui.QLabel('Parameter'), 0, 1)
        self._parameter_layout.addWidget(QtGui.QLabel('Step'), 0, 3)
        self._parameter_layout.addWidget(QtGui.QLabel('P:'), 1, 0)
        self._parameter_layout.addWidget(QtGui.QLabel('T:'), 2, 0)
        self._parameter_layout.addWidget(QtGui.QLabel('GPa'), 1, 2)
        self._parameter_layout.addWidget(QtGui.QLabel('K'), 2, 2)

        self._parameter_layout.addWidget(self.pressure_sb, 1, 1)
        self._parameter_layout.addWidget(self.pressure_step_txt, 1, 3)
        self._parameter_layout.addWidget(self.temperature_sb, 2, 1)
        self._parameter_layout.addWidget(self.temperature_step_txt, 2, 3)

        self._parameter_layout.addWidget(self.apply_to_all_cb, 3, 0, 1, 5)
        self._parameter_layout.addWidget(self.show_in_spectrum_cb, 4, 0, 1, 5)
        self._parameter_layout.addItem(VerticalSpacerItem(), 5, 0)
        self.parameter_widget.setLayout(self._parameter_layout)

        self._body_layout = QtGui.QHBoxLayout()

        self.phase_tw = QtGui.QTableWidget()
        self._body_layout.addWidget(self.phase_tw, 10)
        self._body_layout.addWidget(self.parameter_widget, 0)

        self._layout.addLayout(self._body_layout)

        self.setLayout(self._layout)

        self.style_widgets()

    def style_widgets(self):
        self.phase_tw.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.MinimumExpanding)
        self.parameter_widget.setSizePolicy(QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Minimum)
        self.phase_tw.setMinimumHeight(130)

        self.temperature_step_txt.setMaximumWidth(60)
        self.pressure_step_txt.setMaximumWidth(60)
        self.pressure_sb.setMinimumWidth(100)

        self.pressure_sb.setMaximum(999999)
        self.pressure_sb.setMinimum(0)
        self.pressure_sb.setValue(0)

        self.temperature_sb.setMaximum(99999999)
        self.temperature_sb.setMinimum(0)
        self.temperature_sb.setValue(298)


class OverlayControlWidget(QtGui.QWidget):
    def __init__(self):
        super(OverlayControlWidget, self).__init__()

        self._layout = QtGui.QVBoxLayout()

        self._control_layout = QtGui.QHBoxLayout()
        self.add_btn = FlatButton('Add')
        self.delete_btn = FlatButton('Delete')
        self.clear_btn = FlatButton('Clear')

        self._control_layout.addWidget(self.add_btn)
        self._control_layout.addWidget(self.delete_btn)
        self._control_layout.addWidget(self.clear_btn)
        self._control_layout.addSpacerItem(HorizontalSpacerItem())
        self._layout.addLayout(self._control_layout)

        self._parameter_layout = QtGui.QGridLayout()

        self.scale_sb = DoubleSpinBoxAlignRight()
        self.offset_sb = DoubleSpinBoxAlignRight()
        self.scale_step_txt = NumberTextField('0.01')
        self.offset_step_txt = NumberTextField('100')
        self.waterfall_separation_txt = NumberTextField('100')
        self.waterfall_btn = FlatButton('Waterfall')
        self.waterfall_reset_btn = FlatButton('Reset')
        self.set_as_background_btn = CheckableFlatButton('Set as Background')

        self._parameter_layout.addWidget(QtGui.QLabel('Step'), 0, 2)
        self._parameter_layout.addWidget(LabelAlignRight('Scale:'), 1, 0)
        self._parameter_layout.addWidget(LabelAlignRight('Offset:'), 2, 0)

        self._parameter_layout.addWidget(self.scale_sb, 1, 1)
        self._parameter_layout.addWidget(self.scale_step_txt, 1, 2)
        self._parameter_layout.addWidget(self.offset_sb, 2, 1)
        self._parameter_layout.addWidget(self.offset_step_txt, 2, 2)

        self._parameter_layout.addItem(VerticalSpacerItem(), 3, 0, 1, 3)

        self._waterfall_layout = QtGui.QHBoxLayout()
        self._waterfall_layout.addWidget(self.waterfall_btn)
        self._waterfall_layout.addWidget(self.waterfall_separation_txt)
        self._waterfall_layout.addWidget(self.waterfall_reset_btn)
        self._parameter_layout.addLayout(self._waterfall_layout, 4, 0, 1, 3)
        self._parameter_layout.addItem(VerticalSpacerItem(), 5, 0, 1, 3)

        self._background_layout = QtGui.QHBoxLayout()
        self._background_layout.addSpacerItem(HorizontalSpacerItem())
        self._background_layout.addWidget(self.set_as_background_btn)
        self._parameter_layout.addLayout(self._background_layout, 6, 0, 1, 3)

        self._body_layout = QtGui.QHBoxLayout()
        self.overlay_tw = QtGui.QTableWidget()
        self._body_layout.addWidget(self.overlay_tw, 10)
        self._body_layout.addLayout(self._parameter_layout, 0)

        self._layout.addLayout(self._body_layout)

        self.setLayout(self._layout)
        self.style_widgets()

    def style_widgets(self):
        step_txt_width = 70
        self.scale_step_txt.setMaximumWidth(step_txt_width)
        self.scale_step_txt.setMinimumWidth(step_txt_width)
        self.offset_step_txt.setMaximumWidth(step_txt_width)
        self.waterfall_separation_txt.setMaximumWidth(step_txt_width)

        sb_width = 110
        self.scale_sb.setMaximumWidth(sb_width)
        self.scale_sb.setMinimumWidth(sb_width)
        self.offset_sb.setMaximumWidth(sb_width)
        self.offset_sb.setMinimumWidth(sb_width)

        self.scale_sb.setMinimum(-9999999)
        self.scale_sb.setMaximum(9999999)
        self.scale_sb.setValue(1)

        self.offset_sb.setMaximum(999999998)
        self.offset_sb.setMinimum(-99999999)


class CorrectionsControlWidget(QtGui.QWidget):
    def __init__(self, *args, **kwargs):
        super(CorrectionsControlWidget, self).__init__(*args, **kwargs)

        self._layout = QtGui.QVBoxLayout()

        self.cbn_seat_gb = QtGui.QGroupBox('cBN Seat Correction')
        self._cbn_seat_layout = QtGui.QGridLayout()

        self.anvil_thickness_txt = NumberTextField('2.3')
        self.seat_thickness_txt = NumberTextField('5.3')
        self.seat_inner_radius_txt = NumberTextField('0.4')
        self.seat_outer_radius_txt = NumberTextField('1.95')
        self.cell_tilt_txt = NumberTextField('0.0')
        self.cell_tilt_rotation_txt = NumberTextField('0.0')
        self.center_offset_txt = NumberTextField('0.0')
        self.center_offset_angle_txt = NumberTextField('0.0')
        self.anvil_absorption_length_txt = NumberTextField('13.7')
        self.seat_absorption_length_txt = NumberTextField('21.1')

        self.cbn_seat_plot_btn = CheckableFlatButton('Plot')

        self._cbn_seat_layout.addWidget(LabelAlignRight('Anvil d:'), 0, 0)
        self._cbn_seat_layout.addWidget(LabelAlignRight('Seat r1:'), 0, 4)
        self._cbn_seat_layout.addWidget(LabelAlignRight('Cell Tilt:'), 0, 8)
        self._cbn_seat_layout.addWidget(LabelAlignRight('Offset:'), 0, 12)
        self._cbn_seat_layout.addWidget(LabelAlignRight('Anvil AL:'), 0, 16)

        self._cbn_seat_layout.addWidget(LabelAlignRight('Seat d:'), 1, 0)
        self._cbn_seat_layout.addWidget(LabelAlignRight('Seat r2:'), 1, 4)
        self._cbn_seat_layout.addWidget(LabelAlignRight('Tilt Rot:'), 1, 8)
        self._cbn_seat_layout.addWidget(LabelAlignRight(u"Offs. 2θ  :"), 1, 12)
        self._cbn_seat_layout.addWidget(LabelAlignRight('Seat AL:'), 1, 16)

        self._cbn_seat_layout.addWidget(QtGui.QLabel('mm'), 0, 2)
        self._cbn_seat_layout.addWidget(QtGui.QLabel('mm'), 0, 6)
        self._cbn_seat_layout.addWidget(QtGui.QLabel('mm'), 0, 14)
        self._cbn_seat_layout.addWidget(QtGui.QLabel('mm'), 1, 2)
        self._cbn_seat_layout.addWidget(QtGui.QLabel('mm'), 1, 6)
        self._cbn_seat_layout.addWidget(QtGui.QLabel(u'°'), 0, 10)
        self._cbn_seat_layout.addWidget(QtGui.QLabel(u'°'), 1, 10)
        self._cbn_seat_layout.addWidget(QtGui.QLabel(u'°'), 1, 14)

        self._cbn_seat_layout.addItem(HorizontalSpacerItem(3), 0, 3)
        self._cbn_seat_layout.addItem(HorizontalSpacerItem(3), 0, 7)
        self._cbn_seat_layout.addItem(HorizontalSpacerItem(3), 0, 11)
        self._cbn_seat_layout.addItem(HorizontalSpacerItem(3), 0, 15)

        self._cbn_seat_layout.addWidget(self.anvil_thickness_txt, 0, 1)
        self._cbn_seat_layout.addWidget(self.seat_thickness_txt, 1, 1)
        self._cbn_seat_layout.addWidget(self.seat_inner_radius_txt, 0, 5)
        self._cbn_seat_layout.addWidget(self.seat_outer_radius_txt, 1, 5)
        self._cbn_seat_layout.addWidget(self.cell_tilt_txt, 0, 9)
        self._cbn_seat_layout.addWidget(self.cell_tilt_rotation_txt, 1, 9)
        self._cbn_seat_layout.addWidget(self.center_offset_txt, 0, 13)
        self._cbn_seat_layout.addWidget(self.center_offset_angle_txt, 1, 13)
        self._cbn_seat_layout.addWidget(self.anvil_absorption_length_txt, 0, 17)
        self._cbn_seat_layout.addWidget(self.seat_absorption_length_txt, 1, 17)

        self._cbn_seat_layout.addWidget(self.cbn_seat_plot_btn, 0, 18, 2, 1)

        self.cbn_seat_gb.setLayout(self._cbn_seat_layout)

        self.oiadac_gb = QtGui.QGroupBox('Oblique Incidence Angle Detector Absorption Correction')
        self._oiadac_layout = QtGui.QHBoxLayout()

        self.detector_thickness_txt = NumberTextField('40')
        self.detector_absorption_length_txt = NumberTextField('465.5')
        self.oiadac_plot_btn = CheckableFlatButton('Plot')

        self._oiadac_layout.addWidget(LabelAlignRight('Det. Thickness:'))
        self._oiadac_layout.addWidget(self.detector_thickness_txt)
        self._oiadac_layout.addWidget(QtGui.QLabel('mm'))
        self._oiadac_layout.addSpacing(10)
        self._oiadac_layout.addWidget(LabelAlignRight('Abs. Length:'))
        self._oiadac_layout.addWidget(self.detector_absorption_length_txt)
        self._oiadac_layout.addWidget(QtGui.QLabel('um'))
        self._oiadac_layout.addWidget(self.oiadac_plot_btn)
        self._oiadac_layout.addSpacerItem(HorizontalSpacerItem())

        self.oiadac_gb.setLayout(self._oiadac_layout)

        self._layout.addWidget(self.cbn_seat_gb)
        self._layout.addWidget(self.oiadac_gb)
        self._layout.addSpacerItem(VerticalSpacerItem())

        self.setLayout(self._layout)
        self.style_widgets()

    def style_widgets(self):
        self.cbn_seat_gb.setCheckable(True)
        self.cbn_seat_gb.setChecked(False)

        txt_width = 50
        self.anvil_thickness_txt.setMinimumWidth(txt_width)
        self.seat_thickness_txt.setMinimumWidth(txt_width)
        self.seat_inner_radius_txt.setMinimumWidth(txt_width)
        self.seat_outer_radius_txt.setMinimumWidth(txt_width)
        self.cell_tilt_txt.setMinimumWidth(txt_width)
        self.cell_tilt_rotation_txt.setMinimumWidth(txt_width)
        self.center_offset_txt.setMinimumWidth(txt_width)
        self.center_offset_angle_txt.setMinimumWidth(txt_width)
        self.anvil_absorption_length_txt.setMinimumWidth(txt_width)
        self.seat_absorption_length_txt.setMinimumWidth(txt_width)

        self.anvil_thickness_txt.setMaximumWidth(txt_width)
        self.seat_thickness_txt.setMaximumWidth(txt_width)
        self.seat_inner_radius_txt.setMaximumWidth(txt_width)
        self.seat_outer_radius_txt.setMaximumWidth(txt_width)
        self.cell_tilt_txt.setMaximumWidth(txt_width)
        self.cell_tilt_rotation_txt.setMaximumWidth(txt_width)
        self.center_offset_txt.setMaximumWidth(txt_width)
        self.center_offset_angle_txt.setMaximumWidth(txt_width)
        self.anvil_absorption_length_txt.setMaximumWidth(txt_width)
        self.seat_absorption_length_txt.setMaximumWidth(txt_width)

        self.cbn_seat_plot_btn.setMaximumHeight(150)

        self.oiadac_gb.setCheckable(True)
        self.oiadac_gb.setChecked(False)
        self.detector_thickness_txt.setMinimumWidth(60)
        self.detector_thickness_txt.setMaximumWidth(60)
        self.detector_absorption_length_txt.setMinimumWidth(60)
        self.detector_absorption_length_txt.setMaximumWidth(60)


class BackgroundControlWidget(QtGui.QWidget):
    def __init__(self):
        super(BackgroundControlWidget, self).__init__()

        self._layout = QtGui.QVBoxLayout()

        self.image_background_gb = QtGui.QGroupBox('Image Background')
        self._image_background_gb_layout = QtGui.QGridLayout()

        self.load_image_btn = FlatButton('Load')
        self.filename_lbl = QtGui.QLabel('')
        self.remove_image_btn = FlatButton('Remove')
        self.scale_sb = DoubleSpinBoxAlignRight()
        self.offset_sb = DoubleSpinBoxAlignRight()
        self.scale_step_txt = NumberTextField('0.01')
        self.offset_step_txt = NumberTextField('100')

        self._image_background_gb_layout.addWidget(self.load_image_btn, 0, 0)
        self._image_background_gb_layout.addWidget(self.remove_image_btn, 1, 0)
        self._image_background_gb_layout.addWidget(self.filename_lbl, 0, 1, 1, 8)
        self._image_background_gb_layout.addWidget(LabelAlignRight('Scale:'), 1, 1)
        self._image_background_gb_layout.addWidget(self.scale_sb, 1, 2)
        self._image_background_gb_layout.addWidget(self.scale_step_txt, 1, 3)
        self._image_background_gb_layout.addItem(HorizontalSpacerItem(), 1, 4)
        self._image_background_gb_layout.addWidget(LabelAlignRight('Offset:'), 1, 5)
        self._image_background_gb_layout.addWidget(self.offset_sb, 1, 6)
        self._image_background_gb_layout.addWidget(self.offset_step_txt, 1, 7)
        self._image_background_gb_layout.addItem(HorizontalSpacerItem(), 1, 8)

        self.image_background_gb.setLayout(self._image_background_gb_layout)

        self._layout.addWidget(self.image_background_gb)

        self._layout.addSpacerItem(VerticalSpacerItem())
        self.setLayout(self._layout)

        self.pattern_background_gb = QtGui.QGroupBox('Pattern Background')
        self._pattern_background_gb = QtGui.QGridLayout()

        self.smooth_with_sb = DoubleSpinBoxAlignRight()
        self.iterations_sb = SpinBoxAlignRight()
        self.poly_order_sb = SpinBoxAlignRight()
        self.x_range_min_txt = NumberTextField('0')
        self.x_range_max_txt = NumberTextField('50')
        self.inspect_btn = CheckableFlatButton('Inspect')

        self._smooth_layout = QtGui.QHBoxLayout()
        self._smooth_layout.addWidget(LabelAlignRight('Smooth Width:'))
        self._smooth_layout.addWidget(self.smooth_with_sb)
        self._smooth_layout.addWidget(LabelAlignRight('Iterations:'))
        self._smooth_layout.addWidget(self.iterations_sb)
        self._smooth_layout.addWidget(LabelAlignRight('Poly Order:'))
        self._smooth_layout.addWidget(self.poly_order_sb)

        self._range_layout = QtGui.QHBoxLayout()
        self._range_layout.addWidget(QtGui.QLabel('X-Range:'))
        self._range_layout.addWidget(self.x_range_min_txt)
        self._range_layout.addWidget(QtGui.QLabel('-'))
        self._range_layout.addWidget(self.x_range_max_txt)
        self._range_layout.addSpacerItem(HorizontalSpacerItem())

        self._pattern_background_gb.addLayout(self._smooth_layout, 0, 0)
        self._pattern_background_gb.addLayout(self._range_layout, 1, 0)

        self._pattern_background_gb.addWidget(self.inspect_btn, 0, 2, 2, 1)
        self._pattern_background_gb.addItem(HorizontalSpacerItem(), 0, 3, 2, 1)

        self.pattern_background_gb.setLayout(self._pattern_background_gb)

        self._layout.addWidget(self.pattern_background_gb)

        self.setLayout(self._layout)
        self.style_widgets()

    def style_widgets(self):
        self.style_image_background_widgets()
        self.style_pattern_background_widgets()

    def style_image_background_widgets(self):
        step_txt_width = 70
        self.scale_step_txt.setMaximumWidth(step_txt_width)
        self.scale_step_txt.setMinimumWidth(step_txt_width)
        self.offset_step_txt.setMaximumWidth(step_txt_width)

        sb_width = 110
        self.scale_sb.setMaximumWidth(sb_width)
        self.scale_sb.setMinimumWidth(sb_width)
        self.offset_sb.setMaximumWidth(sb_width)
        self.offset_sb.setMinimumWidth(sb_width)

        self.scale_sb.setMinimum(-9999999)
        self.scale_sb.setMaximum(9999999)
        self.scale_sb.setValue(1)

        self.pattern_background_gb.setCheckable(True)
        self.pattern_background_gb.setChecked(False)

        self.offset_sb.setMaximum(999999998)
        self.offset_sb.setMinimum(-99999999)

    def style_pattern_background_widgets(self):
        self.smooth_with_sb.setValue(0.100)
        self.smooth_with_sb.setMinimum(0)
        self.smooth_with_sb.setMaximum(10000000)
        self.smooth_with_sb.setSingleStep(0.02)
        self.smooth_with_sb.setDecimals(3)
        self.smooth_with_sb.setMaximumWidth(100)

        self.iterations_sb.setMaximum(99999)
        self.iterations_sb.setMinimum(1)
        self.iterations_sb.setValue(150)
        self.poly_order_sb.setMaximum(999999)
        self.poly_order_sb.setMinimum(1)
        self.poly_order_sb.setValue(50)

        self.x_range_min_txt.setMaximumWidth(70)
        self.x_range_max_txt.setMaximumWidth(70)


class OptionsWidget(QtGui.QWidget):
    def __init__(self):
        super(OptionsWidget, self).__init__()

        self._layout = QtGui.QGridLayout()

        self.integration_gb = QtGui.QGroupBox('Integration')
        self._integration_layout = QtGui.QGridLayout()

        self.bin_count_txt = IntegerTextField('0')
        self.bin_count_cb = QtGui.QCheckBox('auto')
        self.supersampling_sb = SpinBoxAlignRight()

        self._integration_layout.addWidget(LabelAlignRight('Number of Bins:'), 0, 0)
        self._integration_layout.addWidget(LabelAlignRight('Supersampling:'), 1, 0)

        self._integration_layout.addWidget(self.bin_count_txt, 0, 1)
        self._integration_layout.addWidget(self.bin_count_cb, 0, 2)

        self._integration_layout.addWidget(self.supersampling_sb, 1, 1)

        self.integration_gb.setLayout(self._integration_layout)

        self._layout.addWidget(self.integration_gb, 0, 0)
        self._layout.addItem(HorizontalSpacerItem(), 0, 1)
        self._layout.addItem(VerticalSpacerItem(), 1, 0, 1, 2)

        self.setLayout(self._layout)
        self.style_widgets()

    def style_widgets(self):
        max_width = 110
        self.bin_count_txt.setMaximumWidth(max_width)
        self.supersampling_sb.setMaximumWidth(max_width)

        self.supersampling_sb.setMinimum(1)
        self.supersampling_sb.setMaximum(20)
        self.supersampling_sb.setSingleStep(1)

        self.bin_count_txt.setEnabled(False)
        self.bin_count_cb.setChecked(True)


class BrowseFileWidget(QtGui.QWidget):
    def __init__(self, files, checkbox_text):
        super(BrowseFileWidget, self).__init__()

        self._layout = QtGui.QGridLayout()

        self.load_btn = FlatButton('Load {}(s)'.format(files))
        self.file_cb = QtGui.QCheckBox(checkbox_text)
        self.next_btn = FlatButton('>')
        self.previous_btn = FlatButton('<')
        self.step_txt = QtGui.QLineEdit('1')
        self.step_txt.setValidator(QtGui.QIntValidator())
        self.browse_by_name_rb = QtGui.QRadioButton('By Name')
        self.browse_by_name_rb.setChecked(True)
        self.browse_by_time_rb = QtGui.QRadioButton('By Time')
        self.directory_txt = QtGui.QLineEdit('')
        self.directory_btn = FlatButton('...')
        self.file_txt = QtGui.QLineEdit('')

        self._layout.addWidget(self.load_btn, 0, 0)
        self._layout.addWidget(self.file_cb, 1, 0)

        self._layout.addWidget(self.previous_btn, 0, 1)
        self._layout.addWidget(self.next_btn, 0, 2)
        self._step_layout = QtGui.QHBoxLayout()
        self._step_layout.addWidget(LabelAlignRight('Step:'))
        self._step_layout.addWidget(self.step_txt)
        self._layout.addLayout(self._step_layout, 1, 1, 1, 2)

        self._layout.addWidget(self.browse_by_name_rb, 0, 3)
        self._layout.addWidget(self.browse_by_time_rb, 1, 3)

        self._layout.addWidget(self.file_txt, 0, 4, 1, 2)
        self._layout.addWidget(self.directory_txt, 1, 4)
        self._layout.addWidget(self.directory_btn, 1, 5)

        self.setLayout(self._layout)

        self.style_widgets()

    def style_widgets(self):
        self.load_btn.setMaximumWidth(120)
        self.load_btn.setMinimumWidth(120)
        maximum_width = 40

        self.next_btn.setMaximumWidth(maximum_width)
        self.previous_btn.setMaximumWidth(maximum_width)
        self.directory_btn.setMaximumWidth(maximum_width)

        self.step_txt.setMaximumWidth(30)


class IntegrationPatternWidget(QtGui.QWidget):
    def __init__(self):
        super(IntegrationPatternWidget, self).__init__()

        self.frame = QtGui.QFrame()
        self.frame.setObjectName('pattern_frame')

        self._frame_layout = QtGui.QVBoxLayout()
        self._frame_layout.setContentsMargins(0,0,6,0)

        self._top_control_layout = QtGui.QHBoxLayout()
        self._top_control_layout.setContentsMargins(8, 8, 0, 0)

        self.save_image_btn = FlatButton('Save Image')
        self.save_pattern_btn = FlatButton('Save Pattern')
        self.as_overlay_btn = FlatButton('As Overlay')
        self.as_bkg_btn = FlatButton('As Bkg')
        self.load_calibration_btn = FlatButton('Load Calibration')
        self.calibration_lbl = LabelAlignRight('None')

        self._top_control_layout.addWidget(self.save_image_btn)
        self._top_control_layout.addWidget(self.save_pattern_btn)
        self._top_control_layout.addWidget(self.as_overlay_btn)
        self._top_control_layout.addWidget(self.as_bkg_btn)
        self._top_control_layout.addSpacerItem(HorizontalSpacerItem())
        self._top_control_layout.addWidget(self.load_calibration_btn)
        self._top_control_layout.addWidget(self.calibration_lbl)

        self._frame_layout.addLayout(self._top_control_layout)

        self.right_control_widget = QtGui.QWidget()
        self.right_control_widget.setObjectName('pattern_right_control_widget')
        self._right_control_layout = QtGui.QVBoxLayout()
        self._right_control_layout.setContentsMargins(0,0,0,6)

        self.tth_btn = CheckableFlatButton(u"2θ")
        self.q_btn = CheckableFlatButton('Q')
        self.d_btn = CheckableFlatButton('d')
        self.background_btn = CheckableFlatButton('bg')
        self.background_inspect_btn = CheckableFlatButton('I')
        self.antialias_btn = CheckableFlatButton('AA')
        self.auto_range_btn = CheckableFlatButton('A')

        self._right_control_layout.addWidget(self.tth_btn)
        self._right_control_layout.addWidget(self.q_btn)
        self._right_control_layout.addWidget(self.d_btn)
        self._right_control_layout.addSpacerItem(VerticalSpacerItem())
        self._right_control_layout.addWidget(self.background_btn)
        self._right_control_layout.addWidget(self.background_inspect_btn)
        self._right_control_layout.addSpacerItem(VerticalSpacerItem())
        self._right_control_layout.addWidget(self.antialias_btn)
        self._right_control_layout.addSpacerItem(VerticalSpacerItem())
        self._right_control_layout.addWidget(self.auto_range_btn)

        self.right_control_widget.setLayout(self._right_control_layout)

        self._central_layout = QtGui.QHBoxLayout()
        self._central_layout.setSpacing(0)

        self.spectrum_pg_layout = GraphicsLayoutWidget()
        self.spectrum_view = SpectrumWidget(self.spectrum_pg_layout)

        self._central_layout.addWidget(self.spectrum_pg_layout)
        self._central_layout.addWidget(self.right_control_widget)
        self._frame_layout.addLayout(self._central_layout)

        self.frame.setLayout(self._frame_layout)

        self._layout = QtGui.QVBoxLayout()
        self._layout.addWidget(self.frame)
        self._layout.setContentsMargins(0,0,0,0)
        self.setLayout(self._layout)


        self.style_widgets()

    def style_widgets(self):
        self.tth_btn.setChecked(True)

        self.setStyleSheet("""
            #pattern_frame, #pattern_right_control_widget, QLabel {
                background: black;
                color: yellow;
            }
            #pattern_right_control_widget QPushButton{
                padding: 0px;
	            padding-right: 1px;
	            border-radius: 3px;
            }
	    """)

        right_controls_button_width = 25
        self.tth_btn.setMaximumWidth(right_controls_button_width)
        self.q_btn.setMaximumWidth(right_controls_button_width)
        self.d_btn.setMaximumWidth(right_controls_button_width)
        self.background_btn.setMaximumWidth(right_controls_button_width)
        self.background_inspect_btn.setMaximumWidth(right_controls_button_width)
        self.antialias_btn.setMaximumWidth(right_controls_button_width)
        self.auto_range_btn.setMaximumWidth(right_controls_button_width)


class IntegrationStatusWidget(QtGui.QWidget):
    def __init__(self):
        super(IntegrationStatusWidget, self).__init__()

        self._layout = QtGui.QHBoxLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)

        self.mouse_pos_widget = MouseCurrentAndClickedWidget()
        self.mouse_unit_widget = MouseUnitCurrentAndClickedWidget()
        self.bkg_name_lbl = LabelAlignRight('')

        self._layout.addWidget(self.mouse_pos_widget)
        self._layout.addSpacerItem(HorizontalSpacerItem())
        self._layout.addWidget(self.mouse_unit_widget)
        self._layout.addSpacerItem(HorizontalSpacerItem())
        self._layout.addWidget(self.bkg_name_lbl)

        self.setLayout(self._layout)


class MouseCurrentAndClickedWidget(QtGui.QWidget):
    def __init__(self):
        super(MouseCurrentAndClickedWidget, self).__init__()

        self._layout = QtGui.QVBoxLayout()
        self._layout.setSpacing(0)

        self.cur_pos_widget = MousePositionWidget()
        self.clicked_pos_widget = MousePositionWidget(clicked_color)

        self._layout.addWidget(self.cur_pos_widget)
        self._layout.addWidget(self.clicked_pos_widget)

        self.setLayout(self._layout)


class MousePositionWidget(QtGui.QWidget):
    def __init__(self, color=None):
        super(MousePositionWidget, self).__init__()

        self._layout = QtGui.QHBoxLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)

        self.x_pos_lbl = LabelAlignRight('X:')
        self.y_pos_lbl = LabelAlignRight('Y:')
        self.int_lbl = LabelAlignRight('I:')

        self._layout.addWidget(self.x_pos_lbl)
        self._layout.addWidget(self.y_pos_lbl)
        self._layout.addWidget(self.int_lbl)

        self.setLayout(self._layout)

        if color is not None:
            style_str = 'color: {};'.format(color)
            self.x_pos_lbl.setStyleSheet(style_str)
            self.y_pos_lbl.setStyleSheet(style_str)
            self.int_lbl.setStyleSheet(style_str)


class MouseUnitCurrentAndClickedWidget(QtGui.QWidget):
    def __init__(self):
        super(MouseUnitCurrentAndClickedWidget, self).__init__()
        self._layout = QtGui.QVBoxLayout()
        self._layout.setSpacing(0)

        self.cur_unit_widget = MouseUnitWidget()
        self.clicked_unit_widget = MouseUnitWidget(clicked_color)

        self._layout.addWidget(self.cur_unit_widget)
        self._layout.addWidget(self.clicked_unit_widget)

        self.setLayout(self._layout)


class MouseUnitWidget(QtGui.QWidget):
    def __init__(self, color=None):
        super(MouseUnitWidget, self).__init__()

        self._layout = QtGui.QHBoxLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)

        self.tth_lbl = LabelAlignRight(u"2θ:")
        self.q_lbl = LabelAlignRight('Q:')
        self.d_lbl = LabelAlignRight('d:')
        self.azi_lbl = LabelAlignRight('X:')

        self._layout.addWidget(self.tth_lbl)
        self._layout.addWidget(self.q_lbl)
        self._layout.addWidget(self.d_lbl)
        self._layout.addWidget(self.azi_lbl)

        self.setLayout(self._layout)

        if color is not None:
            style_str = 'color: {};'.format(color)
            self.tth_lbl.setStyleSheet(style_str)
            self.d_lbl.setStyleSheet(style_str)
            self.q_lbl.setStyleSheet(style_str)
            self.azi_lbl.setStyleSheet(style_str)


if __name__ == '__main__':
    app = QtGui.QApplication([])
    widget = IntegrationWidget()
    widget.show()
    # widget.setWindowState(widget.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
    # widget.activateWindow()
    # widget.raise_()
    app.exec_()
