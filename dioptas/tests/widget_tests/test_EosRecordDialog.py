# SPDX-License-Identifier: MIT

import pytest

from ...widgets.EosRecordDialog import EosRecordDialog


def _record():
    return {
        "label": "Example fit",
        "reference": {
            "authors": ["Example", "Author"],
            "year": 2024,
            "source": "J. Tests",
            "doi": "10.1234/example",
        },
        "eos": {
            "type": "BM3",
            "parameters": {"V0": 100.0, "K0": 150.0, "K0_prime": 4.2},
        },
        "parameter_errors": {"V0": 0.1, "K0": 2.0, "K0_prime": None},
        "fixed_parameters": ["K0_prime"],
        "experimental_pressure_range_gpa": [0.0, 20.0],
        "temperature_ref": 300.0,
    }


def test_record_dialog_round_trip(qapp):
    dialog = EosRecordDialog(_record())
    result = dialog.record()

    assert result["label"] == "Example fit"
    assert result["reference"]["authors"] == ["Example", "Author"]
    assert result["eos"]["parameters"]["K0"] == pytest.approx(150.0)
    assert result["parameter_errors"]["V0"] == pytest.approx(0.1)
    assert result["fixed_parameters"] == ["K0_prime"]
    assert result["experimental_pressure_range_gpa"] == [0.0, 20.0]
    dialog.close()


def test_record_dialog_changes_equation_parameter_rows(qapp):
    dialog = EosRecordDialog(_record())
    dialog.eos_type_cb.setCurrentIndex(dialog.eos_type_cb.findData("BM4"))

    names = [dialog.parameters_table.item(row, 1).text()
             for row in range(dialog.parameters_table.rowCount())]
    assert "K0_double_prime" in names
    dialog.close()


def test_error_column_header_is_readable(qapp):
    dialog = EosRecordDialog(_record())
    dialog.show()
    qapp.processEvents()

    header_item = dialog.parameters_table.horizontalHeaderItem(3)
    assert header_item.text() == "Error"
    assert dialog.parameters_table.horizontalHeader().sectionSize(3) >= 65
    assert "reported" in header_item.toolTip()
    dialog.close()
