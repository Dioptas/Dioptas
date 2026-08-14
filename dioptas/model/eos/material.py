# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
"""
Material and EoS-record structures for the bundled equation-of-state
database.

One material document (a ``.json`` file in ``resources/eos_database/``, or
a user-saved ``.eosmat`` file — same content) looks like::

    {
      "format_version": 2,
      "name": "Gold",
      "formula": "Au",
      "aliases": ["native gold"],
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
      "source": {"kind": "cif", "name": "sample.cif",
                 "text": "data_..."},              # optional, lossless
      "notes": "...",
      "peaks": [[h, k, l, d0, intensity], ...], # optional legacy fallback
      "eos_records": [ <record>, ... ]
    }

Every EoS record is future-proof by construction: it names a Peritheos
class and carries that class's constructor keywords verbatim, so new
equations of state (or thermal models) in Peritheos need data only — no
schema change::

    {
      "label": "Anderson et al 1989",        # record-specific label
      "reference": {
          "authors": ["Anderson", "Isaak", "Yamamoto"],
          "year": 1989,
          "source": "J. Appl. Phys.",
          "volume": "65",
          "locator": "1534-1543",
          "doi": "10.1063/1.342969"
      },
      "default": true,                        # optional preferred record
      "eos": {"type": "BM3",                 # peritheos.eos.rt class name
              "parameters": {"V0": 67.847, "K0": 166.65,
                             "K0_prime": 5.4823}},
      "parameter_errors": {"V0": 0.004,       # same units as parameters
                           "K0": null,          # no verified error recorded
                           "K0_prime": 0.02},
      "fixed_parameters": ["K0"],             # held fixed in the EoS fit
      "experimental_pressure_range_gpa": [0.0, 8.9], # optional fit data
      "pressure_range_status": "theoretical", # alternative when no
                                                 # experimental interval exists
      "experimental_temperature_range_k": [298.0, 298.0], # optional
      "thermal": {"type": "AlphaKT",         # optional
                  "parameters": {"alpha0": 4.2e-5, "dK_dT": -0.02},
                  "parameter_errors": {"alpha0": null, "dK_dT": null},
                  "fixed_parameters": []},
      "temperature_ref": 298.15,             # optional, K
      "notes": "..."                         # optional
    }

``reference.authors`` stores the publication's complete, ordered author list.
``reference.authors_truncated`` remains supported for imported user files
whose source metadata supplies only the first author followed by "et al.";
bundled database records do not use it. ``volume``, ``locator``, ``doi``, and
a free-form ``details`` field (for example, a table or supplementary workbook)
are optional.

``thermal.type`` is reserved for ``peritheos.eos.thermal`` class names
(``MieGruneisenDebye``, ``HollandPowell2011``, ...); the one exception is
``AlphaKT``, the classic JCPDS-style correction (thermal expansion alpha0
and dK/dT applied as a pressure shift) that Dioptas computes itself.
Thermal ``parameters`` likewise use the selected Peritheos constructor's
names verbatim. ``thermal.parameter_errors`` and
``thermal.fixed_parameters`` have the same meaning as their room-temperature
counterparts.

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
``pressure_range_status`` is used instead of a numeric pressure interval for
theoretical EoS records, source compilations, and sources that report their
experimental limit only qualitatively.
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
    """A material with its structure, optional fallback peaks and EoS records."""

    name: str = ""
    formula: str = ""
    #: Material-specific alternative names used by the database search.
    #: Keeping these beside the material avoids ambiguous global aliases
    #: that accidentally match every polymorph with the same chemistry.
    aliases: list = field(default_factory=list)
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
    #: Optional lossless source document. CIF-derived materials keep the
    #: original text here so recalculating reflections does not depend on the
    #: normalized atom-site projection alone. This is material provenance,
    #: unlike the runtime ownership state (bundled/file/custom), which is
    #: deliberately kept on the loaded phase and is not exported.
    source: dict = field(default_factory=dict)
    notes: str = ""
    #: [h, k, l, d0, intensity] per peak.  Used only when the complete
    #: structure needed for PhaseSmith calculation is unavailable.
    peaks: list = field(default_factory=list)
    #: EoS record dicts, schema in the module docstring
    eos_records: list = field(default_factory=list)

    @property
    def display_name(self) -> str:
        """'Gold (Au)' when name and formula differ, else just the name."""
        if self.formula and self.formula != self.name:
            return f"{self.name} ({self.formula})"
        return self.name

    @property
    def default_eos_index(self) -> int:
        """Preferred EoS record, falling back to the first for old files."""
        for index, record in enumerate(self.eos_records):
            if record.get("default") is True:
                return index
        return 0

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
            "format_version": 2,
            "name": self.name,
            "formula": self.formula,
            "aliases": list(self.aliases),
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
            "source": dict(self.source),
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
            aliases=[str(alias) for alias in document.get("aliases", [])
                     if alias],
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
            source=dict(document.get("source") or {}),
            notes=document.get("notes") or "",
            peaks=[list(peak) for peak in document.get("peaks", [])],
            eos_records=list(document.get("eos_records", [])),
        )


def record_label(record: dict) -> str:
    """Display label, including the experimental fit domain when known."""
    label = record.get("label") or reference_short(record.get("reference"))
    pressure_range = record_pressure_range(record)
    return f"{label} [{pressure_range}]" if pressure_range else label


def reference_authors(reference: dict | str | None) -> str:
    """Compact author display (``Dewaele et al.``) for a reference."""
    if not isinstance(reference, dict):
        return _legacy_reference_authors(reference or "")

    authors = [str(author) for author in reference.get("authors", [])
               if author]
    if not authors:
        return ""
    if reference.get("authors_truncated") or len(authors) > 2:
        return f"{authors[0]} et al."
    if len(authors) == 2:
        return f"{authors[0]} and {authors[1]}"
    return authors[0]


def reference_year(reference: dict | str | None) -> str:
    """Publication year as display text, including legacy string records."""
    if isinstance(reference, dict):
        year = reference.get("year")
        return str(year) if year is not None else ""
    matches = re.findall(r"\((\d{4})\)", reference or "")
    return matches[-1] if matches else ""


def reference_short(reference: dict | str | None) -> str:
    """Compact author/year citation suitable for narrow controls."""
    authors = reference_authors(reference)
    year = reference_year(reference)
    if authors and year:
        return f"{authors} ({year})"
    return authors or year or reference_text(reference)


def reference_text(reference: dict | str | None) -> str:
    """
    Reconstruct the complete citation from a structured reference.

    String references remain supported for projects and ``.eosmat`` files
    created by versions using the format-1 schema.
    """
    if not reference:
        return ""
    if isinstance(reference, str):
        return reference
    if not isinstance(reference, dict):
        return str(reference)

    authors = [str(author) for author in reference.get("authors", [])
               if author]
    if reference.get("authors_truncated") and authors:
        author_text = f"{authors[0]} et al."
    elif len(authors) > 2:
        author_text = f"{', '.join(authors[:-1])}, and {authors[-1]}"
    elif len(authors) == 2:
        author_text = f"{authors[0]} and {authors[1]}"
    else:
        author_text = authors[0] if authors else ""

    source = str(reference.get("source") or "")
    volume = str(reference.get("volume") or "")
    locator = str(reference.get("locator") or "")
    publication = source
    if volume:
        publication += f" {volume}"
    if locator:
        publication += f", {locator}"

    parts = [part for part in (author_text, publication) if part]
    text = ", ".join(parts)
    year = reference.get("year")
    if year is not None:
        text += f" ({year})"
    details = reference.get("details")
    if details:
        text += f", {details}"
    doi = reference.get("doi")
    if doi:
        text += f", doi:{doi}"
    return text


def _legacy_reference_authors(reference: str) -> str:
    """Best-effort compact author text for a format-1 citation string."""
    if not reference:
        return ""
    prefix = reference.split(",", 1)[0].strip()
    if " et al." in prefix:
        return prefix
    if " and " in prefix:
        return prefix
    # Multi-author legacy strings put the conjunction after a comma.
    match = re.match(r"^(.+?, and [^,]+),", reference)
    if match:
        names = [name.strip() for name in
                 match.group(1).replace(", and ", ", ").split(",")]
        return f"{names[0]} et al." if len(names) > 2 else match.group(1)
    return prefix


def record_pressure_range(record: dict) -> str:
    """Human-readable fit pressure domain or explicit non-numeric status."""
    values = record.get("experimental_pressure_range_gpa")
    if isinstance(values, (list, tuple)) and len(values) == 2:
        low, high = values
        try:
            if float(low) == float(high):
                return f"{float(low):g} GPa"
            return f"{float(low):g}\N{EN DASH}{float(high):g} GPa"
        except (TypeError, ValueError):
            pass
    statuses = {
        "theoretical": "theoretical",
        "reference_parameterization": "reference model",
        "reported_qualitatively": "qualitative limit",
    }
    return statuses.get(record.get("pressure_range_status"), "")


def record_eos_type(record: dict) -> str:
    """Peritheos class name of an EoS record, e.g. 'BM3'."""
    return (record.get("eos") or {}).get("type") or "BM3"


def _parse_formula(formula: str) -> list:
    """
    Parse a simple chemical formula into ``(element, amount)`` pairs.

    Decimal occupancies and Unicode subscript/superscript digits are
    accepted so searches such as ``Mg₀.₂Fe₀.₈O`` can be compared with
    integer-ratio formulas stored by the database. Returns ``[]`` for
    names and for formulas containing unsupported grouping syntax.
    """
    if not formula:
        return []
    normalized = formula.translate(str.maketrans(
        "₀₁₂₃₄₅₆₇₈₉⁰¹²³⁴⁵⁶⁷⁸⁹",
        "01234567890123456789",
    )).strip()
    token = re.compile(r"([A-Z][a-z]?)(\d+(?:\.\d*)?|\.\d+)?")
    parsed = []
    position = 0
    while position < len(normalized):
        match = token.match(normalized, position)
        if match is None:
            return []
        element, amount_text = match.groups()
        if amount_text:
            amount = (float(amount_text) if "." in amount_text
                      else int(amount_text))
            if amount <= 0:
                return []
        else:
            amount = 1
        parsed.append((element, amount))
        position = match.end()
    return parsed
