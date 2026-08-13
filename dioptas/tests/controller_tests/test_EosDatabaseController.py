# -*- coding: utf-8 -*-
"""
Tests for the EoS database browser: the controller drives the (dumb)
dialog, search filters the bundled materials, and loading builds a jcpds
phase carrying the full reference-switcher state.
"""
import gc

from qtpy import QtWidgets

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

    def test_search_filters_and_alias_works(self):
        self.dialog.search_input.setText("gold")
        rows = self.dialog.materials_table.rowCount()
        assert 1 <= rows < len(eos.load_materials())
        assert "Au" in self.dialog.materials_table.item(0, 0).text()

        self.dialog.clear_btn.click()
        assert (self.dialog.materials_table.rowCount()
                == len(eos.load_materials()))

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
        item = self.dialog.eos_table.horizontalHeaderItem(2)
        assert item.text() == "FIT P RANGE"

    def test_reference_and_fit_range_share_available_width(self):
        self.dialog.resize(680, 520)
        self.dialog.show()
        QtWidgets.QApplication.processEvents()

        table = self.dialog.eos_table
        assert abs(table.columnWidth(1) - table.columnWidth(2)) <= 1

    def test_selecting_material_shows_eos_records(self):
        self.dialog.search_input.setText("gold")
        self.dialog.materials_table.selectRow(0)
        material = self.controller.shown_materials[0]
        assert (self.dialog.eos_table.rowCount()
                == len(material.eos_records))
        assert (self.dialog.selected_eos_row()
                == material.default_eos_index == 1)
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
        assert self.controller.result_phase.params["eos_current_index"] == 1

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

        self.dialog.search_input.setText("diamond")
        material = self.controller.shown_materials[0]
        assert material.formula == "C"
        assert (self.dialog.eos_table.rowCount()
                == len(material.eos_records))
        assert self.dialog.eos_table.rowCount() != gold_rows

    def test_material_without_records_is_still_loadable(self):
        materials = eos.load_materials()
        material = next(
            m for m in materials
            if (not m.eos_records
                and len(eos.search_materials(m.name, materials)) == 1)
        )
        self.dialog.search_input.setText(material.name)
        self.dialog.materials_table.selectRow(0)
        assert self.dialog.eos_table.rowCount() == 0
        assert self.dialog.load_btn.isEnabled()
        self.dialog.load_btn.click()
        phase = self.controller.result_phase
        assert phase is not None
        assert len(phase.reflections) > 0


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
        "Vinet", "A publication", "12–80.5 GPa", "395.0 ± 2",
        "3.62 (error n/r)",
        "47.250 ± 0.0048 (fixed)",
    )


def test_record_row_displays_implicit_bm2_derivative_as_fixed():
    record = {
        "eos": {"type": "BM2", "parameters": {"V0": 10.0, "K0": 20.0}},
        "parameter_errors": {"V0": None, "K0": 1.0},
        "fixed_parameters": [],
    }
    assert _record_row(record)[3:] == (
        "20.0 ± 1", "4 (fixed)", "10.000 (error n/r)",
    )
