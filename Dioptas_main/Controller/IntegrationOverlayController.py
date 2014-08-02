# -*- coding: utf-8 -*-
#  Py2DeX - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2014  Clemens Prescher (clemens.prescher@gmail.com)
# GSECARS, University of Chicago
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <http://www.gnu.org/licenses/>.
#



__author__ = 'Clemens Prescher'
import os
from PyQt4 import QtGui, QtCore
import numpy as np
from Data.HelperModule import get_base_name


class IntegrationOverlayController(object):
    def __init__(self, working_dir, view, spectrum_data):
        self.working_dir = working_dir
        self.view = view
        self.spectrum_data = spectrum_data
        self.overlay_lw_items = []
        self.create_signals()

    def create_signals(self):
        self.connect_click_function(self.view.overlay_add_btn, self.add_overlay)
        self.connect_click_function(self.view.overlay_del_btn, self.del_overlay)
        self.view.overlay_clear_btn.clicked.connect(self.clear_overlays)

        self.view.overlay_tw.currentCellChanged.connect(self.overlay_selection_changed)
        self.view.overlay_color_btn_clicked.connect(self.overlay_color_btn_clicked)
        self.view.overlay_show_cb_state_changed.connect(self.overlay_show_cb_state_changed)
        self.view.overlay_name_changed.connect(self.rename_overlay)

        self.view.overlay_scale_step_txt.editingFinished.connect(self.update_overlay_scale_step)
        self.view.overlay_offset_step_txt.editingFinished.connect(self.update_overlay_offset_step)
        self.view.overlay_scale_sb.valueChanged.connect(self.overlay_scale_sb_changed)
        self.view.overlay_offset_sb.valueChanged.connect(self.overlay_offset_sb_changed)

        self.view.overlay_set_as_bkg_btn.clicked.connect(self.overlay_set_as_bkg_btn_clicked)

        # creating the quickactions signals

        self.connect_click_function(self.view.qa_img_set_as_overlay_btn, self.set_as_overlay)
        self.connect_click_function(self.view.qa_spectrum_set_as_overlay_btn, self.set_as_overlay)

        self.connect_click_function(self.view.qa_img_set_as_background_btn, self.qa_set_as_background_btn_click)
        self.connect_click_function(self.view.qa_spectrum_set_as_background_btn, self.qa_set_as_background_btn_click)

    def connect_click_function(self, emitter, function):
        self.view.connect(emitter, QtCore.SIGNAL('clicked()'), function)

    def add_overlay(self, filename=None):
        if filename is None:
            filenames = QtGui.QFileDialog.getOpenFileNames(self.view, "Load Overlay(s).", self.working_dir['overlay'])
            if len(filenames):
                for filename in filenames:
                    filename = str(filename)
                    self.spectrum_data.add_overlay_file(filename)
                    color = self.view.spectrum_view.add_overlay(self.spectrum_data.overlays[-1])
                    self.view.add_overlay(get_base_name(filename), '#%02x%02x%02x' % (color[0], color[1], color[2]))
                self.working_dir['overlay'] = os.path.dirname(str(filenames[0]))
        else:
            self.spectrum_data.add_overlay_file(filename)
            color = self.view.spectrum_view.add_overlay(self.spectrum_data.overlays[-1])
            self.view.add_overlay(get_base_name(filename), '#%02x%02x%02x' % (color[0], color[1], color[2]))
            self.working_dir['overlay'] = os.path.dirname(str(filename))

    def del_overlay(self):
        cur_ind = self.view.get_selected_overlay_row()
        if cur_ind >= 0:
            if self.spectrum_data.bkg_ind > cur_ind:
                self.spectrum_data.bkg_ind -= 1
            elif self.spectrum_data.bkg_ind == cur_ind:
                self.spectrum_data.spectrum.reset_background()
                self.spectrum_data.bkg_ind = -1
                self.spectrum_data.notify()
            self.spectrum_data.overlays.remove(self.spectrum_data.overlays[cur_ind])
            self.view.del_overlay(cur_ind)
            self.view.spectrum_view.del_overlay(cur_ind)

    def set_as_overlay(self, show=True):
        self.spectrum_data.set_current_spectrum_as_overlay()
        color = self.view.spectrum_view.add_overlay(self.spectrum_data.overlays[-1], show)
        self.view.add_overlay(get_base_name(self.spectrum_data.overlays[-1].name),
                              '#%02x%02x%02x' % (color[0], color[1], color[2]))

    def clear_overlays(self):
        while self.view.overlay_tw.rowCount() > 0:
            self.del_overlay()

    def update_overlay_scale_step(self):
        value = np.float(self.view.overlay_scale_step_txt.text())
        self.view.overlay_scale_sb.setSingleStep(value)

    def update_overlay_offset_step(self):
        value = np.float(self.view.overlay_offset_step_txt.text())
        self.view.overlay_offset_sb.setSingleStep(value)

    def overlay_selection_changed(self, row, col, prev_row, prev_col):
        cur_ind = row
        self.view.overlay_scale_sb.blockSignals(True)
        self.view.overlay_offset_sb.blockSignals(True)
        self.view.overlay_scale_sb.setValue(self.spectrum_data.overlays[cur_ind].scaling)
        self.view.overlay_offset_sb.setValue(self.spectrum_data.overlays[cur_ind].offset)
        # self.view.spectrum_view.update_overlay(self.spectrum_data.overlays[cur_ind], cur_ind)
        self.view.overlay_scale_sb.blockSignals(False)
        self.view.overlay_offset_sb.blockSignals(False)
        if cur_ind == self.spectrum_data.bkg_ind and not cur_ind == -1:
            self.view.overlay_set_as_bkg_btn.setChecked(True)
        else:
            self.view.overlay_set_as_bkg_btn.setChecked(False)

    def overlay_color_btn_clicked(self, ind, button):
        previous_color = button.palette().color(1)
        new_color = QtGui.QColorDialog.getColor(previous_color, self.view)
        if new_color.isValid():
            color = str(new_color.name())
        else:
            color = str(previous_color.name())
        self.view.spectrum_view.set_overlay_color(ind, color)
        button.setStyleSheet('background-color:' + color)

    def overlay_scale_sb_changed(self, value):
        cur_ind = self.view.get_selected_overlay_row()
        self.spectrum_data.overlays[cur_ind].scaling = value
        self.view.spectrum_view.update_overlay(self.spectrum_data.overlays[cur_ind], cur_ind)
        if self.view.overlay_set_as_bkg_btn.isChecked():
            self.spectrum_data.notify()

    def overlay_offset_sb_changed(self, value):
        cur_ind = self.view.get_selected_overlay_row()
        self.spectrum_data.overlays[cur_ind].offset = value
        self.view.spectrum_view.update_overlay(self.spectrum_data.overlays[cur_ind], cur_ind)
        if self.view.overlay_set_as_bkg_btn.isChecked():
            self.spectrum_data.notify()

    def overlay_set_as_bkg_btn_clicked(self):
        cur_ind = self.view.get_selected_overlay_row()
        if cur_ind is -1: #no overlay selected
            self.view.overlay_set_as_bkg_btn.setChecked(False)
            return

        if not self.view.overlay_set_as_bkg_btn.isChecked():
            #if the overlay is not currently a background
            self.spectrum_data.bkg_ind = -1
            self.spectrum_data.spectrum.reset_background()
            self.view.overlay_show_cb_set_checked(cur_ind, True)
            self.spectrum_data.notify()
        else:
            #if the overlay is currently the active background
            if self.spectrum_data.bkg_ind is not -1:
                self.view.overlay_show_cb_set_checked(self.spectrum_data.bkg_ind, True)  #show the old overlay again
            self.spectrum_data.bkg_ind = cur_ind
            self.spectrum_data.spectrum.set_background(self.spectrum_data.overlays[cur_ind])
            if self.view.overlay_show_cb_is_checked(cur_ind):
                self.view.spectrum_view.hide_overlay(cur_ind)

                self.view.blockSignals(True)
                self.view.overlay_show_cb_set_checked(cur_ind, False)
                self.view.blockSignals(False)
            self.spectrum_data.notify()

    def qa_set_as_background_btn_click(self):
        self.set_as_overlay(True)
        self.view.overlay_set_as_bkg_btn.setChecked(True)
        self.overlay_set_as_bkg_btn_clicked()


    def overlay_show_cb_state_changed(self, ind, state):
        if state:
            self.view.spectrum_view.show_overlay(ind)
        else:
            self.view.spectrum_view.hide_overlay(ind)

    def rename_overlay(self, ind, name):
        self.view.spectrum_view.rename_overlay(ind, name)