# SPDX-License-Identifier: MIT
"""Editor for one user-owned equation-of-state record."""

from __future__ import annotations

from copy import deepcopy

from qtpy import QtCore, QtGui, QtWidgets

from ..model.util.eos_phase import (
    EOS_DISPLAY_NAMES,
    EosPhase,
    RT_EOS_TYPES,
    eos_parameter_names,
)


_THERMAL_PARAMETERS = {
    "": (),
    "AlphaKT": ("alpha0", "d_alpha_dT", "dK_dT", "dK_prime_dT"),
    "MieGruneisenDebye": ("Tr", "theta0", "gamma0", "q", "n"),
    "MieGruneisenEinstein": ("Tr", "theta0", "gamma0", "q", "n"),
    "Sokolova2016": (
        "Tr", "QE1o", "mE1", "QE2o", "mE2", "delta", "t",
        "a_0", "m", "g", "e_0",
    ),
}


class EosRecordDialog(QtWidgets.QDialog):
    """Edit parameters, provenance and fit metadata for one EoS record."""

    def __init__(self, record: dict | None = None, parent=None, *,
                 title: str = "EoS Record"):
        super().__init__(parent)
        self._source_record = deepcopy(record or {})
        self._result_record = None
        # Parameter rows appear and disappear with the selected equations.
        # Keep edits for hidden rows so switching away and back is lossless.
        self._parameter_state = {}
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumSize(680, 680)

        self._create_widgets()
        self._create_layout()
        self._load_record(self._source_record)

    def _create_widgets(self):
        self.label_edit = QtWidgets.QLineEdit()
        self.eos_type_cb = QtWidgets.QComboBox()
        for key in RT_EOS_TYPES:
            self.eos_type_cb.addItem(EOS_DISPLAY_NAMES.get(key, key), key)
        self.thermal_type_cb = QtWidgets.QComboBox()
        self.thermal_type_cb.addItem("None", "")
        self.thermal_type_cb.addItem("Constant alpha / dK-dT", "AlphaKT")
        for key in ("MieGruneisenDebye", "MieGruneisenEinstein",
                    "Sokolova2016"):
            self.thermal_type_cb.addItem(EOS_DISPLAY_NAMES.get(key, key), key)

        self.parameters_table = QtWidgets.QTableWidget()
        self.parameters_table.setColumnCount(5)
        self.parameters_table.setHorizontalHeaderLabels(
            ["Part", "Parameter", "Value", "Error", "Fixed"])
        header = self.parameters_table.horizontalHeader()
        header.setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(
            1, QtWidgets.QHeaderView.Stretch)
        # ResizeToContents made the old "Error" heading only ~36 px wide,
        # which clips with some native themes. Keep the editable numeric and
        # checkbox columns comfortably readable while Parameter absorbs the
        # remaining width.
        for column, width in ((2, 80), (3, 70), (4, 60)):
            header.setSectionResizeMode(column, QtWidgets.QHeaderView.Interactive)
            header.resizeSection(column, width)
        self.parameters_table.horizontalHeaderItem(3).setToolTip(
            "Published/reported parameter error")

        self.authors_edit = QtWidgets.QLineEdit()
        self.authors_edit.setPlaceholderText("Surname; Surname; Surname")
        self.authors_truncated_cb = QtWidgets.QCheckBox(
            "Source gives first author as et al.")
        self.year_edit = QtWidgets.QLineEdit()
        self.year_edit.setValidator(QtGui.QIntValidator(0, 9999, self))
        self.source_edit = QtWidgets.QLineEdit()
        self.volume_edit = QtWidgets.QLineEdit()
        self.locator_edit = QtWidgets.QLineEdit()
        self.doi_edit = QtWidgets.QLineEdit()
        self.details_edit = QtWidgets.QLineEdit()

        self.pressure_min_edit = QtWidgets.QLineEdit()
        self.pressure_max_edit = QtWidgets.QLineEdit()
        self.temperature_min_edit = QtWidgets.QLineEdit()
        self.temperature_max_edit = QtWidgets.QLineEdit()
        self.temperature_ref_edit = QtWidgets.QLineEdit()
        validator = QtGui.QDoubleValidator(self)
        for field in (
            self.pressure_min_edit, self.pressure_max_edit,
            self.temperature_min_edit, self.temperature_max_edit,
            self.temperature_ref_edit,
        ):
            field.setValidator(validator)
            field.setMaximumWidth(90)
        self.notes_edit = QtWidgets.QPlainTextEdit()
        self.notes_edit.setPlaceholderText(
            "Optional notes about the fit, sample, method, or provenance")
        self.notes_edit.setMinimumHeight(70)
        self.notes_edit.setMaximumHeight(90)
        self.notes_edit.setStyleSheet("""
            QPlainTextEdit {
                color: #f1f1f1;
                background-color: rgba(35, 38, 41, 0.75);
                border: 2px solid rgba(241, 241, 241, 0.2);
                border-width: 0 0 2px 0;
                border-radius: 0;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                padding: 4px 8px;
            }
        """)

        self.buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.eos_type_cb.currentIndexChanged.connect(self._refresh_parameters)
        self.thermal_type_cb.currentIndexChanged.connect(
            self._refresh_parameters)

    def _create_layout(self):
        root = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()
        form.addRow("Record label:", self.label_edit)
        form.addRow("Equation:", self.eos_type_cb)
        form.addRow("Thermal model:", self.thermal_type_cb)
        root.addLayout(form)
        root.addWidget(QtWidgets.QLabel("Parameters and publication errors:"))
        root.addWidget(self.parameters_table, 1)

        reference_box = QtWidgets.QGroupBox("Literature reference")
        reference_form = QtWidgets.QFormLayout(reference_box)
        reference_form.addRow("Authors:", self.authors_edit)
        reference_form.addRow("", self.authors_truncated_cb)
        reference_form.addRow("Year:", self.year_edit)
        reference_form.addRow("Journal/source:", self.source_edit)
        reference_form.addRow("Volume:", self.volume_edit)
        reference_form.addRow("Pages/article:", self.locator_edit)
        reference_form.addRow("DOI:", self.doi_edit)
        reference_form.addRow("Details:", self.details_edit)
        root.addWidget(reference_box)

        range_box = QtWidgets.QGroupBox("Fit domain and provenance")
        range_grid = QtWidgets.QGridLayout(range_box)
        range_grid.addWidget(QtWidgets.QLabel("Experimental pressure:"), 0, 0)
        range_grid.addWidget(self.pressure_min_edit, 0, 1)
        range_grid.addWidget(QtWidgets.QLabel("to"), 0, 2,
                             alignment=QtCore.Qt.AlignCenter)
        range_grid.addWidget(self.pressure_max_edit, 0, 3)
        range_grid.addWidget(QtWidgets.QLabel("GPa"), 0, 4)
        range_grid.addWidget(
            QtWidgets.QLabel("Experimental temperature:"), 1, 0)
        range_grid.addWidget(self.temperature_min_edit, 1, 1)
        range_grid.addWidget(QtWidgets.QLabel("to"), 1, 2,
                             alignment=QtCore.Qt.AlignCenter)
        range_grid.addWidget(self.temperature_max_edit, 1, 3)
        range_grid.addWidget(QtWidgets.QLabel("K"), 1, 4)
        range_grid.addWidget(
            QtWidgets.QLabel("Reference temperature:"), 2, 0)
        range_grid.addWidget(self.temperature_ref_edit, 2, 1, 1, 3)
        range_grid.addWidget(QtWidgets.QLabel("K"), 2, 4)
        notes_label = QtWidgets.QLabel("Notes (optional):")
        range_grid.addWidget(notes_label, 3, 0,
                             alignment=QtCore.Qt.AlignTop)
        range_grid.addWidget(self.notes_edit, 3, 1, 1, 5)
        range_grid.setColumnStretch(5, 1)
        root.addWidget(range_box)
        root.addWidget(self.buttons)

    def _load_record(self, record: dict):
        self.label_edit.setText(str(record.get("label") or ""))
        eos = record.get("eos") or {}
        eos_type = eos.get("type") or "BM3"
        self.eos_type_cb.setCurrentIndex(max(
            0, self.eos_type_cb.findData(eos_type)))
        thermal = record.get("thermal") or {}
        self.thermal_type_cb.setCurrentIndex(max(
            0, self.thermal_type_cb.findData(thermal.get("type") or "")))

        reference = record.get("reference") or {}
        if isinstance(reference, str):
            self.details_edit.setText(reference)
        else:
            self.authors_edit.setText("; ".join(
                str(author) for author in reference.get("authors", [])))
            self.authors_truncated_cb.setChecked(bool(
                reference.get("authors_truncated")))
            self.year_edit.setText(
                "" if reference.get("year") is None
                else str(reference.get("year")))
            self.source_edit.setText(str(reference.get("source") or ""))
            self.volume_edit.setText(str(reference.get("volume") or ""))
            self.locator_edit.setText(str(reference.get("locator") or ""))
            self.doi_edit.setText(str(reference.get("doi") or ""))
            self.details_edit.setText(str(reference.get("details") or ""))

        self._set_range(record.get("experimental_pressure_range_gpa"),
                        self.pressure_min_edit, self.pressure_max_edit)
        self._set_range(record.get("experimental_temperature_range_k"),
                        self.temperature_min_edit, self.temperature_max_edit)
        self.temperature_ref_edit.setText(
            "" if record.get("temperature_ref") is None
            else str(record.get("temperature_ref")))
        self.notes_edit.setPlainText(str(record.get("notes") or ""))
        self._refresh_parameters()

    @staticmethod
    def _set_range(values, low_edit, high_edit):
        if isinstance(values, (list, tuple)) and len(values) == 2:
            low_edit.setText(str(values[0]))
            high_edit.setText(str(values[1]))

    def _table_state(self) -> dict:
        state = {}
        for row in range(self.parameters_table.rowCount()):
            scope = self.parameters_table.item(row, 0).data(QtCore.Qt.UserRole)
            name = self.parameters_table.item(row, 1).text()
            state[(scope, name)] = (
                self.parameters_table.item(row, 2).text(),
                self.parameters_table.item(row, 3).text(),
                self.parameters_table.item(row, 4).checkState()
                == QtCore.Qt.Checked,
            )
        return state

    def _refresh_parameters(self):
        self._parameter_state.update(self._table_state())
        state = self._parameter_state
        source = self._source_record
        eos_source = source.get("eos") or {}
        thermal_source = source.get("thermal") or {}
        source_values = {
            **{("EoS", key): value for key, value in
               (eos_source.get("parameters") or {}).items()},
            **{("Thermal", key): value for key, value in
               (thermal_source.get("parameters") or {}).items()},
        }
        source_errors = {
            **{("EoS", key): value for key, value in
               (source.get("parameter_errors") or {}).items()},
            **{("Thermal", key): value for key, value in
               (thermal_source.get("parameter_errors") or {}).items()},
        }
        source_fixed = {
            *(('EoS', key) for key in source.get("fixed_parameters", [])),
            *(('Thermal', key) for key in
              thermal_source.get("fixed_parameters", [])),
        }

        eos_type = self.eos_type_cb.currentData() or "BM3"
        keys = [("EoS", "V0")]
        keys.extend(("EoS", name) for name in eos_parameter_names(eos_type))
        thermal_type = self.thermal_type_cb.currentData() or ""
        keys.extend(("Thermal", name)
                    for name in _THERMAL_PARAMETERS[thermal_type])
        self.parameters_table.setRowCount(len(keys))
        for row, (scope, name) in enumerate(keys):
            scope_item = QtWidgets.QTableWidgetItem(scope)
            scope_item.setData(QtCore.Qt.UserRole, scope)
            scope_item.setFlags(scope_item.flags() & ~QtCore.Qt.ItemIsEditable)
            name_item = QtWidgets.QTableWidgetItem(name)
            name_item.setFlags(name_item.flags() & ~QtCore.Qt.ItemIsEditable)
            previous = state.get((scope, name))
            value = previous[0] if previous else source_values.get((scope, name))
            error = previous[1] if previous else source_errors.get((scope, name))
            fixed = previous[2] if previous else (scope, name) in source_fixed
            value_item = QtWidgets.QTableWidgetItem(
                "" if value is None else str(value))
            error_item = QtWidgets.QTableWidgetItem(
                "" if error is None else str(error))
            fixed_item = QtWidgets.QTableWidgetItem()
            fixed_item.setFlags(
                (fixed_item.flags() | QtCore.Qt.ItemIsUserCheckable)
                & ~QtCore.Qt.ItemIsEditable)
            fixed_item.setCheckState(
                QtCore.Qt.Checked if fixed else QtCore.Qt.Unchecked)
            for column, item in enumerate((scope_item, name_item, value_item,
                                           error_item, fixed_item)):
                self.parameters_table.setItem(row, column, item)

    @staticmethod
    def _optional_float(text: str):
        text = text.strip()
        return None if not text else float(text)

    def _read_range(self, low_edit, high_edit, label):
        low = self._optional_float(low_edit.text())
        high = self._optional_float(high_edit.text())
        if low is None and high is None:
            return None
        if low is None or high is None:
            raise ValueError(f"{label} needs both a minimum and maximum")
        if high < low:
            raise ValueError(f"{label} maximum must not be below its minimum")
        return [low, high]

    def _build_record(self) -> dict:
        record = deepcopy(self._source_record)
        record["label"] = self.label_edit.text().strip() or "Custom EoS"
        eos_parameters = {}
        eos_errors = {}
        eos_fixed = []
        thermal_parameters = {}
        thermal_errors = {}
        thermal_fixed = []
        for row in range(self.parameters_table.rowCount()):
            scope = self.parameters_table.item(row, 0).data(QtCore.Qt.UserRole)
            name = self.parameters_table.item(row, 1).text()
            value = self._optional_float(
                self.parameters_table.item(row, 2).text())
            error = self._optional_float(
                self.parameters_table.item(row, 3).text())
            fixed = (self.parameters_table.item(row, 4).checkState()
                     == QtCore.Qt.Checked)
            target = eos_parameters if scope == "EoS" else thermal_parameters
            errors = eos_errors if scope == "EoS" else thermal_errors
            fixed_names = eos_fixed if scope == "EoS" else thermal_fixed
            if value is not None:
                target[name] = value
            errors[name] = error
            if fixed:
                fixed_names.append(name)
        if eos_parameters.get("V0", 0) <= 0:
            raise ValueError("V0 must be positive")
        if eos_parameters.get("K0", 0) <= 0:
            raise ValueError("K0 must be positive")
        eos_type = self.eos_type_cb.currentData() or "BM3"
        record["eos"] = {
            "type": eos_type,
            "parameters": eos_parameters,
        }
        record["parameter_errors"] = eos_errors
        record["fixed_parameters"] = eos_fixed

        thermal_type = self.thermal_type_cb.currentData() or ""
        if thermal_type:
            record["thermal"] = {
                "type": thermal_type,
                "parameters": thermal_parameters,
                "parameter_errors": thermal_errors,
                "fixed_parameters": thermal_fixed,
            }
        else:
            record.pop("thermal", None)

        self._validate_engine_parameters(
            eos_type,
            eos_parameters,
            thermal_type,
            thermal_parameters,
        )

        authors_text = self.authors_edit.text().strip()
        authors = [part.strip() for part in authors_text.split(";")
                   if part.strip()]
        reference = {
            "authors": authors,
            "authors_truncated": self.authors_truncated_cb.isChecked(),
            "year": (int(self.year_edit.text())
                     if self.year_edit.text().strip() else None),
            "source": self.source_edit.text().strip(),
            "volume": self.volume_edit.text().strip(),
            "locator": self.locator_edit.text().strip(),
            "doi": self.doi_edit.text().strip(),
            "details": self.details_edit.text().strip(),
        }
        record["reference"] = {
            key: value for key, value in reference.items()
            if value not in (None, "", [], False)
        }
        pressure_range = self._read_range(
            self.pressure_min_edit, self.pressure_max_edit,
            "Experimental pressure range")
        temperature_range = self._read_range(
            self.temperature_min_edit, self.temperature_max_edit,
            "Experimental temperature range")
        for key, value in (
            ("experimental_pressure_range_gpa", pressure_range),
            ("experimental_temperature_range_k", temperature_range),
        ):
            if value is None:
                record.pop(key, None)
            else:
                record[key] = value
        temperature_ref = self._optional_float(
            self.temperature_ref_edit.text())
        if temperature_ref is None:
            record.pop("temperature_ref", None)
        else:
            record["temperature_ref"] = temperature_ref
        notes = self.notes_edit.toPlainText().strip()
        if notes:
            record["notes"] = notes
        else:
            record.pop("notes", None)
        record.pop("default", None)
        return record

    @staticmethod
    def _validate_engine_parameters(
        eos_type: str,
        eos_parameters: dict,
        thermal_type: str,
        thermal_parameters: dict,
    ) -> None:
        """Reject records that the selected Peritheos engines cannot use."""
        required_eos = ["V0", *eos_parameter_names(eos_type)]
        missing = [name for name in required_eos
                   if eos_parameters.get(name) is None]
        if missing:
            raise ValueError(
                f"{eos_type} requires parameters: {', '.join(missing)}"
            )

        # AlphaKT is Dioptas' optional legacy coefficient correction. The
        # Peritheos thermal models, in contrast, must be complete records.
        if thermal_type and thermal_type != "AlphaKT":
            missing = [
                name for name in _THERMAL_PARAMETERS[thermal_type]
                if thermal_parameters.get(name) is None
            ]
            if missing:
                raise ValueError(
                    f"{thermal_type} requires parameters: {', '.join(missing)}"
                )

        n_value = eos_parameters.get("n", thermal_parameters.get("n"))
        if n_value is not None and n_value <= 0:
            raise ValueError("n must be positive")

        # Zc belongs to the material rather than an EoS record. A dummy value
        # lets the constructor validate every record-owned parameter here;
        # the phase editor separately exposes the real crystallographic Zc.
        EosPhase(
            eos_type,
            eos_parameters,
            n=n_value,
            z=eos_parameters.get("Z"),
            formula_units_per_cell=1,
            thermal_type=(
                thermal_type
                if thermal_type and thermal_type != "AlphaKT"
                else None
            ),
            thermal_parameters=thermal_parameters,
        )

    def accept(self):
        try:
            self._result_record = self._build_record()
        except ValueError as error:
            QtWidgets.QMessageBox.warning(self, "Invalid EoS record", str(error))
            return
        super().accept()

    def record(self) -> dict:
        """The accepted record, or the current form content for tests."""
        return deepcopy(self._result_record or self._build_record())
