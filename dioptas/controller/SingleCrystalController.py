# SPDX-License-Identifier: MIT
"""Experimental mode: one native job at a time, with stale-result protection."""

from functools import partial
from pathlib import Path

import numpy as np
from qtpy import QtWidgets

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
    refinement_summary,
    export_refinement,
)
from ..widgets.PredictionResidualDialog import PredictionResidualDialog


class _SeriesCancelled(Exception):
    """Inputs changed while a series worker was between frames."""


class SingleCrystalController:
    def __init__(self, widget, model, *, run_async=True):
        from ..file_dialogs import configure_file_dialogs

        configure_file_dialogs(experimental=True)
        self.widget, self.model = widget, model
        self.result = None
        self.cell_result = None
        self.refinement_result = None
        self._residual_dialog = None
        self.cell_calibration_filename = ""
        self.series = None
        self._browsing_series = False
        self._active = False
        self._closed = False
        self._generation = 0
        self._jobs = {}
        self._available = backend_available()
        self.omega_background_controller = OmegaBackgroundController(self)
        self._runner = DedicatedAsyncJobRunner(widget) if run_async else None
        if self._runner is not None:
            self._runner.succeeded.connect(self._succeeded)
            self._runner.failed.connect(self._failed)
        widget.detect_button.clicked.connect(self.detect)
        widget.cell_button.clicked.connect(self.index_cells)
        widget.cell_export_button.clicked.connect(self.export_cell_candidates)
        widget.refine_button.clicked.connect(lambda: self.refine_positions())
        widget.orthorhombic_button.clicked.connect(
            lambda: self.refine_positions(symmetry="orthorhombic")
        )
        widget.residual_button.clicked.connect(self.show_refinement_residuals)
        widget.refinement_export_button.clicked.connect(self.export_position_refinement)
        widget.prediction_enabled.toggled.connect(self.plot_predictions)
        widget.prediction_model.currentIndexChanged.connect(self.plot_predictions)
        widget.predicted_overlay.sigClicked.connect(self._prediction_clicked)
        widget.load_button.clicked.connect(self.open_image)
        widget.series_button.clicked.connect(self.open_series)
        widget.series_progress.connect(self._series_progress)
        widget.frame_slider.valueChanged.connect(self.browse_frame)
        widget.table_view.selectionModel().selectionChanged.connect(
            self.show_position_track
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
            self.widget.update_frame_buttons()
            self.widget.detect_button.setText("Find spots and extract counts")
        self.invalidate()

    def _series_progress(self, generation, done, total):
        if not self._closed and generation == self._generation:
            self.widget.status_label.setText(
                f"Finding positions: frame {done}/{total}…"
            )

    def activate(self):
        self._active = True
        self.plot_image()

    def deactivate(self):
        self._active = False

    def shutdown(self):
        self._closed = True
        self.omega_background_controller.cancel()
        self._generation += 1
        if self._runner is not None:
            self._runner.shutdown(wait=False)

    def invalidate(self, *_):
        if self._closed or self._browsing_series:
            return
        self._generation += 1
        self.result = None
        self.cell_result = None
        self._clear_refinement()
        self.widget.cell_summary.clear()
        self.widget.cell_summary.hide()
        self.widget.cell_export_button.setEnabled(False)
        self.widget.table_model.set_result(None)
        self.widget.position_table_model.set_result(None)
        self.widget.position_plot.clear()
        self.widget.position_plot.hide()
        self.widget.position_track_label.setText(
            "Select a spot row in the Positions tab to inspect its motion across frames."
        )
        self.widget.position_track_label.setVisible(self.series is not None)
        self.widget.spot_overlay.clear()
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
        can_refine = False
        if self.cell_result is not None:
            try:
                preferred_candidate(self.cell_result)
                can_refine = True
            except ValueError:
                pass
        self.widget.refine_button.setEnabled(
            can_refine and not busy and not self._closed
        )
        self.widget.orthorhombic_button.setEnabled(
            can_refine and not busy and not self._closed
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
            i = self.widget.frame_slider.value()
            a, b = self.series.omega_bounds[i]
            self.widget.frame_label.setText(
                f"Frame {i + 1}/{len(self.series.files)} · file #{self.series.frame_numbers[i]} · "
                f"ω {a:g} → {b:g}° · midpoint {(a + b) / 2:g}°"
            )
            self._plot_frame_positions(i)
            self.plot_predictions()

    def _clear_refinement(self):
        self.refinement_result = None
        self.widget.predicted_overlay.clear()
        self.widget.prediction_note.setText(
            "Predictions require an indexed cell. No intensity or extinction model."
        )
        self.widget.prediction_model.setEnabled(False)
        self.widget.refinement_summary.clear()
        self.widget.refinement_summary.hide()
        self.widget.residual_button.setEnabled(False)
        self.widget.refinement_export_button.setEnabled(False)
        if self._residual_dialog is not None:
            self._residual_dialog.close()
            self._residual_dialog.deleteLater()
            self._residual_dialog = None

    def plot_predictions(self, *_):
        w = self.widget
        w.predicted_overlay.clear()
        if self.refinement_result is None or not w.prediction_enabled.isChecked():
            return
        predictions = (
            self.refinement_result.initial_scan
            if w.prediction_model.currentIndex() == 0
            else self.refinement_result.refined_scan
        )
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
        w.prediction_note.setText(
            f"{len(rows)} possible Bragg centres in this exposure · cyan +. "
            "Click a prediction for HKL/omega. Weak or systematically absent reflections may be predicted."
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
        brushes = ["r" if t.flags[int(track)] else "y" for track in rows[:, 0]]
        self.widget.spot_overlay.setData(
            x=rows[:, 2] + 0.5, y=rows[:, 3] + 0.5, pen=None, brush=brushes, size=8
        )

    def browse_frame(self, index):
        if self.series is None:
            return
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
        slider = self.widget.frame_slider
        slider.blockSignals(True)
        slider.setRange(0, len(series.files) - 1)
        slider.setValue(index)
        slider.setEnabled(True)
        slider.blockSignals(False)
        self.widget.update_frame_buttons()
        self.widget.position_plot.hide()
        self.widget.position_track_label.show()
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

    def show_position_track(self, *_):
        self.widget.position_plot.hide()
        if not isinstance(self.result, SeriesPositions):
            return
        selected = self.widget.table_view.selectionModel().selectedRows()
        if not selected:
            return
        track = selected[0].row()
        rows = self.result.table.observations
        rows = rows[rows[:, 0] == track]
        plot = self.widget.position_plot
        plot.clear()
        self.widget.position_track_label.setText(
            f"Spot {track + 1}: detector coordinates across frames · position, not intensity"
        )
        plot.plot(rows[:, 4], rows[:, 2], pen="y", symbol="o", name="x position")
        plot.plot(rows[:, 4], rows[:, 3], pen="c", symbol="o", name="y position")
        if len(rows):
            plot.show()
            plot.getViewBox().autoRange()
            self.widget.frame_slider.setValue(int(rows[len(rows) // 2, 1]))

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

                def progress(done, total):
                    if self._closed or generation != self._generation:
                        raise _SeriesCancelled
                    self.widget.series_progress.emit(generation, done, total)

                def operation(task):
                    try:
                        return locate_positions(task, progress=progress)
                    except _SeriesCancelled:
                        return None  # Generation/closed checks discard this result.
        except Exception as exc:
            self.widget.status_label.setText(str(exc))
            return
        if self._runner is None:
            try:
                self._show_result(operation(task), generation)
            except Exception as exc:
                self.widget.status_label.setText(str(exc))
        else:
            job = self._runner.submit(partial(operation, task))
            self._jobs[job] = generation
            self._set_ready()

    def _succeeded(self, job, result):
        generation = self._jobs.pop(job, -1)
        if self._closed:
            return
        self._set_ready()
        if generation == self._generation:
            self._show_result(result, generation)

    def _failed(self, job, exc, _traceback):
        generation = self._jobs.pop(job, -1)
        if not self._closed:
            self._set_ready()
            if generation == self._generation:
                self.widget.status_label.setText(
                    f"Experimental processing failed: {exc}"
                )

    def _show_result(self, result, generation):
        if generation != self._generation or self._closed:
            return
        if isinstance(result, CellSearchResult):
            self._clear_refinement()
            self.cell_result = result
            self.widget.cell_summary.setPlainText(cell_summary(result))
            self.widget.cell_summary.show()
            self.widget.sections.setCurrentIndex(2)
            self.widget.cell_export_button.setEnabled(True)
            self._set_ready()
            self.widget.status_label.setText(
                "Cell search completed. Review the candidate cells and held-out matches below."
            )
            return
        if isinstance(result, PositionRefinement):
            self.refinement_result = result
            self.widget.refinement_summary.setPlainText(refinement_summary(result))
            self.widget.refinement_summary.show()
            self.widget.prediction_model.setItemText(
                1,
                "Orthorhombic model"
                if result.metadata.get("metric_constraint") == "orthorhombic"
                else "Refined model",
            )
            self.widget.prediction_model.setEnabled(True)
            self.widget.prediction_model.setCurrentIndex(
                1 if result.refinement.metrics["validation_improved"] else 0
            )
            self.widget.residual_button.setEnabled(True)
            self.widget.refinement_export_button.setEnabled(True)
            self.widget.sections.setCurrentIndex(3)
            self._set_ready()
            self.plot_predictions()
            self.widget.status_label.setText(
                "Prediction/refinement complete. Compare models and inspect residual plots."
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
                    self.show_position_track
                )
            self._plot_frame_positions(self.widget.frame_slider.value())
            self.widget.export_button.setEnabled(True)
            self.widget.cell_button.setEnabled(True)
            self.widget.status_label.setText(
                f"{len(table)} position candidates · {len(table.observations)} frame observations · "
                f"{np.count_nonzero(table.flags)} flagged. Select a row to inspect its trajectory. "
                "No unit cell, symmetry or integrated intensities have been determined."
            )
            return
        self.widget.table_view.setModel(self.widget.table_model)
        self.widget.export_button.setText("Export spots…")
        self.widget.table_model.set_result(table)
        brushes = ["r" if flag else "y" for flag in table.flags]
        self.widget.spot_overlay.setData(
            x=table.column("x") + 0.5,
            y=table.column("y") + 0.5,
            pen=None,
            brush=brushes,
            size=8,
        )
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
            options = IndexingOptions(max_length=dialog.maximum.value())
            operation = partial(find_cells, self.result, geometries, options=options)
        except Exception as exc:
            self.widget.status_label.setText(f"Could not configure cell search: {exc}")
            return
        self.cell_result = None
        self._clear_refinement()
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
        shape = self.model.img_model.raw_img_data.shape
        self._clear_refinement()

        def progress(_done, _total):
            if self._closed or generation != self._generation:
                raise _SeriesCancelled

        def operation():
            try:
                return refine_positions(
                    positions, cells, shape, progress=progress, symmetry=symmetry
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
