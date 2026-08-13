# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
"""
Material and EoS-record structures for the bundled equation-of-state
database.

One material document (a ``.json`` file in ``resources/eos_database/``, or
a user-saved ``.eosmat`` file — same content) looks like::

    {
      "format_version": 1,
      "name": "Gold",
      "formula": "Au",
      "symmetry": "CUBIC",
      "lattice": {"a": 4.0786, "b": null, "c": null,
                  "alpha": 90.0, "beta": 90.0, "gamma": 90.0},
      "formula_units_per_cell": 4,
      "space_group": "Fm-3m",
      "space_group_number": 225,
      "atom_sites": [
        {"element": "Au", "x": 0.0, "y": 0.0, "z": 0.0,
         "occupancy": 1.0, "wyckoff": "4a"}
      ],
      "notes": "...",
      "peaks": [[h, k, l, d0, intensity], ...],
      "eos_records": [ <record>, ... ]
    }

Every EoS record is future-proof by construction: it names a Peritheos
class and carries that class's constructor keywords verbatim, so new
equations of state (or thermal models) in Peritheos need data only — no
schema change::

    {
      "label": "Anderson et al 1989",        # short display label
      "reference": "full literature reference",
      "eos": {"type": "BM3",                 # peritheos.eos.rt class name
              "parameters": {"V0": 67.847, "K0": 166.65,
                             "K0_prime": 5.4823}},
      "parameter_errors": {"V0": 0.004,       # same units as parameters
                           "K0": null,          # no verified error recorded
                           "K0_prime": 0.02},
      "fixed_parameters": ["K0"],             # held fixed in the EoS fit
      "experimental_pressure_range_gpa": [0.0, 8.9], # optional fit data
      "experimental_temperature_range_k": [298.0, 298.0], # optional
      "thermal": {"type": "AlphaKT",         # optional
                  "parameters": {"alpha0": 4.2e-5, "dK_dT": -0.02}},
      "temperature_ref": 298.15,             # optional, K
      "notes": "..."                         # optional
    }

``thermal.type`` is reserved for ``peritheos.eos.thermal`` class names
(``MieGruneisenDebye``, ``HollandPowell2011``, ...); the one exception is
``AlphaKT``, the classic JCPDS-style correction (thermal expansion alpha0
and dK/dT applied as a pressure shift) that Dioptas computes itself.

Records are handled as plain dicts throughout: the same dict is stored in
the bundled files, on ``CrystalState.eos_records`` (and therefore in
``.dio`` projects and undo snapshots), and consumed by the EosPhase
engine wrapper.

``parameter_errors`` uses the publication's reported error convention and
the same units as the corresponding EoS parameters.  A JSON ``null`` means
that no verified uncertainty is recorded; it must never be interpreted as
zero.  ``fixed_parameters`` records parameters held fixed during the EoS fit.
A fixed value may still have an independently measured uncertainty.
``experimental_pressure_range_gpa`` and
``experimental_temperature_range_k`` describe the measurements used to
constrain the published fit.  They are not phase-stability limits, and an
EoS should not automatically be extrapolated beyond them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Lattice:
    """Zero-pressure lattice parameters (Å / degrees)."""

    a: float = 0.0
    b: Optional[float] = None
    c: Optional[float] = None
    alpha: float = 90.0
    beta: float = 90.0
    gamma: float = 90.0


@dataclass
class Material:
    """A material with its lattice, diffraction peaks and EoS records."""

    name: str = ""
    formula: str = ""
    symmetry: str = ""
    lattice: Lattice = field(default_factory=Lattice)
    #: formula units per unit cell (crystallographic Z) — needed to convert
    #: the unit-cell volume to molar volume for Holzapfel-type equations
    formula_units_per_cell: Optional[int] = None
    #: Hermann-Mauguin symbol and International Tables number. ``atom_sites``
    #: contains the asymmetric-unit representatives with their Wyckoff
    #: multiplicity/letter, ready for a crystallographic symmetry engine to
    #: generate the full cell and calculate reflection intensities.
    space_group: str = ""
    space_group_number: Optional[int] = None
    atom_sites: list = field(default_factory=list)
    notes: str = ""
    #: [h, k, l, d0, intensity] per peak
    peaks: list = field(default_factory=list)
    #: EoS record dicts, schema in the module docstring
    eos_records: list = field(default_factory=list)

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
            import xraydb
            return int(sum(xraydb.atomic_number(el) * count
                           for el, count in parsed))
        except (ImportError, ValueError):
            return None

    def to_dict(self) -> dict:
        return {
            "format_version": 1,
            "name": self.name,
            "formula": self.formula,
            "symmetry": self.symmetry,
            "lattice": {
                "a": self.lattice.a, "b": self.lattice.b, "c": self.lattice.c,
                "alpha": self.lattice.alpha, "beta": self.lattice.beta,
                "gamma": self.lattice.gamma,
            },
            "formula_units_per_cell": self.formula_units_per_cell,
            "space_group": self.space_group,
            "space_group_number": self.space_group_number,
            "atom_sites": [dict(site) for site in self.atom_sites],
            "notes": self.notes,
            "peaks": [list(peak) for peak in self.peaks],
            "eos_records": self.eos_records,
        }

    @classmethod
    def from_dict(cls, document: dict) -> "Material":
        lattice = document.get("lattice") or {}
        return cls(
            name=document.get("name") or "",
            formula=document.get("formula") or "",
            symmetry=(document.get("symmetry") or "").upper(),
            lattice=Lattice(
                a=lattice.get("a") or 0.0,
                b=lattice.get("b"),
                c=lattice.get("c"),
                alpha=lattice.get("alpha") or 90.0,
                beta=lattice.get("beta") or 90.0,
                gamma=lattice.get("gamma") or 90.0,
            ),
            formula_units_per_cell=document.get("formula_units_per_cell"),
            space_group=document.get("space_group") or "",
            space_group_number=document.get("space_group_number"),
            atom_sites=[dict(site)
                        for site in document.get("atom_sites", [])],
            notes=document.get("notes") or "",
            peaks=[list(peak) for peak in document.get("peaks", [])],
            eos_records=list(document.get("eos_records", [])),
        )


def record_label(record: dict) -> str:
    """Display label, including the experimental fit domain when known."""
    label = record.get("label") or record.get("reference") or ""
    pressure_range = record_pressure_range(record)
    return f"{label} [{pressure_range}]" if pressure_range else label


def record_pressure_range(record: dict) -> str:
    """Human-readable experimental pressure range, including units."""
    values = record.get("experimental_pressure_range_gpa")
    if not isinstance(values, (list, tuple)) or len(values) != 2:
        return ""
    low, high = values
    try:
        if float(low) == float(high):
            return f"{float(low):g} GPa"
        return f"{float(low):g}\N{EN DASH}{float(high):g} GPa"
    except (TypeError, ValueError):
        return ""


def record_eos_type(record: dict) -> str:
    """Peritheos class name of an EoS record, e.g. 'BM3'."""
    return (record.get("eos") or {}).get("type") or "BM3"


def _parse_formula(formula: str) -> list:
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
