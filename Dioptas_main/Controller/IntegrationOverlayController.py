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

__author__ = 'Clemens Prescher'
import os

from PyQt4 import QtGui, QtCore
import numpy as np

from Data.HelperModule import get_base_name


# imports for type hinting in PyCharm -- DO NOT DELETE
from Views.IntegrationView import IntegrationView
from Data.SpectrumData import SpectrumData


class IntegrationOverlayController(object):
    """
    IntegrationOverlayController handles all the interaction between the Overlay controls of the integration view and
    the corresponding overlay data in the SpectrumData
    """

    def __init__(self, working_dir, view, spectrum_data):
        """
        :param working_dir: dictionary of working directories
        :param view: Reference to IntegrationView object
        :param spectrum_data: Reference to SpectrumData object

        :type view: IntegrationView
        :type spectrum_data: SpectrumData
        """
        self.working_dir = working_dir
        self.view = view
        self.spectrum_data = spectrum_data
        self.overlay_lw_items = []
        self.create_signals()

    def create_signals(self):
        self.connect_click_function(self.view.overlay_add_btn, self.add_overlay_btn_click_callback)
        self.connect_click_function(self.view.overlay_del_btn, self.remove_overlay_btn_click_callback)
        self.view.overlay_clear_btn.clicked.connect(self.clear_overlays_btn_click_callback)

        self.view.overlay_tw.currentCellChanged.connect(self.overlay_selection_changed)
        self.view.overlay_color_btn_clicked.connect(self.overlay_color_btn_clicked)
        self.view.overlay_show_cb_state_changed.connect(self.overlay_show_cb_state_changed)
        self.view.overlay_name_changed.connect(self.rename_overlay)

        self.view.overlay_scale_step_txt.editingFinished.connect(self.update_overlay_scale_step)
        self.view.overlay_offset_step_txt.editingFinished.connect(self.update_overlay_offset_step)
        self.view.overlay_scale_sb.valueChanged.connect(self.overlay_scale_sb_changed)
        self.view.overlay_offset_sb.valueChanged.connect(self.overlay_offset_sb_changed)

        self.view.overlay_set_as_bkg_btn.clicked.connect(self.overlay_set_as_bkg_btn_clicked)

        # creating the quick-actions signals

        self.connect_click_function(self.view.qa_img_set_as_overlay_btn,
                                    self.spectrum_data.add_spectrum_as_overlay)
        self.connect_click_function(self.view.qa_spectrum_set_as_overlay_btn,
                                    self.spectrum_data.add_spectrum_as_overlay)

        self.connect_click_function(self.view.qa_img_set_as_background_btn, self.qa_set_as_background_btn_click)
        self.connect_click_function(self.view.qa_spectrum_set_as_background_btn, self.qa_set_as_background_btn_click)

        # spectrum_data signals
        self.spectrum_data.overlay_removed.connect(self.overlay_removed)
        self.spectrum_data.overlay_added.connect(self.overlay_added)

    def connect_click_function(self, emitter, function):
        self.view.connect(emitter, QtCore.SIGNAL('clicked()'), function)

    def add_overlay_btn_click_callback(self, filename=None):
        """

        :param filename: filepath of an overlay file, if set to None (default value) it will open a QFileDialog to
            select a spectrum file
        """
        if filename is None:
            filenames = QtGui.QFileDialog.getOpenFileNames(self.view, "Load Overlay(s).", self.working_dir['overlay'])
            if len(filenames):
                for filename in filenames:
                    filename = str(filename)
                    self.spectrum_data.add_overlay_file(filename)
                self.working_dir['overlay'] = os.path.dirname(str(filenames[0]))
        else:
            self.spectrum_data.add_overlay_file(filename)
            self.working_dir['overlay'] = os.path.dirname(str(filename))

    def overlay_added(self):
        color = self.view.spectrum_view.add_overlay(self.spectrum_data.overlays[-1])
        self.view.add_overlay(self.spectrum_data.get_overlay_name(-1),
                              '#%02x%02x%02x' % (color[0], color[1], color[2]))

    def remove_overlay_btn_click_callback(self):
        """
        Removes the currently in the overlay table selected overlay from the table, spectrum_data and spectrum_view
        """
        cur_ind = self.view.get_selected_overlay_row()
        self.spectrum_data.remove_overlay(cur_ind)

    def overlay_removed(self, ind):
        self.view.del_overlay(ind)
        self.view.spectrum_view.del_overlay(ind)

    def clear_overlays_btn_click_callback(self):
        """
        removes all currently loaded overlays
        """
        while self.view.overlay_tw.rowCount() > 0:
            self.remove_overlay_btn_click_callback()

    def update_overlay_scale_step(self):
        """
        Sets the step size for scale spinbox from the step text box.
        """
        value = np.float(self.view.overlay_scale_step_txt.text())
        self.view.overlay_scale_sb.setSingleStep(value)

    def update_overlay_offset_step(self):
        """
        Sets the step size for the offset spinbox from the offset_step text box.
        """
        value = np.float(self.view.overlay_offset_step_txt.text())
        self.view.overlay_offset_sb.setSingleStep(value)

    def overlay_selection_changed(self, row, *args):
        """
        Callback when the selected row in the overlay table is changed. It will update the scale and offset values
        for the newly selected overlay and check whether it is set as background or not and check the
        the set_as_bkg_btn appropriately.
        :param row: selected row in the overlay table
        """
        cur_ind = row
        self.view.overlay_scale_sb.blockSignals(True)
        self.view.overlay_offset_sb.blockSignals(True)
        self.view.overlay_scale_sb.setValue(self.spectrum_data.overlays[cur_ind].scaling)
        self.view.overlay_offset_sb.setValue(self.spectrum_data.overlays[cur_ind].offset)

        self.view.overlay_scale_sb.blockSignals(False)
        self.view.overlay_offset_sb.blockSignals(False)
        if self.spectrum_data.overlay_is_bkg(cur_ind):
            self.view.overlay_set_as_bkg_btn.setChecked(True)
        else:
            self.view.overlay_set_as_bkg_btn.setChecked(False)

    def overlay_color_btn_clicked(self, ind, button):
        """
        Callback for the color buttons in the overlay table. Opens up a color dialog. The color of the overlay and
        its respective button will be changed according to the selection
        :param ind: overlay ind
        :param button: button to color
        """
        previous_color = button.palette().color(1)
        new_color = QtGui.QColorDialog.getColor(previous_color, self.view)
        if new_color.isValid():
            color = str(new_color.name())
        else:
            color = str(previous_color.name())
        self.view.spectrum_view.set_overlay_color(ind, color)
        button.setStyleSheet('background-color:' + color)

    def overlay_scale_sb_changed(self, value):
        """
        Callback for overlay_scale_sb spinbox.
        :param value: new scale value
        """
        cur_ind = self.view.get_selected_overlay_row()
        self.spectrum_data.set_overlay_scaling(cur_ind, value)
        self.view.spectrum_view.update_overlay(self.spectrum_data.overlays[cur_ind], cur_ind)

    def overlay_offset_sb_changed(self, value):
        """
        Callback gor the overlay_offset_sb spinbox.
        :param value: new value
        """
        cur_ind = self.view.get_selected_overlay_row()
        self.spectrum_data.set_overlay_offset(cur_ind, value)
        self.view.spectrum_view.update_overlay(self.spectrum_data.overlays[cur_ind], cur_ind)

    def overlay_set_as_bkg_btn_clicked(self):
        """
        Callback for the overlay_set_as_bkg_btn QPushButton. Will try to either set the currently selected overlay as
        background or unset if it already. Any other overlay which was set before as bkg will
        """
        cur_ind = self.view.get_selected_overlay_row()
        if cur_ind is -1:  # no overlay selected
            self.view.overlay_set_as_bkg_btn.setChecked(False)
            return

        if not self.view.overlay_set_as_bkg_btn.isChecked():
            ## if the overlay is not currently a background
            # it will unset the current background and redisplay it in the spectrum view
            # (which is achieved by checking the cb)
            self.spectrum_data.unset_overlay_as_bkg()
            self.view.overlay_show_cb_set_checked(cur_ind, True)
        else:
            # if the overlay is currently the active background

            #show the old used background (if any) again
            if self.spectrum_data.bkg_ind is not -1:
                self.view.overlay_show_cb_set_checked(self.spectrum_data.bkg_ind, True)

            self.spectrum_data.set_overlay_as_bkg(cur_ind)
            # hide the original overlay
            if self.view.overlay_show_cb_is_checked(cur_ind):
                self.view.overlay_show_cb_set_checked(cur_ind, False)
            self.spectrum_data.spectrum_changed.emit()

    def qa_set_as_background_btn_click(self):
        """
        Callback for the quick action button "Set as Background" in image and spectrum tab. It will add the currently
        displayed spectrum as overlay and then set it as background
        :return:
        """
        self.spectrum_data.add_spectrum_as_overlay()
        self.view.overlay_set_as_bkg_btn.setChecked(True)
        self.overlay_set_as_bkg_btn_clicked()


    def overlay_show_cb_state_changed(self, ind, state):
        """
        Callback for the checkboxes in the overlay tablewidget. Controls the visibility of the overlay in the spectrum
        view
        :param ind: index of overlay
        :param state: boolean value whether the checkbox was checked or unchecked
        """
        if state:
            self.view.spectrum_view.show_overlay(ind)
        else:
            self.view.spectrum_view.hide_overlay(ind)

    def rename_overlay(self, ind, name):
        """
        Callback for changing the name in the overlay tablewidget (by double clicking the name and entering a new one).
        This will update the visible name in the spectrum view
        :param ind: index of overlay for which the name was changed
        :param name: new name
        """
        self.view.spectrum_view.rename_overlay(ind, name)