# SPDX-License-Identifier: MIT

"""Declarative two-way bindings between Qt widgets and model attributes.

A :class:`Binder` replaces hand-written ``update_gui`` methods and their
``blockSignals`` sandwiches. Each binding declares two directions once:

- widget → model: the widget's edit signal writes through the owner's
  (side-effectful) property setter.
- model → widget: a render function reads the model and updates the
  widget(s); the binder blocks the widgets' Qt signals while rendering, so
  rendering can never re-trigger the widget→model path.

``refresh()`` re-renders every binding; hook it via ``connect_refresh`` to
the signals that indicate the underlying model changed wholesale (e.g.
``configuration_selected``). Owners are passed as callables (e.g.
``lambda: model.current_configuration``) and resolved at every access, so
bindings never go stale when the current configuration changes.

With *field_events* (a signal emitting ``(field, new, old)``, e.g.
``DioptasModel.configuration_params_changed``), field bindings additionally
re-render individually whenever their field changes in the model — no
matter who changed it (another controller, a script, the pipeline).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

__all__ = ["Binder"]


class _Binding:
    def __init__(self, render_fn: Callable[[], None], widgets: tuple) -> None:
        self._render_fn = render_fn
        self._widgets = widgets

    def render(self) -> None:
        for widget in self._widgets:
            widget.blockSignals(True)
        try:
            self._render_fn()
        finally:
            for widget in self._widgets:
                widget.blockSignals(False)


class Binder:
    def __init__(self, field_events: Any = None) -> None:
        self._bindings: list[_Binding] = []
        self._bindings_by_field: dict[str, list[_Binding]] = {}
        if field_events is not None:
            field_events.connect(self._on_field_changed)

    def _on_field_changed(self, field: str, new: Any = None, old: Any = None) -> None:
        for binding in self._bindings_by_field.get(field, ()):
            binding.render()

    def _register(self, binding: _Binding, field: str | None) -> None:
        self._bindings.append(binding)
        if field is not None:
            self._bindings_by_field.setdefault(field, []).append(binding)

    def refresh(self) -> None:
        """Re-renders all bindings from the current model state."""
        for binding in self._bindings:
            binding.render()

    def connect_refresh(self, signal: Any) -> None:
        """Re-renders everything whenever *signal* fires."""
        signal.connect(self.refresh)

    def add_render(
        self, render_fn: Callable[[], None], *widgets: Any, field: str | None = None
    ) -> None:
        """Registers a model→widget render; *widgets* have their Qt signals
        blocked while it runs. For display-only values, this is the whole
        binding. With *field*, the render also runs on matching field
        events."""
        self._register(_Binding(render_fn, widgets), field)

    def bind_checkbox(
        self,
        checkbox: Any,
        owner: Callable[[], Any],
        field: str,
        event_field: str | None = None,
    ) -> None:
        """Two-way binding for a QCheckBox-like widget (toggled/isChecked).

        *event_field* overrides the field-event name to react to when it
        differs from the attribute name (e.g. namespaced sub-model fields
        like "img.factor")."""
        checkbox.toggled.connect(
            lambda checked: setattr(owner(), field, bool(checked))
        )
        self.add_render(
            lambda: checkbox.setChecked(bool(getattr(owner(), field))),
            checkbox,
            field=event_field or field,
        )

    def bind_number_field(
        self,
        line_edit: Any,
        owner: Callable[[], Any],
        field: str,
        dtype: Callable[[Any], Any] = float,
        fmt: Callable[[Any], str] = str,
        event_field: str | None = None,
    ) -> None:
        """Two-way binding for a QLineEdit-like numeric field.

        The widget writes on editingFinished; invalid input is ignored and
        the field re-renders from the model on the next refresh."""

        def apply() -> None:
            try:
                value = dtype(line_edit.text())
            except (TypeError, ValueError):
                return
            setattr(owner(), field, value)

        line_edit.editingFinished.connect(apply)
        self.add_render(
            lambda: line_edit.setText(fmt(getattr(owner(), field))),
            line_edit,
            field=event_field or field,
        )

    def bind_radio_pair(
        self,
        true_btn: Any,
        false_btn: Any,
        owner: Callable[[], Any],
        field: str,
        event_field: str | None = None,
        on_changed: Callable[[bool], None] | None = None,
    ) -> None:
        """Two-way binding for two mutually exclusive buttons representing a
        boolean field.

        *on_changed* runs after every render with the current value — use it
        for display side effects that follow the setting."""
        true_btn.clicked.connect(lambda: setattr(owner(), field, True))
        false_btn.clicked.connect(lambda: setattr(owner(), field, False))

        def render() -> None:
            value = bool(getattr(owner(), field))
            # auto-exclusive buttons ignore setChecked(False), so unchecking
            # is done with exclusivity temporarily disabled — this must not
            # depend on the two buttons sharing a parent
            for button, state in ((true_btn, value), (false_btn, not value)):
                exclusive = button.autoExclusive()
                button.setAutoExclusive(False)
                button.setChecked(state)
                button.setAutoExclusive(exclusive)
            if on_changed is not None:
                on_changed(value)

        self.add_render(render, true_btn, false_btn, field=event_field or field)

    def bind_spinbox(
        self,
        spinbox: Any,
        owner: Callable[[], Any],
        field: str,
        dtype: Callable[[Any], Any] = int,
        event_field: str | None = None,
    ) -> None:
        """Two-way binding for a QSpinBox-like widget (valueChanged/value)."""
        spinbox.valueChanged.connect(
            lambda *args: setattr(owner(), field, dtype(spinbox.value()))
        )
        self.add_render(
            lambda: spinbox.setValue(getattr(owner(), field)),
            spinbox,
            field=event_field or field,
        )

    def mirror_toggles(
        self,
        *toggles: Any,
        on_toggled: Callable[[bool], None],
    ) -> Callable[[bool], None]:
        """Keeps several checkable widgets showing the same state.

        Toggling any of them syncs the others (with their signals blocked)
        and invokes *on_toggled* exactly once. Returns a ``set_checked``
        function for programmatic state changes that syncs all widgets
        without invoking *on_toggled*."""

        def set_checked(checked: bool) -> None:
            for toggle in toggles:
                toggle.blockSignals(True)
                toggle.setChecked(checked)
                toggle.blockSignals(False)

        def handler(checked: bool) -> None:
            set_checked(checked)
            on_toggled(checked)

        for toggle in toggles:
            toggle.toggled.connect(handler)
        return set_checked

    def bind_optional_range(
        self,
        min_txt: Any,
        max_txt: Any,
        full_btn: Any,
        owner: Callable[[], Any],
        field: str,
        on_full_changed: Callable[[bool], None] | None = None,
    ) -> None:
        """Binding for an optional (min, max) range edited via two number
        text fields and a "Full" toggle button.

        The model field is None while the full range is selected. Unchecking
        the toggle applies the current text field values; checking it sets
        the field to None. The text fields are disabled while the full range
        is active. *on_full_changed* is called with the new full-state after
        every render for additional widget side effects."""

        def apply_range() -> None:
            setattr(
                owner(), field, (float(min_txt.text()), float(max_txt.text()))
            )

        def toggled(checked: bool) -> None:
            if checked:
                setattr(owner(), field, None)
            else:
                apply_range()
            render_binding.render()

        def render() -> None:
            value = getattr(owner(), field)
            is_full = value is None
            full_btn.setChecked(is_full)
            min_txt.setDisabled(is_full)
            max_txt.setDisabled(is_full)
            if not is_full:
                min_txt.setText(str(value[0]))
                max_txt.setText(str(value[1]))
            if on_full_changed is not None:
                on_full_changed(is_full)

        min_txt.editingFinished.connect(apply_range)
        max_txt.editingFinished.connect(apply_range)
        full_btn.toggled.connect(toggled)
        render_binding = _Binding(render, (min_txt, max_txt, full_btn))
        self._register(render_binding, field)
