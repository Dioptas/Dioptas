# SPDX-License-Identifier: MIT

"""The GUI side of undo/redo: buttons, shortcuts, and view refreshes."""

import numpy as np
import pytest
from qtpy import QtCore, QtGui

from dioptas.controller.MaskController import MaskController
from dioptas.model.DioptasModel import DioptasModel
from dioptas.widgets.MaskWidget import MaskWidget


@pytest.fixture
def model():
    m = DioptasModel()
    m.img_model._img_data = np.zeros((50, 50))
    m.img_model.img_changed.emit()
    m.history.reset()
    return m


@pytest.fixture
def mask_widget(qapp, qtbot):
    widget = MaskWidget()
    qtbot.addWidget(widget)
    yield widget
    widget.close()


@pytest.fixture
def mask_controller(mask_widget, model):
    return MaskController(mask_widget, model)


# ---------------------------------------------------------------------------
# mask mode: no undo/redo buttons of its own any more — the sidebar pair is
# application-wide — but the view still has to follow the shared history
# ---------------------------------------------------------------------------


def test_mask_mode_has_no_undo_redo_buttons(mask_widget):
    """A second pair in one mode is the duplication the shared history removed."""
    assert not hasattr(mask_widget, "undo_btn")
    assert not hasattr(mask_widget, "redo_btn")


def test_plugin_checkboxes_follow_the_history(mask_controller, mask_widget, model):
    """Undoing an imprint re-enables the plugin, and the checkbox has to say so
    however the undo was triggered."""
    seen = []
    mask_controller._update_plugin_checkboxes = lambda: seen.append(1)
    model.history.changed.connect(mask_controller._update_plugin_checkboxes)

    model.mask_model.mask_rect(10, 10, 5, 5)
    model.history.undo()
    assert seen


def test_undo_from_elsewhere_still_refreshes_this_view(
    mask_controller, mask_widget, model
):
    """An undo triggered by the global shortcut must repaint the mask, not
    only one triggered by this controller's own button."""
    model.mask_model.mask_rect(10, 10, 5, 5)
    plotted = []
    mask_widget.img_widget.plot_mask = lambda mask: plotted.append(mask.sum())

    model.history.undo()  # as the application-wide shortcut would
    assert plotted and plotted[-1] == 0


def test_main_controller_binds_undo_shortcuts(main_controller):
    """Ctrl+Z / Ctrl+Y / Ctrl+Shift+Z reach the model's history in any mode."""
    model = main_controller.model
    model.img_model._img_data = np.zeros((50, 50))
    model.img_model.img_changed.emit()
    model.history.reset()

    model.current_configuration.integration_unit = "q_A^-1"
    assert model.history.can_undo is True

    main_controller.undo()
    assert model.current_configuration.integration_unit == "2th_deg"
    main_controller.redo()
    assert model.current_configuration.integration_unit == "q_A^-1"

    bound = {
        s.key().toString()
        for s in main_controller.widget.findChildren(QtGui.QShortcut)
    }
    assert QtGui.QKeySequence(QtGui.QKeySequence.StandardKey.Undo).toString() in bound
    assert "Ctrl+Y" in bound


# ---------------------------------------------------------------------------
# the sidebar buttons — the only visible affordance outside mask mode
# ---------------------------------------------------------------------------


def test_sidebar_buttons_sit_between_the_menu_and_the_modes(main_controller):
    """They act on the whole session, so they belong with the global actions
    at the top rather than below the mode buttons."""
    widget = main_controller.widget
    assert widget.undo_btn.y() > widget.menu_btn.y()
    assert widget.undo_btn.y() < widget.calibration_mode_btn.y()
    # side by side, the conventional arrangement for the pair
    assert widget.redo_btn.x() > widget.undo_btn.x()
    assert widget.redo_btn.y() == widget.undo_btn.y()
    # small and centred rather than filling the column: these are quick
    # actions, not modes
    pair = widget.undo_btn.width() + widget.redo_btn.width()
    assert pair < widget.calibration_mode_btn.width()
    assert widget.undo_btn.height() < widget.calibration_mode_btn.height() / 2


def test_sidebar_buttons_use_icons_not_text(main_controller):
    widget = main_controller.widget
    for button in (widget.undo_btn, widget.redo_btn):
        assert button.text() == ""
        assert not button.icon().isNull()


def test_disabled_history_button_shows_a_faded_icon(main_controller):
    """The greyed icon is the whole disabled cue — the buttons carry no
    background of their own. Qt draws through the stylesheet style, which
    ignores an icon's disabled mode, so the faded icon is swapped in by hand
    and this guards that it actually happens."""
    from qtpy import QtCore

    model, widget = main_controller.model, main_controller.widget

    def ink(button):
        image = button.icon().pixmap(QtCore.QSize(14, 14)).toImage()
        return sum(
            image.pixelColor(x, y).alpha()
            for y in range(image.height())
            for x in range(image.width())
        )

    faded = ink(widget.undo_btn)          # nothing to undo yet
    model.current_configuration.integration_unit = "q_A^-1"
    assert ink(widget.undo_btn) > faded * 2


def test_sidebar_buttons_start_disabled(main_controller):
    assert main_controller.widget.undo_btn.isEnabled() is False
    assert main_controller.widget.redo_btn.isEnabled() is False


def test_sidebar_buttons_drive_the_history(main_controller, qtbot):
    model, widget = main_controller.model, main_controller.widget
    model.img_model._img_data = np.zeros((50, 50))
    model.img_model.img_changed.emit()
    model.history.reset()

    model.current_configuration.integration_unit = "q_A^-1"
    assert widget.undo_btn.isEnabled() is True

    qtbot.mouseClick(widget.undo_btn, QtCore.Qt.MouseButton.LeftButton)
    assert model.current_configuration.integration_unit == "2th_deg"
    assert widget.redo_btn.isEnabled() is True

    qtbot.mouseClick(widget.redo_btn, QtCore.Qt.MouseButton.LeftButton)
    assert model.current_configuration.integration_unit == "q_A^-1"


def test_sidebar_tooltips_name_the_step_and_the_shortcut(main_controller):
    model, widget = main_controller.model, main_controller.widget
    model.img_model._img_data = np.zeros((50, 50))
    model.img_model.img_changed.emit()
    model.history.reset()

    shortcut = QtGui.QKeySequence(QtGui.QKeySequence.StandardKey.Undo).toString(
        QtGui.QKeySequence.SequenceFormat.NativeText
    )
    assert "Nothing to undo" in widget.undo_btn.toolTip()
    assert shortcut in widget.undo_btn.toolTip()

    model.current_configuration.integration_unit = "q_A^-1"
    assert "integration unit" in widget.undo_btn.toolTip()
    assert shortcut in widget.undo_btn.toolTip()


def test_redo_shortcut_shown_is_the_z_variant(main_controller):
    """Reads better beside the undo shortcut, and is the macOS convention."""
    from dioptas.controller.MainController import _shortcut_text

    assert _shortcut_text(QtGui.QKeySequence.StandardKey.Redo).endswith("Z")
