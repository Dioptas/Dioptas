# SPDX-License-Identifier: MIT
"""Explicit angle confirmation for one numbered detector run."""

from pathlib import Path
from qtpy import QtWidgets

from ..model.rotation_series import import_series, series_files, sidecar_record


class RotationSeriesDialog(QtWidgets.QDialog):
    def __init__(self, seed, parent=None):
        super().__init__(parent)
        self.seed = seed
        self.setWindowTitle("Open rotation series")
        layout = QtWidgets.QVBoxLayout(self)
        files, numbers = series_files(seed)
        records = [sidecar_record(p) for p in files]
        missing = sorted(set(range(numbers[0], numbers[-1] + 1)) - set(numbers))
        summary = QtWidgets.QLabel(
            f"{Path(files[0]).name} … {Path(files[-1]).name}\n"
            f"{len(files)} frames; {len(missing)} missing frame numbers.\n"
            "Confirm the exposure angles before finding positions."
        )
        summary.setWordWrap(True)
        layout.addWidget(summary)
        self.sidecars = QtWidgets.QCheckBox(
            "Use per-frame omega0 (start) and omegaR (width)"
        )
        have = all({"omega0", "omegaR"} <= set(r.get("values", {})) for r in records)
        self.sidecars.setEnabled(have)
        self.sidecars.setChecked(have)
        layout.addWidget(self.sidecars)
        form = QtWidgets.QFormLayout()
        layout.addLayout(form)
        first = records[0].get("values", {})
        second = records[1].get("values", {})
        start = first.get("omega0", 0.0)
        step = (second.get("omega0", start + 1) - start) / (numbers[1] - numbers[0])

        def number(label, value, minimum, maximum):
            box = QtWidgets.QDoubleSpinBox()
            box.setDecimals(6)
            box.setRange(minimum, maximum)
            box.setValue(value)
            form.addRow(label, box)
            return box

        self.start = number("First frame start (°)", start, -1e6, 1e6)
        self.step = number("Step between frame starts (°)", step, -360, 360)
        self.width = number(
            "Rotation width per frame (°)", abs(first.get("omegaR", 1)), 0.000001, 360
        )

        def enable_manual():
            for field in (self.start, self.step, self.width):
                field.setEnabled(not self.sidecars.isChecked())

        self.sidecars.toggled.connect(enable_manual)
        enable_manual()
        note = QtWidgets.QLabel(
            "Step and exposure width are separate. Manual angles apply to numeric frame IDs, "
            "so missing numbers retain gaps. Chi, detector position and exposure time are "
            "preserved as metadata; they are not substituted for omega."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        self.error = QtWidgets.QLabel()
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Open | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.confirm)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.series = None

    def confirm(self):
        try:
            manual = (
                None
                if self.sidecars.isChecked()
                else (self.start.value(), self.step.value(), self.width.value())
            )
            self.series = import_series(self.seed, manual_angles=manual)
        except (ValueError, OSError) as exc:
            self.error.setText(str(exc))
        else:
            self.accept()
