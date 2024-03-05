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

import os

import numpy as np
from qtpy import QtWidgets, QtGui
from ...widgets.UtilityWidgets import open_files_dialog

# imports for type hinting in PyCharm -- DO NOT DELETE
from ...widgets.integration import IntegrationWidget
from ...model.DioptasModel import DioptasModel


class OverlayController(object):
    """
    IntegrationOverlayController handles all the interaction between the Overlay controls of the integration view and
    the corresponding overlay data in the Pattern Model.
    """

    def __init__(self, widget, dioptas_model):
        """
        :param widget: Reference to IntegrationWidget object
        :param pattern_model: Reference to PatternModel object

        :type widget: IntegrationWidget
        :type dioptas_model: DioptasModel
        """
        self.integration_widget = widget
        self.overlay_widget = self.integration_widget.overlay_widget
        self.model = dioptas_model

        self.overlay_lw_items = []
        self.create_signals()

    def create_signals(self):
        self.connect_click_function(self.overlay_widget.add_btn, self.add_overlay_btn_click_callback)
        self.connect_click_function(self.overlay_widget.delete_btn, self.delete_btn_click_callback)
        self.connect_click_function(self.overlay_widget.move_up_btn, self.move_up_overlay_btn_click_callback)
        self.connect_click_function(self.overlay_widget.move_down_btn, self.move_down_overlay_btn_click_callback)
        self.overlay_widget.clear_btn.clicked.connect(self.clear_overlays_btn_click_callback)

        self.overlay_widget.overlay_tw.currentCellChanged.connect(self.overlay_selected)
        self.overlay_widget.color_btn_clicked.connect(self.color_btn_clicked)
        self.overlay_widget.show_cb_state_changed.connect(self.show_cb_state_changed)
        self.overlay_widget.name_changed.connect(self.rename_overlay)

        self.overlay_widget.scale_step_msb.valueChanged.connect(self.update_scale_step)
        self.overlay_widget.offset_step_msb.valueChanged.connect(self.update_overlay_offset_step)
        self.overlay_widget.scale_sb_value_changed.connect(self.scale_sb_changed)
        self.overlay_widget.offset_sb_value_changed.connect(self.offset_sb_changed)

        self.overlay_widget.waterfall_btn.clicked.connect(self.waterfall_btn_click_callback)
        self.overlay_widget.waterfall_reset_btn.clicked.connect(self.model.overlay_model.reset_overlay_offsets)

        self.overlay_widget.set_as_bkg_btn.clicked.connect(self.set_as_bkg_btn_click_callback)

        self.overlay_widget.overlay_tw.horizontalHeader().sectionClicked.connect(self.overlay_tw_header_section_clicked)

        # creating the quick-actions signals

        self.connect_click_function(self.integration_widget.qa_set_as_overlay_btn, self.set_current_pattern_as_overlay)
        self.connect_click_function(self.integration_widget.qa_set_as_background_btn, self.set_current_pattern_as_background)

        # pattern_data signals
        self.model.overlay_model.overlay_removed.connect(self.overlay_removed)
        self.model.overlay_model.overlay_added.connect(self.overlay_added)
        self.model.overlay_model.overlay_changed.connect(self.overlay_changed)

    def connect_click_function(self, emitter, function):
        emitter.clicked.connect(function)

    def add_overlay_btn_click_callback(self):
        """

        """
        filenames = open_files_dialog(self.integration_widget, "Load Overlay(s).",
                                      self.model.working_directories['overlay'])
        if len(filenames):
            for filename in filenames:
                filename = str(filename)
                self.model.overlay_model.add_overlay_file(filename)
            self.model.working_directories['overlay'] = os.path.dirname(str(filenames[0]))

    def overlay_added(self):
        """
        callback when overlay is added to the PatternData
        """
        color = self.integration_widget.pattern_widget.add_overlay(self.model.overlay_model.overlays[-1])
        self.overlay_widget.add_overlay(self.model.overlay_model.overlays[-1].name,
                                               '#%02x%02x%02x' % (int(color[0]), int(color[1]), int(color[2])))

    def delete_btn_click_callback(self):
        """
        Removes the currently in the overlay table selected overlay from the table, pattern_data and pattern_view
        """
        cur_ind = self.overlay_widget.get_selected_overlay_row()
        if cur_ind < 0:
            return
        if self.model.pattern_model.background_pattern == self.model.overlay_model.overlays[cur_ind]:
            self.model.pattern_model.background_pattern = None
        self.model.overlay_model.remove_overlay(cur_ind)

    def overlay_removed(self, ind):
        """
        callback when overlay is removed from PatternData
        :param ind: index of overlay removed
        """
        self.integration_widget.pattern_widget.remove_overlay(ind)
        self.overlay_widget.remove_overlay(ind)

        # if no more overlays are present the set_as_bkg_btn should be unchecked
        if self.overlay_widget.overlay_tw.rowCount() == 0:
            self.overlay_widget.set_as_bkg_btn.setChecked(False)

    def move_up_overlay_btn_click_callback(self):
        cur_ind = self.overlay_widget.get_selected_overlay_row()
        if cur_ind < 1:
            return
        new_ind = cur_ind - 1

        self.overlay_widget.move_overlay_up(cur_ind)
        self.model.overlay_model.overlays.insert(new_ind, self.model.overlay_model.overlays.pop(cur_ind))
        self.integration_widget.pattern_widget.move_overlay_up(cur_ind)

        if self.overlay_widget.show_cbs[cur_ind].isChecked():
            self.integration_widget.pattern_widget.legend.showItem(cur_ind + 1)
        else:
            self.integration_widget.pattern_widget.legend.hideItem(cur_ind + 1)

        if self.overlay_widget.show_cbs[new_ind].isChecked():
            self.integration_widget.pattern_widget.legend.showItem(cur_ind)
        else:
            self.integration_widget.pattern_widget.legend.hideItem(cur_ind)

    def move_down_overlay_btn_click_callback(self):
        cur_ind = self.overlay_widget.get_selected_overlay_row()
        if cur_ind < 0 or cur_ind >= self.integration_widget.overlay_tw.rowCount() - 1:
            return

        self.overlay_widget.move_overlay_down(cur_ind)
        self.model.overlay_model.overlays.insert(cur_ind + 1, self.model.overlay_model.overlays.pop(cur_ind))
        self.integration_widget.pattern_widget.move_overlay_down(cur_ind)

        if self.overlay_widget.show_cbs[cur_ind].isChecked():
            self.integration_widget.pattern_widget.legend.showItem(cur_ind + 1)
        else:
            self.integration_widget.pattern_widget.legend.hideItem(cur_ind + 1)

        if self.overlay_widget.show_cbs[cur_ind + 1].isChecked():
            self.integration_widget.pattern_widget.legend.showItem(cur_ind + 2)
        else:
            self.integration_widget.pattern_widget.legend.hideItem(cur_ind + 2)

    def clear_overlays_btn_click_callback(self):
        """
        removes all currently loaded overlays
        """
        while self.integration_widget.overlay_tw.rowCount() > 0:
            self.delete_btn_click_callback()

    def update_scale_step(self):
        """
        Sets the step size for the scale spinboxes from the step text box.
        """
        value = self.overlay_widget.scale_step_msb.value()
        for scale_sb in self.overlay_widget.scale_sbs:
            scale_sb.setSingleStep(value)

    def update_overlay_offset_step(self):
        """
        Sets the step size for the offset spinbox from the offset_step text box.
        """
        value = self.overlay_widget.offset_step_msb.value()
        for offset_sb in self.overlay_widget.offset_sbs:
            offset_sb.setSingleStep(value)

    def overlay_selected(self, row, *args):
        """
        Callback when the selected row in the overlay table is changed. It will update the scale and offset values
        for the newly selected overlay and check whether it is set as background or not and check the
        the set_as_bkg_btn appropriately.
        :param row: selected row in the overlay table
        """
        if self.model.pattern_model.background_pattern == self.model.overlay_model.overlays[row]:
            self.overlay_widget.set_as_bkg_btn.setChecked(True)
        else:
            self.overlay_widget.set_as_bkg_btn.setChecked(False)

    def color_btn_clicked(self, ind, button):
        """
        Callback for the color buttons in the overlay table. Opens up a color dialog. The color of the overlay and
        its respective button will be changed according to the selection
        :param ind: overlay ind
        :param button: button to color
        """
        previous_color = button.palette().color(QtGui.QPalette.Button)
        new_color = QtWidgets.QColorDialog.getColor(previous_color, self.integration_widget)
        if new_color.isValid():
            color = str(new_color.name())
        else:
            color = str(previous_color.name())
        self.integration_widget.pattern_widget.set_overlay_color(ind, color)
        button.setStyleSheet(f"background-color: {color}; margin: 2px")

    def scale_sb_changed(self, overlay_ind, new_value):
        """
        Callback for scale_sb spinbox.
        :param overlay_ind: index of overlay
        :param new_value: new scale value
        """
        self.model.overlay_model.set_overlay_scaling(overlay_ind, new_value)
        if self.model.overlay_model.overlays[overlay_ind] == self.model.pattern_model.background_pattern:
            self.model.pattern_changed.emit()

    def offset_sb_changed(self, overlay_ind, new_value):
        """
        Callback gor the offset_sb spinbox.
        :param overlay_ind: index of overlay
        :param new_value: new value
        """
        self.model.overlay_model.set_overlay_offset(overlay_ind, new_value)
        if self.model.overlay_model.overlays[overlay_ind] == self.model.pattern_model.background_pattern:
            self.model.pattern_changed.emit()

    def overlay_changed(self, ind):
        self.integration_widget.pattern_widget.update_overlay(self.model.overlay_model.overlays[ind], ind)
        self.overlay_widget.offset_sbs[ind].blockSignals(True)
        self.overlay_widget.scale_sbs[ind].blockSignals(True)
        self.overlay_widget.offset_sbs[ind].setValue(self.model.overlay_model.get_overlay_offset(ind))
        self.overlay_widget.scale_sbs[ind].setValue(self.model.overlay_model.get_overlay_scaling(ind))
        self.overlay_widget.offset_sbs[ind].blockSignals(False)
        self.overlay_widget.scale_sbs[ind].blockSignals(False)

    def waterfall_btn_click_callback(self):
        separation = self.overlay_widget.waterfall_separation_msb.value()
        self.model.overlay_model.overlay_waterfall(separation)

    def set_as_bkg_btn_click_callback(self):
        """
        Callback for the set_as_bkg_btn QPushButton. Will try to either set the currently selected overlay as
        background or unset if it already. Any other overlay which was set before as bkg will
        """
        cur_ind = self.overlay_widget.get_selected_overlay_row()
        if cur_ind == -1:  # no overlay selected
            self.overlay_widget.set_as_bkg_btn.setChecked(False)
            return

        if not self.overlay_widget.set_as_bkg_btn.isChecked():
            ## if the overlay is not currently a background
            # it will unset the current background and redisplay
            self.model.pattern_model.background_pattern = None
        else:
            # if the overlay is currently the active background
            self.model.pattern_model.background_pattern = self.model.overlay_model.overlays[cur_ind]
            if self.overlay_widget.show_cb_is_checked(cur_ind):
                self.overlay_widget.show_cb_set_checked(cur_ind, False)

    def set_current_pattern_as_overlay(self):
        self.model.overlay_model.add_overlay_pattern(self.model.pattern)

    def set_current_pattern_as_background(self):
        self.model.overlay_model.add_overlay_pattern(self.model.pattern)
        self.model.pattern_model.background_pattern = self.model.overlay_model.overlays[-1]

        self.overlay_widget.set_as_bkg_btn.setChecked(True)
        self.overlay_widget.show_cb_set_checked(-1, False)

    def overlay_set_as_bkg(self, ind):
        cur_selected_ind = self.overlay_widget.get_selected_overlay_row()
        self.overlay_widget.set_as_bkg_btn.setChecked(ind == cur_selected_ind)
        # hide the original overlay
        if self.overlay_widget.show_cb_is_checked(ind):
            self.overlay_widget.show_cb_set_checked(ind, False)

    def overlay_unset_as_bkg(self, ind):
        self.overlay_widget.show_cb_set_checked(ind, True)
        if self.model.pattern_model.bkg_ind == -1:
            self.overlay_widget.set_as_bkg_btn.setChecked(False)

    def show_cb_state_changed(self, ind, state):
        """
        Callback for the checkboxes in the overlay tablewidget. Controls the visibility of the overlay in the pattern
        view
        :param ind: index of overlay
        :param state: boolean value whether the checkbox was checked or unchecked
        """
        if state:
            self.integration_widget.pattern_widget.show_overlay(ind)
        else:
            self.integration_widget.pattern_widget.hide_overlay(ind)

    def rename_overlay(self, ind, name):
        """
        Callback for changing the name in the overlay tablewidget (by double clicking the name and entering a new one).
        This will update the visible name in the pattern view
        :param ind: index of overlay for which the name was changed
        :param name: new name
        """
        self.integration_widget.pattern_widget.rename_overlay(ind, name)
        self.model.overlay_model.overlays[ind].name = name

    def overlay_tw_header_section_clicked(self, ind):
        if ind != 0:
            return

        current_checkbox_state = False
        # check whether any checkbox is checked, if one is true current_checkbox_state will be True too
        for cb in self.overlay_widget.show_cbs:
            current_checkbox_state = current_checkbox_state or cb.isChecked()

        # assign the the opposite to all checkboxes
        for cb in self.overlay_widget.show_cbs:
            cb.setChecked(not current_checkbox_state)