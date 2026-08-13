# SPDX-License-Identifier: MIT

import logging
import os
from qtpy import QtWidgets, QtCore, QtGui

import numpy as np
import pyqtgraph as pg
from skimage.measure import find_contours

from ..widgets.UtilityWidgets import open_file_dialog, save_file_dialog
from ..model.util.HelperModule import get_partial_index, get_partial_value
from ..model.util.file_type import FileLoadingError
from .. import calibrants_path

# imports for type hinting in PyCharm -- DO NOT DELETE
from ..widgets.CalibrationWidget import CalibrationWidget, WIZARD_STEP_TITLES
from ..model.DioptasModel import DioptasModel
from .binding import Binder
from ..model.CalibrationGuide import CalibrationGuide, Step
from ..model.CalibrationModel import (
    NotEnoughSpacingsInCalibrant,
    get_available_detectors,
    DetectorModes,
)

logger = logging.getLogger(__name__)


class CalibrationController:
    """
    CalibrationController handles all the interaction between the CalibrationView and the CalibrationData class
    """

    def __init__(self, widget, dioptas_model):
        """Manages the connection between the calibration GUI and data

        :param widget: Gives the Calibration Widget
        :type widget: CalibrationWidget

        :param dioptas_model: Reference to DioptasModel Object
        :type dioptas_model: DioptasModel

        """
        self.widget = widget
        self.model = dioptas_model
        self.binder = Binder()
        # calibration is the mode the application starts in; activate()/
        # deactivate() track mode switches so hidden validation views are
        # not redrawn from signals fired in other modes
        self._mode_active = True

        self.widget.set_start_values(self.model.calibration_model.start_values)
        self.create_signals()
        self.load_detectors_list()
        self.load_calibrants_list()
        self._setup_unconfirmed_fields()
        self.update_peak_table()

        self.guide = CalibrationGuide(dioptas_model)
        self.guide.changed.connect(self.update_guide_in_view)
        self.update_guide_in_view()

    def create_signals(self):
        """
        Connects the GUI signals to the appropriate Controller methods.
        """
        self.model.img_changed.connect(self.plot_image)
        self.model.mask_changed.connect(self.update_mask_gui)
        # picked peaks can change without this controller doing it — an undo
        # from any mode restores them, and the view has to follow
        self._last_peak_selection_count = len(self.model.calibration_model.points)
        self.model.calibration_model.points_changed.connect(self._on_points_changed)
        self.model.configuration_selected.connect(
            self.update_calibration_parameter_in_view
        )
        self.model.configuration_selected.connect(
            self.update_detector_parameters_in_view
        )
        # configuration switching (and project reset) replaces the
        # calibration model — re-wire its instance signals and refresh the
        # peak views, which would otherwise keep showing the old peaks
        self.model.configuration_selected.connect(self._on_configuration_selected)
        self.model.calibration_model.detector_reset.connect(
            self.update_detector_parameters_in_view
        )
        self.model.calibration_model.detector_reset.connect(
            self.show_detector_reset_message_box
        )

        self.create_transformation_signals()
        self.create_update_signals()
        self.create_mouse_signals()

        self.widget.detectors_cb.currentIndexChanged.connect(self.load_detector)
        self.widget.detector_load_btn.clicked.connect(self.load_detector_from_file)
        self.widget.detector_reset_btn.clicked.connect(self.reset_detector_from_file)

        self.widget.calibrant_cb.currentIndexChanged.connect(self.load_calibrant)
        self.widget.load_img_btn.clicked.connect(self.load_img)
        self.widget.load_next_img_btn.clicked.connect(self.load_next_img)
        self.widget.load_previous_img_btn.clicked.connect(self.load_previous_img)
        self.widget.filename_txt.editingFinished.connect(self.update_filename_txt)

        self.widget.save_calibration_btn.clicked.connect(self.save_calibration)
        self.widget.load_calibration_btn.clicked.connect(self.load_calibration)
        self.widget.calibrate_btn.clicked.connect(self.calibrate)
        self.widget.refine_btn.clicked.connect(self.refine)

        # the pyFAI/Fit2d choice on the validation step is a workflow
        # preference (Fit2d numbers feed CrysAlis and friends), so it lives
        # in the view params and comes back with the session
        self.widget.parameters_tab_widget.currentChanged.connect(
            self._parameters_tab_changed
        )
        self.model.view.events.calibration_param_display.connect(
            self._parameters_display_changed
        )
        self._parameters_display_changed()

        self.widget.clear_peaks_btn.clicked.connect(self.clear_peaks)
        self.widget.peak_num_sb.valueChanged.connect(self.current_ring_changed)

        self.widget.show_calibrant_lines_cb.toggled.connect(
            self._calibrant_visibility_changed
        )
        self.widget.show_calibrant_numbers_cb.toggled.connect(
            self._calibrant_visibility_changed
        )

        self._updating_peak_table = False
        self.widget.peak_table.itemSelectionChanged.connect(
            self.peak_table_selection_changed
        )
        self.widget.delete_peak_btn.clicked.connect(self.delete_selected_peaks)
        self._delete_peak_shortcut = QtGui.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.Key_Delete), self.widget.peak_table
        )
        self._delete_peak_shortcut.setContext(QtCore.Qt.WidgetShortcut)
        self._delete_peak_shortcut.activated.connect(self.delete_selected_peaks)

        self.widget.load_spline_btn.clicked.connect(self.load_spline_btn_click)
        self.widget.spline_reset_btn.clicked.connect(self.reset_spline_btn_click)

        self.binder.mirror_toggles(
            self.widget.f2_wavelength_cb,
            self.widget.pf_wavelength_cb,
            self.widget.sv_wavelength_cb,
            on_toggled=self.wavelength_cb_changed,
        )
        self.binder.mirror_toggles(
            self.widget.f2_distance_cb,
            self.widget.pf_distance_cb,
            self.widget.sv_distance_cb,
            on_toggled=self.distance_cb_changed,
        )

        # the rotation/PONI fit checkboxes in the start values and on the
        # pyFAI parameter page show the same state; the values are read via
        # get_fixed_values() when a calibration or refinement starts
        start_values_gb = (
            self.widget.calibration_control_widget
            .calibration_parameters_widget.start_values_gb
        )
        for pyfai_cb, calibrate_cb in [
            (self.widget.pf_rot1_cb, start_values_gb.rotation1_cb),
            (self.widget.pf_rot2_cb, start_values_gb.rotation2_cb),
            (self.widget.pf_rot3_cb, start_values_gb.rotation3_cb),
            (self.widget.pf_poni1_cb, start_values_gb.poni1_cb),
            (self.widget.pf_poni2_cb, start_values_gb.poni2_cb),
        ]:
            self.binder.mirror_toggles(
                pyfai_cb, calibrate_cb, on_toggled=lambda _checked: None
            )

        self.widget.use_mask_cb.stateChanged.connect(self.use_mask_cb_changed)
        self.widget.mask_transparent_cb.stateChanged.connect(
            self.mask_transparent_status_changed
        )

        self.widget.wizard_back_btn.clicked.connect(self.wizard_back)
        self.widget.wizard_next_btn.clicked.connect(self.wizard_next)
        self.widget.step_indicator.step_clicked.connect(self.go_to_wizard_step)

        self._manual_parameters_requested = False
        self.widget.enter_parameters_btn.clicked.connect(
            self.enter_parameters_manually
        )

        # linked click position and calibrant overlays on the validation step;
        # the position markers stay hidden until the first linked click —
        # both widgets create them visible at position 0 by default
        self.widget.pattern_widget.deactivate_pos_line()
        self.widget.cake_widget.deactivate_vertical_line()
        self._calibrant_overlays_dirty = True
        self.widget.img_widget.mouse_left_clicked.connect(self.validation_img_click)
        self.widget.cake_widget.mouse_left_clicked.connect(self.validation_cake_click)
        self.widget.pattern_widget.mouse_left_clicked.connect(
            self.validation_pattern_click
        )
        self.model.clicked_tth_changed.connect(self.update_validation_line_positions)
        self.model.calibration_model.parameters_changed.connect(
            self._calibrant_overlays_changed
        )

    def _parameters_tab_changed(self, index):
        self.model.view.calibration_param_display = (
            self.widget.parameters_tab_widget.tabText(index)
        )

    def _parameters_display_changed(self, *_args):
        tab_widget = self.widget.parameters_tab_widget
        for index in range(tab_widget.count()):
            if tab_widget.tabText(index) == self.model.view.calibration_param_display:
                tab_widget.setCurrentIndex(index)
                return

    def create_transformation_signals(self):
        """
        Connects all the rotation GUI controls.
        """
        self.widget.rotate_m90_btn.clicked.connect(self.rotate_m90_btn_clicked)
        self.widget.rotate_p90_btn.clicked.connect(self.rotate_p90_btn_clicked)
        self.widget.invert_horizontal_btn.clicked.connect(
            self.invert_horizontal_btn_clicked
        )
        self.widget.invert_vertical_btn.clicked.connect(
            self.invert_vertical_btn_clicked
        )
        self.widget.reset_transformations_btn.clicked.connect(
            self.reset_transformations_btn_clicked
        )

    def activate(self):
        self._mode_active = True
        if not self.model.img_changed.has_listener(self.plot_image):
            self.model.img_changed.connect(self.plot_image)
        if not self.model.mask_changed.has_listener(self.update_mask_gui):
            self.model.mask_changed.connect(self.update_mask_gui)
        self.plot_image()
        self.update_mask_gui()
        # overlays that went stale while another mode was active — they are
        # visible on every wizard step, so refresh regardless of the step
        if self._calibrant_overlays_dirty:
            self._update_calibrant_overlays()

    def deactivate(self):
        self._mode_active = False
        if self.model.img_changed.has_listener(self.plot_image):
            self.model.img_changed.disconnect(self.plot_image)
        if self.model.mask_changed.has_listener(self.update_mask_gui):
            self.model.mask_changed.disconnect(self.update_mask_gui)

    def rotate_m90_btn_clicked(self):
        self.model.calibration_model.rotate_detector_m90()
        self.model.img_model.rotate_img_m90()
        self.clear_peaks()

    def rotate_p90_btn_clicked(self):
        self.model.calibration_model.rotate_detector_p90()
        self.model.img_model.rotate_img_p90()
        self.clear_peaks()

    def invert_horizontal_btn_clicked(self):
        self.model.calibration_model.flip_detector_horizontally()
        self.model.img_model.flip_img_horizontally()
        self.clear_peaks()

    def invert_vertical_btn_clicked(self):
        self.model.calibration_model.flip_detector_vertically()
        self.model.img_model.flip_img_vertically()
        self.clear_peaks()

    def reset_transformations_btn_clicked(self):
        self.model.calibration_model.reset_transformations()
        self.model.img_model.reset_transformations()
        self.clear_peaks()

    def create_update_signals(self):
        """
        Connects all the txt box signals. Which specifically are the update buttons here.
        """
        self.widget.f2_update_btn.clicked.connect(self.update_f2_btn_click)
        self.widget.pf_update_btn.clicked.connect(self.update_pyFAI_btn_click)

    def create_mouse_signals(self):
        """
        Creates the mouse_move connections to show the current position of the mouse pointer.
        """
        self.widget.img_widget.mouse_moved.connect(self.update_img_mouse_position_lbl)
        self.widget.cake_widget.mouse_moved.connect(self.update_cake_mouse_position_lbl)
        self.widget.pattern_widget.mouse_moved.connect(
            self.update_pattern_mouse_position_lbl
        )
        self.widget.img_widget.mouse_left_clicked.connect(self.search_peaks)

    def update_f2_btn_click(self):
        """
        Takes all parameters inserted into the fit2d txt-fields and updates the current calibration accordingly.
        """
        try:
            fit2d_parameter = self.widget.get_fit2d_parameter()
        except ValueError:
            self._show_incomplete_parameters_message("Fit2d")
            return
        self.model.calibration_model.set_fit2d(fit2d_parameter)
        self.update_all()

    def update_pyFAI_btn_click(self):
        """
        Takes all parameters inserted into the pyFAI txt-fields and updates the current calibration accordingly.
        """
        try:
            pyFAI_parameter = self.widget.get_pyFAI_parameter()
        except ValueError:
            self._show_incomplete_parameters_message("pyFAI")
            return
        self.model.calibration_model.set_pyFAI(pyFAI_parameter)
        self.update_all()

    def _show_file_error_message(self, message):
        QtWidgets.QMessageBox.critical(
            self.widget,
            "Error",
            message,
            QtWidgets.QMessageBox.Ok,
        )

    def _show_incomplete_parameters_message(self, parameter_kind):
        QtWidgets.QMessageBox.critical(
            self.widget,
            "Incomplete parameters",
            "Please fill in all {} parameter fields before updating.".format(
                parameter_kind
            ),
            QtWidgets.QMessageBox.Ok,
        )

    def enter_parameters_manually(self):
        """Opens the validation page for typing pyFAI/Fit2d parameters
        directly — the expert entry path that needs neither picked peaks
        nor a .poni file."""
        self._manual_parameters_requested = True
        self.widget.set_wizard_step(3)
        self.update_guide_in_view()

    # ------------------------------------------------------------------
    # validation step: linked click position across image, cake, pattern
    # ------------------------------------------------------------------

    def _on_validation_step(self):
        return (
            self._wizard_widget().current_step()
            == self._wizard_widget().step_stack.count() - 1
        )

    def validation_img_click(self, x, y):
        """Publishes the 2θ of a click on the image as the linked position."""
        if not self._on_validation_step():
            return
        if not self.model.calibration_model.is_calibrated:
            return
        x, y = y, x  # image array indices vs. mouse position
        shape = self.model.img_model.img_data.shape
        if not (0 <= x < shape[0] and 0 <= y < shape[1]):
            return
        tth = np.rad2deg(
            self.model.calibration_model.get_two_theta_img(
                np.array([x]), np.array([y])
            )
        )
        self.model.clicked_tth_changed.emit(float(tth))

    def validation_cake_click(self, x, _y):
        """Publishes the 2θ of a click on the cake as the linked position."""
        if not self._on_validation_step():
            return
        if self.model.cake_tth is None:
            return
        tth = get_partial_value(self.model.cake_tth, x - 0.5)
        if tth is None:
            return
        self.model.clicked_tth_changed.emit(float(tth))

    def validation_pattern_click(self, x, _y):
        """Publishes the 2θ of a click in the pattern as the linked position."""
        if not self._on_validation_step():
            return
        tth = self.convert_x_value(
            x, self.model.current_configuration.integration_unit, "2th_deg", None
        )
        self.model.clicked_tth_changed.emit(float(tth))

    def update_validation_line_positions(self, tth=None):
        """Places the green position line at *tth* (degrees) in all three
        validation views: pos line in the pattern, vertical line in the
        cake, iso-2θ contour on the image."""
        if not self._mode_active or not self._on_validation_step():
            # clicked_tth also changes from clicks in other modes — do not
            # run the (contour-computing) update for hidden views
            return
        if tth is None:
            tth = self.model.clicked_tth

        pattern_x = self.convert_x_value(
            tth, "2th_deg", self.model.current_configuration.integration_unit, None
        )
        self.widget.pattern_widget.activate_pos_line()
        self.widget.pattern_widget.set_pos_line(pattern_x)

        if self.model.cake_tth is not None:
            position = get_partial_index(self.model.cake_tth, tth)
            if position is not None:
                self.widget.cake_widget.set_vertical_line_pos(position + 0.5, 0)
                self.widget.cake_widget.activate_vertical_line()
            else:
                self.widget.cake_widget.deactivate_vertical_line()

        if self.model.calibration_model.is_calibrated:
            self.widget.img_widget.activate_circle_scatter()
            self.widget.img_widget.set_circle_line(
                self.model.calibration_model.get_two_theta_array(), np.deg2rad(tth)
            )

    # ------------------------------------------------------------------
    # validation step: calibrant overlays in cake and image
    # ------------------------------------------------------------------

    def _calibrant_overlays_changed(self, *_):
        self._calibrant_overlays_dirty = True
        if self._on_validation_step():
            self._update_calibrant_overlays()

    #: alpha for the calibrant overlays, so the peaks stay visible underneath
    _CALIBRANT_OVERLAY_ALPHA = 180
    #: image downsampling for the ring contours — full 2k×2k contouring
    #: per reflection would take seconds
    _CALIBRANT_RING_DOWNSAMPLE = 4

    #: color of the calibrant overlay lines — same red the pattern's
    #: calibrant lines use
    _CALIBRANT_LINE_COLOR = (200, 50, 50)

    def _update_calibrant_overlays(self):
        """Draws the calibrant's reflections as vertical lines into the cake
        and as iso-2θ rings onto the image. The pattern's calibrant lines are
        drawn separately by ``_plot_calibrant_pattern_lines``."""
        if not self._mode_active:
            # stays dirty; recomputed when the calibration mode reactivates
            return
        self._calibrant_overlays_dirty = False
        cake_lines = []
        ring_segments = []
        ring_labels = []

        if self.model.calibration_model.is_calibrated:
            downsample = self._CALIBRANT_RING_DOWNSAMPLE
            tth_img = self.model.calibration_model.tth_array[::downsample, ::downsample]
            tth_img_min, tth_img_max = tth_img.min(), tth_img.max()
            # only ring positions within the integrated range — the extreme
            # image corners reach higher angles, where dense high-order
            # rings would just clutter the view
            if self.model.cake_tth is not None:
                tth_img_max = min(
                    tth_img_max, np.deg2rad(np.max(self.model.cake_tth))
                )

            def add_positions(line_positions, rgba, numbered=False):
                # numbered labels the lines with their 1-based index in the
                # full line list — the same numbering the ring spinbox uses
                # during peak picking
                for ind, tth in enumerate(line_positions):
                    label = str(ind + 1) if numbered else None
                    if self.model.cake_tth is not None:
                        position = get_partial_index(self.model.cake_tth, tth)
                        if position is not None:
                            cake_lines.append((position + 0.5, rgba, label))
                    tth_rad = np.deg2rad(tth)
                    if not tth_img_min < tth_rad < tth_img_max:
                        continue
                    segments = find_contours(tth_img, tth_rad)
                    if not segments:
                        continue
                    for segment in segments:
                        ring_segments.append(
                            (
                                segment[:, 1] * downsample + 0.5,
                                segment[:, 0] * downsample + 0.5,
                                rgba,
                            )
                        )
                    if label is not None:
                        # the widget anchors the number to whichever part
                        # of the ring is in view, so it hands over all
                        # contour points as candidates
                        points = np.concatenate(segments)
                        ring_labels.append(
                            (
                                points[:, 1] * downsample + 0.5,
                                points[:, 0] * downsample + 0.5,
                                label,
                                rgba,
                            )
                        )

            if self.widget.show_calibrant_lines_cb.isChecked():
                calibrant_positions = (
                    np.array(self.model.calibration_model.calibrant.get_2th())
                    / np.pi
                    * 180
                )
                add_positions(
                    calibrant_positions,
                    (*self._CALIBRANT_LINE_COLOR, self._CALIBRANT_OVERLAY_ALPHA),
                    numbered=self.widget.show_calibrant_numbers_cb.isChecked(),
                )

        self.widget.cake_widget.set_phase_lines(cake_lines)
        self.widget.img_widget.set_phase_rings(ring_segments, ring_labels)

    def _calibrant_visibility_changed(self, _checked=False):
        """Applies the calibrant lines/numbers checkboxes to all views."""
        self.widget.show_calibrant_numbers_cb.setEnabled(
            self.widget.show_calibrant_lines_cb.isChecked()
        )
        self._plot_calibrant_pattern_lines()
        self._calibrant_overlays_changed()
        if self._calibrant_overlays_dirty and self._mode_active:
            # the overlays show on every wizard step, not just validation
            self._update_calibrant_overlays()

    def _plot_calibrant_pattern_lines(self, positions=None, numbers=None, name=None):
        """Draws the calibrant's vertical lines into the pattern plot,
        honoring the lines/numbers checkboxes.

        With arguments it also remembers them, so a later checkbox toggle
        can redraw the same lines without recomputing the positions.
        """
        if positions is not None:
            self._calibrant_pattern_line_data = (positions, numbers, name)
        positions, numbers, name = getattr(
            self, "_calibrant_pattern_line_data", (np.array([]), None, None)
        )
        if not self.widget.show_calibrant_lines_cb.isChecked():
            positions, numbers = np.array([]), None
        elif not self.widget.show_calibrant_numbers_cb.isChecked():
            numbers = None
        self.widget.pattern_widget.plot_vertical_lines(
            positions=positions, name=name, numbers=numbers
        )

    def load_img(self):
        """
        Loads an image file.
        """
        logger.info("Loading calibration image")
        filename = open_file_dialog(
            self.widget,
            caption="Load Calibration Image",
            directory=self.model.working_directories["image"],
        )

        if filename != "":
            self.model.working_directories["image"] = os.path.dirname(filename)
            try:
                self.model.img_model.load(filename)
            except FileLoadingError as e:
                self._show_file_error_message(str(e))

    def load_next_img(self):
        self.model.img_model.load_next_file()

    def load_previous_img(self):
        self.model.img_model.load_previous_file()

    def update_filename_txt(self):
        """
        Updates the filename in the GUI corresponding to the filename in img_data
        """
        current_filename = os.path.basename(self.model.img_model.filename)
        current_directory = os.path.dirname(self.model.img_model.filename)
        new_filename = str(self.widget.filename_txt.text())
        if current_filename == new_filename:
            return
        if os.path.exists(os.path.join(current_directory, new_filename)):
            try:
                self.load_img(os.path.join(current_directory, new_filename))
            except TypeError:
                self.widget.filename_txt.setText(current_filename)
        else:
            self.widget.filename_txt.setText(current_filename)

    def load_detectors_list(self):
        self._detectors_list, _ = get_available_detectors()
        self._detectors_list.insert(0, "Custom")
        self.widget.detectors_cb.blockSignals(True)
        self.widget.detectors_cb.clear()
        self.widget.detectors_cb.addItems(self._detectors_list)
        self.widget.detectors_cb.insertSeparator(1)
        self.widget.detectors_cb.insertSeparator(1)
        self.widget.detectors_cb.blockSignals(False)

    def load_detector(self, ind):
        """
        Loads the selected Detector from the Detector combobox into the calibration model. This blackout disable the
        controls for pixel widths, unless "custom" (the first element) is selected.
        """
        if ind != 0:
            self.model.calibration_model.load_detector(
                self.widget.detectors_cb.currentText()
            )
            self._confirm_fields(*self._pixel_fields)
            emit_img_changed = (
                self.model.calibration_model.detector.shape
                == self.model.img_model.img_data.shape
            )
            # makes no sense to have transformations when loading a detector, however only emitting that the img changed
            # if detector and image have same size, otherwise the user should have the possibility to load an image
            # without error
            self.model.img_model.reset_transformations(emit_img_changed)
        else:
            self.model.calibration_model.reset_detector()
        self.update_detector_parameters_in_view()

    def load_detector_from_file(self):
        filename = open_file_dialog(
            self.widget,
            caption="Load Nexus Detector",
            directory=self.model.working_directories["image"],
            filter="*.h5",
        )

        if filename != "":
            self.model.calibration_model.load_detector_from_file(filename)
            self._confirm_fields(*self._pixel_fields)
            self.update_detector_parameters_in_view()

    def reset_detector_from_file(self):
        self.model.calibration_model.reset_detector()
        self.model.img_model.reset_transformations()
        self.update_detector_parameters_in_view()

    def _update_pixel_size_in_gui(self):
        self.widget.set_pixel_size(
            self.model.calibration_model.orig_pixel2,
            self.model.calibration_model.orig_pixel1,
        )

    def _update_spline_in_gui(self):
        if self.model.calibration_model.detector.splinefile is not None:
            self.widget.spline_filename_txt.setText(
                os.path.basename(self.model.calibration_model.detector.splinefile)
            )
        elif not self.model.calibration_model.detector.uniform_pixel:
            self.widget.spline_filename_txt.setText("from Detector")
        else:
            self.widget.spline_filename_txt.setText("None")

    def load_calibrants_list(self):
        """
        Loads all calibrants from the ExampleData/calibrants directory into the calibrants combobox. And loads number 7.
        """
        self._calibrants_file_list = []
        self._calibrants_file_names_list = []
        for file in os.listdir(calibrants_path):
            if file.endswith(".D"):
                self._calibrants_file_list.append(file)
                self._calibrants_file_names_list.append(file.split(".")[:-1][0])
        self._calibrants_file_list.sort()
        self._calibrants_file_names_list.sort()
        self.widget.calibrant_cb.blockSignals(True)
        self.widget.calibrant_cb.clear()
        self.widget.calibrant_cb.addItems(self._calibrants_file_names_list)
        self.widget.calibrant_cb.blockSignals(False)
        self.widget.calibrant_cb.setCurrentIndex(
            self._calibrants_file_names_list.index("LaB6")
        )  # to LaB6
        self.load_calibrant()

    def load_calibrant(self, wavelength_from="start_values"):
        """
        Loads the selected calibrant in the calibrant combobox into the calibration data.
        :param wavelength_from: determines which wavelength to use possible values: "start_values", "pyFAI"
        """
        current_index = self.widget.calibrant_cb.currentIndex()
        filename = os.path.join(
            self.model.calibration_model._calibrants_working_dir,
            self._calibrants_file_list[current_index],
        )
        self.model.calibration_model.set_calibrant(filename)

        if wavelength_from == "start_values":
            start_values = self.widget.get_start_values()
            wavelength = start_values["wavelength"]
        elif wavelength_from == "pyFAI":
            pyFAI_parameter, _ = (
                self.model.calibration_model.get_calibration_parameter()
            )
            if pyFAI_parameter["wavelength"] != 0:
                wavelength = pyFAI_parameter["wavelength"]
            else:
                start_values = self.widget.get_start_values()
                wavelength = start_values["wavelength"]
        else:
            start_values = self.widget.get_start_values()
            wavelength = start_values["wavelength"]

        self.model.calibration_model.calibrant.setWavelength_change2th(wavelength)
        try:
            integration_unit = self.model.current_configuration.integration_unit
        except:
            integration_unit = "2th_deg"

        calibrant_line_positions = self.convert_x_value(
            np.array(self.model.calibration_model.calibrant.get_2th()) / np.pi * 180,
            "2th_deg",
            integration_unit,
            wavelength,
        )
        # filter them to only show the ones visible with the current pattern;
        # the numbers stay indices into the full line list so they match the
        # ring spinbox used during peak picking
        calibrant_line_numbers = np.arange(1, len(calibrant_line_positions) + 1)
        if len(self.model.pattern.x) > 0:
            pattern_min = np.min(self.model.pattern.x)
            pattern_max = np.max(self.model.pattern.x)
            visible = (calibrant_line_positions > pattern_min) & (
                calibrant_line_positions < pattern_max
            )
            self._plot_calibrant_pattern_lines(
                positions=calibrant_line_positions[visible],
                numbers=calibrant_line_numbers[visible],
                name=self._calibrants_file_names_list[current_index],
            )
        # the calibrant's reflections are part of the validation overlays
        self._calibrant_overlays_changed()

    def set_calibrant(self, index):
        """
        :param index:
            index of a specific calibrant in the calibrant combobox
        """
        self.widget.calibrant_cb.setCurrentIndex(index)
        self.load_calibrant()

    def plot_image(self, autoscale=True):
        """
        Plots the current image loaded in img_data and autoscales the intensity.
        """
        self.widget.img_widget.plot_image(self.model.img_data, autoscale)
        self.widget.set_img_filename(self.model.img_model.filename)

    def search_peaks(self, x, y):
        """
        Searches peaks around a specific points (x,y) in the current image file. The algorithm for searching
        (either automatic or single peaksearch) is set in the GUI.
        :param x:
            x-Position for the search.
        :param y:
            y-Position for the search
        """
        # picking only belongs to the Pick Rings step — a click on the image
        # in any other step must not silently add peaks
        if self._wizard_widget().current_step() != 1:
            return

        x, y = (
            y,
            x,
        )  # indices for the img array are transposed compared to the mouse position

        # convert pixel coord into pixel index
        x, y = int(x), int(y)

        # filter events outside the image
        shape = self.model.img_model.img_data.shape
        if not (0 <= x < shape[0]):
            return
        if not (0 <= y < shape[1]):
            return

        peak_ind = self.widget.peak_num_sb.value()
        if self.widget.automatic_peak_search_rb.isChecked():
            points = self.model.calibration_model.find_peaks_automatic(
                x, y, peak_ind - 1
            )
        else:
            search_size = int(self.widget.search_size_sb.value())
            points = self.model.calibration_model.find_peak(
                x, y, search_size, peak_ind - 1
            )
        if len(points):
            self.plot_points(points)
            if self.widget.automatic_peak_num_inc_cb.isChecked():
                self.widget.peak_num_sb.setValue(peak_ind + 1)

    _UNCONFIRMED_TOOLTIP = (
        "Still at its default value — check that it matches your experiment."
    )

    def _setup_unconfirmed_fields(self):
        """Flags setup fields that still show their shipped defaults.

        A first-time user gets garbage out of a calibration run against the
        default wavelength, distance, pixel size or calibrant without any
        error — the orange border marks each value that has not been
        confirmed yet. A field counts as confirmed once the user edits it,
        a detector or calibration file provides it, or a calibration
        succeeds with it.
        """
        widget = self.widget
        detector_gb = (
            widget.calibration_control_widget.calibration_parameters_widget.detector_gb
        )
        sv_gb = (
            widget.calibration_control_widget.calibration_parameters_widget.start_values_gb
        )
        self._pixel_fields = (detector_gb.pixel_width_txt, detector_gb.pixel_height_txt)
        self._wavelength_fields = (widget.sv_wavelength_txt, widget.sv_energy_txt)

        self._unconfirmed_fields = {
            widget.sv_distance_txt,
            widget.sv_wavelength_txt,
            widget.sv_energy_txt,
            widget.calibrant_cb,
            *self._pixel_fields,
        }
        for field in self._unconfirmed_fields:
            field.setProperty("unconfirmed", True)
            field.setToolTip(self._UNCONFIRMED_TOOLTIP)
            field.style().unpolish(field)
            field.style().polish(field)

        # the energy display tracks the wavelength field, so an edit of
        # either confirms both
        widget.sv_wavelength_txt.textEdited.connect(
            lambda _: (
                sv_gb.update_energy_from_wavelength(),
                self._confirm_fields(*self._wavelength_fields),
            )
        )
        widget.sv_energy_txt.textEdited.connect(
            lambda _: (
                sv_gb.update_wavelength_from_energy(),
                self._confirm_fields(*self._wavelength_fields),
            )
        )
        widget.sv_distance_txt.textEdited.connect(
            lambda _: self._confirm_fields(widget.sv_distance_txt)
        )
        detector_gb.pixel_width_txt.textEdited.connect(
            lambda _: self._confirm_fields(detector_gb.pixel_width_txt)
        )
        detector_gb.pixel_height_txt.textEdited.connect(
            lambda _: self._confirm_fields(detector_gb.pixel_height_txt)
        )
        widget.calibrant_cb.activated.connect(
            lambda _: self._confirm_fields(widget.calibrant_cb)
        )

    def _confirm_fields(self, *fields):
        for field in fields:
            if field in self._unconfirmed_fields:
                self._unconfirmed_fields.discard(field)
                field.setProperty("unconfirmed", False)
                field.setToolTip("")
                field.style().unpolish(field)
                field.style().polish(field)

    _WIZARD_STEP_INDICES = {
        Step.IMAGE: 0,
        Step.PEAKS: 1,
        Step.CALIBRATE: 2,
        Step.VALIDATE: 3,
    }

    def _wizard_widget(self):
        return self.widget.calibration_control_widget.calibration_parameters_widget

    def _wizard_step_reachable(self, index, state=None):
        """A wizard page is reachable once its prerequisites exist: an image
        for peak picking, peaks (or a loaded calibration) for calibrating,
        a calibration for validating."""
        if state is None:
            state = self.guide.state
        if index <= 0:
            return True
        if index == 1:
            return state.image_loaded
        if index == 2:
            return state.image_loaded and (
                state.num_peaks > 0 or state.is_calibrated
            )
        return state.is_calibrated or self._manual_parameters_requested

    def wizard_next(self):
        self.go_to_wizard_step(self._wizard_widget().current_step() + 1)

    def wizard_back(self):
        self.go_to_wizard_step(self._wizard_widget().current_step() - 1)

    def go_to_wizard_step(self, index):
        wizard = self._wizard_widget()
        if not 0 <= index < wizard.step_stack.count():
            return
        if not self._wizard_step_reachable(index):
            # an (unlikely) click on a not-yet-reachable indicator button —
            # put the check mark back onto the current page
            self.widget.step_indicator.set_current_step(wizard.current_step())
            return
        self.widget.set_wizard_step(index)
        self.update_guide_in_view()

    def update_guide_in_view(self, state=None):
        """Pushes the guide's derived workflow state into the view: the step
        indicator, the wizard navigation, the peak counter, the validation
        views and the readiness of the Calibrate/Refine/Save buttons.
        """
        if state is None:
            state = self.guide.state

        if state.is_calibrated:
            # a working calibration exists, so its setup values are evidently
            # usable — whether calibrated here or loaded from a file
            self._confirm_fields(*list(self._unconfirmed_fields))

        self.widget.calibration_display_widget.empty_state_lbl.setVisible(
            not state.image_loaded
        )

        wizard = self._wizard_widget()
        step_indicator = self.widget.step_indicator
        for step, index in self._WIZARD_STEP_INDICES.items():
            step_indicator.set_step_status(
                index, state.step_status[step].name.lower()
            )
            step_indicator.set_step_enabled(
                index, self._wizard_step_reachable(index, state)
            )

        # a state regression (e.g. switching to an uncalibrated
        # configuration) can strand the wizard on a page that is no longer
        # reachable — fall back to the closest one that is
        current = wizard.current_step()
        while current > 0 and not self._wizard_step_reachable(current, state):
            current -= 1
        if current != wizard.current_step():
            self.widget.set_wizard_step(current)

        last = wizard.step_stack.count() - 1
        wizard.back_btn.setVisible(current > 0)
        wizard.back_btn.setEnabled(current > 0)
        wizard.next_btn.setVisible(current < last)
        if current < last:
            wizard.next_btn.setText(
                "Next: {} ›".format(WIZARD_STEP_TITLES[current + 1])
            )
        if current == last:
            # Back is the only navigation on the result page — let it fill
            # the row and say where it goes instead of floating alone
            wizard.back_btn.setMaximumWidth(16777215)
            wizard.back_btn.setText(
                "‹ Back: {}".format(WIZARD_STEP_TITLES[current - 1])
            )
        else:
            wizard.back_btn.setMaximumWidth(80)
            wizard.back_btn.setText("‹ Back")
        wizard.next_btn.setEnabled(
            current < last and self._wizard_step_reachable(current + 1, state)
        )
        if current == 0 and not state.image_loaded:
            wizard.next_btn.setToolTip("Load an image first.")
        elif current == 1 and not (state.num_peaks or state.is_calibrated):
            wizard.next_btn.setToolTip(
                "Pick at least one peak first — click on the innermost ring "
                "in the image."
            )
        elif current == 2 and not state.is_calibrated:
            wizard.next_btn.setToolTip("Run Calibrate first.")
        else:
            wizard.next_btn.setToolTip("")

        # the cake and pattern views are for judging the finished
        # calibration — they appear only on the validation step
        on_validation = current == last
        self.widget.calibration_display_widget.show_validation_views(on_validation)
        if on_validation and self._calibrant_overlays_dirty:
            self._update_calibrant_overlays()

        if state.num_peaks == 0:
            self.widget.peak_counter_lbl.setText("No peaks selected")
        else:
            self.widget.peak_counter_lbl.setText(
                "{} peaks on {} ring{}".format(
                    state.num_peaks,
                    state.num_rings,
                    "" if state.num_rings == 1 else "s",
                )
            )

        self.widget.calibrate_btn.setEnabled(state.num_peaks > 0)
        self.widget.calibrate_btn.setToolTip(
            ""
            if state.num_peaks > 0
            else "Needs picked peaks — click on the innermost ring in the image first."
        )
        self.widget.refine_btn.setEnabled(state.is_calibrated)
        self.widget.refine_btn.setToolTip(
            ""
            if state.is_calibrated
            else "Needs an existing calibration — run Calibrate or load a *.poni file first."
        )
        self.widget.save_calibration_btn.setEnabled(state.is_calibrated)

    def _on_points_changed(self):
        """Keeps the ring counter and the plotted peaks in step with the model.

        Picking advances the counter, so undoing a pick has to take it back —
        otherwise the next pick lands on the wrong ring. This lives here
        rather than in the undo button because the points can change from
        anywhere: the keyboard shortcut, the sidebar buttons, a script.
        """
        selections = len(self.model.calibration_model.points)
        if (
            selections < self._last_peak_selection_count
            and self.widget.automatic_peak_num_inc_cb.isChecked()
        ):
            steps = self._last_peak_selection_count - selections
            self.widget.peak_num_sb.setValue(
                max(self.widget.peak_num_sb.value() - steps, 1)
            )
        self._last_peak_selection_count = selections
        self.update_peak_table()
        self.plot_points()

    def _on_configuration_selected(self, _ind=None):
        """Follows a configuration switch or project reset: the calibration
        model is a different instance now, so its instance signals need
        re-wiring, and the peak table/plot must show the new state."""
        calibration_model = self.model.calibration_model
        if not calibration_model.points_changed.has_listener(self._on_points_changed):
            calibration_model.points_changed.connect(self._on_points_changed)
        if not calibration_model.detector_reset.has_listener(
            self.update_detector_parameters_in_view
        ):
            calibration_model.detector_reset.connect(
                self.update_detector_parameters_in_view
            )
        if not calibration_model.detector_reset.has_listener(
            self.show_detector_reset_message_box
        ):
            calibration_model.detector_reset.connect(
                self.show_detector_reset_message_box
            )
        if not calibration_model.parameters_changed.has_listener(
            self._calibrant_overlays_changed
        ):
            calibration_model.parameters_changed.connect(
                self._calibrant_overlays_changed
            )
        # the calibrant is not part of the configuration — sync the new
        # model from the combo box and redraw the pattern's calibrant lines
        self.load_calibrant(wavelength_from="pyFAI")
        self._calibrant_overlays_dirty = True
        if self._mode_active:
            # the overlays are visible on every wizard step, so a stale
            # ring drawing must not survive a reset or configuration switch
            self._update_calibrant_overlays()
        # the ring counter continues after the new configuration's picked
        # rings — and returns to 1 on a project reset
        selections = calibration_model.params.peak_selections
        self.widget.peak_num_sb.setValue(
            max(ring for ring, _ in selections) + 2 if selections else 1
        )
        # a plain refresh — the ring-counter bookkeeping in
        # _on_points_changed must not treat the cross-configuration count
        # difference as an undo
        self._last_peak_selection_count = len(calibration_model.points)
        self.update_peak_table()
        self.plot_points()

    def _selected_pick_rows(self):
        selection_model = self.widget.peak_table.selectionModel()
        if selection_model is None:
            return []
        return sorted(index.row() for index in selection_model.selectedRows())

    def update_peak_table(self):
        """Rebuilds the peak-group table from the model, one row per pick,
        preserving the row selection where possible.

        The ring spinboxes are updated in place rather than recreated — a
        rebuild triggered from a spinbox's own valueChanged must not delete
        the emitting widget mid-signal.
        """
        table = self.widget.peak_table
        selections = self.model.calibration_model.params.peak_selections
        previously_selected = set(self._selected_pick_rows())

        self._updating_peak_table = True
        table.blockSignals(True)
        table.setRowCount(len(selections))
        for row, (ring_ind, positions) in enumerate(selections):
            ring_sb = table.cellWidget(row, 0)
            if ring_sb is None:
                ring_sb = QtWidgets.QSpinBox()
                ring_sb.setMinimum(1)
                ring_sb.setMaximum(999)
                ring_sb.setAlignment(
                    QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter
                )
                ring_sb.setFrame(False)
                ring_sb.valueChanged.connect(
                    lambda value, row=row: self.peak_ring_changed(row, value)
                )
                table.setCellWidget(row, 0, ring_sb)
            ring_sb.blockSignals(True)
            ring_sb.setValue(ring_ind + 1)
            ring_sb.blockSignals(False)

            count_item = QtWidgets.QTableWidgetItem(str(len(positions)))
            count_item.setTextAlignment(QtCore.Qt.AlignCenter)
            count_item.setFlags(count_item.flags() & ~QtCore.Qt.ItemIsEditable)
            table.setItem(row, 1, count_item)

            positions_array = np.atleast_2d(np.array(positions))
            pos_item = QtWidgets.QTableWidgetItem(
                "%.0f, %.0f"
                % (positions_array[:, 1].mean(), positions_array[:, 0].mean())
            )
            pos_item.setFlags(pos_item.flags() & ~QtCore.Qt.ItemIsEditable)
            pos_item.setToolTip("Mean position of the group's peaks (x, y)")
            table.setItem(row, 2, pos_item)

        for row in previously_selected:
            if row < table.rowCount():
                table.selectionModel().select(
                    table.model().index(row, 0),
                    QtCore.QItemSelectionModel.Select
                    | QtCore.QItemSelectionModel.Rows,
                )
        table.blockSignals(False)
        self._updating_peak_table = False

    def peak_table_selection_changed(self):
        if self._updating_peak_table:
            return
        self.plot_points()

    def peak_ring_changed(self, row, ring_number):
        """Reassigns a pick to another ring via its table spinbox."""
        if self._updating_peak_table:
            return
        self.model.calibration_model.set_peak_selection_ring(
            row, ring_number - 1
        )

    def current_ring_changed(self):
        """Selects (and thereby highlights) every peak group belonging to
        the newly chosen current ring."""
        self._select_rows_of_ring(self.widget.peak_num_sb.value() - 1)
        self.plot_points()

    def _select_rows_of_ring(self, ring_ind):
        table = self.widget.peak_table
        selection_model = table.selectionModel()
        if selection_model is None:
            return
        rings = self.model.calibration_model.points_index
        self._updating_peak_table = True
        selection_model.clearSelection()
        for row, row_ring in enumerate(rings):
            if int(row_ring) == int(ring_ind):
                selection_model.select(
                    table.model().index(row, 0),
                    QtCore.QItemSelectionModel.Select
                    | QtCore.QItemSelectionModel.Rows,
                )
        self._updating_peak_table = False

    def delete_selected_peaks(self):
        """Deletes the peak groups selected in the table."""
        for row in sorted(self._selected_pick_rows(), reverse=True):
            self.model.calibration_model.remove_peak_selection(row)

    def plot_points(self, _=None):
        """
        Plots all picked peaks into the image view. Peaks belonging to the
        currently selected ring get their own color; groups selected in the
        table are marked by a slightly larger dot with a white outline.
        """
        picks = self.model.calibration_model.points
        rings = self.model.calibration_model.points_index
        self.widget.img_widget.clear_scatter_plot()
        if len(picks) == 0:
            return
        selected_rows = set(self._selected_pick_rows())
        current_ring = self.widget.peak_num_sb.value() - 1
        highlight_pen = pg.mkPen(255, 255, 255, 255, width=2)
        normal_pen = pg.mkPen(255, 255, 255, 90)
        xs, ys, brushes, sizes, pens = [], [], [], [], []
        for pick_ind, (positions, ring_ind) in enumerate(zip(picks, rings)):
            if int(ring_ind) == current_ring:
                brush = pg.mkBrush(255, 140, 0, 255)
            else:
                brush = pg.mkBrush(255, 0, 0, 255)
            if pick_ind in selected_rows:
                pen = highlight_pen
                size = 9
            else:
                pen = normal_pen
                size = 7
            for position in np.atleast_2d(positions):
                xs.append(position[1] + 0.5)
                ys.append(position[0] + 0.5)
                brushes.append(brush)
                sizes.append(size)
                pens.append(pen)
        self.widget.img_widget.img_scatter_plot_item.addPoints(
            x=xs, y=ys, brush=brushes, size=sizes, pen=pens
        )

    def clear_peaks(self):
        """
        Deletes all points/peaks in the calibration_data and in the GUI.
        """
        self.model.calibration_model.clear_peaks()
        self.widget.img_widget.clear_scatter_plot()
        self.widget.peak_num_sb.setValue(1)

    def load_spline_btn_click(self):
        filename = open_file_dialog(
            self.widget,
            caption="Load Distortion Spline File",
            directory=self.model.working_directories["image"],
            filter="*.spline",
        )

        if filename != "":
            self.model.calibration_model.load_distortion(filename)
            self._update_spline_in_gui()
            self.widget.spline_reset_btn.setEnabled(True)

    def reset_spline_btn_click(self):
        self.model.calibration_model.reset_distortion_correction()
        self.widget.spline_filename_txt.setText("None")
        self.widget.spline_reset_btn.setEnabled(False)

    def wavelength_cb_changed(self, value):
        """
        Sets the fit_wavelength parameter in the calibration data according to the GUI state.
        """
        self.model.calibration_model.fit_wavelength = value

    def distance_cb_changed(self, value):
        """The distance checkboxes only need to stay in sync (done by the
        mirror binding) — their state is read via get_fixed_values() when a
        calibration or refinement starts."""

    def update_fixed_values(self):
        self.model.calibration_model.set_fixed_values(self.widget.get_fixed_values())

    def calibrate(self):
        """
        Performs calibration based on the previously inputted/searched peaks and start values.
        """
        logger.info("Starting calibration")
        if len(self.model.calibration_model.points) == 0:
            QtWidgets.QMessageBox.critical(
                self.widget,
                "No peaks defined!",
                "No peaks defined. Please define initial peaks first as a starting point.<br><br><a href='https://dioptas.readthedocs.io/en/stable/calibration.html'>Consult the manual for more information. </a>",
                QtWidgets.QMessageBox.Ok,
            )
            return
        self.load_calibrant()  # load the right calibration file...
        self.model.calibration_model.set_start_values(self.widget.get_start_values())
        self.model.calibration_model.set_pixel_size(self.widget.get_pixel_size())
        self.model.calibration_model.set_fixed_values(self.widget.get_fixed_values())
        progress_dialog = self.create_progress_dialog(
            "Calibrating.", "", 0, show_cancel_btn=False
        )
        self.model.calibration_model.calibrate()

        progress_dialog.close()

        if self.widget.options_automatic_refinement_cb.isChecked():
            self.automatic_refinement()
        else:
            self.update_all()
        self.update_calibration_parameter_in_view()

    def refine(self):
        logger.info("Refining calibration")
        self.model.calibration_model.set_fixed_values(self.widget.get_fixed_values())

        if self.widget.options_automatic_refinement_cb.isChecked():
            self.automatic_refinement()
        else:
            progress_dialog = self.create_progress_dialog(
                "Refining.", "", 0, show_cancel_btn=False
            )
            self.model.calibration_model.refine()
            progress_dialog.close()
            self.update_all()

        self.update_calibration_parameter_in_view()

    def create_progress_dialog(
        self, text_str, abort_str, end_value, show_cancel_btn=True
    ):
        """Creates a Progress Bar Dialog.
        :param text_str:  Main message string
        :param abort_str:  Text on the abort button
        :param end_value:  Number of steps for which the progressbar is being used
        :param show_cancel_btn: Whether the cancel button should be shown.
        :return: ProgressDialog reference which is already shown in the interface
        :rtype: QtWidgets.ProgressDialog
        """
        progress_dialog = QtWidgets.QProgressDialog(
            text_str, abort_str, 0, end_value, self.widget
        )

        display_widget = self.widget.calibration_display_widget
        progress_dialog.move(
            int(
                display_widget.x()
                + display_widget.size().width() / 2.0
                - progress_dialog.size().width() / 2.0
            ),
            int(
                display_widget.y()
                + display_widget.size().height() / 2.0
                - progress_dialog.size().height() / 2.0
            ),
        )

        progress_dialog.setWindowTitle("   ")
        progress_dialog.setWindowModality(QtCore.Qt.WindowModal)
        progress_dialog.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        if not show_cancel_btn:
            progress_dialog.setCancelButton(None)
        progress_dialog.show()
        QtWidgets.QApplication.processEvents()
        return progress_dialog

    def automatic_refinement(self):
        """
        Refines the current calibration parameters by searching peaks in the approximate positions and subsequent
        refinement. Parameters for this search are set in the GUI.
        """

        # Basic Algorithm:
        # search peaks on first and second ring
        #   calibrate based on those two rings
        #   repeat until ring_ind = max_ind:
        #       search next ring
        #       calibrate based on all previous found points

        num_rings = self.widget.options_num_rings_sb.value()

        progress_dialog = self.create_progress_dialog(
            "Refining Calibration.", "Abort", num_rings
        )
        # remember the manually picked peaks so they can be restored if the
        # automatic search comes up empty (e.g. threshold set too low)
        previous_peak_selections = self.model.calibration_model.params.peak_selections
        previous_peak_num = self.widget.peak_num_sb.value()
        self.clear_peaks()
        self.load_calibrant(wavelength_from="pyFAI")  # load right calibration file

        # get options
        algorithm = str(self.widget.options_peaksearch_algorithm_cb.currentText())
        delta_tth = float(self.widget.options_delta_tth_txt.text())
        intensity_min_factor = float(
            self.widget.options_intensity_mean_factor_sb.value()
        )
        intensity_max = float(self.widget.options_intensity_limit_txt.text())

        self.model.calibration_model.setup_peak_search_algorithm(algorithm)

        if self.widget.use_mask_cb.isChecked():
            mask = self.model.mask_model.get_mask()
        else:
            mask = None

        self.model.calibration_model.search_peaks_on_ring(
            0, delta_tth, intensity_min_factor, intensity_max, mask
        )
        self.widget.peak_num_sb.setValue(2)
        progress_dialog.setValue(1)
        self.model.calibration_model.search_peaks_on_ring(
            1, delta_tth, intensity_min_factor, intensity_max, mask
        )
        self.widget.peak_num_sb.setValue(3)
        if len(self.model.calibration_model.points):
            self.model.calibration_model.refine()
            self.plot_points()
        else:
            logger.warning(
                "Did not find any points with the specified parameters for the first two rings"
            )

        progress_dialog.setValue(2)

        refinement_canceled = False
        for i in range(num_rings - 2):
            try:
                points = self.model.calibration_model.search_peaks_on_ring(
                    i + 2, delta_tth, intensity_min_factor, intensity_max, mask
                )
            except NotEnoughSpacingsInCalibrant:
                QtWidgets.QMessageBox.critical(
                    self.widget,
                    "Not enough d-spacings!.",
                    "The calibrant file does not contain enough d-spacings.",
                    QtWidgets.QMessageBox.Ok,
                )
                break
            self.widget.peak_num_sb.setValue(i + 4)
            if len(self.model.calibration_model.points):
                self.plot_points(points)
                QtWidgets.QApplication.processEvents()
                QtWidgets.QApplication.processEvents()
                self.model.calibration_model.refine()
            else:
                logger.warning("Did not find enough points with the specified parameters")
            progress_dialog.setLabelText(
                "Refining Calibration. \n" "Finding peaks on Ring {0}.".format(i + 3)
            )
            progress_dialog.setValue(i + 3)
            if progress_dialog.wasCanceled():
                refinement_canceled = True
                break
        progress_dialog.close()
        del progress_dialog

        QtWidgets.QApplication.processEvents()
        peaks_found = len(self.model.calibration_model.points) > 0
        if not peaks_found:
            message = (
                "Automatic peak search did not find any peaks.\nThis might be due to "
                "the peak search settings or the wrong calibrant being selected."
            )
            if len(previous_peak_selections):
                self.model.calibration_model.params.peak_selections = (
                    previous_peak_selections
                )
                self.widget.peak_num_sb.setValue(previous_peak_num)
                message += "\nThe previously picked peaks have been restored."
            QtWidgets.QMessageBox.critical(
                self.widget,
                "No peaks found!",
                message,
                QtWidgets.QMessageBox.Ok,
            )
        if not refinement_canceled and peaks_found:
            self.update_all()

    def load_calibration(self):
        """
        Loads a '*.poni' file and updates the calibration data class
        """
        logger.info("Loading calibration file")
        filename = open_file_dialog(
            self.widget,
            caption="Load calibration...",
            directory=self.model.working_directories["calibration"],
            filter="*.poni",
        )
        if filename != "":
            self.model.working_directories["calibration"] = os.path.dirname(filename)
            try:
                self.model.calibration_model.load(filename)
            except FileLoadingError as e:
                self._show_file_error_message(str(e))
                return
            self.update_all(integrate=self.model.img_model.filename != "")

    def update_mask_gui(self):
        """
        Updates the mask checkbox and transparency state from the current
        configuration, then replots the mask.
        """
        self.widget.use_mask_cb.setChecked(bool(self.model.use_mask))
        self.widget.mask_transparent_cb.setChecked(bool(self.model.transparent_mask))
        self.plot_mask()

    def use_mask_cb_changed(self):
        self.model.use_mask = self.widget.use_mask_cb.isChecked()
        self.model.mask_changed.emit()

    def plot_mask(self):
        """
        Plots the mask
        """
        state = self.widget.use_mask_cb.isChecked()
        if state:
            self.widget.img_widget.activate_mask()
            self.widget.img_widget.plot_mask(self.model.mask_model.get_display_mask())
        else:
            self.widget.img_widget.deactivate_mask()

    def mask_transparent_status_changed(self, state):
        """
        :param state: Boolean value whether the mask is being transparent
        :type state: bool
        """
        if state:
            self.widget.img_widget.set_mask_color([255, 0, 0, 100])
        else:
            self.widget.img_widget.set_mask_color([255, 0, 0, 255])

    def update_all(self, integrate=True):
        """
        Performs 1d and 2d integration based on the current calibration parameter set. Updates the GUI interface
        accordingly with the new diffraction pattern and cake image.
        """
        if integrate:
            progress_dialog = self.create_progress_dialog(
                "Integrating to cake.", "", 0, show_cancel_btn=False
            )
            QtWidgets.QApplication.processEvents()
            self.model.current_configuration.integrate_image_2d()
            progress_dialog.setLabelText("Integrating to pattern.")
            QtWidgets.QApplication.processEvents()
            QtWidgets.QApplication.processEvents()
            self.model.current_configuration.integrate_image_1d()
            progress_dialog.close()
        self.widget.cake_widget.plot_image(self.model.cake_data, False)
        self.widget.cake_widget.auto_level()

        self.widget.pattern_widget.plot_data(*self.model.pattern.data)
        calibrant_line_positions = self.convert_x_value(
            np.array(self.model.calibration_model.calibrant.get_2th())
            / np.pi
            * 180,
            "2th_deg",
            self.model.current_configuration.integration_unit,
            None,
        )
        self._plot_calibrant_pattern_lines(
            positions=calibrant_line_positions,
            numbers=np.arange(1, len(calibrant_line_positions) + 1),
        )

        if self.model.current_configuration.integration_unit == "2th_deg":
            self.widget.pattern_widget.pattern_plot.setLabel("bottom", "2θ", "°")
        elif self.model.current_configuration.integration_unit == "q_A^-1":
            self.widget.pattern_widget.pattern_plot.setLabel(
                "bottom", "Q", "A<sup>-1</sup>"
            )
        elif self.model.current_configuration.integration_unit == "d_A":
            self.widget.pattern_widget.pattern_plot.setLabel("bottom", "d", "A")

        self.widget.pattern_widget.view_box.autoRange()
        self.update_calibration_parameter_in_view()
        # marks the overlays dirty for the freshly integrated cake, too
        self.load_calibrant("pyFAI")
        # a calibration (or loaded .poni) exists now — bring the wizard to
        # the validation page, where image, cake and pattern are shown
        # side by side and the overlays get drawn once
        self.go_to_wizard_step(3)

    def update_calibration_parameter_in_view(self):
        """
        Reads the calibration parameter from the calibration_data object and displays them in the GUI.
        :return:
        """
        pyFAI_parameter, fit2d_parameter = (
            self.model.calibration_model.get_calibration_parameter()
        )
        self.widget.set_calibration_parameters(pyFAI_parameter, fit2d_parameter)
        self._update_spline_in_gui()

    def update_detector_parameters_in_view(self):
        detector_mode = self.model.calibration_model.detector_mode

        self.widget.enable_pixel_size_txt(detector_mode == DetectorModes.CUSTOM)
        self.widget.detectors_cb.setVisible(
            detector_mode in (DetectorModes.CUSTOM, DetectorModes.PREDEFINED)
        )
        self.widget.detector_name_lbl.setVisible(detector_mode == DetectorModes.NEXUS)
        self.widget.detector_reset_btn.setEnabled(detector_mode == DetectorModes.NEXUS)

        if detector_mode == DetectorModes.CUSTOM:
            self.widget.detectors_cb.blockSignals(True)
            self.widget.detectors_cb.setCurrentText("Custom")
            self.widget.detectors_cb.blockSignals(False)

        if detector_mode == DetectorModes.PREDEFINED:
            self.widget.detectors_cb.blockSignals(True)
            self.widget.detectors_cb.setCurrentText(
                self.model.calibration_model.detector.name
            )
            self.widget.detectors_cb.blockSignals(False)

        if detector_mode == DetectorModes.NEXUS:
            self.widget.detector_name_lbl.setText(
                os.path.basename(self.model.calibration_model.detector.filename)
            )

        self._update_pixel_size_in_gui()
        self._update_spline_in_gui()

    def show_detector_reset_message_box(self):
        QtWidgets.QMessageBox.critical(
            self.widget,
            "Shape mismatch.",
            "Image and detector definition do not have the same shape!\n"
            + "The Detector has been reset.",
            QtWidgets.QMessageBox.Ok,
        )

    def save_calibration(self):
        """
        Saves the current calibration in a file.
        :return:
        """
        logger.info("Saving calibration file")

        filename = save_file_dialog(
            self.widget,
            "Save calibration...",
            self.model.working_directories["calibration"],
            "*.poni",
        )
        if filename != "":
            self.model.working_directories["calibration"] = os.path.dirname(filename)
            if not filename.rsplit(".", 1)[-1] == "poni":
                filename = filename + ".poni"
            self.model.calibration_model.save(filename)

    def update_img_mouse_position_lbl(self, x, y):
        """
        Displays the values of x, y (usually mouse -position) and their image intensity in the GUI.
        """
        # x, y = pos
        try:
            if x > 0 and y > 0:
                str = "x: %.1f y: %.1f I: %.0f" % (
                    x,
                    y,
                    self.widget.img_widget.img_data.T[
                        int(np.round(x)), int(np.round(y))
                    ],
                )
            else:
                str = "x: %.1f y: %.1f" % (x, y)
        except (IndexError, AttributeError):
            str = "x: %.1f y: %.1f" % (x, y)
        self.widget.pos_lbl.setText(str)

    def update_cake_mouse_position_lbl(self, x, y):
        """
        Displays the values of x, y (usually mouse -position) and their cake intensity in the GUI.
        """
        # x, y = pos
        try:
            if x > 0 and y > 0:
                str = "x: %.1f y: %.1f I: %.0f" % (
                    x,
                    y,
                    self.widget.cake_widget.img_data.T[
                        int(np.round(x)), int(np.round(y))
                    ],
                )
            else:
                str = "x: %.1f y: %.1f" % (x, y)
        except (IndexError, AttributeError):
            str = "x: %.1f y: %.1f" % (x, y)
        self.widget.pos_lbl.setText(str)

    def update_pattern_mouse_position_lbl(self, x, y):
        """
        Displays the values of x, y (pattern mouse-position) in the GUI.
        """
        # x, y = pos
        str = "x: %.1f y: %.1f" % (x, y)
        self.widget.pos_lbl.setText(str)

    def convert_x_value(self, value, previous_unit, new_unit, wavelength):
        if wavelength is None:
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
