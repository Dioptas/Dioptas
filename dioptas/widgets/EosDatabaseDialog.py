# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
"""
EoS material database browser dialog — pure view, opened as a compact
modal from the Phase panel. All content and behavior comes from
EosDatabaseController; the dialog only lays out widgets and re-emits
user actions as signals.
"""

from qtpy import QtWidgets, QtCore

from .CustomWidgets import FlatButton, HorizontalLine


class EosDatabaseDialog(QtWidgets.QDialog):

    search_changed = QtCore.Signal(str)
    material_selected = QtCore.Signal(int)   # row in the materials table
    load_clicked = QtCore.Signal()
    export_clicked = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("EoS Material Database")
        self.setMinimumSize(680, 520)
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
            "Search: Au, Fe, MgO, gold, iron, alumina…")
        self.clear_btn = FlatButton("All")

        self.materials_table = QtWidgets.QTableWidget()
        self.materials_table.setColumnCount(2)
        self.materials_table.setHorizontalHeaderLabels(
            ["Material", "Space Group"])
        self.eos_table = QtWidgets.QTableWidget()
        self.eos_table.setColumnCount(5)
        self.eos_table.setHorizontalHeaderLabels(
            ["EoS", "Reference", "K0 (GPa)", "K0′", "V0 (Å³)"])
        for table in (self.materials_table, self.eos_table):
            table.setSelectionBehavior(
                QtWidgets.QAbstractItemView.SelectRows)
            table.setSelectionMode(
                QtWidgets.QAbstractItemView.SingleSelection)
            table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            table.verticalHeader().setVisible(False)
        self.materials_table.setAlternatingRowColors(True)
        # the name / reference column takes the free space
        self.materials_table.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.Stretch)
        # keep the "Space Group" header readable even when all cell
        # contents are narrower
        self.materials_table.horizontalHeader().setMinimumSectionSize(120)
        self.eos_table.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.Stretch)

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
        self.load_btn.clicked.connect(self.load_clicked)
        self.export_btn.clicked.connect(self.export_clicked)
        self.close_btn.clicked.connect(self.reject)

    def _emit_material_selected(self):
        self.material_selected.emit(self.selected_material_row())

    # -- view interface used by the controller -------------------------

    def fill_materials(self, rows):
        """*rows*: list of (display_name, symmetry) tuples."""
        table = self.materials_table
        # Drop any previous selection first: after a refill the same row
        # index would still count as "selected" without ever firing
        # selectionChanged, leaving the EoS table below showing the
        # records of whatever material sat at that row before.
        table.clearSelection()
        table.setRowCount(len(rows))
        for r, (name, symmetry) in enumerate(rows):
            table.setItem(r, 0, QtWidgets.QTableWidgetItem(name))
            table.setItem(r, 1, QtWidgets.QTableWidgetItem(symmetry))
        table.resizeColumnsToContents()

    def fill_eos_records(self, rows):
        """*rows*: list of (eos_type, reference, k0, k0_prime, v0) strings."""
        table = self.eos_table
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, text in enumerate(row):
                item = QtWidgets.QTableWidgetItem(text)
                if c == 1:
                    item.setToolTip(text)
                table.setItem(r, c, item)
        table.resizeColumnsToContents()
        if rows:
            table.selectRow(0)
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
