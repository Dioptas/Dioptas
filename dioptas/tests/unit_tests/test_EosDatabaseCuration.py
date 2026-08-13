# -*- coding: utf-8 -*-
"""Regression checks for the publication audit of imported JCPDS EoS data."""
from collections import defaultdict
import json
import math
from pathlib import Path
import re

import pytest

from ...model import eos


DATABASE = Path(eos.eos_database_path)


def _document(filename):
    with (DATABASE / filename).open(encoding="utf-8") as stream:
        return json.load(stream)


def test_every_eos_parameter_has_explicit_uncertainty_metadata():
    for path in DATABASE.glob("*.json"):
        for record in _document(path.name)["eos_records"]:
            parameters = record["eos"]["parameters"]
            errors = record["parameter_errors"]
            fixed = record["fixed_parameters"]
            assert set(errors) == set(parameters), path.name
            assert set(fixed) <= set(parameters), path.name
            assert len(fixed) == len(set(fixed)), path.name
            for name, error in errors.items():
                assert error is None or error > 0, (path.name, name)


def test_records_without_any_parameter_error_explain_why():
    explanation_markers = {
        "uncertaint", "standard error", "no error", "non-meaningful",
    }
    for path in DATABASE.glob("*.json"):
        for record in _document(path.name)["eos_records"]:
            if all(error is None
                   for error in record["parameter_errors"].values()):
                notes = record.get("notes", "").lower()
                assert any(marker in notes for marker in explanation_markers), (
                    path.name, record["label"]
                )


@pytest.mark.parametrize(
    "filename,index,errors,fixed",
    [
        ("boron_nitride.json", 0,
         {"V0": 0.0048, "K0": 2.0, "K0_prime": 0.05}, ["V0"]),
        ("copper.json", 0,
         {"V0": None, "K0": 1.4, "K0_prime": 0.06}, ["V0"]),
        ("diamond.json", 1,
         {"V0": 0.0128, "K0": None, "K0_prime": 0.15}, ["K0"]),
        ("mgo.json", 1,
         {"V0": 0.01, "K0": None, "K0_prime": 0.01}, ["K0"]),
        ("ca_perovskite_perovskite_pv.json", 0,
         {"V0": 0.05, "K0": 4.0, "K0_prime": 0.2}, ["V0"]),
        ("cao_b2.json", 0,
         {"V0": 0.3321, "K0": 20.0, "K0_prime": 0.5}, []),
        ("e_feooh.json", 0,
         {"V0": 0.5, "K0": 5.0}, []),
        ("feh2.json", 0,
         {"V0": 0.7174, "K0": 8.1, "K0_prime": None},
         ["K0_prime"]),
        ("goethite.json", 0,
         {"V0": 0.02, "K0": 3.7, "K0_prime": 0.4}, []),
        ("magnesite.json", 0,
         {"V0": 0.03, "K0": 3.0, "K0_prime": 0.7}, []),
        ("naalsio4_calcium_ferrite.json", 0,
         {"V0": 0.1328, "K0": 1.0, "K0_prime": 0.1}, []),
        ("sno2_cubic_27gpa.json", 0,
         {"V0": 3.0, "K0": 28.0, "K0_prime": 2.2}, []),
        ("rhenium.json", 0,
         {"V0": 0.0332, "K0": 8.0, "K0_prime": 0.17}, []),
        ("silicon_carbide_b1.json", 0,
         {"V0": 0.1, "K0": 3.0, "K0_prime": 0.43}, []),
    ],
)
def test_publication_verified_parameter_errors(filename, index, errors, fixed):
    record = _document(filename)["eos_records"][index]
    assert record["parameter_errors"] == errors
    assert record["fixed_parameters"] == fixed


@pytest.mark.parametrize(
    "filename,index,eos_type,v0,k0,k0_prime",
    [
        ("aragonite.json", 0, "BM3", 227.14, 65.4, 2.7),
        ("boron_nitride.json", 0, "Vinet", 47.2496, 395.0, 3.62),
        ("diamond.json", 0, "Vinet", 45.3864, 443.0, 3.97),
        ("diamond.json", 1, "Vinet", 45.3544, 444.5, 4.18),
        ("e_feooh.json", 0, "BM2", 66.3, 158.0, None),
        ("feh2.json", 0, "Vinet", 67.8895, 127.2, 5.0),
        ("feh3.json", 0, "Vinet", 18.5499, 190.1, 5.0),
        ("kcl.json", 1, "BM3", 53.53, 23.7, 4.4),
        ("magnesite.json", 0, "BM3", 279.28, 117.0, 2.3),
        ("mgo.json", 1, "BM3", 74.71, 160.2, 3.99),
        ("graphite.json", 0, "Murnaghan", 35.12, 33.8, 8.9),
        ("rhenium.json", 0, "Vinet", 29.4666, 352.6, 4.56),
        ("cobalt_hcp.json", 0, "BM3", 22.4685, 199.0, 3.6),
        ("nacl_b2.json", 0, "BM2", 41.67, 36.2, None),
        ("iceviii.json", 0, "BM3", 165.39, 20.4, 4.7),
        ("geo2_rutile.json", 0, "BM3", 55.3268, 258.0, 7.0),
        ("naalsi2o6.json", 0, "BM3", 401.19, 125.0, 5.0),
        ("perovskite_orthorhombic.json", 0, "BM3", 162.77, 266.0, 3.9),
        ("sio2_stv_andr.json", 0, "BM3", 46.5025, 309.9, 4.59),
        ("tungsten.json", 1, "Vinet", 31.724, 295.2, 4.32),
        ("copper.json", 0, "Vinet", 47.24, 132.4, 5.32),
        ("b4c.json", 0, "BM3", 328.5, 221.0, 3.3),
        ("alumina.json", 0, "Vinet", 255.45, 254.1, 4.0),
        ("fe2o3.json", 0, "BM2", 301.88, 207.0, None),
        ("silicon_v.json", 0, "Vinet", 15.3, 95.0, 4.6),
        ("silicon_vii.json", 0, "Vinet", 28.6, 96.9, 4.01),
        ("silicon_x.json", 0, "Vinet", 53.2, 136.0, 4.2),
        ("silicon_carbide_b3.json", 0, "BM3", 82.8, 224.0, 4.1),
        ("silicon_carbide_b1.json", 0, "BM3", 66.3, 323.0, 3.1),
        ("boron_nitride_hexagonal.json", 0, "BM3", 36.18, 27.4, 11.4),
        ("niobium.json", 0, "BM3", 35.96, 168.0, 3.4),
        ("forsterite.json", 0, "BM3", 290.1, 130.0, 4.12),
        ("wadsleyite.json", 0, "BM3", 538.185, 169.2, 4.1),
        ("ringwoodite.json", 0, "BM3", 526.7, 182.0, 4.2),
    ],
)
def test_publication_corrected_eos_records(
        filename, index, eos_type, v0, k0, k0_prime):
    record = _document(filename)["eos_records"][index]
    parameters = record["eos"]["parameters"]
    assert record["eos"]["type"] == eos_type
    assert parameters["V0"] == pytest.approx(v0)
    assert parameters["K0"] == pytest.approx(k0)
    if k0_prime is None:
        assert "K0_prime" not in parameters
    else:
        assert parameters["K0_prime"] == pytest.approx(k0_prime)
    assert "doi:" in record["reference"].lower()


@pytest.mark.parametrize(
    "filename,v0,k0,k0_prime",
    [
        ("platinum.json", 60.364, 261.2, 5.75),
        ("gold.json", 67.792, 167.5, 5.85),
        ("tantalum.json", 36.14, 195.2, 3.62),
        ("tungsten.json", 31.704, 307.0, 4.02),
        ("molybdenum.json", 31.14, 260.6, 4.06),
        ("mgo.json", 74.636, 161.9, 4.08),
        ("nacl_b1.json", 179.41, 23.5, 5.23),
        ("nacl_b2.json", 41.35, 24.92, 5.63),
        ("fe.json", 23.506, 162.1, 5.4),
        ("iron.json", 22.352, 168.55, 5.53),
    ],
)
def test_shen_smith_2026_vinet_records_match_table_ii(
        filename, v0, k0, k0_prime):
    records = _document(filename)["eos_records"]
    record = next(
        record for record in records
        if "doi:10.1103/fxgq-96sg" in record["reference"]
    )
    assert record["eos"] == {
        "type": "Vinet",
        "parameters": {
            "V0": pytest.approx(v0),
            "K0": pytest.approx(k0),
            "K0_prime": pytest.approx(k0_prime),
        },
    }
    assert record["temperature_ref"] == pytest.approx(300.0)


@pytest.mark.parametrize(
    "filename,space_group,number,sites",
    [
        ("platinum.json", "Fm-3m", 225,
         [("Pt", "4a", 0.0, 0.0, 0.0)]),
        ("gold.json", "Fm-3m", 225,
         [("Au", "4a", 0.0, 0.0, 0.0)]),
        ("copper.json", "Fm-3m", 225,
         [("Cu", "4a", 0.0, 0.0, 0.0)]),
        ("tantalum.json", "Im-3m", 229,
         [("Ta", "2a", 0.0, 0.0, 0.0)]),
        ("tungsten.json", "Im-3m", 229,
         [("W", "2a", 0.0, 0.0, 0.0)]),
        ("molybdenum.json", "Im-3m", 229,
         [("Mo", "2a", 0.0, 0.0, 0.0)]),
        ("mgo.json", "Fm-3m", 225,
         [("Mg", "4a", 0.0, 0.0, 0.0),
          ("O", "4b", 0.5, 0.5, 0.5)]),
        ("nacl_b1.json", "Fm-3m", 225,
         [("Na", "4a", 0.0, 0.0, 0.0),
          ("Cl", "4b", 0.5, 0.5, 0.5)]),
        ("nacl_b2.json", "Pm-3m", 221,
         [("Na", "1a", 0.0, 0.0, 0.0),
          ("Cl", "1b", 0.5, 0.5, 0.5)]),
        ("fe.json", "Im-3m", 229,
         [("Fe", "2a", 0.0, 0.0, 0.0)]),
        ("iron.json", "P63/mmc", 194,
         [("Fe", "2c", 1 / 3, 2 / 3, 0.25)]),
    ],
)
def test_shen_smith_calibrants_store_asymmetric_unit_wyckoff_sites(
        filename, space_group, number, sites):
    document = _document(filename)
    assert document["space_group"] == space_group
    assert document["space_group_number"] == number
    assert len(document["atom_sites"]) == len(sites)
    for site, (element, wyckoff, x, y, z) in zip(
            document["atom_sites"], sites):
        assert site == {
            "element": element,
            "wyckoff": wyckoff,
            "x": pytest.approx(x),
            "y": pytest.approx(y),
            "z": pytest.approx(z),
            "occupancy": pytest.approx(1.0),
        }


def test_all_curated_structures_are_complete_and_stoichiometric():
    structured = []
    for path in DATABASE.glob("*.json"):
        document = _document(path.name)
        sites = document.get("atom_sites") or []
        if not sites:
            assert not document.get("space_group")
            assert document.get("space_group_number") is None
            continue

        structured.append(path.name)
        assert document["space_group"]
        assert 1 <= document["space_group_number"] <= 230
        assert document["formula_units_per_cell"] > 0

        actual = defaultdict(float)
        for site in sites:
            assert set(site) == {
                "element", "wyckoff", "x", "y", "z", "occupancy"
            }
            match = re.fullmatch(r"(\d+)[a-zA-Z]", site["wyckoff"])
            assert match, f"invalid Wyckoff label in {path.name}: {site}"
            assert all(0.0 <= site[axis] < 1.0 for axis in "xyz")
            assert 0.0 < site["occupancy"] <= 1.0
            actual[site["element"]] += (
                int(match.group(1)) * site["occupancy"]
            )

        expected = defaultdict(float)
        tokens = re.findall(r"([A-Z][a-z]?)(\d*)", document["formula"])
        assert tokens
        assert "".join(element + count
                       for element, count in tokens) == document["formula"]
        for element, count in tokens:
            expected[element] += (
                int(count or 1) * document["formula_units_per_cell"]
            )
        assert dict(actual) == pytest.approx(dict(expected)), path.name

    assert len(structured) == 74


@pytest.mark.parametrize(
    "filename,eos_type,v0,k0,k0_prime",
    [
        ("aluminum.json", "Vinet", 66.292, 74.3, 4.47),
        ("silver.json", "Vinet", 68.28, 100.2, 5.70),
        ("nickel.json", "Vinet", 43.816, 177.5, 4.83),
        ("chromium.json", "BM3", 24.08, 185.0, 4.74),
        ("ruthenium.json", "BM3", 27.122, 323.4, 4.15),
        ("rhodium.json", "Vinet", 55.046, 251.0, 5.7),
        ("palladium.json", "BM3", 58.88, 190.0, 5.3),
        ("iridium.json", "BM3", 56.62, 327.0, 5.46),
        ("silicon.json", "Vinet", 160.248, 97.89, 4.24),
        ("forsterite.json", "BM3", 290.1, 130.0, 4.12),
        ("wadsleyite.json", "BM3", 538.185, 169.2, 4.1),
        ("ringwoodite.json", "BM3", 526.7, 182.0, 4.2),
    ],
)
def test_literature_expansion_eos_records(
        filename, eos_type, v0, k0, k0_prime):
    record = _document(filename)["eos_records"][0]
    assert record["eos"] == {
        "type": eos_type,
        "parameters": {
            "V0": pytest.approx(v0),
            "K0": pytest.approx(k0),
            "K0_prime": pytest.approx(k0_prime),
        },
    }
    assert "doi:" in record["reference"].lower()


@pytest.mark.parametrize(
    "filename",
    [
        "aluminum.json", "silver.json", "nickel.json", "chromium.json",
        "ruthenium.json", "rhodium.json", "palladium.json",
        "iridium.json", "silicon.json", "graphite.json", "rhenium.json",
        "copper.json", "b4c.json", "alumina.json", "fe2o3.json",
        "silicon_v.json", "silicon_vii.json", "silicon_x.json",
        "silicon_carbide_b3.json", "silicon_carbide_b1.json",
        "boron_nitride_hexagonal.json", "niobium.json",
        "ringwoodite.json",
    ],
)
def test_literature_expansion_peak_d_spacings(filename):
    document = _document(filename)
    lattice = document["lattice"]
    for h, k, l, stored_d, _intensity in document["peaks"]:
        if document["symmetry"] == "CUBIC":
            calculated_d = lattice["a"] / math.sqrt(h * h + k * k + l * l)
        else:
            calculated_d = 1.0 / math.sqrt(
                4.0 * (h * h + h * k + k * k) / (3.0 * lattice["a"] ** 2)
                + l * l / lattice["c"] ** 2
            )
        assert calculated_d == pytest.approx(stored_d, abs=1e-5)


@pytest.mark.parametrize(
    "filename",
    ["forsterite.json", "wadsleyite.json", "bridgmanite.json"],
)
def test_mantle_phase_orthorhombic_peak_d_spacings(filename):
    document = _document(filename)
    lattice = document["lattice"]
    for h, k, l, stored_d, _intensity in document["peaks"]:
        calculated_d = 1.0 / math.sqrt(
            (h / lattice["a"]) ** 2
            + (k / lattice["b"]) ** 2
            + (l / lattice["c"]) ** 2
        )
        assert calculated_d == pytest.approx(stored_d, abs=1e-5)


@pytest.mark.parametrize("filename", ["e_feooh.json", "fes.json"])
def test_reindexed_orthorhombic_structures_preserve_peak_d_spacings(filename):
    document = _document(filename)
    lattice = document["lattice"]
    for h, k, l, stored_d, _intensity in document["peaks"]:
        calculated_d = 1.0 / math.sqrt(
            (h / lattice["a"]) ** 2
            + (k / lattice["b"]) ** 2
            + (l / lattice["c"]) ** 2
        )
        assert calculated_d == pytest.approx(stored_d, abs=5e-5)


def test_walker_kcl_thermal_parameters_match_publication():
    thermal = _document("kcl.json")["eos_records"][1]["thermal"]
    assert thermal["type"] == "AlphaKT"
    assert thermal["parameters"] == {
        "alpha0": pytest.approx(1.8e-4),
        "dK_dT": pytest.approx(0.0),
    }


def test_martinez_aragonite_thermal_parameters_match_publication():
    record = _document("aragonite.json")["eos_records"][0]
    assert record["temperature_ref"] == pytest.approx(298.0)
    assert record["thermal"]["type"] == "AlphaKT"
    assert record["thermal"]["parameters"] == {
        "alpha0": pytest.approx(6.7e-5),
        "dK_dT": pytest.approx(-0.013),
    }


@pytest.mark.parametrize(
    "filename,v0,k0",
    [
        ("argon_hcp.json", 47.7648, 6.5),
        ("phase_d.json", 84.7321, 134.0),
        ("zircon.json", 260.803, 227.0),
        ("bridgmanite.json", 162.51, 253.0),
    ],
)
def test_publication_second_order_fits_do_not_store_fitted_k0_prime(
        filename, v0, k0):
    record = _document(filename)["eos_records"][0]
    assert record["eos"]["type"] == "BM2"
    assert record["eos"]["parameters"] == {
        "V0": pytest.approx(v0),
        "K0": pytest.approx(k0),
    }


@pytest.mark.parametrize(
    "filename,errors,fixed",
    [
        ("forsterite.json",
         {"V0": 0.1, "K0": 0.9, "K0_prime": 0.07}, ["V0"]),
        ("wadsleyite.json",
         {"V0": None, "K0": None, "K0_prime": 0.1},
         ["V0", "K0"]),
        ("ringwoodite.json",
         {"V0": 0.3, "K0": 3.0, "K0_prime": 0.3}, []),
        ("bridgmanite.json", {"V0": 0.02, "K0": 1.0}, []),
    ],
)
def test_mantle_phase_eos_uncertainties_and_constraints(
        filename, errors, fixed):
    record = _document(filename)["eos_records"][0]
    assert record["parameter_errors"] == errors
    assert record["fixed_parameters"] == fixed


def test_phase_only_materials_have_explicit_card_references():
    expected = {
        "fe_fcc.json": "JCPDS 4-0829",
        "fes_iii.json": "doi:10.1103/PhysRevB.59.9048",
        "nitrogen_epsilon.json": "doi:10.1063/1.450310",
        "o8.json": "doi:10.1103/PhysRevLett.97.085503",
    }
    actual = {}
    for path in DATABASE.glob("*.json"):
        document = _document(path.name)
        if not document["eos_records"]:
            actual[path.name] = document["notes"]

    assert set(actual) == set(expected)
    for filename, card in expected.items():
        assert card in actual[filename]
        if filename != "fe_fcc.json":
            assert "removed" in actual[filename].lower()


def test_b4c_hexagonal_cell_metadata_matches_phase_publication():
    document = _document("b4c.json")
    assert document["symmetry"] == "HEXAGONAL"
    assert document["formula_units_per_cell"] == 9
    assert "doi:10.1021/ja01251a026" in document["notes"]


def test_misidentified_material_files_were_corrected_or_removed():
    assert not (DATABASE / "tibr.json").exists()
    assert not (DATABASE / "molibdenum.json").exists()
    assert not (DATABASE / "molibdenum_2.json").exists()
    assert not (DATABASE / "naalsi2o6_2.json").exists()
    assert not (DATABASE / "casio3_perovskite.json").exists()
    assert not (DATABASE / "perovskite_cubic.json").exists()
    assert not (DATABASE / "ca_perovskite_tetragonal.json").exists()

    unsupported_calcium_silicates = {
        "alpha_ca2sio5.json", "alphah_ca2sio5.json",
        "alphal_ca2sio5.json", "gamma_ca2sio5.json",
        "k2nif4_ca2sio5.json", "larnite.json",
        "casi2o5.json", "casi2o5_2.json",
    }
    assert not any((DATABASE / filename).exists()
                   for filename in unsupported_calcium_silicates)

    assert not (DATABASE / "moc_fm.json").exists()
    assert not (DATABASE / "mo2c_hex_haines.json").exists()

    calcium_ferrite = _document("naalsio4_calcium_ferrite.json")
    assert (
        calcium_ferrite["name"], calcium_ferrite["formula"],
        calcium_ferrite["formula_units_per_cell"],
    ) == ("NaAlSiO4 (calcium-ferrite type)", "NaAlSiO4", 4)


def test_retained_references_do_not_use_non_public_provenance_markers():
    rejected_markers = {
        "dcal", "private communication", "from alex", "from leonid",
        "fitted by shen", "made by shim", "eos from ?", "unknown",
    }
    for path in DATABASE.glob("*.json"):
        for record in _document(path.name)["eos_records"]:
            reference = record["reference"].lower()
            assert not any(marker in reference for marker in rejected_markers)


def test_retained_references_have_normalized_publication_metadata():
    no_registered_doi = {
        "Levien and Prewitt, American Mineralogist 66, 324-333 (1981)",
        "Hazen and Finger, American Mineralogist 64, 196-201 (1979)",
    }
    references = []
    for path in DATABASE.glob("*.json"):
        references.extend(
            record["reference"] for record in _document(path.name)["eos_records"]
        )

    assert len(references) == 97
    assert {reference for reference in references if "doi:" not in reference} == (
        no_registered_doi
    )
    assert all("(" in reference and ")" in reference for reference in references)


def test_unpublished_alternatives_were_removed():
    assert len(_document("gold.json")["eos_records"]) == 3
    assert _document("gold.json")["eos_records"][1]["eos"]["type"] == "Vinet"
    assert len(_document("iron.json")["eos_records"]) == 2
