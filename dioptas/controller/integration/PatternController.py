# SPDX-License-Identifier: MIT

import os

import numpy as np
from qtpy import QtWidgets, QtCore

from ...widgets.UtilityWidgets import save_file_dialog, open_file_dialog
from ...model.util.calc import convert_units
from ...model.util.file_type import FileLoadingError

# imports for type hinting in PyCharm -- DO NOT DELETE
from ...model.DioptasModel import DioptasModel
from ...widgets.integration import IntegrationWidget

from ..binding import Binder


class PatternController:
    """
    IntegrationPatternController handles all the interaction from the IntegrationView with the pattern data.
    It manages the auto integration of image files to  in addition to pattern browsing and changing of units
    (2 Theta, Q, A)
    """

    def __init__(self, widget, dioptas_model):
        """
        :param widget: Reference to an IntegrationWidget
        :param dioptas_model: reference to DioptasModel object

        :type widget: IntegrationWidget
        :type dioptas_model: DioptasModel
        """

        self.widget = widget
        self.model = dioptas_model
        self.binder = Binder(field_events=self.model.configuration_params_changed)

        self.create_subscriptions()
        self.create_gui_signals()
        self.binder.refresh()

    def create_subscriptions(self):
        # Data subscriptions
        self.model.pattern_changed.connect(self.plot_pattern)
        self.model.configuration_selected.connect(self.update_gui)
        self.model.integration_unit_changed.connect(self._integration_unit_changed)
        self.binder.connect_refresh(self.model.configuration_selected)

        # Gui subscriptions
        # self.widget.img_widget.roi.sigRegionChangeFinished.connect(self.image_changed)
        self.widget.pattern_widget.mouse_left_clicked.connect(self.pattern_left_click)
        self.model.clicked_tth_changed.connect(self.set_line_position)
        self.widget.pattern_widget.mouse_moved.connect(self.show_pattern_mouse_position)

    def create_gui_signals(self):
        """
        creating callbacks for the ui controls
        """

        # file callbacks
        self.binder.bind_checkbox(
            self.widget.pattern_autocreate_cb,
            lambda: self.model.current_configuration,
            "auto_save_integrated_pattern",
        )
        self.widget.pattern_load_btn.clicked.connect(self.load)
        self.widget.pattern_previous_btn.clicked.connect(self.load_previous)
        self.widget.pattern_next_btn.clicked.connect(self.load_next)
        self.widget.pattern_filename_txt.editingFinished.connect(
            self.filename_txt_changed
        )

        self.widget.pattern_directory_btn.clicked.connect(
            self.pattern_directory_btn_click
        )
        self.widget.pattern_browse_by_name_rb.clicked.connect(
            self.set_iteration_mode_number
        )
        self.widget.pattern_browse_by_time_rb.clicked.connect(
            self.set_iteration_mode_time
        )

        self.widget.pattern_directory_txt.editingFinished.connect(
            self.pattern_directory_txt_changed
        )

        # unit callbacks (the batch view's unit buttons are owned by
        # BatchController; both write the same model property)
        self.widget.pattern_tth_btn.clicked.connect(self.set_unit_tth)
        self.widget.pattern_q_btn.clicked.connect(self.set_unit_q)
        self.widget.pattern_d_btn.clicked.connect(self.set_unit_d)

        # quick actions
        self.widget.qa_save_pattern_btn.clicked.connect(self.save_pattern)

        # integration controls
        self.widget.automatic_binning_cb.stateChanged.connect(
            self.integration_binning_changed
        )
        self.widget.bin_count_txt.editingFinished.connect(
            self.integration_binning_changed
        )
        self.widget.supersampling_sb.valueChanged.connect(self.supersampling_changed)

        # pattern_plot interaction
        self.widget.keyPressEvent = self.key_press_event

        # pattern_plot auto range functions
        self.widget.pattern_auto_range_btn.clicked.connect(
            self.pattern_auto_range_btn_click_callback
        )
        self.widget.pattern_widget.auto_range_status_changed.connect(
            self.widget.pattern_auto_range_btn.setChecked
        )

        # pattern_plot antialias
        self.widget.antialias_btn.toggled.connect(
            self.widget.pattern_widget.set_antialias
        )

        # pattern_plot y-scale toggles
        self.widget.pattern_log_btn.clicked.connect(self._y_scale_log_clicked)
        self.widget.pattern_sqrt_btn.clicked.connect(self._y_scale_sqrt_clicked)

        self.widget.pattern_header_xy_cb.clicked.connect(
            self.update_pattern_file_endings
        )
        self.widget.pattern_header_xye_cb.clicked.connect(
            lambda checked: self._error_file_format_clicked(
                self.widget.pattern_header_xye_cb, checked
            )
        )
        self.widget.pattern_header_chi_cb.clicked.connect(
            self.update_pattern_file_endings
        )
        self.widget.pattern_header_dat_cb.clicked.connect(
            self.update_pattern_file_endings
        )
        self.widget.pattern_header_fxye_cb.clicked.connect(
            lambda checked: self._error_file_format_clicked(
                self.widget.pattern_header_fxye_cb, checked
            )
        )

    def update_pattern_file_endings(self):
        res = []
        if self.widget.pattern_header_xy_cb.isChecked():
            res.append(".xy")
        if self.widget.pattern_header_xye_cb.isChecked():
            res.append(".xye")
        if self.widget.pattern_header_chi_cb.isChecked():
            res.append(".chi")
        if self.widget.pattern_header_dat_cb.isChecked():
            res.append(".dat")
        if self.widget.pattern_header_fxye_cb.isChecked():
            res.append(".fxye")
        self.model.current_configuration.integrated_patterns_file_formats = res

    def _error_file_format_clicked(self, checkbox, checked):
        if checked and not self._ensure_poisson_errors():
            checkbox.blockSignals(True)
            checkbox.setChecked(False)
            checkbox.blockSignals(False)
        self.update_pattern_file_endings()

    def _ensure_poisson_errors(self) -> bool:
        configuration = self.model.current_configuration
        if (
            configuration.calculate_poisson_errors
            and self.model.pattern_model.errors is not None
        ):
            return True

        if (
            self.model.pattern_model.pattern_source != "integrated"
            or not configuration.is_calibrated
            or not self.model.img_model.filename
        ):
            self.widget.show_error_msg(
                "Poisson errors can only be calculated for an integrated image."
            )
            return False

        answer = QtWidgets.QMessageBox.question(
            self.widget,
            "Calculate Poisson errors?",
            "The current pattern has no calculated errors. Enable Poisson "
            "error calculation and reintegrate it now?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Cancel,
            QtWidgets.QMessageBox.Yes,
        )
        if answer != QtWidgets.QMessageBox.Yes:
            return False

        # Changing the option normally triggers automatic integration. Hold
        # that reaction so this explicit request performs exactly one pass,
        # even when automatic integration is enabled.
        with configuration.pattern_integration.hold(flush=False):
            configuration.calculate_poisson_errors = True
        configuration.integrate_image_1d()
        return self.model.pattern_model.errors is not None

    def plot_pattern(self):
        if self.widget.bkg_pattern_inspect_btn.isChecked():
            self.widget.pattern_widget.plot_data(
                *self.model.pattern.auto_background_before_subtraction_pattern.data,
                name=self.model.pattern.name
            )
            self.widget.pattern_widget.plot_bkg(
                *self.model.pattern.auto_background_pattern.data
            )
        else:
            self.widget.pattern_widget.plot_data(
                *self.model.pattern.data, name=self.model.pattern.name
            )
            self.widget.pattern_widget.plot_bkg([], [])

        # update the bkg_name
        if self.model.pattern_model.background_pattern is not None:
            self.widget.bkg_name_lbl.setText(
                "Bkg: " + self.model.pattern_model.background_pattern.name
            )
            self.widget.bkg_name_lbl.setText(
                "Bkg: " + self.model.pattern_model.background_pattern.name
            )
        else:
            self.widget.bkg_name_lbl.setText("")

    def reset_background(self, popup=True):
        self.widget.show_cb_set_checked(
            self.model.pattern_model.bkg_ind, True
        )  # show the old overlay again
        self.model.pattern_model.bkg_ind = -1
        self.model.pattern.unset_background_pattern()
        self.widget.overlay_set_as_bkg_btn.setChecked(False)

    def integration_binning_changed(self):
        current_value = self.widget.automatic_binning_cb.isChecked()
        if current_value:
            self.model.current_configuration.integration_rad_points = None
        else:
            self.model.current_configuration.integration_rad_points = int(
                str(self.widget.bin_count_txt.text())
            )
        self.widget.bin_count_txt.setEnabled(not current_value)

    def supersampling_changed(self, value):
        self.model.calibration_model.set_supersampling(value)
        self.model.img_model.img_changed.emit()

    def save_pattern(self):
        img_filename, _ = os.path.splitext(
            os.path.basename(self.model.img_model.filename)
        )
        filename = save_file_dialog(
            self.widget,
            "Save Pattern Data.",
            os.path.join(
                self.model.working_directories["pattern"], img_filename + ".xy"
            ),
            (
                "Data (*.xy);;Data with errors (*.xye);;Data (*.chi);;Data (*.dat);;GSAS with errors (*.fxye);;png (*.png);;svg (*.svg)"
            ),
        )

        if filename != "":
            self.model.working_directories["pattern"] = os.path.dirname(filename)
            if filename.endswith(".png"):
                self.widget.pattern_widget.save_png(filename)
            elif filename.endswith(".svg"):
                self.widget.pattern_widget.save_svg(filename)
            else:
                if filename.lower().endswith((".xye", ".fxye")):
                    if not self._ensure_poisson_errors():
                        return
                self.model.current_configuration.save_pattern(
                    filename, subtract_background=True
                )

    def load(self, *args, **kwargs):
        filename = kwargs.get("filename", None)
        if filename is None:
            filename = open_file_dialog(
                self.widget,
                caption="Load Pattern",
                directory=self.model.working_directories["pattern"],
            )

        if filename != "":
            self.model.working_directories["pattern"] = os.path.dirname(filename)
            try:
                self.model.pattern_model.load_pattern(filename)
            except FileLoadingError as e:
                self.widget.show_error_msg(str(e))
                return
            self.widget.pattern_filename_txt.setText(os.path.basename(filename))
            self.widget.pattern_directory_txt.setText(os.path.dirname(filename))
            self.widget.pattern_next_btn.setEnabled(True)
            self.widget.pattern_previous_btn.setEnabled(True)

    def load_previous(self):
        step = int(str(self.widget.pattern_browse_step_txt.text()))
        self.model.pattern_model.load_previous_file(step=step)
        self.widget.pattern_filename_txt.setText(
            os.path.basename(self.model.pattern.filename)
        )

    def load_next(self):
        step = int(str(self.widget.pattern_browse_step_txt.text()))
        self.model.pattern_model.load_next_file(step=step)
        self.widget.pattern_filename_txt.setText(
            os.path.basename(self.model.pattern.filename)
        )

    def filename_txt_changed(self):
        current_filename = os.path.basename(self.model.pattern.filename)
        current_directory = str(self.widget.pattern_directory_txt.text())
        new_filename = str(self.widget.pattern_filename_txt.text())
        if os.path.isfile(os.path.join(current_directory, new_filename)):
            try:
                self.load(filename=os.path.join(current_directory, new_filename))
            except TypeError:
                self.widget.pattern_filename_txt.setText(current_filename)
        else:
            self.widget.pattern_filename_txt.setText(current_filename)

    def pattern_directory_btn_click(self):
        directory = QtWidgets.QFileDialog.getExistingDirectory(
            self.widget,
            "Please choose the default directory for autosaved .",
            self.model.working_directories["pattern"],
        )
        if directory != "":
            self.model.working_directories["pattern"] = str(directory)
            self.widget.pattern_directory_txt.setText(directory)

    def pattern_directory_txt_changed(self):
        if os.path.exists(self.widget.pattern_directory_txt.text()):
            self.model.working_directories["pattern"] = str(
                self.widget.pattern_directory_txt.text()
            )
        else:
            self.widget.pattern_directory_txt.setText(
                self.model.working_directories["pattern"]
            )

    def set_iteration_mode_number(self):
        self.model.pattern_model.set_file_iteration_mode("number")

    def set_iteration_mode_time(self):
        self.model.pattern_model.set_file_iteration_mode("time")

    # (axis label, unit suffix, inverted x-axis) per integration unit
    _UNIT_DISPLAY = {
        "2th_deg": ("2θ", "°", False),
        "q_A^-1": ("Q", "Å⁻¹", False),
        "d_A": ("d", "Å", True),
    }

    def set_unit_tth(self):
        self.set_unit("2th_deg")

    def set_unit_q(self):
        self.set_unit("q_A^-1")

    def set_unit_d(self):
        self.set_unit("d_A")

    def set_unit(self, unit):
        """The single write path for the integration unit; display updates
        happen in reaction to the model's integration_unit_changed signal."""
        self.model.current_configuration.integration_unit = unit

    def _integration_unit_changed(self, new_unit, previous_unit):
        self._apply_unit_change(previous_unit, new_unit)

    def _displayed_unit(self):
        """The unit the pattern plot currently displays, from the button
        states (the widgets are the display, not the source of truth)."""
        if self.widget.pattern_q_btn.isChecked():
            return "q_A^-1"
        if self.widget.pattern_d_btn.isChecked():
            return "d_A"
        return "2th_deg"

    def _apply_unit_change(self, previous_unit, new_unit):
        self._render_unit(new_unit)
        if previous_unit == new_unit:
            return
        if self.model.calibration_model.is_calibrated:
            self.update_x_range(previous_unit, new_unit)
            self.update_line_position(previous_unit, new_unit)

    def _render_unit(self, unit):
        label, unit_suffix, inverted = self._UNIT_DISPLAY[unit]
        button = {
            "2th_deg": self.widget.pattern_tth_btn,
            "q_A^-1": self.widget.pattern_q_btn,
            "d_A": self.widget.pattern_d_btn,
        }[unit]
        button.setChecked(True)
        self.widget.pattern_widget.pattern_plot.setLabel(
            "bottom", label, unit_suffix
        )
        self.widget.pattern_widget.pattern_plot.invertX(inverted)

    def update_x_range(self, previous_unit, new_unit):
        old_x_axis_range = self.widget.pattern_widget.pattern_plot.viewRange()[0]
        pattern_x = self.model.pattern.data[0]
        if len(pattern_x) < 1:
            return
        if (
            np.min(pattern_x) < old_x_axis_range[0]
            or np.max(pattern_x) > old_x_axis_range[1]
        ):
            new_x_axis_range = self.convert_x_value(
                np.array(old_x_axis_range), previous_unit, new_unit
            )
            if new_x_axis_range[0] is None or np.isnan(new_x_axis_range[0]):
                return
            self.widget.pattern_widget.pattern_plot.setRange(
                xRange=new_x_axis_range, padding=0
            )

    def pattern_auto_range_btn_click_callback(self):
        self.widget.integration_pattern_widget.pattern_view.auto_range = (
            self.widget.pattern_auto_range_btn.isChecked()
        )

    def update_line_position(self, previous_unit, new_unit):
        cur_line_pos = self.widget.pattern_widget.pos_line.getPos()[0]
        if cur_line_pos == 0 and new_unit == "d_A":
            cur_line_pos = 0.01
        try:
            new_line_pos = self.convert_x_value(cur_line_pos, previous_unit, new_unit)
        except RuntimeWarning:  # no calibration available
            new_line_pos = cur_line_pos
        self.widget.pattern_widget.set_pos_line(new_line_pos)

    def convert_x_value(self, value, previous_unit, new_unit):
        wavelength = self.model.calibration_model.wavelength
        return convert_units(value, wavelength, previous_unit, new_unit)

    def pattern_left_click(self, x, y):
        tth_clicked = self.convert_x_value(
            x, self.model.current_configuration.integration_unit, "2th_deg"
        )
        self.model.clicked_tth_changed.emit(tth_clicked)

        self.widget.click_tth_lbl.setText(self.widget.mouse_tth_lbl.text())
        self.widget.click_d_lbl.setText(self.widget.mouse_d_lbl.text())
        self.widget.click_q_lbl.setText(self.widget.mouse_q_lbl.text())
        self.widget.click_azi_lbl.setText(self.widget.mouse_azi_lbl.text())

        self.model.map_model.theta_center = tth_clicked
        try:
            self.model.map_model.wavelength = self.model.calibration_model.wavelength
        except RuntimeWarning:
            self.model.map_model.wavelength = 3.344e-11

    def set_line_position(self, tth):
        x = self.convert_x_value(
            tth, "2th_deg", self.model.current_configuration.integration_unit
        )
        self.widget.pattern_widget.set_pos_line(x)

    def show_pattern_mouse_position(self, x, _):
        tth_str, d_str, q_str, azi_str = self.get_position_strings(x)
        self.widget.mouse_tth_lbl.setText(tth_str)
        self.widget.mouse_d_lbl.setText(d_str)
        self.widget.mouse_q_lbl.setText(q_str)
        self.widget.mouse_azi_lbl.setText(azi_str)

    def get_position_strings(self, x):
        if self.model.calibration_model.is_calibrated:
            if self.model.current_configuration.integration_unit == "2th_deg":
                tth = x
                q_value = self.convert_x_value(tth, "2th_deg", "q_A^-1")
                d_value = self.convert_x_value(tth, "2th_deg", "d_A")
            elif self.model.current_configuration.integration_unit == "q_A^-1":
                q_value = x
                tth = self.convert_x_value(q_value, "q_A^-1", "2th_deg")
                d_value = self.convert_x_value(q_value, "q_A^-1", "d_A")
            elif self.model.current_configuration.integration_unit == "d_A":
                d_value = x
                q_value = self.convert_x_value(d_value, "d_A", "q_A^-1")
                tth = self.convert_x_value(d_value, "d_A", "2th_deg")

            tth_str = "2θ:%9.3f  " % tth
            d_str = "d:%9.3f  " % d_value
            q_str = "Q:%9.3f  " % q_value
        else:
            tth_str = "2θ: -"
            d_str = "d: -"
            q_str = "Q: -"
            if self.model.current_configuration.integration_unit == "2th_deg":
                tth_str = "2θ:%9.3f  " % x
            elif self.model.current_configuration.integration_unit == "q_A^-1":
                q_str = "Q:%9.3f  " % x
            elif self.model.current_configuration.integration_unit == "d_A":
                d_str = "d:%9.3f  " % x
        azi_str = "X: -"
        return tth_str, d_str, q_str, azi_str

    def key_press_event(self, ev):
        if (ev.key() == QtCore.Qt.Key_Left) or (ev.key() == QtCore.Qt.Key_Right):
            if not (ev.modifiers() & QtCore.Qt.AltModifier):
                ev.ignore()
                return
            pos = self.widget.pattern_widget.get_pos_line()
            step = np.min(np.diff(self.model.pattern.data[0]))
            if ev.modifiers() & QtCore.Qt.ControlModifier:
                step /= 20.0
            elif ev.modifiers() & QtCore.Qt.ShiftModifier:
                step *= 10
            if self.model.current_configuration.integration_unit == "d_A":
                step *= -1
            if ev.key() == QtCore.Qt.Key_Left:
                new_pos = pos - step
            elif ev.key() == QtCore.Qt.Key_Right:
                new_pos = pos + step
            self.model.clicked_tth_changed.emit(new_pos)

    def _y_scale_log_clicked(self):
        if self.widget.pattern_log_btn.isChecked():
            self.widget.pattern_sqrt_btn.setChecked(False)
            self.widget.pattern_widget.set_y_scale("log")
        else:
            self.widget.pattern_widget.set_y_scale("linear")

    def _y_scale_sqrt_clicked(self):
        if self.widget.pattern_sqrt_btn.isChecked():
            self.widget.pattern_log_btn.setChecked(False)
            self.widget.pattern_widget.set_y_scale("sqrt")
        else:
            self.widget.pattern_widget.set_y_scale("linear")

    def update_gui(self):
        self._apply_unit_change(
            self._displayed_unit(),
            self.model.current_configuration.integration_unit,
        )
        formats = self.model.current_configuration.integrated_patterns_file_formats
        for checkbox, suffix in (
            (self.widget.pattern_header_xy_cb, ".xy"),
            (self.widget.pattern_header_xye_cb, ".xye"),
            (self.widget.pattern_header_chi_cb, ".chi"),
            (self.widget.pattern_header_dat_cb, ".dat"),
            (self.widget.pattern_header_fxye_cb, ".fxye"),
        ):
            checkbox.blockSignals(True)
            checkbox.setChecked(suffix in formats)
            checkbox.blockSignals(False)
