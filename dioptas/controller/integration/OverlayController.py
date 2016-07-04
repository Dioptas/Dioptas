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

import os

import numpy as np
from PyQt4 import QtGui, QtCore

# imports for type hinting in PyCharm -- DO NOT DELETE
from widgets.integration import IntegrationWidget
from model.DioptasModel import DioptasModel

class OverlayController(object):
    """
    IntegrationOverlayController handles all the interaction between the Overlay controls of the integration view and
    the corresponding overlay data in the SpectrumData
    """

    def __init__(self, working_dir, widget, dioptas_model):
        """
        :param working_dir: dictionary of working directories
        :param widget: Reference to IntegrationWidget object
        :param spectrum_model: Reference to SpectrumModel object

        :type widget: IntegrationWidget
        :type dioptas_model: DioptasModel
        """
        self.working_dir = working_dir
        self.widget = widget
        self.model = dioptas_model

        self.overlay_lw_items = []
        self.create_signals()

    def create_signals(self):
        self.connect_click_function(self.widget.overlay_add_btn, self.add_overlay_btn_click_callback)
        self.connect_click_function(self.widget.overlay_del_btn, self.remove_overlay_btn_click_callback)
        self.widget.overlay_clear_btn.clicked.connect(self.clear_overlays_btn_click_callback)

        self.widget.overlay_tw.currentCellChanged.connect(self.overlay_selection_changed)
        self.widget.overlay_color_btn_clicked.connect(self.overlay_color_btn_clicked)
        self.widget.overlay_show_cb_state_changed.connect(self.overlay_show_cb_state_changed)
        self.widget.overlay_name_changed.connect(self.rename_overlay)

        self.widget.overlay_scale_step_txt.editingFinished.connect(self.update_overlay_scale_step)
        self.widget.overlay_offset_step_txt.editingFinished.connect(self.update_overlay_offset_step)
        self.widget.overlay_scale_sb.valueChanged.connect(self.overlay_scale_sb_changed)
        self.widget.overlay_offset_sb.valueChanged.connect(self.overlay_offset_sb_changed)

        self.widget.waterfall_btn.clicked.connect(self.overlay_waterfall_btn_click_callback)
        self.widget.reset_waterfall_btn.clicked.connect(self.model.pattern_model.reset_overlay_offsets)

        self.widget.overlay_set_as_bkg_btn.clicked.connect(self.overlay_set_as_bkg_btn_click_callback)

        # creating the quick-actions signals

        self.connect_click_function(self.widget.qa_set_as_overlay_btn, self.model.pattern_model.add_spectrum_as_overlay)
        self.connect_click_function(self.widget.qa_set_as_background_btn, self.qa_set_as_background_btn_click)

        # spectrum_data signals
        self.model.pattern_model.overlay_removed.connect(self.overlay_removed)
        self.model.pattern_model.overlay_added.connect(self.overlay_added)
        self.model.pattern_model.overlay_changed.connect(self.overlay_changed)
        self.model.pattern_model.overlay_set_as_bkg.connect(self.overlay_set_as_bkg)
        self.model.pattern_model.overlay_unset_as_bkg.connect(self.overlay_unset_as_bkg)

    def connect_click_function(self, emitter, function):
        self.widget.connect(emitter, QtCore.SIGNAL('clicked()'), function)

    def add_overlay_btn_click_callback(self, filename=None):
        """

        :param filename: filepath of an overlay file, if set to None (default value) it will open a QFileDialog to
            select a spectrum file
        """
        if filename is None:
            filenames = QtGui.QFileDialog.getOpenFileNames(self.widget, "Load Overlay(s).", self.working_dir['overlay'])
            if len(filenames):
                for filename in filenames:
                    filename = str(filename)
                    self.model.pattern_model.add_overlay_file(filename)
                self.working_dir['overlay'] = os.path.dirname(str(filenames[0]))
        else:
            self.model.pattern_model.add_overlay_file(filename)
            self.working_dir['overlay'] = os.path.dirname(str(filename))

    def overlay_added(self):
        """
        callback when overlay is added to the SpectrumData
        """
        color = self.widget.pattern_widget.add_overlay(self.model.pattern_model.overlays[-1])
        self.widget.add_overlay(self.model.pattern_model.get_overlay_name(-1),
                                '#%02x%02x%02x' % (int(color[0]), int(color[1]), int(color[2])))

    def remove_overlay_btn_click_callback(self):
        """
        Removes the currently in the overlay table selected overlay from the table, spectrum_data and spectrum_view
        """
        cur_ind = self.widget.get_selected_overlay_row()
        self.model.pattern_model.remove_overlay(cur_ind)

    def overlay_removed(self, ind):
        """
        callback when overlay is removed from SpectrumData
        :param ind: index of overlay removed
        """
        self.widget.remove_overlay(ind)
        self.widget.pattern_widget.remove_overlay(ind)

        # if no more overlays are present the set_as_bkg_btn should be unchecked
        if self.widget.overlay_tw.rowCount() == 0:
            self.widget.overlay_set_as_bkg_btn.setChecked(False)

    def clear_overlays_btn_click_callback(self):
        """
        removes all currently loaded overlays
        """
        while self.widget.overlay_tw.rowCount() > 0:
            self.remove_overlay_btn_click_callback()

    def update_overlay_scale_step(self):
        """
        Sets the step size for scale spinbox from the step text box.
        """
        value = np.float(self.widget.overlay_scale_step_txt.text())
        self.widget.overlay_scale_sb.setSingleStep(value)

    def update_overlay_offset_step(self):
        """
        Sets the step size for the offset spinbox from the offset_step text box.
        """
        value = np.float(self.widget.overlay_offset_step_txt.text())
        self.widget.overlay_offset_sb.setSingleStep(value)

    def overlay_selection_changed(self, row, *args):
        """
        Callback when the selected row in the overlay table is changed. It will update the scale and offset values
        for the newly selected overlay and check whether it is set as background or not and check the
        the set_as_bkg_btn appropriately.
        :param row: selected row in the overlay table
        """
        cur_ind = row
        self.widget.overlay_scale_sb.blockSignals(True)
        self.widget.overlay_offset_sb.blockSignals(True)
        self.widget.overlay_scale_sb.setValue(self.model.pattern_model.overlays[cur_ind].scaling)
        self.widget.overlay_offset_sb.setValue(self.model.pattern_model.overlays[cur_ind].offset)

        self.widget.overlay_scale_sb.blockSignals(False)
        self.widget.overlay_offset_sb.blockSignals(False)
        if self.model.pattern_model.overlay_is_bkg(cur_ind):
            self.widget.overlay_set_as_bkg_btn.setChecked(True)
        else:
            self.widget.overlay_set_as_bkg_btn.setChecked(False)

    def overlay_color_btn_clicked(self, ind, button):
        """
        Callback for the color buttons in the overlay table. Opens up a color dialog. The color of the overlay and
        its respective button will be changed according to the selection
        :param ind: overlay ind
        :param button: button to color
        """
        previous_color = button.palette().color(1)
        new_color = QtGui.QColorDialog.getColor(previous_color, self.widget)
        if new_color.isValid():
            color = str(new_color.name())
        else:
            color = str(previous_color.name())
        self.widget.pattern_widget.set_overlay_color(ind, color)
        button.setStyleSheet('background-color:' + color)

    def overlay_scale_sb_changed(self, value):
        """
        Callback for overlay_scale_sb spinbox.
        :param value: new scale value
        """
        cur_ind = self.widget.get_selected_overlay_row()
        self.model.pattern_model.set_overlay_scaling(cur_ind, value)

    def overlay_offset_sb_changed(self, value):
        """
        Callback gor the overlay_offset_sb spinbox.
        :param value: new value
        """
        cur_ind = self.widget.get_selected_overlay_row()
        self.model.pattern_model.set_overlay_offset(cur_ind, value)

    def overlay_changed(self, ind):
        self.widget.pattern_widget.update_overlay(self.model.pattern_model.overlays[ind], ind)
        cur_ind = self.widget.get_selected_overlay_row()
        if ind == cur_ind:
            self.widget.overlay_offset_sb.blockSignals(True)
            self.widget.overlay_scale_sb.blockSignals(True)
            self.widget.overlay_offset_sb.setValue(self.model.pattern_model.get_overlay_offset(ind))
            self.widget.overlay_scale_sb.setValue(self.model.pattern_model.get_overlay_scaling(ind))
            self.widget.overlay_offset_sb.blockSignals(False)
            self.widget.overlay_scale_sb.blockSignals(False)

    def overlay_waterfall_btn_click_callback(self):
        separation = float(str(self.widget.waterfall_separation_txt.text()))
        self.model.pattern_model.overlay_waterfall(separation)

    def overlay_set_as_bkg_btn_click_callback(self):
        """
        Callback for the overlay_set_as_bkg_btn QPushButton. Will try to either set the currently selected overlay as
        background or unset if it already. Any other overlay which was set before as bkg will
        """
        cur_ind = self.widget.get_selected_overlay_row()
        if cur_ind is -1:  # no overlay selected
            self.widget.overlay_set_as_bkg_btn.setChecked(False)
            return

        if not self.widget.overlay_set_as_bkg_btn.isChecked():
            ## if the overlay is not currently a background
            # it will unset the current background and redisplay it in the spectrum view
            # (which is achieved by checking the cb)
            self.model.pattern_model.unset_overlay_as_bkg()
        else:
            # if the overlay is currently the active background
            self.model.pattern_model.set_overlay_as_bkg(cur_ind)

    def overlay_set_as_bkg(self, ind):
        cur_selected_ind = self.widget.get_selected_overlay_row()
        self.widget.overlay_set_as_bkg_btn.setChecked(ind == cur_selected_ind)
        # hide the original overlay
        if self.widget.overlay_show_cb_is_checked(ind):
            self.widget.overlay_show_cb_set_checked(ind, False)

    def overlay_unset_as_bkg(self, ind):
        self.widget.overlay_show_cb_set_checked(ind, True)
        if self.model.pattern_model.bkg_ind == -1:
            self.widget.overlay_set_as_bkg_btn.setChecked(False)

    def qa_set_as_background_btn_click(self):
        """
        Callback for the quick action button "Set as Background" in image and spectrum tab. It will add the currently
        displayed spectrum as overlay and then set it as background
        """
        self.model.pattern_model.set_spectrum_as_bkg()

    def overlay_show_cb_state_changed(self, ind, state):
        """
        Callback for the checkboxes in the overlay tablewidget. Controls the visibility of the overlay in the spectrum
        view
        :param ind: index of overlay
        :param state: boolean value whether the checkbox was checked or unchecked
        """
        if state:
            self.widget.pattern_widget.show_overlay(ind)
        else:
            self.widget.pattern_widget.hide_overlay(ind)

    def rename_overlay(self, ind, name):
        """
        Callback for changing the name in the overlay tablewidget (by double clicking the name and entering a new one).
        This will update the visible name in the spectrum view
        :param ind: index of overlay for which the name was changed
        :param name: new name
        """
        self.widget.pattern_widget.rename_overlay(ind, name)
