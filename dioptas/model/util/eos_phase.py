# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
"""
EosPhase: Peritheos-backed equation-of-state calculations for jcpds
phases.

Dioptas' legacy ``jcpds.compute_volume()`` only supports 3rd-order
Birch-Murnaghan. ``EosPhase`` is a thin, generic wrapper around the
``peritheos.eos`` classes: the EoS type is the Peritheos class name and
the parameters are that class's constructor keywords, exactly as stored
in the EoS database records (see model/eos/material.py). New equations
in Peritheos become available here by adding their name to
``RT_EOS_TYPES`` — nothing else.

A thermal model (``peritheos.eos.thermal``) can be composed on top of
the room-temperature equation, mirroring Peritheos' own structure:
``MieGruneisenDebye(rt_eos=BM3(...), Tr=..., theta0=..., gamma0=...,
q=..., n=...)``. With a thermal model, volume() and pressure() take the
temperature explicitly.

Units
-----
Most rt equations are unit-agnostic, so they work directly in the
Å³-per-unit-cell convention Dioptas uses. Holzapfel is not (its
Fermi-gas reference term needs the absolute molar volume) — and neither
are the thermal models, whose Debye/Einstein energy is per mole of
formula units. Peritheos expects V in JBar⁻¹ (= cm³/mol / 10) per
chemical formula there, plus the number of atoms in the formula (n).
EosPhase converts:

    V[JBar⁻¹ per formula] = V[Å³ per cell] / Zc * 0.60221415 / 10

where Zc is the number of formula units per unit cell (the
crystallographic "Z", e.g. 4 for fcc gold). The conversion happens
inside this class, so callers always work in Å³ per unit cell.
"""

from __future__ import annotations

import inspect
from typing import Optional

from peritheos.eos import rt, thermal

#: Peritheos rt classes selectable as a phase's equation of state. The
#: names are the class names; a record's parameters go straight into the
#: constructor.
RT_EOS_TYPES = (
    "BM2", "BM3", "BM4", "Murnaghan", "Vinet", "ModifiedTait",
    "NaturalStrain2", "NaturalStrain3", "NaturalStrain4", "Holzapfel",
)

#: Peritheos thermal models selectable on top of the rt equation. (The
#: Sokolova2016 is constrained to a Holzapfel room-temperature equation.
THERMAL_EOS_TYPES = (
    "MieGruneisenDebye", "MieGruneisenEinstein", "Sokolova2016",
)

#: case-insensitive lookups, so 'VINET' (stored by earlier versions of
#: this feature branch) still resolves
_CANONICAL = {name.upper(): name for name in RT_EOS_TYPES}
_THERMAL_CANONICAL = {name.upper(): name for name in THERMAL_EOS_TYPES}

#: human-readable names for the UI (phase editor comboboxes etc.)
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
    "MieGruneisenDebye": "Mie-Grüneisen-Debye",
    "MieGruneisenEinstein": "Mie-Grüneisen-Einstein",
    "Sokolova2016": "Sokolova et al. (2016)",
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
    One constructed Peritheos equation of state — optionally with a
    thermal model composed on top — parameterized the same way as the
    database records. All volumes in and out are Å³ per unit cell,
    regardless of the EoS type.

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
        thermal_type: Optional[str] = None,
        thermal_parameters: Optional[dict] = None,
    ):
        canonical = _CANONICAL.get(str(eos_type).upper())
        if canonical is None:
            raise ValueError(
                f"Unsupported EoS type '{eos_type}'. "
                f"Supported: {', '.join(RT_EOS_TYPES)}")
        self.eos_type = canonical
        eos_class = getattr(rt, canonical)

        thermal_canonical = None
        if thermal_type:
            thermal_canonical = _THERMAL_CANONICAL.get(
                str(thermal_type).upper())
            if thermal_canonical is None:
                raise ValueError(
                    f"Unsupported thermal model '{thermal_type}'. "
                    f"Supported: {', '.join(THERMAL_EOS_TYPES)}")
        self.thermal_type = thermal_canonical

        # Holzapfel and the thermal models work in molar volume — decide
        # the conversion before building anything so the rt equation and
        # the thermal wrapper share the same units.
        self._scale = 1.0
        needs_molar = canonical == "Holzapfel" or thermal_canonical
        if needs_molar:
            what = canonical if canonical == "Holzapfel" else thermal_canonical
            if n is None:
                raise ValueError(
                    f"{what} requires n (atoms per chemical formula)")
            if not formula_units_per_cell:
                raise ValueError(
                    f"{what} requires formula_units_per_cell (the "
                    "crystallographic Z) to convert the unit-cell volume "
                    "to molar volume")
            self._scale = _A3_TO_JBAR / formula_units_per_cell

        accepted = [p for p in
                    inspect.signature(eos_class.__init__).parameters
                    if p != "self"]
        kwargs = {key: value for key, value in parameters.items()
                  if key in accepted and value is not None}

        if canonical == "Holzapfel":
            # Sokolova's MgO workbook supplies an effective Z that differs
            # from the integer electron sum derived from the formula. A
            # record-level constructor value therefore takes precedence.
            holzapfel_z = parameters.get("Z", z)
            if holzapfel_z is None:
                raise ValueError(
                    "Holzapfel requires Z (the equation's atomic-number "
                    "parameter)")
            kwargs["n"] = n
            kwargs["Z"] = holzapfel_z
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

        if thermal_canonical in ("MieGruneisenDebye",
                                 "MieGruneisenEinstein"):
            tp = thermal_parameters or {}
            theta0 = tp.get("theta0")
            gamma0 = tp.get("gamma0")
            if not theta0 or theta0 <= 0:
                raise ValueError(
                    f"{thermal_canonical} requires a positive Debye/"
                    "Einstein temperature theta0")
            if not gamma0:
                raise ValueError(
                    f"{thermal_canonical} requires a non-zero Grüneisen "
                    "parameter gamma0")
            thermal_class = getattr(thermal, thermal_canonical)
            self._eos = thermal_class(
                rt_eos=self._eos,
                Tr=tp.get("Tr") or 298.15,
                theta0=theta0,
                gamma0=gamma0,
                q=tp.get("q", 1.0),
                n=n,
            )
        elif thermal_canonical == "Sokolova2016":
            if canonical != "Holzapfel":
                raise ValueError(
                    "Sokolova2016 requires a Holzapfel room-temperature "
                    "equation")
            tp = thermal_parameters or {}
            thermal_class = getattr(thermal, thermal_canonical)
            signature = inspect.signature(thermal_class.__init__)
            accepted = [name for name in signature.parameters
                        if name not in ("self", "rt_eos")]
            thermal_kwargs = {
                key: value for key, value in tp.items()
                if key in accepted and value is not None
            }
            missing = [
                name for name in accepted
                if name not in thermal_kwargs
                and signature.parameters[name].default
                is inspect.Parameter.empty
            ]
            if missing:
                raise ValueError(
                    "Sokolova2016 requires parameters: "
                    + ", ".join(missing))
            self._eos = thermal_class(
                rt_eos=self._eos, **thermal_kwargs)

    def pressure(self, volume: float,
                 temperature: Optional[float] = None) -> float:
        """Pressure (GPa) at a given unit-cell volume (Å³). With a
        thermal model, at the given *temperature* (K)."""
        if self.thermal_type:
            return float(self._eos.pressure(
                volume * self._scale,
                temperature if temperature is not None else 298.15))
        return float(self._eos.pressure(volume * self._scale))

    def volume(self, pressure: float,
               temperature: Optional[float] = None) -> float:
        """Unit-cell volume (Å³) at a given pressure (GPa). With a
        thermal model, at the given *temperature* (K)."""
        if self.thermal_type:
            return float(self._eos.calculate_volume(
                pressure,
                temperature if temperature is not None else 298.15)
            ) / self._scale
        return float(self._eos.calculate_volume(pressure)) / self._scale

    @classmethod
    def from_jcpds(cls, jcpds_obj, eos_type: Optional[str] = None,
                   k0: Optional[float] = None,
                   k0p: Optional[float] = None,
                   with_thermal: bool = False) -> "EosPhase":
        """
        Build an ``EosPhase`` from a Dioptas ``jcpds`` object, reusing its
        V0/K0/K0' parameters (and n/z/zc when present, as set by
        model.eos.build_jcpds for database materials). *k0*/*k0p* override
        the stored values — compute_volume passes its temperature-corrected
        ones on the legacy path. With *with_thermal*, the phase's
        peritheos thermal model (params['thermal_type']) is composed on
        top and no overrides should be given.
        """
        p = jcpds_obj.params
        thermal_type = (p.get("thermal_type") or None) if with_thermal else None
        thermal_parameters = (p.get("thermal_parameters") or {
            "Tr": p.get("t_ref"),
            "theta0": p.get("theta_t0"),
            "gamma0": p.get("gamma_t0"),
            "q": p.get("q_t0", 1.0),
        }) if thermal_type else None
        record_parameters = {}
        records = p.get("eos_records") or []
        index = p.get("eos_current_index") or 0
        if 0 <= index < len(records):
            record_parameters = dict(
                (records[index].get("eos") or {}).get("parameters") or {})
        return cls(
            eos_type=eos_type or p.get("eos_type") or "BM3",
            parameters={
                **record_parameters,
                "V0": p["v0"],
                "K0": k0 if k0 is not None else p["k0"],
                "K0_prime": k0p if k0p is not None
                else (p.get("k0p0") or p.get("k0p")),
                "K0_double_prime": p.get("k0pp0") or 0.0,
            },
            n=(p.get("n") if p.get("n") is not None
               else (thermal_parameters or {}).get("n")),
            z=p.get("z"),
            formula_units_per_cell=p.get("zc"),
            thermal_type=thermal_type,
            thermal_parameters=thermal_parameters,
        )

    def __repr__(self) -> str:
        return f"EosPhase({self.eos_type}, {self._eos!r})"
