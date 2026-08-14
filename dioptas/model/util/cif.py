# SPDX-License-Identifier: MIT
from __future__ import annotations

import os
from dataclasses import replace

from .jcpds import jcpds, jcpds_reflection


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
        """Read *filename* and calculate its powder reflections."""
        from phasesmith.io.cif import read_cif

        from .phasesmith import calculate_structure_reflections

        structure = read_cif(filename, strict=False).structure
        cell = structure.cell

        phase = jcpds()
        phase.params["a0"] = cell.a_angstrom
        phase.params["b0"] = cell.b_angstrom
        phase.params["c0"] = cell.c_angstrom
        phase.params["alpha0"] = cell.alpha_deg
        phase.params["beta0"] = cell.beta_deg
        phase.params["gamma0"] = cell.gamma_deg
        phase.params["v0"] = cell.geometry().volume_angstrom3
        phase.params["symmetry"] = structure.space_group.crystal_system.upper()
        phase.params["comments"] = [structure.name]

        # CIF oxidation states are useful provenance, but the PhaseSmith X-ray
        # table intentionally does not contain every possible ion. Dioptas has
        # historically used neutral-atom factors, so retain that convention.
        structure = replace(
            structure,
            sites=tuple(
                replace(site, type_symbol=site.element_symbol, charge=None)
                for site in structure.sites
            ),
        )
        for h, k, ell, d_spacing, intensity in calculate_structure_reflections(
            structure,
            minimum_d_spacing=self.min_d_spacing,
            minimum_intensity=self.min_intensity,
            wavelength_angstrom=self.wavelength,
        ):
            phase.reflections.append(
                jcpds_reflection(
                    h=h,
                    k=k,
                    l=ell,
                    intensity=intensity,
                    d=d_spacing,
                )
            )

        phase.filename = filename
        phase.name = os.path.splitext(os.path.basename(filename))[0]
        phase.params["modified"] = False
        return phase
