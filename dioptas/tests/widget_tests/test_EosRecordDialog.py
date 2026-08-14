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


def _parameter_row(dialog, name, scope="EoS"):
    return next(
        row for row in range(dialog.parameters_table.rowCount())
        if dialog.parameters_table.item(row, 0).text() == scope
        and dialog.parameters_table.item(row, 1).text() == name
    )


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


def test_record_dialog_rejects_missing_required_equation_parameter(qapp):
    dialog = EosRecordDialog(_record())
    dialog.eos_type_cb.setCurrentIndex(dialog.eos_type_cb.findData("BM4"))

    with pytest.raises(ValueError, match="K0_double_prime"):
        dialog.record()
    dialog.close()


def test_record_dialog_rejects_incomplete_peritheos_thermal_model(qapp):
    dialog = EosRecordDialog(_record())
    dialog.thermal_type_cb.setCurrentIndex(
        dialog.thermal_type_cb.findData("MieGruneisenDebye")
    )

    with pytest.raises(ValueError, match="MieGruneisenDebye requires"):
        dialog.record()
    dialog.close()


def test_record_dialog_accepts_complete_peritheos_thermal_model(qapp):
    dialog = EosRecordDialog(_record())
    dialog.thermal_type_cb.setCurrentIndex(
        dialog.thermal_type_cb.findData("MieGruneisenDebye")
    )
    values = {
        "Tr": 300.0,
        "theta0": 500.0,
        "gamma0": 1.5,
        "q": 1.0,
        "n": 2.0,
    }
    for name, value in values.items():
        row = _parameter_row(dialog, name, scope="Thermal")
        dialog.parameters_table.item(row, 2).setText(str(value))

    result = dialog.record()

    assert result["thermal"]["parameters"] == values
    dialog.close()


def test_record_dialog_preserves_edits_hidden_by_equation_switch(qapp):
    dialog = EosRecordDialog(_record())
    row = _parameter_row(dialog, "K0_prime")
    dialog.parameters_table.item(row, 2).setText("6.5")

    dialog.eos_type_cb.setCurrentIndex(dialog.eos_type_cb.findData("BM2"))
    dialog.eos_type_cb.setCurrentIndex(dialog.eos_type_cb.findData("BM3"))

    row = _parameter_row(dialog, "K0_prime")
    assert dialog.parameters_table.item(row, 2).text() == "6.5"
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


def test_fit_domain_rows_align_and_notes_are_discoverable(qapp):
    dialog = EosRecordDialog(_record())
    dialog.show()
    qapp.processEvents()

    assert dialog.pressure_min_edit.geometry().x() == (
        dialog.temperature_min_edit.geometry().x())
    assert dialog.pressure_min_edit.width() == (
        dialog.temperature_min_edit.width())
    assert dialog.pressure_max_edit.geometry().x() == (
        dialog.temperature_max_edit.geometry().x())
    assert dialog.pressure_max_edit.width() == (
        dialog.temperature_max_edit.width())
    assert dialog.pressure_min_edit.width() <= 90
    assert dialog.pressure_max_edit.width() <= 90
    assert dialog.notes_edit.placeholderText().startswith("Optional notes")
    assert dialog.notes_edit.minimumHeight() >= 70
    assert dialog.notes_edit.width() > dialog.pressure_min_edit.width() * 3
    notes_style = dialog.notes_edit.styleSheet()
    assert "background-color: rgba(35, 38, 41, 0.75)" in notes_style
    assert "color: #f1f1f1" in notes_style
    dialog.close()
