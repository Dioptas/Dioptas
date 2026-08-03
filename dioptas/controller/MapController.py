# SPDX-License-Identifier: MIT
from typing import Optional

import numpy as np
from qtpy import QtGui, QtWidgets

from dioptas.model import map_expression
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
        self.widget.control_widget.file_list.model().rowsMoved.connect(
            self._file_list_rows_moved
        )
        self.widget.control_widget.file_list.customContextMenuRequested.connect(
            self._file_list_context_menu
        )
        self.widget.control_widget.file_list.currentRowChanged.connect(
            lambda _row: self.update_point_actions()
        )
        control = self.widget.control_widget
        control.move_up_btn.clicked.connect(lambda: self.move_selected_cell(-1))
        control.move_down_btn.clicked.connect(lambda: self.move_selected_cell(1))
        control.insert_blank_btn.clicked.connect(self.insert_blank)
        control.remove_blank_btn.clicked.connect(self.remove_blank)
        control.exclude_btn.clicked.connect(self.toggle_point_excluded)
        self.widget.control_widget.reintegrate_cb.toggled.connect(
            self._auto_integrate_toggled
        )

        layer_widget = self.widget.control_widget.layer_widget
        layer_widget.sigRoiChanged.connect(self._roi_changed)
        layer_widget.sigAddRoiRequested.connect(self._add_roi)
        layer_widget.sigRemoveRoiRequested.connect(self._remove_roi)
        layer_widget.sigExpressionChanged.connect(self._expression_changed)
        layer_widget.sigAddExpressionRequested.connect(self._add_expression)
        layer_widget.sigRemoveExpressionRequested.connect(self._remove_expression)
        layer_widget.sigLayerSelected.connect(self._layer_selected)

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
        # a blank cell has no point, but its row in the list is where the
        # insert/remove/move actions live; translated, because the map
        # closes up over excluded points while the list keeps them
        self.panel_controller.blank_selected.connect(self._blank_cell_selected)

        self._connected_map_model = self.model.map_model
        self._connected_map_model.map_changed.connect(self._map_changed)
        # removing a configuration switches to another one without emitting
        # configuration_selected, and this stays connected while the map mode
        # is hidden so its file list is right when it comes back
        self.model.configuration_removed.connect(self._configuration_removed)
        self.model.clicked_tth_changed.connect(self.update_pattern_green_line)
        self.model.clicked_tth_changed.connect(self.update_image_green_line)
        self.model.clicked_tth_changed.connect(self.update_clicked_pos_label)
        self.model.clicked_azi_changed.connect(self.update_clicked_azi_label)

        self.model.pattern_changed.connect(self.update_pattern)
        # the overlay column offers what currently exists; the map values
        # themselves are recomputed by the model when overlays change
        self.model.overlay_model.overlay_added.connect(
            lambda *args: self.update_layer_widget()
        )
        self.model.overlay_model.overlay_removed.connect(
            lambda *args: self.update_layer_widget()
        )
        self.model.overlay_model.overlay_changed.connect(
            lambda *args: self.update_layer_widget()
        )
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
            # the list rows are grid cells, so the point behind the selected
            # one has to be looked up rather than assumed to be its index
            slot = self.widget.control_widget.file_list.currentRow()
            self._set_stored_pattern(self.model.map_model.get_point_of_slot(slot))

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
        # None indexes a numpy array as "add an axis" rather than failing, so
        # a blank cell would quietly produce a nonsense pattern
        if index is None or not 0 <= index < len(map_model.pattern_intensities):
            return
        x = self._pattern_x_in_display_unit(map_model)
        if x is None:
            return
        y = map_model.pattern_intensities[index]
        filename = self.model.img_model.filename
        self.model.current_configuration.pattern_model.set_pattern(
            x, y, filename, unit=self.model.integration_unit
        )

    def _pattern_x_in_display_unit(self, map_model):
        """The stored map x values, in the unit the pattern is displayed in.

        The map keeps them in the unit it was integrated in, which the user
        can have changed since. Converting d spacing leaves the values in
        descending order, as a regular integration in d does.
        """
        unit = self.model.integration_unit
        if map_model.pattern_unit is None or map_model.pattern_unit == unit:
            return map_model.pattern_x
        wavelength = self.model.calibration_model.wavelength
        if not wavelength:
            return None
        return convert_units(
            map_model.pattern_x, wavelength, map_model.pattern_unit, unit
        )

    def load_btn_clicked(self):
        self.panel_controller.load_map()

    def save_map(self, filename: str):
        self.panel_controller.save_map(filename)

    def update_file_list(self):
        """Shows the arrangement in order, blanks included.

        Excluded points stay in their row, struck through — the map closes
        up over them, but the list keeps their place, so leaving one out
        does not shuffle the list.
        """
        map_model = self.model.map_model
        file_list = self.widget.control_widget.file_list
        labels = map_model.get_slot_labels() if map_model.map is not None else []
        current = file_list.currentRow()

        # unblock even when there are no files: leaving the list blocked would
        # swallow the row changes of the next map loaded into it
        file_list.blockSignals(True)
        try:
            file_list.clear()
            slots = map_model.get_slots() if labels else []
            for label, point in zip(labels, slots):
                item = QtWidgets.QListWidgetItem(label)
                if point is None:
                    item.setForeground(QtGui.QColor(128, 128, 128))
                elif map_model.is_point_excluded(point):
                    font = item.font()
                    font.setStrikeOut(True)
                    item.setFont(font)
                    item.setForeground(QtGui.QColor(128, 128, 128))
                file_list.addItem(item)
            if 0 <= current < file_list.count():
                file_list.setCurrentRow(current)
        finally:
            file_list.blockSignals(False)

    def update_layer_widget(self):
        map_model = self.model.map_model
        layer_widget = self.widget.control_widget.layer_widget
        layer_widget.set_rois(map_model.rois)
        layer_widget.set_expressions(map_model.expressions)
        layer_widget.set_active_layer(map_model.active_layer)
        for name, expression in map_model.expressions.items():
            problem = map_expression.validate(
                expression,
                {roi.name for roi in map_model.rois},
                overlay_exists=map_model.overlay_exists,
            )
            if problem is not None:
                layer_widget.set_message(f"{name}: {problem}")
                break

    def _layer_selected(self, name):
        if name in self.model.map_model.layer_names():
            self.model.map_model.active_layer = name

    def _roi_changed(self, name, field, value):
        map_model = self.model.map_model
        layer_widget = self.widget.control_widget.layer_widget
        if field == "name":
            if value and not map_model.rename_roi(name, value):
                layer_widget.set_message(f"'{value}' is not a usable name.")
                self.update_layer_widget()
            else:
                layer_widget.set_message("")
            return
        if field == "value_kind":
            reduction, subtract_background = value
            layer_widget.set_message("")
            map_model.set_roi_value_kind(name, reduction, subtract_background)
            return
        roi = map_model.get_roi(name)
        if roi is None:
            return
        layer_widget.set_message("")
        setattr(roi, field, value)

    def _add_roi(self):
        if self.model.map_model.map is None:
            self.widget.control_widget.layer_widget.set_message(
                "Load a map first."
            )
            return
        # show the new window straight away — otherwise adding one appears to
        # do nothing, the map still being the layer that was already up
        roi = self.model.map_model.add_roi()
        self.model.map_model.active_layer = roi.name
        self.update_layer_widget()

    def _remove_roi(self, name):
        layer_widget = self.widget.control_widget.layer_widget
        if not self.model.map_model.remove_roi(name):
            layer_widget.set_message("The map needs at least one window.")
            return
        layer_widget.set_message("")
        self.update_layer_widget()

    def _expression_changed(self, name, expression):
        map_model = self.model.map_model
        layer_widget = self.widget.control_widget.layer_widget
        if not map_model.set_expression(name, expression):
            layer_widget.set_message(
                f"'{name}' is already a window — pick another name."
            )
            self.update_layer_widget()
            return
        problem = map_expression.validate(
            expression,
            {roi.name for roi in map_model.rois},
            overlay_exists=map_model.overlay_exists,
        )
        if problem is None:
            values = map_model.layer_values(name)
            if values is not None and not np.any(np.isfinite(values)):
                # valid but useless — e.g. A**B of two large sums overflows
                # everywhere. Without a word the map just goes blank.
                problem = (
                    "The expression gives no finite values — it overflows or "
                    "divides by zero at every point."
                )
        layer_widget.set_message("" if problem is None else problem)
        self.update_layer_widget()

    def _add_expression(self):
        map_model = self.model.map_model
        names = [roi.name for roi in map_model.rois]
        if len(names) < 2:
            self.widget.control_widget.layer_widget.set_message(
                "Add a second window first — a computed layer combines them."
            )
            return
        # a ratio of the first two windows is the common case and shows the
        # syntax without the user having to guess it
        suggestion = f"{names[0]}/{names[1]}"
        name = suggestion
        index = 2
        while name in map_model.layer_names():
            name = f"{suggestion} ({index})"
            index += 1
        map_model.set_expression(name, suggestion)
        map_model.active_layer = name
        self.update_layer_widget()

    def _remove_expression(self, name):
        self.model.map_model.remove_expression(name)
        self.update_layer_widget()

    def _file_list_rows_moved(self, _parent, start, end, _dest_parent, dest_row):
        """Applies a drag in the cell list to the map arrangement."""
        if start != end:  # the list only ever moves one row at a time
            return
        # dest_row is the insertion point before the row is taken out
        target = dest_row if dest_row < start else dest_row - 1
        num_slots = self.model.map_model.num_slots
        target = min(target, num_slots - 1)
        self.model.map_model.move_slot(start, target)

    def _file_list_context_menu(self, position):
        """The same actions as the buttons beside the list, where the mouse
        already is."""
        file_list = self.widget.control_widget.file_list
        map_model = self.model.map_model
        if map_model.map is None:
            return
        item = file_list.itemAt(position)
        if item is None:
            return
        slot = file_list.row(item)
        file_list.setCurrentRow(slot)
        point = self._row_point(slot)

        menu = QtWidgets.QMenu(file_list)
        move_up_action = menu.addAction("Move up")
        move_up_action.setEnabled(slot > 0)
        move_down_action = menu.addAction("Move down")
        move_down_action.setEnabled(slot < map_model.num_slots - 1)
        menu.addSeparator()
        insert_action = menu.addAction("Insert blank cell here")
        remove_action = menu.addAction("Remove blank cell")
        remove_action.setEnabled(map_model.can_remove_blank(slot))
        menu.addSeparator()
        if point is not None and map_model.is_point_excluded(point):
            exclude_action = menu.addAction("Include point in map")
        else:
            exclude_action = menu.addAction("Leave point out of map")
        exclude_action.setEnabled(point is not None)

        chosen = menu.exec_(file_list.mapToGlobal(position))
        if chosen is move_up_action:
            self.move_selected_cell(-1)
        elif chosen is move_down_action:
            self.move_selected_cell(1)
        elif chosen is insert_action:
            self.insert_blank()
        elif chosen is remove_action:
            self.remove_blank()
        elif chosen is exclude_action:
            self.toggle_point_excluded()

    # --- point actions, shared by the buttons and the context menu -------

    def _selected_slot(self) -> int:
        return self.widget.control_widget.file_list.currentRow()

    def _row_point(self, row: int):
        """The point behind a list row, excluded ones included."""
        if row < 0:
            return None
        return self.model.map_model.get_point_of_slot(row)

    def _selected_point(self):
        return self._row_point(self._selected_slot())

    def move_selected_cell(self, offset: int):
        """Moves the selected cell one place along the scan order.

        Works on blanks as much as on points — a blank in the wrong place is
        exactly what has to be nudged after a dropped frame is found.
        """
        map_model = self.model.map_model
        slot = self._selected_slot()
        target = slot + offset
        if slot < 0 or not 0 <= target < map_model.num_slots:
            return
        map_model.move_slot(slot, target)
        # the rebuilt list restores the row that was selected, which is the
        # place the cell has just left; the selection follows the cell
        self._select_slot(target)

    def _blank_cell_selected(self, visible_slot: int):
        row = self.model.map_model.get_row_of_visible_slot(visible_slot)
        if row is not None:
            self._select_slot(row)

    def _select_slot(self, slot: int):
        """Selects a list row without re-selecting the point behind it."""
        file_list = self.widget.control_widget.file_list
        file_list.blockSignals(True)
        file_list.setCurrentRow(slot)
        file_list.blockSignals(False)
        self.update_point_actions()

    def insert_blank(self):
        slot = self._selected_slot()
        if slot >= 0:
            self.model.map_model.insert_blank(slot)

    def remove_blank(self):
        slot = self._selected_slot()
        if slot >= 0:
            self.model.map_model.remove_blank(slot)

    def toggle_point_excluded(self):
        point = self._selected_point()
        if point is None:
            return
        map_model = self.model.map_model
        map_model.set_point_excluded(point, not map_model.is_point_excluded(point))

    def update_point_actions(self):
        """Enables only what the selected cell can actually do.

        The buttons double as the explanation of what is possible here, so
        they say which of them apply rather than failing when pressed.
        """
        control = self.widget.control_widget
        map_model = self.model.map_model
        has_map = map_model.map is not None
        slot = self._selected_slot()
        point = self._row_point(slot) if has_map else None
        is_cell = has_map and 0 <= slot < map_model.num_slots
        selected = is_cell

        control.move_up_btn.setEnabled(is_cell and slot > 0)
        control.move_down_btn.setEnabled(
            is_cell and slot < map_model.num_slots - 1
        )
        control.insert_blank_btn.setEnabled(selected)
        control.remove_blank_btn.setEnabled(
            is_cell and map_model.can_remove_blank(slot)
        )
        control.exclude_btn.setEnabled(point is not None)
        control.set_point_excluded(
            point is not None and map_model.is_point_excluded(point)
        )

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
        # rows are grid cells, which is not the point index once blanks are
        # in play, and a blank row selects nothing. Excluded rows below the
        # cells still load their image — a left-out frame can be inspected.
        point = self._row_point(row)
        self.update_point_actions()
        if point is None:
            return
        self.model.map_model.select_point_by_index(point)
        self._set_stored_pattern(point)

    def map_point_selected(self, index):
        """Follows a selection made in the map plot with the file list.

        Stays connected while other modes are shown so the list is up to date
        when the map mode comes back.
        """
        self._set_stored_pattern(index)
        self._set_file_list_row(index)

    def _set_file_list_row(self, index):
        """Selects the cell the given point sits in; -1 clears the selection."""
        if index is not None and index >= 0:
            row = self._row_of_point(index)
            row = -1 if row is None else row
        else:
            row = -1
        self.widget.control_widget.file_list.blockSignals(True)
        self.widget.control_widget.file_list.setCurrentRow(row)
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

    def _row_of_point(self, index):
        """The list row a point sits in; excluded points keep their row."""
        return self.model.map_model.get_slot_of_point(index)

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

    def _map_changed(self):
        self.update_file_list()
        self.update_layer_widget()
        self.update_point_actions()

    def configuration_selected(self):
        self._update_map_model_connection()
        self._map_changed()
        self.update_image()
        self.update_pattern()

    def _configuration_removed(self, _index=None):
        self._update_map_model_connection()
        self._map_changed()
        self._sync_file_list_selection()

    def _update_map_model_connection(self):
        """Rebinds map_changed to the current configuration's map model.

        The map model is configuration-scoped, so the subscription made at
        construction time goes stale when the configuration changes (switch,
        add/remove, project load)."""
        if self.model.map_model is self._connected_map_model:
            return
        self._connected_map_model.map_changed.disconnect(self._map_changed)
        self._connected_map_model = self.model.map_model
        self._connected_map_model.map_changed.connect(self._map_changed)
