# SPDX-License-Identifier: MIT
"""
Pydantic data models for EoS database materials.

These are the canonical structures used between the database API, the
.eosmat file format, and the jcpds phase builder. Nested fields
(Material -> Lattice / Peak / EosParameters) replace the flat dicts and
repeated ``.get(...)`` chains that were used before.

Data flow:
    API JSON  --Material.from_api-->  Material  --build_jcpds-->  jcpds phase
    .eosmat   --read_eosmat------->   Material  --build_jcpds-->  jcpds phase
"""

from __future__ import annotations

import re
from typing import List, Optional

from pydantic import BaseModel, Field


class Peak(BaseModel):
    """One diffraction peak: Miller indices, d-spacing and intensity."""
    h: int = 0
    k: int = 0
    l: int = 0
    d_spacing: float = 0.0   # Å
    intensity: float = 0.0   # relative


class Lattice(BaseModel):
    """Zero-pressure lattice parameters."""
    symmetry: str = ""       # space-group system, e.g. CUBIC, HEXAGONAL
    a: float = 0.0           # Å
    b: Optional[float] = None
    c: Optional[float] = None
    alpha: float = 90.0      # degrees
    beta: float = 90.0
    gamma: float = 90.0


class EosParameters(BaseModel):
    """One equation-of-state record for a material."""
    id: Optional[str] = None            # database id (UUID as string)
    eos_type: str = "Birch-Murnaghan"   # human label from the database
    eos_order: Optional[int] = 3        # 2 or 3 for Birch-Murnaghan
    reference: str = ""
    v0: Optional[float] = None          # Å³ — zero-pressure unit-cell volume
    k0: Optional[float] = None          # GPa — zero-pressure bulk modulus
    k0_prime: Optional[float] = None    # dK/dP
    alpha0: Optional[float] = None      # K⁻¹ — thermal expansion coefficient
    dK_dT: Optional[float] = None       # GPa/K
    reference_temperature: Optional[float] = None  # K

    @property
    def engine_type(self) -> str:
        """Engine key for EosPhase: BM2 / BM3 / VINET / HOLZAPFEL."""
        label = self.eos_type.lower()
        if "vinet" in label:
            return "VINET"
        if "holzapfel" in label:
            return "HOLZAPFEL"
        return "BM2" if self.eos_order == 2 else "BM3"

    @classmethod
    def from_api(cls, d: dict) -> "EosParameters":
        """Build from one record of the /api/v1/eos response."""
        return cls(
            id=str(d.get("id")) if d.get("id") else None,
            eos_type=d.get("eos_type") or "Birch-Murnaghan",
            eos_order=d.get("eos_order"),
            reference=d.get("reference") or "",
            v0=d.get("v0"),
            k0=d.get("k0"),
            k0_prime=d.get("k0_prime"),
            alpha0=d.get("alpha0"),
            dK_dT=d.get("dK_dT"),
            reference_temperature=d.get("reference_temperature"),
        )


class Material(BaseModel):
    """A material with its lattice, diffraction peaks and EoS records."""
    id: Optional[str] = None
    name: str = ""
    formula: str = ""
    lattice: Lattice = Field(default_factory=Lattice)
    peaks: List[Peak] = Field(default_factory=list)
    # Formula units per unit cell (crystallographic Z). Needed to convert
    # the unit-cell volume (Å³) to molar volume for the Holzapfel EoS.
    formula_units_per_cell: Optional[int] = None
    notes: str = ""

    @property
    def display_name(self) -> str:
        """'Gold (Au)' when name and formula differ, else just the name."""
        if self.formula and self.formula != self.name:
            return f"{self.name} ({self.formula})"
        return self.name

    def atoms_per_formula(self) -> Optional[float]:
        """Number of atoms in the chemical formula, e.g. MgO -> 2."""
        parsed = _parse_formula(self.formula)
        return sum(count for _, count in parsed) if parsed else None

    def electrons_per_formula(self) -> Optional[int]:
        """Summed atomic number of the formula, e.g. MgO -> 12 + 8 = 20."""
        parsed = _parse_formula(self.formula)
        if not parsed:
            return None
        try:
            import xraydb  # already a Dioptas dependency
            return int(sum(xraydb.atomic_number(el) * count
                           for el, count in parsed))
        except (ImportError, ValueError):
            return None

    @classmethod
    def from_api(cls, d: dict) -> "Material":
        """Build from one record of the /api/v1/materials response."""
        return cls(
            id=str(d.get("id")) if d.get("id") else None,
            name=d.get("name") or "",
            formula=d.get("formula") or "",
            lattice=Lattice(
                symmetry=(d.get("symmetry") or "").upper(),
                a=d.get("a") or 0.0,
                b=d.get("b"),
                c=d.get("c"),
                alpha=d.get("alpha") if d.get("alpha") else 90.0,
                beta=d.get("beta") if d.get("beta") else 90.0,
                gamma=d.get("gamma") if d.get("gamma") else 90.0,
            ),
            peaks=[Peak(**p) if not isinstance(p, Peak) else p
                   for p in d.get("diffraction_peaks", [])],
            formula_units_per_cell=d.get("formula_units_per_cell"),
            notes=d.get("notes") or "",
        )


def _parse_formula(formula: str) -> List[tuple]:
    """
    Parse a chemical formula like 'Al2O3' into [('Al', 2), ('O', 3)].
    Returns [] for strings that are not simple formulas.
    """
    if not formula:
        return []
    tokens = re.findall(r"([A-Z][a-z]?)(\d*)", formula)
    parsed = [(el, int(num) if num else 1) for el, num in tokens if el]
    # Reject if the tokens don't reproduce the input (e.g. name-like strings)
    reconstructed = "".join(
        f"{el}{num if num > 1 else ''}" for el, num in parsed)
    return parsed if reconstructed == formula else []
