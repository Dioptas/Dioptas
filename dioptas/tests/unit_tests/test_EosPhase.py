# SPDX-License-Identifier: MIT
"""
Cross-validates EosPhase (Peritheos-backed) against the legacy
jcpds.compute_volume() implementation. Both should agree on V(P) for the
same material, since they implement the same Birch-Murnaghan physics —
just with different numerical solvers.
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


@pytest.mark.parametrize("pressure", [0.0, 5.0, 10.0, 25.0, 50.0, 100.0])
def test_eos_phase_matches_legacy_jcpds(gold_jcpds, pressure):
    gold_jcpds.compute_volume(pressure=pressure)
    legacy_volume = gold_jcpds.params["v"]

    eos_phase = EosPhase.from_jcpds(gold_jcpds, eos_type="BM3")
    peritheos_volume = eos_phase.volume(pressure)

    # Two independent numerical solvers on the same BM3 equation —
    # expect agreement well within experimental precision.
    assert peritheos_volume == pytest.approx(legacy_volume, rel=1e-3)


def test_eos_phase_pressure_roundtrip(gold_jcpds):
    eos_phase = EosPhase.from_jcpds(gold_jcpds, eos_type="BM3")
    v_at_10gpa = eos_phase.volume(10.0)
    recovered_pressure = eos_phase.pressure(v_at_10gpa)
    assert recovered_pressure == pytest.approx(10.0, abs=1e-2)


def test_eos_phase_rejects_unknown_type():
    with pytest.raises(ValueError):
        EosPhase(eos_type="not-a-real-eos", v0=67.85, k0=167.0, k0_prime=6.0)
