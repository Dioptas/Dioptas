# SPDX-License-Identifier: MIT
"""Experimental mode: one native job at a time, with stale-result protection."""

from functools import partial
from pathlib import Path

import numpy as np

from .async_job import DedicatedAsyncJobRunner
from ..model.single_crystal import (
    SpotTask,
    backend_available,
    export_spots,
    measure_spots,
)
from ..widgets.UtilityWidgets import open_file_dialog, save_file_dialog


class SingleCrystalController:
    def __init__(self, widget, model, *, run_async=True):
        self.widget, self.model = widget, model
        self.result = None
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
        widget.export_button.clicked.connect(self.export)
        for item in widget.parameter_widgets():
            item.valueChanged.connect(self.invalidate)
        widget.saturation_enabled.toggled.connect(self.invalidate)
        widget.zero_padding.toggled.connect(self.invalidate)
        # Remain subscribed while hidden to invalidate work when its source changes.
        for signal in (
            model.img_changed,
            model.mask_changed,
            model.configuration_selected,
            model.configuration_params_changed,
        ):
            signal.connect(self.invalidate)
        self.invalidate()

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
        if self._closed:
            return
        self._generation += 1
        self.result = None
        self.widget.table_model.set_result(None)
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
        message = "Source or settings changed. Run detection to measure this image."
        if not self._available:
            message = (
                "The experimental spot engine is not included in this PhaseSmith build."
            )
        elif busy:
            message = "Measuring spots…"
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
        except Exception as exc:
            self.widget.status_label.setText(str(exc))
            return
        if self._runner is None:
            try:
                self._show_result(measure_spots(task), generation)
            except Exception as exc:
                self.widget.status_label.setText(str(exc))
        else:
            job = self._runner.submit(partial(measure_spots, task))
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
        default = (
            str(Path(self.result.metadata["source_file"]).with_suffix(""))
            + "_spots.csv"
        )
        filename = save_file_dialog(
            self.widget, "Export spot measurements", default, "CSV (*.csv)"
        )
        if filename:
            try:
                export_spots(self.result, filename)
                self.widget.status_label.setText(
                    "Exported all spots and their measurement settings."
                )
            except Exception as exc:
                self.widget.status_label.setText(f"Could not export spots: {exc}")
