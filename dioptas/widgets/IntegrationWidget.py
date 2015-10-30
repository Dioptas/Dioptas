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

from __future__ import absolute_import

__author__ = 'Clemens Prescher'

from PyQt4 import QtGui, QtCore
from functools import partial

from .UiFiles.IntegrationUI import Ui_xrs_integration_widget
from widgets.plot_widgets.ImgWidget import IntegrationImgView
from widgets.plot_widgets import SpectrumWidget
from .FileInfoWidget import FileInfoWidget


class IntegrationWidget(QtGui.QWidget, Ui_xrs_integration_widget):
    overlay_color_btn_clicked = QtCore.pyqtSignal(int, QtGui.QWidget)
    overlay_show_cb_state_changed = QtCore.pyqtSignal(int, bool)
    overlay_name_changed = QtCore.pyqtSignal(int, str)
    phase_color_btn_clicked = QtCore.pyqtSignal(int, QtGui.QWidget)
    phase_show_cb_state_changed = QtCore.pyqtSignal(int, bool)

    def __init__(self):
        super(IntegrationWidget, self).__init__()
        self.setupUi(self)

        self.tabWidget.setCurrentIndex(0)

        self.horizontal_splitter.setStretchFactor(0, 1)
        self.horizontal_splitter.setStretchFactor(1, 1)
        self.horizontal_splitter.setSizes([500, 500])
        self.vertical_splitter.setStretchFactor(0, 0)
        self.vertical_splitter.setStretchFactor(1, 1)
        self.vertical_splitter.setSizes([50, 700])

        self.img_view = IntegrationImgView(self.img_pg_layout, orientation='horizontal')
        self.img_pg_layout.ci.layout.setContentsMargins(10, 10, 10, 5)
        self.img_pg_layout.ci.layout.setSpacing(5)
        self.frame_img_positions_widget.hide()
        self.img_frame_size = QtCore.QSize(400, 500)
        self.img_frame_position = QtCore.QPoint(0, 0)

        self.spectrum_view = SpectrumWidget(self.spectrum_pg_layout)
        self.spectrum_pg_layout.ci.layout.setContentsMargins(5, 0, 0, 5)

        self.set_validator()

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

    def set_validator(self):
        self.phase_pressure_step_txt.setValidator(QtGui.QDoubleValidator())
        self.phase_temperature_step_txt.setValidator(QtGui.QDoubleValidator())
        self.overlay_scale_step_txt.setValidator(QtGui.QDoubleValidator())
        self.overlay_offset_step_txt.setValidator(QtGui.QDoubleValidator())
        self.waterfall_separation_txt.setValidator(QtGui.QDoubleValidator())
        self.phase_pressure_step_txt.setValidator(QtGui.QDoubleValidator())
        self.phase_temperature_step_txt.setValidator(QtGui.QDoubleValidator())
        self.bin_count_txt.setValidator(QtGui.QIntValidator())

        self.cbn_diamond_thickness_txt.setValidator(QtGui.QDoubleValidator())
        self.cbn_seat_thickness_txt.setValidator(QtGui.QDoubleValidator())
        self.cbn_cell_tilt_txt.setValidator(QtGui.QDoubleValidator())
        self.cbn_inner_seat_radius_txt.setValidator(QtGui.QDoubleValidator())
        self.cbn_outer_seat_radius_txt.setValidator(QtGui.QDoubleValidator())
        self.cbn_tilt_rotation_txt.setValidator(QtGui.QDoubleValidator())
        self.cbn_center_offset_txt.setValidator(QtGui.QDoubleValidator())
        self.cbn_center_offset_angle_txt.setValidator(QtGui.QDoubleValidator())

        self.oiadac_abs_length_txt.setValidator(QtGui.QDoubleValidator())
        self.oiadac_thickness_txt.setValidator(QtGui.QDoubleValidator())

        self.bkg_spectrum_x_max_txt.setValidator(QtGui.QDoubleValidator())
        self.bkg_spectrum_x_min_txt.setValidator(QtGui.QDoubleValidator())

        self.spec_browse_step_txt.setValidator(QtGui.QIntValidator())
        self.image_browse_step_txt.setValidator(QtGui.QIntValidator())

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

            #remove all widgets/frames from horizontal splitter to be able to arrange them in the correct order
            self.vertical_splitter.setParent(self)

            self.img_frame.setParent(self.horizontal_splitter)
            self.horizontal_splitter.addWidget(self.img_frame)

            self.vertical_splitter.setParent(self.horizontal_splitter)
            self.horizontal_splitter.addWidget(self.vertical_splitter)

            # restore the previously used size when image was undocked
            self.horizontal_splitter.restoreState(self.horizontal_splitter_state)

    def get_progress_dialog(self, msg, title, num_points):
        progress_dialog = QtGui.QProgressDialog("Integrating multiple files.", "Abort Integration", 0,
                                                num_points,  self)
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

        name_str = str(self.phase_tw.item(ind,2).text())
        parameter_str = ''

        if self.show_parameter_in_spectrum:
            if pressure > 0:
                parameter_str += '{0} GPa '.format(pressure)
            if temperature !=0 and temperature!=298 and temperature is not None:
                parameter_str += '{0} K '.format(temperature)

        self.spectrum_view.rename_phase(ind, parameter_str+name_str)

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


class NoRectDelegate(QtGui.QItemDelegate):
    def __init__(self):
        super(NoRectDelegate, self).__init__()

    def drawFocus(self, painter, option, rect):
        option.state &= ~QtGui.QStyle.State_HasFocus
        QtGui.QItemDelegate.drawFocus(self, painter, option, rect)