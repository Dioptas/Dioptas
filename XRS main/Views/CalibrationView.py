__author__ = 'Clemens Prescher'

import sys
import os
from PyQt4 import QtGui, QtCore
from UiFiles.CalibrationUI import Ui_XrsCalibrationWidget
from ImgView import ImgView, CalibrationCakeView
from SpectrumView import SpectrumView
import numpy as np
import pyqtgraph as pg


class CalibrationView(QtGui.QWidget, Ui_XrsCalibrationWidget):
    def __init__(self):
        super(CalibrationView, self).__init__(None)
        self.setupUi(self)
        self.splitter.setStretchFactor(0, 1)

        self.img_view = ImgView(self.img_pg_layout)
        self.img_view.add_mouse_move_observer(self.show_img_mouse_position)

        self.cake_view = CalibrationCakeView(self.cake_pg_layout)
        self.cake_view.add_mouse_move_observer(self.show_cake_mouse_position)

        self.spectrum_view = SpectrumView(self.spectrum_pg_layout)
        self.spectrum_view.add_mouse_move_observer(self.show_spectrum_mouse_position)

        self.set_validator()

    def set_validator(self):
        self.f2_center_x_txt.setValidator(QtGui.QDoubleValidator())
        self.f2_center_y_txt.setValidator(QtGui.QDoubleValidator())
        self.f2_distance_txt.setValidator(QtGui.QDoubleValidator())
        self.f2_pixel_height_txt.setValidator(QtGui.QDoubleValidator())
        self.f2_pixel_width_txt.setValidator(QtGui.QDoubleValidator())
        self.f2_rotation_txt.setValidator(QtGui.QDoubleValidator())
        self.f2_tilt_txt.setValidator(QtGui.QDoubleValidator())
        self.f2_wavelength_txt.setValidator(QtGui.QDoubleValidator())

        self.pf_distance_txt.setValidator(QtGui.QDoubleValidator())
        self.pf_pixel_height_txt.setValidator(QtGui.QDoubleValidator())
        self.pf_pixel_width_txt.setValidator(QtGui.QDoubleValidator())
        self.pf_poni1_txt.setValidator(QtGui.QDoubleValidator())
        self.pf_poni2_txt.setValidator(QtGui.QDoubleValidator())
        self.pf_rotation1_txt.setValidator(QtGui.QDoubleValidator())
        self.pf_rotation2_txt.setValidator(QtGui.QDoubleValidator())
        self.pf_rotation3_txt.setValidator(QtGui.QDoubleValidator())
        self.pf_wavelength_txt.setValidator(QtGui.QDoubleValidator())

        self.sv_pixel_height_txt.setValidator(QtGui.QDoubleValidator())
        self.sv_pixel_width_txt.setValidator(QtGui.QDoubleValidator())
        self.sv_distance_txt.setValidator(QtGui.QDoubleValidator())
        self.sv_wavelength_txt.setValidator(QtGui.QDoubleValidator())

    def show_img_mouse_position(self, x, y):
        try:
            if x > 0 and y > 0:
                str = "x: %.1f y: %.1f I: %.0f" % (x, y, self.img_view.img_data.T[np.round(x), np.round(y)])
            else:
                str = "x: %.1f y: %.1f" % (x, y)
        except (IndexError, AttributeError):
            str = "x: %.1f y: %.1f" % (x, y)
        self.pos_lbl.setText(str)

    def show_cake_mouse_position(self, x, y):
        try:
            if x > 0 and y > 0:
                str = "x: %.1f y: %.1f I: %.0f" % (x, y, self.cake_view.img_data.T[np.round(x), np.round(y)])
            else:
                str = "x: %.1f y: %.1f" % (x, y)
        except (IndexError, AttributeError):
            str = "x: %.1f y: %.1f" % (x, y)
        self.pos_lbl.setText(str)

    def show_spectrum_mouse_position(self, x, y):
        str = "x: %.1f y: %.1f" % (x, y)
        self.pos_lbl.setText(str)


    def set_img_filename(self, filename):
        self.filename_lbl.setText(os.path.basename(filename))

    def get_start_values(self):
        start_values = {'dist': float(self.sv_distance_txt.text()) * 1e-3,
                        'wavelength': float(self.sv_wavelength_txt.text()) * 1e-10,
                        'pixel_width': float(self.sv_pixel_width_txt.text()) * 1e-6,
                        'pixel_height': float(self.sv_pixel_height_txt.text()) * 1e-6}
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
        self.pf_pixel_width_txt.setText('%.4f' % (pyFAI_parameter['pixel1'] * 1e6))
        self.pf_pixel_height_txt.setText('%.4f' % (pyFAI_parameter['pixel2'] * 1e6))

    def get_pyFAI_parameter(self):
        pyFAI_parameter = {'dist': float(self.pf_distance_txt.text()) / 1000, 'poni1': float(self.pf_poni1_txt.text()),
                           'poni2': float(self.pf_poni2_txt.text()), 'rot1': float(self.pf_rotation1_txt.text()),
                           'rot2': float(self.pf_rotation2_txt.text()), 'rot3': float(self.pf_rotation3_txt.text()),
                           'wavelength': float(self.pf_wavelength_txt.text()) / 1e10,
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
        self.f2_pixel_width_txt.setText('%.4f' % (fit2d_parameter['pixelX']))
        self.f2_pixel_height_txt.setText('%.4f' % (fit2d_parameter['pixelY']))

    def get_fit2d_parameter(self):
        fit2d_parameter = {'directDist': float(self.f2_distance_txt.text()),
                           'centerX': float(self.f2_center_x_txt.text()), 'centerY': float(self.f2_center_y_txt.text()),
                           'tilt': float(self.f2_tilt_txt.text()),
                           'tiltPlanRotation': float(self.f2_rotation_txt.text()),
                           'wavelength': float(self.f2_wavelength_txt.text()) / 1e10,
                           'pixelX': float(self.f2_pixel_width_txt.text()),
                           'pixelY': float(self.f2_pixel_height_txt.text())}
        return fit2d_parameter
