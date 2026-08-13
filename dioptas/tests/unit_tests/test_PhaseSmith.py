# SPDX-License-Identifier: MIT
"""Tests for the PhaseSmith phase-line adapter."""

from copy import deepcopy

import pytest

from ...model import eos
from ...model.util.phasesmith import (
    calculate_material_reflections,
    material_has_complete_structure,
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


def test_builder_ignores_stale_peaks_when_structure_is_complete():
    gold = deepcopy(_material("Au"))
    gold.peaks = [[9, 9, 9, 99.0, 100.0]]

    phase = eos.build_jcpds(gold)

    assert material_has_complete_structure(gold)
    assert len(phase.reflections) > 1
    assert all(reflection.d0 != 99.0 for reflection in phase.reflections)


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
