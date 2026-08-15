# SPDX-License-Identifier: MIT

from qtpy import QtWidgets

from ..utility import QtTest
from ...widgets.integration.control.PhaseWidget import PhaseWidget


class PhaseWidgetTest(QtTest):
    def setUp(self):
        self.phase_widget = PhaseWidget()

    def tearDown(self):
        self.phase_widget.close()
        del self.phase_widget

    def test_name_and_reference_columns_are_resizable(self):
        header = self.phase_widget.phase_tw.horizontalHeader()

        self.assertEqual(
            header.sectionResizeMode(2), QtWidgets.QHeaderView.Interactive
        )
        self.assertEqual(
            header.sectionResizeMode(5), QtWidgets.QHeaderView.Interactive
        )

    def test_reference_column_follows_pressure_and_temperature(self):
        table = self.phase_widget.phase_tw

        self.assertEqual(
            [table.horizontalHeaderItem(column).text() for column in range(2, 6)],
            ["Name", "P (GPa)", "T (K)", "Ref"],
        )

        self.phase_widget.add_phase("Au", "#ffd700")
        self.assertIs(table.cellWidget(0, 3), self.phase_widget.pressure_sbs[0])
        self.assertIs(table.cellWidget(0, 4), self.phase_widget.temperature_sbs[0])
        self.assertIs(table.cellWidget(0, 5), self.phase_widget.reference_cbs[0])

    def test_spinbox_columns_fit_before_first_layout_update(self):
        table = self.phase_widget.phase_tw
        self.phase_widget.add_phase("Au", "#ffd700")

        self.assertEqual(table.columnWidth(3), 70)
        self.assertEqual(table.columnWidth(4), 80)
        self.assertEqual(
            table.columnWidth(3), self.phase_widget.pressure_sbs[0].width()
        )
        self.assertEqual(
            table.columnWidth(4), self.phase_widget.temperature_sbs[0].width()
        )

    def test_temperature_spinbox_disallows_negative_kelvin(self):
        self.phase_widget.add_phase("Au", "#ffd700")
        temperature = self.phase_widget.temperature_sbs[0]

        self.assertEqual(temperature.minimum(), 0.0)
        temperature.setValue(-1.0)
        self.assertEqual(temperature.value(), 0.0)

    def test_layout_update_preserves_name_and_reference_column_widths(self):
        table = self.phase_widget.phase_tw
        table.setColumnWidth(2, 150)
        table.setColumnWidth(5, 220)

        self.phase_widget.update_phase_tw_column_sizes()

        self.assertEqual(table.columnWidth(2), 150)
        self.assertEqual(table.columnWidth(5), 220)
