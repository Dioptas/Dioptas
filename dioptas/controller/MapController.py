# SPDX-License-Identifier: MIT
from typing import Optional

import numpy as np

from dioptas.model.DioptasModel import DioptasModel
from dioptas.model.util.calc import convert_units
from dioptas.widgets.MapWidget import MapWidget

from .MapPanelController import MapPanelController
from .integration.MapRoiInPatternController import MapRoiInPatternController
from .integration.phase.PhaseInPatternController import PhaseInPatternController
from .integration.overlay.OverlayInPatternController import OverlayInPatternController


class MapController:
    def __init__(
        self,
        widget: MapWidget,
        dioptas_model: DioptasModel,
        panel_controller: Optional[MapPanelController] = None,
    ):
        self.widget = widget
        self.model = dioptas_model

        # The map panel is shared with the integration view, so its controller
        # is normally owned by the MainController and passed in here.
        if panel_controller is None:
            panel_controller = MapPanelController(
                self.widget.map_panel_widget, self.model
            )
        self.panel_controller = panel_controller

        self._setting_levels = False
        self._active = False

        self.phase_in_pattern_controller = PhaseInPatternController(
            self.widget.pattern_plot_widget, self.model
        )
        self.overlay_in_pattern_controller = OverlayInPatternController(
            self.widget.pattern_plot_widget, self.model.overlay_model
        )
        # this plot exists to drive the map, so its window region is always up
        self.map_roi_controller = MapRoiInPatternController(
            self.widget.pattern_plot_widget, self.model, always_visible=True
        )

        self.create_signals()

    def create_signals(self):
        self.widget.control_widget.load_btn.clicked.connect(self.load_btn_clicked)
        self.widget.control_widget.file_list.currentRowChanged.connect(
            self.file_list_row_changed
            # needs to be its own function, to always recall the model.map_model
            # this ensures, that the currently selected configuration is used
        )
        self.widget.control_widget.reintegrate_cb.toggled.connect(
            self._auto_integrate_toggled
        )

        self.widget.pattern_footer_widget.log_btn.clicked.connect(
            self._y_scale_log_clicked
        )
        self.widget.pattern_footer_widget.sqrt_btn.clicked.connect(
            self._y_scale_sqrt_clicked
        )

        self.widget.pattern_plot_widget.mouse_left_clicked.connect(self.pattern_clicked)
        self.widget.pattern_plot_widget.mouse_moved.connect(
            self.pattern_plot_mouse_moved
        )

        self.widget.img_plot_widget.mouse_left_clicked.connect(
            self.img_plot_left_clicked
        )
        self.widget.img_plot_widget.mouse_moved.connect(self.img_plot_mouse_moved)
        self.widget.img_autoscale_btn.clicked.connect(
            self._img_autoscale_btn_clicked
        )
        self.widget.img_plot_widget.img_histogram_LUT_horizontal.sigLevelChangeFinished.connect(
            self._img_levels_manually_changed
        )

        self.panel_controller.point_selected.connect(self.map_point_selected)

        self._connected_map_model = self.model.map_model
        self._connected_map_model.map_changed.connect(self.update_file_list)
        self.model.clicked_tth_changed.connect(self.update_pattern_green_line)
        self.model.clicked_tth_changed.connect(self.update_image_green_line)
        self.model.clicked_tth_changed.connect(self.update_clicked_pos_label)
        self.model.clicked_azi_changed.connect(self.update_clicked_azi_label)

        self.model.pattern_changed.connect(self.update_pattern)
        self.activate_model_signals()

    def activate(self):
        self._active = True
        self.activate_model_signals()
        self._apply_auto_integrate()
        self.configuration_selected()
        self._sync_file_list_selection()

    def activate_model_signals(self):
        self.model.img_changed.connect(self.update_image)
        self.model.configuration_selected.connect(self.configuration_selected)

    def deactivate(self):
        self._active = False
        self.model.img_changed.disconnect(self.update_image)
        self.model.configuration_selected.disconnect(self.configuration_selected)
        self.model.current_configuration.auto_integrate_pattern = True

    def _auto_integrate_toggled(self, checked):
        self.model.current_configuration.auto_integrate_pattern = checked
        if checked:
            self.model.current_configuration.integrate_image_1d()
        else:
            ind = self.widget.control_widget.file_list.currentRow()
            if ind >= 0:
                self._set_stored_pattern(ind)

    def _img_autoscale_btn_clicked(self):
        if self.widget.img_autoscale_btn.isChecked():
            self._setting_levels = True
            self.widget.img_plot_widget.auto_level()
            self._setting_levels = False

    def _img_levels_manually_changed(self, *args):
        if not self._setting_levels:
            self.widget.img_autoscale_btn.setChecked(False)

    def _apply_auto_integrate(self):
        checked = self.widget.control_widget.reintegrate_cb.isChecked()
        self.model.current_configuration.auto_integrate_pattern = checked

    def _set_stored_pattern(self, index):
        """Set pattern from stored map data when reintegrate is off.

        Only applies while the map mode itself is shown: a point picked from
        the integration view has to go through the normal integration
        pipeline, or the pattern there would ignore the mask, background and
        unit currently set in that view.
        """
        if not self._active:
            return
        if self.widget.control_widget.reintegrate_cb.isChecked():
            return
        map_model = self.model.map_model
        if map_model.pattern_x is None or map_model.pattern_intensities is None:
            return
        x = map_model.pattern_x
        y = map_model.pattern_intensities[index]
        filename = self.model.img_model.filename
        self.model.current_configuration.pattern_model.set_pattern(
            x, y, filename, unit=self.model.integration_unit
        )

    def load_btn_clicked(self):
        self.panel_controller.load_map()

    def save_map(self, filename: str):
        self.panel_controller.save_map(filename)

    def update_file_list(self):
        # get current items
        items = [
            self.widget.control_widget.file_list.item(i).text()
            for i in range(self.widget.control_widget.file_list.count())
        ]
        if items == self.model.map_model.get_filenames():
            return

        self.widget.control_widget.file_list.blockSignals(True)
        self.widget.control_widget.file_list.clear()
        filenames = self.model.map_model.get_filenames()
        if len(filenames) == 0:  # no files loaded
            return
        self.widget.control_widget.file_list.addItems(filenames)
        self.widget.control_widget.file_list.blockSignals(False)

    def update_image(self):
        if self.model.img_model.img_data is None:
            self.widget.img_plot_widget.plot_image(np.array([[], []]))
        else:
            auto_level = self.widget.img_autoscale_btn.isChecked()
            self._setting_levels = True
            self.widget.img_plot_widget.plot_image(
                self.model.img_model.img_data, auto_level=auto_level
            )
            self._setting_levels = False
            self.plot_mask()

    def plot_mask(self):
        if self.model.current_configuration.use_mask:
            self.widget.img_plot_widget.activate_mask()
            self.widget.img_plot_widget.plot_mask(self.model.mask_model.get_mask())
        else:
            self.widget.img_plot_widget.deactivate_mask()

    def update_pattern(self):
        self.widget.pattern_plot_widget.plot_data(
            self.model.pattern.x, self.model.pattern.y, self.model.pattern.name
        )
        self.update_pattern_green_line(self.model.clicked_tth)

        cur_unit = self.model.integration_unit
        pattern_plot = self.widget.pattern_plot_widget.pattern_plot

        if cur_unit == "2th_deg":
            pattern_plot.setLabel("bottom", "2θ", "°")
            pattern_plot.invertX(False)
        elif cur_unit == "q_A^-1":
            pattern_plot.setLabel("bottom", "Q", "Å⁻¹")
            pattern_plot.invertX(False)
        elif cur_unit == "d_A":
            pattern_plot.setLabel("bottom", "d", "Å")
            pattern_plot.invertX(True)

    def update_pattern_green_line(self, pos):
        if self.model.integration_unit == "2th_deg":
            self.widget.pattern_plot_widget.set_pos_line(pos)
        else:
            wavelength = self.model.calibration_model.wavelength
            new_pos = convert_units(
                pos, wavelength, "2th_deg", self.model.integration_unit
            )
            self.widget.pattern_plot_widget.set_pos_line(new_pos)

    def update_image_green_line(self, pos):
        if not self.model.current_configuration.is_calibrated:
            return

        self.widget.img_plot_widget.set_circle_line(
            self.model.calibration_model.tth_array, np.deg2rad(pos)
        )

    def file_list_row_changed(self, row):
        self.model.map_model.select_point_by_index(row)
        self._set_stored_pattern(row)

    def map_point_selected(self, index):
        """Follows a selection made in the map plot with the file list.

        Stays connected while other modes are shown so the list is up to date
        when the map mode comes back.
        """
        self._set_stored_pattern(index)
        self._set_file_list_row(index)

    def _set_file_list_row(self, index):
        self.widget.control_widget.file_list.blockSignals(True)
        self.widget.control_widget.file_list.setCurrentRow(index)
        self.widget.control_widget.file_list.blockSignals(False)

    def _sync_file_list_selection(self):
        """Points the file list at the currently loaded image.

        Images can also be loaded while the map mode is hidden, e.g. by
        stepping through files in the integration view. An image that is not
        part of the map clears the selection, matching the map marker which
        hides in that case.
        """
        img_model = self.model.img_model
        index = self.model.map_model.get_index_of_file(
            img_model.filename, img_model.series_pos - 1
        )
        self._set_file_list_row(index if index is not None else -1)

    def img_plot_left_clicked(self, x, y):
        if not self.model.current_configuration.is_calibrated:
            return

        calibration_model = self.model.calibration_model
        img_shape = self.model.img_model.img_data.shape

        x, y = np.array([y]), np.array([x])
        if 0.5 < x < img_shape[0] - 0.5 and 0.5 < y < img_shape[1] - 0.5:
            tth = calibration_model.get_two_theta_img(x, y)
            azi = calibration_model.get_azi_img(x, y)

            self.model.clicked_tth_changed.emit(np.rad2deg(tth))
            self.model.clicked_azi_changed.emit(np.rad2deg(azi))

    def img_plot_mouse_moved(self, x, y):
        image_x = self.widget.map_plot_control_widget.mouse_x_label
        image_y = self.widget.map_plot_control_widget.mouse_y_label
        image_int = self.widget.map_plot_control_widget.mouse_int_label

        if self.model.img_model.img_data is None:
            image_x.setText(f"X: ")
            image_y.setText(f"Y: ")
            image_int.setText(f"I: ")
            return

        img_shape = self.model.img_model.img_data.shape
        if 0 <= x < img_shape[1] and 0 <= y < img_shape[0]:
            image_x.setText(f"X: {x:.0f}")
            image_y.setText(f"Y: {y:.0f}")
            image_int.setText(f"I: {self.model.img_model.img_data[int(y), int(x)]:.0f}")
        else:
            image_x.setText(f"X: ")
            image_y.setText(f"Y: ")
            image_int.setText(f"I: ")

        if not self.model.current_configuration.is_calibrated:
            return

        x, y = y, x  # swap x and y for the calibration model
        img_tth = self.model.calibration_model.get_two_theta_img(x, y)
        img_tth = np.rad2deg(img_tth)
        img_azi = self.model.calibration_model.get_azi_img(x, y)
        img_azi = np.rad2deg(img_azi)

        tth_str, d_str, q_str, _ = self.get_position_strings(img_tth, "2th_deg")
        pos_widget = self.widget.pattern_footer_widget.mouse_unit_widget.cur_unit_widget
        pos_widget.tth_lbl.setText(tth_str)
        pos_widget.d_lbl.setText(d_str)
        pos_widget.q_lbl.setText(q_str)
        pos_widget.azi_lbl.setText(f"X: {img_azi:.3f}")

    def get_position_strings(
        self, x: float, current_unit: Optional[str] = None
    ) -> tuple[str, str, str, str]:
        if current_unit is None:
            current_unit = self.model.integration_unit
        if self.model.calibration_model.is_calibrated:
            wavelength = self.model.calibration_model.wavelength
            if current_unit == "2th_deg":
                tth = x
                q_value = convert_units(tth, wavelength, "2th_deg", "q_A^-1")
                d_value = convert_units(tth, wavelength, "2th_deg", "d_A")
            elif current_unit == "q_A^-1":
                q_value = x
                tth = convert_units(q_value, wavelength, "q_A^-1", "2th_deg")
                d_value = convert_units(q_value, wavelength, "q_A^-1", "d_A")
            elif current_unit == "d_A":
                d_value = x
                q_value = convert_units(d_value, wavelength, "d_A", "q_A^-1")
                tth = convert_units(d_value, wavelength, "d_A", "2th_deg")
            else:
                tth = 0
                d_value = 0
                q_value = 0

            tth_str = "2θ:%9.3f" % tth
            d_str = "d:%9.3f" % d_value
            q_str = "Q:%9.3f" % q_value
        else:
            tth_str = "2θ: -"
            d_str = "d: -"
            q_str = "Q: -"
            if current_unit == "2th_deg":
                tth_str = "2θ:%9.3f" % x
            elif current_unit == "q_A^-1":
                q_str = "Q:%9.3f" % x
            elif current_unit == "d_A":
                d_str = "d:%9.3f" % x
        azi_str = "X: -"
        return tth_str, d_str, q_str, azi_str

    def pattern_plot_mouse_moved(self, x, _):
        tth_str, d_str, q_str, azi_str = self.get_position_strings(x)
        pos_widget = self.widget.pattern_footer_widget.mouse_unit_widget.cur_unit_widget
        pos_widget.tth_lbl.setText(tth_str)
        pos_widget.d_lbl.setText(d_str)
        pos_widget.q_lbl.setText(q_str)
        pos_widget.azi_lbl.setText(azi_str)

    def update_clicked_pos_label(self, pos):
        tth_str, d_str, q_str, azi_str = self.get_position_strings(pos)
        pos_widget = (
            self.widget.pattern_footer_widget.mouse_unit_widget.clicked_unit_widget
        )
        pos_widget.tth_lbl.setText(tth_str)
        pos_widget.d_lbl.setText(d_str)
        pos_widget.q_lbl.setText(q_str)
        pos_widget.azi_lbl.setText(azi_str)

    def update_clicked_azi_label(self, azi):
        pos_widget = (
            self.widget.pattern_footer_widget.mouse_unit_widget.clicked_unit_widget
        )
        pos_widget.azi_lbl.setText(f"X: {azi:.3f}")

    def pattern_clicked(self, x, _):
        self.map_roi_controller.set_center(x)

    def _y_scale_log_clicked(self):
        if self.widget.pattern_footer_widget.log_btn.isChecked():
            self.widget.pattern_footer_widget.sqrt_btn.setChecked(False)
            self.widget.pattern_plot_widget.set_y_scale("log")
        else:
            self.widget.pattern_plot_widget.set_y_scale("linear")

    def _y_scale_sqrt_clicked(self):
        if self.widget.pattern_footer_widget.sqrt_btn.isChecked():
            self.widget.pattern_footer_widget.log_btn.setChecked(False)
            self.widget.pattern_plot_widget.set_y_scale("sqrt")
        else:
            self.widget.pattern_plot_widget.set_y_scale("linear")

    def configuration_selected(self):
        self._update_map_model_connection()
        self.update_file_list()
        self.update_image()
        self.update_pattern()

    def _update_map_model_connection(self):
        """Rebinds map_changed to the current configuration's map model.

        The map model is configuration-scoped, so the subscription made at
        construction time goes stale when the configuration changes (switch,
        add/remove, project load)."""
        if self.model.map_model is self._connected_map_model:
            return
        self._connected_map_model.map_changed.disconnect(self.update_file_list)
        self._connected_map_model = self.model.map_model
        self._connected_map_model.map_changed.connect(self.update_file_list)
