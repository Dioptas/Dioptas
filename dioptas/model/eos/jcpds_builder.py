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

from .material import Material, record_eos_type, record_label


def build_jcpds(material: Material, record_index: int = 0):
    """
    Build a Dioptas ``jcpds`` object from a Material, applying the EoS
    record at *record_index* (when the material has any). The phase is
    named by its chemistry alone ("Au") — the active literature
    reference is shown in the phase table's Ref column and kept in the
    comments, not baked into the name.

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
        record_index = max(0, min(record_index, len(records) - 1))
        record = records[record_index]

    obj._name = chemistry
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
    if material_has_complete_structure(material):
        peak_rows = calculate_material_reflections(material)
    else:
        peak_rows = material.peaks
    for h, k, l, d0, intensity in peak_rows:
        obj.reflections.append(jcpds_reflection(
            h=h, k=k, l=l, intensity=intensity, d=d0))

    # Reference switcher state
    obj.params["chemistry"] = chemistry
    obj.params["eos_records"] = records
    obj.params["eos_current_index"] = record_index if record else 0

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
    reference = record.get("reference") or record_label(record)
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
    if thermal_type in ("MieGruneisenDebye", "MieGruneisenEinstein"):
        # full thermal engine: parameters go to the thermal state fields,
        # the legacy coefficients stay zero
        phase.params["thermal_type"] = thermal_type
        phase.params["theta_t0"] = thermal_parameters.get("theta0") or 0.0
        phase.params["gamma_t0"] = thermal_parameters.get("gamma0") or 0.0
        phase.params["q_t0"] = thermal_parameters.get("q", 1.0)
        phase.params["t_ref"] = thermal_parameters.get("Tr") or 298.15
        phase.params["alpha_t0"] = 0.0
        phase.params["dk0dt"] = 0.0
    else:
        # 'AlphaKT' (the classic correction) or no thermal data at all
        phase.params["thermal_type"] = ""
        if thermal_type != "AlphaKT":
            thermal_parameters = {}
        phase.params["alpha_t0"] = thermal_parameters.get("alpha0") or 0.0
        phase.params["dk0dt"] = thermal_parameters.get("dK_dT") or 0.0

    phase.params["eos_type"] = eos.get("type") or "BM3"
    if parameters.get("V0"):
        phase.params["v0"] = parameters["V0"]
        phase.params["v"] = parameters["V0"]


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
