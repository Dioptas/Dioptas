"""Explicit diffraction approximations, separate from the source EOS catalog."""

from copy import deepcopy
from math import isfinite, radians, tan

from .material import Lattice, Material
from ..util.phasesmith import material_has_diffraction_data


def can_assume_tetragonal_perovskite(material: Material | None) -> bool:
    return bool(
        material is not None
        and material.identifier in {
            "casio3_perovskite_tetragonal", "ca_perovskite_tetragonal"}
        and material.formula == "CaSiO3"
        and material.symmetry == "TETRAGONAL"
        and material.formula_units_per_cell == (
            1 if material.identifier == "casio3_perovskite_tetragonal" else 4)
        and not material.atom_sites and not material.peaks
        and not material_has_diffraction_data(material)
    )


def assume_tetragonal_perovskite(material: Material) -> Material:
    """Return an annotated copy with fixed shape and constructed atomic sites.

    Neither the library document nor its EOS records are changed. Reference
    metrics only seed the shape; the selected EOS supplies the cell volume.
    This approximation does not model pressure-dependent tilts or c/a.
    """
    if not can_assume_tetragonal_perovskite(material):
        raise ValueError("No tetragonal perovskite approximation is available")
    volume = material.eos_records[material.default_eos_index]["eos"]["parameters"]["V0"]
    if not isfinite(volume) or volume <= 0:
        raise ValueError("An assumed structure needs a positive EOS reference volume")
    assumed = deepcopy(material)

    def site(element, x, y, z):
        return {"element": element, "x": x, "y": y, "z": z,
                "occupancy": 1.0}

    original_document = material.to_dict()
    original_structure = {
        key: original_document[key] for key in
        ("lattice", "space_group", "space_group_number", "atom_sites", "peaks")
    }
    if material.formula_units_per_cell == 1:
        ratio = 0.996
        assumed.space_group, assumed.space_group_number = "P4/mmm", 123
        assumed.atom_sites = [
            site("Ca", 0, 0, 0), site("Si", .5, .5, .5),
            site("O", .5, .5, 0), site("O", .5, 0, .5),
        ]
        reference = {
            "doi": "10.1029/2002GL016148", "location": "paragraph 9; Figure 2",
            "finding": "The c axis is approximately 0.4% shorter than a.",
        }
        detail = "P4/mmm, Z=1, c/a=0.996; ideal perovskite sites without octahedral tilt."
        tilt = 0.0
    else:
        # Chen et al. (2018), Table 1, first I4/mcm row (28.824 GPa).
        ratio = 6.9677 / 4.8896
        tilt = 8.0
        x = (1 - tan(radians(tilt))) / 4
        assumed.space_group, assumed.space_group_number = "I4/mcm", 140
        assumed.atom_sites = [
            site("Ca", 0, .5, .25), site("Si", 0, 0, 0),
            site("O", 0, 0, .25), site("O", x, x + .5, 0),
        ]
        reference = {
            "doi": "10.2138/am-2018-6087", "location": "Table 1, first I4/mcm row",
            "pressure_gpa": 28.824, "a_angstrom": 4.8896, "c_angstrom": 6.9677,
            "tilt_deg": tilt,
        }
        detail = (
            "I4/mcm, Z=4; c/a and 8° tilt seeded from Chen (2018), Table 1 at "
            "28.824 GPa; oxygen sites constructed from ideal perovskite geometry."
        )
    a = (volume / ratio) ** (1 / 3)
    assumed.lattice = Lattice(a=a, b=a, c=a * ratio)
    assumed.name += " (assumed structure)"
    note = (
        "Assumed diffraction structure: " + detail + " The EOS sets the volume; "
        "c/a and fractional coordinates are held fixed with pressure and temperature. "
        "Intensities are approximate; this is not a refined structure."
    )
    assumed.notes = (assumed.notes + "\n\n" + note).strip()
    assumed.source["assumed_structure"] = {
        "status": "assumed", "note": note,
        "model": "tetragonal_perovskite", "c_over_a": ratio,
        "tilt_deg": tilt, "normalize_to_eos_v0": True,
        "shape_reference": reference, "original_structure": original_structure,
    }
    return assumed
