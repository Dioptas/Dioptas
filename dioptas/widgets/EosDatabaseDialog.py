# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
"""
EoS material database browser dialog — pure view, opened as a compact
modal from the Phase panel. All content and behavior comes from
EosDatabaseController; the dialog only lays out widgets and re-emits
user actions as signals.
"""

import re

from qtpy import QtWidgets, QtCore

from .CustomWidgets import FlatButton, HorizontalLine


_SUBSCRIPT_DIGITS = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
_SCREW_AXIS_PREFIX = re.compile(r"^([PABCIFR]\s*)([2346])([1-5])")


def _display_space_group(space_group: str) -> str:
    """Render compact Hermann-Mauguin symbols in crystallographic form."""
    displayed = _SCREW_AXIS_PREFIX.sub(
        lambda match: (
            f"{match.group(1)}{match.group(2)}"
            f"{match.group(3).translate(_SUBSCRIPT_DIGITS)}"
        ),
        space_group,
    )
    displayed = re.sub(
        r"_(\d)",
        lambda match: match.group(1).translate(_SUBSCRIPT_DIGITS),
        displayed,
    )
    return displayed


class EosDatabaseDialog(QtWidgets.QDialog):

    search_changed = QtCore.Signal(str)
    material_selected = QtCore.Signal(int)   # row in the materials table
    load_clicked = QtCore.Signal()
    export_clicked = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("EoS Material Database")
        self.setMinimumSize(720, 520)
        self.setModal(True)
        self.setWindowModality(QtCore.Qt.ApplicationModal)

        self._create_widgets()
        self._create_layout()
        self._connect_signals()

    def showEvent(self, event):
        """
        On macOS, a QDialog shown via exec_() from a button click can come
        up without keyboard focus actually landing on a child widget — the
        text fields look interactive but don't accept clicks/typing until
        the window is explicitly activated. Force it here.
        """
        super().showEvent(event)
        self.raise_()
        self.activateWindow()
        self.search_input.setFocus(QtCore.Qt.OtherFocusReason)

    def _create_widgets(self):
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText(
            "Search: Au, MgFe, gold, periclase, alumina…")
        self.clear_btn = FlatButton("All")

        self.materials_table = QtWidgets.QTableWidget()
        self.materials_table.setColumnCount(2)
        self.materials_table.setHorizontalHeaderLabels(
            ["Material", "Space Group"])
        self.eos_table = QtWidgets.QTableWidget()
        self.eos_table.setColumnCount(8)
        # Keep this label uppercase in the model as well as on screen. The
        # theme's text-transform happens only while painting, after Qt has
        # measured the narrower mixed-case text, and otherwise clips the F.
        self.eos_table.setHorizontalHeaderLabels(
            ["EoS", "T", "Authors", "Year", "FIT P RANGE",
             "K0 (GPa)", "K0′", "V0 (Å³)"])
        self.eos_table.setToolTip(
            "Fit P range is the experimental pressure interval used to "
            "constrain the published EoS, not a phase-stability range.\n"
            "Theoretical, reference-model, and qualitative-limit records "
            "have no defensible numeric fit interval.\n"
            "± values are publication-reported errors in the displayed "
            "units.\n‘error n/r’ means that no verified error is recorded; "
            "it does not mean zero.")
        for table in (self.materials_table, self.eos_table):
            table.setSelectionBehavior(
                QtWidgets.QAbstractItemView.SelectRows)
            table.setSelectionMode(
                QtWidgets.QAbstractItemView.SingleSelection)
            table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            table.verticalHeader().setVisible(False)
        self.materials_table.setAlternatingRowColors(True)
        # Keep the material columns governed by persistent resize modes.
        # A one-shot resizeColumnsToContents() briefly shrinks the header to
        # the width of a single search result before Qt gets another layout
        # pass, which can leave a visible gap on some platforms.
        materials_header = self.materials_table.horizontalHeader()
        materials_header.setSectionResizeMode(
            0, QtWidgets.QHeaderView.Stretch)
        materials_header.setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeToContents)
        # keep the "Space Group" header readable even when all cell
        # contents are narrower
        materials_header.setMinimumSectionSize(120)
        eos_header = self.eos_table.horizontalHeader()
        for column in (0, 1, 3, 5, 6, 7):
            eos_header.setSectionResizeMode(
                column, QtWidgets.QHeaderView.ResizeToContents)
        # The two descriptive columns share the available width. Giving all
        # of it to Authors makes that column dominate the result table.
        for column in (2, 4):
            eos_header.setSectionResizeMode(
                column, QtWidgets.QHeaderView.Stretch)

        self.export_btn = FlatButton("Export .eosmat…")
        self.export_btn.setEnabled(False)
        self.export_btn.setToolTip(
            "Save the selected material (all its EoS records) as a\n"
            ".eosmat file that can be loaded with the normal Add button")
        self.load_btn = QtWidgets.QPushButton("Load as Phase")
        self.load_btn.setEnabled(False)
        self.load_btn.setDefault(True)
        self.close_btn = QtWidgets.QPushButton("Close")

    def _create_layout(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        search_row = QtWidgets.QHBoxLayout()
        search_row.addWidget(self.search_input, 1)
        search_row.addWidget(self.clear_btn)
        root.addLayout(search_row)

        root.addWidget(QtWidgets.QLabel("Materials:"))
        root.addWidget(self.materials_table, 3)
        root.addWidget(QtWidgets.QLabel("Equation of state records:"))
        root.addWidget(self.eos_table, 2)

        root.addWidget(HorizontalLine())

        bottom = QtWidgets.QHBoxLayout()
        bottom.addWidget(self.export_btn)
        bottom.addStretch()
        bottom.addWidget(self.load_btn)
        bottom.addWidget(self.close_btn)
        root.addLayout(bottom)

    def _connect_signals(self):
        self.search_input.textChanged.connect(self.search_changed)
        self.clear_btn.clicked.connect(self.search_input.clear)
        self.materials_table.selectionModel().selectionChanged.connect(
            self._emit_material_selected)
        self.materials_table.doubleClicked.connect(
            self._load_material_from_double_click)
        self.eos_table.doubleClicked.connect(
            self._load_eos_from_double_click)
        self.load_btn.clicked.connect(self.load_clicked)
        self.export_btn.clicked.connect(self.export_clicked)
        self.close_btn.clicked.connect(self.reject)

    def _emit_material_selected(self):
        self.material_selected.emit(self.selected_material_row())

    def _load_material_from_double_click(self, index):
        if index.isValid():
            self.materials_table.selectRow(index.row())
            self.load_clicked.emit()

    def _load_eos_from_double_click(self, index):
        if index.isValid():
            self.eos_table.selectRow(index.row())
            self.load_clicked.emit()

    # -- view interface used by the controller -------------------------

    def fill_materials(self, rows):
        """*rows*: list of (display_name, space_group) tuples."""
        table = self.materials_table
        # Drop any previous selection first: after a refill the same row
        # index would still count as "selected" without ever firing
        # selectionChanged, leaving the EoS table below showing the
        # records of whatever material sat at that row before.
        table.clearSelection()
        table.setRowCount(len(rows))
        for r, (name, space_group) in enumerate(rows):
            table.setItem(r, 0, QtWidgets.QTableWidgetItem(name))
            space_group_item = QtWidgets.QTableWidgetItem(
                _display_space_group(space_group)
            )
            table.setItem(r, 1, space_group_item)

    def fill_eos_records(self, rows, selected_row=0,
                         reference_tooltips=None, thermal_tooltips=None):
        """Rows include authors/year, thermal indicator and fit values."""
        table = self.eos_table
        reference_tooltips = reference_tooltips or []
        thermal_tooltips = thermal_tooltips or []
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, text in enumerate(row):
                item = QtWidgets.QTableWidgetItem(text)
                if c in (2, 3) and r < len(reference_tooltips):
                    item.setToolTip(reference_tooltips[r])
                elif c == 1:
                    item.setTextAlignment(QtCore.Qt.AlignCenter)
                    if r < len(thermal_tooltips):
                        item.setToolTip(thermal_tooltips[r])
                table.setItem(r, c, item)
        if rows:
            table.selectRow(max(0, min(selected_row, len(rows) - 1)))
        # A material without EoS records is still loadable — its peak
        # positions at ambient conditions are useful on their own.
        material_selected = self.selected_material_row() >= 0
        self.load_btn.setEnabled(material_selected)
        self.export_btn.setEnabled(material_selected)

    def selected_material_row(self) -> int:
        rows = self.materials_table.selectionModel().selectedRows()
        return rows[0].row() if rows else -1

    def selected_eos_row(self) -> int:
        rows = self.eos_table.selectionModel().selectedRows()
        return rows[0].row() if rows else -1
