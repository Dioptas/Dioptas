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
    with pytest.raises(ValueError, match="atoms per chemical formula"):
        EosPhase("Holzapfel", GOLD, formula_units_per_cell=4)
    with pytest.raises(ValueError, match="atomic-number parameter"):
        EosPhase("Holzapfel", GOLD, n=1, formula_units_per_cell=4)


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


# ---------------------------------------------------------------------------
# Thermal models: Mie-Grüneisen-Debye/Einstein composed over the rt equation
# ---------------------------------------------------------------------------

GOLD_MGD = {"Tr": 300.0, "theta0": 170.0, "gamma0": 2.97, "q": 0.6}


def _gold_mgd(thermal_type="MieGruneisenDebye"):
    return EosPhase("Vinet", GOLD, n=1, formula_units_per_cell=4,
                    thermal_type=thermal_type, thermal_parameters=GOLD_MGD)


def test_mgd_reduces_to_rt_equation_at_reference_temperature():
    v_thermal = _gold_mgd().volume(30.0, temperature=300.0)
    v_rt = EosPhase("Vinet", GOLD).volume(30.0)
    assert v_thermal == pytest.approx(v_rt, rel=1e-6)


def test_mgd_expands_with_temperature_and_roundtrips():
    eos = _gold_mgd()
    v_300 = eos.volume(30.0, temperature=300.0)
    v_2000 = eos.volume(30.0, temperature=2000.0)
    assert v_2000 > v_300
    assert eos.pressure(v_2000, temperature=2000.0) == pytest.approx(
        30.0, abs=1e-2)


def test_mgd_thermal_pressure_magnitude_matches_alpha_k0():
    # At fixed volume, the MGD thermal pressure over 1000 K should be in
    # the same ballpark as the classic alpha*K0*dT estimate for gold
    # (~4.26e-5 * 167 * 1000 = 7.1 GPa) — same physics, different model.
    eos = _gold_mgd()
    v = eos.volume(10.0, temperature=300.0)
    delta_p = (eos.pressure(v, temperature=1300.0)
               - eos.pressure(v, temperature=300.0))
    assert 4.0 < delta_p < 11.0


def test_einstein_close_to_debye_well_above_theta():
    v_debye = _gold_mgd().volume(30.0, temperature=1500.0)
    v_einstein = _gold_mgd("MieGruneisenEinstein").volume(
        30.0, temperature=1500.0)
    # both converge to the classical limit far above theta0 = 170 K
    assert v_einstein == pytest.approx(v_debye, rel=5e-3)


def test_thermal_model_requires_parameters_and_material_data():
    with pytest.raises(ValueError, match="theta0"):
        EosPhase("Vinet", GOLD, n=1, formula_units_per_cell=4,
                 thermal_type="MieGruneisenDebye",
                 thermal_parameters={"gamma0": 2.97})
    with pytest.raises(ValueError, match="formula_units_per_cell"):
        EosPhase("Vinet", GOLD, n=1,
                 thermal_type="MieGruneisenDebye",
                 thermal_parameters=GOLD_MGD)
    with pytest.raises(ValueError, match="Unsupported thermal"):
        EosPhase("Vinet", GOLD, n=1, formula_units_per_cell=4,
                 thermal_type="NotAModel", thermal_parameters=GOLD_MGD)


def test_compute_volume_routes_through_thermal_engine(gold_jcpds):
    p = gold_jcpds.params
    p["eos_type"] = "Vinet"
    p["thermal_type"] = "MieGruneisenDebye"
    p["theta_t0"] = 170.0
    p["gamma_t0"] = 2.97
    p["q_t0"] = 0.6
    p["t_ref"] = 300.0
    p["n"] = 1
    p["zc"] = 4

    gold_jcpds.compute_volume(pressure=30.0, temperature=2000.0)
    via_jcpds = p["v"]
    expected = EosPhase(
        "Vinet",
        {"V0": p["v0"], "K0": p["k0"], "K0_prime": p["k0p0"]},
        n=1, formula_units_per_cell=4,
        thermal_type="MieGruneisenDebye",
        thermal_parameters={"Tr": 300.0, "theta0": 170.0,
                            "gamma0": 2.97, "q": 0.6},
    ).volume(30.0, temperature=2000.0)
    assert via_jcpds == pytest.approx(expected, rel=1e-6)

    # temperature spinbox relies on this
    assert gold_jcpds.has_thermal_expansion()


def test_incomplete_thermal_model_falls_back_gracefully(gold_jcpds, caplog):
    # MGD selected but theta0 never entered: computes exactly like the
    # phase without the thermal model (the legacy path, including its
    # alpha correction) and logs the reason
    gold_jcpds.params["thermal_type"] = "MieGruneisenDebye"
    gold_jcpds.compute_volume(pressure=30.0, temperature=2000.0)
    with_incomplete_mgd = gold_jcpds.params["v"]
    assert "cannot be constructed" in caplog.text

    gold_jcpds.params["thermal_type"] = ""
    gold_jcpds.compute_volume(pressure=30.0, temperature=2000.0)
    assert with_incomplete_mgd == pytest.approx(gold_jcpds.params["v"],
                                                rel=1e-9)


GOLD_SOKOLOVA = {
    "Tr": 298.15, "QE1o": 179.5, "mE1": 1.5,
    "QE2o": 83.0, "mE2": 1.5, "delta": 0.134, "t": 0.087,
    "a_0": 0.0, "m": 0.0, "g": 0.0, "e_0": 0.0,
}


def test_sokolova2016_reduces_to_holzapfel_at_reference_temperature():
    eos = EosPhase(
        "Holzapfel", GOLD, n=1, z=79, formula_units_per_cell=4,
        thermal_type="Sokolova2016", thermal_parameters=GOLD_SOKOLOVA)
    reference = EosPhase(
        "Holzapfel", GOLD, n=1, z=79, formula_units_per_cell=4)
    assert eos.volume(100.0, 298.15) == pytest.approx(
        reference.volume(100.0), rel=1e-8)


def test_sokolova2016_expands_and_roundtrips():
    eos = EosPhase(
        "Holzapfel", GOLD, n=1, z=79, formula_units_per_cell=4,
        thermal_type="Sokolova2016", thermal_parameters=GOLD_SOKOLOVA)
    v_ref = eos.volume(100.0, 298.15)
    v_hot = eos.volume(100.0, 2000.0)
    assert v_hot > v_ref
    assert eos.pressure(v_hot, 2000.0) == pytest.approx(100.0, abs=1e-6)


def test_sokolova2016_requires_holzapfel_and_full_parameters():
    with pytest.raises(ValueError, match="requires a Holzapfel"):
        EosPhase(
            "Vinet", GOLD, n=1, z=79, formula_units_per_cell=4,
            thermal_type="Sokolova2016", thermal_parameters=GOLD_SOKOLOVA)
    with pytest.raises(ValueError, match="QE1o"):
        EosPhase(
            "Holzapfel", GOLD, n=1, z=79, formula_units_per_cell=4,
            thermal_type="Sokolova2016", thermal_parameters={"Tr": 298.15})
