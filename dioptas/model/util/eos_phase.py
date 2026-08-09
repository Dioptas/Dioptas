# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
"""
EosPhase: Peritheos-backed equation-of-state calculations for jcpds
phases.

Dioptas' legacy ``jcpds.compute_volume()`` only supports 3rd-order
Birch-Murnaghan. ``EosPhase`` is a thin, generic wrapper around the
``peritheos.eos.rt`` classes: the EoS type is the Peritheos class name
and the parameters are that class's constructor keywords, exactly as
stored in the EoS database records (see model/eos/material.py). New
equations in Peritheos become available here by adding their name to
``RT_EOS_TYPES`` — nothing else.

Units
-----
Most equations are unit-agnostic, so they work directly in the
Å³-per-unit-cell convention Dioptas uses. Holzapfel is not: its Fermi-gas
reference term needs the absolute molar volume, so Peritheos expects V in
JBar⁻¹ (= cm³/mol / 10) per chemical formula, plus the number of atoms in
the formula (n) and its summed atomic number (Z). EosPhase converts:

    V[JBar⁻¹ per formula] = V[Å³ per cell] / Zc * 0.60221415 / 10

where Zc is the number of formula units per unit cell (the
crystallographic "Z", e.g. 4 for fcc gold). The conversion happens inside
this class, so callers always work in Å³ per unit cell.
"""

from __future__ import annotations

import inspect
from typing import Optional

from peritheos.eos import rt

#: Peritheos rt classes selectable as a phase's equation of state. The
#: names are the class names; a record's parameters go straight into the
#: constructor.
RT_EOS_TYPES = (
    "BM2", "BM3", "BM4", "Murnaghan", "Vinet", "ModifiedTait",
    "NaturalStrain2", "NaturalStrain3", "NaturalStrain4", "Holzapfel",
)

#: case-insensitive lookup, so 'VINET' (stored by earlier versions of
#: this feature branch) still resolves
_CANONICAL = {name.upper(): name for name in RT_EOS_TYPES}

#: human-readable names for the UI (phase editor combobox etc.)
EOS_DISPLAY_NAMES = {
    "BM2": "Birch-Murnaghan (2nd order)",
    "BM3": "Birch-Murnaghan (3rd order)",
    "BM4": "Birch-Murnaghan (4th order)",
    "Murnaghan": "Murnaghan",
    "Vinet": "Vinet",
    "ModifiedTait": "Modified Tait",
    "NaturalStrain2": "Natural Strain (2nd order)",
    "NaturalStrain3": "Natural Strain (3rd order)",
    "NaturalStrain4": "Natural Strain (4th order)",
    "Holzapfel": "Holzapfel",
}


def eos_parameter_names(eos_type: str) -> list:
    """
    The constructor parameters of a peritheos rt equation, in signature
    order, without ``self`` and without ``V0`` (Dioptas derives the
    zero-pressure volume from the lattice). E.g. BM4 ->
    ['K0', 'K0_prime', 'K0_double_prime'].
    """
    canonical = _CANONICAL.get(str(eos_type).upper())
    if canonical is None:
        raise ValueError(f"Unsupported EoS type '{eos_type}'")
    eos_class = getattr(rt, canonical)
    return [name for name in
            inspect.signature(eos_class.__init__).parameters
            if name not in ("self", "V0")]

# Å³ per formula unit -> JBar⁻¹ (= cm³/mol / 10): Avogadro * 1e-24 / 10
_A3_TO_JBAR = 0.060221415


class EosPhase:
    """
    One constructed Peritheos equation of state, parameterized the same
    way as the database records. All volumes in and out are Å³ per unit
    cell, regardless of the EoS type.

    Raises ValueError for an unknown type or missing parameters — the
    message names what is missing, so callers can surface it.
    """

    def __init__(
        self,
        eos_type: str,
        parameters: dict,
        n: Optional[float] = None,
        z: Optional[int] = None,
        formula_units_per_cell: Optional[int] = None,
    ):
        canonical = _CANONICAL.get(str(eos_type).upper())
        if canonical is None:
            raise ValueError(
                f"Unsupported EoS type '{eos_type}'. "
                f"Supported: {', '.join(RT_EOS_TYPES)}")
        self.eos_type = canonical
        eos_class = getattr(rt, canonical)
        self._scale = 1.0  # volume conversion (identity except Holzapfel)

        accepted = [p for p in
                    inspect.signature(eos_class.__init__).parameters
                    if p != "self"]
        kwargs = {key: value for key, value in parameters.items()
                  if key in accepted and value is not None}

        if canonical == "Holzapfel":
            if n is None or z is None:
                raise ValueError(
                    "Holzapfel requires n and Z (atoms and summed atomic "
                    "number of the chemical formula)")
            if not formula_units_per_cell:
                raise ValueError(
                    "Holzapfel requires formula_units_per_cell (the "
                    "crystallographic Z) to convert the unit-cell volume "
                    "to molar volume")
            self._scale = _A3_TO_JBAR / formula_units_per_cell
            kwargs["n"] = n
            kwargs["Z"] = z
            if "V0" in kwargs:
                kwargs["V0"] = kwargs["V0"] * self._scale

        missing = [p for p in accepted
                   if p not in kwargs
                   and inspect.signature(eos_class.__init__).parameters[p].default
                   is inspect.Parameter.empty]
        if missing:
            raise ValueError(
                f"{canonical} requires parameters: {', '.join(missing)}")

        self._eos = eos_class(**kwargs)

    def pressure(self, volume: float) -> float:
        """Pressure (GPa) at a given unit-cell volume (Å³)."""
        return float(self._eos.pressure(volume * self._scale))

    def volume(self, pressure: float) -> float:
        """Unit-cell volume (Å³) at a given pressure (GPa)."""
        return float(self._eos.calculate_volume(pressure)) / self._scale

    @classmethod
    def from_jcpds(cls, jcpds_obj, eos_type: Optional[str] = None,
                   k0: Optional[float] = None,
                   k0p: Optional[float] = None) -> "EosPhase":
        """
        Build an ``EosPhase`` from a Dioptas ``jcpds`` object, reusing its
        V0/K0/K0' parameters (and n/z/zc when present, as set by
        model.eos.build_jcpds for database materials). *k0*/*k0p* override
        the stored values — compute_volume passes its temperature-corrected
        ones.
        """
        p = jcpds_obj.params
        return cls(
            eos_type=eos_type or p.get("eos_type") or "BM3",
            parameters={
                "V0": p["v0"],
                "K0": k0 if k0 is not None else p["k0"],
                "K0_prime": k0p if k0p is not None
                else (p.get("k0p0") or p.get("k0p")),
                "K0_double_prime": p.get("k0pp0") or 0.0,
            },
            n=p.get("n"),
            z=p.get("z"),
            formula_units_per_cell=p.get("zc"),
        )

    def __repr__(self) -> str:
        return f"EosPhase({self.eos_type}, {self._eos!r})"
