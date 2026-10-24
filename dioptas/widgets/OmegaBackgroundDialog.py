# SPDX-License-Identifier: MIT
"""Controls for CPU background estimation along a loaded omega series."""

from qtpy import QtCore, QtWidgets


class OmegaBackgroundDialog(QtWidgets.QDialog):
    progress_changed = QtCore.Signal(str, int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Omega background subtraction")
        self.setMinimumWidth(600)
        layout = QtWidgets.QVBoxLayout(self)
        self.source_label = QtWidgets.QLabel()
        self.source_label.setWordWrap(True)
        layout.addWidget(self.source_label)
        description = QtWidgets.QLabel(
            "Estimate a smooth background at each detector pixel across the rotation "
            "series. Export signed corrected frames and summed images into a new folder. "
            "The original files are preserved."
        )
        description.setWordWrap(True)
        layout.addWidget(description)
        form = QtWidgets.QFormLayout()
        layout.addLayout(form)
        self.smoothness = QtWidgets.QDoubleSpinBox()
        self.smoothness.setDecimals(6)
        self.smoothness.setRange(1e-6, 1e9)
        self.smoothness.setValue(1e4)
        self.smoothness.setToolTip(
            "Larger values fit a smoother background along omega. Broad reflections may enter the baseline."
        )
        form.addRow("Background smoothness (λ)", self.smoothness)
        self.tolerance = QtWidgets.QDoubleSpinBox()
        self.tolerance.setDecimals(6)
        self.tolerance.setRange(1e-6, 0.1)
        self.tolerance.setValue(0.001)
        form.addRow("Convergence tolerance", self.tolerance)
        self.iterations = QtWidgets.QSpinBox()
        self.iterations.setRange(1, 1000)
        self.iterations.setValue(30)
        form.addRow("Maximum iterations", self.iterations)
        self.workers = QtWidgets.QSpinBox()
        self.workers.setRange(1, 128)
        form.addRow("CPU workers", self.workers)
        self.backend_label = QtWidgets.QLabel()
        form.addRow("Processing", self.backend_label)
        self.use_mask = QtWidgets.QCheckBox("Use the current detector mask")
        self.use_mask.setToolTip(
            "Use a fixed snapshot of the current mask, including plugins and ROI, for the whole scan."
        )
        self.use_mask.setChecked(True)
        form.addRow(self.use_mask)
        self.zero_padding = QtWidgets.QCheckBox(
            "Exclude pixels that are zero in any frame"
        )
        self.zero_padding.setToolTip(
            "Enable only when zeros mark detector padding; this also excludes genuine zero-count pixels."
        )
        form.addRow(self.zero_padding)
        self.export_frames = QtWidgets.QCheckBox(
            "Export individual corrected omega frames"
        )
        self.export_frames.setChecked(True)
        form.addRow(self.export_frames)
        row = QtWidgets.QHBoxLayout()
        self.output_parent = QtWidgets.QLineEdit()
        self.browse_button = QtWidgets.QPushButton("Browse…")
        row.addWidget(self.output_parent, 1)
        row.addWidget(self.browse_button)
        form.addRow("Save results inside", row)
        note = QtWidgets.QLabel(
            "Negative residuals are retained. Background subtraction does not remove "
            "counting noise; corrected counts alone do not provide intensity uncertainties. "
            "Masked pixels remain unchanged."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        credit = QtWidgets.QLabel(
            'Omega-sequence approach inspired by <a href="https://gitlab.desy.de/konstantin.glazyrin/background-sc">'
            "Konstantin Glazyrin’s background-sc</a>.<br>Independent implementation of "
            '<a href="https://doi.org/10.1039/C4AN01061B">arPLS, Baek et al. (2015)</a>.'
        )
        credit.setOpenExternalLinks(True)
        credit.setWordWrap(True)
        layout.addWidget(credit)
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)
        self.status_label = QtWidgets.QLabel(
            "Ready. Results include processing and export timings."
        )
        self.status_label.setWordWrap(True)
        self.status_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        layout.addWidget(self.status_label)
        buttons = QtWidgets.QHBoxLayout()
        self.run_button = QtWidgets.QPushButton("Subtract background")
        self.cancel_button = QtWidgets.QPushButton("Cancel processing")
        self.cancel_button.setEnabled(False)
        self.open_result_button = QtWidgets.QPushButton("Open corrected series")
        self.open_result_button.setEnabled(False)
        self.close_button = QtWidgets.QPushButton("Close")
        for button in (
            self.run_button,
            self.cancel_button,
            self.open_result_button,
            self.close_button,
        ):
            buttons.addWidget(button)
        layout.addLayout(buttons)

    def set_busy(self, busy):
        for control in (
            self.smoothness,
            self.tolerance,
            self.iterations,
            self.workers,
            self.use_mask,
            self.zero_padding,
            self.export_frames,
            self.output_parent,
            self.browse_button,
            self.run_button,
            self.close_button,
        ):
            control.setEnabled(not busy)
        self.cancel_button.setEnabled(busy)
        if busy:
            self.open_result_button.setEnabled(False)
