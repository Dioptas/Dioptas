# SPDX-License-Identifier: MIT

import pytest
from peritheos import Material as PeritheosMaterial, get_material_document

from ...widgets.EosRecordDialog import EosRecordDialog
from ...model import eos
from ...model.util.eos_phase import RT_EOS_TYPES, THERMAL_EOS_TYPES


def test_reference_pressure_record_explains_and_preserves_its_reference(qapp):
    document = get_material_document("coesite_iv")
    record = next(record for record in document["eos_records"]
                  if record["eos"]["type"] == "BM2Reference")
    dialog = EosRecordDialog(record)
    row = _parameter_row(dialog, "P0")
    assert "Reference pressure" in dialog.parameters_table.item(row, 1).toolTip()
    assert "defined at reference pressure P0" in dialog.defaults_label.text()
    assert dialog.record()["eos"] == record["eos"]
    dialog.parameters_table.item(row, 2).setText("35")
    assert dialog.record()["eos"]["parameters"]["P0"] == 35.
    assert record["eos"]["parameters"]["P0"] == 32.7
    dialog.close()


@pytest.mark.parametrize("model", RT_EOS_TYPES)
def test_new_equation_has_complete_editable_defaults(qapp, model):
    from ...model.util.eos_phase import EosPhase
    dialog = EosRecordDialog(parameter_context={"n": 2., "z": 20.})
    dialog.eos_type_cb.setCurrentIndex(dialog.eos_type_cb.findData(model))
    record = dialog.record()
    parameters = record["eos"]["parameters"]
    engine = EosPhase(model, parameters, n=parameters.get("n"),
                      z=parameters.get("Z"), formula_units_per_cell=1)
    volume = engine.volume(20.)
    assert engine.pressure(volume) == pytest.approx(20., abs=1e-6)
    assert "starting estimates" in dialog.defaults_label.text()
    dialog.close()


def test_defaults_follow_current_values_and_do_not_refill_cleared_fields(qapp):
    dialog = EosRecordDialog(_record())
    dialog.parameters_table.item(_parameter_row(dialog, "K0"), 2).setText("200")
    dialog.parameters_table.item(_parameter_row(dialog, "K0_prime"), 2).setText("5")
    dialog.eos_type_cb.setCurrentIndex(dialog.eos_type_cb.findData("BM4"))
    row = _parameter_row(dialog, "K0_double_prime")
    assert float(dialog.parameters_table.item(row, 2).text()) == pytest.approx(-.025)
    dialog.parameters_table.item(row, 2).setText("")
    dialog.eos_type_cb.setCurrentIndex(dialog.eos_type_cb.findData("BM3"))
    dialog.eos_type_cb.setCurrentIndex(dialog.eos_type_cb.findData("BM4"))
    assert dialog.parameters_table.item(_parameter_row(dialog, "K0_double_prime"), 2).text() == ""
    with pytest.raises(ValueError, match="K0_double_prime"):
        dialog.record()
    dialog.close()


def test_thermal_defaults_use_material_atom_count_and_molar_volume(qapp):
    dialog = EosRecordDialog(_record(), parameter_context={"n": 2., "zc": 4})
    dialog.thermal_type_cb.setCurrentIndex(
        dialog.thermal_type_cb.findData("DoubleDebyeHelmholtz"))
    parameters = dialog.record()["thermal"]["parameters"]
    assert parameters["n"] == 2.
    assert parameters["Vp"] == pytest.approx(100. * .060221415 / 4)
    assert parameters.get("Tr") is None
    dialog.close()


@pytest.mark.parametrize("k0", [2., 5., 100.])
@pytest.mark.parametrize("canonical", [False, True])
def test_alphakt_starting_slope_does_not_make_soft_materials_unphysical(qapp, k0, canonical):
    from ...model.util.eos_phase import EosPhase
    record = _record()
    record["eos"]["parameters"]["K0"] = k0
    if canonical:
        record["eos"]["model"] = "birch_murnaghan_3"
    dialog = EosRecordDialog(record)
    dialog.thermal_type_cb.setCurrentIndex(dialog.thermal_type_cb.findData("AlphaKT"))
    parameters = dialog.record()["thermal"]["parameters"]
    assert parameters["dK_dT"] == pytest.approx(-1e-4 * k0)
    # The legacy form uses the same starting coefficients, but has no Tr row.
    engine = EosPhase("BM3", record["eos"]["parameters"], thermal_type="AlphaKT",
                      thermal_parameters={**parameters, "Tr": 300.})
    volume = engine.volume(1., 1000.)
    assert engine.pressure(volume, 1000.) == pytest.approx(1., abs=1e-6)
    dialog.close()


@pytest.mark.parametrize("model", THERMAL_EOS_TYPES)
def test_new_thermal_defaults_construct_calculate_and_export(qapp, tmp_path, model):
    from ...model.PhaseModel import PhaseModel
    document = get_material_document("gold")
    index = next(i for i, record in enumerate(document["eos_records"])
                 if record["eos"]["type"] == "Vinet" and not record.get("thermal"))
    phase = eos.build_jcpds(eos.Material.from_dict(document),
                            record_index=index, origin="bundled")
    phase_model = PhaseModel()
    phase_model.add_jcpds_object(phase, filename=phase.filename)
    dialog = EosRecordDialog(document["eos_records"][index],
                             parameter_context={"n": 1., "z": 79., "zc": 4})
    if model == "ThermalModifiedTait":
        dialog.eos_type_cb.setCurrentIndex(dialog.eos_type_cb.findData("ModifiedTait"))
    dialog.thermal_type_cb.setCurrentIndex(dialog.thermal_type_cb.findData(model))
    record = dialog.record()
    custom = phase_model.duplicate_eos_record(0, index, record)
    assert phase_model.set_pressure_temperature(0, 20., 1000.)
    path = tmp_path / "starting-estimates.eosmat"
    eos.save_material_file(str(path), eos.material_from_jcpds(phase))
    saved = eos.load_material_file(str(path))
    identifier = saved.eos_records[custom]["identifier"]
    native = PeritheosMaterial.from_eosmat(
        saved.to_dict(), record_identifiers=[identifier],
        require_primary_validation=False).eos_records[0]
    assert native.pressure(phase.params["v"], 1000., check_validity=False) == pytest.approx(
        20., abs=1e-6)
    dialog.close()


def test_every_library_record_preserves_its_model_and_parameters(qapp):
    for material in eos.load_materials():
        for record in material.eos_records:
            dialog = EosRecordDialog(record)
            try:
                result = dialog.record()
                for component in ("eos", "thermal"):
                    for field in ("type", "model", "parameters", "configuration"):
                        assert result.get(component, {}).get(field) == (
                            record.get(component, {}).get(field)
                        ), (material.identifier, record["identifier"], component, field)
            finally:
                dialog.close()
                dialog.deleteLater()
        qapp.processEvents()


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

    row = _parameter_row(dialog, "K0_double_prime")
    dialog.parameters_table.item(row, 2).setText("")

    with pytest.raises(ValueError, match="K0_double_prime"):
        dialog.record()
    dialog.close()


def test_record_dialog_rejects_incomplete_peritheos_thermal_model(qapp):
    dialog = EosRecordDialog(_record())
    dialog.thermal_type_cb.setCurrentIndex(
        dialog.thermal_type_cb.findData("MieGruneisenDebye")
    )
    row = _parameter_row(dialog, "theta0", "Thermal")
    dialog.parameters_table.item(row, 2).setText("")

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


def test_record_dialog_preserves_newer_peritheos_thermal_model(qapp):
    record = _record()
    record["thermal"] = {
        "type": "LogVolumeThermalPressure",
        "model": "log_volume_thermal_pressure",
        "parameters": {
            "Tr": 300.0,
            "alpha_KT_ref": 0.00714,
            "dK_dT_V": -0.0115,
        },
    }
    dialog = EosRecordDialog(record)

    result = dialog.record()

    assert dialog.thermal_type_cb.currentData() == "LogVolumeThermalPressure"
    assert result["thermal"]["type"] == record["thermal"]["type"]
    assert result["thermal"]["model"] == record["thermal"]["model"]
    assert result["thermal"]["parameters"] == record["thermal"]["parameters"]
    dialog.close()


def test_record_dialog_updates_canonical_eos_model_when_type_changes(qapp):
    document = get_material_document("gold")
    record_index = next(i for i, record in enumerate(document["eos_records"])
                        if not record.get("thermal"))
    record = document["eos_records"][record_index]
    dialog = EosRecordDialog(record)
    dialog.eos_type_cb.setCurrentIndex(
        dialog.eos_type_cb.findData("Vinet"))

    result = dialog.record()

    assert result["eos"]["type"] == "Vinet"
    assert result["eos"]["model"] == "vinet"
    document["eos_records"][record_index] = result
    executable = PeritheosMaterial.from_eosmat(
        document,
        record_identifiers=[result["identifier"]],
        require_primary_validation=False,
    )
    from peritheos.eos.rt import Vinet
    expected = Vinet(**result["eos"]["parameters"]).volume(50.0)
    assert executable.eos_records[0].volume(
        50.0, 300.0, check_validity=False
    ) == pytest.approx(expected)
    dialog.close()


def test_record_dialog_updates_canonical_thermal_model_when_type_changes(qapp):
    record = get_material_document("gold")["eos_records"][0]
    dialog = EosRecordDialog(record)
    dialog.thermal_type_cb.setCurrentIndex(
        dialog.thermal_type_cb.findData("MieGruneisenDebye"))
    values = {
        "Tr": 300.0,
        "theta0": 500.0,
        "gamma0": 1.5,
        "q": 1.0,
        "n": 1.0,
    }
    for name, value in values.items():
        row = _parameter_row(dialog, name, scope="Thermal")
        dialog.parameters_table.item(row, 2).setText(str(value))

    result = dialog.record()

    assert result["thermal"]["type"] == "MieGruneisenDebye"
    assert result["thermal"]["model"] == "mie_gruneisen_debye"
    dialog.close()


def test_record_dialog_preserves_native_reference_extensions(qapp):
    record = next(
        record for record in get_material_document("diamond")["eos_records"]
        if record["identifier"] == "diamond_benedict_2014_double_debye_4"
    )
    dialog = EosRecordDialog(record)

    result = dialog.record()

    assert result["reference"]["title"] == record["reference"]["title"]
    assert result["reference"]["locations"] == record["reference"]["locations"]
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


def test_thermal_switch_retains_edits_without_reusing_unrelated_coefficients(qapp):
    record = next(record for record in get_material_document("diamond")["eos_records"]
                  if record.get("thermal", {}).get("type") == "Sokolova2016")
    dialog = EosRecordDialog(record)
    row = _parameter_row(dialog, "m", "Thermal")
    dialog.parameters_table.item(row, 2).setText("1.25")
    dialog.thermal_type_cb.setCurrentIndex(dialog.thermal_type_cb.findData(
        "AsymptoticPowerLawMieGruneisenDebyeExcess"))
    row = _parameter_row(dialog, "m", "Thermal")
    assert float(dialog.parameters_table.item(row, 2).text()) == 0.
    dialog.parameters_table.item(row, 2).setText("2.5")
    dialog.thermal_type_cb.setCurrentIndex(dialog.thermal_type_cb.findData("Sokolova2016"))
    row = _parameter_row(dialog, "m", "Thermal")
    assert dialog.parameters_table.item(row, 2).text() == "1.25"
    dialog.close()


@pytest.mark.parametrize("model", ["LinearThermalPressure", "ThermalModifiedTait"])
def test_new_thermal_model_can_be_created_from_an_isothermal_copy(qapp, model):
    document = get_material_document("gold")
    index = next(i for i, record in enumerate(document["eos_records"])
                 if record["eos"]["type"] == "Vinet" and not record.get("thermal"))
    dialog = EosRecordDialog(document["eos_records"][index])
    dialog.thermal_type_cb.setCurrentIndex(dialog.thermal_type_cb.findData(model))
    values = {"Tr": 300., "alpha_KT": .007, "theta": 500., "alpha0": 3e-5, "n": 1.}
    for name in dialog._thermal_parameters[model]:
        row = _parameter_row(dialog, name, "Thermal")
        dialog.parameters_table.item(row, 2).setText(str(values[name]))
    if model == "ThermalModifiedTait":
        with pytest.raises(ValueError, match="Modified Tait reference"):
            dialog.record()
        dialog.eos_type_cb.setCurrentIndex(dialog.eos_type_cb.findData("ModifiedTait"))
        row = _parameter_row(dialog, "K0_double_prime")
        dialog.parameters_table.item(row, 2).setText("-.03")
    result = dialog.record()
    document["eos_records"][index] = result
    native = PeritheosMaterial.from_eosmat(
        document, record_identifiers=[result["identifier"]],
        require_primary_validation=False).eos_records[0]
    volume = native.volume(20., 1000., check_validity=False)
    assert native.pressure(volume, 1000., check_validity=False) == pytest.approx(20.)
    dialog.close()


@pytest.mark.parametrize("thermal_type", ["AlphaKT", "MieGruneisenDebye", ""])
def test_changed_thermal_model_can_be_duplicated_calculated_and_saved(
        qapp, tmp_path, thermal_type):
    from ...model.PhaseModel import PhaseModel

    document = get_material_document("gold")
    source_index = next(i for i, record in enumerate(document["eos_records"])
                        if record.get("equation_kind") == "isothermal")
    source = document["eos_records"][source_index]
    # Also exercise removing a thermal model with explicit equation metadata.
    if not thermal_type:
        source_index = next(i for i, record in enumerate(document["eos_records"])
                            if record.get("equation_kind") == "thermal")
        source = document["eos_records"][source_index]
    phase = eos.build_jcpds(eos.Material.from_dict(document),
                            record_index=source_index, origin="bundled")
    model = PhaseModel()
    model.add_jcpds_object(phase, filename=phase.filename)
    dialog = EosRecordDialog(source)
    dialog.eos_type_cb.setCurrentIndex(dialog.eos_type_cb.findData("Vinet"))
    dialog.thermal_type_cb.setCurrentIndex(
        dialog.thermal_type_cb.findData(thermal_type))
    values = {"Tr": 300., "theta0": 500., "gamma0": 1.5, "q": 1., "n": 1.,
              "alpha0": 3e-5, "dK_dT": -.01}
    for name, value in values.items():
        for row in range(dialog.parameters_table.rowCount()):
            if (dialog.parameters_table.item(row, 0).text() == "Thermal"
                    and dialog.parameters_table.item(row, 1).text() == name):
                dialog.parameters_table.item(row, 2).setText(str(value))
    result = dialog.record()
    assert result["equation_kind"] == ("thermal" if thermal_type else "isothermal")
    custom_index = model.duplicate_eos_record(0, source_index, result)
    assert model.set_pressure_temperature(0, 20., 1000.)
    custom = phase.params["eos_records"][custom_index]
    path = tmp_path / "custom.eosmat"
    eos.save_material_file(str(path), eos.material_from_jcpds(phase))
    restored = PeritheosMaterial.from_eosmat(
        eos.load_material_file(str(path)).to_dict(),
        record_identifiers=[custom["identifier"]], require_primary_validation=False,
    ).eos_records[0]
    assert phase.params["v"] == pytest.approx(
        restored.volume(20., 1000. if thermal_type else None, check_validity=False))
    if thermal_type:
        assert phase.params["v"] != pytest.approx(restored.volume(
            20., 300., check_validity=False))
    assert phase.params["eos_records"][source_index] == source
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
    dialog.metadata_tabs.setCurrentIndex(1)
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


def test_coefficients_remain_visible_while_editing_either_metadata_tab(qapp):
    dialog = EosRecordDialog(_record())
    dialog.resize(680, 680)
    dialog.show()
    try:
        for index in (0, 1):
            dialog.metadata_tabs.setCurrentIndex(index)
            qapp.processEvents()
            table = dialog.parameters_table
            assert table.viewport().height() >= 3 * table.rowHeight(0)
        dialog.metadata_tabs.setCurrentIndex(0)
        dialog.authors_edit.setText("Example; Revised Author")
        dialog.metadata_tabs.setCurrentIndex(1)
        dialog.pressure_min_edit.setText("2")
        record = dialog.record()
        assert record['reference']['authors'] == ['Example', 'Revised Author']
        assert record['experimental_pressure_range_gpa'][0] == 2
    finally:
        dialog.close()
