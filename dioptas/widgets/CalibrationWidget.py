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

import os
from PyQt4 import QtGui

from .UiFiles.CalibrationUI import Ui_XrsCalibrationWidget
from widgets.plot_widgets import MaskImgWidget, CalibrationCakeWidget
from .plot_widgets import SpectrumWidget


class CalibrationWidget(QtGui.QWidget, Ui_XrsCalibrationWidget):
    def __init__(self):
        super(CalibrationWidget, self).__init__(None)
        self.setupUi(self)
        self.splitter.setStretchFactor(0, 2)

        self.img_view = MaskImgWidget(self.img_pg_layout)
        self.cake_view = CalibrationCakeWidget(self.cake_pg_layout)
        self.spectrum_view = SpectrumWidget(self.spectrum_pg_layout)

        self.set_validator()
        self.set_cb_style()

    def set_validator(self):
        self.f2_center_x_txt.setValidator(QtGui.QDoubleValidator())
        self.f2_center_y_txt.setValidator(QtGui.QDoubleValidator())
        self.f2_distance_txt.setValidator(QtGui.QDoubleValidator())
        self.f2_pixel_height_txt.setValidator(QtGui.QDoubleValidator())
        self.f2_pixel_width_txt.setValidator(QtGui.QDoubleValidator())
        self.f2_rotation_txt.setValidator(QtGui.QDoubleValidator())
        self.f2_tilt_txt.setValidator(QtGui.QDoubleValidator())
        self.f2_wavelength_txt.setValidator(QtGui.QDoubleValidator())
        self.f2_polarization_txt.setValidator(QtGui.QDoubleValidator())

        self.pf_distance_txt.setValidator(QtGui.QDoubleValidator())
        self.pf_pixel_height_txt.setValidator(QtGui.QDoubleValidator())
        self.pf_pixel_width_txt.setValidator(QtGui.QDoubleValidator())
        self.pf_poni1_txt.setValidator(QtGui.QDoubleValidator())
        self.pf_poni2_txt.setValidator(QtGui.QDoubleValidator())
        self.pf_rotation1_txt.setValidator(QtGui.QDoubleValidator())
        self.pf_rotation2_txt.setValidator(QtGui.QDoubleValidator())
        self.pf_rotation3_txt.setValidator(QtGui.QDoubleValidator())
        self.pf_wavelength_txt.setValidator(QtGui.QDoubleValidator())
        self.pf_polarization_txt.setValidator(QtGui.QDoubleValidator())

        self.sv_pixel_height_txt.setValidator(QtGui.QDoubleValidator())
        self.sv_pixel_width_txt.setValidator(QtGui.QDoubleValidator())
        self.sv_distance_txt.setValidator(QtGui.QDoubleValidator())
        self.sv_wavelength_txt.setValidator(QtGui.QDoubleValidator())
        self.sv_polarization_txt.setValidator(QtGui.QDoubleValidator())

        self.options_delta_tth_txt.setValidator(QtGui.QDoubleValidator())
        self.options_intensity_limit_txt.setValidator(QtGui.QDoubleValidator())

    def set_cb_style(self):
        cleanlooks = QtGui.QStyleFactory.create('cleanlooks')
        self.calibrant_cb.setStyle(cleanlooks)
        self.options_peaksearch_algorithm_cb.setStyle(cleanlooks)

    def set_img_filename(self, filename):
        self.filename_txt.setText(os.path.basename(filename))

    def set_start_values(self, start_values):
        self.sv_distance_txt.setText('%.3f' % (start_values['dist'] * 1000))
        self.sv_wavelength_txt.setText('%.6f' % (start_values['wavelength'] * 1e10))
        self.sv_polarization_txt.setText('%.3f' % (start_values['polarization_factor']))
        self.sv_pixel_height_txt.setText('%.0f' % (start_values['pixel_width'] * 1e6))
        self.sv_pixel_width_txt.setText('%.0f' % (start_values['pixel_width'] * 1e6))
        return start_values

    def get_start_values(self):
        start_values = {'dist': float(self.sv_distance_txt.text()) * 1e-3,
                        'wavelength': float(self.sv_wavelength_txt.text()) * 1e-10,
                        'pixel_width': float(self.sv_pixel_width_txt.text()) * 1e-6,
                        'pixel_height': float(self.sv_pixel_height_txt.text()) * 1e-6,
                        'polarization_factor': float(self.sv_polarization_txt.text())}
        return start_values

    def set_calibration_parameters(self, pyFAI_parameter, fit2d_parameter):
        self.set_pyFAI_parameter(pyFAI_parameter)
        self.set_fit2d_parameter(fit2d_parameter)


    def set_pyFAI_parameter(self, pyFAI_parameter):
        self.pf_distance_txt.setText('%.6f' % (pyFAI_parameter['dist'] * 1000))
        self.pf_poni1_txt.setText('%.6f' % (pyFAI_parameter['poni1']))
        self.pf_poni2_txt.setText('%.6f' % (pyFAI_parameter['poni2']))
        self.pf_rotation1_txt.setText('%.8f' % (pyFAI_parameter['rot1']))
        self.pf_rotation2_txt.setText('%.8f' % (pyFAI_parameter['rot2']))
        self.pf_rotation3_txt.setText('%.8f' % (pyFAI_parameter['rot3']))
        self.pf_wavelength_txt.setText('%.6f' % (pyFAI_parameter['wavelength'] * 1e10))
        self.pf_polarization_txt.setText('%.3f' % (pyFAI_parameter['polarization_factor']))
        self.pf_pixel_width_txt.setText('%.4f' % (pyFAI_parameter['pixel1'] * 1e6))
        self.pf_pixel_height_txt.setText('%.4f' % (pyFAI_parameter['pixel2'] * 1e6))

    def get_pyFAI_parameter(self):
        pyFAI_parameter = {'dist': float(self.pf_distance_txt.text()) / 1000, 'poni1': float(self.pf_poni1_txt.text()),
                           'poni2': float(self.pf_poni2_txt.text()), 'rot1': float(self.pf_rotation1_txt.text()),
                           'rot2': float(self.pf_rotation2_txt.text()), 'rot3': float(self.pf_rotation3_txt.text()),
                           'wavelength': float(self.pf_wavelength_txt.text()) / 1e10,
                           'polarization_factor': float(self.pf_polarization_txt.text()),
                           'pixel1': float(self.pf_pixel_width_txt.text()) / 1e6,
                           'pixel2': float(self.pf_pixel_height_txt.text()) / 1e6}
        return pyFAI_parameter


    def set_fit2d_parameter(self, fit2d_parameter):
        self.f2_distance_txt.setText('%.4f' % (fit2d_parameter['directDist']))
        self.f2_center_x_txt.setText('%.3f' % (fit2d_parameter['centerX']))
        self.f2_center_y_txt.setText('%.3f' % (fit2d_parameter['centerY']))
        self.f2_tilt_txt.setText('%.6f' % (fit2d_parameter['tilt']))
        self.f2_rotation_txt.setText('%.6f' % (fit2d_parameter['tiltPlanRotation']))
        self.f2_wavelength_txt.setText('%.4f' % (fit2d_parameter['wavelength'] * 1e10))
        self.f2_polarization_txt.setText('%.3f' % (fit2d_parameter['polarization_factor']))
        self.f2_pixel_width_txt.setText('%.4f' % (fit2d_parameter['pixelX']))
        self.f2_pixel_height_txt.setText('%.4f' % (fit2d_parameter['pixelY']))

    def get_fit2d_parameter(self):
        fit2d_parameter = {'directDist': float(self.f2_distance_txt.text()),
                           'centerX': float(self.f2_center_x_txt.text()), 'centerY': float(self.f2_center_y_txt.text()),
                           'tilt': float(self.f2_tilt_txt.text()),
                           'tiltPlanRotation': float(self.f2_rotation_txt.text()),
                           'wavelength': float(self.f2_wavelength_txt.text()) / 1e10,
                           'polarization_factor': float(self.f2_polarization_txt.text()),
                           'pixelX': float(self.f2_pixel_width_txt.text()),
                           'pixelY': float(self.f2_pixel_height_txt.text())}
        return fit2d_parameter
