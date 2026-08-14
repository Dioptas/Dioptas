# SPDX-License-Identifier: MIT
from __future__ import annotations

import os
import re
from pathlib import Path

from ..eos.material import Lattice, Material
from .jcpds import jcpds


class CifConverter:
    """Convert CIF structures into Dioptas phase records using PhaseSmith."""

    def __init__(
        self,
        wavelength: float,
        min_d_spacing: float = 0.5,
        min_intensity: float = 0.5,
    ) -> None:
        self.wavelength = wavelength
        self.min_d_spacing = min_d_spacing
        self.min_intensity = min_intensity

    def convert_cif_to_jcpds(self, filename: str) -> jcpds:
        """Read *filename* into a canonical Material and build its phase."""
        from ..eos import build_jcpds

        material = self.convert_cif_to_material(filename)
        phase = build_jcpds(
            material,
            minimum_d_spacing=self.min_d_spacing,
            minimum_intensity=self.min_intensity,
            wavelength_angstrom=self.wavelength,
            origin="cif",
        )
        phase.filename = filename
        phase.name = (
            material.display_name
            or os.path.splitext(os.path.basename(filename))[0]
        )
        phase.params["comments"] = [material.name]
        phase.params["modified"] = False
        return phase

    def convert_cif_to_material(self, filename: str) -> Material:
        """Read *filename* as a normalized, lossless EoS Material.

        The normalized lattice, formula, space group, crystallographic Z and
        atom sites support the shared material workflow. The original CIF text
        remains attached as provenance and as the authoritative reflection
        source, preserving information that the compact material schema does
        not model yet (anisotropic displacement, disorder groups, and so on).
        """
        from phasesmith.io.cif import read_cif

        structure = read_cif(filename, strict=False).structure
        cell = structure.cell
        metadata = dict(structure.metadata)
        formula = _normalized_formula(
            metadata.get("chemical_formula_sum") or structure.name
        )
        z_value = metadata.get("formula_units_per_cell")
        formula_units = None
        if z_value not in (None, ""):
            numeric_z = float(z_value)
            if numeric_z.is_integer():
                formula_units = int(numeric_z)

        space_group_number = metadata.get("space_group_number")
        if space_group_number not in (None, ""):
            space_group_number = int(space_group_number)
        else:
            space_group_number = None

        atom_sites = []
        for site in structure.sites:
            x, y, z = site.fractional_xyz
            atom_site = {
                "site_id": site.site_id,
                "label": site.source_label,
                "element": site.element_symbol,
                "type_symbol": site.type_symbol,
                "x": float(x), "y": float(y), "z": float(z),
                "occupancy": float(site.occupancy),
            }
            for key in ("u_iso_angstrom2", "charge", "isotope"):
                value = getattr(site, key, None)
                if value is not None:
                    atom_site[key] = value
            atom_sites.append(atom_site)

        return Material(
            name=structure.name or Path(filename).stem,
            formula=formula,
            symmetry=structure.space_group.crystal_system.upper(),
            lattice=Lattice(
                a=cell.a_angstrom,
                b=cell.b_angstrom,
                c=cell.c_angstrom,
                alpha=cell.alpha_deg,
                beta=cell.beta_deg,
                gamma=cell.gamma_deg,
            ),
            formula_units_per_cell=formula_units,
            space_group=str(metadata.get("space_group_hm") or ""),
            space_group_number=space_group_number,
            atom_sites=atom_sites,
            source={
                "kind": "cif",
                "text": Path(filename).read_text(encoding="utf-8"),
                "name": Path(filename).name,
            },
        )


def _normalized_formula(value: str) -> str:
    """Turn a CIF sum formula such as ``Fe0.3 Mg0.7 O1`` into a token."""
    compact = re.sub(r"\s+", "", str(value or ""))
    if not compact or any(character in compact for character in "()[]"):
        return compact
    return re.sub(r"([A-Z][a-z]?)1(?=[A-Z]|$)", r"\1", compact)
