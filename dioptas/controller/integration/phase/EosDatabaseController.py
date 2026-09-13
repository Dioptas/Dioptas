# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
"""
Controller for the EoS material database browser dialog. Owns the
dialog's content and behavior: loading Peritheos's library, filtering,
showing a material's EoS records, exporting .eosmat files, and building
the jcpds phase the user asked to load.
"""

import logging
from pathlib import Path

from qtpy import QtCore, QtWidgets

from ....model import eos
from ....model.util.phasesmith import material_has_diffraction_data
from ....widgets.EosDatabaseDialog import EosDatabaseDialog

logger = logging.getLogger(__name__)


class EosDatabaseController(object):

    RECENT_LIMIT = 20

    def __init__(
        self,
        parent_widget=None,
        *,
        minimum_d_spacing: float = 0.5,
        wavelength_angstrom: float = 0.31,
        settings=None,
    ):
        self.dialog = EosDatabaseDialog(parent_widget)
        self.minimum_d_spacing = minimum_d_spacing
        self.wavelength_angstrom = wavelength_angstrom
        self.materials = eos.load_materials()
        self.settings = settings if settings is not None else QtCore.QSettings(
            str(Path.home() / ".Dioptas" / "eos_browser.ini"),
            QtCore.QSettings.IniFormat,
        )
        self.recent_ids = self._read_ids("recent")[:self.RECENT_LIMIT]
        self.favourite_ids = set(self._read_ids("favourites"))
        self.shown_materials = []
        self._view_before_search = None
        #: jcpds object built when the user clicks "Load as Phase"
        self.result_phase = None

        self.dialog.search_changed.connect(self.search)
        self.dialog.material_selected.connect(self.show_material)
        self.dialog.load_clicked.connect(self.load)
        self.dialog.export_clicked.connect(self.export)
        self.dialog.view_changed.connect(self.change_view)
        self.dialog.favourite_clicked.connect(self.toggle_favourite)

        self._refresh_materials()

    def exec_(self):
        """
        Show the dialog modally; returns the built jcpds object when the
        user loaded a material, else None.
        """
        self.dialog.exec_()
        return self.result_phase

    def search(self, query: str):
        # Start a new search across the library, but let subsequent tab
        # clicks narrow it without discarding the query.
        tabs = self.dialog.view_tabs
        if query.strip() and self._view_before_search is None:
            self._view_before_search = tabs.currentIndex()
            with QtCore.QSignalBlocker(tabs):
                tabs.setCurrentIndex(2)
        elif not query.strip() and self._view_before_search is not None:
            with QtCore.QSignalBlocker(tabs):
                tabs.setCurrentIndex(self._view_before_search)
            self._view_before_search = None
        self._refresh_materials()

    def change_view(self, view):
        if self._view_before_search is not None:
            # Clearing the query should keep a view explicitly chosen
            # during the search.
            self._view_before_search = view
        self._refresh_materials()

    def _read_ids(self, key):
        value = self.settings.value(key, [])
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, (list, tuple)):
            return []
        known_ids = {material.identifier for material in self.materials}
        return list(dict.fromkeys(
            identifier for identifier in value
            if isinstance(identifier, str) and identifier in known_ids))

    def _refresh_materials(self, *_):
        query = self.dialog.search_input.text().strip()
        view = self.dialog.view_tabs.currentIndex()
        if view == 2:
            self.shown_materials = list(self.materials)
            empty_message = "No materials match your search."
        elif view == 1:
            self.shown_materials = [
                material for material in self.materials
                if material.identifier in self.favourite_ids]
            empty_message = (
                "No favourites yet. Search or choose All, then select a "
                "material and click ☆ Favourite.")
        else:
            by_id = {material.identifier: material for material in self.materials}
            self.shown_materials = [by_id[key] for key in self.recent_ids
                                    if key in by_id]
            empty_message = (
                "No recently used materials yet. Search or choose All to "
                "load a phase; your last 20 materials will appear here.")
        if query:
            self.shown_materials = eos.search_materials(query, self.shown_materials)
            empty_message = "No materials in this view match your search."
        self.dialog.set_materials_summary(
            len(self.shown_materials), bool(query), empty_message)
        self._fill_materials()

    def show_material(self, row: int):
        material = self._selected_material(row)
        self.dialog.set_favourite(
            material is not None,
            material is not None and material.identifier in self.favourite_ids)
        if material is None:
            self.dialog.fill_eos_records([])
            return
        self.dialog.fill_eos_records([
            _record_row(record) for record in material.eos_records],
            selected_row=material.default_eos_index,
            reference_tooltips=[
                eos.reference_text(record.get("reference"))
                for record in material.eos_records
            ],
            thermal_tooltips=[
                _thermal_tooltip(record) for record in material.eos_records
            ])
        self.dialog.set_phase_load_enabled(
            material_has_diffraction_data(material))

    def toggle_favourite(self):
        row = self.dialog.selected_material_row()
        material = self._selected_material(row)
        if material is None:
            return
        identifier = material.identifier
        if identifier in self.favourite_ids:
            self.favourite_ids.remove(identifier)
        else:
            self.favourite_ids.add(identifier)
        self.settings.setValue("favourites", sorted(self.favourite_ids))
        self.settings.sync()
        if self.dialog.view_tabs.currentIndex() == 1:
            self._refresh_materials()
        else:
            self.dialog.set_favourite(True, identifier in self.favourite_ids)

    def load(self):
        material = self._selected_material(self.dialog.selected_material_row())
        if material is None or not material_has_diffraction_data(material):
            return
        record_index = self.dialog.selected_eos_row()
        if record_index < 0:
            record_index = material.default_eos_index
        self.result_phase = eos.build_jcpds(
            material,
            record_index,
            minimum_d_spacing=self.minimum_d_spacing,
            wavelength_angstrom=self.wavelength_angstrom,
            origin="bundled",
        )
        self.recent_ids = [material.identifier] + [
            key for key in self.recent_ids if key != material.identifier]
        self.recent_ids = self.recent_ids[:self.RECENT_LIMIT]
        self.settings.setValue("recent", self.recent_ids)
        self.settings.sync()
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
            (material.display_name, material.space_group)
            for material in self.shown_materials])
        # Select the first hit so the EoS table below always reflects the
        # current material list — never a previous search's selection.
        if self.shown_materials:
            self.dialog.materials_table.selectRow(0)
        else:
            self.show_material(-1)

    def _selected_material(self, row: int):
        if 0 <= row < len(self.shown_materials):
            return self.shown_materials[row]
        return None


def _record_row(record: dict) -> tuple:
    """One EoS table row, including source-reported parameter errors."""
    eos_block = record.get("eos") or {}
    parameters = eos_block.get("parameters") or {}
    if ("K0_prime" not in parameters
            and eos_block.get("type") == "BM2"):
        k0p_text = "4 (fixed)"
    else:
        k0p_text = _parameter_text(record, "K0_prime", ".2f")
    return (
        eos_block.get("type") or "",
        "✓" if (record.get("thermal") or {}).get("type") else "—",
        eos.reference_authors(record.get("reference")),
        eos.reference_year(record.get("reference")),
        eos.record_pressure_range(record),
        _parameter_text(record, "K0", ".1f"),
        k0p_text,
        _parameter_text(record, "V0", ".3f"),
    )


def _thermal_tooltip(record: dict) -> str:
    """Explain the thermal indicator without crowding the table."""
    thermal_type = (record.get("thermal") or {}).get("type")
    if not thermal_type:
        return "No thermal model"
    names = {
        "AlphaKT": "Constant α / dK/dT correction",
        "MieGruneisenDebye": "Mie–Grüneisen–Debye model",
        "MieGruneisenEinstein": "Mie–Grüneisen–Einstein model",
        "Sokolova2016": "Sokolova et al. (2016) thermal model",
        "LinearThermalPressure": "Linear thermal-pressure model",
        "LogVolumeThermalPressure": "Log-volume thermal-pressure model",
        "DoubleDebyeHelmholtz": "Double-Debye Helmholtz model",
    }
    return names.get(thermal_type, thermal_type)


def _parameter_text(record: dict, name: str, value_format: str) -> str:
    """Format a parameter, distinguishing errors, fixed values and gaps."""
    parameters = ((record.get("eos") or {}).get("parameters") or {})
    if name not in parameters:
        return ""

    text = format(parameters[name], value_format)
    errors = record.get("parameter_errors") or {}
    fixed = name in (record.get("fixed_parameters") or [])
    error = errors.get(name)
    if error is not None:
        text += f" ± {error:g}"
    elif not fixed:
        text += " (error n/r)"
    if fixed:
        text += " (fixed)"
    return text
