# -*- coding: utf-8 -*-
"""
Tests for the EoS database browser: the controller drives the (dumb)
dialog, search filters the bundled materials, and loading builds a jcpds
phase carrying the full reference-switcher state.
"""
import gc
from functools import cmp_to_key
from unittest.mock import patch

from qtpy import QtCore, QtWidgets
from qtpy.QtTest import QTest

from ..utility import QtTest

from ...controller.integration.phase.EosDatabaseController import (
    EosDatabaseController, _record_row)
from ...model import eos


class EosDatabaseControllerTest(QtTest):
    def setUp(self):
        self.controller = EosDatabaseController()
        self.dialog = self.controller.dialog

    def tearDown(self):
        self.dialog.close()
        del self.controller
        gc.collect()

    def test_all_materials_shown_on_open(self):
        assert (self.dialog.materials_table.rowCount()
                == len(eos.load_materials()))

    def test_material_headers_sort_and_keep_selection_attached_to_material(self):
        self.dialog.search_input.setText("Mg")
        self.dialog.show()
        QtWidgets.QApplication.processEvents()
        table = self.dialog.materials_table
        selected = self.dialog.selected_material_row()
        header = table.horizontalHeader()
        collator = QtCore.QCollator()
        for column in (0, 1):
            position = QtCore.QPoint(
                header.sectionViewportPosition(column)
                + header.sectionSize(column) // 2, header.height() // 2)
            for _ in range(2):
                QTest.mouseClick(header.viewport(), QtCore.Qt.LeftButton,
                                 pos=position)
                values = [table.item(row, column).text()
                          for row in range(table.rowCount())]
                descending = header.sortIndicatorOrder() == QtCore.Qt.DescendingOrder
                assert values == sorted(values, key=cmp_to_key(collator.compare),
                                        reverse=descending)
                assert self.dialog.selected_material_row() == selected

        table.selectRow(0)
        material = self.controller.shown_materials[self.dialog.selected_material_row()]
        assert table.item(0, 0).text() == material.display_name
        assert self.dialog.eos_table.rowCount() == len(material.eos_records)
        with patch.object(QtWidgets.QFileDialog, "getSaveFileName",
                          return_value=("selected.eosmat", "")), \
                patch.object(eos, "save_material_file") as save:
            self.dialog.export_btn.click()
        save.assert_called_once_with("selected.eosmat", material)

    def test_sorted_tables_refill_without_mixing_rows_and_load_selected_record(self):
        self.dialog.materials_table.sortItems(0, QtCore.Qt.DescendingOrder)
        self.dialog.eos_table.sortItems(5, QtCore.Qt.DescendingOrder)
        for query in ("gold", "silver", "Mg", "gold"):
            self.dialog.search_input.setText(query)
            table = self.dialog.materials_table
            for row in range(table.rowCount()):
                table.selectRow(row)
                material = self.controller.shown_materials[self.dialog.selected_material_row()]
                assert table.item(row, 0).text() == material.display_name
                assert self.dialog.selected_eos_row() == material.default_eos_index
                records = self.dialog.eos_table
                for record_row in range(records.rowCount()):
                    records.selectRow(record_row)
                    record = material.eos_records[self.dialog.selected_eos_row()]
                    assert tuple(records.item(record_row, c).text()
                                 for c in range(8)) == _record_row(record)

        records.selectRow(0)
        record_index = self.dialog.selected_eos_row()
        with patch.object(eos, "build_jcpds") as build:
            records.doubleClicked.emit(records.model().index(0, 0))
        assert build.call_args.args == (material, record_index)

    def test_eos_headers_sort_formatted_values_numerically(self):
        self.dialog.search_input.setText("gold")
        self.dialog.fill_eos_records([
            ("Vinet", "—", "A", "2000", "100–200 GPa",
             "100.0 ± 2", "10.00 (fixed)", "100.000 (error n/r)"),
            ("BM3", "✓", "B", "1999", "9–80 GPa",
             "9.0 (error n/r)", "2.00 ± 0.1", "9.000 ± 0.2"),
        ])
        self.dialog.show()
        QtWidgets.QApplication.processEvents()
        table = self.dialog.eos_table
        header = table.horizontalHeader()
        for column in range(3, 8):
            position = QtCore.QPoint(
                header.sectionViewportPosition(column)
                + header.sectionSize(column) // 2, header.height() // 2)
            for _ in range(2):
                QTest.mouseClick(header.viewport(), QtCore.Qt.LeftButton,
                                 pos=position)
                descending = header.sortIndicatorOrder() == QtCore.Qt.DescendingOrder
                assert table.item(0, 0).text() == ("Vinet" if descending else "BM3")
                assert self.dialog.selected_eos_row() == 0

    def test_search_filters_and_alias_works(self):
        self.dialog.search_input.setText("gold")
        rows = self.dialog.materials_table.rowCount()
        assert 1 <= rows < len(eos.load_materials())
        assert "Au" in self.dialog.materials_table.item(0, 0).text()

        self.dialog.clear_btn.click()
        assert (self.dialog.materials_table.rowCount()
                == len(eos.load_materials()))

    def test_material_table_displays_space_group_not_crystal_system(self):
        self.dialog.search_input.setText("gold")
        material = self.controller.shown_materials[0]

        assert material.space_group == "Fm-3m"
        assert self.dialog.materials_table.item(0, 1).text() == "Fm-3m"
        assert self.dialog.materials_table.item(0, 1).text() != material.symmetry

    def test_material_table_displays_screw_axis_as_subscript(self):
        self.dialog.search_input.setText("alpha quartz")
        row = next(
            index
            for index, material in enumerate(self.controller.shown_materials)
            if material.name == "Alpha quartz"
        )

        assert self.controller.shown_materials[row].space_group == "P3221"
        assert self.dialog.materials_table.item(row, 1).text() == "P3\u208221"

    def test_material_table_keeps_missing_space_group_blank(self):
        self.dialog.fill_materials([("Legacy material", "")])

        assert self.dialog.materials_table.item(0, 1).text() == ""

    def test_h2o_search_shows_water_ice_but_not_heavy_water(self):
        self.dialog.search_input.setText("H2O")

        names = {material.name for material in self.controller.shown_materials}
        assert {"Ice VI", "Ice VII"} <= names
        assert "Ice VIII (D2O)" not in names

    def test_formula_subset_search_finds_solid_solution(self):
        self.dialog.search_input.setText("MgFe")

        formulas = {
            material.formula for material in self.controller.shown_materials
        }
        assert "Mg0.4Fe0.6O" in formulas

    def test_single_search_result_keeps_material_table_full_width(self):
        self.dialog.resize(680, 520)
        self.dialog.show()
        QtWidgets.QApplication.processEvents()

        self.dialog.search_input.setText("gold")

        table = self.dialog.materials_table
        header = table.horizontalHeader()
        assert table.rowCount() == 1
        assert header.length() == table.viewport().width()

    def test_fit_pressure_header_is_measured_in_painted_uppercase(self):
        # The application theme paints headers uppercase. Supplying this one
        # as mixed case makes Qt size it too narrowly before that transform.
        item = self.dialog.eos_table.horizontalHeaderItem(4)
        assert item.text() == "FIT P RANGE"

    def test_reference_and_fit_range_share_available_width(self):
        self.dialog.resize(680, 520)
        self.dialog.show()
        QtWidgets.QApplication.processEvents()

        table = self.dialog.eos_table
        assert abs(table.columnWidth(2) - table.columnWidth(4)) <= 1

    def test_reference_has_separate_authors_and_year_columns(self):
        self.dialog.search_input.setText("silver")
        row = next(
            index for index, material in enumerate(self.controller.shown_materials)
            if material.formula == "Ag"
        )
        self.dialog.materials_table.selectRow(row)

        material = self.controller.shown_materials[row]
        reference = material.eos_records[0]["reference"]
        assert self.dialog.eos_table.item(0, 2).text() == "Dewaele et al."
        assert self.dialog.eos_table.item(0, 3).text() == "2008"
        assert (self.dialog.eos_table.item(0, 2).toolTip()
                == eos.reference_text(reference))

    def test_thermal_column_is_an_indicator_with_model_tooltip(self):
        self.dialog.search_input.setText("gold")
        self.dialog.materials_table.selectRow(0)

        table = self.dialog.eos_table
        assert table.horizontalHeaderItem(1).text() == "T"
        thermal_row = next(
            row for row, record in enumerate(
                self.controller.shown_materials[0].eos_records)
            if record.get("thermal", {}).get("type") == "LogVolumeThermalPressure"
        )
        assert table.item(thermal_row, 1).text() == "✓"
        assert table.item(thermal_row, 1).toolTip() == (
            "Log-volume thermal-pressure model"
        )

        record_without_thermal = next(
            row for row, record in enumerate(
                self.controller.shown_materials[0].eos_records
            )
            if not record.get("thermal")
        )
        assert table.item(record_without_thermal, 1).text() == "—"
        assert (table.item(record_without_thermal, 1).toolTip()
                == "No thermal model")

    def test_selecting_material_shows_eos_records(self):
        self.dialog.search_input.setText("gold")
        self.dialog.materials_table.selectRow(0)
        material = self.controller.shown_materials[0]
        assert (self.dialog.eos_table.rowCount()
                == len(material.eos_records))
        assert (self.dialog.selected_eos_row()
                == material.default_eos_index)
        assert self.dialog.load_btn.isEnabled()

    def test_load_builds_phase_with_selected_record(self):
        self.dialog.search_input.setText("gold")
        self.dialog.materials_table.selectRow(0)
        self.dialog.eos_table.selectRow(2)
        self.dialog.load_btn.click()

        phase = self.controller.result_phase
        assert phase is not None
        material = self.controller.shown_materials[0]
        assert phase.params["eos_current_index"] == 2
        assert (phase.params["k0"] == material.eos_records[2]
                ["eos"]["parameters"]["K0"])
        assert len(phase.params["eos_records"]) == len(material.eos_records)

    def test_double_clicking_material_loads_default_record(self):
        self.dialog.search_input.setText("gold")
        table = self.dialog.materials_table

        table.doubleClicked.emit(table.model().index(0, 0))

        assert self.controller.result_phase is not None
        assert self.controller.result_phase.params["eos_current_index"] == (
            self.controller.shown_materials[0].default_eos_index)

    def test_double_clicking_eos_record_loads_that_record(self):
        self.dialog.search_input.setText("gold")
        table = self.dialog.eos_table

        table.doubleClicked.emit(table.model().index(0, 0))

        assert self.controller.result_phase is not None
        assert self.controller.result_phase.params["eos_current_index"] == 0

    def test_new_search_refreshes_eos_records(self):
        # Regression: after clicking into the EoS table and searching
        # again, the previous selection's row index survived the refill
        # without firing selectionChanged, so the EoS table kept showing
        # the old material's records.
        self.dialog.search_input.setText("gold")
        self.dialog.eos_table.selectRow(0)   # user clicks into the viewer
        gold_rows = self.dialog.eos_table.rowCount()
        assert gold_rows > 0

        self.dialog.search_input.setText("silver")
        material = self.controller.shown_materials[0]
        assert material.formula == "Ag"
        assert (self.dialog.eos_table.rowCount()
                == len(material.eos_records))
        assert self.dialog.eos_table.rowCount() != gold_rows

    def test_eos_only_material_is_exportable_but_cannot_load_as_phase(self):
        from ...model.util.phasesmith import material_has_diffraction_data

        row = next(i for i, material in enumerate(self.controller.shown_materials)
                   if not material_has_diffraction_data(material))
        self.dialog.materials_table.selectRow(row)

        assert not self.dialog.load_btn.isEnabled()
        assert "No crystal structure" in self.dialog.load_btn.toolTip()
        assert self.dialog.export_btn.isEnabled()
        self.controller.load()
        self.dialog.materials_table.doubleClicked.emit(
            self.dialog.materials_table.model().index(row, 0))
        assert self.controller.result_phase is None

        self.dialog.search_input.setText("gold")
        assert self.dialog.load_btn.isEnabled()
        assert self.dialog.load_btn.toolTip() == ""


def test_record_row_displays_reported_errors_and_fixed_parameters():
    record = {
        "reference": "A publication",
        "eos": {
            "type": "Vinet",
            "parameters": {"V0": 47.2496, "K0": 395.0,
                           "K0_prime": 3.62},
        },
        "parameter_errors": {"V0": 0.0048, "K0": 2.0,
                             "K0_prime": None},
        "fixed_parameters": ["V0"],
        "experimental_pressure_range_gpa": [12.0, 80.5],
    }
    assert _record_row(record) == (
        "Vinet", "—", "A publication", "", "12–80.5 GPa", "395.0 ± 2",
        "3.62 (error n/r)",
        "47.250 ± 0.0048 (fixed)",
    )


def test_record_row_displays_implicit_bm2_derivative_as_fixed():
    record = {
        "eos": {"type": "BM2", "parameters": {"V0": 10.0, "K0": 20.0}},
        "parameter_errors": {"V0": None, "K0": 1.0},
        "fixed_parameters": [],
    }
    assert _record_row(record)[5:] == (
        "20.0 ± 1", "4 (fixed)", "10.000 (error n/r)",
    )
