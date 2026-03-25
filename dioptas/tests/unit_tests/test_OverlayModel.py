# SPDX-License-Identifier: MIT

import os
import numpy as np
import pytest
from unittest.mock import MagicMock

from ...model.OverlayModel import OverlayModel

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, "../data")


@pytest.fixture
def overlay_model():
    return OverlayModel()


def test_add_overlay(overlay_model: OverlayModel):
    x_overlay = np.linspace(0, 10)
    y_overlay = np.linspace(0, 100)
    overlay_model.add_overlay(x_overlay, y_overlay, "dummy")

    assert len(overlay_model.overlays) == 1

    new_overlay = overlay_model.get_overlay(0)
    assert new_overlay is not None
    assert new_overlay.name == "dummy"
    assert np.array_equal(new_overlay.x, x_overlay)
    assert np.array_equal(new_overlay.y, y_overlay)


def test_add_overlay_from_file(overlay_model: OverlayModel):
    filename = os.path.join(data_path, "pattern_001.xy")
    overlay_model.add_overlay_file(filename)

    assert len(overlay_model.overlays) == 1
    overlay = overlay_model.get_overlay(0)
    assert overlay is not None
    assert overlay.name == "".join(os.path.basename(filename).split(".")[0:-1])


def test_different_colors_for_overlay(overlay_model: OverlayModel):
    x_overlay = np.linspace(0, 10)
    y_overlay = np.linspace(0, 100)
    overlay_model.add_overlay(x_overlay, y_overlay, "dummy")
    overlay_model.add_overlay(x_overlay, y_overlay, "dummy")
    overlay_model.add_overlay(x_overlay, y_overlay, "dummy")

    assert len(overlay_model.overlays) == 3

    color1 = overlay_model.get_overlay_color(0)
    color2 = overlay_model.get_overlay_color(1)
    color3 = overlay_model.get_overlay_color(2)

    assert not np.array_equal(color1, color2)
    assert not np.array_equal(color2, color3)
    assert not np.array_equal(color1, color3)


def test_move_up_overlay(overlay_model: OverlayModel):
    x_overlay = np.linspace(0, 10)
    y_overlay = np.linspace(0, 100)
    overlay_model.add_overlay(x_overlay, y_overlay, "dummy1")
    overlay_model.add_overlay(x_overlay, y_overlay, "dummy2")
    overlay_model.add_overlay(x_overlay, y_overlay, "dummy3")

    overlay_model.move_overlay_up(1)

    overlay1 = overlay_model.get_overlay(0)
    overlay2 = overlay_model.get_overlay(1)
    overlay3 = overlay_model.get_overlay(2)

    assert overlay1 is not None
    assert overlay2 is not None
    assert overlay3 is not None

    assert overlay1.name == "dummy2"
    assert overlay2.name == "dummy1"
    assert overlay3.name == "dummy3"


def test_move_down_overlay(overlay_model: OverlayModel):
    x_overlay = np.linspace(0, 10)
    y_overlay = np.linspace(0, 100)
    overlay_model.add_overlay(x_overlay, y_overlay, "dummy1")
    overlay_model.add_overlay(x_overlay, y_overlay, "dummy2")
    overlay_model.add_overlay(x_overlay, y_overlay, "dummy3")

    overlay_model.move_overlay_down(1)

    overlay1 = overlay_model.get_overlay(0)
    overlay2 = overlay_model.get_overlay(1)
    overlay3 = overlay_model.get_overlay(2)

    assert overlay1 is not None
    assert overlay2 is not None
    assert overlay3 is not None

    assert overlay1.name == "dummy1"
    assert overlay2.name == "dummy3"
    assert overlay3.name == "dummy2"


def test_move_signals(overlay_model: OverlayModel):
    for i in range(10):
        overlay_model.add_overlay(np.linspace(0, 10), np.linspace(0, 100), f"dummy{i}")

    overlay_model.overlay_changed.emit = MagicMock()
    overlay_model.move_overlay_up(1)

    assert overlay_model.overlay_changed.emit.call_count == 2
    overlay_model.overlay_changed.emit.assert_any_call(1)
    overlay_model.overlay_changed.emit.assert_any_call(0)

    overlay_model.overlay_changed.emit.reset_mock()
    overlay_model.move_overlay_down(3)
    assert overlay_model.overlay_changed.emit.call_count == 2
    overlay_model.overlay_changed.emit.assert_any_call(3)
    overlay_model.overlay_changed.emit.assert_any_call(4)


def test_remove_overlay(overlay_model: OverlayModel):
    x = np.linspace(0, 10)
    y = np.linspace(0, 100)
    overlay_model.add_overlay(x, y, "first")
    overlay_model.add_overlay(x, y, "second")

    overlay_model.overlay_removed.emit = MagicMock()
    overlay_model.remove_overlay(0)

    assert len(overlay_model.overlays) == 1
    assert overlay_model.overlays[0].name == "second"
    overlay_model.overlay_removed.emit.assert_called_once_with(0)


def test_get_overlay_invalid_index(overlay_model: OverlayModel):
    assert overlay_model.get_overlay(0) is None
    overlay_model.add_overlay(np.linspace(0, 10), np.linspace(0, 100), "dummy")
    assert overlay_model.get_overlay(5) is None


def test_set_and_get_overlay_scaling(overlay_model: OverlayModel):
    overlay_model.add_overlay(np.linspace(0, 10), np.linspace(0, 100), "dummy")

    overlay_model.overlay_changed.emit = MagicMock()
    overlay_model.set_overlay_scaling(0, 2.5)

    assert overlay_model.get_overlay_scaling(0) == 2.5
    overlay_model.overlay_changed.emit.assert_called_once_with(0)


def test_set_and_get_overlay_offset(overlay_model: OverlayModel):
    overlay_model.add_overlay(np.linspace(0, 10), np.linspace(0, 100), "dummy")

    overlay_model.overlay_changed.emit = MagicMock()
    overlay_model.set_overlay_offset(0, 3.0)

    assert overlay_model.get_overlay_offset(0) == 3.0
    overlay_model.overlay_changed.emit.assert_called_once_with(0)


def test_set_overlay_visible(overlay_model: OverlayModel):
    overlay_model.add_overlay(np.linspace(0, 10), np.linspace(0, 100), "dummy")

    overlay_model.overlay_changed.emit = MagicMock()
    overlay_model.set_overlay_visible(0, False)

    assert overlay_model.overlays[0].visible is False
    overlay_model.overlay_changed.emit.assert_called_once_with(0)


def test_set_and_get_overlay_color(overlay_model: OverlayModel):
    overlay_model.add_overlay(np.linspace(0, 10), np.linspace(0, 100), "dummy")

    overlay_model.overlay_changed.emit = MagicMock()
    overlay_model.set_overlay_color(0, "#FF0000")

    assert overlay_model.get_overlay_color(0) == "#FF0000"
    overlay_model.overlay_changed.emit.assert_called_once_with(0)


def test_set_and_get_overlay_name(overlay_model: OverlayModel):
    overlay_model.add_overlay(np.linspace(0, 10), np.linspace(0, 100), "dummy")

    overlay_model.overlay_changed.emit = MagicMock()
    overlay_model.set_overlay_name(0, "renamed")

    assert overlay_model.get_overlay_name(0) == "renamed"
    overlay_model.overlay_changed.emit.assert_called_once_with(0)


def test_overlay_waterfall(overlay_model: OverlayModel):
    x = np.linspace(0, 10)
    y = np.linspace(0, 100)
    overlay_model.add_overlay(x, y, "first")
    overlay_model.add_overlay(x, y, "second")
    overlay_model.add_overlay(x, y, "third")

    overlay_model.overlay_changed.emit = MagicMock()
    overlay_model.overlay_waterfall(10.0)

    # Waterfall applies increasing negative offsets from the last overlay
    assert overlay_model.overlays[2].offset == -10.0
    assert overlay_model.overlays[1].offset == -20.0
    assert overlay_model.overlays[0].offset == -30.0
    assert overlay_model.overlay_changed.emit.call_count == 3


def test_reset_overlay_offsets(overlay_model: OverlayModel):
    x = np.linspace(0, 10)
    y = np.linspace(0, 100)
    overlay_model.add_overlay(x, y, "first")
    overlay_model.add_overlay(x, y, "second")
    overlay_model.overlays[0].offset = 5.0
    overlay_model.overlays[1].offset = 10.0

    overlay_model.overlay_changed.emit = MagicMock()
    overlay_model.reset_overlay_offsets()

    assert overlay_model.overlays[0].offset == 0
    assert overlay_model.overlays[1].offset == 0
    assert overlay_model.overlay_changed.emit.call_count == 2


def test_reset(overlay_model: OverlayModel):
    x = np.linspace(0, 10)
    y = np.linspace(0, 100)
    overlay_model.add_overlay(x, y, "first")
    overlay_model.add_overlay(x, y, "second")
    overlay_model.add_overlay(x, y, "third")

    overlay_model.overlay_removed.emit = MagicMock()
    overlay_model.reset()

    assert len(overlay_model.overlays) == 0
    assert overlay_model.overlay_removed.emit.call_count == 3
