# SPDX-License-Identifier: MIT
"""PhaseSmith adapters for Dioptas phase-line calculations.

The EoS database stores a crystallographic asymmetric unit as its source of
truth.  This module turns that structure into the compact reflection records
used by the existing :mod:`jcpds` phase model.  Stored peak tables remain a
fallback for legacy materials whose structure is incomplete.
"""

from __future__ import annotations

from dataclasses import replace
from functools import lru_cache
from math import asin, degrees, pi
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from phasesmith import CrystalStructure

    from ..eos.material import Material


DEFAULT_WAVELENGTH_ANGSTROM = 0.31
DEFAULT_MIN_D_SPACING_ANGSTROM = 0.5
DEFAULT_MIN_INTENSITY_PERCENT = 0.5
REFLECTION_Q_MARGIN = 1.05
TWO_THETA_MERGE_TOLERANCE_DEG = 1.0e-5

# Short monoclinic symbols do not always select a unique conventional setting.
# Keep aliases here, at the adapter boundary, rather than rewriting literature
# provenance in every material document.
_SPACE_GROUP_ALIASES = {
    "P21/a": "P 1 21/a 1",
}


def material_has_complete_structure(material: Material) -> bool:
    """Return whether *material* contains everything needed for intensities."""

    lattice = material.lattice
    return bool(
        lattice.a
        and (lattice.b or lattice.a)
        and (lattice.c or lattice.a)
        and material.space_group
        and material.atom_sites
    )


@lru_cache(maxsize=256)
def _space_group_info(symbol: str, expected_number: int | None):
    from phasesmith.io.space_groups import space_group_by_symbol

    lookup_symbol = _SPACE_GROUP_ALIASES.get(symbol, symbol)
    info = space_group_by_symbol(lookup_symbol)
    if expected_number is not None and info.number != expected_number:
        raise ValueError(
            f"space-group symbol {symbol!r} resolves to number {info.number}, "
            f"not the stored number {expected_number}"
        )
    return info


@lru_cache(maxsize=256)
def _reflection_generator(symbol: str, expected_number: int | None):
    from phasesmith import PreparedReflectionGenerator

    return PreparedReflectionGenerator(
        _space_group_info(symbol, expected_number).space_group
    )


def structure_from_material(material: Material) -> CrystalStructure:
    """Build a typed PhaseSmith structure from one database material."""

    if not material_has_complete_structure(material):
        raise ValueError(f"{material.display_name} has no complete crystal structure")

    from phasesmith import AtomSite, CrystalStructure, UnitCell

    lattice = material.lattice
    info = _space_group_info(material.space_group, material.space_group_number)
    sites = []
    for index, site in enumerate(material.atom_sites, start=1):
        element = str(site.get("element") or "").strip()
        if not element:
            raise ValueError(
                f"{material.display_name} atom site {index} has no element"
            )
        site_id = str(site.get("site_id") or f"{element}{index}")
        source_label = str(
            site.get("label") or f"{element} {site.get('wyckoff', index)}"
        )
        sites.append(
            AtomSite(
                site_id=site_id,
                source_label=source_label,
                type_symbol=str(site.get("type_symbol") or element),
                element_symbol=element,
                fractional_xyz=(
                    float(site["x"]),
                    float(site["y"]),
                    float(site["z"]),
                ),
                occupancy=float(site.get("occupancy", 1.0)),
                u_iso_angstrom2=(
                    None
                    if site.get("u_iso_angstrom2") is None
                    else float(site["u_iso_angstrom2"])
                ),
                charge=site.get("charge"),
                isotope=site.get("isotope"),
            )
        )

    return CrystalStructure(
        structure_id=material.formula or material.name,
        name=material.display_name,
        cell=UnitCell(
            lattice.a,
            lattice.b or lattice.a,
            lattice.c or lattice.a,
            lattice.alpha,
            lattice.beta,
            lattice.gamma,
        ),
        space_group=info.space_group,
        sites=tuple(sites),
        metadata={
            "space_group_symbol": material.space_group,
            "space_group_number": str(info.number),
        },
    )


def calculate_material_reflections(
    material: Material,
    *,
    minimum_d_spacing: float = DEFAULT_MIN_D_SPACING_ANGSTROM,
    minimum_intensity: float = DEFAULT_MIN_INTENSITY_PERCENT,
    wavelength_angstrom: float = DEFAULT_WAVELENGTH_ANGSTROM,
) -> list[tuple[int, int, int, float, float]]:
    """Calculate ``(h, k, l, d, I)`` rows for a complete material."""

    structure = structure_from_material(material)
    generator = _reflection_generator(
        material.space_group, material.space_group_number
    )
    return calculate_structure_reflections(
        structure,
        generator=generator,
        minimum_d_spacing=minimum_d_spacing,
        minimum_intensity=minimum_intensity,
        wavelength_angstrom=wavelength_angstrom,
    )


def minimum_d_spacing_for_pattern(
    x_values,
    unit: str,
    wavelength_angstrom: float,
    *,
    fallback: float = DEFAULT_MIN_D_SPACING_ANGSTROM,
    q_margin: float = REFLECTION_Q_MARGIN,
) -> float:
    """Return the d cutoff covering the complete pattern plus a Q margin."""

    values = np.asarray(x_values, dtype=float)
    values = values[np.isfinite(values)]
    if not len(values) or wavelength_angstrom <= 0:
        return fallback

    if unit == "q_A^-1":
        positive = values[values > 0]
        measured_q_max = float(np.max(positive)) if len(positive) else 0.0
    elif unit == "d_A":
        positive = values[values > 0]
        measured_q_max = (
            float(2.0 * pi / np.min(positive)) if len(positive) else 0.0
        )
    elif unit == "2th_deg":
        valid = values[(values > 0) & (values < 180)]
        measured_q_max = (
            float(
                np.max(
                    4.0
                    * pi
                    / wavelength_angstrom
                    * np.sin(np.deg2rad(valid) / 2.0)
                )
            )
            if len(valid)
            else 0.0
        )
    else:
        raise ValueError(f"unsupported diffraction unit {unit!r}")

    if measured_q_max <= 0:
        return fallback

    # The LP correction is defined only inside the elastic-scattering sphere.
    physical_q_max = np.nextafter(4.0 * pi / wavelength_angstrom, 0.0)
    target_q_max = min(measured_q_max * q_margin, physical_q_max)
    return 2.0 * pi / target_q_max


def calculate_reflection_source(
    source: dict,
    *,
    minimum_d_spacing: float,
    minimum_intensity: float,
    wavelength_angstrom: float,
) -> list[tuple[int, int, int, float, float]]:
    """Recalculate reflections from a serializable phase structure source."""

    kind = source.get("kind")
    if kind == "material":
        from ..eos.material import Material

        structure = structure_from_material(Material.from_dict(source["material"]))
    elif kind == "cif":
        from phasesmith.io.cif import read_cif

        structure = read_cif(source["text"], strict=False).structure
        # Preserve Dioptas' neutral-atom scattering convention for CIFs.
        structure = replace(
            structure,
            sites=tuple(
                replace(site, type_symbol=site.element_symbol, charge=None)
                for site in structure.sites
            ),
        )
    else:
        raise ValueError(f"unsupported reflection source {kind!r}")

    return calculate_structure_reflections(
        structure,
        minimum_d_spacing=minimum_d_spacing,
        minimum_intensity=minimum_intensity,
        wavelength_angstrom=wavelength_angstrom,
    )


def calculate_structure_reflections(
    structure: CrystalStructure,
    *,
    generator=None,
    minimum_d_spacing: float = DEFAULT_MIN_D_SPACING_ANGSTROM,
    minimum_intensity: float = DEFAULT_MIN_INTENSITY_PERCENT,
    wavelength_angstrom: float = DEFAULT_WAVELENGTH_ANGSTROM,
) -> list[tuple[int, int, int, float, float]]:
    """Calculate normalized powder lines from a PhaseSmith structure.

    PhaseSmith intentionally preserves distinct accidental equal-d families.
    Dioptas historically displays those as one line, so this compatibility
    adapter merges them using the same two-theta tolerance as the old CIF
    converter before normalizing and applying the intensity cutoff.
    """

    from phasesmith import (
        BraggBrentanoUnpolarizedLp,
        DSpacingRange,
        PreparedReflectionGenerator,
        XrayNonResonant,
        calculate_structure_factor_values,
    )

    if minimum_d_spacing <= 0:
        raise ValueError("minimum_d_spacing must be positive")
    if not 0 <= minimum_intensity < 100:
        raise ValueError("minimum_intensity must be in [0, 100)")
    if wavelength_angstrom <= 0 or minimum_d_spacing <= wavelength_angstrom / 2:
        raise ValueError(
            "minimum_d_spacing must exceed half the calculation wavelength"
        )

    if generator is None:
        generator = PreparedReflectionGenerator(structure.space_group)
    max_d_spacing = max(100.0, 10.0 * max(structure.cell.as_tuple()[:3]))
    generated = generator.generate(
        structure.cell,
        DSpacingRange(minimum_d_spacing, max_d_spacing),
    )
    if not len(generated.hkl):
        return []

    values = calculate_structure_factor_values(
        structure,
        generated.hkl,
        generated.multiplicity,
        XrayNonResonant(),
        correction=BraggBrentanoUnpolarizedLp(wavelength_angstrom),
    )
    merged = _merge_equal_two_theta(
        generated.conventional_hkl,
        generated.d_spacing_angstrom,
        values.integrated_intensity,
        wavelength_angstrom,
    )
    max_intensity = max(row[4] for row in merged)
    if not np.isfinite(max_intensity) or max_intensity <= 0:
        raise ValueError(f"{structure.name} produced no positive reflection intensity")

    result = []
    for h, k, ell, d_spacing, intensity in merged:
        scaled = float(intensity / max_intensity * 100.0)
        if scaled > minimum_intensity:
            result.append((h, k, ell, d_spacing, scaled))
    return result


def _merge_equal_two_theta(hkl, d_spacings, intensities, wavelength):
    rows = sorted(
        zip(hkl, d_spacings, intensities, strict=True),
        key=lambda row: float(row[1]),
        reverse=True,
    )
    merged: list[list[float | int]] = []
    last_two_theta = None
    for indices, d_spacing, intensity in rows:
        d_value = float(d_spacing)
        two_theta = degrees(2.0 * asin(wavelength / (2.0 * d_value)))
        if (
            merged
            and last_two_theta is not None
            and abs(two_theta - last_two_theta) < TWO_THETA_MERGE_TOLERANCE_DEG
        ):
            merged[-1][4] += float(intensity)
        else:
            merged.append(
                [
                    int(indices[0]),
                    int(indices[1]),
                    int(indices[2]),
                    d_value,
                    float(intensity),
                ]
            )
            last_two_theta = two_theta
    return [tuple(row) for row in merged]
