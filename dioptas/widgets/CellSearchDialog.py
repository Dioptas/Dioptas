# SPDX-License-Identifier: MIT
"""Explicit instrument assumptions; deliberately no material/cell input."""

from qtpy import QtWidgets
from .UtilityWidgets import open_file_dialog


class CellSearchDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, *, filename=""):
        super().__init__(parent)
        self.setWindowTitle("Geometry and blind cell search · experimental")
        layout = QtWidgets.QVBoxLayout(self)
        note = QtWidgets.QLabel(
            "Use the detector calibration for this run. "
            "The search uses positions only and assumes a vertical sample axis. "
            "Both rotation signs can be tested when the direction is uncertain."
            " Primitive and Bravais cell settings are ranked automatically after "
            "a passing lattice is found."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        form = QtWidgets.QFormLayout()
        layout.addLayout(form)
        self.filename = QtWidgets.QLineEdit(filename)
        form.addRow("Detector calibration", self.filename)
        browse = QtWidgets.QPushButton("Choose PONI file…")
        browse.clicked.connect(self.browse)
        form.addRow(browse)
        self.rows = QtWidgets.QComboBox()
        self.rows.addItems(
            [
                "Dioptas displayed rows (legacy calibration)",
                "Original file rows (before Dioptas flip)",
            ]
        )
        form.addRow("Calibration coordinates", self.rows)
        self.direction = QtWidgets.QComboBox()
        self.direction.addItems(
            ["Test both signs (uncertain)", "Axis +vertical", "Axis −vertical"]
        )
        form.addRow("Omega rotation", self.direction)
        self.backend = QtWidgets.QComboBox()
        self.backend.addItem("FFT grain search", "fft_grains")
        self.backend.addItem("Compact FFT cell search (comparison)", "compact_fft")
        form.addRow("Search method", self.backend)
        self.max_grains = QtWidgets.QSpinBox()
        self.max_grains.setRange(1, 40)
        self.max_grains.setValue(8)
        form.addRow("Maximum grain candidates", self.max_grains)
        self.backend.currentIndexChanged.connect(
            lambda: self.max_grains.setEnabled(
                self.backend.currentData() == "fft_grains"
            )
        )
        self.maximum = QtWidgets.QDoubleSpinBox()
        self.maximum.setRange(3, 100)
        self.maximum.setValue(30)
        form.addRow("Maximum cell edge (Å)", self.maximum)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.resize(620, 300)

    def browse(self):
        filename = open_file_dialog(
            self, "Detector calibration for this scan", "", "PONI (*.poni)"
        )
        if filename:
            self.filename.setText(filename)

    def signs(self):
        return [(1, -1), (1,), (-1,)][self.direction.currentIndex()]
