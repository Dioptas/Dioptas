# SPDX-License-Identifier: MIT
"""Tests for the PhaseSmith phase-line adapter."""

from copy import deepcopy
from math import asin, degrees, pi

import numpy as np
import pytest

from ...model import eos
from ...model.util.phasesmith import (
    calculate_material_reflections,
    material_has_complete_structure,
    minimum_d_spacing_for_pattern,
)


def _material(formula):
    return next(material for material in eos.load_materials()
                if material.formula == formula and material.atom_sites)


def test_complete_structure_generates_normalized_reflections():
    gold = _material("Au")
    rows = calculate_material_reflections(gold)

    assert rows
    assert max(row[4] for row in rows) == pytest.approx(100.0)
    assert rows[0][3] == pytest.approx(2.35917, abs=1e-5)
    assert all(row[3] >= 0.5 and row[4] > 0.5 for row in rows)


def test_cubic_reflections_prefer_100_over_equivalent_001():
    cubic = _material("FeH3")
    rows = calculate_material_reflections(cubic)

    assert rows[0][:3] == (1, 0, 0)
    assert (0, 0, 1) not in {row[:3] for row in rows}


def test_builder_ignores_stale_peaks_when_structure_is_complete():
    gold = deepcopy(_material("Au"))
    gold.peaks = [[9, 9, 9, 99.0, 100.0]]

    phase = eos.build_jcpds(gold)

    assert material_has_complete_structure(gold)
    assert len(phase.reflections) > 1
    assert all(reflection.d0 != 99.0 for reflection in phase.reflections)


@pytest.mark.parametrize(
    ("unit", "x_values"),
    [
        ("q_A^-1", np.array([1.0, 20.0])),
        ("d_A", np.array([2.0 * pi / 20.0, 4.0])),
        (
            "2th_deg",
            np.array([5.0, degrees(2.0 * asin(20.0 * 0.31 / (4.0 * pi)))]),
        ),
    ],
)
def test_pattern_cutoff_adds_five_percent_q_margin(unit, x_values):
    minimum_d = minimum_d_spacing_for_pattern(x_values, unit, 0.31)

    assert 2.0 * pi / minimum_d == pytest.approx(21.0)


def test_gold_builder_uses_requested_pattern_coverage():
    gold = _material("Au")
    phase = eos.build_jcpds(
        gold,
        minimum_d_spacing=2.0 * pi / 21.0,
        wavelength_angstrom=0.31,
    )

    assert len(phase.reflections) > 22
    assert phase.state.reflection_q_max == pytest.approx(21.0)
    assert phase.state.reflection_source["kind"] == "material"


def test_builder_uses_stored_peaks_for_incomplete_structure():
    material = next(
        item for item in eos.load_materials()
        if not material_has_complete_structure(item)
    )

    phase = eos.build_jcpds(material)

    expected = material.peaks[0]
    actual = phase.reflections[0]
    assert (actual.h, actual.k, actual.l, actual.d0, actual.intensity) == (
        expected[0], expected[1], expected[2], expected[3], expected[4]
    )
