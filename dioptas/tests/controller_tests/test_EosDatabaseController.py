# -*- coding: utf-8 -*-
"""
Tests for the EoS database browser: the controller drives the (dumb)
dialog, search filters the bundled materials, and loading builds a jcpds
phase carrying the full reference-switcher state.
"""
import gc

from ..utility import QtTest

from ...controller.integration.phase.EosDatabaseController import (
    EosDatabaseController)
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

    def test_selecting_material_shows_eos_records(self):
        self.dialog.search_input.setText("gold")
        self.dialog.materials_table.selectRow(0)
        material = self.controller.shown_materials[0]
        assert (self.dialog.eos_table.rowCount()
                == len(material.eos_records))
        assert self.dialog.load_btn.isEnabled()

    def test_load_builds_phase_with_selected_record(self):
        self.dialog.search_input.setText("gold")
        self.dialog.materials_table.selectRow(0)
        self.dialog.eos_table.selectRow(1)
        self.dialog.load_btn.click()

        phase = self.controller.result_phase
        assert phase is not None
        material = self.controller.shown_materials[0]
        assert phase.params["eos_current_index"] == 1
        assert (phase.params["k0"] == material.eos_records[1]
                ["eos"]["parameters"]["K0"])
        assert len(phase.params["eos_records"]) == len(material.eos_records)

    def test_new_search_refreshes_eos_records(self):
        # Regression: after clicking into the EoS table and searching
        # again, the previous selection's row index survived the refill
        # without firing selectionChanged, so the EoS table kept showing
        # the old material's records.
        self.dialog.search_input.setText("gold")
        self.dialog.eos_table.selectRow(0)   # user clicks into the viewer
        gold_rows = self.dialog.eos_table.rowCount()
        assert gold_rows > 0

        self.dialog.search_input.setText("mgo")
        material = self.controller.shown_materials[0]
        assert material.formula == "MgO"
        assert (self.dialog.eos_table.rowCount()
                == len(material.eos_records))
        assert self.dialog.eos_table.rowCount() != gold_rows

    def test_material_without_records_is_still_loadable(self):
        self.dialog.search_input.setText("copper")
        self.dialog.materials_table.selectRow(0)
        assert self.dialog.eos_table.rowCount() == 0
        assert self.dialog.load_btn.isEnabled()
        self.dialog.load_btn.click()
        phase = self.controller.result_phase
        assert phase is not None
        assert len(phase.reflections) > 0
