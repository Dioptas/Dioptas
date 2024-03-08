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

import pytest
import numpy as np

from dioptas.controller.integration.overlay.OverlayInPatternController import (
    OverlayInPatternController,
)
from dioptas.widgets.integration import IntegrationWidget
from dioptas.widgets.plot_widgets import PatternWidget
from ...model.OverlayModel import OverlayModel
from ...model.util.HelperModule import rgb_to_hex


@pytest.fixture
def overlay_model() -> OverlayModel:
    return OverlayModel()


@pytest.fixture
def overlay_in_pattern_controller(
    pattern_widget, overlay_model
) -> OverlayInPatternController:
    return OverlayInPatternController(pattern_widget, overlay_model)


@pytest.fixture
def pattern_widget(integration_widget: IntegrationWidget) -> PatternWidget:
    return integration_widget.pattern_widget


def test_adding_overlays(
    overlay_in_pattern_controller: OverlayInPatternController,
    pattern_widget: PatternWidget,
    overlay_model: OverlayModel,
):
    assert pattern_widget.legend.numItems == 1

    overlay_model.add_overlay(np.arange(10), np.arange(10), name="test1")
    overlay_model.add_overlay(np.arange(10), np.arange(10), name="test2")
    assert len(pattern_widget.overlays) == 2
    assert pattern_widget.legend.numItems == 3

    assert pattern_widget.legend.legendItems[1][1].text == "test1"
    assert pattern_widget.legend.legendItems[2][1].text == "test2"


def test_removing_overlays(
    overlay_in_pattern_controller: OverlayInPatternController,
    pattern_widget: PatternWidget,
    overlay_model: OverlayModel,
):
    overlay_model.add_overlay(np.arange(10), np.arange(10), name="test1")
    overlay_model.add_overlay(np.arange(10), np.arange(10), name="test2")

    overlay_model.remove_overlay(0)
    assert len(pattern_widget.overlays) == 1
    assert len(pattern_widget.legend.legendItems) == 2
    assert pattern_widget.legend.numItems == 2
    assert pattern_widget.legend.legendItems[1][1].text == "test2"


def test_rename_overlay(
    overlay_in_pattern_controller: OverlayInPatternController,
    pattern_widget: PatternWidget,
    overlay_model: OverlayModel,
):
    overlay_model.add_overlay(np.arange(10), np.arange(10), name="test1")
    overlay_model.add_overlay(np.arange(10), np.arange(10), name="test2")

    overlay_model.set_overlay_name(0, "test3")
    assert pattern_widget.legend.legendItems[1][1].text == "test3"


def test_set_overlay_color(
    overlay_in_pattern_controller: OverlayInPatternController,
    pattern_widget: PatternWidget,
    overlay_model: OverlayModel,
):
    overlay_model.add_overlay(np.arange(10), np.arange(10), name="test1")
    overlay_model.add_overlay(np.arange(10), np.arange(10), name="test2")

    new_color = rgb_to_hex((120, 100, 10))
    overlay_model.set_overlay_color(0, new_color)
    assert pattern_widget.legend.legendItems[1][1].opts["color"] == new_color
    assert pattern_widget.overlays[0].opts["pen"].color().name() == new_color


def test_move_overlay_up(
    overlay_in_pattern_controller: OverlayInPatternController,
    pattern_widget: PatternWidget,
    overlay_model: OverlayModel,
):
    overlay_model.add_overlay(np.arange(10), np.arange(10), name="test1")
    overlay_model.add_overlay(np.arange(11), np.arange(11), name="test2")
    overlay_model.add_overlay(np.arange(12), np.arange(12), name="test3")

    overlay_model.move_overlay_up(2)
    assert pattern_widget.legend.legendItems[1][1].text == "test1"
    assert pattern_widget.legend.legendItems[2][1].text == "test3"
    assert pattern_widget.legend.legendItems[3][1].text == "test2"

    assert np.array_equal(pattern_widget.overlays[0].xData, np.arange(10))
    assert np.array_equal(pattern_widget.overlays[1].xData, np.arange(12))
    assert np.array_equal(pattern_widget.overlays[2].xData, np.arange(11))


def test_move_overlay_down(
    overlay_in_pattern_controller: OverlayInPatternController,
    pattern_widget: PatternWidget,
    overlay_model: OverlayModel,
):
    overlay_model.add_overlay(np.arange(10), np.arange(10), name="test1")
    overlay_model.add_overlay(np.arange(11), np.arange(11), name="test2")
    overlay_model.add_overlay(np.arange(12), np.arange(12), name="test3")

    overlay_model.move_overlay_down(0)
    assert pattern_widget.legend.legendItems[1][1].text == "test2"
    assert pattern_widget.legend.legendItems[2][1].text == "test1"
    assert pattern_widget.legend.legendItems[3][1].text == "test3"

    assert np.array_equal(pattern_widget.overlays[0].xData, np.arange(11))
    assert np.array_equal(pattern_widget.overlays[1].xData, np.arange(10))
    assert np.array_equal(pattern_widget.overlays[2].xData, np.arange(12))


def test_hide_overlay(
    overlay_in_pattern_controller: OverlayInPatternController,
    pattern_widget: PatternWidget,
    overlay_model: OverlayModel,
):
    overlay_model.add_overlay(np.arange(10), np.arange(10), name="test1")
    overlay_model.add_overlay(np.arange(11), np.arange(11), name="test2")
    overlay_model.add_overlay(np.arange(12), np.arange(12), name="test3")

    overlay_model.set_overlay_visible(0, False)

    assert not pattern_widget.overlays[0] in pattern_widget.pattern_plot.items
    assert pattern_widget.overlays[1] in pattern_widget.pattern_plot.items
    assert pattern_widget.overlays[2] in pattern_widget.pattern_plot.items


def test_change_scaling(
    overlay_in_pattern_controller: OverlayInPatternController,
    pattern_widget: PatternWidget,
    overlay_model: OverlayModel,
):
    overlay_model.add_overlay(np.arange(10), np.arange(10), name="test1")
    overlay_model.add_overlay(np.arange(11), np.arange(11), name="test2")

    overlay_model.set_overlay_scaling(0, 0.5)
    assert np.array_equal(pattern_widget.overlays[0].yData, np.arange(10) * 0.5)

    overlay_model.set_overlay_scaling(1, 2)
    assert np.array_equal(pattern_widget.overlays[1].yData, np.arange(11) * 2)


def test_change_offset(
    overlay_in_pattern_controller: OverlayInPatternController,
    pattern_widget: PatternWidget,
    overlay_model: OverlayModel,
):
    overlay_model.add_overlay(np.arange(10), np.arange(10), name="test1")
    overlay_model.add_overlay(np.arange(11), np.arange(11), name="test2")

    overlay_model.set_overlay_offset(0, 0.5)
    assert np.array_equal(pattern_widget.overlays[0].yData, np.arange(10) + 0.5)

    overlay_model.set_overlay_offset(1, 2)
    assert np.array_equal(pattern_widget.overlays[1].yData, np.arange(11) + 2)
