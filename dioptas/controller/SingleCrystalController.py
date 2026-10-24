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


class _SeriesCancelled(Exception):
    """Inputs changed while a series worker was between frames."""


class SingleCrystalController:
    def __init__(self, widget, model, *, run_async=True):
        self.widget, self.model = widget, model
        self.result = None
        self.series = None
        self._browsing_series = False
        self._active = False
        self._closed = False
        self._generation = 0
        self._jobs = {}
        self._available = backend_available()
        self._runner = DedicatedAsyncJobRunner(widget) if run_async else None
        if self._runner is not None:
            self._runner.succeeded.connect(self._succeeded)
            self._runner.failed.connect(self._failed)
        widget.detect_button.clicked.connect(self.detect)
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
        self._generation += 1
        if self._runner is not None:
            self._runner.shutdown(wait=False)

    def invalidate(self, *_):
        if self._closed or self._browsing_series:
            return
        self._generation += 1
        self.result = None
        self.widget.table_model.set_result(None)
        self.widget.position_table_model.set_result(None)
        self.widget.position_plot.clear()
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

    def load_series(self, series):
        self._browsing_series = True
        try:
            self.model.img_model.load(series.files[0])
        finally:
            self._browsing_series = False
        self.series = series
        slider = self.widget.frame_slider
        slider.blockSignals(True)
        slider.setRange(0, len(series.files) - 1)
        slider.setValue(0)
        slider.setEnabled(True)
        slider.blockSignals(False)
        self.widget.position_plot.show()
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
            options=QtWidgets.QFileDialog.DontUseNativeDialog,
        )
        if not filename:
            return
        try:
            dialog = RotationSeriesDialog(filename, self.widget)
            if dialog.exec_() == QtWidgets.QDialog.Accepted:
                self.load_series(dialog.series)
        except Exception as exc:
            self.widget.status_label.setText(f"Could not open series: {exc}")

    def show_position_track(self, *_):
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
            f"Spot {track + 1}: detected x (yellow) and y (cyan) versus omega"
        )
        plot.plot(rows[:, 4], rows[:, 2], pen="y", symbol="o")
        plot.plot(rows[:, 4], rows[:, 3], pen="c", symbol="o")
        if len(rows):
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
                self.widget.status_label.setText(f"Spot measurement failed: {exc}")

    def _show_result(self, result, generation):
        if generation != self._generation or self._closed:
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
