# SPDX-License-Identifier: MIT
"""Async CPU processing for the experimental single-crystal rotation series."""

from dataclasses import replace
from datetime import datetime
from pathlib import Path
import threading
import time
from uuid import uuid4

import numpy as np
from PIL import Image
from qtpy import QtCore, QtWidgets

from .async_job import AsyncJobRunner
from ..model.omega_background import (
    BackgroundCancelled,
    OmegaBackgroundTask,
    display_detector_mask,
    native_detector_mask,
    subtract_omega_background,
)
from ..model.util.omega_background import ArPLSParameters, backend_name, default_workers
from ..widgets.OmegaBackgroundDialog import OmegaBackgroundDialog


class OmegaBackgroundController(QtCore.QObject):
    def __init__(self, single_crystal_controller):
        super().__init__(single_crystal_controller.widget)
        self.owner = single_crystal_controller
        self.dialog = OmegaBackgroundDialog(self.owner.widget)
        self._runner = AsyncJobRunner(self)
        self._cancelled = threading.Event()
        self._result = None
        self._source_series = None
        self._started = 0
        self._runner.succeeded.connect(self._succeeded)
        self._runner.failed.connect(self._failed)
        self.owner.widget.omega_background_button.clicked.connect(self.show)
        self.dialog.run_button.clicked.connect(self.run)
        self.dialog.cancel_button.clicked.connect(self.cancel)
        self.dialog.close_button.clicked.connect(self.dialog.reject)
        self.dialog.rejected.connect(self.cancel)
        self.dialog.browse_button.clicked.connect(self.browse)
        self.dialog.open_result_button.clicked.connect(self.open_result)
        self.dialog.progress_changed.connect(self._progress)
        self.dialog.workers.setValue(default_workers())
        self.dialog.backend_label.setText(backend_name())

    def show(self):
        if self._runner.is_busy:
            self.dialog.show()
            self.dialog.raise_()
            return
        series = self.owner.series
        if series is None:
            self.owner.widget.status_label.setText(
                "Open a rotation series before subtracting its background."
            )
            return
        self.dialog.source_label.setText(
            f"{len(series.files)} frames · {Path(series.files[0]).name}\n"
            f"ω {series.omega_bounds[0, 0]:g} → {series.omega_bounds[-1, 1]:g}°"
        )
        if not self.dialog.output_parent.text():
            self.dialog.output_parent.setText(str(Path(series.files[0]).parent))
        self.dialog.zero_padding.setChecked(self.owner.widget.zero_padding.isChecked())
        self.dialog.show()
        self.dialog.raise_()

    def browse(self):
        directory = QtWidgets.QFileDialog.getExistingDirectory(
            self.dialog,
            "Choose the parent folder for new results",
            self.dialog.output_parent.text(),
            options=QtWidgets.QFileDialog.DontUseNativeDialog,
        )
        if directory:
            self.dialog.output_parent.setText(directory)

    def run(self):
        if self._runner.is_busy:
            return
        self._result = None
        self.dialog.open_result_button.setEnabled(False)
        try:
            series = self.owner.series
            if series is None:
                raise ValueError("Open a rotation series first.")
            parent = Path(self.dialog.output_parent.text()).expanduser()
            if not parent.is_dir():
                raise ValueError("Choose an existing output parent folder.")
            mask = None
            if self.dialog.use_mask.isChecked():
                mask = native_detector_mask(
                    np.array(self.owner.model.mask_model.get_mask(), copy=True),
                    tuple(self.owner.model.img_model.params.transformations),
                )
            task = OmegaBackgroundTask(
                series=series,
                mask=mask,
                parameters=ArPLSParameters(
                    self.dialog.smoothness.value(),
                    self.dialog.tolerance.value(),
                    self.dialog.iterations.value(),
                ),
                workers=self.dialog.workers.value(),
                export_frames=self.dialog.export_frames.isChecked(),
                exclude_zero_padding=self.dialog.zero_padding.isChecked(),
            )
            output = (
                parent
                / f"omega_background_{datetime.now():%Y%m%d_%H%M%S}_{uuid4().hex[:6]}"
            )
        except (ValueError, KeyError) as exc:
            self.dialog.status_label.setText(str(exc))
            return
        self._source_series = series
        self._cancelled.clear()
        self._started = time.perf_counter()
        self.dialog.progress_bar.setValue(0)
        self.dialog.set_busy(True)
        self._runner.submit(
            lambda: subtract_omega_background(
                task, output, progress=self._report_progress
            )
        )

    def _report_progress(self, stage, done, total):
        if self._cancelled.is_set():
            return False
        try:
            self.dialog.progress_changed.emit(stage, done, total)
        except RuntimeError:
            self._cancelled.set()
        return not self._cancelled.is_set()

    @QtCore.Slot(str, int, int)
    def _progress(self, stage, done, total):
        self.dialog.progress_bar.setValue(round(100 * done / max(1, total)))
        self.dialog.status_label.setText(
            f"{stage}: {done:,} / {total:,}\n{time.perf_counter() - self._started:.1f} s elapsed"
        )

    def cancel(self):
        self._cancelled.set()
        if self._runner.is_busy:
            self.dialog.status_label.setText(
                "Cancelling after the current frame or processing tile…"
            )

    def _succeeded(self, job_id, result):
        self.dialog.set_busy(False)
        self._result = result
        m = result.metadata
        t = m["seconds"]
        self.dialog.progress_bar.setValue(100)
        self.dialog.status_label.setText(
            f"Saved {m['frames']} frames’ results to:\n{result.directory}\n"
            f"Read {t['read']:.2f} s · processing {t['processing']:.2f} s · export {t['write']:.2f} s · total {t['total']:.2f} s\n"
            f"{m['unconverged_pixels']:,} pixels reached the iteration limit; inspect unconverged.tif."
        )
        self.dialog.open_result_button.setEnabled(m["export_frames"])

    def _failed(self, job_id, exc, traceback_text):
        self.dialog.set_busy(False)
        self.dialog.status_label.setText(
            "Cancelled; incomplete output removed."
            if isinstance(exc, BackgroundCancelled)
            else f"Background subtraction failed: {exc}"
        )

    def open_result(self):
        if self._result is None or not self._result.metadata["export_frames"]:
            return
        records = self._result.metadata["source_records"]
        series = replace(
            self._source_series,
            files=tuple(
                str(self._result.directory / r["corrected_file"]) for r in records
            ),
            source_records=tuple(records),
            angle_source=self._source_series.angle_source
            + "; arPLS corrected; see manifest.json",
        )
        self.owner.load_series(series)
        # Some traces were excluded because of padding/nonfinite values in
        # another frame. Reapply the complete exported mask, not just the
        # currently visible frame's exclusions.
        with Image.open(self._result.directory / "mask.tif") as image:
            mask = display_detector_mask(
                np.asarray(image),
                tuple(self.owner.model.img_model.params.transformations),
            )
        self.owner.model.mask_model.set_mask_data(mask)
        self.owner.model.use_mask = True
        self.owner.widget.status_label.setText(
            "Browsing arPLS-corrected frames for position finding. Use original counts and validated uncertainties for intensity analysis."
        )
        self.dialog.hide()
