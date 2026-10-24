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
