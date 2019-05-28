# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
# Principal author: Clemens Prescher (clemens.prescher@gmail.com)
# Copyright (C) 2014-2019 GSECARS, University of Chicago, USA
# Copyright (C) 2015-2018 Institute for Geology and Mineralogy, University of Cologne, Germany
# Copyright (C) 2019 DESY, Hamburg, Germany
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
from qtpy import QtWidgets, QtCore

from ...widgets.UtilityWidgets import open_file_dialog, save_file_dialog

# imports for type hinting in PyCharm -- DO NOT DELETE
from ...widgets.integration import IntegrationWidget
from ...model.DioptasModel import DioptasModel
from ...model.ImgModel import BackgroundDimensionWrongException


class BackgroundController(object):
    """
    The IntegrationImageController manages the Image actions in the Integration Window. It connects the file actions, as
    well as interaction with the image_view.
    """

    def __init__(self, widget, dioptas_model):
        """
        :param widget: IntegrationWidget
        :param dioptas_model: DioptasModel reference

        :type widget: IntegrationWidget
        :type dioptas_model: DioptasModel
        """
        self.widget = widget
        self.background_widget = widget.integration_control_widget.background_control_widget
        self.model = dioptas_model

        self.model.configuration_selected.connect(self.update_bkg_image_widgets)
        self.model.configuration_selected.connect(self.update_auto_pattern_bkg_widgets)

        self.create_image_background_signals()
        self.create_pattern_background_signals()

    def create_image_background_signals(self):
        self.connect_click_function(self.widget.bkg_image_load_btn, self.load_background_image)
        self.connect_click_function(self.widget.bkg_image_delete_btn, self.remove_background_image)

        self.widget.bkg_image_scale_step_msb.editingFinished.connect(self.update_bkg_image_scale_step)
        self.widget.bkg_image_offset_step_msb.editingFinished.connect(self.update_bkg_image_offset_step)
        self.widget.bkg_image_scale_sb.valueChanged.connect(self.background_img_scale_changed)
        self.widget.bkg_image_offset_sb.valueChanged.connect(self.background_img_offset_changed)

        self.model.img_changed.connect(self.update_background_image_filename)

    def create_pattern_background_signals(self):
        self.widget.bkg_pattern_gb.toggled.connect(self.bkg_pattern_gb_toggled_callback)
        self.widget.qa_bkg_pattern_btn.toggled.connect(self.bkg_pattern_gb_toggled_callback)

        self.widget.bkg_pattern_iterations_sb.valueChanged.connect(self.bkg_pattern_parameters_changed)
        self.widget.bkg_pattern_poly_order_sb.valueChanged.connect(self.bkg_pattern_parameters_changed)
        self.widget.bkg_pattern_smooth_width_sb.valueChanged.connect(self.bkg_pattern_parameters_changed)
        self.widget.bkg_pattern_x_min_txt.editingFinished.connect(self.bkg_pattern_parameters_changed)
        self.widget.bkg_pattern_x_max_txt.editingFinished.connect(self.bkg_pattern_parameters_changed)

        self.widget.bkg_pattern_inspect_btn.toggled.connect(self.bkg_pattern_inspect_btn_toggled_callback)
        self.widget.bkg_pattern_save_btn.clicked.connect(self.bkg_pattern_save_btn_callback)
        self.widget.bkg_pattern_as_overlay_btn.clicked.connect(self.bkg_pattern_as_overlay_btn_callback)
        self.widget.qa_bkg_pattern_inspect_btn.toggled.connect(self.bkg_pattern_inspect_btn_toggled_callback)

        self.model.pattern_changed.connect(self.update_bkg_gui_parameters)

    def connect_click_function(self, emitter, function):
        """
        Small helper function for the button-click connection.
        """
        emitter.clicked.connect(function)

    def load_background_image(self):
        filename = open_file_dialog(
            self.widget, "Load an image background file",
            self.model.working_directories['image'])

        if filename is not None and filename is not '':
            self.widget.bkg_image_filename_lbl.setText("Loading File")
            try:
                self.model.img_model.load_background(filename)
                self.widget.img_show_background_subtracted_btn.setVisible(True)
            except BackgroundDimensionWrongException:
                QtWidgets.QMessageBox.critical(self.widget, 'ERROR',
                                               'Background image does not have the same dimensions as original Image. ' + \
                                               'Resetting Background Image.')
                self.widget.bkg_image_filename_lbl.setText("None")

    def remove_background_image(self):
        self.widget.bkg_image_filename_lbl.setText("None")
        self.widget.bkg_name_lbl.setText('')
        self.widget.img_show_background_subtracted_btn.setVisible(False)
        self.model.img_model.reset_background()

    def update_bkg_image_scale_step(self):
        self.widget.bkg_image_scale_sb.setSingleStep(self.widget.bkg_image_scale_step_msb.value())

    def update_bkg_image_offset_step(self):
        self.widget.bkg_image_offset_sb.setSingleStep(self.widget.bkg_image_offset_step_msb.value())

    def update_background_image_filename(self):
        if self.model.img_model.has_background():
            self.widget.bkg_image_filename_lbl.setText(os.path.basename(self.model.img_model.background_filename))
            self.widget.bkg_name_lbl.setText(
                'Bkg image: {0}'.format(os.path.basename(self.model.img_model.background_filename)))
        else:
            self.widget.bkg_image_filename_lbl.setText('None')
            self.widget.bkg_name_lbl.setText('')

    def background_img_scale_changed(self):
        self.model.img_model.background_scaling = self.widget.bkg_image_scale_sb.value()

    def background_img_offset_changed(self):
        self.model.img_model.background_offset = self.widget.bkg_image_offset_sb.value()

    def bkg_pattern_gb_toggled_callback(self, is_checked):
        self.widget.bkg_pattern_gb.blockSignals(True)
        self.widget.qa_bkg_pattern_btn.blockSignals(True)
        self.widget.bkg_pattern_gb.setChecked(is_checked)
        self.widget.qa_bkg_pattern_btn.setChecked(is_checked)
        self.widget.bkg_pattern_gb.blockSignals(False)
        self.widget.qa_bkg_pattern_btn.blockSignals(False)
        self.widget.qa_bkg_pattern_inspect_btn.setVisible(is_checked)

        if is_checked:
            bkg_pattern_parameters = self.background_widget.get_bkg_pattern_parameters()
            bkg_pattern_roi = self.background_widget.get_bkg_pattern_roi()
            self.model.pattern_model.set_auto_background_subtraction(bkg_pattern_parameters, bkg_pattern_roi)
        else:
            self.widget.bkg_pattern_inspect_btn.setChecked(False)
            self.widget.qa_bkg_pattern_inspect_btn.setChecked(False)
            self.widget.pattern_widget.hide_bkg_roi()
            self.model.pattern_model.unset_auto_background_subtraction()

    def bkg_pattern_parameters_changed(self):
        bkg_pattern_parameters = self.background_widget.get_bkg_pattern_parameters()
        bkg_pattern_roi = self.background_widget.get_bkg_pattern_roi()
        if self.model.pattern_model.pattern.auto_background_subtraction:
            self.model.pattern_model.set_auto_background_subtraction(bkg_pattern_parameters, bkg_pattern_roi)

    def update_bkg_gui_parameters(self):
        if self.model.pattern_model.pattern.auto_background_subtraction:
            self.background_widget.set_bkg_pattern_parameters(self.model.pattern.auto_background_subtraction_parameters)
            self.background_widget.set_bkg_pattern_roi(self.model.pattern.auto_background_subtraction_roi)

            self.widget.pattern_widget.bkg_roi.blockSignals(True)
            self.widget.pattern_widget.set_bkg_roi(
                *self.model.pattern_model.pattern.auto_background_subtraction_roi)
            self.widget.pattern_widget.bkg_roi.blockSignals(False)

    def bkg_pattern_inspect_btn_toggled_callback(self, checked):
        self.widget.bkg_pattern_inspect_btn.blockSignals(True)
        self.widget.qa_bkg_pattern_inspect_btn.blockSignals(True)
        self.widget.bkg_pattern_inspect_btn.setChecked(checked)
        self.widget.qa_bkg_pattern_inspect_btn.setChecked(checked)
        self.widget.bkg_pattern_inspect_btn.blockSignals(False)
        self.widget.qa_bkg_pattern_inspect_btn.blockSignals(False)

        if checked:
            self.widget.pattern_widget.show_bkg_roi()
            self.widget.pattern_widget.bkg_roi.sigRegionChanged.connect(
                self.bkg_pattern_linear_region_callback
            )
            self.widget.bkg_pattern_x_min_txt.editingFinished.connect(self.update_bkg_pattern_linear_region)
            self.widget.bkg_pattern_x_max_txt.editingFinished.connect(self.update_bkg_pattern_linear_region)
        else:
            self.widget.pattern_widget.hide_bkg_roi()
            self.widget.pattern_widget.bkg_roi.sigRegionChanged.disconnect(
                self.bkg_pattern_linear_region_callback
            )

            self.widget.bkg_pattern_x_min_txt.editingFinished.disconnect(self.update_bkg_pattern_linear_region)
            self.widget.bkg_pattern_x_max_txt.editingFinished.disconnect(self.update_bkg_pattern_linear_region)
        self.model.pattern_changed.emit()

    def bkg_pattern_save_btn_callback(self):
        img_filename, _ = os.path.splitext(os.path.basename(self.model.img_model.filename))
        filename = save_file_dialog(
            self.widget, "Save Fit Background as Pattern Data.",
            os.path.join(self.model.working_directories['pattern'],
                         img_filename + '.xy'), ('Data (*.xy);;Data (*.chi);;Data (*.dat);;GSAS (*.fxye)'))

        if filename is not '':
            self.model.current_configuration.save_background_pattern(filename)

    def bkg_pattern_as_overlay_btn_callback(self):
        self.model.overlay_model.add_overlay_pattern(self.model.pattern.auto_background_pattern)

    def bkg_pattern_linear_region_callback(self):
        x_min, x_max = self.widget.pattern_widget.get_bkg_roi()
        self.widget.bkg_pattern_x_min_txt.setText('{:.3f}'.format(x_min))
        self.widget.bkg_pattern_x_max_txt.setText('{:.3f}'.format(x_max))
        self.bkg_pattern_parameters_changed()

    def update_bkg_pattern_linear_region(self):
        self.widget.pattern_widget.bkg_roi.blockSignals(True)
        self.widget.pattern_widget.set_bkg_roi(*self.widget.get_bkg_pattern_roi())
        self.widget.pattern_widget.bkg_roi.blockSignals(False)

    def update_bkg_image_widgets(self):
        self.update_background_image_filename()
        self.widget.bkg_image_offset_sb.setValue(self.model.img_model.background_offset)
        self.widget.bkg_image_scale_sb.setValue(self.model.img_model.background_scaling)
        self.widget.img_show_background_subtracted_btn.setVisible(self.model.img_model.has_background())

    def update_auto_pattern_bkg_widgets(self):
        # set the state of the toggles:
        self.widget.bkg_pattern_gb.blockSignals(True)
        self.widget.qa_bkg_pattern_btn.blockSignals(True)
        self.widget.bkg_pattern_gb.setChecked(self.model.pattern.auto_background_subtraction)
        self.widget.qa_bkg_pattern_inspect_btn.setVisible(self.model.pattern.auto_background_subtraction)
        self.widget.qa_bkg_pattern_btn.setChecked(self.model.pattern.auto_background_subtraction)
        self.widget.bkg_pattern_gb.blockSignals(False)
        self.widget.qa_bkg_pattern_btn.blockSignals(False)

        self.update_bkg_gui_parameters()
        self.widget.qa_bkg_pattern_inspect_btn.setChecked(False)
        self.widget.bkg_pattern_inspect_btn.setChecked(False)
