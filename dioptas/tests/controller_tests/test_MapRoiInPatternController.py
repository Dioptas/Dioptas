# SPDX-License-Identifier: MIT

import os

import numpy as np
import pytest
from pytest import approx

from dioptas.controller.integration import IntegrationController
from dioptas.model.DioptasModel import DioptasModel
from dioptas.model.MapModel import MapPointInfo
from dioptas.model.util.calc import convert_units

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, os.pardir, "data")
map_img_path = os.path.join(data_path, "map")
map_img_file_paths = [
    os.path.join(map_img_path, f)
    for f in os.listdir(map_img_path)
    if os.path.isfile(os.path.join(map_img_path, f))
]


@pytest.fixture
def map_in_integration(integration_controller: IntegrationController):
    """An integration view with a small map loaded, shown in its own window."""
    model = integration_controller.model
    model.calibration_model.load(os.path.join(data_path, "CeO2_Pilatus1M.poni"))
    model.img_model.load(map_img_file_paths[0])

    map_model = model.map_model
    pattern_x = np.linspace(1, 30, 300)
    intensities = np.ones((6, 300))
    map_model.window = [10.0, 12.0]
    map_model.set_integration_results(
        pattern_x,
        intensities,
        [MapPointInfo(f) for f in map_img_file_paths[:6]],
        map_img_file_paths[:6],
    )
    model.view.map_docked = False
    return integration_controller


def pattern_widget(integration_controller: IntegrationController):
    return integration_controller.widget.pattern_widget


def roi_is_shown(integration_controller: IntegrationController) -> bool:
    widget = pattern_widget(integration_controller)
    return widget.map_interactive_roi in widget.pattern_plot.items


def test_roi_is_only_shown_while_the_map_is_undocked(map_in_integration):
    assert roi_is_shown(map_in_integration)

    map_in_integration.model.view.map_docked = True
    assert not roi_is_shown(map_in_integration)

    map_in_integration.model.view.map_docked = False
    assert roi_is_shown(map_in_integration)


def test_roi_is_not_shown_without_a_map(integration_controller: IntegrationController):
    integration_controller.model.view.map_docked = False
    assert not roi_is_shown(integration_controller)


def test_roi_shows_the_window_of_the_map(map_in_integration):
    x_min, x_max = pattern_widget(map_in_integration).map_interactive_roi.getRegion()
    assert (x_min, x_max) == approx((10.0, 12.0))


def test_dragging_the_roi_sets_the_map_window(map_in_integration):
    widget = pattern_widget(map_in_integration)
    widget.map_interactive_roi.setRegion((14.0, 16.0))

    assert map_in_integration.model.map_model.window == approx((14.0, 16.0))


@pytest.mark.parametrize("unit", ["q_A^-1", "d_A"])
def test_dragging_the_roi_converts_into_the_unit_of_the_map(map_in_integration, unit):
    """The map keeps its window in the unit it was integrated in."""
    model = map_in_integration.model
    assert model.map_model.pattern_unit == "2th_deg"

    model.integration_unit = unit
    wavelength = model.calibration_model.wavelength

    region = sorted(
        convert_units(x, wavelength, "2th_deg", unit) for x in (14.0, 16.0)
    )
    pattern_widget(map_in_integration).map_interactive_roi.setRegion(region)

    assert model.map_model.window == approx((14.0, 16.0), rel=1e-6)


@pytest.mark.parametrize("unit", ["q_A^-1", "d_A"])
def test_changing_the_unit_moves_the_roi(map_in_integration, unit):
    model = map_in_integration.model
    model.integration_unit = unit

    wavelength = model.calibration_model.wavelength
    expected = sorted(
        convert_units(x, wavelength, "2th_deg", unit) for x in (10.0, 12.0)
    )
    region = pattern_widget(map_in_integration).map_interactive_roi.getRegion()
    assert region == approx(tuple(expected), rel=1e-6)


def test_regions_that_have_no_meaningful_conversion_are_ignored(map_in_integration):
    """d spacing runs through a division by the position, and q has an upper
    bound; neither may reach the model as inf/nan or raise."""
    model = map_in_integration.model
    model.integration_unit = "d_A"
    window_before = tuple(model.map_model.window)

    pattern_widget(map_in_integration).map_interactive_roi.setRegion((0.0, 2.0))
    assert model.map_model.window == approx(window_before)

    model.integration_unit = "q_A^-1"
    q_max = 4 * np.pi / model.calibration_model.wavelength / 1e10
    pattern_widget(map_in_integration).map_interactive_roi.setRegion(
        (q_max + 5, q_max + 10)
    )
    assert all(np.isfinite(model.map_model.window))


def test_map_window_survives_a_round_trip_through_a_unit_change(map_in_integration):
    model = map_in_integration.model
    for unit in ["q_A^-1", "d_A", "2th_deg"]:
        model.integration_unit = unit

    assert model.map_model.window == approx((10.0, 12.0), rel=1e-6)
