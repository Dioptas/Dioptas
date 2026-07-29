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


def test_buttons_start_disabled(mask_controller, mask_widget):
    assert mask_widget.undo_btn.isEnabled() is False
    assert mask_widget.redo_btn.isEnabled() is False


def test_buttons_follow_the_history(mask_controller, mask_widget, model):
    model.mask_model.mask_rect(10, 10, 5, 5)
    assert mask_widget.undo_btn.isEnabled() is True
    assert mask_widget.redo_btn.isEnabled() is False

    model.history.undo()
    assert mask_widget.undo_btn.isEnabled() is False
    assert mask_widget.redo_btn.isEnabled() is True


def test_buttons_react_to_a_settings_change_made_elsewhere(
    mask_controller, mask_widget, model
):
    """The stack is global, so a change in another mode enables undo here."""
    model.current_configuration.integration_unit = "q_A^-1"
    assert mask_widget.undo_btn.isEnabled() is True


def test_tooltip_names_the_step(mask_controller, mask_widget, model):
    model.current_configuration.integration_unit = "q_A^-1"
    assert "integration unit" in mask_widget.undo_btn.toolTip()

    model.history.undo()
    assert "integration unit" in mask_widget.redo_btn.toolTip()
    assert mask_widget.undo_btn.toolTip() == "Nothing to undo"


def test_undo_button_reverts_the_mask(mask_controller, mask_widget, model, qtbot):
    model.mask_model.mask_rect(10, 10, 5, 5)
    assert model.mask_model.get_img().sum() > 0

    qtbot.mouseClick(mask_widget.undo_btn, QtCore.Qt.MouseButton.LeftButton)
    assert model.mask_model.get_img().sum() == 0

    qtbot.mouseClick(mask_widget.redo_btn, QtCore.Qt.MouseButton.LeftButton)
    assert model.mask_model.get_img().sum() > 0


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


def test_sidebar_buttons_sit_below_the_mode_buttons(main_controller):
    widget = main_controller.widget
    assert widget.undo_btn.y() > widget.map_mode_btn.y()
    assert widget.redo_btn.y() > widget.undo_btn.y()


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
