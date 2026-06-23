# SPDX-License-Identifier: MIT
"""
EoS Database Browser Dialog
Opens as a compact modal from the Phase panel.
"""
import os
import tempfile
import logging

from qtpy import QtWidgets, QtCore, QtGui

from .CustomWidgets import FlatButton, HorizontalLine

logger = logging.getLogger(__name__)

# Chemical element aliases for friendlier search
_ELEMENT_ALIASES = {
    "gold": "Au", "silver": "Ag", "iron": "Fe", "copper": "Cu",
    "platinum": "Pt", "iridium": "Ir", "rhenium": "Re", "tungsten": "W",
    "neon": "Ne", "argon": "Ar", "diamond": "C", "graphite": "C",
    "alumina": "Al2O3", "magnesia": "MgO", "periclase": "MgO",
    "hematite": "Fe2O3", "boron carbide": "B4C",
}


class EosDatabaseDialog(QtWidgets.QDialog):
    """
    Compact dialog for browsing the EoS material database and loading
    a selected material as a Dioptas phase.
    """

    def __init__(self, parent=None, api_url: str = "http://localhost:8000"):
        super().__init__(parent)
        self.setWindowTitle("EoS Material Database")
        self.setMinimumSize(680, 520)
        self.setModal(True)

        self._api_url = api_url
        self._client = None
        self._EoSClientError = None
        self._materials = []
        self._current_material = None
        self._eos_list = []

        self._create_widgets()
        self._create_layout()
        self._connect_signals()
        self._try_connect()

    # ------------------------------------------------------------------
    # Widget creation
    # ------------------------------------------------------------------

    def _create_widgets(self):
        # Connection bar
        self.api_url_input = QtWidgets.QLineEdit(self._api_url)
        self.api_url_input.setPlaceholderText("http://localhost:8000")
        self.api_url_input.setMaximumWidth(240)
        self.connect_btn = FlatButton("Connect")
        self.status_lbl = QtWidgets.QLabel("Connecting…")
        self.status_lbl.setStyleSheet("color: gray; font-style: italic;")

        # Search bar
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText(
            "Search: Au, Fe, MgO, gold, iron, alumina…"
        )
        self.search_btn = FlatButton("Search")
        self.all_btn = FlatButton("All")

        # Materials table
        # Note: lattice angles (α/β/γ) are intentionally not shown here —
        # they vary with pressure/temperature via the EoS, and are only
        # meaningful once a phase is loaded into Dioptas' own phase editor.
        self.materials_table = QtWidgets.QTableWidget()
        self.materials_table.setColumnCount(2)
        self.materials_table.setHorizontalHeaderLabels(["Material", "Space Group"])
        self.materials_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.materials_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.materials_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.materials_table.verticalHeader().setVisible(False)
        self.materials_table.horizontalHeader().setStretchLastSection(True)
        self.materials_table.setAlternatingRowColors(True)

        # EOS table
        self.eos_table = QtWidgets.QTableWidget()
        self.eos_table.setColumnCount(5)
        self.eos_table.setHorizontalHeaderLabels(
            ["Type", "Reference", "K0 (GPa)", "K0′", "V0 (Å³)"]
        )
        self.eos_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.eos_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.eos_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.eos_table.verticalHeader().setVisible(False)
        self.eos_table.horizontalHeader().setStretchLastSection(True)

        # Verification result
        self.verify_lbl = QtWidgets.QLabel("")
        self.verify_lbl.setWordWrap(True)
        self.verify_btn = FlatButton("Verify with Peritheos")
        self.verify_btn.setEnabled(False)
        self.verify_btn.setToolTip(
            "Calculate a test pressure via the Peritheos EoS engine\n"
            "and compare with stored parameters"
        )

        # Format selector
        self.fmt_jcpds_rb = QtWidgets.QRadioButton("JCPDS")
        self.fmt_eosmat_rb = QtWidgets.QRadioButton("Save as .eosmat")
        self.fmt_jcpds_rb.setChecked(True)
        self.fmt_group = QtWidgets.QButtonGroup()
        self.fmt_group.addButton(self.fmt_jcpds_rb)
        self.fmt_group.addButton(self.fmt_eosmat_rb)

        # Action buttons
        self.load_btn = QtWidgets.QPushButton("Load as Phase")
        self.load_btn.setEnabled(False)
        self.load_btn.setDefault(True)
        self.close_btn = QtWidgets.QPushButton("Close")

    def _create_layout(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # — Connection row —
        conn_row = QtWidgets.QHBoxLayout()
        conn_row.addWidget(QtWidgets.QLabel("API:"))
        conn_row.addWidget(self.api_url_input)
        conn_row.addWidget(self.connect_btn)
        conn_row.addWidget(self.status_lbl, 1)
        root.addLayout(conn_row)

        root.addWidget(HorizontalLine())

        # — Search row —
        search_row = QtWidgets.QHBoxLayout()
        search_row.addWidget(self.search_input, 1)
        search_row.addWidget(self.search_btn)
        search_row.addWidget(self.all_btn)
        root.addLayout(search_row)

        # — Materials table —
        root.addWidget(QtWidgets.QLabel("Materials:"))
        root.addWidget(self.materials_table, 3)

        # — EOS table —
        root.addWidget(QtWidgets.QLabel("Equation of State Parameters:"))
        root.addWidget(self.eos_table, 2)

        # — Verify row —
        verify_row = QtWidgets.QHBoxLayout()
        verify_row.addWidget(self.verify_btn)
        verify_row.addWidget(self.verify_lbl, 1)
        root.addLayout(verify_row)

        root.addWidget(HorizontalLine())

        # — Bottom bar: format + buttons —
        bottom = QtWidgets.QHBoxLayout()
        bottom.addWidget(QtWidgets.QLabel("Save format:"))
        bottom.addWidget(self.fmt_jcpds_rb)
        bottom.addWidget(self.fmt_eosmat_rb)
        bottom.addStretch()
        bottom.addWidget(self.load_btn)
        bottom.addWidget(self.close_btn)
        root.addLayout(bottom)

    def _connect_signals(self):
        self.connect_btn.clicked.connect(self._on_connect)
        self.api_url_input.returnPressed.connect(self._on_connect)
        self.search_btn.clicked.connect(self._on_search)
        self.search_input.returnPressed.connect(self._on_search)
        self.all_btn.clicked.connect(self._on_load_all)
        self.materials_table.selectionModel().selectionChanged.connect(
            self._on_material_selected
        )
        self.verify_btn.clicked.connect(self._on_verify)
        self.load_btn.clicked.connect(self._on_load)
        self.close_btn.clicked.connect(self.reject)

    # ------------------------------------------------------------------
    # Stored result (read by PhaseController after exec_())
    # ------------------------------------------------------------------

    #: Set by _on_load; tuple (jcpds_obj, filename_str) or None
    result_phase = None

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _try_connect(self):
        """Attempt auto-connect on open."""
        self._on_connect()

    def _on_connect(self):
        url = self.api_url_input.text().strip() or "http://localhost:8000"
        try:
            from ..eos_client import EoSClient, EoSClientError
            self._EoSClientError = EoSClientError
            self._client = EoSClient(url)
            self._client.list_materials(limit=1)           # connectivity check
            self._set_status(f"Connected: {url}", "green")
            self._on_load_all()
        except Exception as e:
            self._client = None
            self._set_status(f"Connection failed: {e}", "red")

    def _on_search(self):
        if not self._check_connected():
            return
        raw = self.search_input.text().strip()
        if not raw:
            self._on_load_all()
            return
        # Expand common name → formula
        query = _ELEMENT_ALIASES.get(raw.lower(), raw)
        try:
            self._materials = self._client.search_material(query)
            self._fill_materials(self._materials)
        except Exception as e:
            self._show_err("Search failed", e)

    def _on_load_all(self):
        if not self._check_connected():
            return
        try:
            self._materials = self._client.list_materials(limit=200)
            self._fill_materials(self._materials)
        except Exception as e:
            self._show_err("Could not load materials", e)

    def _on_material_selected(self):
        rows = self.materials_table.selectionModel().selectedRows()
        self._clear_eos()
        self.verify_lbl.setText("")
        if not rows or not self._check_connected(silent=True):
            return
        row = rows[0].row()
        if row >= len(self._materials):
            return
        try:
            mat_id = self._materials[row]["id"]
            self._current_material = self._client.get_material(mat_id)
            self._eos_list = self._client.list_eos(material_id=mat_id)
            self._fill_eos(self._eos_list)
            self.load_btn.setEnabled(True)
            self.verify_btn.setEnabled(bool(self._eos_list))
        except Exception as e:
            self._show_err("Could not load material", e)

    def _on_verify(self):
        """Call the database's Peritheos-backed calculate endpoint and show result."""
        eos = self._selected_eos()
        if eos is None:
            return
        v0 = eos.get("v0")
        if not v0:
            self.verify_lbl.setText("V0 not available for this EoS.")
            return
        test_volume = float(v0) * 0.95      # 5 % compression
        try:
            p = self._client.calculate_pressure(
                eos["id"], volume=test_volume, temperature=298.15
            )
            self.verify_lbl.setText(
                f"✓ Peritheos: V = {test_volume:.3f} Å³ (0.95 V₀)  →  P = {p:.2f} GPa"
            )
            self.verify_lbl.setStyleSheet("color: green;")
        except Exception as e:
            self.verify_lbl.setText(f"Verification error: {e}")
            self.verify_lbl.setStyleSheet("color: red;")

    def _on_load(self):
        if self._current_material is None:
            return
        eos = self._selected_eos()
        try:
            from ..eos_formats import build_jcpds, write_eosmat
            jcpds_obj = build_jcpds(self._current_material, eos)

            if self.fmt_eosmat_rb.isChecked():
                name = (
                    self._current_material.get("name")
                    or self._current_material.get("formula", "material")
                )
                dest, _ = QtWidgets.QFileDialog.getSaveFileName(
                    self,
                    "Save .eosmat material file",
                    f"{name}.eosmat",
                    "EoS material (*.eosmat);;All files (*)",
                )
                if dest:
                    write_eosmat(dest, self._current_material, eos)

            # Always hand back a phase
            self.result_phase = (jcpds_obj, jcpds_obj._filename)
            self.accept()
        except Exception as e:
            self._show_err("Load failed", e)

    # ------------------------------------------------------------------
    # Table helpers
    # ------------------------------------------------------------------

    def _fill_materials(self, materials):
        t = self.materials_table
        t.setRowCount(len(materials))
        for r, m in enumerate(materials):
            name = m.get("name", "")
            formula = m.get("formula", "")
            # Name and formula are the same concept for most entries — only
            # show both when they actually differ (e.g. "Gold (Au)").
            label = name if name == formula or not formula else f"{name} ({formula})"
            t.setItem(r, 0, QtWidgets.QTableWidgetItem(label))
            t.setItem(r, 1, QtWidgets.QTableWidgetItem(m.get("symmetry", "")))
        t.resizeColumnsToContents()

    def _fill_eos(self, eos_list):
        t = self.eos_table
        t.setRowCount(len(eos_list))
        for r, e in enumerate(eos_list):
            t.setItem(r, 0, QtWidgets.QTableWidgetItem(e.get("eos_type", "")))
            t.setItem(r, 1, QtWidgets.QTableWidgetItem(e.get("reference") or ""))
            k0 = e.get("k0")
            t.setItem(r, 2, QtWidgets.QTableWidgetItem(
                f"{k0:.1f}" if k0 is not None else ""
            ))
            k0p = e.get("k0_prime")
            t.setItem(r, 3, QtWidgets.QTableWidgetItem(
                f"{k0p:.2f}" if k0p is not None else ""
            ))
            v0 = e.get("v0")
            t.setItem(r, 4, QtWidgets.QTableWidgetItem(
                f"{v0:.3f}" if v0 is not None else ""
            ))
        t.resizeColumnsToContents()
        if eos_list:
            t.selectRow(0)

    def _clear_eos(self):
        self.eos_table.setRowCount(0)
        self.load_btn.setEnabled(False)
        self.verify_btn.setEnabled(False)
        self._eos_list = []
        self._current_material = None

    def _selected_eos(self):
        rows = self.eos_table.selectionModel().selectedRows()
        if rows and rows[0].row() < len(self._eos_list):
            return self._eos_list[rows[0].row()]
        return self._eos_list[0] if self._eos_list else None

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _set_status(self, text, color="gray"):
        self.status_lbl.setText(text)
        self.status_lbl.setStyleSheet(f"color: {color}; font-style: italic;")

    def _check_connected(self, silent=False):
        if self._client is None:
            if not silent:
                QtWidgets.QMessageBox.information(
                    self, "Not Connected",
                    "Enter the API URL and press Connect first."
                )
            return False
        return True

    def _show_err(self, title, exc):
        logger.error("%s: %s", title, exc)
        QtWidgets.QMessageBox.warning(self, title, str(exc))
