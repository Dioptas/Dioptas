# SPDX-License-Identifier: MIT

import pytest
from qtpy import QtWidgets

from dioptas.controller.binding import Binder


class Settings:
    def __init__(self):
        self.flag = False
        self.points = 360
        self.range = None
        self.writes = []

    def __setattr__(self, name, value):
        if name != "writes" and hasattr(self, "writes"):
            self.writes.append((name, value))
        super().__setattr__(name, value)


@pytest.fixture
def settings():
    return Settings()


@pytest.fixture
def binder():
    return Binder()


def test_checkbox_binding_widget_to_model(qapp, binder, settings):
    checkbox = QtWidgets.QCheckBox()
    binder.bind_checkbox(checkbox, lambda: settings, "flag")

    checkbox.setChecked(True)
    assert settings.flag is True
    checkbox.setChecked(False)
    assert settings.flag is False


def test_checkbox_binding_render(qapp, binder, settings):
    checkbox = QtWidgets.QCheckBox()
    binder.bind_checkbox(checkbox, lambda: settings, "flag")

    settings.flag = True
    binder.refresh()
    assert checkbox.isChecked() is True


def test_render_does_not_write_back(qapp, binder, settings):
    """Rendering must never trigger the widget→model path."""
    checkbox = QtWidgets.QCheckBox()
    binder.bind_checkbox(checkbox, lambda: settings, "flag")

    settings.flag = True
    settings.writes.clear()
    binder.refresh()
    assert settings.writes == []


def test_spinbox_binding(qapp, binder, settings):
    spinbox = QtWidgets.QSpinBox()
    spinbox.setMaximum(10000)
    binder.bind_spinbox(spinbox, lambda: settings, "points")

    spinbox.setValue(720)
    assert settings.points == 720

    settings.points = 500
    binder.refresh()
    assert spinbox.value() == 500


def test_owner_resolved_at_access_time(qapp, binder):
    """Bindings follow the callable owner — no stale references."""
    first, second = Settings(), Settings()
    current = {"owner": first}
    checkbox = QtWidgets.QCheckBox()
    binder.bind_checkbox(checkbox, lambda: current["owner"], "flag")

    checkbox.setChecked(True)
    assert first.flag is True and second.flag is False

    current["owner"] = second
    checkbox.setChecked(False)
    assert first.flag is True and second.flag is False


def _make_range_widgets():
    min_txt = QtWidgets.QLineEdit("-180")
    max_txt = QtWidgets.QLineEdit("180")
    full_btn = QtWidgets.QPushButton()
    full_btn.setCheckable(True)
    full_btn.setChecked(True)
    return min_txt, max_txt, full_btn


def test_optional_range_toggle_off_applies_text_values(qapp, binder, settings):
    min_txt, max_txt, full_btn = _make_range_widgets()
    binder.bind_optional_range(min_txt, max_txt, full_btn, lambda: settings, "range")

    full_btn.setChecked(False)
    assert settings.range == (-180.0, 180.0)
    assert min_txt.isEnabled() and max_txt.isEnabled()

    min_txt.setText("-90")
    min_txt.editingFinished.emit()
    assert settings.range == (-90.0, 180.0)


def test_optional_range_toggle_on_sets_none(qapp, binder, settings):
    min_txt, max_txt, full_btn = _make_range_widgets()
    binder.bind_optional_range(min_txt, max_txt, full_btn, lambda: settings, "range")

    full_btn.setChecked(False)
    full_btn.setChecked(True)
    assert settings.range is None
    assert not min_txt.isEnabled() and not max_txt.isEnabled()


def test_optional_range_render_syncs_toggle_state(qapp, binder, settings):
    """Rendering reflects the model even when it changed behind the GUI."""
    min_txt, max_txt, full_btn = _make_range_widgets()
    binder.bind_optional_range(min_txt, max_txt, full_btn, lambda: settings, "range")

    settings.range = (-30.0, 30.0)
    binder.refresh()
    assert full_btn.isChecked() is False
    assert min_txt.text() == "-30.0"
    assert max_txt.text() == "30.0"

    settings.range = None
    binder.refresh()
    assert full_btn.isChecked() is True
    assert not min_txt.isEnabled()


def test_optional_range_on_full_changed_callback(qapp, binder, settings):
    min_txt, max_txt, full_btn = _make_range_widgets()
    states = []
    binder.bind_optional_range(
        min_txt,
        max_txt,
        full_btn,
        lambda: settings,
        "range",
        on_full_changed=states.append,
    )
    full_btn.setChecked(False)
    assert states[-1] is False
    full_btn.setChecked(True)
    assert states[-1] is True


def test_connect_refresh(qapp, binder, settings):
    from dioptas.model.util.signal import Signal

    checkbox = QtWidgets.QCheckBox()
    binder.bind_checkbox(checkbox, lambda: settings, "flag")

    changed = Signal()
    binder.connect_refresh(changed)
    settings.flag = True
    changed.emit()
    assert checkbox.isChecked() is True


def test_mirror_toggles(qapp, binder):
    a = QtWidgets.QCheckBox()
    b = QtWidgets.QCheckBox()
    events = []
    set_checked = binder.mirror_toggles(a, b, on_toggled=events.append)

    a.setChecked(True)
    assert b.isChecked() is True
    assert events == [True]  # handler ran exactly once despite two widgets

    b.setChecked(False)
    assert a.isChecked() is False
    assert events == [True, False]

    # programmatic sync must not invoke the handler
    set_checked(True)
    assert a.isChecked() and b.isChecked()
    assert events == [True, False]


def test_field_events_render_individual_bindings(qapp, settings):
    from dioptas.model.util.signal import Signal

    field_events = Signal(str, object, object)
    binder = Binder(field_events=field_events)

    checkbox = QtWidgets.QCheckBox()
    spinbox = QtWidgets.QSpinBox()
    spinbox.setMaximum(10000)
    binder.bind_checkbox(checkbox, lambda: settings, "flag")
    binder.bind_spinbox(spinbox, lambda: settings, "points")

    settings.flag = True
    settings.points = 999
    field_events.emit("flag", True, False)

    assert checkbox.isChecked() is True
    assert spinbox.value() != 999  # only the matching binding rendered

    field_events.emit("points", 999, 360)
    assert spinbox.value() == 999


def test_number_field_binding(qapp, binder, settings):
    field = QtWidgets.QLineEdit()
    binder.bind_number_field(field, lambda: settings, "points", dtype=float)

    field.setText("2.5")
    field.editingFinished.emit()
    assert settings.points == 2.5

    settings.points = 7.0
    binder.refresh()
    assert field.text() == "7.0"


def test_number_field_binding_ignores_invalid_input(qapp, binder, settings):
    field = QtWidgets.QLineEdit()
    binder.bind_number_field(field, lambda: settings, "points", dtype=float)

    settings.points = 5.0
    field.setText("not a number")
    field.editingFinished.emit()
    assert settings.points == 5.0  # unchanged


def test_radio_pair_binding(qapp, binder, settings):
    true_btn = QtWidgets.QRadioButton()
    false_btn = QtWidgets.QRadioButton()
    seen = []
    binder.bind_radio_pair(
        true_btn, false_btn, lambda: settings, "flag", on_changed=seen.append
    )

    true_btn.click()
    assert settings.flag is True
    false_btn.click()
    assert settings.flag is False

    settings.flag = True
    binder.refresh()
    assert true_btn.isChecked() and not false_btn.isChecked()
    assert seen[-1] is True  # display side effect follows the setting
