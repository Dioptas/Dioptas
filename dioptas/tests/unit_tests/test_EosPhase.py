# -*- coding: utf-8 -*-
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

GOLD = {"V0": 67.85, "K0": 167.0, "K0_prime": 6.0}


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
        "BM3", {"V0": v0, "K0": k0, "K0_prime": k0p}
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
    with pytest.raises(ValueError, match="Unsupported"):
        EosPhase("not-a-real-eos", GOLD)


def test_eos_phase_reports_missing_parameters():
    with pytest.raises(ValueError, match="K0_prime"):
        EosPhase("BM3", {"V0": 67.85, "K0": 167.0})


def test_eos_type_is_case_insensitive():
    # Earlier versions of this branch stored 'VINET' — must still resolve
    v_upper = EosPhase("VINET", GOLD).volume(30.0)
    v_canonical = EosPhase("Vinet", GOLD).volume(30.0)
    assert v_upper == v_canonical


# ---------------------------------------------------------------------------
# Generic dispatch: any peritheos rt class with its constructor keywords
# ---------------------------------------------------------------------------

def test_bm4_constructible_from_record_parameters():
    # BM4 needs K0'' — available straight from a record's parameter dict,
    # proving the wrapper is generic rather than a fixed four-type switch.
    eos = EosPhase("BM4", {**GOLD, "K0_double_prime": -0.04})
    assert eos.volume(0.0) == pytest.approx(GOLD["V0"], rel=1e-4)
    assert eos.volume(50.0) < GOLD["V0"]


def test_murnaghan_gives_distinct_volumes():
    v_bm3 = EosPhase("BM3", GOLD).volume(80.0)
    v_murnaghan = EosPhase("Murnaghan", GOLD).volume(80.0)
    assert v_bm3 != pytest.approx(v_murnaghan, rel=1e-4)


# ---------------------------------------------------------------------------
# Holzapfel: unit conversion (Å³/cell <-> molar volume) and physicality
# ---------------------------------------------------------------------------

def test_holzapfel_roundtrip_and_physicality():
    # Gold: formula Au -> n=1, Z=79; fcc -> 4 formula units per cell.
    eos = EosPhase("Holzapfel", GOLD, n=1, z=79, formula_units_per_cell=4)
    # At zero pressure the volume must be V0 (in Å³ per cell, unconverted)
    assert eos.volume(0.0) == pytest.approx(67.85, rel=1e-4)
    # Compression must reduce the volume, and P(V(P)) must round-trip
    v_50 = eos.volume(50.0)
    assert v_50 < 67.85
    assert eos.pressure(v_50) == pytest.approx(50.0, abs=1e-2)


def test_holzapfel_close_to_bm3_at_moderate_pressure():
    # All EoS forms share V0/K0/K0', so at moderate compression Holzapfel
    # should be in the same ballpark as BM3 (they diverge at high P).
    v_bm3 = EosPhase("BM3", GOLD).volume(30.0)
    v_holz = EosPhase("Holzapfel", GOLD,
                      n=1, z=79, formula_units_per_cell=4).volume(30.0)
    assert v_holz == pytest.approx(v_bm3, rel=0.02)


def test_holzapfel_requires_cell_data():
    with pytest.raises(ValueError, match="formula_units_per_cell"):
        EosPhase("Holzapfel", GOLD, n=1, z=79)
    with pytest.raises(ValueError, match="n and Z"):
        EosPhase("Holzapfel", GOLD, formula_units_per_cell=4)


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
    gold_jcpds.params["eos_type"] = "Vinet"
    gold_jcpds.compute_volume(pressure=50.0, temperature=298.0)
    via_engine = gold_jcpds.params["v"]

    expected = EosPhase(
        "Vinet",
        {"V0": gold_jcpds.params["v0"],
         "K0": gold_jcpds.params["k0"],
         "K0_prime": gold_jcpds.params["k0p0"]},
    ).volume(50.0)

    assert via_engine == pytest.approx(expected, rel=1e-6)


def test_different_eos_types_give_different_volumes(gold_jcpds):
    # The whole point: BM3 and Vinet with the same parameters must produce
    # genuinely different volumes at non-trivial compression.
    gold_jcpds.params["eos_type"] = "BM3"
    gold_jcpds.compute_volume(pressure=80.0, temperature=298.0)
    v_bm3 = gold_jcpds.params["v"]

    gold_jcpds.params["eos_type"] = "Vinet"
    gold_jcpds.compute_volume(pressure=80.0, temperature=298.0)
    v_vinet = gold_jcpds.params["v"]

    assert v_bm3 != pytest.approx(v_vinet, rel=1e-4)


def test_unconstructible_eos_falls_back_to_bm3(gold_jcpds, caplog):
    # A legacy phase has no n/Z/Zc, so Holzapfel cannot be built; the
    # volume must still be computed (legacy BM3) and the fallback logged.
    # The UI greys such choices out — this is the safety net behind it.
    gold_jcpds.params["eos_type"] = "Holzapfel"
    gold_jcpds.compute_volume(pressure=20.0, temperature=298.0)
    legacy = gold_jcpds._legacy_bm3_volume(
        gold_jcpds.params["k0"], gold_jcpds.params["k0p0"], 20.0)
    assert gold_jcpds.params["v"] == pytest.approx(legacy, rel=1e-6)
    assert "legacy BM3" in caplog.text


def test_selecting_eos_type_marks_phase_modified(gold_jcpds):
    # A different equation produces different lines than the file implies,
    # so the GUI's modified asterisk must appear.
    assert gold_jcpds.params["modified"] is False
    gold_jcpds.params["eos_type"] = "Vinet"
    assert gold_jcpds.params["modified"] is True
