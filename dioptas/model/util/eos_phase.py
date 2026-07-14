# SPDX-License-Identifier: MIT
"""
EosPhase: Peritheos-backed equation of state calculations for jcpds phases.

Dioptas' legacy ``jcpds.compute_volume()`` only supports 3rd-order
Birch-Murnaghan. ``EosPhase`` wraps the Peritheos library instead, giving
access to BM2, BM3, Vinet, and Holzapfel.

Units
-----
BM2/BM3/Vinet are unit-agnostic, so they work directly in the Å³-per-unit-
cell convention Dioptas uses. Holzapfel is not: its Fermi-gas reference
term needs the absolute molar volume, so Peritheos expects V in
JBar⁻¹ (= cm³/mol / 10) per chemical formula, plus the number of atoms in
the formula (n) and its summed atomic number (Z). EosPhase converts:

    V[JBar⁻¹ per formula] = V[Å³ per cell] / Zc * 0.60221415 / 10

where Zc is the number of formula units per unit cell (the
crystallographic "Z", e.g. 4 for fcc gold). The conversion happens inside
this class, so callers always work in Å³ per unit cell.
"""

from __future__ import annotations

from typing import Optional

from peritheos.eos.rt import BM2, BM3, Vinet
from peritheos.eos.rt.holzapfel import Holzapfel

SUPPORTED_TYPES = ("BM2", "BM3", "VINET", "HOLZAPFEL")

# Å³ per formula unit -> JBar⁻¹ (= cm³/mol / 10): Avogadro * 1e-24 / 10
_A3_TO_JBAR = 0.060221415


class EosPhase:
    """
    Thin wrapper around Peritheos EoS classes, parameterized the same way
    as a Dioptas ``jcpds`` object. All volumes in and out are Å³ per unit
    cell, regardless of the EoS type.
    """

    def __init__(
        self,
        eos_type: str,
        v0: float,
        k0: float,
        k0_prime: Optional[float] = None,
        n: Optional[float] = None,
        z: Optional[int] = None,
        formula_units_per_cell: Optional[int] = None,
    ):
        self.eos_type = eos_type.upper()
        self.v0 = v0
        self.k0 = k0
        self.k0_prime = k0_prime
        self._scale = 1.0  # volume conversion factor (identity except Holzapfel)

        if self.eos_type == "BM2":
            self._eos = BM2(V0=v0, K0=k0)
        elif self.eos_type == "BM3":
            if k0_prime is None:
                raise ValueError("BM3 requires k0_prime")
            self._eos = BM3(V0=v0, K0=k0, K0_prime=k0_prime)
        elif self.eos_type == "VINET":
            if k0_prime is None:
                raise ValueError("Vinet requires k0_prime")
            self._eos = Vinet(V0=v0, K0=k0, K0_prime=k0_prime)
        elif self.eos_type == "HOLZAPFEL":
            if k0_prime is None or n is None or z is None:
                raise ValueError(
                    "Holzapfel requires k0_prime, and n/Z (atoms and summed "
                    "atomic number of the chemical formula)")
            if not formula_units_per_cell:
                raise ValueError(
                    "Holzapfel requires formula_units_per_cell (the "
                    "crystallographic Z) to convert the unit-cell volume "
                    "to molar volume")
            self._scale = _A3_TO_JBAR / formula_units_per_cell
            self._eos = Holzapfel(
                V0=v0 * self._scale, K0=k0, K0_prime=k0_prime, n=n, Z=z)
        else:
            raise ValueError(
                f"Unsupported EoS type '{eos_type}'. "
                f"Supported: {', '.join(SUPPORTED_TYPES)}")

    def pressure(self, volume: float) -> float:
        """Pressure (GPa) at a given unit-cell volume (Å³)."""
        return float(self._eos.pressure(volume * self._scale))

    def volume(self, pressure: float) -> float:
        """Unit-cell volume (Å³) at a given pressure (GPa)."""
        return float(self._eos.calculate_volume(pressure)) / self._scale

    @classmethod
    def from_jcpds(cls, jcpds_obj, eos_type: Optional[str] = None) -> "EosPhase":
        """
        Build an ``EosPhase`` from an existing Dioptas ``jcpds`` object,
        reusing its V0/K0/K0' parameters (and n/z/zc when present, as set
        by eos_formats.build_jcpds for database materials).
        """
        p = jcpds_obj.params
        return cls(
            eos_type=eos_type or p.get("eos_type", "BM3"),
            v0=p["v0"],
            k0=p["k0"],
            k0_prime=p.get("k0p0") or p.get("k0p"),
            n=p.get("n"),
            z=p.get("z"),
            formula_units_per_cell=p.get("zc"),
        )

    def __repr__(self) -> str:
        return (f"EosPhase({self.eos_type}, V0={self.v0}, K0={self.k0}, "
                f"K0'={self.k0_prime})")
