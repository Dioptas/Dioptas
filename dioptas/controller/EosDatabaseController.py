# SPDX-License-Identifier: MIT

import logging

from qtpy import QtWidgets

logger = logging.getLogger(__name__)


class EosDatabaseController:
    """
    Controller for the EoS database panel.

    Connects to a running eos_database API, lets the user browse materials,
    and loads the selected material as a Dioptas phase.
    """

    def __init__(self, widget, model):
        self.widget = widget
        self.model = model

        self._client = None
        self._EoSClientError = None
        self._materials = []       # list of material dicts from last query
        self._current_material = None  # full material dict (with peaks)
        self._eos_list = []        # EoS records for selected material

        self._connect_signals()

    # ------------------------------------------------------------------
    # Activation / deactivation (called by MainController when switching modes)
    # ------------------------------------------------------------------

    def activate(self):
        pass

    def deactivate(self):
        pass

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self):
        self.widget.connect_btn.clicked.connect(self._on_connect)
        self.widget.search_btn.clicked.connect(self._on_search)
        self.widget.search_input.returnPressed.connect(self._on_search)
        self.widget.load_all_btn.clicked.connect(self._on_load_all)
        self.widget.materials_table.selectionModel().selectionChanged.connect(
            self._on_material_selected
        )
        self.widget.eos_table.selectionModel().selectionChanged.connect(
            self._on_eos_selected
        )
        self.widget.load_phase_btn.clicked.connect(self._on_load_phase)
        self.widget.clear_btn.clicked.connect(self._on_clear)

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _on_connect(self):
        base_url = self.widget.api_url_input.text().strip() or "http://localhost:8000"
        try:
            from ..eos_client import EoSClient, EoSClientError
            self._EoSClientError = EoSClientError
            self._client = EoSClient(base_url)
            # Quick connectivity test
            self._client.list_materials(limit=1)
            self.widget.status_lbl.setText(f"Connected: {base_url}")
            self.widget.status_lbl.setStyleSheet("color: green;")
            logger.info("Connected to EoS database at %s", base_url)
            self._on_load_all()
        except Exception as e:
            self._client = None
            msg = str(e)
            self.widget.status_lbl.setText(f"Connection failed: {msg}")
            self.widget.status_lbl.setStyleSheet("color: red;")
            logger.error("EoS database connection failed: %s", msg)
            QtWidgets.QMessageBox.warning(
                self.widget,
                "Connection Error",
                f"Could not connect to EoS database at {base_url}:\n\n{msg}",
            )

    def _on_search(self):
        if not self._assert_connected():
            return
        query = self.widget.search_input.text().strip()
        if not query:
            self._on_load_all()
            return
        try:
            materials = self._client.search_material(query)
            self._materials = materials
            self._populate_materials_table(materials)
        except Exception as e:
            self._show_error("Search failed", e)

    def _on_load_all(self):
        if not self._assert_connected():
            return
        try:
            materials = self._client.list_materials(limit=200)
            self._materials = materials
            self._populate_materials_table(materials)
        except Exception as e:
            self._show_error("Could not load materials", e)

    def _on_material_selected(self):
        rows = self.widget.materials_table.selectionModel().selectedRows()
        if not rows or not self._assert_connected():
            self._clear_eos_panel()
            return
        row = rows[0].row()
        if row >= len(self._materials):
            return
        material_summary = self._materials[row]
        try:
            # Fetch full record (includes diffraction peaks)
            self._current_material = self._client.get_material(material_summary["id"])
            self._eos_list = self._client.list_eos(material_id=material_summary["id"])
            self._populate_eos_table(self._eos_list)
            self._update_detail_label(self._current_material)
            self.widget.load_phase_btn.setEnabled(True)
        except Exception as e:
            self._show_error("Could not load material details", e)

    def _on_eos_selected(self):
        pass  # reserved for future EoS-specific actions

    def _on_load_phase(self):
        """Build a jcpds object from the database material and add it as a phase."""
        if self._current_material is None:
            return

        # Pick EoS parameters if one is selected; otherwise use the first available
        eos = None
        rows = self.widget.eos_table.selectionModel().selectedRows()
        if rows and rows[0].row() < len(self._eos_list):
            eos = self._eos_list[rows[0].row()]
        elif self._eos_list:
            eos = self._eos_list[0]

        try:
            jcpds_obj = self._build_jcpds(self._current_material, eos)
            self.model.phase_model.add_jcpds_object(jcpds_obj)
            name = self._current_material.get("name") or self._current_material.get("formula", "material")
            logger.info("Loaded phase from EoS database: %s", name)
        except Exception as e:
            self._show_error("Could not load phase", e)

    def _on_clear(self):
        self.widget.materials_table.setRowCount(0)
        self.widget.search_input.clear()
        self._clear_eos_panel()
        self._materials = []
        self._current_material = None

    # ------------------------------------------------------------------
    # Table population helpers
    # ------------------------------------------------------------------

    def _populate_materials_table(self, materials):
        table = self.widget.materials_table
        table.setRowCount(len(materials))
        for row, mat in enumerate(materials):
            table.setItem(row, 0, QtWidgets.QTableWidgetItem(mat.get("name", "")))
            table.setItem(row, 1, QtWidgets.QTableWidgetItem(mat.get("formula", "")))
            table.setItem(row, 2, QtWidgets.QTableWidgetItem(mat.get("symmetry", "")))
        table.resizeColumnsToContents()

    def _populate_eos_table(self, eos_list):
        table = self.widget.eos_table
        table.setRowCount(len(eos_list))
        for row, eos in enumerate(eos_list):
            table.setItem(row, 0, QtWidgets.QTableWidgetItem(eos.get("eos_type", "")))
            table.setItem(row, 1, QtWidgets.QTableWidgetItem(eos.get("reference", "") or ""))
            k0 = eos.get("k0")
            table.setItem(row, 2, QtWidgets.QTableWidgetItem(f"{k0:.1f}" if k0 is not None else ""))
            k0p = eos.get("k0_prime")
            table.setItem(row, 3, QtWidgets.QTableWidgetItem(f"{k0p:.2f}" if k0p is not None else ""))
            v0 = eos.get("v0")
            table.setItem(row, 4, QtWidgets.QTableWidgetItem(f"{v0:.3f}" if v0 is not None else ""))
        table.resizeColumnsToContents()
        if eos_list:
            table.selectRow(0)

    def _update_detail_label(self, material):
        a = material.get("a", "")
        b = material.get("b", "")
        c = material.get("c", "")
        sym = material.get("symmetry", "")
        peaks = material.get("diffraction_peaks", [])
        self.widget.detail_lbl.setText(
            f"a={a} Å  b={b} Å  c={c} Å   |   {sym}   |   {len(peaks)} diffraction peaks"
        )

    def _clear_eos_panel(self):
        self.widget.eos_table.setRowCount(0)
        self.widget.detail_lbl.setText("")
        self.widget.load_phase_btn.setEnabled(False)
        self._eos_list = []

    # ------------------------------------------------------------------
    # jcpds object builder
    # ------------------------------------------------------------------

    def _build_jcpds(self, material, eos=None):
        """Construct a Dioptas jcpds object from database records."""
        from ..model.util.jcpds import jcpds, jcpds_reflection

        obj = jcpds()
        name = material.get("name") or material.get("formula", "unknown")
        obj._name = name
        obj._filename = f"<EoS DB: {name}>"

        obj.params["symmetry"] = (material.get("symmetry") or "").upper()
        obj.params["a0"] = float(material.get("a") or 0)
        obj.params["b0"] = float(material.get("b") or 0) or obj.params["a0"]
        obj.params["c0"] = float(material.get("c") or 0) or obj.params["a0"]
        obj.params["alpha0"] = float(material.get("alpha") or 90)
        obj.params["beta0"] = float(material.get("beta") or 90)
        obj.params["gamma0"] = float(material.get("gamma") or 90)

        # Mirror to current lattice params
        for suffix in ("a", "b", "c", "alpha", "beta", "gamma"):
            obj.params[suffix] = obj.params[f"{suffix}0"]

        if eos:
            obj.params["k0"] = float(eos.get("k0") or 0)
            obj.params["k0p0"] = float(eos.get("k0_prime") or 0)
            obj.params["k0p"] = obj.params["k0p0"]
            obj.params["alpha_t0"] = float(eos.get("alpha0") or 0)
            obj.params["dk0dt"] = float(eos.get("dK_dT") or 0)
            v0 = eos.get("v0")
            if v0:
                obj.params["v0"] = float(v0)
                obj.params["v"] = float(v0)

        for peak in material.get("diffraction_peaks", []):
            refl = jcpds_reflection(
                h=int(peak.get("h", 0)),
                k=int(peak.get("k", 0)),
                l=int(peak.get("l", 0)),
                intensity=float(peak.get("intensity", 0)),
                d=float(peak.get("d_spacing", 0)),
            )
            obj.reflections.append(refl)

        obj.params["modified"] = False
        return obj

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _assert_connected(self):
        if self._client is None:
            QtWidgets.QMessageBox.information(
                self.widget,
                "Not Connected",
                "Please enter the API URL and press Connect first.",
            )
            return False
        return True

    def _show_error(self, title, exc):
        logger.error("%s: %s", title, exc)
        QtWidgets.QMessageBox.warning(self.widget, title, str(exc))
