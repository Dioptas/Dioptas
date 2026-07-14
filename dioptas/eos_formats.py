# SPDX-License-Identifier: MIT
"""
EoS material format utilities.

Provides:
- build_jcpds(material, eos)        -> jcpds object ready for Dioptas
- write_eosmat(path, material, eos) -> .eosmat file (see format below)
- read_eosmat(path)                 -> (Material, EosParameters | None)

All functions work on the pydantic models in eos_models.py (Material,
EosParameters, ...). Plain dicts from the API are accepted too and are
converted at the boundary.

The .eosmat format
-------------------
A plain-text, line-oriented format: one ``KEY value`` pair per line, plus
a single comment header documenting the diffraction-peak table that
follows. Unlike JCPDS's ``DIHKL`` lines, the peak keyword is not repeated
for every row — one comment line explains the column order once, and the
peaks themselves are just whitespace-separated numbers.

Example
-------
# EoS Material File - Gold (Au)

NAME       Gold
FORMULA    Au
SPACEGROUP CUBIC
A          4.0786   # Å

EOS_TYPE   Birch-Murnaghan
EOS_ORDER  3
K0         167.0    # GPa
K0_PRIME   6.0

# Diffraction peaks: h  k  l  d(Å)  intensity
1  1  1  2.3550  100.0
"""

from __future__ import annotations

import datetime
from typing import Optional, Tuple, Union

from .eos_models import Material, EosParameters, Peak, Lattice


def _as_material(material: Union[Material, dict]) -> Material:
    return material if isinstance(material, Material) else Material.from_api(material)


def _as_eos(eos: Union[EosParameters, dict, None]) -> Optional[EosParameters]:
    if eos is None or isinstance(eos, EosParameters):
        return eos
    return EosParameters.from_api(eos)


# ---------------------------------------------------------------------------
# jcpds object builder
# ---------------------------------------------------------------------------

def build_jcpds(material: Union[Material, dict],
                eos: Union[EosParameters, dict, None] = None,
                all_eos: Optional[list] = None):
    """
    Build a Dioptas ``jcpds`` object from a Material (+ optional
    EosParameters). The phase is named "<formula> (<reference>)" so both
    the chemistry and the literature source are visible in the phase list.

    When ``all_eos`` is given (every EoS record of the material), they are
    stored on the phase so the user can switch between references from the
    phase table later (PhaseModel.set_eos_reference).
    """
    from .model.util.jcpds import jcpds, jcpds_reflection

    material = _as_material(material)
    eos = _as_eos(eos)

    obj = jcpds()

    # Phase name: chemistry + reference, e.g. "Au (Anderson et al 1989)"
    chemistry = material.formula or material.name or "unknown"
    if eos is not None and eos.reference:
        ref = _short_reference(eos.reference, material)
        name = f"{chemistry} ({ref})" if ref else chemistry
    else:
        name = chemistry
    obj._name = name
    obj._filename = name

    # Lattice
    lat = material.lattice
    obj.params["symmetry"] = lat.symmetry
    obj.params["a0"] = lat.a
    obj.params["b0"] = lat.b or lat.a
    obj.params["c0"] = lat.c or lat.a
    obj.params["alpha0"] = lat.alpha
    obj.params["beta0"] = lat.beta
    obj.params["gamma0"] = lat.gamma
    for key in ("a", "b", "c", "alpha", "beta", "gamma"):
        obj.params[key] = obj.params[f"{key}0"]

    # EoS parameters
    if eos is not None:
        obj.params["k0"] = eos.k0 or 0.0
        obj.params["k0p0"] = eos.k0_prime or 0.0
        obj.params["k0p"] = obj.params["k0p0"]
        obj.params["alpha_t0"] = eos.alpha0 or 0.0
        obj.params["dk0dt"] = eos.dK_dT or 0.0
        obj.params["eos_type"] = eos.engine_type
        if eos.v0:
            obj.params["v0"] = eos.v0
            obj.params["v"] = eos.v0

    # Holzapfel needs atoms/electrons per formula and formula units per
    # cell. Store them whenever derivable, so switching the phase's EoS
    # dropdown to Holzapfel later works without reloading.
    n = material.atoms_per_formula()
    z = material.electrons_per_formula()
    if n is not None and z is not None:
        obj.params["n"] = n
        obj.params["z"] = z
    if material.formula_units_per_cell:
        obj.params["zc"] = material.formula_units_per_cell

    # Diffraction peaks
    for peak in material.peaks:
        obj.reflections.append(jcpds_reflection(
            h=peak.h, k=peak.k, l=peak.l,
            intensity=peak.intensity, d=peak.d_spacing,
        ))

    # All EoS records of this material, for the per-phase reference
    # switcher. Stored as plain attributes (not in params, which only
    # holds numbers/strings for the jcpds file format).
    records = [_as_eos(e) for e in (all_eos if all_eos else
                                    ([eos] if eos is not None else []))]
    obj.chemistry = chemistry
    obj.eos_records = records
    obj.eos_record_labels = [_short_reference(e.reference, material)
                             for e in records]
    obj.eos_current_index = 0
    if eos is not None:
        for i, rec in enumerate(records):
            if rec.id is not None and rec.id == eos.id:
                obj.eos_current_index = i
                break

    obj.params["modified"] = False
    return obj


# ---------------------------------------------------------------------------
# .eosmat writer
# ---------------------------------------------------------------------------

def write_eosmat(path: str,
                 material: Union[Material, dict],
                 eos: Union[EosParameters, dict, None] = None) -> None:
    """Write a compact, comment-documented ``.eosmat`` file."""
    material = _as_material(material)
    eos = _as_eos(eos)
    today = datetime.date.today().isoformat()

    lines = [
        f"# EoS Material File - {material.display_name}",
        f"# Generated by Dioptas / EoS Database - {today}",
    ]
    if eos is not None and eos.reference:
        lines.append(f"# EoS reference: {eos.reference}")
    lines.append("")

    lat = material.lattice
    lines += [
        f"NAME       {material.name}",
        f"FORMULA    {material.formula}",
        f"SPACEGROUP {lat.symmetry}",
        f"A          {_num(lat.a)}   # Å",
        f"B          {_num(lat.b or lat.a)}   # Å",
        f"C          {_num(lat.c or lat.a)}   # Å",
    ]
    if material.formula_units_per_cell:
        lines.append(f"FORMULA_UNITS {material.formula_units_per_cell}"
                     "   # formula units per unit cell (crystallographic Z)")
    if material.notes:
        lines.append(f"NOTES      {material.notes}")
    lines.append("")

    if eos is not None:
        lines.append(f"EOS_TYPE   {eos.eos_type}")
        if eos.eos_order is not None:
            lines.append(f"EOS_ORDER  {eos.eos_order}")
        lines += [
            f"REFERENCE  {eos.reference}",
            f"V0         {_num(eos.v0)}   # Å³",
            f"K0         {_num(eos.k0)}   # GPa",
            f"K0_PRIME   {_num(eos.k0_prime)}",
        ]
        if eos.alpha0 is not None:
            lines.append(f"ALPHA_T    {_num(eos.alpha0)}  # K⁻¹")
        if eos.dK_dT is not None:
            lines.append(f"DK_DT      {_num(eos.dK_dT)}  # GPa K⁻¹")
        if eos.reference_temperature is not None:
            lines.append(f"T_REF      {_num(eos.reference_temperature)}  # K")
        lines.append("")

    if material.peaks:
        lines.append("# Diffraction peaks: h  k  l  d(Å)  intensity")
        for pk in material.peaks:
            lines.append(f"{pk.h}  {pk.k}  {pk.l}  "
                         f"{pk.d_spacing:.4f}  {pk.intensity:.1f}")

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# .eosmat reader
# ---------------------------------------------------------------------------

# KEY -> (model section, field name, type). One table instead of if/elif.
_KEY_MAP = {
    "NAME":          ("material", "name", str),
    "FORMULA":       ("material", "formula", str),
    "NOTES":         ("material", "notes", str),
    "FORMULA_UNITS": ("material", "formula_units_per_cell", int),
    "SPACEGROUP":    ("lattice", "symmetry", str),
    "A":             ("lattice", "a", float),
    "B":             ("lattice", "b", float),
    "C":             ("lattice", "c", float),
    "EOS_TYPE":      ("eos", "eos_type", str),
    "EOS_ORDER":     ("eos", "eos_order", int),
    "REFERENCE":     ("eos", "reference", str),
    "V0":            ("eos", "v0", float),
    "K0":            ("eos", "k0", float),
    "K0_PRIME":      ("eos", "k0_prime", float),
    "ALPHA_T":       ("eos", "alpha0", float),
    "DK_DT":         ("eos", "dK_dT", float),
    "T_REF":         ("eos", "reference_temperature", float),
}


def read_eosmat(path: str) -> Tuple[Material, Optional[EosParameters]]:
    """Parse a ``.eosmat`` file back into (Material, EosParameters)."""
    sections = {"material": {}, "lattice": {}, "eos": {}}
    peaks = []
    in_peaks = False

    with open(path, "r", encoding="utf-8") as fh:
        for raw_line in fh:
            if raw_line.strip().startswith("#"):
                if "peak" in raw_line.lower():
                    in_peaks = True
                continue
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue

            if in_peaks:
                parts = line.split()
                if len(parts) >= 5:
                    peaks.append(Peak(
                        h=int(float(parts[0])), k=int(float(parts[1])),
                        l=int(float(parts[2])),
                        d_spacing=float(parts[3]),
                        intensity=float(parts[4]),
                    ))
                continue

            key, _, value = line.partition(" ")
            entry = _KEY_MAP.get(key.strip().upper())
            if entry is not None:
                section, field, cast = entry
                sections[section][field] = cast(value.strip())

    material = Material(
        **sections["material"],
        lattice=Lattice(**sections["lattice"]),
        peaks=peaks,
    )
    eos = EosParameters(**sections["eos"]) if sections["eos"] else None
    return material, eos


def _short_reference(reference: str, material: Material) -> str:
    """
    Tidy a reference for use in the phase name. Many database references
    start with the material name (e.g. "Gold (04-0784, shock wave)") —
    repeating it after the formula would give "Au (Gold (04-0784, ...))",
    so strip that leading name and any enclosing parentheses.
    """
    ref = reference.strip()
    for prefix in (material.name, material.formula):
        if prefix and ref.lower().startswith(prefix.lower()):
            ref = ref[len(prefix):].strip()
    if ref.startswith("(") and ref.endswith(")"):
        ref = ref[1:-1].strip()
    return ref


def _num(value) -> str:
    return "0" if value is None else f"{float(value)}"
