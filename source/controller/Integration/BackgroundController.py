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
from model.SpectrumData import SpectrumData
from model.ImgData import ImgData
from widgets.IntegrationView import IntegrationView


class BackgroundController(object):
    """
    The IntegrationImageController manages the Image actions in the Integration Window. It connects the file actions, as
    well as interaction with the image_view.
    """

    def __init__(self, working_dir, view, img_data, spectrum_data):
        """
        :param working_dir: dictionary with working directories (uses the 'image' key) for the background image
        :param view: IntegrationWidget
        :param img_data: Reference to the ImgData object
        :param spectrum_data: Reference to the spectrum_data object

        :type view: IntegrationView
        :type img_data: ImgData
        :type spectrum_data: SpectrumData
        """
        self.working_dir = working_dir
        self.view = view
        self.img_data = img_data
        self.spectrum_data = spectrum_data
        self.create_image_background_signals()
        self.create_spectrum_background_signals()

    def create_image_background_signals(self):

        self.connect_click_function(self.view.bkg_image_load_btn, self.load_background_image)
        self.connect_click_function(self.view.bkg_image_delete_btn, self.remove_background_image)

        self.view.bkg_image_scale_step_txt.editingFinished.connect(self.update_bkg_image_scale_step)
        self.view.bkg_image_offset_step_txt.editingFinished.connect(self.update_bkg_image_offset_step)
        self.view.bkg_image_scale_sb.valueChanged.connect(self.img_data.set_background_scaling)
        self.view.bkg_image_offset_sb.valueChanged.connect(self.img_data.set_background_offset)

        self.img_data.subscribe(self.update_background_image_filename)

    def create_spectrum_background_signals(self):
        self.view.bkg_spectrum_gb.toggled.connect(self.bkg_spectrum_gb_toggled_callback)
        self.view.qa_bkg_spectrum_btn.toggled.connect(self.bkg_spectrum_gb_toggled_callback)

        self.view.bkg_spectrum_iterations_sb.valueChanged.connect(self.bkg_spectrum_parameters_changed)
        self.view.bkg_spectrum_poly_order_sb.valueChanged.connect(self.bkg_spectrum_parameters_changed)
        self.view.bkg_spectrum_smooth_width_sb.valueChanged.connect(self.bkg_spectrum_parameters_changed)
        self.view.bkg_spectrum_x_min_txt.editingFinished.connect(self.bkg_spectrum_parameters_changed)
        self.view.bkg_spectrum_x_max_txt.editingFinished.connect(self.bkg_spectrum_parameters_changed)

        self.view.bkg_spectrum_inspect_btn.toggled.connect(self.bkg_spectrum_inspect_btn_toggled_callback)
        self.view.qa_bkg_spectrum_inspect_btn.toggled.connect(self.bkg_spectrum_inspect_btn_toggled_callback)

    def connect_click_function(self, emitter, function):
        """
        Small helper function for the button-click connection.
        """
        self.view.connect(emitter, QtCore.SIGNAL('clicked()'), function)

    def load_background_image(self, filename=None):
        if filename is None:
            filename = str(QtGui.QFileDialog.getOpenFileName(
                self.view, "Load an image background file",
                self.working_dir['image']))

        if filename is not None and filename is not '':
            self.view.bkg_image_filename_lbl.setText("Loading File")
            self.img_data.load_background(filename)

    def remove_background_image(self):
        self.view.bkg_image_filename_lbl.setText("None")
        self.view.bkg_name_lbl.setText('')
        self.img_data.reset_background()

    def update_bkg_image_scale_step(self):
        value = np.float(self.view.bkg_image_scale_step_txt.text())
        self.view.bkg_image_scale_sb.setSingleStep(value)

    def update_bkg_image_offset_step(self):
        value = np.float(self.view.bkg_image_offset_step_txt.text())
        self.view.bkg_image_offset_sb.setSingleStep(value)

    def update_background_image_filename(self):
        if self.img_data.has_background():
            self.view.bkg_image_filename_lbl.setText(os.path.basename(self.img_data.background_filename))
            self.view.bkg_name_lbl.setText('Bkg image: {0}'.format(os.path.basename(self.img_data.background_filename)))
        else:
            if str(self.view.bkg_image_filename_lbl.text())!='None':
                QtGui.QMessageBox.critical(self.view, 'ERROR',
                                           'Background image does not have the same dimensions as original Image. ' +\
                                           'Resetting Background Image.')

            self.view.bkg_image_filename_lbl.setText('None')
            self.view.bkg_name_lbl.setText('')


    def bkg_spectrum_gb_toggled_callback(self, is_checked):
        self.view.bkg_spectrum_gb.blockSignals(True)
        self.view.qa_bkg_spectrum_btn.blockSignals(True)
        self.view.bkg_spectrum_gb.setChecked(is_checked)
        self.view.qa_bkg_spectrum_btn.setChecked(is_checked)
        self.view.bkg_spectrum_gb.blockSignals(False)
        self.view.qa_bkg_spectrum_btn.blockSignals(False)
        self.view.qa_bkg_spectrum_inspect_btn.setVisible(is_checked)

        if is_checked:
            bkg_spectrum_parameters = self.view.get_bkg_spectrum_parameters()
            bkg_spectrum_roi = self.view.get_bkg_spectrum_roi()
            self.spectrum_data.set_auto_background_subtraction(bkg_spectrum_parameters, bkg_spectrum_roi)
        else:
            self.view.bkg_spectrum_inspect_btn.setChecked(False)
            self.view.qa_bkg_spectrum_inspect_btn.setChecked(False)
            self.view.spectrum_view.hide_linear_region()
            self.spectrum_data.unset_auto_background_subtraction()

    def bkg_spectrum_parameters_changed(self):
        bkg_spectrum_parameters = self.view.get_bkg_spectrum_parameters()
        bkg_spectrum_roi = self.view.get_bkg_spectrum_roi()
        self.spectrum_data.set_auto_background_subtraction(bkg_spectrum_parameters, bkg_spectrum_roi)

    def bkg_spectrum_inspect_btn_toggled_callback(self, checked):
        self.view.bkg_spectrum_inspect_btn.blockSignals(True)
        self.view.qa_bkg_spectrum_inspect_btn.blockSignals(True)
        self.view.bkg_spectrum_inspect_btn.setChecked(checked)
        self.view.qa_bkg_spectrum_inspect_btn.setChecked(checked)
        self.view.bkg_spectrum_inspect_btn.blockSignals(False)
        self.view.qa_bkg_spectrum_inspect_btn.blockSignals(False)

        if checked:
            self.view.spectrum_view.show_linear_region()
            x_min, x_max = self.view.get_bkg_spectrum_roi()
            x_spec = self.spectrum_data.spectrum.auto_background_before_subtraction_spectrum.x
            if x_min<x_spec[0]:
                x_min = x_spec[0]
            if x_max>x_spec[-1]:
                x_max=x_spec[-1]
            self.view.spectrum_view.set_linear_region(x_min, x_max)
            self.view.spectrum_view.linear_region_item.sigRegionChanged.connect(
                self.bkg_spectrum_linear_region_callback
            )
            self.view.bkg_spectrum_x_min_txt.editingFinished.connect(self.update_bkg_spectrum_linear_region)
            self.view.bkg_spectrum_x_max_txt.editingFinished.connect(self.update_bkg_spectrum_linear_region)
        else:
            self.view.spectrum_view.hide_linear_region()
            self.view.spectrum_view.linear_region_item.sigRegionChanged.disconnect(
                self.bkg_spectrum_linear_region_callback
            )

            self.view.bkg_spectrum_x_min_txt.editingFinished.disconnect(self.update_bkg_spectrum_linear_region)
            self.view.bkg_spectrum_x_max_txt.editingFinished.disconnect(self.update_bkg_spectrum_linear_region)
        self.spectrum_data.spectrum_changed.emit()

    def bkg_spectrum_linear_region_callback(self):
        x_min, x_max = self.view.spectrum_view.get_linear_region()
        self.view.bkg_spectrum_x_min_txt.setText('{:.3f}'.format(x_min))
        self.view.bkg_spectrum_x_max_txt.setText('{:.3f}'.format(x_max))
        self.bkg_spectrum_parameters_changed()

    def update_bkg_spectrum_linear_region(self):
        self.view.spectrum_view.linear_region_item.blockSignals(True)
        self.view.spectrum_view.set_linear_region(*self.view.get_bkg_spectrum_roi())
        self.view.spectrum_view.linear_region_item.blockSignals(False)