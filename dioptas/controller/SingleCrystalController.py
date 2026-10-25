# SPDX-License-Identifier: MIT
"""Experimental mode: one native job at a time, with stale-result protection."""

from functools import partial
from pathlib import Path
from threading import Lock

import numpy as np
from qtpy import QtCore, QtWidgets

from .async_job import DedicatedAsyncJobRunner
from ..model.single_crystal import (
    SpotTask,
    backend_available,
    export_spots,
    measure_spots,
)
from ..widgets.UtilityWidgets import open_file_dialog, save_file_dialog
from ..model.rotation_series import (
    SeriesPositions,
    SeriesTask,
    export_positions,
    locate_positions,
)
from ..widgets.RotationSeriesDialog import RotationSeriesDialog
from .OmegaBackgroundController import OmegaBackgroundController
from ..model.single_crystal_indexing import (
    CellSearchResult,
    geometry_from_poni,
    find_cells,
    cell_summary,
    export_cells,
)
from ..widgets.CellSearchDialog import CellSearchDialog
from ..model.single_crystal_refinement import (
    PositionRefinement,
    preferred_candidate,
    refine_positions,
    export_refinement,
)
from ..widgets.PredictionResidualDialog import PredictionResidualDialog
from ..model.single_crystal_cells import (
    RankedCells,
    rank_cells,
    preview_ranked_cell,
    export_ranked_cells,
)
from ..model.single_crystal_inspection import spot_cell_details


class _SeriesCancelled(Exception):
    """Inputs changed while a series worker was between frames."""


class SingleCrystalController:
    def __init__(self, widget, model, *, run_async=True):
        from ..file_dialogs import configure_file_dialogs

        configure_file_dialogs(experimental=True)
        self.widget, self.model = widget, model
        self.result = None
        self.cell_result = None
        self.cell_selection = None
        self.ranked_result = None
        self.ranked_selection = None
        self._pending_rank_preview = False
        self.refinement_result = None
        self._residual_dialog = None
        self.cell_calibration_filename = ""
        self._hover_position = None
        self._hover_geometry = None
        self._selecting_image_spot = False
        self._updating_cell_result = False
        self._pending_cell_comparison = False
        self.series = None
        self._browsing_series = False
        self._active = False
        self._closed = False
        self._generation = 0
        self._jobs = {}
        self._preview_lock = Lock()
        self._pending_preview = None
        self._preview_frame = None
        self._preview_generation = None
        self._preview_timer = QtCore.QTimer(widget)
        self._preview_timer.setInterval(100)
        self._preview_timer.timeout.connect(self._show_pending_preview)
        self._available = backend_available()
        self.omega_background_controller = OmegaBackgroundController(self)
        self._runner = DedicatedAsyncJobRunner(widget) if run_async else None
        if self._runner is not None:
            self._runner.succeeded.connect(self._succeeded)
            self._runner.failed.connect(self._failed)
        widget.detect_button.clicked.connect(self.detect)
        widget.cell_table.selectionModel().selectionChanged.connect(self._cell_selected)
        widget.cell_button.clicked.connect(self.index_cells)
        widget.rank_table.selectionModel().selectionChanged.connect(self._rank_selected)
        widget.rank_export_button.clicked.connect(self.export_ranked_candidates)
        widget.cell_export_button.clicked.connect(self.export_cell_candidates)
        widget.residual_button.clicked.connect(self.show_refinement_residuals)
        widget.refinement_export_button.clicked.connect(self.export_position_refinement)
        widget.prediction_enabled.toggled.connect(self.plot_predictions)
        widget.predicted_overlay.sigClicked.connect(self._prediction_clicked)
        widget.spot_overlay.sigClicked.connect(self._spot_clicked)
        widget.img_widget.mouse_moved.connect(self.show_image_mouse_position)
        widget.load_button.clicked.connect(self.open_image)
        widget.series_button.clicked.connect(self.open_series)
        widget.series_progress.connect(self._series_progress)
        widget.follow_search.toggled.connect(self._follow_search_changed)
        widget.frame_slider.valueChanged.connect(self.browse_frame)
        widget.position_frames.currentIndexChanged.connect(
            self._browse_selected_observation
        )
        widget.table_view.selectionModel().selectionChanged.connect(
            self.select_position
        )
        widget.export_button.clicked.connect(self.export)
        for item in widget.parameter_widgets():
            item.valueChanged.connect(self.invalidate)
        widget.saturation_enabled.toggled.connect(self.invalidate)
        widget.zero_padding.toggled.connect(self.invalidate)
        # Remain subscribed while hidden to invalidate work when its source changes.
        for signal in (
            model.mask_changed,
            model.configuration_selected,
            model.configuration_params_changed,
        ):
            signal.connect(self.invalidate)
        model.img_changed.connect(self._image_changed)
        self.invalidate()

    def _image_changed(self):
        if self._browsing_series:
            if self._active:
                self.plot_image()
            return
        if self.series is not None:
            self.series = None
            self.widget.frame_slider.setEnabled(False)
            self.widget.follow_search.setEnabled(False)
            self.widget.update_frame_buttons()
            self.widget.detect_button.setText("Find spots and extract counts")
        self.invalidate()

    def _series_progress(self, generation, done, total):
        if (
            not self._closed
            and generation == self._generation
            and generation == self._preview_generation
        ):
            self.widget.status_label.setText(
                f"Finding positions: frame {done}/{total}…"
                if done < total
                else f"All {total} frames searched; linking spots across omega…"
            )

    def _queue_preview(self, generation, preview):
        # Worker-only presentation handoff: replace one snapshot, never queue
        # full detector images in Qt events. No widget access on this thread.
        with self._preview_lock:
            if self._closed or generation != self._generation:
                raise _SeriesCancelled
            self._pending_preview = (generation, preview)

    def _show_pending_preview(self):
        if (
            self._closed
            or not self._active
            or not self.widget.follow_search.isChecked()
        ):
            return
        with self._preview_lock:
            pending, self._pending_preview = self._pending_preview, None
        if pending is None:
            return
        generation, preview = pending
        if generation != self._generation or self.series is None:
            return
        self._preview_frame = preview
        w = self.widget
        w.frame_slider.blockSignals(True)
        w.frame_slider.setValue(preview.index)
        w.frame_slider.blockSignals(False)
        w.update_frame_buttons()
        # Display the already-read worker frame without loading it again or
        # changing the shared image model / triggering integrations per frame.
        w.img_widget.plot_image(preview.image, auto_level=False)
        self._refresh_mouse_position()
        mask = self.model.mask_model.get_mask()
        if self.model.use_mask and mask.shape == preview.image.shape:
            w.img_widget.plot_mask(mask)
            w.img_widget.activate_mask()
        else:
            w.img_widget.deactivate_mask()
        table = preview.table
        w.show_spots(table.column("x") + 0.5, table.column("y") + 0.5, table.flags)
        a, b = self.series.omega_bounds[preview.index]
        name = Path(self.series.files[preview.index]).name
        w.source_label.setText(f"Completed: {name} · spots found: {len(table)}")
        w.frame_label.setText(
            f"Search preview · completed frame {preview.index + 1}/{len(self.series.files)} · "
            f"file #{self.series.frame_numbers[preview.index]} · ω {a:g} → {b:g}°"
        )

    def _stop_preview(self):
        self._preview_timer.stop()
        with self._preview_lock:
            self._pending_preview = None
        self._preview_frame = None
        self._preview_generation = None

    def _finish_preview(self):
        self._show_pending_preview()
        last = self._preview_frame
        self._stop_preview()
        if last is not None and self.series is not None:
            # Synchronize the actual model once, after processing. Final masks,
            # prediction filters and other modes then reference the shown file.
            self.browse_frame(last.index)

    def _follow_search_changed(self, checked):
        if checked:
            self._show_pending_preview()
        elif self._preview_frame is not None:
            self.browse_frame(self._preview_frame.index)

    def activate(self):
        self._active = True
        self.plot_image()

    def deactivate(self):
        self._active = False
        self._preview_frame = None

    def shutdown(self):
        self._closed = True
        self._stop_preview()
        self.omega_background_controller.cancel()
        self._generation += 1
        if self._runner is not None:
            self._runner.shutdown(wait=False)

    def invalidate(self, *_):
        if self._closed or self._browsing_series:
            return
        self._generation += 1
        self._stop_preview()
        self.result = None
        self.cell_result = None
        self.cell_selection = None
        self._clear_ranked()
        self._clear_refinement()
        self.widget.cell_table_model.set_result(None)
        self.widget.cell_table_button.setEnabled(False)
        self.widget.cell_summary.clear()
        self.widget.cell_summary.hide()
        self.widget.cell_export_button.setEnabled(False)
        self.widget.table_model.set_result(None)
        self.widget.position_table_model.set_result(None)
        self.widget.spot_overlay.clear()
        self.widget.show_selected_spot()
        self.widget.export_button.setEnabled(False)
        self._set_ready()
        if self._active:
            self.plot_image()

    def _set_ready(self):
        busy = self._runner is not None and self._runner.is_busy
        self.widget.detect_button.setEnabled(
            self._available and not busy and not self._closed
        )
        self.widget.cell_button.setEnabled(
            isinstance(self.result, SeriesPositions) and not busy and not self._closed
        )
        self.widget.cell_table.setEnabled(
            self.cell_result is not None and not self._closed
        )
        self.widget.rank_table.setEnabled(
            self.ranked_result is not None and not self._closed
        )
        message = (
            "Ready to find 3D positions across the rotation series."
            if self.series is not None
            else "Source or settings changed. Run detection to measure this image."
        )
        if not self._available:
            message = (
                "The experimental spot engine is not included in this PhaseSmith build."
            )
        elif busy:
            message = (
                "Finding series positions…"
                if self.series is not None
                else "Measuring spots…"
            )
        self.widget.status_label.setText(message)

    def plot_image(self):
        image = self.model.img_model.raw_img_data
        if image is None:
            return
        self.widget.img_widget.plot_image(image, auto_level=True)
        self._refresh_mouse_position()
        mask = self.model.mask_model.get_mask()
        if self.model.use_mask and mask.shape == image.shape:
            self.widget.img_widget.plot_mask(mask)
            self.widget.img_widget.activate_mask()
        else:
            self.widget.img_widget.deactivate_mask()
        filename = self.model.img_model.filename
        self.widget.source_label.setText(
            f"{Path(filename).name or 'Current image'} · "
            f"{image.shape[1]} × {image.shape[0]} pixels · raw counts"
        )
        if self.series is not None:
            filename = self.model.img_model.filename
            i = (
                self.series.files.index(filename)
                if filename in self.series.files
                else self.widget.frame_slider.value()
            )
            self.widget.frame_slider.blockSignals(True)
            self.widget.frame_slider.setValue(i)
            self.widget.frame_slider.blockSignals(False)
            self.widget.update_frame_buttons()
            a, b = self.series.omega_bounds[i]
            self.widget.frame_label.setText(
                f"Frame {i + 1}/{len(self.series.files)} · file #{self.series.frame_numbers[i]} · "
                f"ω {a:g} → {b:g}° · midpoint {(a + b) / 2:g}°"
            )
            self._plot_frame_positions(i)
            self.plot_predictions()
        else:
            self._plot_selected_position()

    def _hover_geometry_context(self):
        image = self.widget.img_widget.img_data
        return (
            id(self.model.current_configuration),
            None if image is None else image.shape,
            tuple(self.model.img_model.params.transformations),
            self.cell_calibration_filename,
        )

    def _remember_image_geometry(self, metadata):
        # Retain detector calibration across detection-parameter changes, but
        # never reuse it for a different configuration, image shape or transform.
        self._hover_geometry = (self._hover_geometry_context(), metadata)
        self._refresh_mouse_position()

    def _refresh_mouse_position(self):
        if self._hover_position is not None:
            self.show_image_mouse_position(*self._hover_position)

    def show_image_mouse_position(self, x, y):
        self._hover_position = (x, y)
        w = self.widget
        w.mouse_pixel_label.setText("x: —   y: —   I: —")
        w.mouse_geometry_label.setText("2θ: —   d: —   Q: —   χ: —")
        image = w.img_widget.img_data
        if (
            image is None
            or not np.isfinite([x, y]).all()
            or not (0 <= x < image.shape[1] and 0 <= y < image.shape[0])
        ):
            return
        # Image coordinates describe pixel edges; array indices describe centres.
        # Read the actual displayed array, including asynchronous search previews.
        value = image[int(np.floor(y)), int(np.floor(x))]
        w.mouse_pixel_label.setText(f"x: {x:.1f}   y: {y:.1f}   I: {value:.6g} counts")
        if (
            self._hover_geometry is not None
            and self._hover_geometry[0] == self._hover_geometry_context()
        ):
            meta = self._hover_geometry[1]
            origin, fast, slow = np.asarray(meta["vectors"])[:3]
            ray = origin + (x - 0.5) * fast + (y - 0.5) * slow
            tth = np.arctan2(np.hypot(ray[0], ray[1]), ray[2])
            azi = np.arctan2(ray[0], ray[1])
            wavelength = meta["wavelength_angstrom"]
        elif self.model.calibration_model.is_calibrated:
            calibration = self.model.calibration_model
            tth = calibration.get_two_theta_img(y, x)
            azi = calibration.get_azi_img(y, x)
            wavelength = calibration.wavelength
            if wavelength is not None:
                wavelength *= 1e10
        else:
            return
        if wavelength is None or not np.isfinite(wavelength) or wavelength <= 0:
            return
        q = 4 * np.pi * np.sin(tth / 2) / wavelength
        d = 2 * np.pi / q if q > 0 else np.inf
        w.mouse_geometry_label.setText(
            f"2θ: {np.degrees(tth):.3f}°   d: {d:.4f} Å   "
            f"Q: {q:.4f} Å⁻¹   χ: {np.degrees(azi):.2f}°"
        )

    def _clear_ranked(self):
        self._pending_cell_comparison = False
        self.ranked_result = None
        self.ranked_selection = None
        self._pending_rank_preview = False
        self.widget.rank_table_model.set_result(None)
        self.widget.rank_table_button.setEnabled(False)
        self.widget.rank_export_button.setEnabled(False)
        self.widget.rank_summary.setText(
            "Select a passing lattice to obtain ranked cells."
        )
        self.widget.ranked_group.setTitle("Ranked cell settings")

    def _clear_refinement(self):
        self.refinement_result = None
        self.widget.predicted_overlay.hide()
        self.widget.predicted_overlay.clear()
        self.widget.prediction_note.setText(
            "Select a ranked cell to show its predicted positions."
        )
        self.widget.prediction_selected_cell_label.setText(
            "Preparing positions for the selected cell…"
            if self.ranked_result is not None and self.ranked_selection is not None
            else "No ranked cell selected."
        )
        self.widget.residual_button.setEnabled(False)
        self.widget.refinement_export_button.setEnabled(False)
        self._refresh_selected_position_details()
        if self._residual_dialog is not None:
            self._residual_dialog.close()
            self._residual_dialog.deleteLater()
            self._residual_dialog = None

    def plot_predictions(self, *_):
        w = self.widget
        self._refresh_selected_position_details()
        # Hide while the old bounds still exist, so Qt invalidates the painted
        # crosses. ScatterPlotItem.clear() alone resets bounds before updating.
        w.predicted_overlay.hide()
        w.predicted_overlay.clear()
        if not w.prediction_enabled.isChecked():
            w.prediction_note.setText("Predicted Bragg centres are hidden.")
            return
        if self.refinement_result is None:
            return
        predictions = self.refinement_result.refined_scan
        rows = np.flatnonzero(predictions.frame_indices == w.frame_slider.value())
        values = predictions.values[rows]
        image = self.model.img_model.raw_img_data
        if image is None:
            return
        x, y = np.floor(values[:, :2] + 0.5).astype(int).T
        valid = np.isfinite(image[y, x])
        if w.zero_padding.isChecked():
            valid &= image[y, x] != 0
        if self.model.use_mask:
            mask = self.model.mask_model.get_mask()
            if mask.shape == image.shape:
                valid &= ~mask[y, x]
        rows, values = rows[valid], values[valid]
        data = [
            (*map(int, predictions.hkl[i]), float(predictions.values[i, 2]))
            for i in rows
        ]
        w.predicted_overlay.setData(
            x=values[:, 0] + 0.5, y=values[:, 1] + 0.5, data=data
        )
        w.predicted_overlay.show()
        w.prediction_note.setText(
            f"{len(rows)} predicted positions in this frame · cyan +."
        )

    def _prediction_clicked(self, _item, points, *_):
        if points:
            h, k, l, omega = points[0].data()
            self.widget.prediction_note.setText(
                f"Calculated HKL ({h}, {k}, {l}) · Bragg centre ω={omega:.4f}°. "
                "No intensity or space-group assumption."
            )

    def _plot_frame_positions(self, i):
        if not isinstance(self.result, SeriesPositions):
            return
        t = self.result.table
        rows = t.observations[t.observations[:, 1] == i]
        self.widget.show_spots(
            rows[:, 2] + 0.5,
            rows[:, 3] + 0.5,
            t.flags[rows[:, 0].astype(int)],
            row_ids=rows[:, 0].astype(int),
        )
        self._plot_selected_position()

    def _spot_clicked(self, _item, points, event=None):
        if self.result is None:
            return
        # Preview detections have no linked track IDs yet. Never treat their
        # frame-local ordinal as a row in the final positions table.
        points = [p for p in points if p.data() is not None]
        if not points:
            return

        def distance(point):
            delta = point.pos() - event.pos()
            return delta.x() ** 2 + delta.y() ** 2

        point = min(points, key=distance) if event is not None else points[0]
        row = int(point.data())
        table = self.widget.table_view
        if not 0 <= row < table.model().rowCount():
            return
        self.widget.sections.setCurrentWidget(self.widget.positions_section)
        self._selecting_image_spot = True
        try:
            table.selectRow(row)
            # Repeated clicks on an already selected row emit no change signal.
            self.select_position()
        finally:
            self._selecting_image_spot = False
        table.scrollTo(
            table.model().index(row, 0), QtWidgets.QAbstractItemView.PositionAtCenter
        )

    def _plot_selected_position(self):
        self.widget.show_selected_spot()
        self._refresh_selected_position_details()
        if self.result is None:
            return
        selected = self.widget.table_view.selectionModel().selectedRows()
        if not selected:
            return
        track = selected[0].row()
        if isinstance(self.result, SeriesPositions):
            rows = self.result.table.observations
            rows = rows[
                (rows[:, 0] == track) & (rows[:, 1] == self.widget.frame_slider.value())
            ]
            if not len(rows):
                return
            # Mark this frame's observation, rather than the merged x/y centroid.
            x, y = rows[0, 2:4]
        else:
            if track >= len(self.result.table):
                return
            x = self.result.table.column("x")[track]
            y = self.result.table.column("y")[track]
        point = (float(x) + 0.5, float(y) + 0.5)
        self.widget.show_selected_spot(*point)
        return point

    def _browse_selected_observation(self, index):
        frame = self.widget.position_frames.itemData(index)
        if frame is not None and self.series is not None:
            self.widget.frame_slider.setValue(frame)

    def _refresh_selected_position_details(self):
        w = self.widget
        selected = w.table_view.selectionModel().selectedRows()
        if self.result is None or not selected:
            w.position_details.hide()
            return
        track = selected[0].row()
        if not 0 <= track < len(self.result.table):
            w.position_details.hide()
            return
        w.position_details.setTitle(f"Selected spot {track + 1}")
        w.position_details.show()
        try:
            detail = spot_cell_details(
                self.result,
                track,
                cells=self.cell_result,
                selection=self.cell_selection,
                ranked=self.ranked_result,
                setting_index=self.ranked_selection,
                refinement=self.refinement_result,
                refined=True,
            )
            w.position_cell_label.setText(detail.model)
            status = (
                "Not assessed"
                if detail.indexed is None
                else "Yes"
                if detail.indexed
                else "No"
            )
            w.position_indexing_label.setText(
                status + (f" · {detail.note}" if detail.note else "")
            )
            w.position_hkl_label.setText(
                "—" if detail.hkl is None else " ".join(map(str, detail.hkl))
            )
            if detail.residual is None:
                w.position_residual_label.setText("—")
            else:
                dx, dy, domega = detail.residual
                w.position_residual_label.setText(
                    f"Δxy {np.hypot(dx, dy):.3f} px · Δω {domega:+.4f}°\n"
                    f"Δx {dx:+.3f}, Δy {dy:+.3f} px"
                )
        except (ValueError, IndexError, StopIteration, RuntimeError) as exc:
            w.position_cell_label.setText("Selected cell")
            w.position_indexing_label.setText(f"Not assessed · {exc}")
            w.position_hkl_label.setText("—")
            w.position_residual_label.setText("—")
        combo = w.position_frames
        blocker = QtCore.QSignalBlocker(combo)
        combo.clear()
        if isinstance(self.result, SeriesPositions):
            rows = self.result.table.observations
            frames = np.unique(rows[rows[:, 0] == track, 1].astype(int))
            for frame in frames:
                a, b = self.result.table.omega_bounds[frame]
                numbers = self.result.metadata.get("frame_numbers")
                file_number = f" · file #{numbers[frame]}" if numbers else ""
                combo.addItem(
                    f"Frame {frame + 1}{file_number} · ω {a:g} → {b:g}°", int(frame)
                )
            w.position_frames_label.setText(f"Observed frames ({len(frames)})")
            combo.setCurrentIndex(combo.findData(w.frame_slider.value()))
            combo.setEnabled(self.series is not None)
        else:
            w.position_frames_label.setText("Observed frames (1)")
            combo.addItem("Current image · omega unavailable")
            combo.setEnabled(False)
        del blocker

    def browse_frame(self, index):
        if self.series is None:
            return
        self._preview_frame = None
        if self._preview_timer.isActive():
            self.widget.follow_search.setChecked(False)
        self._browsing_series = True
        try:
            self.model.img_model.load(self.series.files[index])
        except Exception as exc:
            self.widget.status_label.setText(f"Could not load series frame: {exc}")
        finally:
            self._browsing_series = False

    def load_series(self, series, selected_file=None):
        index = (
            series.files.index(str(Path(selected_file)))
            if selected_file is not None
            else 0
        )
        self._browsing_series = True
        try:
            self.model.img_model.load(series.files[index])
        finally:
            self._browsing_series = False
        self.series = series
        self.widget.follow_search.setEnabled(True)
        slider = self.widget.frame_slider
        slider.blockSignals(True)
        slider.setRange(0, len(series.files) - 1)
        slider.setValue(index)
        slider.setEnabled(True)
        slider.blockSignals(False)
        self.widget.update_frame_buttons()
        self.widget.detect_button.setText("Find 3D positions")
        self.widget.export_button.setText("Export positions…")
        self.widget.measurement_note.setText(
            "Positions use detected signal as centroid weights. Omega values use exposure "
            "midpoints; the listed omega RMS is a detected spread, not an error estimate. "
            "The current application mask applies to every frame. "
            "These are position candidates for later indexing, not integrated intensities."
        )
        self.invalidate()
        self.plot_image()

    def open_series(self):
        current = self.model.img_model.filename
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self.widget,
            "Choose any numbered frame in a rotation series",
            str(Path(current).parent)
            if current
            else self.model.working_directories["image"],
            "Images (*)",
            options=QtWidgets.QFileDialog.DontUseNativeDialog
            | QtWidgets.QFileDialog.DontUseCustomDirectoryIcons,
        )
        if not filename:
            return
        try:
            dialog = RotationSeriesDialog(filename, self.widget)
            if dialog.exec_() == QtWidgets.QDialog.Accepted:
                self.load_series(dialog.series, filename)
        except Exception as exc:
            self.widget.status_label.setText(f"Could not open series: {exc}")

    def select_position(self, *_):
        selected = self.widget.table_view.selectionModel().selectedRows()
        if self.result is None or not selected:
            self.widget.show_selected_spot()
            self._refresh_selected_position_details()
            return
        track = selected[0].row()
        if isinstance(self.result, SeriesPositions) and not self._selecting_image_spot:
            rows = self.result.table.observations
            rows = rows[rows[:, 0] == track]
            if len(rows):
                self.widget.frame_slider.setValue(int(rows[len(rows) // 2, 1]))
        # Also update when selecting another spot on the already displayed frame.
        point = self._plot_selected_position()
        if point is not None:
            view = self.widget.img_widget.img_view_box
            rect = view.viewRect()
            if not rect.contains(QtCore.QPointF(*point)):
                rect.moveCenter(QtCore.QPointF(*point))
                view.setRange(rect=rect, padding=0)
            self.widget.status_label.setText(
                f"Selected spot {track + 1} · magenta ring · "
                f"x {point[0] - 0.5:.2f}, y {point[1] - 0.5:.2f} px"
            )

    def _task(self):
        raw = self.model.img_model.raw_img_data
        if raw is None:
            raise ValueError("Load a detector image first.")
        image = np.array(raw, order="C", copy=True)
        mask = (
            self.model.mask_model.get_mask()
            if self.model.use_mask
            else np.zeros(image.shape, bool)
        )
        if mask.shape != image.shape:
            raise ValueError("The enabled mask does not match this image.")
        mask = np.array(mask, dtype=bool, order="C", copy=True)
        # Detector gaps represented by NaN are explicit exclusions, not zeros.
        mask |= ~np.isfinite(image)
        if self.widget.zero_padding.isChecked():
            mask |= image == 0
        image.flags.writeable = mask.flags.writeable = False
        w = self.widget
        options = dict(
            threshold_sigma=w.threshold.value(),
            outer_radius=int(w.outer_radius.value()),
            min_pixels=int(w.min_pixels.value()),
            padding=int(w.padding.value()),
            background_margin=int(w.background_margin.value()),
        )
        return SpotTask(
            image,
            mask,
            self.model.img_model.filename,
            options,
            w.gain.value(),
            w.read_noise.value(),
            w.saturation.value() if w.saturation_enabled.isChecked() else None,
            tuple(self.model.img_model.params.transformations),
            dict(
                application_mask_enabled=bool(self.model.use_mask),
                exclude_zero_padding=self.widget.zero_padding.isChecked(),
                exclude_nonfinite=True,
            ),
        )

    def detect(self):
        if (
            self._closed
            or not self._available
            or (self._runner and self._runner.is_busy)
        ):
            return
        self.invalidate()
        generation = self._generation
        try:
            task = self._task()
            operation = measure_spots
            if self.series is not None:
                # Freeze only the application mask. Zero/nonfinite exclusions
                # are computed separately from each source frame by the worker.
                mask = (
                    self.model.mask_model.get_mask()
                    if self.model.use_mask
                    else np.zeros(task.mask.shape, bool)
                )
                task = SeriesTask(
                    self.series,
                    np.array(mask, dtype=bool, copy=True),
                    task.options,
                    self.widget.link_radius.value(),
                    self.widget.zero_padding.isChecked(),
                    task.gain,
                    task.read_noise,
                    task.saturation,
                    task.transformations,
                )
                task.mask.flags.writeable = False
                self._preview_generation = generation
                self._preview_timer.start()

                def preview(frame):
                    self._queue_preview(generation, frame)

                def progress(done, total):
                    if self._closed or generation != self._generation:
                        raise _SeriesCancelled
                    self.widget.series_progress.emit(generation, done, total)

                def operation(task):
                    try:
                        return locate_positions(
                            task, progress=progress, preview=preview
                        )
                    except _SeriesCancelled:
                        return None  # Generation/closed checks discard this result.
        except Exception as exc:
            self.widget.status_label.setText(str(exc))
            return
        if self._runner is None:
            try:
                result = operation(task)
                self._finish_preview()
                self._show_result(result, generation)
            except Exception as exc:
                self._stop_preview()
                self.plot_image()
                self.widget.status_label.setText(str(exc))
        else:
            job = self._runner.submit(partial(operation, task))
            self._jobs[job] = generation
            self._set_ready()

    def _succeeded(self, job, result):
        generation = self._jobs.pop(job, -1)
        if self._closed:
            return
        if generation == self._generation:
            self._finish_preview()
        self._set_ready()
        if generation == self._generation:
            self._show_result(result, generation)
        if self._pending_cell_comparison and not self._closed:
            self.compare_ranked_cells()
        elif self._pending_rank_preview and not self._closed:
            self._preview_rank_selection()

    def _failed(self, job, exc, _traceback):
        generation = self._jobs.pop(job, -1)
        if not self._closed:
            self._set_ready()
            if generation == self._generation and not self._pending_cell_comparison:
                self._stop_preview()
                self.plot_image()
                self.widget.spot_overlay.clear()
                self.widget.status_label.setText(
                    f"Experimental processing failed: {exc}"
                )

        if self._pending_cell_comparison and not self._closed:
            self.compare_ranked_cells()
        elif self._pending_rank_preview and not self._closed:
            self._preview_rank_selection()

    def _show_result(self, result, generation):
        if generation != self._generation or self._closed:
            return
        if isinstance(result, RankedCells):
            try:
                origin = preferred_candidate(self.cell_result, self.cell_selection)[:2]
            except (ValueError, AttributeError):
                return
            if result.selection != origin:
                return
            self._pending_cell_comparison = False
            self.ranked_result = result
            self.widget.rank_table_model.set_result(result)
            self.widget.rank_table_button.setEnabled(True)
            self.widget.rank_export_button.setEnabled(True)
            sign, number = result.selection
            self.widget.ranked_group.setTitle(
                f"Cells for lattice {number + 1} · axis {sign:+d}"
            )
            self.widget.sections.setCurrentWidget(self.widget.cell_section)
            self._set_ready()
            self.widget.rank_table.selectRow(
                self.widget.rank_table_proxy.mapFromSource(
                    self.widget.rank_table_model.index(0, 0)
                ).row()
            )
            return
        if isinstance(result, CellSearchResult):
            self._clear_ranked()
            self._clear_refinement()
            self.cell_selection = None
            self.cell_result = result
            if result.metadata.get("geometry"):
                self._remember_image_geometry(result.metadata["geometry"][0])
            self._updating_cell_result = True
            self.widget.cell_table_model.set_result(result)
            self.widget.cell_table_button.setEnabled(
                bool(self.widget.cell_table_model.rows)
            )
            self.widget.cell_summary.setPlainText(cell_summary(result))
            self.widget.cell_summary.show()
            # Training-based default only; users can choose any displayed row.
            try:
                sign, index, _, _ = preferred_candidate(result)
                source_row = next(
                    i
                    for i, row in enumerate(self.widget.cell_table_model.rows)
                    if row[0] == (sign, index)
                )
            except ValueError:
                source_row = 0
            if self.widget.cell_table_model.rows:
                mapped = self.widget.cell_table_proxy.mapFromSource(
                    self.widget.cell_table_model.index(source_row, 0)
                )
                self.widget.cell_table.selectRow(mapped.row())
            self.widget.sections.setCurrentWidget(self.widget.cell_section)
            self.widget.cell_export_button.setEnabled(True)
            self._set_ready()
            self.widget.status_label.setText(
                "Cell search completed. Review the candidate cells and held-out matches below."
            )
            self._updating_cell_result = False
            self._cell_selected()
            return
        if isinstance(result, PositionRefinement):
            ranked = result.metadata.get("ranked_setting")
            if ranked is not None and (
                self.ranked_result is None
                or ranked["setting_index"] != self.ranked_selection
                or (result.metadata["axis_sign"], result.metadata["candidate_index"])
                != self.ranked_result.selection
            ):
                return
            self.refinement_result = result
            self.widget.prediction_selected_cell_label.setText(
                f"Selected cell: rank {ranked['rank']} · {ranked['symbol']}"
                if ranked
                else f"Selected cell: {result.metadata.get('metric_constraint', 'triclinic')}"
            )
            self.widget.residual_button.setEnabled(True)
            self.widget.refinement_export_button.setEnabled(True)
            self.widget.sections.setCurrentWidget(self.widget.cell_section)
            self._set_ready()
            self.plot_predictions()
            self.widget.status_label.setText(
                f"Displaying rank {ranked['rank']} · {ranked['symbol']}. Select another row to compare cells."
                if ranked
                else "Prediction/refinement complete. Compare models and inspect residual plots."
            )
            return
        self.result = result
        table = result.table
        if isinstance(result, SeriesPositions):
            model = self.widget.position_table_model
            model.set_result(table)
            if self.widget.table_view.model() is not model:
                self.widget.table_view.setModel(model)
                self.widget.table_view.selectionModel().selectionChanged.connect(
                    self.select_position
                )
            self._plot_frame_positions(self.widget.frame_slider.value())
            self.widget.export_button.setEnabled(True)
            self.widget.cell_button.setEnabled(True)
            self.widget.status_label.setText(
                f"{len(table)} position candidates · {len(table.observations)} frame observations · "
                f"{np.count_nonzero(table.flags)} flagged. Select a row to show its frame. "
                "No unit cell, symmetry or integrated intensities have been determined."
            )
            return
        if self.widget.table_view.model() is not self.widget.table_model:
            self.widget.table_view.setModel(self.widget.table_model)
            self.widget.table_view.selectionModel().selectionChanged.connect(
                self.select_position
            )
        self.widget.export_button.setText("Export spots…")
        self.widget.table_model.set_result(table)
        self.widget.show_spots(
            table.column("x") + 0.5,
            table.column("y") + 0.5,
            table.flags,
            row_ids=np.arange(len(table)),
        )
        self._plot_selected_position()
        self.widget.export_button.setEnabled(True)
        self.widget.status_label.setText(
            f"{len(table)} spots · {np.count_nonzero(table.flags)} flagged · "
            f"{table.rejected_small_components} components below the size limit. "
            "Yellow markers: unflagged; red markers: inspect quality flags."
        )

    def index_cells(self):
        if (
            not isinstance(self.result, SeriesPositions)
            or self._closed
            or (self._runner and self._runner.is_busy)
        ):
            return
        filename = self.cell_calibration_filename
        if not filename and self.model.calibration_model.is_calibrated:
            filename = self.model.calibration_model.filename
        dialog = CellSearchDialog(self.widget, filename=filename)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        try:
            from phasesmith.experimental.indexing import IndexingOptions
            from phasesmith.experimental.grains import GrainSearchOptions

            filename = dialog.filename.text().strip()
            self.cell_calibration_filename = filename
            geometries = []
            for sign in dialog.signs():
                geometry, metadata = geometry_from_poni(
                    filename,
                    axis_sign=sign,
                    shape=self.model.img_model.raw_img_data.shape,
                    original_rows=dialog.rows.currentIndex() == 1,
                    transformations=tuple(self.model.img_model.params.transformations),
                )
                geometries.append((sign, geometry, metadata))
            self._remember_image_geometry(geometries[0][2])
            backend = dialog.backend.currentData()
            options = (
                GrainSearchOptions(
                    max_length=dialog.maximum.value(),
                    max_grains=dialog.max_grains.value(),
                )
                if backend == "fft_grains"
                else IndexingOptions(max_length=dialog.maximum.value())
            )
            operation = partial(
                find_cells, self.result, geometries, options=options, backend=backend
            )
        except Exception as exc:
            self.widget.status_label.setText(f"Could not configure cell search: {exc}")
            return
        self.cell_result = None
        self.cell_selection = None
        self._clear_ranked()
        self._clear_refinement()
        self.widget.cell_table_model.set_result(None)
        self.widget.cell_table_button.setEnabled(False)
        self.widget.cell_summary.clear()
        self.widget.cell_export_button.setEnabled(False)
        generation = self._generation
        if self._runner is None:
            try:
                self._show_result(operation(), generation)
            except Exception as exc:
                self.widget.status_label.setText(f"Cell search failed: {exc}")
        else:
            job = self._runner.submit(operation)
            self._jobs[job] = generation
            self._set_ready()
            self.widget.status_label.setText(
                "Correcting geometry and searching for a cell…"
            )

    def _cell_selected(self, *_):
        if self._updating_cell_result:
            return
        index = self.widget.cell_table.currentIndex()
        selection = index.data(QtCore.Qt.UserRole) if index.isValid() else None
        if selection == self.cell_selection:
            return
        self.cell_selection = selection
        self._clear_ranked()
        self._clear_refinement()
        if selection is not None and self.cell_result is not None:
            sign, number = selection
            search = next(r[2] for r in self.cell_result.reports if r[0] == sign)
            candidate = search.candidates[number]
            self.widget.cell_summary.setPlainText(
                f"Candidate {number + 1}, axis {sign:+d}: {'passes' if candidate.accepted else 'fails'} held-out checks.\n"
                f"Angles: {candidate.cell[3]:.3f}, {candidate.cell[4]:.3f}, {candidate.cell[5]:.3f}°; "
                f"V={candidate.volume:.2f} Å³.\n"
                f"Training {candidate.training_fraction:.1%}; held out {candidate.validation_fraction:.1%}; "
                f"control ≤{candidate.null_fraction:.1%}.\n"
                "Select a passing candidate for prediction/refinement. Cell symmetry and primitivity remain unproven."
            )
        self._set_ready()

        self._refresh_selected_position_details()
        if selection is not None and self.cell_result is not None:
            if candidate.accepted:
                self.compare_ranked_cells()
            else:
                self.widget.status_label.setText(
                    "Selected lattice did not pass its checks; no ranked cells. "
                    "Inspect the lattice candidates."
                )

    def compare_ranked_cells(self):
        if self._closed or self.cell_result is None:
            return
        try:
            preferred_candidate(self.cell_result, self.cell_selection)
        except ValueError:
            self._pending_cell_comparison = False
            return
        if self._runner and self._runner.is_busy:
            self._pending_cell_comparison = True
            self.widget.status_label.setText("Waiting to compare the selected lattice…")
            return
        generation = self._generation
        self._clear_ranked()
        self._clear_refinement()
        operation = partial(
            rank_cells, self.result, self.cell_result, selection=self.cell_selection
        )
        if self._runner is None:
            try:
                self._show_result(operation(), generation)
            except Exception as exc:
                self.widget.status_label.setText(f"Cell comparison failed: {exc}")
        else:
            job = self._runner.submit(operation)
            self._jobs[job] = generation
            self._set_ready()
            self.widget.status_label.setText(
                "Comparing primitive hypotheses and ranking Bravais settings…"
            )

    def _rank_selected(self, *_):
        index = self.widget.rank_table.currentIndex()
        selected = index.data(QtCore.Qt.UserRole) if index.isValid() else None
        if (
            self.ranked_result is None
            or selected is None
            or selected == self.ranked_selection
        ):
            return
        self.ranked_selection = selected
        self._clear_refinement()
        row = next(
            r
            for r in self.ranked_result.comparison.ranking
            if r.setting_index == selected
        )
        fit = self.ranked_result.comparison.settings[selected]
        self.widget.rank_summary.setText(
            f"Rank {row.rank} · {fit.setting.symbol} · Δ score {row.score_delta:.3f}. "
            f"{row.reason}. Select a row to preview its fitted cell; no new refinement. "
            "Lattice metric only; physical primitivity and space group remain unproven."
        )
        self._pending_rank_preview = True
        self._preview_rank_selection()

    def _preview_rank_selection(self):
        if self._closed or self.ranked_result is None or self.ranked_selection is None:
            self._pending_rank_preview = False
            return
        if self._runner and self._runner.is_busy:
            return  # Coalesce rapid selections; only the last requested row is previewed next.
        self._pending_rank_preview = False
        operation = partial(
            preview_ranked_cell,
            self.ranked_result,
            self.result,
            self.model.img_model.raw_img_data.shape,
            self.ranked_selection,
        )
        generation = self._generation
        if self._runner is None:
            try:
                self._show_result(operation(), generation)
            except Exception as exc:
                self.widget.status_label.setText(f"Cell preview failed: {exc}")
        else:
            job = self._runner.submit(operation)
            self._jobs[job] = generation
            self._set_ready()
            self.widget.status_label.setText(
                "Predicting spots for the selected ranked cell…"
            )

    def export_ranked_candidates(self):
        if self.ranked_result is None:
            return
        filename = save_file_dialog(
            self.widget, "Export ranked cells", "ranked_cells.json", "JSON (*.json)"
        )
        if filename:
            try:
                export_ranked_cells(self.ranked_result, filename)
                self.widget.status_label.setText(
                    "Exported ranks, fitted settings and rejected primitive support."
                )
            except Exception as exc:
                self.widget.status_label.setText(
                    f"Could not export ranked cells: {exc}"
                )

    def refine_positions(self, *, symmetry="triclinic"):
        if (
            self.cell_result is None
            or not isinstance(self.result, SeriesPositions)
            or self._closed
            or (self._runner and self._runner.is_busy)
        ):
            return
        generation = self._generation
        positions, cells = self.result, self.cell_result
        selection = self.cell_selection
        shape = self.model.img_model.raw_img_data.shape
        self._clear_refinement()

        def progress(_done, _total):
            if self._closed or generation != self._generation:
                raise _SeriesCancelled

        def operation():
            try:
                return refine_positions(
                    positions,
                    cells,
                    shape,
                    progress=progress,
                    symmetry=symmetry,
                    selection=selection,
                )
            except _SeriesCancelled:
                return None

        if self._runner is None:
            try:
                self._show_result(operation(), generation)
            except Exception as exc:
                self.widget.status_label.setText(f"Prediction/refinement failed: {exc}")
        else:
            job = self._runner.submit(operation)
            self._jobs[job] = generation
            self._set_ready()
            self.widget.status_label.setText(
                "Refining cell/orientation and predicting Bragg centres…"
            )

    def show_refinement_residuals(self):
        if self.refinement_result is None:
            return
        if self._residual_dialog is None:
            self._residual_dialog = PredictionResidualDialog(
                self.refinement_result, self.widget
            )
        self._residual_dialog.show()
        self._residual_dialog.raise_()

    def export_position_refinement(self):
        if self.refinement_result is None:
            return
        filename = save_file_dialog(
            self.widget,
            "Export positional refinement",
            "position_refinement.json",
            "JSON (*.json)",
        )
        if filename:
            try:
                export_refinement(self.refinement_result, filename)
                self.widget.status_label.setText(
                    "Exported initial/refined predictions, residuals and provenance."
                )
            except Exception as exc:
                self.widget.status_label.setText(f"Could not export refinement: {exc}")

    def export_cell_candidates(self):
        if self.cell_result is None:
            return
        filename = save_file_dialog(
            self.widget,
            "Export blind cell candidates",
            "cell_candidates.json",
            "JSON (*.json)",
        )
        if filename:
            try:
                export_cells(self.cell_result, filename)
                self.widget.status_label.setText(
                    "Exported candidates, reciprocal positions, assignments and provenance."
                )
            except Exception as exc:
                self.widget.status_label.setText(
                    f"Could not export cell candidates: {exc}"
                )

    def open_image(self):
        filename = open_file_dialog(
            self.widget, "Open detector image", "", "Images (*)"
        )
        if filename:
            try:
                self.model.img_model.load(filename)
            except Exception as exc:
                self.widget.status_label.setText(f"Could not open image: {exc}")

    def export(self):
        if self.result is None:
            return
        series_result = isinstance(self.result, SeriesPositions)
        default = (
            str(
                Path(
                    self.result.metadata["source_files"][0]
                    if series_result
                    else self.result.metadata["source_file"]
                ).with_suffix("")
            )
            + "_spots.csv"
        )
        filename = save_file_dialog(
            self.widget, "Export spot measurements", default, "CSV (*.csv)"
        )
        if filename:
            try:
                (export_positions if series_result else export_spots)(
                    self.result, filename
                )
                self.widget.status_label.setText(
                    "Exported all spots and their measurement settings."
                )
            except Exception as exc:
                self.widget.status_label.setText(f"Could not export spots: {exc}")
