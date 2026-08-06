# SPDX-License-Identifier: MIT

from __future__ import annotations

from qtpy import QtWidgets, QtCore, QtGui

from .CustomWidgets import IconActionButton


class _InfoIcon(QtWidgets.QLabel):
    """Small circled 'i' icon that shows a tooltip immediately on hover."""

    def __init__(self, tooltip: str, parent=None):
        super().__init__(parent)
        self.setToolTip(tooltip)
        self.setCursor(QtCore.Qt.CursorShape.WhatsThisCursor)

        # Draw a circled "i" as a pixmap
        size = 16
        pixmap = QtGui.QPixmap(size, size)
        pixmap.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.setPen(QtGui.QPen(QtGui.QColor(120, 120, 120), 1.2))
        painter.drawEllipse(1, 1, size - 3, size - 3)
        font = painter.font()
        font.setBold(True)
        font.setPixelSize(11)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, "i")
        painter.end()
        self.setPixmap(pixmap)

    def enterEvent(self, event):
        pos = self.mapToGlobal(QtCore.QPoint(self.width(), 0))
        QtWidgets.QToolTip.showText(pos, self.toolTip(), self)
        super().enterEvent(event)


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
    ) -> tuple[QtWidgets.QCheckBox, QtWidgets.QPushButton | None, QtWidgets.QPushButton]:
        """Add a row for a plugin. Returns (checkbox, settings_btn or None, imprint_btn)."""
        row = _PluginRow(name, has_settings, self)
        self._plugin_rows[name] = row
        self._layout.addWidget(row)
        return row.checkbox, row.settings_btn, row.imprint_btn

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
            # the same gear the rest of the application uses for settings —
            # the previous standard icon was a file-list glyph
            self.settings_btn = IconActionButton(
                "settings.svg", f"Settings for {name}"
            )
            self.settings_btn.setFixedSize(24, 24)
            layout.addWidget(self.settings_btn)

        # a stamp, not the letter "I": that read as the Inspect buttons of
        # the integration view, which do something entirely different
        self.imprint_btn = IconActionButton(
            "mask_imprint.svg",
            f"Imprint\n\n"
            f"Bakes the current {name} mask into the user-drawn mask\n"
            f"and disables the plugin.",
        )
        self.imprint_btn.setFixedSize(24, 24)
        self.imprint_btn.setEnabled(False)  # only enabled when plugin is on
        layout.addWidget(self.imprint_btn)


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
            self._widgets[key] = widget

            description = spec.get("description")
            if description:
                row_widget = QtWidgets.QWidget()
                row_layout = QtWidgets.QHBoxLayout(row_widget)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.setSpacing(4)
                row_layout.addWidget(widget, stretch=1)
                info_icon = _InfoIcon(
                    f"<p style='max-width:300px;'>{description}</p>",
                )
                info_icon.setFixedSize(16, 16)
                row_layout.addWidget(info_icon)
                form_layout.addRow(label, row_widget)
            else:
                form_layout.addRow(label, widget)

        layout.addLayout(form_layout)

        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
            | QtWidgets.QDialogButtonBox.StandardButton.RestoreDefaults
        )
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        restore_button = button_box.button(
            QtWidgets.QDialogButtonBox.StandardButton.RestoreDefaults
        )
        restore_button.setToolTip("Set every value back to the plugin's defaults")
        restore_button.clicked.connect(self.restore_defaults)
        layout.addWidget(button_box)

    def _create_widget(self, param_type: str, spec: dict, value) -> QtWidgets.QWidget:
        if param_type == "float":
            widget = QtWidgets.QDoubleSpinBox()
            widget.setDecimals(spec.get("decimals", 4))
            widget.setRange(
                spec.get("min", -1e12),
                spec.get("max", 1e12),
            )
            if "step" in spec:
                widget.setSingleStep(spec["step"])
            if value is not None:
                widget.setValue(float(value))
            return widget

        elif param_type == "int":
            widget = QtWidgets.QSpinBox()
            widget.setRange(
                spec.get("min", -2**31),
                spec.get("max", 2**31 - 1),
            )
            if "step" in spec:
                widget.setSingleStep(spec["step"])
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

    def restore_defaults(self):
        """Sets every field back to its schema default.

        Goes through the widgets rather than the plugin, so the change flows
        through the same live-update path as manual edits — including undo.
        Widget signals are blocked during the loop and one change is emitted
        at the end: per-field emissions would recompute the mask once per
        field and leave one undo step each.
        """
        for key, widget in self._widgets.items():
            spec = self._schema[key]
            default = spec.get("default")
            if default is None:
                continue
            param_type = spec.get("type", "str")
            blocker = QtCore.QSignalBlocker(widget)
            try:
                if param_type in ("float", "int"):
                    widget.setValue(default)
                elif param_type == "bool":
                    widget.setChecked(bool(default))
                elif param_type == "choice":
                    widget.setCurrentText(str(default))
                else:
                    widget.setText(str(default))
            finally:
                del blocker
        self._on_value_changed()

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
