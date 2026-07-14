# SPDX-License-Identifier: MIT
"""
Tests for the Peritheos-backed EoS engine and its integration into the
live jcpds volume calculation.

Two things are checked:
  1. EosPhase (Peritheos) agrees with the legacy 3rd-order Birch-Murnaghan
     solver for the same input — i.e. swapping the engine doesn't move
     existing BM3 phase lines.
  2. jcpds.compute_volume() actually dispatches on params['eos_type'], so
     selecting BM2 / Vinet / Holzapfel genuinely changes the calculation.
"""
import os

import pytest

from ...model.util import jcpds as jcpds_class
from ...model.util.eos_phase import EosPhase

unittest_path = os.path.dirname(__file__)
jcpds_path = os.path.join(unittest_path, "../data/jcpds")


@pytest.fixture
def gold_jcpds():
    j = jcpds_class()
    j.load_file(os.path.join(jcpds_path, "au_Anderson.jcpds"))
    return j


# ---------------------------------------------------------------------------
# Engine cross-validation: Peritheos BM3 vs the legacy scipy solver
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("pressure", [0.0, 5.0, 10.0, 25.0, 50.0, 100.0])
def test_peritheos_bm3_matches_legacy_solver(gold_jcpds, pressure):
    k0 = gold_jcpds.params["k0"]
    k0p = gold_jcpds.params["k0p0"]
    v0 = gold_jcpds.params["v0"]

    # legacy reference (scipy.minimize on the BM3 residual)
    legacy_volume = gold_jcpds._legacy_bm3_volume(k0, k0p, pressure)

    # Peritheos engine
    peritheos_volume = EosPhase(
        eos_type="BM3", v0=v0, k0=k0, k0_prime=k0p
    ).volume(pressure)

    # Two independent numerical methods on the same BM3 equation — expect
    # agreement well within experimental precision.
    assert peritheos_volume == pytest.approx(legacy_volume, rel=1e-3)


def test_eos_phase_pressure_roundtrip(gold_jcpds):
    eos_phase = EosPhase.from_jcpds(gold_jcpds, eos_type="BM3")
    v_at_10gpa = eos_phase.volume(10.0)
    recovered_pressure = eos_phase.pressure(v_at_10gpa)
    assert recovered_pressure == pytest.approx(10.0, abs=1e-2)


def test_eos_phase_rejects_unknown_type():
    with pytest.raises(ValueError):
        EosPhase(eos_type="not-a-real-eos", v0=67.85, k0=167.0, k0_prime=6.0)


# ---------------------------------------------------------------------------
# Holzapfel: unit conversion (Å³/cell <-> molar volume) and physicality
# ---------------------------------------------------------------------------

def test_holzapfel_roundtrip_and_physicality():
    # Gold: formula Au -> n=1, Z=79; fcc -> 4 formula units per cell.
    eos = EosPhase(
        eos_type="HOLZAPFEL", v0=67.85, k0=167.0, k0_prime=6.0,
        n=1, z=79, formula_units_per_cell=4,
    )
    # At zero pressure the volume must be V0 (in Å³ per cell, unconverted)
    assert eos.volume(0.0) == pytest.approx(67.85, rel=1e-4)
    # Compression must reduce the volume, and P(V(P)) must round-trip
    v_50 = eos.volume(50.0)
    assert v_50 < 67.85
    assert eos.pressure(v_50) == pytest.approx(50.0, abs=1e-2)


def test_holzapfel_close_to_bm3_at_moderate_pressure():
    # All EoS forms share V0/K0/K0', so at moderate compression Holzapfel
    # should be in the same ballpark as BM3 (they diverge at high P).
    kwargs = dict(v0=67.85, k0=167.0, k0_prime=6.0)
    v_bm3 = EosPhase(eos_type="BM3", **kwargs).volume(30.0)
    v_holz = EosPhase(eos_type="HOLZAPFEL", n=1, z=79,
                      formula_units_per_cell=4, **kwargs).volume(30.0)
    assert v_holz == pytest.approx(v_bm3, rel=0.02)


def test_holzapfel_requires_cell_data():
    with pytest.raises(ValueError):
        EosPhase(eos_type="HOLZAPFEL", v0=67.85, k0=167.0, k0_prime=6.0)


# ---------------------------------------------------------------------------
# Live integration: compute_volume() dispatches on eos_type via Peritheos
# ---------------------------------------------------------------------------

def test_default_eos_type_is_bm3_and_matches_legacy(gold_jcpds):
    # A freshly loaded JCPDS phase defaults to BM3.
    assert gold_jcpds.params["eos_type"] == "BM3"

    gold_jcpds.compute_volume(pressure=50.0, temperature=298.0)
    via_engine = gold_jcpds.params["v"]

    legacy = gold_jcpds._legacy_bm3_volume(
        gold_jcpds.params["k0"], gold_jcpds.params["k0p0"], 50.0
    )
    assert via_engine == pytest.approx(legacy, rel=1e-3)


def test_compute_volume_uses_selected_eos_type(gold_jcpds):
    # Switch the phase to Vinet and confirm compute_volume() routes through
    # the Vinet engine (not BM3).
    gold_jcpds.params["eos_type"] = "VINET"
    gold_jcpds.compute_volume(pressure=50.0, temperature=298.0)
    via_engine = gold_jcpds.params["v"]

    expected = EosPhase(
        eos_type="VINET",
        v0=gold_jcpds.params["v0"],
        k0=gold_jcpds.params["k0"],
        k0_prime=gold_jcpds.params["k0p0"],
    ).volume(50.0)

    assert via_engine == pytest.approx(expected, rel=1e-6)


def test_different_eos_types_give_different_volumes(gold_jcpds):
    # The whole point: BM3 and Vinet with the same parameters must produce
    # genuinely different volumes at non-trivial compression.
    gold_jcpds.params["eos_type"] = "BM3"
    gold_jcpds.compute_volume(pressure=80.0, temperature=298.0)
    v_bm3 = gold_jcpds.params["v"]

    gold_jcpds.params["eos_type"] = "VINET"
    gold_jcpds.compute_volume(pressure=80.0, temperature=298.0)
    v_vinet = gold_jcpds.params["v"]

    assert v_bm3 != pytest.approx(v_vinet, rel=1e-4)
