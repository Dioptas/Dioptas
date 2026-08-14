# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
"""
Turns an EoS-database Material into a Dioptas jcpds phase, and reads/
writes ``.eosmat`` material files.

A ``.eosmat`` file is simply one material document in JSON — byte-for-byte
the same schema as the bundled ``resources/eos_database/*.json`` files
(see material.py), so exported materials, bundled materials and the
records stored inside ``.dio`` projects all share one format.
"""

from __future__ import annotations

import copy
import json
from math import pi

from .material import (Material, record_eos_type, record_label,
                       reference_text)


def build_jcpds(
    material: Material,
    record_index: int | None = None,
    *,
    minimum_d_spacing: float = 0.5,
    minimum_intensity: float = 0.5,
    wavelength_angstrom: float = 0.31,
    origin: str = "custom",
):
    """
    Build a Dioptas ``jcpds`` object from a Material, applying the EoS
    preferred record (or the explicitly supplied *record_index*) when the
    material has any. The phase display name combines the mineral/material
    name and chemistry ("Akimotoite (MgSiO3)"). The active literature
    reference is shown separately in the phase table's Ref column.

    All EoS records are stored on the phase state, so the user can switch
    between literature references from the phase table later
    (PhaseModel.set_eos_reference) and the choice survives project
    save/load and undo.
    """
    from ..util.jcpds import jcpds, jcpds_reflection

    obj = jcpds()

    chemistry = material.formula or material.name or "unknown"
    records = copy.deepcopy(material.eos_records)
    record = None
    if records:
        if record_index is None:
            record_index = material.default_eos_index
        record_index = max(0, min(record_index, len(records) - 1))
        record = records[record_index]

    obj._name = material.display_name or chemistry
    obj._filename = chemistry

    # Lattice
    lat = material.lattice
    obj.params["symmetry"] = material.symmetry
    obj.params["a0"] = lat.a
    obj.params["b0"] = lat.b or lat.a
    obj.params["c0"] = lat.c or lat.a
    obj.params["alpha0"] = lat.alpha
    obj.params["beta0"] = lat.beta
    obj.params["gamma0"] = lat.gamma
    for key in ("a", "b", "c", "alpha", "beta", "gamma"):
        obj.params[key] = obj.params[f"{key}0"]

    # Holzapfel-type equations need atoms/electrons per formula and the
    # formula units per cell; store them whenever derivable so switching
    # the phase's EoS dropdown later works without reloading.
    n = material.atoms_per_formula()
    z = material.electrons_per_formula()
    if n is not None and z is not None:
        obj.params["n"] = n
        obj.params["z"] = z
    if material.formula_units_per_cell:
        obj.params["zc"] = material.formula_units_per_cell

    # A complete crystal structure is the source of truth.  Legacy records
    # without one retain their stored JCPDS/reference peak table as a fallback.
    from ..util.phasesmith import (
        calculate_material_reflections,
        material_has_complete_structure,
    )
    cif_source = (
        material.source
        if material.source.get("kind") == "cif" and material.source.get("text")
        else None
    )
    if cif_source or material_has_complete_structure(material):
        if cif_source:
            from ..util.phasesmith import calculate_reflection_source
            peak_rows = calculate_reflection_source(
                cif_source,
                minimum_d_spacing=minimum_d_spacing,
                minimum_intensity=minimum_intensity,
                wavelength_angstrom=wavelength_angstrom,
            )
        else:
            peak_rows = calculate_material_reflections(
                material,
                minimum_d_spacing=minimum_d_spacing,
                minimum_intensity=minimum_intensity,
                wavelength_angstrom=wavelength_angstrom,
            )
        structure_document = material.to_dict()
        structure_document["peaks"] = []
        structure_document["eos_records"] = []
        obj.state.reflection_source = (
            copy.deepcopy(cif_source) if cif_source else {
                "kind": "material",
                "material": structure_document,
            }
        )
        obj.state.reflection_q_max = 2.0 * pi / minimum_d_spacing
        obj.state.reflection_wavelength = wavelength_angstrom
        obj.state.reflection_intensity_cutoff = minimum_intensity
    else:
        peak_rows = material.peaks
    for h, k, l, d0, intensity in peak_rows:
        obj.reflections.append(jcpds_reflection(
            h=h, k=k, l=l, intensity=intensity, d=d0))

    # Reference switcher state
    obj.params["chemistry"] = chemistry
    obj.params["eos_records"] = records
    obj.params["eos_current_index"] = record_index if record else 0
    obj.params["eos_default_index"] = material.default_eos_index if records else 0
    obj.params["eos_record_origins"] = [origin for _ in records]
    material_document = material.to_dict()
    material_document["eos_records"] = []
    obj.params["material_document"] = material_document
    obj.params["material_origin"] = origin

    if record is not None:
        apply_eos_record(obj, record)
    else:
        obj.compute_v0()
        obj.params["v"] = obj.params["v0"]

    obj.params["modified"] = False
    return obj


def apply_eos_record(phase, record: dict) -> None:
    """
    Copy one EoS record's parameters onto a jcpds phase: bulk modulus,
    K0', V0, the thermal correction, and the equation-of-state type.
    The record's reference goes into the comments, so it is visible in
    the phase editor and survives a jcpds export.
    Shared by build_jcpds and PhaseModel.set_eos_reference.
    """
    eos = record.get("eos") or {}
    parameters = eos.get("parameters") or {}
    phase.params["eos_parameter_errors"] = dict(
        record.get("parameter_errors") or {})
    phase.params["eos_fixed_parameters"] = list(
        record.get("fixed_parameters") or [])
    reference = reference_text(record.get("reference")) or record_label(record)
    if reference:
        phase.params["comments"] = [reference]
    phase.params["k0"] = parameters.get("K0") or 0.0
    # BM2 fixes K0' = 4 by definition; carry that so switching the phase
    # to a 3rd-order equation later starts from the sensible value.
    phase.params["k0p0"] = (parameters.get("K0_prime")
                            or (4.0 if eos.get("type") == "BM2" else 0.0))
    phase.params["k0p"] = phase.params["k0p0"]
    phase.params["k0pp0"] = parameters.get("K0_double_prime") or 0.0
    thermal = record.get("thermal") or {}
    thermal_type = thermal.get("type") or ""
    thermal_parameters = thermal.get("parameters") or {}

    material_document = phase.params.get("material_document") or {}
    base_material = Material.from_dict(material_document) if material_document else None
    if parameters.get("n") is not None:
        phase.params["n"] = parameters["n"]
    elif thermal_parameters.get("n") is not None:
        # Mie-Gruneisen records carry the thermal constructor's atom count
        # inside their thermal parameter block.
        phase.params["n"] = thermal_parameters["n"]
    elif base_material is not None:
        phase.params["n"] = base_material.atoms_per_formula()
    if parameters.get("Z") is not None:
        phase.params["z"] = parameters["Z"]
    elif base_material is not None:
        phase.params["z"] = base_material.electrons_per_formula()

    phase.params["thermal_parameters"] = dict(thermal_parameters)
    phase.params["thermal_parameter_errors"] = dict(
        thermal.get("parameter_errors") or {})
    phase.params["thermal_fixed_parameters"] = list(
        thermal.get("fixed_parameters") or [])
    if thermal_type in ("MieGruneisenDebye", "MieGruneisenEinstein"):
        # full thermal engine: parameters go to the thermal state fields,
        # the legacy coefficients stay zero
        phase.params["thermal_type"] = thermal_type
        phase.params["theta_t0"] = thermal_parameters.get("theta0") or 0.0
        phase.params["gamma_t0"] = thermal_parameters.get("gamma0") or 0.0
        phase.params["q_t0"] = thermal_parameters.get("q", 1.0)
        phase.params["t_ref"] = thermal_parameters.get("Tr") or 298.15
        phase.params["alpha_t0"] = 0.0
        phase.params["d_alpha_dt"] = 0.0
        phase.params["dk0dt"] = 0.0
        phase.params["dk0pdt"] = 0.0
    elif thermal_type == "Sokolova2016":
        # The native Sokolova model has eleven fitted coefficients. Keep
        # its source dictionary intact instead of coercing it into the
        # four-field Debye/Einstein editor representation.
        phase.params["thermal_type"] = thermal_type
        phase.params["t_ref"] = thermal_parameters.get("Tr") or 298.15
        phase.params["theta_t0"] = 0.0
        phase.params["gamma_t0"] = 0.0
        phase.params["q_t0"] = 1.0
        phase.params["alpha_t0"] = 0.0
        phase.params["d_alpha_dt"] = 0.0
        phase.params["dk0dt"] = 0.0
        phase.params["dk0pdt"] = 0.0
    else:
        # 'AlphaKT' (the classic correction) or no thermal data at all
        phase.params["thermal_type"] = ""
        if thermal_type != "AlphaKT":
            thermal_parameters = {}
        phase.params["alpha_t0"] = thermal_parameters.get("alpha0") or 0.0
        phase.params["d_alpha_dt"] = (
            thermal_parameters.get("d_alpha_dT") or 0.0)
        phase.params["dk0dt"] = thermal_parameters.get("dK_dT") or 0.0
        phase.params["dk0pdt"] = (
            thermal_parameters.get("dK_prime_dT") or 0.0)

    phase.params["t_ref"] = (
        thermal_parameters.get("Tr")
        or record.get("temperature_ref")
        or 298.15
    )

    phase.params["eos_type"] = eos.get("type") or "BM3"
    if parameters.get("V0"):
        phase.params["v0"] = parameters["V0"]
        phase.params["v"] = parameters["V0"]


def material_from_jcpds(phase) -> Material:
    """Return a portable :class:`Material` representing the live phase.

    Material-backed phases retain their normalized structure document. A
    legacy JCPDS phase is still exportable: its current reflection table is
    used as the fallback structure. Runtime ownership flags are deliberately
    omitted, so loading the resulting .eosmat creates a user-owned material.
    """
    document = copy.deepcopy(phase.params.get("material_document") or {})
    material = Material.from_dict(document) if document else Material()

    material.name = material.name or phase.name.rstrip("*") or "Material"
    material.formula = (
        material.formula or phase.params.get("chemistry") or phase.name.rstrip("*")
    )
    material.symmetry = phase.params["symmetry"]
    material.lattice.a = phase.params["a0"]
    material.lattice.b = phase.params["b0"]
    material.lattice.c = phase.params["c0"]
    material.lattice.alpha = phase.params["alpha0"]
    material.lattice.beta = phase.params["beta0"]
    material.lattice.gamma = phase.params["gamma0"]
    if phase.params.get("zc"):
        material.formula_units_per_cell = phase.params["zc"]

    records = copy.deepcopy(phase.params.get("eos_records") or [])
    default_index = phase.params.get("eos_default_index") or 0
    for index, record in enumerate(records):
        record.pop("default", None)
        if index == default_index:
            record["default"] = True
    material.eos_records = records

    has_structure = bool(material.atom_sites and material.space_group)
    has_lossless_source = bool(
        material.source.get("kind") == "cif" and material.source.get("text")
    )
    if not has_structure and not has_lossless_source:
        material.peaks = [
            [r.h, r.k, r.l, r.d0, r.intensity]
            for r in phase.reflections
        ]
    return material


def save_material_file(path: str, material: Material) -> None:
    """Write a material as a ``.eosmat`` (JSON) file."""
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(_format_material_json(material.to_dict()))


def _format_material_json(document: dict) -> str:
    """Render each peak and atom site compactly on one line."""
    document = copy.deepcopy(document)
    replacements = {}
    compact_peaks = []
    for index, peak in enumerate(document.get("peaks", [])):
        marker = f"\0DIOPTAS_PEAK_ROW_{index:06d}\0"
        encoded_marker = json.dumps(marker)
        replacements[encoded_marker] = json.dumps(
            peak, ensure_ascii=False, separators=(", ", ": ")
        )
        compact_peaks.append(marker)
    document["peaks"] = compact_peaks

    compact_sites = []
    for index, site in enumerate(document.get("atom_sites", [])):
        marker = f"\0DIOPTAS_ATOM_SITE_{index:06d}\0"
        encoded_marker = json.dumps(marker)
        replacements[encoded_marker] = json.dumps(
            site, ensure_ascii=False, separators=(", ", ": ")
        )
        compact_sites.append(marker)
    document["atom_sites"] = compact_sites

    rendered = json.dumps(document, indent=1, ensure_ascii=False)
    for marker, peak_row in replacements.items():
        if rendered.count(marker) != 1:
            raise ValueError("Peak-row serialization marker is not unique")
        rendered = rendered.replace(marker, peak_row)
    return rendered + "\n"


def load_material_file(path: str) -> Material:
    """Read a ``.eosmat`` (JSON) material file."""
    with open(path, "r", encoding="utf-8") as fh:
        return Material.from_dict(json.load(fh))
