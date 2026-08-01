# SPDX-License-Identifier: MIT

import os
import sys

from qtpy import QtWidgets, QtGui, QtCore
from pyqtgraph import GraphicsLayoutWidget

from ..widgets.plot_widgets import MaskImgWidget, CalibrationCakeWidget
from ..widgets.plot_widgets import PatternWidget

from .CustomWidgets import NumberTextField, LabelAlignRight, CleanLooksComboBox, SpinBoxAlignRight, \
    DoubleSpinBoxAlignRight, OpenIconButton, ResetIconButton


class StepIndicatorWidget(QtWidgets.QWidget):
    """The "1. Image ▸ 2. Pick Rings ▸ 3. Calibrate" header of the
    calibration wizard.

    Shows which page is current, colors each step by its workflow status
    and lets the user jump to an already reachable step by clicking. The
    reachability and status decisions live in the controller/guide — this
    widget only displays them.
    """

    step_clicked = QtCore.Signal(int)

    STATUS_COLORS = {
        'pending': '#989898',
        'attention': '#ffa726',
        'done': '#66bb6a',
    }

    def __init__(self, titles, parent=None):
        super().__init__(parent)
        self._layout = QtWidgets.QHBoxLayout(self)
        self._layout.setContentsMargins(3, 6, 3, 3)
        self._layout.setSpacing(0)

        self.step_btns = []
        self._statuses = []
        for ind, title in enumerate(titles):
            if ind > 0:
                separator = QtWidgets.QLabel('▸')
                separator.setStyleSheet('color: #787878;')
                self._layout.addWidget(separator)
            btn = QtWidgets.QToolButton()
            btn.setText('{}. {}'.format(ind + 1, title))
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
            btn.clicked.connect(lambda _=False, i=ind: self.step_clicked.emit(i))
            self._layout.addWidget(btn)
            self.step_btns.append(btn)
            self._statuses.append('pending')
        self._layout.addStretch()

        self.set_current_step(0)
        for ind in range(len(self.step_btns)):
            self._style_step(ind)

    def set_current_step(self, index):
        self.step_btns[index].setChecked(True)

    def current_step(self):
        for ind, btn in enumerate(self.step_btns):
            if btn.isChecked():
                return ind
        return 0

    def set_step_status(self, index, status):
        """:param status: one of 'pending', 'attention', 'done'"""
        self._statuses[index] = status
        self._style_step(index)

    def step_status(self, index):
        return self._statuses[index]

    def set_step_enabled(self, index, enabled):
        self.step_btns[index].setEnabled(enabled)

    def _style_step(self, index):
        color = self.STATUS_COLORS[self._statuses[index]]
        self.step_btns[index].setStyleSheet(
            'QToolButton {{ border: none; color: {0}; font-size: 14px;'
            ' padding: 4px 10px; }}'
            'QToolButton:checked {{ font-weight: bold; color: #F1F1F1;'
            ' border-bottom: 2px solid {0}; }}'
            'QToolButton:disabled {{ color: #5B5B5B; }}'.format(color))


class AdvancedExpander(QtWidgets.QWidget):
    """A collapsed-by-default disclosure for options that first-time users
    should not need to touch."""

    def __init__(self, content_widget, parent=None, title='advanced'):
        super().__init__(parent)
        self.content_widget = content_widget

        self.header_btn = QtWidgets.QToolButton()
        self.header_btn.setText(title)
        self.header_btn.setCheckable(True)
        self.header_btn.setChecked(False)
        self.header_btn.setArrowType(QtCore.Qt.RightArrow)
        self.header_btn.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.header_btn.setStyleSheet(
            'QToolButton { border: none; color: #989898; }')
        self.header_btn.toggled.connect(self.set_expanded)

        self._layout = QtWidgets.QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._layout.addWidget(self.header_btn)
        self._layout.addWidget(self.content_widget)

        self.content_widget.hide()

    def set_expanded(self, expanded):
        self.header_btn.setChecked(expanded)
        self.content_widget.setVisible(expanded)
        self.header_btn.setArrowType(
            QtCore.Qt.DownArrow if expanded else QtCore.Qt.RightArrow)

    def is_expanded(self):
        return self.header_btn.isChecked()


class CalibrationWidget(QtWidgets.QWidget):
    """
    Defines the main structure of the calibration widget, which is separated into two parts.
    Calibration Display Widget - shows the image and pattern
    Calibration Control Widget - shows all the controls on the right side of the widget
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setObjectName('calibration_widget')

        self.step_indicator = StepIndicatorWidget(
            ['Image', 'Pick Rings', 'Calibrate'])

        self.calibration_display_widget = CalibrationDisplayWidget(self)
        self.calibration_control_widget = CalibrationControlWidget(self)

        self._content_layout = QtWidgets.QHBoxLayout()
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.addWidget(self.calibration_display_widget)
        self._content_layout.addWidget(self.calibration_control_widget)

        self._layout = QtWidgets.QVBoxLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._layout.addWidget(self.step_indicator)
        self._layout.addLayout(self._content_layout)
        self.setLayout(self._layout)

        self.create_shortcuts()

    def set_wizard_step(self, index):
        """Shows the given wizard page and moves the top step indicator
        along with it."""
        self.calibration_control_widget.calibration_parameters_widget.set_current_step(index)
        self.step_indicator.set_current_step(index)

    def create_shortcuts(self):
        """
        Creates shortcuts for the widgets which are directly interfacing with the controller.
        """
        parameters_widget = self.calibration_control_widget.calibration_parameters_widget
        self.load_img_btn = parameters_widget.load_img_btn
        self.load_next_img_btn = parameters_widget.load_next_img_btn
        self.load_previous_img_btn = parameters_widget.load_previous_img_btn
        self.filename_txt = parameters_widget.filename_txt

        self.save_calibration_btn = parameters_widget.save_calibration_btn
        self.load_calibration_btn = self.calibration_control_widget.load_calibration_btn

        self.calibrate_btn = parameters_widget.calibrate_btn
        self.refine_btn = parameters_widget.refine_btn
        self.pyfai_expander = parameters_widget.pyfai_expander
        self.fit2d_expander = parameters_widget.fit2d_expander
        self.pos_lbl = self.calibration_display_widget.position_lbl

        self.tab_widget = self.calibration_display_widget.tab_widget

        detector_gb = self.calibration_control_widget.calibration_parameters_widget.detector_gb
        self.detectors_cb = detector_gb.detector_cb
        self.detector_name_lbl = detector_gb.detector_name_lbl
        self.detector_load_btn = detector_gb.detector_load_btn
        self.detector_reset_btn = detector_gb.detector_reset_btn
        self.spline_reset_btn = detector_gb.spline_reset_btn
        self.load_spline_btn = detector_gb.spline_load_btn
        self.spline_filename_txt = detector_gb.spline_name_txt

        self.rotate_m90_btn = parameters_widget.rotate_m90_btn
        self.rotate_p90_btn = parameters_widget.rotate_p90_btn
        self.invert_horizontal_btn = parameters_widget.flip_horizontal_btn
        self.invert_vertical_btn = parameters_widget.flip_vertical_btn
        self.reset_transformations_btn = parameters_widget.reset_transformations_btn

        sv_gb = self.calibration_control_widget.calibration_parameters_widget.start_values_gb
        self.calibrant_cb = sv_gb.calibrant_cb

        self.sv_wavelength_txt = sv_gb.wavelength_txt
        self.sv_wavelength_cb = sv_gb.wavelength_cb
        self.sv_energy_txt = sv_gb.energy_txt
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
        self.clear_ring_btn = peak_selection_gb.clear_ring_btn
        self.peak_counter_lbl = peak_selection_gb.peak_counter_lbl

        self.step_stack = parameters_widget.step_stack
        self.wizard_back_btn = parameters_widget.back_btn
        self.wizard_next_btn = parameters_widget.next_btn

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
        sv_gb.update_energy_from_wavelength()

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
            sv_gb.update_energy_from_wavelength()
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
        super().__init__(*args, **kwargs)

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
        self.position_lbl = QtWidgets.QLabel("position_lbl")

        self._status_layout.addSpacerItem(QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Expanding,
                                                                QtWidgets.QSizePolicy.Minimum))
        self._status_layout.addWidget(self.position_lbl)
        self._layout.addLayout(self._status_layout)

        self.setLayout(self._layout)
        self.style_widgets()

    def style_widgets(self):
        self.pattern_widget.deactivate_pos_line()


class CalibrationControlWidget(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._layout = QtWidgets.QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

        self.calibration_parameters_widget = CalibrationParameterWidget()
        self._layout.addWidget(self.calibration_parameters_widget)

        # the wizard owns the step content; these aliases keep the
        # historical access paths working
        self.pyfai_parameters_widget = (
            self.calibration_parameters_widget.pyfai_parameters_widget
        )
        self.fit2d_parameters_widget = (
            self.calibration_parameters_widget.fit2d_parameters_widget
        )

        # loading an existing .poni is the alternative entry into the
        # workflow, so it stays reachable from every step
        self._bottom_layout = QtWidgets.QHBoxLayout()
        self.load_calibration_btn = QtWidgets.QPushButton('Load Calibration')
        self._bottom_layout.addWidget(self.load_calibration_btn)
        self._layout.addLayout(self._bottom_layout)

        self.style_widgets()

    def style_widgets(self):
        parameters_widget = self.calibration_parameters_widget
        parameters_widget.load_previous_img_btn.setMaximumWidth(50)
        parameters_widget.load_next_img_btn.setMaximumWidth(50)
        self.setMaximumWidth(310)
        self.setMinimumWidth(310)


class CalibrationParameterWidget(QtWidgets.QWidget):
    """The calibration wizard: one page per workflow step, a step
    indicator on top and Back/Next navigation below.

    Page 1 — load and orient the image, describe the detector.
    Page 2 — pick peaks on the diffraction rings.
    Page 3 — calibrant and start values, refinement options.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._layout = QtWidgets.QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(6)

        # --- page 1: image & detector -----------------------------------
        self._file_layout = QtWidgets.QHBoxLayout()
        self.load_img_btn = QtWidgets.QPushButton("Load Image File", self)
        self.load_previous_img_btn = QtWidgets.QPushButton("<", self)
        self.load_next_img_btn = QtWidgets.QPushButton(">", self)

        self._file_layout.addWidget(self.load_img_btn)
        self._file_layout.addWidget(self.load_previous_img_btn)
        self._file_layout.addWidget(self.load_next_img_btn)

        self.filename_txt = QtWidgets.QLineEdit('', self)

        self.rotate_p90_btn = QtWidgets.QPushButton('Rotate +90')
        self.rotate_m90_btn = QtWidgets.QPushButton('Rotate -90')
        self.flip_horizontal_btn = QtWidgets.QPushButton('Flip horizontal')
        self.flip_vertical_btn = QtWidgets.QPushButton('Flip vertical')
        self.reset_transformations_btn = QtWidgets.QPushButton('Reset transformations')

        self._transformation_layout = QtWidgets.QGridLayout()
        self._transformation_layout.setSpacing(6)
        self._transformation_layout.addWidget(self.rotate_p90_btn, 0, 0)
        self._transformation_layout.addWidget(self.rotate_m90_btn, 0, 1)
        self._transformation_layout.addWidget(self.flip_horizontal_btn, 1, 0)
        self._transformation_layout.addWidget(self.flip_vertical_btn, 1, 1)
        self._transformation_layout.addWidget(self.reset_transformations_btn, 2, 0, 1, 2)

        self.detector_gb = DetectorGroupbox()

        self.image_page = QtWidgets.QWidget()
        self._image_page_layout = QtWidgets.QVBoxLayout(self.image_page)
        self._image_page_layout.setContentsMargins(0, 0, 0, 0)
        self._image_page_layout.addLayout(self._file_layout)
        self._image_page_layout.addWidget(self.filename_txt)
        self._image_page_layout.addLayout(self._transformation_layout)
        self._image_page_layout.addWidget(self.detector_gb)
        self._image_page_layout.addStretch()

        # --- page 2: peak picking ---------------------------------------
        self.peak_selection_gb = PeakSelectionGroupBox()
        self.peak_selection_gb.setTitle('')

        self.peaks_page = QtWidgets.QWidget()
        self._peaks_page_layout = QtWidgets.QVBoxLayout(self.peaks_page)
        self._peaks_page_layout.setContentsMargins(0, 0, 0, 0)
        self._peaks_page_layout.addWidget(self.peak_selection_gb)
        self._peaks_page_layout.addStretch()

        # --- page 3: calibrant, start values, calibrate & results -------
        self.start_values_gb = StartValuesGroupBox(self)
        self.refinement_options_gb = RefinementOptionsGroupBox()

        self.calibrate_btn = QtWidgets.QPushButton('Calibrate')
        self.calibrate_btn.setProperty('primary', True)
        self.calibrate_btn.setMinimumHeight(28)
        self.refine_btn = QtWidgets.QPushButton('Refine')
        self._action_layout = QtWidgets.QHBoxLayout()
        self._action_layout.addWidget(self.calibrate_btn)
        self._action_layout.addWidget(self.refine_btn)

        # the fitted parameters are the *result* of the workflow — they
        # appear (collapsed) only once a calibration exists
        self.pyfai_parameters_widget = PyfaiParametersWidget()
        self.fit2d_parameters_widget = Fit2dParametersWidget()
        self.pyfai_expander = AdvancedExpander(
            self.pyfai_parameters_widget, title='pyFAI parameters')
        self.fit2d_expander = AdvancedExpander(
            self.fit2d_parameters_widget, title='Fit2d parameters')

        self.save_calibration_btn = QtWidgets.QPushButton('Save Calibration')
        self.save_calibration_btn.setProperty('primary', True)
        self.save_calibration_btn.setMinimumHeight(28)

        self.calibrate_page = QtWidgets.QWidget()
        self._calibrate_page_layout = QtWidgets.QVBoxLayout(self.calibrate_page)
        self._calibrate_page_layout.setContentsMargins(0, 0, 0, 0)
        self._calibrate_page_layout.setSpacing(12)
        self._calibrate_page_layout.addWidget(self.start_values_gb)
        self._calibrate_page_layout.addWidget(self.refinement_options_gb)
        self._calibrate_page_layout.addLayout(self._action_layout)
        self._calibrate_page_layout.addWidget(self.pyfai_expander)
        self._calibrate_page_layout.addWidget(self.fit2d_expander)
        self._calibrate_page_layout.addWidget(self.save_calibration_btn)
        self._calibrate_page_layout.addStretch()

        # --- wizard chrome ----------------------------------------------
        self.step_stack = QtWidgets.QStackedWidget()
        self.step_stack.addWidget(self.image_page)
        self.step_stack.addWidget(self.peaks_page)
        self.step_stack.addWidget(self.calibrate_page)

        self._scroll_area = QtWidgets.QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        self._scroll_area.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarAlwaysOff)
        self._scroll_area.setWidget(self.step_stack)

        self.back_btn = QtWidgets.QPushButton('< Back')
        self.next_btn = QtWidgets.QPushButton('Next >')
        self.next_btn.setProperty('primary', True)
        self._nav_layout = QtWidgets.QHBoxLayout()
        self._nav_layout.addWidget(self.back_btn)
        self._nav_layout.addStretch()
        self._nav_layout.addWidget(self.next_btn)

        self._layout.addWidget(self._scroll_area)
        self._layout.addLayout(self._nav_layout)

        self.setLayout(self._layout)
        if sys.platform.startswith('linux'):
            self.setMaximumWidth(295)

    def current_step(self):
        return self.step_stack.currentIndex()

    def set_current_step(self, index):
        """Shows the given wizard page; navigation gating stays with the
        controller, which calls this only for allowed transitions."""
        self.step_stack.setCurrentIndex(index)


class DetectorGroupbox(QtWidgets.QGroupBox):
    def __init__(self, *args, **kwargs):
        super().__init__('Detector', *args, **kwargs)

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
        super().__init__('Start values', *args, **kwargs)

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

        self._grid_layout1.addWidget(LabelAlignRight('Energy:'), 2, 0)
        self.energy_txt = NumberTextField()
        self._grid_layout1.addWidget(self.energy_txt, 2, 1)
        self._grid_layout1.addWidget(QtWidgets.QLabel('keV'), 2, 2)

        self._grid_layout1.addWidget(LabelAlignRight('Polarization:'), 3, 0)
        self.polarization_txt = NumberTextField('0.99')
        self._grid_layout1.addWidget(self.polarization_txt, 3, 1)

        self._grid_layout1.addWidget(LabelAlignRight('Calibrant:'), 5, 0)
        self.calibrant_cb = CleanLooksComboBox()
        self._grid_layout1.addWidget(self.calibrant_cb, 5, 1, 1, 2)

        self._layout.addLayout(self._grid_layout1)

        self.setLayout(self._layout)
        self.update_energy_from_wavelength()

    #: hc in keV·Å for photon energy/wavelength conversion
    HC_KEV_ANGSTROM = 12.398419843320026

    def update_energy_from_wavelength(self):
        """Recomputes the energy display from the wavelength field."""
        try:
            wavelength = float(self.wavelength_txt.text())
            self.energy_txt.setText('%.4f' % (self.HC_KEV_ANGSTROM / wavelength))
        except (ValueError, ZeroDivisionError):
            self.energy_txt.setText('')

    def update_wavelength_from_energy(self):
        """Recomputes the wavelength field from the energy display."""
        try:
            energy = float(self.energy_txt.text())
            self.wavelength_txt.setText('%.6f' % (self.HC_KEV_ANGSTROM / energy))
        except (ValueError, ZeroDivisionError):
            pass


class PeakSelectionGroupBox(QtWidgets.QGroupBox):
    def __init__(self):
        super().__init__('Peak Selection')

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

        self.clear_ring_btn = QtWidgets.QPushButton("Clear Ring")
        self.clear_peaks_btn = QtWidgets.QPushButton("Clear All")

        self._peak_btn_layout = QtWidgets.QHBoxLayout()
        self._peak_btn_layout.setSpacing(6)
        self._peak_btn_layout.addWidget(self.clear_ring_btn)
        self._peak_btn_layout.addWidget(self.clear_peaks_btn)
        self._layout.addLayout(self._peak_btn_layout, 2, 0, 1, 4)

        self.peak_counter_lbl = QtWidgets.QLabel('No peaks selected')
        self.peak_counter_lbl.setStyleSheet('color: #787878; font-style: italic;')
        self._layout.addWidget(self.peak_counter_lbl, 3, 0, 1, 4)

        # search mode and size are expert options — collapsed by default
        self.automatic_peak_search_rb = QtWidgets.QRadioButton('automatic peak search')
        self.automatic_peak_search_rb.setChecked(True)
        self.select_peak_rb = QtWidgets.QRadioButton('single peak search')

        self.search_size_sb = SpinBoxAlignRight()
        self.search_size_sb.setValue(10)
        self.search_size_sb.setMaximumWidth(50)

        advanced_content = QtWidgets.QWidget()
        self._advanced_layout = QtWidgets.QGridLayout(advanced_content)
        self._advanced_layout.setContentsMargins(0, 0, 0, 0)
        self._advanced_layout.setVerticalSpacing(3)
        self._advanced_layout.addWidget(self.automatic_peak_search_rb, 0, 0, 1, 3)
        self._advanced_layout.addWidget(self.select_peak_rb, 1, 0, 1, 3)
        self._advanced_layout.addWidget(LabelAlignRight('Search size:'), 2, 0)
        self._advanced_layout.addWidget(self.search_size_sb, 2, 1)
        self._advanced_layout.addItem(
            QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Expanding,
                                  QtWidgets.QSizePolicy.Minimum), 2, 2)

        self.advanced_expander = AdvancedExpander(advanced_content)
        self._layout.addWidget(self.advanced_expander, 4, 0, 1, 4)

        self.setLayout(self._layout)


class RefinementOptionsGroupBox(QtWidgets.QGroupBox):
    def __init__(self):
        super().__init__('Refinement Options')

        self._layout = QtWidgets.QGridLayout()
        self._layout.setSpacing(3)
        self._layout.setContentsMargins(6, 8, 6, 6)

        self.automatic_refinement_cb = QtWidgets.QCheckBox('automatic refinement')
        self.automatic_refinement_cb.setChecked(True)
        self._layout.addWidget(self.automatic_refinement_cb, 0, 0, 1, 1)

        self.use_mask_cb = QtWidgets.QCheckBox('use mask')
        self._layout.addWidget(self.use_mask_cb, 1, 0)

        self.mask_transparent_cb = QtWidgets.QCheckBox('transparent')
        self._layout.addWidget(self.mask_transparent_cb, 1, 1)

        # refinement tuning parameters are expert options — collapsed by default
        self.peak_search_algorithm_cb = CleanLooksComboBox()
        self.peak_search_algorithm_cb.addItems(['Massif', 'Blob'])

        self.delta_tth_txt = NumberTextField('0.1')

        self.intensity_mean_factor_sb = DoubleSpinBoxAlignRight()
        self.intensity_mean_factor_sb.setValue(3.0)
        self.intensity_mean_factor_sb.setSingleStep(0.1)

        self.intensity_limit_txt = NumberTextField('55000')

        self.number_of_rings_sb = SpinBoxAlignRight()
        self.number_of_rings_sb.setValue(15)

        advanced_content = QtWidgets.QWidget()
        self._advanced_layout = QtWidgets.QGridLayout(advanced_content)
        self._advanced_layout.setContentsMargins(0, 0, 0, 0)
        self._advanced_layout.setSpacing(3)
        self._advanced_layout.addWidget(LabelAlignRight('Peak Search Algorithm:'), 0, 0)
        self._advanced_layout.addWidget(self.peak_search_algorithm_cb, 0, 1)
        self._advanced_layout.addWidget(LabelAlignRight('Delta 2Th:'), 1, 0)
        self._advanced_layout.addWidget(self.delta_tth_txt, 1, 1)
        self._advanced_layout.addWidget(LabelAlignRight('Intensity Mean Factor:'), 2, 0)
        self._advanced_layout.addWidget(self.intensity_mean_factor_sb, 2, 1)
        self._advanced_layout.addWidget(LabelAlignRight('Intensity Limit:'), 3, 0)
        self._advanced_layout.addWidget(self.intensity_limit_txt, 3, 1)
        self._advanced_layout.addWidget(LabelAlignRight('Number of rings:'), 4, 0)
        self._advanced_layout.addWidget(self.number_of_rings_sb, 4, 1)

        self.advanced_expander = AdvancedExpander(advanced_content)
        self._layout.addWidget(self.advanced_expander, 2, 0, 1, 2)

        self.setLayout(self._layout)


class PyfaiParametersWidget(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

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
        super().__init__(*args, **kwargs)

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
