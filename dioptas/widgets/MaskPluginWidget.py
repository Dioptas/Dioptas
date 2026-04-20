# SPDX-License-Identifier: MIT

from __future__ import annotations

from qtpy import QtWidgets, QtCore, QtGui


class MaskPluginWidget(QtWidgets.QWidget):
    """Widget section showing mask plugin enable/settings controls."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QtWidgets.QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)

        self._plugin_rows: dict[str, _PluginRow] = {}

    def add_plugin_row(
        self, name: str, has_settings: bool = False
    ) -> tuple[QtWidgets.QCheckBox, QtWidgets.QPushButton | None]:
        """Add a row for a plugin. Returns (checkbox, settings_btn or None)."""
        row = _PluginRow(name, has_settings, self)
        self._plugin_rows[name] = row
        self._layout.addWidget(row)
        return row.checkbox, row.settings_btn

    def get_row(self, name: str) -> _PluginRow | None:
        return self._plugin_rows.get(name)

    @property
    def plugin_names(self) -> list[str]:
        return list(self._plugin_rows.keys())


class _PluginRow(QtWidgets.QWidget):
    """A single plugin row: checkbox + optional settings button."""

    def __init__(self, name: str, has_settings: bool, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.checkbox = QtWidgets.QCheckBox(name)
        layout.addWidget(self.checkbox, stretch=1)

        self.settings_btn: QtWidgets.QPushButton | None = None
        if has_settings:
            self.settings_btn = QtWidgets.QPushButton()
            self.settings_btn.setIcon(
                self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_FileDialogDetailedView)
            )
            self.settings_btn.setFixedSize(24, 24)
            self.settings_btn.setToolTip(f"Settings for {name}")
            layout.addWidget(self.settings_btn)


class MaskPluginSettingsDialog(QtWidgets.QDialog):
    """Dialog built from a plugin's settings schema."""

    settings_changed = QtCore.Signal(dict)

    def __init__(
        self,
        plugin_name: str,
        schema: dict,
        current_settings: dict,
        plugin_description: str = "",
        info_text: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(f"{plugin_name} Settings")
        self.setMinimumWidth(300)

        self._schema = schema
        self._widgets: dict[str, QtWidgets.QWidget] = {}

        layout = QtWidgets.QVBoxLayout(self)

        if plugin_description:
            desc_label = QtWidgets.QLabel(plugin_description)
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet("color: gray; margin-bottom: 6px;")
            layout.addWidget(desc_label)

        if info_text:
            info_label = QtWidgets.QLabel(info_text)
            info_label.setWordWrap(True)
            info_label.setStyleSheet("font-weight: bold; margin-bottom: 6px;")
            layout.addWidget(info_label)

        form_layout = QtWidgets.QFormLayout()

        for key, spec in schema.items():
            label = spec.get("label", key)
            param_type = spec.get("type", "str")
            value = current_settings.get(key, spec.get("default"))

            widget = self._create_widget(param_type, spec, value)
            self._connect_live_update(widget, param_type)
            description = spec.get("description")
            if description:
                widget.setToolTip(description)
            self._widgets[key] = widget
            label_widget = QtWidgets.QLabel(label)
            if description:
                label_widget.setToolTip(description)
            form_layout.addRow(label_widget, widget)

        layout.addLayout(form_layout)

        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _create_widget(self, param_type: str, spec: dict, value) -> QtWidgets.QWidget:
        if param_type == "float":
            widget = QtWidgets.QDoubleSpinBox()
            widget.setDecimals(spec.get("decimals", 4))
            widget.setRange(
                spec.get("min", -1e12),
                spec.get("max", 1e12),
            )
            if value is not None:
                widget.setValue(float(value))
            return widget

        elif param_type == "int":
            widget = QtWidgets.QSpinBox()
            widget.setRange(
                spec.get("min", -2**31),
                spec.get("max", 2**31 - 1),
            )
            if value is not None:
                widget.setValue(int(value))
            return widget

        elif param_type == "bool":
            widget = QtWidgets.QCheckBox()
            if value is not None:
                widget.setChecked(bool(value))
            return widget

        elif param_type == "choice":
            widget = QtWidgets.QComboBox()
            choices = spec.get("choices", [])
            widget.addItems(choices)
            if value is not None and value in choices:
                widget.setCurrentText(str(value))
            return widget

        else:  # str or unknown
            widget = QtWidgets.QLineEdit()
            if value is not None:
                widget.setText(str(value))
            return widget

    def _get_values(self) -> dict:
        values = {}
        for key, widget in self._widgets.items():
            param_type = self._schema[key].get("type", "str")
            if param_type == "float":
                values[key] = widget.value()
            elif param_type == "int":
                values[key] = widget.value()
            elif param_type == "bool":
                values[key] = widget.isChecked()
            elif param_type == "choice":
                values[key] = widget.currentText()
            else:
                values[key] = widget.text()
        return values

    def _connect_live_update(self, widget: QtWidgets.QWidget, param_type: str) -> None:
        """Connect widget change signals for immediate feedback."""
        if param_type in ("float", "int"):
            widget.valueChanged.connect(self._on_value_changed)
        elif param_type == "bool":
            widget.toggled.connect(self._on_value_changed)
        elif param_type == "choice":
            widget.currentTextChanged.connect(self._on_value_changed)
        elif param_type == "str":
            widget.editingFinished.connect(self._on_value_changed)

    def _on_value_changed(self, *_args):
        self.settings_changed.emit(self._get_values())

    def _on_accept(self):
        self.settings_changed.emit(self._get_values())
        self.accept()
