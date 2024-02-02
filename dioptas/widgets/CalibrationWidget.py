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
import sys

from qtpy import QtWidgets, QtGui, QtCore
from pyqtgraph import GraphicsLayoutWidget

from ..widgets.plot_widgets import MaskImgWidget, CalibrationCakeWidget
from ..widgets.plot_widgets import PatternWidget

from .CustomWidgets import NumberTextField, LabelAlignRight, CleanLooksComboBox, SpinBoxAlignRight, \
    DoubleSpinBoxAlignRight, OpenIconButton, ResetIconButton


class CalibrationWidget(QtWidgets.QWidget):
    """
    Defines the main structure of the calibration widget, which is separated into two parts.
    Calibration Display Widget - shows the image and pattern
    Calibration Control Widget - shows all the controls on the right side of the widget
    """

    def __init__(self, *args, **kwargs):
        super(CalibrationWidget, self).__init__(*args, **kwargs)

        self.setObjectName('calibration_widget')

        self.calibration_display_widget = CalibrationDisplayWidget(self)
        self.calibration_control_widget = CalibrationControlWidget(self)

        self._layout = QtWidgets.QHBoxLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.addWidget(self.calibration_display_widget)
        self._layout.addWidget(self.calibration_control_widget)
        self.setLayout(self._layout)

        self.create_shortcuts()

    def create_shortcuts(self):
        """
        Creates shortcuts for the widgets which are directly interfacing with the controller.
        """
        self.load_img_btn = self.calibration_control_widget.load_img_btn
        self.load_next_img_btn = self.calibration_control_widget.load_next_img_btn
        self.load_previous_img_btn = self.calibration_control_widget.load_previous_img_btn
        self.filename_txt = self.calibration_control_widget.filename_txt

        self.save_calibration_btn = self.calibration_control_widget.save_calibration_btn
        self.load_calibration_btn = self.calibration_control_widget.load_calibration_btn

        self.calibrate_btn = self.calibration_display_widget.calibrate_btn
        self.refine_btn = self.calibration_display_widget.refine_btn
        self.pos_lbl = self.calibration_display_widget.position_lbl

        self.tab_widget = self.calibration_display_widget.tab_widget
        self.ToolBox = self.calibration_control_widget.toolbox

        detector_gb = self.calibration_control_widget.calibration_parameters_widget.detector_gb
        self.detectors_cb = detector_gb.detector_cb
        self.detector_name_lbl = detector_gb.detector_name_lbl
        self.detector_load_btn = detector_gb.detector_load_btn
        self.detector_reset_btn = detector_gb.detector_reset_btn
        self.spline_reset_btn = detector_gb.spline_reset_btn
        self.load_spline_btn = detector_gb.spline_load_btn
        self.spline_filename_txt = detector_gb.spline_name_txt

        sv_gb = self.calibration_control_widget.calibration_parameters_widget.start_values_gb
        self.rotate_m90_btn = sv_gb.rotate_m90_btn
        self.rotate_p90_btn = sv_gb.rotate_p90_btn
        self.invert_horizontal_btn = sv_gb.flip_horizontal_btn
        self.invert_vertical_btn = sv_gb.flip_vertical_btn
        self.reset_transformations_btn = sv_gb.reset_transformations_btn
        self.calibrant_cb = sv_gb.calibrant_cb

        self.sv_wavelength_txt = sv_gb.wavelength_txt
        self.sv_wavelength_cb = sv_gb.wavelength_cb
        self.sv_distance_txt = sv_gb.distance_txt
        self.sv_distance_cb = sv_gb.distance_cb
        self.sv_polarisation_txt = sv_gb.polarization_txt

        refinement_options_gb = self.calibration_control_widget.calibration_parameters_widget.refinement_options_gb
        self.use_mask_cb = refinement_options_gb.use_mask_cb
        self.mask_transparent_cb = refinement_options_gb.mask_transparent_cb
        self.options_automatic_refinement_cb = refinement_options_gb.automatic_refinement_cb
        self.options_num_rings_sb = refinement_options_gb.number_of_rings_sb
        self.options_peaksearch_algorithm_cb = refinement_options_gb.peak_search_algorithm_cb
        self.options_delta_tth_txt = refinement_options_gb.delta_tth_txt
        self.options_intensity_mean_factor_sb = refinement_options_gb.intensity_mean_factor_sb
        self.options_intensity_limit_txt = refinement_options_gb.intensity_limit_txt

        peak_selection_gb = self.calibration_control_widget.calibration_parameters_widget.peak_selection_gb
        self.peak_num_sb = peak_selection_gb.peak_num_sb
        self.automatic_peak_search_rb = peak_selection_gb.automatic_peak_search_rb
        self.select_peak_rb = peak_selection_gb.select_peak_rb
        self.search_size_sb = peak_selection_gb.search_size_sb
        self.automatic_peak_num_inc_cb = peak_selection_gb.automatic_peak_num_inc_cb
        self.clear_peaks_btn = peak_selection_gb.clear_peaks_btn
        self.undo_peaks_btn = peak_selection_gb.undo_peaks_btn

        self.f2_update_btn = self.calibration_control_widget.fit2d_parameters_widget.update_btn
        self.pf_update_btn = self.calibration_control_widget.pyfai_parameters_widget.update_btn

        self.f2_wavelength_cb = self.calibration_control_widget.fit2d_parameters_widget.wavelength_cb
        self.pf_wavelength_cb = self.calibration_control_widget.pyfai_parameters_widget.wavelength_cb

        self.f2_distance_cb = self.calibration_control_widget.fit2d_parameters_widget.distance_cb
        self.pf_distance_cb = self.calibration_control_widget.pyfai_parameters_widget.distance_cb

        self.pf_poni1_cb = self.calibration_control_widget.pyfai_parameters_widget.poni1_cb
        self.pf_poni2_cb = self.calibration_control_widget.pyfai_parameters_widget.poni2_cb
        self.pf_rot1_cb = self.calibration_control_widget.pyfai_parameters_widget.rotation1_cb
        self.pf_rot2_cb = self.calibration_control_widget.pyfai_parameters_widget.rotation2_cb
        self.pf_rot3_cb = self.calibration_control_widget.pyfai_parameters_widget.rotation3_cb

        self.img_widget = self.calibration_display_widget.img_widget
        self.cake_widget = self.calibration_display_widget.cake_widget
        self.pattern_widget = self.calibration_display_widget.pattern_widget

    def set_img_filename(self, filename):
        self.filename_txt.setText(os.path.basename(filename))

    def set_start_values(self, start_values):
        """
        Sets the Start value widgets with the correct numbers and appropriate formatting
        :param start_values: dictionary with calibration start values, expected fields are: dist, wavelength,
                             polarization_factor, pixel_width, pixel_width
        """
        sv_gb = self.calibration_control_widget.calibration_parameters_widget.start_values_gb
        sv_gb.distance_txt.setText('%.3f' % (start_values['dist'] * 1000))
        sv_gb.wavelength_txt.setText('%.6f' % (start_values['wavelength'] * 1e10))
        sv_gb.polarization_txt.setText('%.3f' % (start_values['polarization_factor']))

    def get_start_values(self):
        """
        Gets start_values from the widgets
        :return: returns a dictionary with the following keys: dist, wavelength, pixel_width, pixel_height,
                polarization_factor
        """
        sv_gb = self.calibration_control_widget.calibration_parameters_widget.start_values_gb
        start_values = {'dist': float(sv_gb.distance_txt.text()) * 1e-3,
                        'wavelength': float(sv_gb.wavelength_txt.text()) * 1e-10,
                        'polarization_factor': float(sv_gb.polarization_txt.text())}
        return start_values

    def get_pixel_size(self):
        detector_gb = self.calibration_control_widget.calibration_parameters_widget.detector_gb
        return float(detector_gb.pixel_height_txt.text()) * 1e-6, \
               float(detector_gb.pixel_width_txt.text()) * 1e-6

    def set_pixel_size(self, pixel_width, pixel_height):
        detector_gb = self.calibration_control_widget.calibration_parameters_widget.detector_gb
        detector_gb.pixel_width_txt.setText('%.0f' % (pixel_width * 1e6))
        detector_gb.pixel_height_txt.setText('%.0f' % (pixel_height * 1e6))

    def enable_pixel_size_txt(self, bool):
        detector_gb = self.calibration_control_widget.calibration_parameters_widget.detector_gb
        detector_gb.pixel_width_txt.setEnabled(bool)
        detector_gb.pixel_height_txt.setEnabled(bool)

    def get_fixed_values(self):
        fixed_values = {}

        pyfai_widget = self.calibration_control_widget.pyfai_parameters_widget
        sv_gb = self.calibration_control_widget.calibration_parameters_widget.start_values_gb

        if not sv_gb.distance_cb.isChecked():
            fixed_values['dist'] = self.get_float_from_txt_field(sv_gb.distance_txt) * 1e-3
        if not pyfai_widget.rotation1_cb.isChecked():
            fixed_values['rot1'] = self.get_float_from_txt_field(pyfai_widget.rotation1_txt)
        if not pyfai_widget.rotation2_cb.isChecked():
            fixed_values['rot2'] = self.get_float_from_txt_field(pyfai_widget.rotation2_txt)
        if not pyfai_widget.rotation3_cb.isChecked():
            fixed_values['rot3'] = self.get_float_from_txt_field(pyfai_widget.rotation3_txt)
        if not pyfai_widget.poni1_cb.isChecked():
            fixed_values['poni1'] = self.get_float_from_txt_field(pyfai_widget.poni1_txt)
        if not pyfai_widget.poni2_cb.isChecked():
            fixed_values['poni2'] = self.get_float_from_txt_field(pyfai_widget.poni2_txt)
        return fixed_values

    def get_float_from_txt_field(self, txt_field):
        if len(txt_field.text()) > 0:
            return float(txt_field.text())
        else:
            return 0

    def set_calibration_parameters(self, pyFAI_parameter, fit2d_parameter):
        self.set_pyFAI_parameter(pyFAI_parameter)
        self.set_fit2d_parameter(fit2d_parameter)

    def set_pyFAI_parameter(self, pyfai_parameter):
        """
        Sets the values of the pyFAI widgets.
        :param pyfai_parameter: dictionary with the following keys: dist, poni1, poni2, rot1, rot2, rot3, wavelength
            polarization_factor, pixel1, pixel2
        """
        pyfai_widget = self.calibration_control_widget.pyfai_parameters_widget
        sv_gb = self.calibration_control_widget.calibration_parameters_widget.start_values_gb
        detector_gb = self.calibration_control_widget.calibration_parameters_widget.detector_gb
        try:
            pyfai_widget.distance_txt.setText('%.6f' % (pyfai_parameter['dist'] * 1000))
            pyfai_widget.poni1_txt.setText('%.6f' % (pyfai_parameter['poni1']))
            pyfai_widget.poni2_txt.setText('%.6f' % (pyfai_parameter['poni2']))
            pyfai_widget.rotation1_txt.setText('%.8f' % (pyfai_parameter['rot1']))
            pyfai_widget.rotation2_txt.setText('%.8f' % (pyfai_parameter['rot2']))
            pyfai_widget.rotation3_txt.setText('%.8f' % (pyfai_parameter['rot3']))
            pyfai_widget.wavelength_txt.setText('%.6f' % (pyfai_parameter['wavelength'] * 1e10))
            pyfai_widget.polarization_txt.setText('%.3f' % (pyfai_parameter['polarization_factor']))
            pyfai_widget.pixel_height_txt.setText('%.4f' % (pyfai_parameter['pixel1'] * 1e6))
            pyfai_widget.pixel_width_txt.setText('%.4f' % (pyfai_parameter['pixel2'] * 1e6))

            sv_gb.wavelength_txt.setText('%.6f' % (pyfai_parameter['wavelength'] * 1e10))
            sv_gb.polarization_txt.setText('%.3f' % (pyfai_parameter['polarization_factor']))
            self.set_pixel_size(pyfai_parameter['pixel2'], pyfai_parameter['pixel1'])
        except (AttributeError, TypeError):
            pyfai_widget.distance_txt.setText('')
            pyfai_widget.poni1_txt.setText('')
            pyfai_widget.poni2_txt.setText('')
            pyfai_widget.rotation1_txt.setText('')
            pyfai_widget.rotation2_txt.setText('')
            pyfai_widget.rotation3_txt.setText('')
            pyfai_widget.wavelength_txt.setText('')
            pyfai_widget.polarization_txt.setText('')
            pyfai_widget.pixel_width_txt.setText('')
            pyfai_widget.pixel_height_txt.setText('')

    def get_pyFAI_parameter(self):
        """
        Gets the pyFAI parameter values from the pyFAI widgets.
        :return: dictionary with the following keys: dist, poni1, poni2, rot1, rot2, rot3, wavelength
            polarization_factor, pixel1, pixel2
        """
        pyfai_widget = self.calibration_control_widget.pyfai_parameters_widget
        pyfai_parameter = {'dist': float(pyfai_widget.distance_txt.text()) / 1000,
                           'poni1': float(pyfai_widget.poni1_txt.text()),
                           'poni2': float(pyfai_widget.poni2_txt.text()),
                           'rot1': float(pyfai_widget.rotation1_txt.text()),
                           'rot2': float(pyfai_widget.rotation2_txt.text()),
                           'rot3': float(pyfai_widget.rotation3_txt.text()),
                           'wavelength': float(pyfai_widget.wavelength_txt.text()) / 1e10,
                           'polarization_factor': float(pyfai_widget.polarization_txt.text()),
                           'pixel1': float(pyfai_widget.pixel_height_txt.text()) / 1e6,
                           'pixel2': float(pyfai_widget.pixel_width_txt.text()) / 1e6}
        return pyfai_parameter

    def set_fit2d_parameter(self, fit2d_parameter):
        """
        Sets the values of the fit2d parameter widgets with the appropriate number formatting.
        :param fit2d_parameter: dictionary with the following keys: directDist, centerX, centerY, tilt,
            tiltPlanRotation, wavelength, pixelX, pixelY
        """
        fit2d_widget = self.calibration_control_widget.fit2d_parameters_widget
        try:
            fit2d_widget.distance_txt.setText('%.4f' % (fit2d_parameter['directDist']))
            fit2d_widget.center_x_txt.setText('%.3f' % (fit2d_parameter['centerX']))
            fit2d_widget.center_y_txt.setText('%.3f' % (fit2d_parameter['centerY']))
            fit2d_widget.tilt_txt.setText('%.6f' % (fit2d_parameter['tilt']))
            fit2d_widget.rotation_txt.setText('%.6f' % (fit2d_parameter['tiltPlanRotation']))
            fit2d_widget.wavelength_txt.setText('%.4f' % (fit2d_parameter['wavelength'] * 1e10))
            fit2d_widget.polarization_txt.setText('%.3f' % (fit2d_parameter['polarization_factor']))
            fit2d_widget.pixel_width_txt.setText('%.4f' % (fit2d_parameter['pixelX']))
            fit2d_widget.pixel_height_txt.setText('%.4f' % (fit2d_parameter['pixelY']))
        except (AttributeError, TypeError):
            fit2d_widget.distance_txt.setText('')
            fit2d_widget.center_x_txt.setText('')
            fit2d_widget.center_y_txt.setText('')
            fit2d_widget.tilt_txt.setText('')
            fit2d_widget.rotation_txt.setText('')
            fit2d_widget.wavelength_txt.setText('')
            fit2d_widget.polarization_txt.setText('')
            fit2d_widget.pixel_width_txt.setText('')
            fit2d_widget.pixel_height_txt.setText('')

    def get_fit2d_parameter(self):
        """
        Gets the values of the fit2d parameter widgets.
        :return: dictionary with the following keys: directDist, centerX, centerY, tilt,
            tiltPlanRotation, wavelength, pixelX, pixelY
        """
        fit2d_widget = self.calibration_control_widget.fit2d_parameters_widget
        fit2d_parameter = {'directDist': float(fit2d_widget.distance_txt.text()),
                           'centerX': float(fit2d_widget.center_x_txt.text()),
                           'centerY': float(fit2d_widget.center_y_txt.text()),
                           'tilt': float(fit2d_widget.tilt_txt.text()),
                           'tiltPlanRotation': float(fit2d_widget.rotation_txt.text()),
                           'wavelength': float(fit2d_widget.wavelength_txt.text()) / 1e10,
                           'polarization_factor': float(fit2d_widget.polarization_txt.text()),
                           'pixelX': float(fit2d_widget.pixel_width_txt.text()),
                           'pixelY': float(fit2d_widget.pixel_height_txt.text())}
        return fit2d_parameter


class CalibrationDisplayWidget(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super(CalibrationDisplayWidget, self).__init__(*args, **kwargs)

        self._layout = QtWidgets.QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

        self.img_layout_widget = GraphicsLayoutWidget()
        self.cake_layout_widget = GraphicsLayoutWidget()
        self.pattern_layout_widget = GraphicsLayoutWidget()

        self.img_widget = MaskImgWidget(self.img_layout_widget)
        self.cake_widget = CalibrationCakeWidget(self.cake_layout_widget)
        self.pattern_widget = PatternWidget(self.pattern_layout_widget)

        self.tab_widget = QtWidgets.QTabWidget()
        self.tab_widget.addTab(self.img_layout_widget, 'Image')
        self.tab_widget.addTab(self.cake_layout_widget, 'Cake')
        self.tab_widget.addTab(self.pattern_layout_widget, 'Pattern')
        self._layout.addWidget(self.tab_widget)

        self._status_layout = QtWidgets.QHBoxLayout()
        self._status_layout.setContentsMargins(6, 0, 0, 0)
        self.calibrate_btn = QtWidgets.QPushButton("Calibrate")
        self.refine_btn = QtWidgets.QPushButton("Refine")
        self.position_lbl = QtWidgets.QLabel("position_lbl")

        self._status_layout.addWidget(self.calibrate_btn)
        self._status_layout.addWidget(self.refine_btn)
        self._status_layout.addSpacerItem(QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Expanding,
                                                                QtWidgets.QSizePolicy.Minimum))
        self._status_layout.addWidget(self.position_lbl)
        self._layout.addLayout(self._status_layout)

        self.setLayout(self._layout)
        self.style_widgets()

    def style_widgets(self):
        self.pattern_widget.deactivate_pos_line()
        self.calibrate_btn.setMinimumWidth(130)
        self.refine_btn.setMinimumWidth(130)


class CalibrationControlWidget(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super(CalibrationControlWidget, self).__init__(*args, **kwargs)

        self._layout = QtWidgets.QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

        self._file_layout = QtWidgets.QHBoxLayout()
        self.load_img_btn = QtWidgets.QPushButton("Load Image File", self)
        self.load_previous_img_btn = QtWidgets.QPushButton("<", self)
        self.load_next_img_btn = QtWidgets.QPushButton(">", self)

        self._file_layout.addWidget(self.load_img_btn)
        self._file_layout.addWidget(self.load_previous_img_btn)
        self._file_layout.addWidget(self.load_next_img_btn)

        self._layout.addLayout(self._file_layout)

        self.filename_txt = QtWidgets.QLineEdit('', self)
        self._layout.addWidget(self.filename_txt)

        self.toolbox = QtWidgets.QToolBox()
        self.calibration_parameters_widget = CalibrationParameterWidget()
        self.pyfai_parameters_widget = PyfaiParametersWidget()
        self.fit2d_parameters_widget = Fit2dParametersWidget()

        self.toolbox.addItem(self.calibration_parameters_widget, "Calibration Parameters")
        self.toolbox.addItem(self.pyfai_parameters_widget, 'pyFAI Parameters')
        self.toolbox.addItem(self.fit2d_parameters_widget, 'Fit2d Parameters')
        self._layout.addWidget(self.toolbox)

        self._bottom_layout = QtWidgets.QHBoxLayout()
        self.load_calibration_btn = QtWidgets.QPushButton('Load Calibration')
        self.save_calibration_btn = QtWidgets.QPushButton('Save Calibration')
        self._bottom_layout.addWidget(self.load_calibration_btn)
        self._bottom_layout.addWidget(self.save_calibration_btn)
        self._layout.addLayout(self._bottom_layout)

        self.style_widgets()

    def style_widgets(self):
        self.load_previous_img_btn.setMaximumWidth(50)
        self.load_next_img_btn.setMaximumWidth(50)
        self.setMaximumWidth(310)
        self.setMinimumWidth(310)


class CalibrationParameterWidget(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super(CalibrationParameterWidget, self).__init__(*args, **kwargs)

        self._layout = QtWidgets.QVBoxLayout(self)

        self.detector_gb = DetectorGroupbox()
        self.start_values_gb = StartValuesGroupBox(self)
        self.peak_selection_gb = PeakSelectionGroupBox()
        self.refinement_options_gb = RefinementOptionsGroupBox()

        self._layout.addWidget(self.detector_gb)
        self._layout.addWidget(self.start_values_gb)
        self._layout.addWidget(self.peak_selection_gb)
        self._layout.addWidget(self.refinement_options_gb)
        self._layout.addSpacerItem(QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Expanding,
                                                         QtWidgets.QSizePolicy.Expanding))

        self.setLayout(self._layout)
        if sys.platform.startswith('linux'):
            self.setMaximumWidth(295)


class DetectorGroupbox(QtWidgets.QGroupBox):
    def __init__(self, *args, **kwargs):
        super(DetectorGroupbox, self).__init__('Detector', *args, **kwargs)

        self._layout = QtWidgets.QVBoxLayout(self)

        self.detector_cb = CleanLooksComboBox()

        self.detector_name_lbl = LabelAlignRight()
        self.detector_name_lbl.hide()

        self.detector_load_btn = OpenIconButton()
        self.detector_load_btn.setIconSize(QtCore.QSize(13, 13))
        self.detector_load_btn.setMaximumWidth(21)
        self.detector_load_btn.setToolTip('Open Detector File')

        self.detector_reset_btn = ResetIconButton()
        self.detector_reset_btn.setIconSize(QtCore.QSize(13, 13))
        self.detector_reset_btn.setMaximumWidth(21)
        self.detector_reset_btn.setToolTip('Reset Detector')
        self.detector_reset_btn.setDisabled(True)

        self._detector_layout = QtWidgets.QHBoxLayout()
        self._detector_layout.addWidget(self.detector_cb)
        self._detector_layout.addWidget(self.detector_name_lbl)
        self._detector_layout.addWidget(self.detector_load_btn)
        self._detector_layout.addWidget(self.detector_reset_btn)

        self._layout.addLayout(self._detector_layout)

        self._grid_layout1 = QtWidgets.QGridLayout()

        self._grid_layout1.addWidget(LabelAlignRight('Pixel width:'), 1, 0)
        self.pixel_width_txt = NumberTextField('79')
        self._grid_layout1.addWidget(self.pixel_width_txt, 1, 1)
        self._grid_layout1.addWidget(QtWidgets.QLabel('um'), 1, 2)

        self._grid_layout1.addWidget(LabelAlignRight('Pixel height:'), 2, 0)
        self.pixel_height_txt = NumberTextField('79')
        self._grid_layout1.addWidget(self.pixel_height_txt, 2, 1)
        self._grid_layout1.addWidget(QtWidgets.QLabel('um'), 2, 2)

        self.spline_name_txt = QtWidgets.QLabel('None')
        self.spline_load_btn = OpenIconButton()
        self.spline_load_btn.setIconSize(QtCore.QSize(13, 13))
        self.spline_load_btn.setMaximumWidth(21)
        self.spline_load_btn.setToolTip('Open Spline File')

        self.spline_reset_btn = ResetIconButton()
        self.spline_reset_btn.setIconSize(QtCore.QSize(13, 13))
        self.spline_reset_btn.setMaximumWidth(21)
        self.spline_reset_btn.setToolTip('Reset distortion correction')
        self.spline_reset_btn.setDisabled(True)

        self._grid_layout1.addWidget(LabelAlignRight('Distortion:'), 3, 0)
        self._grid_layout1.addWidget(self.spline_name_txt, 3, 1)
        self._grid_layout1.addWidget(self.spline_load_btn, 3, 2)
        self._grid_layout1.addWidget(self.spline_reset_btn, 3, 3)

        self._layout.addLayout(self._grid_layout1)

        self.setLayout(self._layout)


class StartValuesGroupBox(QtWidgets.QGroupBox):
    def __init__(self, *args, **kwargs):
        super(StartValuesGroupBox, self).__init__('Start values', *args, **kwargs)

        self._layout = QtWidgets.QVBoxLayout(self)

        self._grid_layout1 = QtWidgets.QGridLayout()

        self._grid_layout1.addWidget(LabelAlignRight('Distance:'), 0, 0)

        self.distance_txt = NumberTextField('200')
        self.distance_cb = QtWidgets.QCheckBox()
        self.distance_cb.setChecked(True)

        self._grid_layout1.addWidget(self.distance_txt, 0, 1)
        self._grid_layout1.addWidget(QtWidgets.QLabel('mm'), 0, 2)
        self._grid_layout1.addWidget(self.distance_cb, 0, 3)

        self._grid_layout1.addWidget(LabelAlignRight('Wavelength:'), 1, 0)

        self.wavelength_txt = NumberTextField('0.3344')
        self.wavelength_cb = QtWidgets.QCheckBox()

        self._grid_layout1.addWidget(self.wavelength_txt, 1, 1)
        self._grid_layout1.addWidget(QtWidgets.QLabel('A'), 1, 2)
        self._grid_layout1.addWidget(self.wavelength_cb, 1, 3)

        self._grid_layout1.addWidget(LabelAlignRight('Polarization:'), 2, 0)
        self.polarization_txt = NumberTextField('0.99')
        self._grid_layout1.addWidget(self.polarization_txt, 2, 1)

        self._grid_layout1.addWidget(LabelAlignRight('Calibrant:'), 5, 0)
        self.calibrant_cb = CleanLooksComboBox()
        self._grid_layout1.addWidget(self.calibrant_cb, 5, 1, 1, 2)

        self._grid_layout2 = QtWidgets.QGridLayout()
        self._grid_layout2.setSpacing(6)

        self.rotate_p90_btn = QtWidgets.QPushButton('Rotate +90')
        self.rotate_m90_btn = QtWidgets.QPushButton('Rotate -90', self)
        self._grid_layout2.addWidget(self.rotate_p90_btn, 1, 0)
        self._grid_layout2.addWidget(self.rotate_m90_btn, 1, 1)

        self.flip_horizontal_btn = QtWidgets.QPushButton('Flip horizontal', self)
        self.flip_vertical_btn = QtWidgets.QPushButton('Flip vertical', self)
        self._grid_layout2.addWidget(self.flip_horizontal_btn, 2, 0)
        self._grid_layout2.addWidget(self.flip_vertical_btn, 2, 1)

        self.reset_transformations_btn = QtWidgets.QPushButton('Reset transformations', self)
        self._grid_layout2.addWidget(self.reset_transformations_btn, 3, 0, 1, 2)

        self._layout.addLayout(self._grid_layout1)
        self._layout.addLayout(self._grid_layout2)

        self.setLayout(self._layout)


class PeakSelectionGroupBox(QtWidgets.QGroupBox):
    def __init__(self):
        super(PeakSelectionGroupBox, self).__init__('Peak Selection')

        self._layout = QtWidgets.QGridLayout()
        self._layout.setVerticalSpacing(3)
        self._layout.setHorizontalSpacing(6)
        self._layout.addItem(QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Expanding,
                                                   QtWidgets.QSizePolicy.Minimum), 0, 0)
        self._layout.addWidget(LabelAlignRight('Current Ring Number:'), 0, 1, 1, 2)
        self.peak_num_sb = SpinBoxAlignRight()
        self.peak_num_sb.setValue(1)
        self.peak_num_sb.setMinimum(1)
        self._layout.addWidget(self.peak_num_sb, 0, 3)

        self._layout.addItem(QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Expanding,
                                                   QtWidgets.QSizePolicy.Minimum), 1, 0, 1, 2)
        self.automatic_peak_num_inc_cb = QtWidgets.QCheckBox('automatic increase')
        self.automatic_peak_num_inc_cb.setChecked(True)
        self._layout.addWidget(self.automatic_peak_num_inc_cb, 1, 2, 1, 2)

        self.automatic_peak_search_rb = QtWidgets.QRadioButton('automatic peak search')
        self.automatic_peak_search_rb.setChecked(True)
        self.select_peak_rb = QtWidgets.QRadioButton('single peak search')
        self._layout.addWidget(self.automatic_peak_search_rb, 2, 0, 1, 4)
        self._layout.addWidget(self.select_peak_rb, 3, 0, 1, 4)

        self._layout.addWidget(LabelAlignRight('Search size:'), 4, 0)
        self.search_size_sb = SpinBoxAlignRight()
        self.search_size_sb.setValue(10)
        self.search_size_sb.setMaximumWidth(50)
        self._layout.addWidget(self.search_size_sb, 4, 1, 1, 2)
        self._layout.addItem(QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Expanding,
                                                   QtWidgets.QSizePolicy.Minimum), 4, 2, 1, 2)

        self.undo_peaks_btn = QtWidgets.QPushButton("Undo")
        self.clear_peaks_btn = QtWidgets.QPushButton("Clear All Peaks")

        self._peak_btn_layout = QtWidgets.QHBoxLayout()
        self._peak_btn_layout.setSpacing(6)
        self._peak_btn_layout.addWidget(self.undo_peaks_btn)
        self._peak_btn_layout.addWidget(self.clear_peaks_btn)
        self._layout.addLayout(self._peak_btn_layout, 5, 0, 1, 4)

        self.setLayout(self._layout)


class RefinementOptionsGroupBox(QtWidgets.QGroupBox):
    def __init__(self):
        super(RefinementOptionsGroupBox, self).__init__('Refinement Options')

        self._layout = QtWidgets.QGridLayout()

        self.automatic_refinement_cb = QtWidgets.QCheckBox('automatic refinement')
        self.automatic_refinement_cb.setChecked(True)
        self._layout.addWidget(self.automatic_refinement_cb, 0, 0, 1, 1)

        self.use_mask_cb = QtWidgets.QCheckBox('use mask')
        self._layout.addWidget(self.use_mask_cb, 1, 0)

        self.mask_transparent_cb = QtWidgets.QCheckBox('transparent')
        self._layout.addWidget(self.mask_transparent_cb, 1, 1)

        self._layout.addWidget(LabelAlignRight('Peak Search Algorithm:'), 2, 0)
        self.peak_search_algorithm_cb = CleanLooksComboBox()
        self.peak_search_algorithm_cb.addItems(['Massif', 'Blob'])
        self._layout.addWidget(self.peak_search_algorithm_cb, 2, 1)

        self._layout.addWidget(LabelAlignRight('Delta 2Th:'), 3, 0)
        self.delta_tth_txt = NumberTextField('0.1')
        self._layout.addWidget(self.delta_tth_txt, 3, 1)

        self._layout.addWidget(LabelAlignRight('Intensity Mean Factor:'), 4, 0)
        self.intensity_mean_factor_sb = DoubleSpinBoxAlignRight()
        self.intensity_mean_factor_sb.setValue(3.0)
        self.intensity_mean_factor_sb.setSingleStep(0.1)
        self._layout.addWidget(self.intensity_mean_factor_sb, 4, 1)

        self._layout.addWidget(LabelAlignRight('Intensity Limit:'), 5, 0)
        self.intensity_limit_txt = NumberTextField('55000')
        self._layout.addWidget(self.intensity_limit_txt, 5, 1)

        self._layout.addWidget(LabelAlignRight('Number of rings:'), 6, 0)
        self.number_of_rings_sb = SpinBoxAlignRight()
        self.number_of_rings_sb.setValue(15)
        self._layout.addWidget(self.number_of_rings_sb, 6, 1)

        self.setLayout(self._layout)


class PyfaiParametersWidget(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super(PyfaiParametersWidget, self).__init__(*args, **kwargs)

        self._layout = QtWidgets.QGridLayout()

        self._layout.addWidget(LabelAlignRight('Distance:'), 0, 0)
        self.distance_txt = NumberTextField()
        self.distance_cb = QtWidgets.QCheckBox()
        self.distance_cb.setChecked(True)
        self._layout.addWidget(self.distance_txt, 0, 1)
        self._layout.addWidget(QtWidgets.QLabel('mm'), 0, 2)
        self._layout.addWidget(self.distance_cb, 0, 3)

        self._layout.addWidget(LabelAlignRight('Wavelength:'), 1, 0)
        self.wavelength_txt = NumberTextField()
        self.wavelength_cb = QtWidgets.QCheckBox()
        self._layout.addWidget(self.wavelength_txt, 1, 1)
        self._layout.addWidget(QtWidgets.QLabel('A'), 1, 2)
        self._layout.addWidget(self.wavelength_cb, 1, 3)

        self._layout.addWidget(LabelAlignRight('Polarization:'), 2, 0)
        self.polarization_txt = NumberTextField()
        self._layout.addWidget(self.polarization_txt, 2, 1)

        self._layout.addWidget(LabelAlignRight('PONI:'), 3, 0)
        self.poni1_txt = NumberTextField()
        self.poni1_cb = QtWidgets.QCheckBox()
        self.poni1_cb.setChecked(True)
        self._layout.addWidget(self.poni1_txt, 3, 1)
        self._layout.addWidget(QtWidgets.QLabel('m'), 3, 2)
        self._layout.addWidget(self.poni1_cb, 3, 3)

        self.poni2_txt = NumberTextField()
        self.poni2_cb = QtWidgets.QCheckBox()
        self.poni2_cb.setChecked(True)
        self._layout.addWidget(self.poni2_txt, 4, 1)
        self._layout.addWidget(QtWidgets.QLabel('m'), 4, 2)
        self._layout.addWidget(self.poni2_cb, 4, 3)

        self._layout.addWidget(LabelAlignRight('Rotations'), 5, 0)
        self.rotation1_txt = NumberTextField()
        self.rotation2_txt = NumberTextField()
        self.rotation3_txt = NumberTextField()
        self.rotation1_cb = QtWidgets.QCheckBox()
        self.rotation2_cb = QtWidgets.QCheckBox()
        self.rotation3_cb = QtWidgets.QCheckBox()
        self.rotation1_cb.setChecked(True)
        self.rotation2_cb.setChecked(True)
        self.rotation3_cb.setChecked(True)
        self._layout.addWidget(self.rotation1_txt, 5, 1)
        self._layout.addWidget(self.rotation2_txt, 6, 1)
        self._layout.addWidget(self.rotation3_txt, 7, 1)
        self._layout.addWidget(QtWidgets.QLabel('rad'), 5, 2)
        self._layout.addWidget(QtWidgets.QLabel('rad'), 6, 2)
        self._layout.addWidget(QtWidgets.QLabel('rad'), 7, 2)
        self._layout.addWidget(self.rotation1_cb, 5, 3)
        self._layout.addWidget(self.rotation2_cb, 6, 3)
        self._layout.addWidget(self.rotation3_cb, 7, 3)

        self._layout.addWidget(LabelAlignRight('Pixel width:'), 8, 0)
        self.pixel_width_txt = NumberTextField()
        self._layout.addWidget(self.pixel_width_txt, 8, 1)
        self._layout.addWidget(QtWidgets.QLabel('um'))

        self._layout.addWidget(LabelAlignRight('Pixel height:'), 9, 0)
        self.pixel_height_txt = NumberTextField()
        self._layout.addWidget(self.pixel_height_txt, 9, 1)
        self._layout.addWidget(QtWidgets.QLabel('um'))

        self.update_btn = QtWidgets.QPushButton('update')
        self._layout.addWidget(self.update_btn, 10, 0, 1, 4)

        self._layout.addItem(
            QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding),
            11, 0, 1, 4)

        self.setLayout(self._layout)


class Fit2dParametersWidget(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super(Fit2dParametersWidget, self).__init__(*args, **kwargs)

        self._layout = QtWidgets.QGridLayout()

        self._layout.addWidget(LabelAlignRight('Distance:'), 0, 0)
        self.distance_txt = NumberTextField()
        self.distance_cb = QtWidgets.QCheckBox()
        self.distance_cb.setChecked(True)
        self._layout.addWidget(self.distance_txt, 0, 1)
        self._layout.addWidget(QtWidgets.QLabel('mm'), 0, 2)
        self._layout.addWidget(self.distance_cb, 0, 3)

        self._layout.addWidget(LabelAlignRight('Wavelength:'), 1, 0)
        self.wavelength_txt = NumberTextField()
        self.wavelength_cb = QtWidgets.QCheckBox()
        self._layout.addWidget(self.wavelength_txt, 1, 1)
        self._layout.addWidget(QtWidgets.QLabel('A'), 1, 2)
        self._layout.addWidget(self.wavelength_cb, 1, 3)

        self._layout.addWidget(LabelAlignRight('Polarization:'), 2, 0)
        self.polarization_txt = NumberTextField()
        self._layout.addWidget(self.polarization_txt, 2, 1)

        self._layout.addWidget(LabelAlignRight('Center X:'), 3, 0)
        self.center_x_txt = NumberTextField()
        self._layout.addWidget(self.center_x_txt, 3, 1)
        self._layout.addWidget(QtWidgets.QLabel('px'), 3, 2)

        self._layout.addWidget(LabelAlignRight('Center Y:'), 4, 0)
        self.center_y_txt = NumberTextField()
        self._layout.addWidget(self.center_y_txt, 4, 1)
        self._layout.addWidget(QtWidgets.QLabel('px'), 4, 2)

        self._layout.addWidget(LabelAlignRight('Rotation:'), 5, 0)
        self.rotation_txt = NumberTextField()
        self._layout.addWidget(self.rotation_txt, 5, 1)
        self._layout.addWidget(QtWidgets.QLabel('deg'), 5, 2)

        self._layout.addWidget(LabelAlignRight('Tilt:'), 6, 0)
        self.tilt_txt = NumberTextField()
        self._layout.addWidget(self.tilt_txt, 6, 1)
        self._layout.addWidget(QtWidgets.QLabel('deg'), 6, 2)

        self._layout.addWidget(LabelAlignRight('Pixel width:'), 8, 0)
        self.pixel_width_txt = NumberTextField()
        self._layout.addWidget(self.pixel_width_txt, 8, 1)
        self._layout.addWidget(QtWidgets.QLabel('um'))

        self._layout.addWidget(LabelAlignRight('Pixel height:'), 9, 0)
        self.pixel_height_txt = NumberTextField()
        self._layout.addWidget(self.pixel_height_txt, 9, 1)
        self._layout.addWidget(QtWidgets.QLabel('um'))

        self.update_btn = QtWidgets.QPushButton('update')
        self._layout.addWidget(self.update_btn, 10, 0, 1, 4)

        self._layout.addItem(
            QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding),
            11, 0, 1, 4)

        self.setLayout(self._layout)
