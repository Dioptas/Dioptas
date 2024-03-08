# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
# Principal author: Clemens Prescher (clemens.prescher@gmail.com)
# Copyright (C) 2014-2019 GSECARS, University of Chicago, USA
# Copyright (C) 2015-2018 Institute for Geology and Mineralogy, University of Cologne, Germany
# Copyright (C) 2019-2020 DESY, Hamburg, Germany
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import numpy as np
import pytest
from unittest.mock import MagicMock

from ...model.OverlayModel import OverlayModel
from ...model.util import Pattern

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')


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
    filename = os.path.join(data_path, 'pattern_001.xy')
    overlay_model.add_overlay_file(filename)

    assert len(overlay_model.overlays) == 1
    overlay = overlay_model.get_overlay(0)
    assert overlay is not None
    assert overlay.name == ''.join(os.path.basename(filename).split('.')[0:-1])


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

    overlay_model.move_up_overlay(1)

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

    overlay_model.move_down_overlay(1)

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
    overlay_model.move_up_overlay(1)

    assert overlay_model.overlay_changed.emit.call_count == 2
    overlay_model.overlay_changed.emit.assert_any_call(1)
    overlay_model.overlay_changed.emit.assert_any_call(0)

    overlay_model.overlay_changed.emit.reset_mock()
    overlay_model.move_down_overlay(3)
    assert overlay_model.overlay_changed.emit.call_count == 2
    overlay_model.overlay_changed.emit.assert_any_call(3)
    overlay_model.overlay_changed.emit.assert_any_call(4)
