# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
"""
Controller for the EoS material database browser dialog. Owns the
dialog's content and behavior: loading the bundled database, filtering,
showing a material's EoS records, exporting .eosmat files, and building
the jcpds phase the user asked to load.
"""

import logging

from qtpy import QtWidgets

from ....model import eos
from ....widgets.EosDatabaseDialog import EosDatabaseDialog

logger = logging.getLogger(__name__)


class EosDatabaseController(object):

    def __init__(self, parent_widget=None):
        self.dialog = EosDatabaseDialog(parent_widget)
        self.materials = eos.load_materials()
        self.shown_materials = list(self.materials)
        #: jcpds object built when the user clicks "Load as Phase"
        self.result_phase = None

        self.dialog.search_changed.connect(self.search)
        self.dialog.material_selected.connect(self.show_material)
        self.dialog.load_clicked.connect(self.load)
        self.dialog.export_clicked.connect(self.export)

        self._fill_materials()

    def exec_(self):
        """
        Show the dialog modally; returns the built jcpds object when the
        user loaded a material, else None.
        """
        self.dialog.exec_()
        return self.result_phase

    def search(self, query: str):
        self.shown_materials = eos.search_materials(query, self.materials)
        self._fill_materials()

    def show_material(self, row: int):
        material = self._selected_material(row)
        if material is None:
            self.dialog.fill_eos_records([])
            return
        self.dialog.fill_eos_records([
            _record_row(record) for record in material.eos_records])

    def load(self):
        material = self._selected_material(self.dialog.selected_material_row())
        if material is None:
            return
        record_index = max(0, self.dialog.selected_eos_row())
        self.result_phase = eos.build_jcpds(material, record_index)
        self.dialog.accept()

    def export(self):
        material = self._selected_material(self.dialog.selected_material_row())
        if material is None:
            return
        default_name = f"{material.formula or material.name}.eosmat"
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self.dialog, "Export .eosmat material file", default_name,
            "EoS material (*.eosmat);;All files (*)")
        if filename:
            eos.save_material_file(filename, material)

    def _fill_materials(self):
        self.dialog.fill_materials([
            (material.display_name, material.symmetry)
            for material in self.shown_materials])
        # Select the first hit so the EoS table below always reflects the
        # current material list — never a previous search's selection.
        if self.shown_materials:
            self.dialog.materials_table.selectRow(0)

    def _selected_material(self, row: int):
        if 0 <= row < len(self.shown_materials):
            return self.shown_materials[row]
        return None


def _record_row(record: dict) -> tuple:
    """One EoS table row: (type, reference, K0, K0', V0) as strings."""
    eos_block = record.get("eos") or {}
    parameters = eos_block.get("parameters") or {}
    k0 = parameters.get("K0")
    k0p = parameters.get("K0_prime")
    if k0p is None and eos_block.get("type") == "BM2":
        k0p_text = "4 (fixed)"
    else:
        k0p_text = f"{k0p:.2f}" if k0p is not None else ""
    v0 = parameters.get("V0")
    return (
        eos_block.get("type") or "",
        record.get("reference") or eos.record_label(record),
        f"{k0:.1f}" if k0 is not None else "",
        k0p_text,
        f"{v0:.3f}" if v0 is not None else "",
    )
