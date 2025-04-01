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
from qtpy import QtWidgets
from xypattern.auto_background import SmoothBrucknerBackground

from ...widgets.UtilityWidgets import open_file_dialog, save_file_dialog
from ...widgets.integration import IntegrationWidget
from ...model.DioptasModel import DioptasModel
from ...model.ImgModel import BackgroundDimensionWrongException


class BackgroundController(object):
    """
    The IntegrationImageController manages the Image actions in the Integration Window. It connects the file actions, as
    well as interaction with the image_view.
    """

    def __init__(self, widget: IntegrationWidget, dioptas_model: DioptasModel):
        """
        :param widget: IntegrationWidget
        :param dioptas_model: DioptasModel reference
        """
        self.widget = widget
        self.background_widget = (
            widget.integration_control_widget.background_control_widget
        )
        self.model = dioptas_model

        self.model.configuration_selected.connect(self.update_bkg_image_widgets)
        self.model.configuration_selected.connect(self.update_auto_pattern_bkg_widgets)

        self.create_image_background_signals()
        self.create_pattern_background_signals()

    def create_image_background_signals(self):
        self.connect_click_function(
            self.widget.bkg_image_load_btn, self.load_background_image
        )
        self.connect_click_function(
            self.widget.bkg_image_delete_btn, self.remove_background_image
        )

        self.widget.bkg_image_scale_step_msb.editingFinished.connect(
            self.update_bkg_image_scale_step
        )
        self.widget.bkg_image_offset_step_msb.editingFinished.connect(
            self.update_bkg_image_offset_step
        )
        self.widget.bkg_image_scale_sb.valueChanged.connect(
            self.background_img_scale_changed
        )
        self.widget.bkg_image_offset_sb.valueChanged.connect(
            self.background_img_offset_changed
        )

        self.model.img_changed.connect(self.update_background_image_filename)

    def create_pattern_background_signals(self):
        self.widget.bkg_pattern_gb.toggled.connect(self.bkg_pattern_gb_toggled_callback)
        self.widget.qa_bkg_pattern_btn.toggled.connect(
            self.bkg_pattern_gb_toggled_callback
        )

        self.widget.bkg_pattern_iterations_sb.valueChanged.connect(
            self.bkg_pattern_parameters_changed
        )
        self.widget.bkg_pattern_poly_order_sb.valueChanged.connect(
            self.bkg_pattern_parameters_changed
        )
        self.widget.bkg_pattern_smooth_width_sb.valueChanged.connect(
            self.bkg_pattern_parameters_changed
        )
        self.widget.bkg_pattern_x_min_txt.editingFinished.connect(
            self.bkg_pattern_parameters_changed
        )
        self.widget.bkg_pattern_x_max_txt.editingFinished.connect(
            self.bkg_pattern_parameters_changed
        )

        self.widget.bkg_pattern_inspect_btn.toggled.connect(
            self.bkg_pattern_inspect_btn_toggled_callback
        )
        self.widget.bkg_pattern_save_btn.clicked.connect(
            self.bkg_pattern_save_btn_callback
        )
        self.widget.bkg_pattern_as_overlay_btn.clicked.connect(
            self.bkg_pattern_as_overlay_btn_callback
        )
        self.widget.qa_bkg_pattern_inspect_btn.toggled.connect(
            self.bkg_pattern_inspect_btn_toggled_callback
        )

        self.model.pattern_changed.connect(self.update_bkg_gui_parameters)

    def connect_click_function(self, emitter, function):
        """
        Small helper function for the button-click connection.
        """
        emitter.clicked.connect(function)

    def load_background_image(self):
        filename = open_file_dialog(
            self.widget,
            "Load an image background file",
            self.model.working_directories["image"],
        )

        if filename is not None and filename != "":
            self.widget.bkg_image_filename_lbl.setText("Loading File")
            try:
                self.model.img_model.load_background(filename)
                self.widget.img_show_background_subtracted_btn.setVisible(True)
            except BackgroundDimensionWrongException:
                QtWidgets.QMessageBox.critical(
                    self.widget,
                    "ERROR",
                    "Background image does not have the same dimensions as original Image. "
                    + "Resetting Background Image.",
                )
                self.widget.bkg_image_filename_lbl.setText("None")

    def remove_background_image(self):
        self.widget.bkg_image_filename_lbl.setText("None")
        self.widget.bkg_name_lbl.setText("")
        self.widget.img_show_background_subtracted_btn.setVisible(False)
        self.model.img_model.reset_background()

    def update_bkg_image_scale_step(self):
        self.widget.bkg_image_scale_sb.setSingleStep(
            self.widget.bkg_image_scale_step_msb.value()
        )

    def update_bkg_image_offset_step(self):
        self.widget.bkg_image_offset_sb.setSingleStep(
            self.widget.bkg_image_offset_step_msb.value()
        )

    def update_background_image_filename(self):
        if self.model.img_model.has_background():
            self.widget.bkg_image_filename_lbl.setText(
                os.path.basename(self.model.img_model.background_filename)
            )
            self.widget.bkg_name_lbl.setText(
                "Bkg image: {0}".format(
                    os.path.basename(self.model.img_model.background_filename)
                )
            )
        else:
            self.widget.bkg_image_filename_lbl.setText("None")
            self.widget.bkg_name_lbl.setText("")

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
            self.model.pattern_model.set_auto_background_subtraction(
                bkg_pattern_parameters, bkg_pattern_roi
            )
        else:
            self.widget.bkg_pattern_inspect_btn.setChecked(False)
            self.widget.qa_bkg_pattern_inspect_btn.setChecked(False)
            self.widget.pattern_widget.hide_bkg_roi()
            self.model.pattern_model.unset_auto_background_subtraction()

    def bkg_pattern_parameters_changed(self):
        bkg_pattern_parameters = self.background_widget.get_bkg_pattern_parameters()
        bkg_pattern_roi = self.background_widget.get_bkg_pattern_roi()
        if self.model.pattern_model.pattern.auto_bkg is not None:
            self.model.pattern_model.set_auto_background_subtraction(
                bkg_pattern_parameters, bkg_pattern_roi
            )

    def update_bkg_gui_parameters(self):
        pattern = self.model.pattern_model.pattern
        auto_bkg = pattern.auto_bkg
        if auto_bkg is None:
            return

        assert type(auto_bkg) == SmoothBrucknerBackground
        self.background_widget.set_bkg_pattern_parameters(
            [auto_bkg.smooth_width, auto_bkg.iterations, auto_bkg.cheb_order]
        )
        self.background_widget.set_bkg_pattern_roi(pattern.auto_bkg_roi)

        self.widget.pattern_widget.bkg_roi.blockSignals(True)
        self.widget.pattern_widget.set_bkg_roi(*pattern.auto_bkg_roi)
        self.widget.pattern_widget.bkg_roi.blockSignals(False)

        if self.model.batch_model.binning is not None:
            start_x, stop_x = (
                self.widget.batch_widget.stack_plot_widget.img_view.x_bin_range
            )
            binning = self.model.batch_model.binning[start_x:stop_x]

            bkg_roi = self.convert_x_value(
                np.array(pattern.auto_bkg_roi),
                self.model.current_configuration.integration_unit,
                "2th_deg",
            )
            scale = (binning[-1] - binning[0]) / binning.shape[0]
            x_min_bin = (bkg_roi[0] - binning[0]) / scale
            x_max_bin = (bkg_roi[1] - binning[0]) / scale
            self.widget.batch_widget.stack_plot_widget.img_view.set_linear_region(
                x_min_bin, x_max_bin
            )

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
            self.widget.bkg_pattern_x_min_txt.editingFinished.connect(
                self.update_bkg_pattern_linear_region
            )
            self.widget.bkg_pattern_x_max_txt.editingFinished.connect(
                self.update_bkg_pattern_linear_region
            )

            self.widget.batch_widget.stack_plot_widget.img_view.show_linear_region()
            self.widget.batch_widget.stack_plot_widget.img_view.linear_region_item.sigRegionChanged.connect(
                self.bkg_batch_linear_region_callback
            )

        else:
            self.widget.pattern_widget.hide_bkg_roi()
            self.widget.pattern_widget.bkg_roi.sigRegionChanged.disconnect(
                self.bkg_pattern_linear_region_callback
            )

            self.widget.batch_widget.stack_plot_widget.img_view.linear_region_item.sigRegionChanged.disconnect(
                self.bkg_batch_linear_region_callback
            )
            self.widget.batch_widget.stack_plot_widget.img_view.hide_linear_region()

            self.widget.bkg_pattern_x_min_txt.editingFinished.disconnect(
                self.update_bkg_pattern_linear_region
            )
            self.widget.bkg_pattern_x_max_txt.editingFinished.disconnect(
                self.update_bkg_pattern_linear_region
            )
        self.model.pattern_changed.emit()

    def bkg_pattern_save_btn_callback(self):
        img_filename, _ = os.path.splitext(
            os.path.basename(self.model.img_model.filename)
        )
        filename = save_file_dialog(
            self.widget,
            "Save Fit Background as Pattern Data.",
            os.path.join(
                self.model.working_directories["pattern"], img_filename + ".xy"
            ),
            ("Data (*.xy);;Data (*.chi);;Data (*.dat);;GSAS (*.fxye)"),
        )

        if filename != "":
            self.model.current_configuration.save_background_pattern(filename)

    def bkg_pattern_as_overlay_btn_callback(self):
        self.model.overlay_model.add_overlay_pattern(
            self.model.pattern.auto_background_pattern
        )

    def bkg_pattern_linear_region_callback(self):
        x_min, x_max = self.widget.pattern_widget.get_bkg_roi()
        self.widget.bkg_pattern_x_min_txt.setText("{:.3f}".format(x_min))
        self.widget.bkg_pattern_x_max_txt.setText("{:.3f}".format(x_max))
        self.bkg_pattern_parameters_changed()

    def bkg_batch_linear_region_callback(self):
        x_min, x_max = (
            self.widget.batch_widget.stack_plot_widget.img_view.get_linear_region()
        )

        if self.model.batch_model.binning is None:
            return
        start_x, stop_x = (
            self.widget.batch_widget.stack_plot_widget.img_view.x_bin_range
        )
        binning = self.model.batch_model.binning[start_x:stop_x]
        scale = (binning[-1] - binning[0]) / binning.shape[0]
        x_min_tth = x_min * scale + binning[0]
        x_max_tth = x_max * scale + binning[0]
        x_min_val = self.convert_x_value(
            x_min_tth, "2th_deg", self.model.current_configuration.integration_unit
        )
        x_max_val = self.convert_x_value(
            x_max_tth, "2th_deg", self.model.current_configuration.integration_unit
        )
        self.widget.bkg_pattern_x_min_txt.setText("{:.3f}".format(x_min_val))
        self.widget.bkg_pattern_x_max_txt.setText("{:.3f}".format(x_max_val))
        self.bkg_pattern_parameters_changed()

    def update_bkg_pattern_linear_region(self):
        self.widget.pattern_widget.bkg_roi.blockSignals(True)
        bkg_roi = (
            self.widget.integration_control_widget.background_control_widget.get_bkg_pattern_roi()
        )
        self.widget.pattern_widget.set_bkg_roi(*bkg_roi)

        if self.model.batch_model.binning is not None:
            start_x, stop_x = (
                self.widget.batch_widget.stack_plot_widget.img_view.x_bin_range
            )
            binning = self.model.batch_model.binning[start_x:stop_x]
            bkg_roi = self.convert_x_value(
                np.array(bkg_roi),
                self.model.current_configuration.integration_unit,
                "2th_deg",
            )
            scale = (binning[-1] - binning[0]) / binning.shape[0]
            x_min_bin = int((bkg_roi[0] - binning[0]) / scale)
            x_max_bin = int((bkg_roi[1] - binning[0]) / scale)
            self.widget.batch_widget.stack_plot_widget.img_view.set_linear_region(
                x_min_bin, x_max_bin
            )
        self.widget.pattern_widget.bkg_roi.blockSignals(False)

    def update_bkg_image_widgets(self):
        self.update_background_image_filename()
        self.widget.bkg_image_offset_sb.setValue(self.model.img_model.background_offset)
        self.widget.bkg_image_scale_sb.setValue(self.model.img_model.background_scaling)
        self.widget.img_show_background_subtracted_btn.setVisible(
            self.model.img_model.has_background()
        )

    def update_auto_pattern_bkg_widgets(self):
        # set the state of the toggles:
        self.widget.bkg_pattern_gb.blockSignals(True)
        self.widget.qa_bkg_pattern_btn.blockSignals(True)
        auto_bkg_enabled = self.model.pattern.auto_bkg is not None
        self.widget.bkg_pattern_gb.setChecked(auto_bkg_enabled)
        self.widget.qa_bkg_pattern_inspect_btn.setVisible(auto_bkg_enabled)
        self.widget.qa_bkg_pattern_btn.setChecked(auto_bkg_enabled)
        self.widget.bkg_pattern_gb.blockSignals(False)
        self.widget.qa_bkg_pattern_btn.blockSignals(False)

        self.update_bkg_gui_parameters()
        self.widget.qa_bkg_pattern_inspect_btn.setChecked(False)
        self.widget.bkg_pattern_inspect_btn.setChecked(False)

    def convert_x_value(self, value, previous_unit, new_unit):
        wavelength = self.model.calibration_model.wavelength
        if previous_unit == "2th_deg":
            tth = value
        elif previous_unit == "q_A^-1":
            tth = np.arcsin(value * 1e10 * wavelength / (4 * np.pi)) * 360 / np.pi
        elif previous_unit == "d_A":
            tth = 2 * np.arcsin(wavelength / (2 * value * 1e-10)) * 180 / np.pi
        else:
            tth = 0

        if new_unit == "2th_deg":
            res = tth
        elif new_unit == "q_A^-1":
            res = 4 * np.pi * np.sin(tth / 360 * np.pi) / wavelength / 1e10
        elif new_unit == "d_A":
            res = wavelength / (2 * np.sin(tth / 360 * np.pi)) * 1e10
        else:
            res = 0
        return res
