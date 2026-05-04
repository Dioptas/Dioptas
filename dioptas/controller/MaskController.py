# SPDX-License-Identifier: MIT

import sys
import os

from qtpy import QtWidgets, QtCore, QtGui
from math import sqrt
import numpy as np

from ..widgets.UtilityWidgets import open_file_dialog, save_file_dialog
from ..widgets.MaskPluginWidget import MaskPluginSettingsDialog

# imports for type hinting in PyCharm -- DO NOT DELETE
from ..widgets.MaskWidget import MaskWidget
from ..model.DioptasModel import DioptasModel


class MaskController:
    DEFAULT_MASK_FILTER = 'Mask (*.mask)'
    FLIPUD_MASK_FILTER_PREFIX = 'Vertically flipped mask'

    def __init__(self, widget, dioptas_model):
        """
        :param widget: Reference to a MaskView object
        :type widget: MaskWidget
        :param dioptas_model: Reference to an DioptasModel object
        :type dioptas_model: DioptasModel
        """
        self.widget = widget
        self.model = dioptas_model

        self.state = None
        self.clicks = 0
        self.create_signals()
        self._setup_plugins()

        self.rect = None
        self.circle = None
        self.polygon = None
        self.point = None
        self.arc = None

    def create_signals(self):
        self.widget.img_widget.mouse_left_clicked.connect(self.process_click)
        self.widget.circle_btn.clicked.connect(self.activate_circle_btn)
        self.widget.rectangle_btn.clicked.connect(self.activate_rectangle_btn)
        self.widget.polygon_btn.clicked.connect(self.activate_polygon_btn)
        self.widget.arc_btn.clicked.connect(self.activate_arc_btn)
        self.widget.point_btn.clicked.connect(self.activate_point_btn)
        self.widget.undo_btn.clicked.connect(self.undo_btn_click)
        self.widget.redo_btn.clicked.connect(self.redo_btn_click)
        self.widget.below_thresh_btn.clicked.connect(self.below_thresh_btn_click)
        self.widget.above_thresh_btn.clicked.connect(self.above_thresh_btn_click)
        self.widget.cosmic_btn.clicked.connect(self.cosmic_btn_click)
        self.widget.grow_btn.clicked.connect(self.grow_btn_click)
        self.widget.shrink_btn.clicked.connect(self.shrink_btn_click)
        self.widget.invert_mask_btn.clicked.connect(self.invert_mask_btn_click)
        self.widget.clear_mask_btn.clicked.connect(self.clear_mask_btn_click)
        self.widget.save_mask_btn.clicked.connect(self.save_mask_btn_click)
        self.widget.load_mask_btn.clicked.connect(self.load_mask_btn_click)
        self.widget.add_mask_btn.clicked.connect(self.add_mask_btn_click)
        self.widget.mask_rb.clicked.connect(self.mask_rb_click)
        self.widget.unmask_rb.clicked.connect(self.unmask_rb_click)
        self.widget.fill_rb.clicked.connect(self.fill_rb_click)
        self.widget.transparent_rb.clicked.connect(self.transparent_rb_click)

        self.widget.point_size_sb.valueChanged.connect(self.set_point_size)
        self.widget.img_widget.mouse_moved.connect(self.show_img_mouse_position)

        self.widget.keyPressEvent = self.key_press_event

        self.model.img_changed.connect(self.plot_image)
        self.model.mask_changed.connect(self.plot_mask)
        self.model.configuration_selected.connect(self.update_gui)

    def _setup_plugins(self):
        """Populate plugin widget and connect signals."""
        manager = self.model.mask_plugin_manager
        if not manager.plugin_names:
            return

        self.widget._plugin_header.show()
        self.widget.plugin_widget.show()
        self.widget._plugin_separator.show()

        for name in manager.plugin_names:
            plugin = manager.get_plugin(name)
            checkbox, settings_btn, imprint_btn = self.widget.plugin_widget.add_plugin_row(
                name, plugin.has_settings
            )
            checkbox.toggled.connect(
                lambda checked, n=name: self._on_plugin_toggled(n, checked)
            )
            if settings_btn is not None:
                settings_btn.clicked.connect(
                    lambda _, n=name: self._on_plugin_settings(n)
                )
            imprint_btn.clicked.connect(
                lambda _, n=name: self._on_plugin_imprint(n)
            )

        manager.mask_changed.connect(self.plot_mask)

    def _on_plugin_toggled(self, name, checked):
        self.model.mask_plugin_manager.set_enabled(name, checked)
        row = self.widget.plugin_widget.get_row(name)
        if row is not None:
            row.imprint_btn.setEnabled(checked)
        self.plot_mask()

    def _on_plugin_imprint(self, name):
        """Bake the current plugin mask into the user-drawn mask, then disable it."""
        self.model.mask_model.imprint_plugin_mask(name)
        # Sync GUI with the now-disabled plugin
        row = self.widget.plugin_widget.get_row(name)
        if row is not None:
            row.checkbox.blockSignals(True)
            row.checkbox.setChecked(False)
            row.checkbox.blockSignals(False)
            row.imprint_btn.setEnabled(False)
        self.plot_mask()

    def _on_plugin_settings(self, name):
        plugin = self.model.mask_plugin_manager.get_plugin(name)
        if plugin is None:
            return
        schema = plugin.get_settings_schema()
        if schema is None:
            return

        manager = self.model.mask_plugin_manager
        old_settings = plugin.get_settings().copy()

        info_text = self._get_plugin_info_text(name)
        dialog = MaskPluginSettingsDialog(
            name,
            schema,
            plugin.get_settings(),
            plugin_description=plugin.description,
            info_text=info_text,
            parent=self.widget,
        )
        dialog.settings_changed.connect(
            lambda settings, n=name: self._apply_plugin_settings(n, settings)
        )
        result = dialog.exec()

        if result != dialog.DialogCode.Accepted:
            # Restore old settings on cancel
            self._apply_plugin_settings(name, old_settings)

    def _apply_plugin_settings(self, name, settings):
        self.model.mask_plugin_manager.update_plugin_settings(name, settings)
        self.plot_mask()

    def _get_plugin_info_text(self, name):
        entry = self.model.mask_plugin_manager.plugins.get(name)
        if entry is None or entry.cached_mask is None:
            return ""
        n_masked = int(entry.cached_mask.sum())
        n_total = entry.cached_mask.size
        pct = 100.0 * n_masked / n_total if n_total > 0 else 0
        return f"Masked pixels: {n_masked:,} ({pct:.2f}%)"

    def activate(self):
        if not self.model.img_changed.has_listener(self.plot_image):
            self.model.img_changed.connect(self.plot_image)
        if not self.model.mask_changed.has_listener(self.plot_mask):
            self.model.mask_changed.connect(self.plot_mask)
        if not self.model.configuration_selected.has_listener(self.update_gui):
            self.model.configuration_selected.connect(self.update_gui)
        self.update_gui()

    def deactivate(self):
        if self.model.img_changed.has_listener(self.plot_image):
            self.model.img_changed.disconnect(self.plot_image)
        if self.model.mask_changed.has_listener(self.plot_mask):
            self.model.mask_changed.disconnect(self.plot_mask)
        if self.model.configuration_selected.has_listener(self.update_gui):
            self.model.configuration_selected.disconnect(self.update_gui)

    def uncheck_all_btn(self, except_btn=None):
        buttons = [self.widget.circle_btn, self.widget.rectangle_btn, self.widget.polygon_btn,
                   self.widget.point_btn, self.widget.arc_btn]
        for btn in buttons:
            if btn is not except_btn:
                if btn.isChecked():
                    btn.toggle()

        shapes = [self.rect, self.circle, self.polygon]
        for shape in shapes:
            if shape is not None:
                if shape.scene() == self.widget.img_widget.img_view_box.scene():
                    self.widget.img_widget.img_view_box.removeItem(shape)
                self.widget.img_widget.mouse_moved.disconnect(shape.set_size)
        self.rect = None
        self.circle = None
        self.polygon = None

        try:
            self.widget.img_widget.mouse_moved.disconnect(self.point.set_position)
            if self.point.scene() == self.widget.img_widget.img_view_box.scene():
                self.widget.img_widget.img_view_box.removeItem(self.point)
            self.point = None
        except AttributeError:
            pass

        if self.arc is not None:
            if self.clicks == 1:
                self.widget.img_widget.mouse_moved.disconnect(self.arc.set_size)
            elif self.clicks == 2:
                self.widget.img_widget.mouse_moved.disconnect(self.arc_calc_and_preview)
            elif self.clicks == 3:
                self.widget.img_widget.mouse_moved.disconnect(self.arc_width_preview)
            if self.arc.scene() == self.widget.img_widget.img_view_box.scene():
                self.widget.img_widget.img_view_box.removeItem(self.arc)
            self.arc = None

    def activate_circle_btn(self):
        if self.widget.circle_btn.isChecked():
            self.state = 'circle'
            self.uncheck_all_btn(except_btn=self.widget.circle_btn)
            self.clicks = 0
        else:
            self.state = None
            self.uncheck_all_btn()
            self.clicks = 0

    def activate_rectangle_btn(self):
        if self.widget.rectangle_btn.isChecked():
            self.state = 'rectangle'
            self.uncheck_all_btn(except_btn=self.widget.rectangle_btn)
            self.clicks = 0
        else:
            self.state = None
            self.uncheck_all_btn()

    def activate_polygon_btn(self):
        if self.widget.polygon_btn.isChecked():
            self.state = 'polygon'
            self.uncheck_all_btn(except_btn=self.widget.polygon_btn)
            self.clicks = 0
        else:
            self.uncheck_all_btn()
            self.state = None

    def activate_arc_btn(self):
        if self.widget.arc_btn.isChecked():
            self.state = 'arc'
            self.uncheck_all_btn(except_btn=self.widget.arc_btn)
            self.clicks = 0
        else:
            self.state = None
            self.uncheck_all_btn()

    def activate_point_btn(self):
        if self.widget.point_btn.isChecked():
            self.state = 'point'
            self.uncheck_all_btn(except_btn=self.widget.point_btn)
            self.clicks = 0
            self.point = self.widget.img_widget.draw_point(self.widget.point_size_sb.value())
            self.widget.img_widget.mouse_moved.connect(self.point.set_position)
        else:
            self.state = 'None'
            self.uncheck_all_btn()

    def undo_btn_click(self):
        self.model.mask_model.undo()
        self._update_plugin_checkboxes()
        self.plot_mask()

    def redo_btn_click(self):
        self.model.mask_model.redo()
        self._update_plugin_checkboxes()
        self.plot_mask()

    def plot_image(self):
        self.widget.img_widget.plot_image(self.model.img_data, False)
        self.widget.img_widget.auto_level()

    def process_click(self, x, y):
        x, y = int(x), int(y)
        if self.state == 'circle':
            self.draw_circle(x, y)
        elif self.state == 'rectangle':
            self.draw_rectangle(x, y)
        elif self.state == 'point':
            self.draw_point(x, y)
        elif self.state == 'polygon':
            self.draw_polygon(x, y)
        elif self.state == 'arc':
            self.draw_arc(x, y)

    def draw_circle(self, x, y):
        if self.clicks == 0:
            self.clicks += 1
            self.circle = self.widget.img_widget.draw_circle(x, y)
            self.widget.img_widget.mouse_moved.connect(self.circle.set_size)
        elif self.clicks == 1:
            self.clicks = 0
            self.model.mask_model.mask_QGraphicsEllipseItem(self.circle)
            if self.circle.scene() == self.widget.img_widget.img_view_box.scene():
                self.widget.img_widget.img_view_box.removeItem(self.circle)
            self.plot_mask()
            self.widget.img_widget.mouse_moved.disconnect(self.circle.set_size)
            self.circle = None

    def draw_rectangle(self, x, y):
        if self.clicks == 0:
            self.clicks += 1
            self.rect = self.widget.img_widget.draw_rectangle(x, y)
            self.widget.img_widget.mouse_moved.connect(self.rect.set_size)
        elif self.clicks == 1:
            self.clicks = 0
            self.model.mask_model.mask_QGraphicsRectItem(self.rect)
            if self.rect.scene() == self.widget.img_widget.img_view_box.scene():
                self.widget.img_widget.img_view_box.removeItem(self.rect)
            self.plot_mask()
            self.widget.img_widget.mouse_moved.disconnect(self.rect.set_size)
            self.rect = None

    def draw_point(self, x, y):
        radius = self.widget.point_size_sb.value()
        if radius <= 0:
            # filter point with no radius
            return
        self.model.mask_model.mask_ellipse(x, y, radius, radius)
        self.plot_mask()

    def set_point_size(self, radius):
        try:
            self.point.set_radius(radius)
        except AttributeError:
            pass

    def draw_polygon(self, x, y):
        if self.clicks == 0:
            self.clicks += 1
            self.polygon = self.widget.img_widget.draw_polygon(x, y)
            self.widget.img_widget.mouse_moved.connect(self.polygon.set_size)
            self.widget.img_widget.mouse_left_double_clicked.connect(self.finish_polygon)
        elif self.clicks == 1:
            self.polygon.set_size(x, y)
            self.polygon.add_point(x, y)

    def draw_arc(self, x, y):
        self.clicks += 1
        if self.clicks == 1:
            self.arc = self.widget.img_widget.draw_arc(x, y)
            self.widget.img_widget.mouse_moved.connect(self.arc.set_size)
        elif self.clicks == 2:
            self.widget.img_widget.mouse_moved.disconnect(self.arc.set_size)
            self.arc.add_point(x, y)
            if self.arc.vertices[0].x() == self.arc.vertices[1].x() and self.arc.vertices[0].y() == self.arc.vertices[
                1].y():
                self.remove_bad_arc()
                return
            self.widget.img_widget.mouse_moved.connect(self.arc_calc_and_preview)
        elif self.clicks == 3:
            self.arc.add_point(x, y)
            self.widget.img_widget.mouse_moved.disconnect(self.arc_calc_and_preview)
            if (self.arc.vertices[0].x() == self.arc.vertices[2].x() and self.arc.vertices[0].y() == self.arc.vertices[
                2].y()) or (self.arc.vertices[1].x() == self.arc.vertices[2].x() and self.arc.vertices[1].y() ==
                            self.arc.vertices[2].y()):
                self.remove_bad_arc()
                return
            arc_center = self.model.mask_model.find_center_of_circle_from_three_points(
                self.arc.vertices[0], self.arc.vertices[1], self.arc.vertices[2]
            )
            if arc_center is None:
                self.remove_bad_arc()
                return
            self.widget.img_widget.mouse_moved.connect(self.arc_width_preview)
        elif self.clicks == 4:
            self.finish_arc()

    def remove_bad_arc(self):
        self.clicks = 0
        if self.arc.scene() == self.widget.img_widget.img_view_box.scene():
            self.widget.img_widget.img_view_box.removeItem(self.arc)
        self.arc = None

    def arc_calc_and_preview(self, x, y):
        v = self.arc.vertices
        new_v = QtCore.QPointF(x, y)
        arc_center = self.model.mask_model.find_center_of_circle_from_three_points(v[0], v[1], new_v)
        if arc_center is None:
            return
        arc_r = self.model.mask_model.find_radius_of_circle_from_center_and_point(arc_center, new_v)
        self.arc.arc_center = arc_center
        self.arc.arc_radius = arc_r
        phi_range = self.model.mask_model.find_n_angles_on_arc_from_three_points_around_p0(arc_center, v[0], v[1], new_v
                                                                                           , 50)
        self.arc.phi_range = phi_range
        arc_points_a = self.model.mask_model.calc_arc_points_from_angles(arc_center, arc_r, 1, phi_range)
        arc_points_b = self.model.mask_model.calc_arc_points_from_angles(arc_center, arc_r, -1, phi_range)
        arc_points = arc_points_a + list(reversed(arc_points_b))

        qt_arc_points = [QtCore.QPointF(p.x(), p.y()) for p in arc_points]
        self.arc.preview_arc(qt_arc_points)

    def arc_width_preview(self, x, y):
        arc_center = self.arc.arc_center
        if arc_center is None:
            return
        arc_r = self.arc.arc_radius
        phi_range = self.arc.phi_range
        width = abs(arc_r - sqrt((x - arc_center.x()) ** 2 + (y - arc_center.y()) ** 2))

        arc_points_a = self.model.mask_model.calc_arc_points_from_angles(arc_center, arc_r, -width, phi_range)
        arc_points_b = self.model.mask_model.calc_arc_points_from_angles(arc_center, arc_r, width, phi_range)
        arc_points = arc_points_a + list(reversed(arc_points_b))
        self.arc.arc_points = arc_points
        qt_arc_points = [QtCore.QPointF(p.x(), p.y()) for p in arc_points]
        self.arc.preview_arc(qt_arc_points)

    def update_shape_preview_fill_color(self):
        try:
            if self.state == 'circle':
                self.circle.setBrush(QtGui.QBrush(self.widget.img_widget.mask_preview_fill_color))
            elif self.state == 'rectangle':
                self.rect.setBrush(QtGui.QBrush(self.widget.img_widget.mask_preview_fill_color))
            elif self.state == 'point':
                self.point.setBrush(QtGui.QBrush(self.widget.img_widget.mask_preview_fill_color))
            elif self.state == 'polygon':
                self.polygon.setBrush(QtGui.QBrush(self.widget.img_widget.mask_preview_fill_color))
            elif self.state == 'arc':
                self.arc.setBrush(QtGui.QBrush(self.widget.img_widget.mask_preview_fill_color))
        except AttributeError:
            return

    def finish_polygon(self, x, y):
        self.widget.img_widget.mouse_moved.disconnect(self.polygon.set_size)
        self.widget.img_widget.mouse_left_double_clicked.disconnect(self.finish_polygon)
        self.polygon.add_point(x, y)
        self.clicks = 0
        self.model.mask_model.mask_QGraphicsPolygonItem(self.polygon)
        self.plot_mask()
        if self.polygon.scene() == self.widget.img_widget.img_view_box.scene():
            self.widget.img_widget.img_view_box.removeItem(self.polygon)
        self.polygon = None

    def finish_arc(self):
        self.widget.img_widget.mouse_moved.disconnect(self.arc_width_preview)
        self.clicks = 0
        self.arc.vertices = self.arc.arc_points
        self.model.mask_model.mask_QGraphicsPolygonItem(self.arc)
        self.plot_mask()
        if self.arc.scene() == self.widget.img_widget.img_view_box.scene():
            self.widget.img_widget.img_view_box.removeItem(self.arc)
        self.arc = None

    def below_thresh_btn_click(self):
        thresh = np.float64(self.widget.below_thresh_txt.text())
        self.model.mask_model.mask_below_threshold(self.model.img_data, thresh)
        self.plot_mask()

    def above_thresh_btn_click(self):
        thresh = np.float64(self.widget.above_thresh_txt.text())
        self.model.mask_model.mask_above_threshold(self.model.img_data, thresh)
        self.plot_mask()

    def grow_btn_click(self):
        self.model.mask_model.grow()
        self.plot_mask()

    def shrink_btn_click(self):
        self.model.mask_model.shrink()
        self.plot_mask()

    def invert_mask_btn_click(self):
        self.model.mask_model.invert_mask()
        self.plot_mask()

    def clear_mask_btn_click(self):
        self.model.mask_model.clear_mask()
        self.plot_mask()

    def cosmic_btn_click(self):
        self.model.mask_model.remove_cosmic(self.model.img_data)
        self.plot_mask()

    def save_mask_btn_click(self):
        img_filename, _ = os.path.splitext(os.path.basename(self.model.img_model.filename))
        filename, selected_filter = QtWidgets.QFileDialog.getSaveFileName(
            self.widget,
            caption="Save mask data",
            directory=os.path.join(self.model.working_directories['mask'],
                                   img_filename + '.mask'),
            filter=';;'.join([
                self.DEFAULT_MASK_FILTER,
                f"{self.FLIPUD_MASK_FILTER_PREFIX} (*.npy)",
                f"{self.FLIPUD_MASK_FILTER_PREFIX} (*.edf)",
            ]))

        if filename != '':
            flipud = selected_filter.startswith(self.FLIPUD_MASK_FILTER_PREFIX)
            self.model.working_directories['mask'] = os.path.dirname(filename)
            self.model.mask_model.save_mask(filename, flipud)

    def load_mask_btn_click(self):
        filename, selected_filter = QtWidgets.QFileDialog.getOpenFileName(
            self.widget,
            caption="Load mask data",
            directory=self.model.working_directories['mask'],
            filter=';;'.join([
                self.DEFAULT_MASK_FILTER,
                f"{self.FLIPUD_MASK_FILTER_PREFIX} (*.npy *.edf)",
            ]))

        if filename != '':
            flipud = selected_filter.startswith(self.FLIPUD_MASK_FILTER_PREFIX)
            self.model.working_directories['mask'] = os.path.dirname(filename)
            if self.model.mask_model.load_mask(filename, flipud):
                self.plot_mask()
            else:
                QtWidgets.QMessageBox.critical(self.widget, 'Error',
                                               'Image data and mask data in selected file do not have '
                                               'the same shape. Mask could not be loaded.')

    def add_mask_btn_click(self):
        filename, selected_filter = QtWidgets.QFileDialog.getOpenFileName(
            self.widget,
            caption="Add mask data",
            directory=self.model.working_directories['mask'],
            filter=';;'.join([
                self.DEFAULT_MASK_FILTER,
                f"{self.FLIPUD_MASK_FILTER_PREFIX} (*.npy *.edf)",
            ]))

        if filename != '':
            flipud = selected_filter.startswith(self.FLIPUD_MASK_FILTER_PREFIX)
            self.model.working_directories['mask'] = os.path.dirname(filename)
            if self.model.mask_model.add_mask(filename, flipud):
                self.plot_mask()
            else:
                QtWidgets.QMessageBox.critical(self.widget, 'Error',
                                               'Image data and mask data in selected file do not have '
                                               'the same shape. Mask could not be added.')

    def plot_mask(self):
        self.model.current_configuration.update_plugin_existing_mask()
        self.widget.img_widget.activate_mask()
        self.widget.img_widget.plot_mask(self.model.mask_model.get_display_mask())

    def key_press_event(self, ev):
        if self.state == "point":
            if ev.text() == 'q':
                self.widget.point_size_sb.setValue(self.widget.point_size_sb.value() + 1)
            if ev.text() == 'w':
                self.widget.point_size_sb.setValue(self.widget.point_size_sb.value() - 1)

        if ev.modifiers() == QtCore.Qt.ControlModifier:
            if ev.key() == 90:  # for pressing z
                self.undo_btn_click()
            elif ev.key() == 89:  # for pressing y
                self.redo_btn_click()
            elif ev.key() == 83:  # for pressing s
                self.save_mask_btn_click()
            elif ev.key == 79:  # for pressing o
                self.load_mask_btn_click()
            elif ev.key == 65:  # for pressing a
                self.add_mask_btn_click()

    def mask_rb_click(self):
        self.model.mask_model.set_mode(True)
        self.widget.img_widget.mask_preview_fill_color = QtGui.QColor(255, 0, 0, 150)
        self.update_shape_preview_fill_color()

    def unmask_rb_click(self):
        self.model.mask_model.set_mode(False)
        self.widget.img_widget.mask_preview_fill_color = QtGui.QColor(0, 255, 0, 150)
        self.update_shape_preview_fill_color()

    def fill_rb_click(self):
        self.model.transparent_mask = False
        self.widget.img_widget.set_mask_color([255, 0, 0, 255])
        self.plot_mask()

    #
    def transparent_rb_click(self):
        self.model.transparent_mask = True
        self.widget.img_widget.set_mask_color([255, 0, 0, 100])
        self.plot_mask()

    def show_img_mouse_position(self, x, y):
        try:
            if x > 0 and y > 0:
                str = "x: %8.1f   y: %8.1f   I: %6.f" % (
                    x, y, self.widget.img_widget.img_data.T[int(np.floor(x)), int(np.floor(y))])
            else:
                str = "x: %.1f y: %.1f" % (x, y)
        except (IndexError, AttributeError):
            str = "x: %.1f y: %.1f" % (x, y)
        self.widget.pos_lbl.setText(str)

    def update_gui(self):
        self.plot_image()

        # transparency
        if self.model.transparent_mask:
            self.widget.transparent_rb.setChecked(True)
            self.transparent_rb_click()
        else:
            self.widget.fill_rb.setChecked(True)
            self.fill_rb_click()

        self._update_plugin_checkboxes()
        self.plot_mask()

    def _update_plugin_checkboxes(self):
        """Sync plugin checkbox states with the model."""
        manager = self.model.mask_plugin_manager
        for name in self.widget.plugin_widget.plugin_names:
            row = self.widget.plugin_widget.get_row(name)
            if row is not None:
                enabled = manager.is_enabled(name)
                row.checkbox.blockSignals(True)
                row.checkbox.setChecked(enabled)
                row.checkbox.blockSignals(False)
                row.imprint_btn.setEnabled(enabled)
