# SPDX-License-Identifier: MIT

import os
import sys

from qtpy import QtWidgets, QtGui, QtCore
from pyqtgraph import GraphicsLayoutWidget

from ..widgets.plot_widgets import CalibrationCakeWidget
from ..widgets.plot_widgets import PatternWidget
from ..widgets.plot_widgets.ImgWidget import IntegrationImgWidget

from .CustomWidgets import NumberTextField, LabelAlignRight, SpinBoxAlignRight, \
    DoubleSpinBoxAlignRight, OpenIconButton, ResetIconButton, EmptyStateOverlay, \
    MaskControlsWidget, VerticalLine


#: the wizard's step titles — shared between the top indicator and the
#: Next button labels
WIZARD_STEP_TITLES = ['Image', 'Pick Rings', 'Calibrate', 'Validation']

#: instance stylesheet for the wizard's primary action buttons — applied
#: per button because the qt_material theme overrides the app-qss
#: property rule inconsistently
PRIMARY_BUTTON_STYLE = (
    'QPushButton { border: 1px solid #E8A33C; color: #E8A33C;'
    ' font-weight: bold; border-radius: 4px; background: transparent; }'
    'QPushButton:hover { background: rgba(232, 163, 60, 30); }'
    'QPushButton:disabled { border: 1px solid #5B5B5B; color: #909090;'
    ' font-weight: normal; }'
)


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
        'pending': '#787878',
        'attention': '#F1F1F1',
        'skipped': '#8C8C8C',
        'done': '#B4B4B4',
    }
    #: badge/underline color of the current step
    CURRENT_COLOR = '#E8A33C'
    DONE_COLOR = '#66bb6a'
    BADGE_SIZE = 20

    def __init__(self, titles, parent=None):
        super().__init__(parent)
        self._layout = QtWidgets.QHBoxLayout(self)
        self._layout.setContentsMargins(6, 0, 10, 0)
        self._layout.setSpacing(8)

        # right-aligned: the wizard controls live in the right panel, so
        # the step navigation sits above them
        self._layout.addStretch()

        self.step_btns = []
        self._titles = list(titles)
        self._statuses = []
        for ind, title in enumerate(titles):
            if ind > 0:
                separator = QtWidgets.QLabel()
                separator.setFixedSize(22, 1)
                separator.setStyleSheet('background-color: #5B5B5B;')
                self._layout.addWidget(separator, 0, QtCore.Qt.AlignVCenter)
            btn = QtWidgets.QToolButton()
            btn.setText(title)
            btn.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
            btn.clicked.connect(lambda _=False, i=ind: self.step_clicked.emit(i))
            self._layout.addWidget(btn)
            self.step_btns.append(btn)
            self._statuses.append('pending')

        self.setMaximumHeight(34)

        self.set_current_step(0)

    def _make_badge_icon(self, index):
        """Paints the step's circular badge: amber with the step number for
        the current step, a green check for completed steps, a gray dash
        for skipped steps, an outlined number otherwise."""
        status = self._statuses[index]
        is_current = self.step_btns[index].isChecked()
        size = self.BADGE_SIZE
        pixmap = QtGui.QPixmap(size * 2, size * 2)
        pixmap.setDevicePixelRatio(2)
        pixmap.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        rect = QtCore.QRectF(1, 1, size - 2, size - 2)
        font = painter.font()
        font.setBold(True)
        font.setPixelSize(11)
        painter.setFont(font)
        if is_current:
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QColor(self.CURRENT_COLOR))
            painter.drawEllipse(rect)
            painter.setPen(QtGui.QColor('#1E1E1E'))
            painter.drawText(rect, QtCore.Qt.AlignCenter, str(index + 1))
        elif status == 'done':
            pen = QtGui.QPen(QtGui.QColor(self.DONE_COLOR))
            pen.setWidthF(1.6)
            painter.setPen(pen)
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawEllipse(rect)
            painter.drawText(rect, QtCore.Qt.AlignCenter, '✓')
        elif status == 'skipped':
            pen = QtGui.QPen(QtGui.QColor(self.STATUS_COLORS['skipped']))
            pen.setWidthF(1.2)
            painter.setPen(pen)
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawEllipse(rect)
            painter.drawText(rect, QtCore.Qt.AlignCenter, '–')
        else:
            color = QtGui.QColor(self.STATUS_COLORS[status])
            pen = QtGui.QPen(color)
            pen.setWidthF(1.2)
            painter.setPen(pen)
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawEllipse(rect)
            painter.drawText(rect, QtCore.Qt.AlignCenter, str(index + 1))
        painter.end()
        return QtGui.QIcon(pixmap)

    def set_current_step(self, index):
        self.step_btns[index].setChecked(True)
        # the badges depend on which step is current
        for ind in range(len(self.step_btns)):
            self._style_step(ind)

    def current_step(self):
        for ind, btn in enumerate(self.step_btns):
            if btn.isChecked():
                return ind
        return 0

    def set_step_status(self, index, status):
        """:param status: one of 'pending', 'attention', 'skipped', 'done'"""
        self._statuses[index] = status
        self.step_btns[index].setToolTip(
            'Skipped – the calibration was loaded or entered manually'
            if status == 'skipped' else ''
        )
        self._style_step(index)

    def step_status(self, index):
        return self._statuses[index]

    def set_step_enabled(self, index, enabled):
        self.step_btns[index].setEnabled(enabled)

    def _style_step(self, index):
        status = self._statuses[index]
        color = self.STATUS_COLORS[status]
        btn = self.step_btns[index]
        btn.setText(' ' + self._titles[index])
        btn.setIcon(self._make_badge_icon(index))
        btn.setIconSize(QtCore.QSize(self.BADGE_SIZE, self.BADGE_SIZE))
        # min-height/margin zeroed to undo the qt_material button sizing,
        # which would inflate the row to ~47px and read as empty space
        btn.setStyleSheet(
            'QToolButton {{ border: none; background: transparent;'
            ' color: {0}; font-size: 14px; padding: 4px 10px;'
            ' margin: 0px; min-height: 0px; }}'
            'QToolButton:checked {{ font-weight: bold; color: #F1F1F1;'
            ' background: #262626; border-bottom: 2px solid {1}; }}'
            'QToolButton:disabled {{ color: #5B5B5B; }}'.format(
                color, self.CURRENT_COLOR))


class CalibrationWidget(QtWidgets.QWidget):
    """
    Defines the main structure of the calibration widget, which is separated into two parts.
    Calibration Display Widget - shows the image and pattern
    Calibration Control Widget - shows all the controls on the right side of the widget
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setObjectName('calibration_widget')

        self.step_indicator = StepIndicatorWidget(WIZARD_STEP_TITLES)

        self.calibration_display_widget = CalibrationDisplayWidget(self)
        self.calibration_control_widget = CalibrationControlWidget(self)

        self._content_layout = QtWidgets.QHBoxLayout()
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(10)
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
        self.enter_parameters_btn = self.calibration_control_widget.enter_parameters_btn

        self.calibrate_btn = parameters_widget.calibrate_btn
        self.refine_btn = parameters_widget.refine_btn
        self.parameters_tab_widget = parameters_widget.parameters_tab_widget
        self.pos_lbl = self.calibration_display_widget.position_lbl
        self.show_calibrant_lines_cb = (
            self.calibration_display_widget.show_calibrant_lines_cb
        )
        self.show_calibrant_numbers_cb = (
            self.calibration_display_widget.show_calibrant_numbers_cb
        )

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

        self.use_mask_cb = self.calibration_display_widget.mask_controls.use_mask_cb
        self.mask_transparent_cb = (
            self.calibration_display_widget.mask_controls.transparent_mask_cb
        )

        refinement_options_gb = self.calibration_control_widget.calibration_parameters_widget.refinement_options_gb
        self.options_automatic_refinement_cb = refinement_options_gb.automatic_refinement_cb
        self.options_num_rings_sb = refinement_options_gb.number_of_rings_sb
        self.options_peaksearch_algorithm_cb = refinement_options_gb.peak_search_algorithm_cb
        self.options_delta_tth_txt = refinement_options_gb.delta_tth_txt
        self.options_intensity_mean_factor_sb = refinement_options_gb.intensity_mean_factor_sb
        self.options_intensity_limit_txt = refinement_options_gb.intensity_limit_txt

        peak_selection_widget = parameters_widget.peak_selection_widget
        self.peak_num_sb = peak_selection_widget.peak_num_sb
        self.automatic_peak_search_rb = peak_selection_widget.automatic_peak_search_rb
        self.select_peak_rb = peak_selection_widget.select_peak_rb
        self.search_size_sb = peak_selection_widget.search_size_sb
        self.automatic_peak_num_inc_cb = peak_selection_widget.automatic_peak_num_inc_cb
        self.clear_peaks_btn = peak_selection_widget.clear_peaks_btn
        self.peak_counter_lbl = peak_selection_widget.peak_counter_lbl
        self.peak_table = peak_selection_widget.peak_table
        self.delete_peak_btn = peak_selection_widget.delete_peak_btn

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
        """Reads the fit constraints from the calibrate page: every
        unchecked parameter is held at the value in its text field. The
        pyFAI-page checkboxes mirror these, so both stay in agreement."""
        fixed_values = {}

        sv_gb = self.calibration_control_widget.calibration_parameters_widget.start_values_gb

        if not sv_gb.distance_cb.isChecked():
            fixed_values['dist'] = self.get_float_from_txt_field(sv_gb.distance_txt) * 1e-3
        if not sv_gb.rotation1_cb.isChecked():
            fixed_values['rot1'] = self.get_float_from_txt_field(sv_gb.rotation1_txt)
        if not sv_gb.rotation2_cb.isChecked():
            fixed_values['rot2'] = self.get_float_from_txt_field(sv_gb.rotation2_txt)
        if not sv_gb.rotation3_cb.isChecked():
            fixed_values['rot3'] = self.get_float_from_txt_field(sv_gb.rotation3_txt)
        if not sv_gb.poni1_cb.isChecked():
            fixed_values['poni1'] = self.get_float_from_txt_field(sv_gb.poni1_txt)
        if not sv_gb.poni2_cb.isChecked():
            fixed_values['poni2'] = self.get_float_from_txt_field(sv_gb.poni2_txt)
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

            # the fit-constraint fields follow the fitted values, so a later
            # "hold this fixed" keeps the calibrated number, not a stale one
            sv_gb.rotation1_txt.setText('%.8f' % (pyfai_parameter['rot1']))
            sv_gb.rotation2_txt.setText('%.8f' % (pyfai_parameter['rot2']))
            sv_gb.rotation3_txt.setText('%.8f' % (pyfai_parameter['rot3']))
            sv_gb.poni1_txt.setText('%.6f' % (pyfai_parameter['poni1']))
            sv_gb.poni2_txt.setText('%.6f' % (pyfai_parameter['poni2']))
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

        # IntegrationImgWidget extends the mask-capable image widget with
        # the iso-2θ circle overlay used by the linked click position
        self.img_widget = IntegrationImgWidget(self.img_layout_widget)
        # shown until an image is loaded; the controller hides it based on
        # the guide state
        self.empty_state_lbl = EmptyStateOverlay(
            self.img_layout_widget,
            "<span style='font-size: 15px;'>"
            "Load a calibration image to begin</span><br/>"
            "<span style='font-size: 12px; color: #6E6E6E;'>"
            "TIFF, CBF, EDF, HDF5 and other formats &mdash; or use "
            "&ldquo;Load Calibration&rdquo; on the right</span>")
        self.cake_widget = CalibrationCakeWidget(self.cake_layout_widget)
        self.pattern_widget = PatternWidget(self.pattern_layout_widget)

        # image alone during the working steps; cake and pattern join it on
        # the validation step
        self._top_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self._top_splitter.addWidget(self.img_layout_widget)
        self._top_splitter.addWidget(self.cake_layout_widget)

        self.view_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        self.view_splitter.addWidget(self._top_splitter)
        self.view_splitter.addWidget(self.pattern_layout_widget)
        self.view_splitter.setStretchFactor(0, 1)
        self.view_splitter.setStretchFactor(1, 1)
        self._layout.addWidget(self.view_splitter)

        self._status_layout = QtWidgets.QHBoxLayout()
        self._status_layout.setContentsMargins(6, 0, 0, 0)
        self.position_lbl = QtWidgets.QLabel("")

        self.mask_controls = MaskControlsWidget()

        # visible on every wizard step, like the calibrant overlays they
        # control
        self.show_calibrant_lines_cb = QtWidgets.QCheckBox("calibrant lines")
        self.show_calibrant_lines_cb.setChecked(True)
        self.show_calibrant_lines_cb.setToolTip(
            "Show the calibrant's lines in the image, cake and pattern views."
        )
        self.show_calibrant_numbers_cb = QtWidgets.QCheckBox("numbers")
        self.show_calibrant_numbers_cb.setChecked(True)
        self.show_calibrant_numbers_cb.setToolTip(
            "Show the ring number on each calibrant line."
        )
        self._status_layout.addWidget(self.show_calibrant_lines_cb)
        self._status_layout.addWidget(self.show_calibrant_numbers_cb)
        self._status_layout.addSpacing(4)
        self.mask_controls_separator = VerticalLine()
        self._status_layout.addWidget(self.mask_controls_separator)
        self._status_layout.addSpacing(4)
        self._status_layout.addWidget(self.mask_controls)

        self._status_layout.addSpacerItem(QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Expanding,
                                                                QtWidgets.QSizePolicy.Minimum))
        self._status_layout.addWidget(self.position_lbl)
        self._layout.addLayout(self._status_layout)

        self.setLayout(self._layout)
        self.show_validation_views(False)

    def show_validation_views(self, show):
        """Shows cake and pattern beside the image (validation step) or the
        image alone (all other steps)."""
        self.cake_layout_widget.setVisible(show)
        self.pattern_layout_widget.setVisible(show)
        if show:
            # give freshly shown views a sensible share once — collapsed
            # widgets otherwise stay at (near) zero size; user-dragged
            # splitter positions are left alone on later calls
            if self.cake_layout_widget.width() < 20:
                total_width = max(self._top_splitter.width(), 2)
                self._top_splitter.setSizes(
                    [total_width // 2, total_width // 2])
            if self.pattern_layout_widget.height() < 20:
                total_height = max(self.view_splitter.height(), 2)
                self.view_splitter.setSizes(
                    [total_height // 2, total_height // 2])


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

        # loading an existing .poni or typing known parameters are the
        # alternative entries into the workflow, so they stay reachable
        # from every step; the caption marks them as a deliberate block
        # rather than two stray buttons
        self.alternative_entry_lbl = QtWidgets.QLabel(
            'Already have a calibration?')
        self.alternative_entry_lbl.setStyleSheet(
            'color: #909090; font-size: 12px; margin-top: 6px;')
        self._layout.addWidget(self.alternative_entry_lbl)

        self._bottom_layout = QtWidgets.QHBoxLayout()
        self.load_calibration_btn = QtWidgets.QPushButton('Load Calibration')
        self.enter_parameters_btn = QtWidgets.QPushButton('Enter Manually')
        self.enter_parameters_btn.setToolTip(
            'Type known pyFAI or Fit2d calibration parameters directly, '
            'without a *.poni file')
        self._bottom_layout.addWidget(self.load_calibration_btn)
        self._bottom_layout.addWidget(self.enter_parameters_btn)
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
        self.peak_selection_widget = PeakSelectionWidget()

        self.peaks_page = QtWidgets.QWidget()
        self._peaks_page_layout = QtWidgets.QVBoxLayout(self.peaks_page)
        self._peaks_page_layout.setContentsMargins(0, 0, 0, 0)
        self._peaks_page_layout.addWidget(self.peak_selection_widget)
        self._peaks_page_layout.addStretch()

        # --- page 3: calibrant, start values, calibrate -----------------
        self.start_values_gb = StartValuesGroupBox(self)
        self.refinement_options_gb = RefinementOptionsGroupBox()

        self.calibrate_btn = QtWidgets.QPushButton('Calibrate')
        self.calibrate_btn.setStyleSheet(PRIMARY_BUTTON_STYLE)
        self.calibrate_btn.setMinimumHeight(28)

        self.calibrate_page = QtWidgets.QWidget()
        self._calibrate_page_layout = QtWidgets.QVBoxLayout(self.calibrate_page)
        self._calibrate_page_layout.setContentsMargins(0, 0, 0, 0)
        self._calibrate_page_layout.setSpacing(12)
        self._calibrate_page_layout.addWidget(self.start_values_gb)
        self._calibrate_page_layout.addWidget(self.refinement_options_gb)
        self._calibrate_page_layout.addWidget(self.calibrate_btn)
        self._calibrate_page_layout.addStretch()

        # --- page 4: validation — fitted parameters, refine, save -------
        self.pyfai_parameters_widget = PyfaiParametersWidget()
        self.fit2d_parameters_widget = Fit2dParametersWidget()
        self.parameters_tab_widget = QtWidgets.QTabWidget()
        self.parameters_tab_widget.addTab(self.pyfai_parameters_widget, 'pyFAI')
        self.parameters_tab_widget.addTab(self.fit2d_parameters_widget, 'Fit2d')

        self.refine_btn = QtWidgets.QPushButton('Refine')
        self.save_calibration_btn = QtWidgets.QPushButton('Save Calibration')
        self.save_calibration_btn.setStyleSheet(PRIMARY_BUTTON_STYLE)
        self.save_calibration_btn.setMinimumHeight(28)

        self.validation_page = QtWidgets.QWidget()
        self._validation_page_layout = QtWidgets.QVBoxLayout(self.validation_page)
        self._validation_page_layout.setContentsMargins(0, 0, 0, 0)
        self._validation_page_layout.setSpacing(12)
        self._validation_page_layout.addWidget(self.parameters_tab_widget)
        self._validation_page_layout.addWidget(self.refine_btn)
        self._validation_page_layout.addWidget(self.save_calibration_btn)
        self._validation_page_layout.addStretch()

        # --- wizard chrome ----------------------------------------------
        self.step_stack = QtWidgets.QStackedWidget()
        self.step_stack.addWidget(self.image_page)
        self.step_stack.addWidget(self.peaks_page)
        self.step_stack.addWidget(self.calibrate_page)
        self.step_stack.addWidget(self.validation_page)

        self._scroll_area = QtWidgets.QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        self._scroll_area.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarAlwaysOff)
        self._scroll_area.setWidget(self.step_stack)

        # the primary way forward: a prominent Next naming the target step,
        # with a compact Back beside it
        self.back_btn = QtWidgets.QPushButton('‹ Back')
        self.back_btn.setMinimumHeight(30)
        self.back_btn.setMaximumWidth(80)
        self.next_btn = QtWidgets.QPushButton('Next ›')
        self.next_btn.setStyleSheet(PRIMARY_BUTTON_STYLE)
        self.next_btn.setMinimumHeight(30)
        self._nav_layout = QtWidgets.QHBoxLayout()
        self._nav_layout.setSpacing(6)
        self._nav_layout.addWidget(self.back_btn)
        self._nav_layout.addWidget(self.next_btn, 1)

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

        self.detector_cb = QtWidgets.QComboBox()

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

        # unchecked checkboxes hold the parameter fixed at the given value
        # during calibration and refinement (mirrored with the pyFAI
        # parameter page), like the distance and wavelength ones above
        self.rotation1_txt = NumberTextField('0')
        self.rotation2_txt = NumberTextField('0')
        self.rotation3_txt = NumberTextField('0')
        self.rotation1_cb = QtWidgets.QCheckBox()
        self.rotation2_cb = QtWidgets.QCheckBox()
        self.rotation3_cb = QtWidgets.QCheckBox()
        self.poni1_txt = NumberTextField('0')
        self.poni2_txt = NumberTextField('0')
        self.poni1_cb = QtWidgets.QCheckBox()
        self.poni2_cb = QtWidgets.QCheckBox()

        fit_tooltip = ('Checked: parameter is refined. Unchecked: it is '
                       'held fixed at the given value.')
        for row_offset, (label, txt_field, unit, checkbox) in enumerate([
                ('Rotation 1:', self.rotation1_txt, 'rad', self.rotation1_cb),
                ('Rotation 2:', self.rotation2_txt, 'rad', self.rotation2_cb),
                ('Rotation 3:', self.rotation3_txt, 'rad', self.rotation3_cb),
                ('PONI 1:', self.poni1_txt, 'm', self.poni1_cb),
                ('PONI 2:', self.poni2_txt, 'm', self.poni2_cb)]):
            checkbox.setChecked(True)
            checkbox.setToolTip(fit_tooltip)
            row = 4 + row_offset
            self._grid_layout1.addWidget(LabelAlignRight(label), row, 0)
            self._grid_layout1.addWidget(txt_field, row, 1)
            self._grid_layout1.addWidget(QtWidgets.QLabel(unit), row, 2)
            self._grid_layout1.addWidget(checkbox, row, 3)

        self._grid_layout1.addWidget(LabelAlignRight('Calibrant:'), 9, 0)
        self.calibrant_cb = QtWidgets.QComboBox()
        self._grid_layout1.addWidget(self.calibrant_cb, 9, 1, 1, 2)

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


class PeakSelectionWidget(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        self._layout = QtWidgets.QGridLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)
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

        self.search_size_sb = SpinBoxAlignRight()
        self.search_size_sb.setValue(10)
        self.search_size_sb.setMaximumWidth(50)
        self._layout.addWidget(LabelAlignRight('Search size:'), 4, 0)
        self._layout.addWidget(self.search_size_sb, 4, 1)
        self._layout.addItem(QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Expanding,
                                                   QtWidgets.QSizePolicy.Minimum), 4, 2, 1, 2)

        # one row per picked peak group; the ring spinbox reassigns a
        # group, selection highlights the peaks in the image
        self.peak_table = QtWidgets.QTableWidget()
        self.peak_table.setColumnCount(3)
        self.peak_table.setHorizontalHeaderLabels(['Ring', 'Peaks', 'Position'])
        self.peak_table.verticalHeader().setVisible(False)
        self.peak_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectRows)
        self.peak_table.setSelectionMode(
            QtWidgets.QAbstractItemView.ExtendedSelection)
        self.peak_table.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeToContents)
        self.peak_table.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeToContents)
        self.peak_table.horizontalHeader().setStretchLastSection(True)
        self.peak_table.horizontalHeaderItem(2).setToolTip(
            "Mean position of the group's peaks (x, y)")
        self.peak_table.setMinimumHeight(140)
        self._layout.addWidget(self.peak_table, 5, 0, 1, 4)

        self.delete_peak_btn = QtWidgets.QPushButton("Delete")
        self.delete_peak_btn.setToolTip(
            "Delete the selected peak groups (Del).\n"
            "Changing the ring number selects every group of that ring,\n"
            "so a whole ring can be deleted in two steps."
        )
        self.clear_peaks_btn = QtWidgets.QPushButton("Clear All")

        self._peak_btn_layout = QtWidgets.QHBoxLayout()
        self._peak_btn_layout.setSpacing(6)
        self._peak_btn_layout.addWidget(self.delete_peak_btn)
        self._peak_btn_layout.addWidget(self.clear_peaks_btn)
        self._layout.addLayout(self._peak_btn_layout, 6, 0, 1, 4)

        self.peak_counter_lbl = QtWidgets.QLabel('No peaks selected')
        self.peak_counter_lbl.setStyleSheet('color: #787878; font-style: italic;')
        self._layout.addWidget(self.peak_counter_lbl, 7, 0, 1, 4)

        self.setLayout(self._layout)


class RefinementOptionsGroupBox(QtWidgets.QGroupBox):
    def __init__(self):
        super().__init__('Refinement Options')

        self._layout = QtWidgets.QGridLayout()
        self._layout.setSpacing(3)
        self._layout.setContentsMargins(6, 8, 6, 6)

        self.automatic_refinement_cb = QtWidgets.QCheckBox('automatic refinement')
        self.automatic_refinement_cb.setChecked(True)
        self._layout.addWidget(self.automatic_refinement_cb, 0, 0, 1, 2)

        # the parameters below belong to the automatic refinement — they
        # are only shown while it is enabled
        self.peak_search_algorithm_cb = QtWidgets.QComboBox()
        self.peak_search_algorithm_cb.addItems(['Massif', 'Blob'])

        self.delta_tth_txt = NumberTextField('0.1')

        self.intensity_mean_factor_sb = DoubleSpinBoxAlignRight()
        self.intensity_mean_factor_sb.setValue(3.0)
        self.intensity_mean_factor_sb.setSingleStep(0.1)

        self.intensity_limit_txt = NumberTextField('55000')

        self.number_of_rings_sb = SpinBoxAlignRight()
        self.number_of_rings_sb.setValue(15)

        self.automatic_refinement_content = QtWidgets.QWidget()
        self._automatic_layout = QtWidgets.QGridLayout(
            self.automatic_refinement_content)
        self._automatic_layout.setContentsMargins(0, 0, 0, 0)
        self._automatic_layout.setSpacing(3)
        self._automatic_layout.addWidget(LabelAlignRight('Peak Search Algorithm:'), 0, 0)
        self._automatic_layout.addWidget(self.peak_search_algorithm_cb, 0, 1)
        self._automatic_layout.addWidget(LabelAlignRight('Delta 2Th:'), 1, 0)
        self._automatic_layout.addWidget(self.delta_tth_txt, 1, 1)
        self._automatic_layout.addWidget(LabelAlignRight('Intensity Mean Factor:'), 2, 0)
        self._automatic_layout.addWidget(self.intensity_mean_factor_sb, 2, 1)
        self._automatic_layout.addWidget(LabelAlignRight('Intensity Limit:'), 3, 0)
        self._automatic_layout.addWidget(self.intensity_limit_txt, 3, 1)
        self._automatic_layout.addWidget(LabelAlignRight('Number of rings:'), 4, 0)
        self._automatic_layout.addWidget(self.number_of_rings_sb, 4, 1)

        self._layout.addWidget(self.automatic_refinement_content, 1, 0, 1, 2)
        self.automatic_refinement_cb.toggled.connect(
            self.automatic_refinement_content.setVisible)

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
