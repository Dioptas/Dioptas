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
from PyQt4 import QtGui, QtCore
import os
import numpy as np


# imports for type hinting in PyCharm -- DO NOT DELETE
from model.SpectrumModel import SpectrumModel
from model.ImgModel import ImgModel
from widgets.IntegrationWidget import IntegrationWidget


class BackgroundController(object):
    """
    The IntegrationImageController manages the Image actions in the Integration Window. It connects the file actions, as
    well as interaction with the image_view.
    """

    def __init__(self, working_dir, widget, img_model, spectrum_model):
        """
        :param working_dir: dictionary with working directories (uses the 'image' key) for the background image
        :param widget: IntegrationWidget
        :param img_model: Reference to the ImgData object
        :param spectrum_model: Reference to the spectrum_data object

        :type widget: IntegrationWidget
        :type img_model: ImgModel
        :type spectrum_model: SpectrumModel
        """
        self.working_dir = working_dir
        self.widget = widget
        self.img_model = img_model
        self.spectrum_model = spectrum_model
        self.create_image_background_signals()
        self.create_spectrum_background_signals()

    def create_image_background_signals(self):

        self.connect_click_function(self.widget.bkg_image_load_btn, self.load_background_image)
        self.connect_click_function(self.widget.bkg_image_delete_btn, self.remove_background_image)

        self.widget.bkg_image_scale_step_txt.editingFinished.connect(self.update_bkg_image_scale_step)
        self.widget.bkg_image_offset_step_txt.editingFinished.connect(self.update_bkg_image_offset_step)
        self.widget.bkg_image_scale_sb.valueChanged.connect(self.img_model.set_background_scaling)
        self.widget.bkg_image_offset_sb.valueChanged.connect(self.img_model.set_background_offset)

        self.img_model.subscribe(self.update_background_image_filename)

    def create_spectrum_background_signals(self):
        self.widget.bkg_spectrum_gb.toggled.connect(self.bkg_spectrum_gb_toggled_callback)
        self.widget.qa_bkg_spectrum_btn.toggled.connect(self.bkg_spectrum_gb_toggled_callback)

        self.widget.bkg_spectrum_iterations_sb.valueChanged.connect(self.bkg_spectrum_parameters_changed)
        self.widget.bkg_spectrum_poly_order_sb.valueChanged.connect(self.bkg_spectrum_parameters_changed)
        self.widget.bkg_spectrum_smooth_width_sb.valueChanged.connect(self.bkg_spectrum_parameters_changed)
        self.widget.bkg_spectrum_x_min_txt.editingFinished.connect(self.bkg_spectrum_parameters_changed)
        self.widget.bkg_spectrum_x_max_txt.editingFinished.connect(self.bkg_spectrum_parameters_changed)

        self.widget.bkg_spectrum_inspect_btn.toggled.connect(self.bkg_spectrum_inspect_btn_toggled_callback)
        self.widget.qa_bkg_spectrum_inspect_btn.toggled.connect(self.bkg_spectrum_inspect_btn_toggled_callback)

    def connect_click_function(self, emitter, function):
        """
        Small helper function for the button-click connection.
        """
        self.widget.connect(emitter, QtCore.SIGNAL('clicked()'), function)

    def load_background_image(self, filename=None):
        if filename is None:
            filename = str(QtGui.QFileDialog.getOpenFileName(
                self.widget, "Load an image background file",
                self.working_dir['image']))

        if filename is not None and filename is not '':
            self.widget.bkg_image_filename_lbl.setText("Loading File")
            self.img_model.load_background(filename)

    def remove_background_image(self):
        self.widget.bkg_image_filename_lbl.setText("None")
        self.widget.bkg_name_lbl.setText('')
        self.img_model.reset_background()

    def update_bkg_image_scale_step(self):
        value = np.float(self.widget.bkg_image_scale_step_txt.text())
        self.widget.bkg_image_scale_sb.setSingleStep(value)

    def update_bkg_image_offset_step(self):
        value = np.float(self.widget.bkg_image_offset_step_txt.text())
        self.widget.bkg_image_offset_sb.setSingleStep(value)

    def update_background_image_filename(self):
        if self.img_model.has_background():
            self.widget.bkg_image_filename_lbl.setText(os.path.basename(self.img_model.background_filename))
            self.widget.bkg_name_lbl.setText('Bkg image: {0}'.format(os.path.basename(self.img_model.background_filename)))
        else:
            if str(self.widget.bkg_image_filename_lbl.text())!='None':
                QtGui.QMessageBox.critical(self.widget, 'ERROR',
                                           'Background image does not have the same dimensions as original Image. ' +\
                                           'Resetting Background Image.')

            self.widget.bkg_image_filename_lbl.setText('None')
            self.widget.bkg_name_lbl.setText('')


    def bkg_spectrum_gb_toggled_callback(self, is_checked):
        self.widget.bkg_spectrum_gb.blockSignals(True)
        self.widget.qa_bkg_spectrum_btn.blockSignals(True)
        self.widget.bkg_spectrum_gb.setChecked(is_checked)
        self.widget.qa_bkg_spectrum_btn.setChecked(is_checked)
        self.widget.bkg_spectrum_gb.blockSignals(False)
        self.widget.qa_bkg_spectrum_btn.blockSignals(False)
        self.widget.qa_bkg_spectrum_inspect_btn.setVisible(is_checked)

        if is_checked:
            bkg_spectrum_parameters = self.widget.get_bkg_spectrum_parameters()
            bkg_spectrum_roi = self.widget.get_bkg_spectrum_roi()
            self.spectrum_model.set_auto_background_subtraction(bkg_spectrum_parameters, bkg_spectrum_roi)
        else:
            self.widget.bkg_spectrum_inspect_btn.setChecked(False)
            self.widget.qa_bkg_spectrum_inspect_btn.setChecked(False)
            self.widget.spectrum_view.hide_linear_region()
            self.spectrum_model.unset_auto_background_subtraction()

    def bkg_spectrum_parameters_changed(self):
        bkg_spectrum_parameters = self.widget.get_bkg_spectrum_parameters()
        bkg_spectrum_roi = self.widget.get_bkg_spectrum_roi()
        self.spectrum_model.set_auto_background_subtraction(bkg_spectrum_parameters, bkg_spectrum_roi)

    def bkg_spectrum_inspect_btn_toggled_callback(self, checked):
        self.widget.bkg_spectrum_inspect_btn.blockSignals(True)
        self.widget.qa_bkg_spectrum_inspect_btn.blockSignals(True)
        self.widget.bkg_spectrum_inspect_btn.setChecked(checked)
        self.widget.qa_bkg_spectrum_inspect_btn.setChecked(checked)
        self.widget.bkg_spectrum_inspect_btn.blockSignals(False)
        self.widget.qa_bkg_spectrum_inspect_btn.blockSignals(False)

        if checked:
            self.widget.spectrum_view.show_linear_region()
            x_min, x_max = self.widget.get_bkg_spectrum_roi()
            x_spec = self.spectrum_model.spectrum.auto_background_before_subtraction_spectrum.x
            if x_min<x_spec[0]:
                x_min = x_spec[0]
            if x_max>x_spec[-1]:
                x_max=x_spec[-1]
            self.widget.spectrum_view.set_linear_region(x_min, x_max)
            self.widget.spectrum_view.linear_region_item.sigRegionChanged.connect(
                self.bkg_spectrum_linear_region_callback
            )
            self.widget.bkg_spectrum_x_min_txt.editingFinished.connect(self.update_bkg_spectrum_linear_region)
            self.widget.bkg_spectrum_x_max_txt.editingFinished.connect(self.update_bkg_spectrum_linear_region)
        else:
            self.widget.spectrum_view.hide_linear_region()
            self.widget.spectrum_view.linear_region_item.sigRegionChanged.disconnect(
                self.bkg_spectrum_linear_region_callback
            )

            self.widget.bkg_spectrum_x_min_txt.editingFinished.disconnect(self.update_bkg_spectrum_linear_region)
            self.widget.bkg_spectrum_x_max_txt.editingFinished.disconnect(self.update_bkg_spectrum_linear_region)
        self.spectrum_model.spectrum_changed.emit()

    def bkg_spectrum_linear_region_callback(self):
        x_min, x_max = self.widget.spectrum_view.get_linear_region()
        self.widget.bkg_spectrum_x_min_txt.setText('{:.3f}'.format(x_min))
        self.widget.bkg_spectrum_x_max_txt.setText('{:.3f}'.format(x_max))
        self.bkg_spectrum_parameters_changed()

    def update_bkg_spectrum_linear_region(self):
        self.widget.spectrum_view.linear_region_item.blockSignals(True)
        self.widget.spectrum_view.set_linear_region(*self.widget.get_bkg_spectrum_roi())
        self.widget.spectrum_view.linear_region_item.blockSignals(False)