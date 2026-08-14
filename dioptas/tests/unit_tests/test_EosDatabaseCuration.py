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


def test_every_thermal_parameter_has_explicit_uncertainty_metadata():
    for path in DATABASE.glob("*.json"):
        for record in _document(path.name)["eos_records"]:
            thermal = record.get("thermal")
            if not thermal or "parameter_errors" not in thermal:
                continue
            parameters = thermal["parameters"]
            errors = thermal["parameter_errors"]
            fixed = thermal.get("fixed_parameters", [])
            assert set(errors) == set(parameters), path.name
            assert set(fixed) <= set(parameters), path.name
            for name, error in errors.items():
                assert error is None or error > 0, (path.name, name)


def test_materials_have_at_most_one_boolean_default_record():
    for path in DATABASE.glob("*.json"):
        defaults = []
        for record in _document(path.name)["eos_records"]:
            if "default" in record:
                assert isinstance(record["default"], bool), path.name
                if record["default"]:
                    defaults.append(record)
        assert len(defaults) <= 1, path.name


def test_bundled_references_store_complete_author_lists():
    for path in DATABASE.glob("*.json"):
        for record in _document(path.name)["eos_records"]:
            reference = record["reference"]
            assert reference.get("authors"), (path.name, record["label"])
            assert not reference.get("authors_truncated"), (
                path.name, record["label"]
            )


@pytest.mark.parametrize(
    "filename,label_fragment",
    [
        ("gold.json", "Fei et al PNAS, 2007 [Vinet]"),
        ("mgo.json", "Speziale et al. (2001)"),
        ("neon_fcc.json", "Fei et al PNAS 2007 [Vinet]"),
        ("tungsten.json", "Dewaele et al. (2004)"),
    ],
)
def test_curated_default_eos_records(filename, label_fragment):
    records = _document(filename)["eos_records"]
    defaults = [record for record in records if record.get("default")]

    assert len(defaults) == 1
    assert label_fragment in defaults[0]["label"]


def test_experimental_ranges_are_ordered_finite_intervals():
    range_fields = {
        "experimental_pressure_range_gpa": 0.0,
        "experimental_temperature_range_k": 0.0,
    }
    for path in DATABASE.glob("*.json"):
        for record in _document(path.name)["eos_records"]:
            for field, lower_bound in range_fields.items():
                if field not in record:
                    continue
                values = record[field]
                assert isinstance(values, list) and len(values) == 2, (
                    path.name, field
                )
                assert all(isinstance(value, (int, float))
                           and math.isfinite(value) for value in values), (
                    path.name, field
                )
                assert lower_bound <= values[0] <= values[1], (
                    path.name, field
                )


def test_every_eos_has_a_numeric_pressure_domain_or_explicit_status():
    allowed_statuses = {
        "theoretical",
        "reference_parameterization",
        "reported_qualitatively",
    }
    for path in DATABASE.glob("*.json"):
        for record in _document(path.name)["eos_records"]:
            has_range = "experimental_pressure_range_gpa" in record
            has_status = "pressure_range_status" in record
            assert has_range != has_status, (path.name, record["label"])
            if has_status:
                assert record["pressure_range_status"] in allowed_statuses, (
                    path.name, record["label"]
                )


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
        ("ca_perovskite.json", 0,
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
        ("ice_vi.json", 0, "BM2", 235.2983858185, 14.05, None),
        ("ice_vii.json", 0, "BM2", 41.480265898, 20.15, None),
        ("ice_vii.json", 1, "BM3", 41.1813688659, 21.1, 4.4),
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
        ("bridgmanite.json", 0, "BM3", 162.373, 256.7, 4.09),
        ("mgsio3_post_perovskite.json", 0, "BM3", 162.2, 225.0, 4.21),
        ("alpha_quartz.json", 0, "BM3", 112.981, 37.12, 5.99),
        ("calcite.json", 0, "BM2", 367.789, 73.46, None),
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
    assert record["reference"].get("doi")


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
        if record["reference"].get("doi") == "10.1103/fxgq-96sg"
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
            assert document["peaks"], path.name
            continue

        structured.append(path.name)
        assert document["peaks"] == [], path.name
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

    assert len(structured) == 107


@pytest.mark.parametrize(
    "filename,index,eos_type,parameters,errors,fixed",
    [
        ("zinc_oxide_wurtzite.json", 0, "BM2",
         {"V0": 47.7, "K0": 139.0},
         {"V0": 0.12, "K0": 8.0}, []),
        ("zinc_oxide_rocksalt.json", 0, "BM2",
         {"V0": 78.44, "K0": 172.0},
         {"V0": 0.4, "K0": 21.0}, []),
        ("zirconium_alpha.json", 0, "Vinet",
         {"V0": 46.63, "K0": 113.7, "K0_prime": 1.0},
         {"V0": None, "K0": 0.7, "K0_prime": None},
         ["V0", "K0_prime"]),
        ("zirconium_omega.json", 0, "Vinet",
         {"V0": 69.15, "K0": 98.0, "K0_prime": 3.6},
         {"V0": 0.09, "K0": 2.0, "K0_prime": 0.2}, ["V0"]),
        ("zirconium_beta.json", 0, "Vinet",
         {"V0": 45.2, "K0": 83.0, "K0_prime": 3.91},
         {"V0": None, "K0": 0.5, "K0_prime": 0.02}, ["V0"]),
        ("nickel_oxide.json", 0, "BM3",
         {"V0": 54.6581199247, "K0": 191.0, "K0_prime": 3.9},
         {"V0": 0.0392564903, "K0": None, "K0_prime": None}, ["V0"]),
        ("cementite.json", 0, "BM3",
         {"V0": 155.26, "K0": 175.4, "K0_prime": 5.1},
         {"V0": 0.14, "K0": 3.5, "K0_prime": 0.3}, []),
        ("iron_carbide_fe7c3.json", 0, "BM3",
         {"V0": 748.0, "K0": 168.0, "K0_prime": 6.1},
         {"V0": 1.0, "K0": 4.0, "K0_prime": 0.1}, []),
        ("calcium_carbonate_post_aragonite.json", 0, "BM3",
         {"V0": 97.76, "K0": 146.7, "K0_prime": 3.4},
         {"V0": None, "K0": 1.9, "K0_prime": 0.1}, ["V0"]),
        ("calcium_carbonate_post_aragonite.json", 1, "BM3",
         {"V0": 97.76, "K0": 151.0, "K0_prime": 3.2},
         {"V0": None, "K0": 4.0, "K0_prime": 0.2}, ["V0"]),
    ],
)
def test_phase_expansion_records_match_primary_sources(
        filename, index, eos_type, parameters, errors, fixed):
    record = _document(filename)["eos_records"][index]
    assert record["eos"]["type"] == eos_type
    assert record["eos"]["parameters"] == pytest.approx(parameters)
    assert record["parameter_errors"] == errors
    assert record["fixed_parameters"] == fixed
    assert record["reference"].get("doi")


def test_post_aragonite_thermal_parameters_match_primary_source():
    thermal = _document(
        "calcium_carbonate_post_aragonite.json"
    )["eos_records"][1]["thermal"]
    assert thermal["type"] == "MieGruneisenDebye"
    assert thermal["parameters"] == pytest.approx({
        "Tr": 300.0,
        "theta0": 631.0,
        "gamma0": 1.6,
        "q": 1.3,
        "n": 5,
    })
    assert thermal["parameter_errors"] == {
        "Tr": None,
        "theta0": None,
        "gamma0": 0.5,
        "q": 0.9,
        "n": None,
    }
    assert thermal["fixed_parameters"] == ["Tr", "theta0", "n"]


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
        ("bridgmanite.json", "BM3", 162.373, 256.7, 4.09),
        ("mgsio3_post_perovskite.json", "BM3", 162.2, 225.0, 4.21),
        ("alpha_quartz.json", "BM3", 112.981, 37.12, 5.99),
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
    assert record["reference"].get("doi")


@pytest.mark.parametrize(
    "filename,eos_type,parameters,errors,fixed,pressure_range",
    [
        ("lif_b1.json", "Vinet",
         {"V0": 65.484, "K0": 64.6, "K0_prime": 4.62},
         {"V0": 0.12, "K0": 1.4, "K0_prime": 0.6},
         [], [0.0, 109.0]),
        ("kbr_b1.json", "Vinet",
         {"V0": 287.56, "K0": 14.2, "K0_prime": 5.5},
         {"V0": None, "K0": None, "K0_prime": None},
         ["K0_prime"], [0.0, 2.3]),
        ("kbr_b2.json", "Vinet",
         {"V0": 63.4, "K0": 14.9, "K0_prime": 5.81},
         {"V0": None, "K0": None, "K0_prime": None},
         ["V0"], [2.3, 165.0]),
        ("boron_phosphide.json", "Vinet",
         {"V0": 93.2061, "K0": 179.0, "K0_prime": 3.3},
         {"V0": None, "K0": 1.0, "K0_prime": 0.1},
         ["V0"], [0.0, 55.0]),
        ("cerium_dioxide.json", "BM3",
         {"V0": 158.428242, "K0": 220.0, "K0_prime": 4.4},
         {"V0": 0.087837, "K0": 9.0, "K0_prime": 0.4},
         ["V0"], [0.0, 20.0]),
        ("praseodymium_dioxide.json", "BM3",
         {"V0": 156.939703, "K0": 187.0, "K0_prime": 4.8},
         {"V0": 0.174571, "K0": 8.0, "K0_prime": 0.5},
         ["V0"], [0.0, 35.0]),
        ("lead_fcc.json", "BM4",
         {"V0": 121.418, "K0": 41.73, "K0_prime": 5.39,
          "K0_double_prime": -0.33},
         {"V0": 0.005, "K0": 0.01, "K0_prime": 0.25,
          "K0_double_prime": 0.02},
         ["V0", "K0"], [0.0, 13.0]),
        ("magnesium_hcp.json", "Vinet",
         {"V0": 46.299, "K0": 30.9, "K0_prime": 4.56},
         {"V0": 0.0016, "K0": 0.4, "K0_prime": 0.06},
         ["V0"], [0.0, 61.0]),
        ("magnesium_bcc.json", "Vinet",
         {"V0": 46.2788, "K0": 26.3, "K0_prime": 5.1},
         {"V0": 0.0016, "K0": 0.6, "K0_prime": 0.06},
         ["V0"], [46.0, 211.0]),
        ("titanium_alpha.json", "Vinet",
         {"V0": 35.304, "K0": 110.4, "K0_prime": 4.0},
         {"V0": 0.04, "K0": 2.7, "K0_prime": None},
         ["K0_prime"], [0.0, 10.0]),
        ("titanium_omega.json", "Vinet",
         {"V0": 52.38, "K0": 106.9, "K0_prime": 3.68},
         {"V0": 0.3, "K0": 6.0, "K0_prime": 0.2},
         [], [0.0, 121.0]),
        ("akimotoite.json", "BM3",
         {"V0": 262.43, "K0": 205.0, "K0_prime": 4.9},
         {"V0": 0.02, "K0": 1.0, "K0_prime": 0.2},
         [], [0.0, 24.86]),
        ("orthoenstatite.json", "BM3",
         {"V0": 832.5, "K0": 105.8, "K0_prime": 8.5},
         {"V0": 0.2, "K0": 0.5, "K0_prime": 0.3},
         [], [0.0, 8.5]),
        ("silica_cacl2.json", "BM2",
         {"V0": 48.1, "K0": 245.0},
         {"V0": 0.2, "K0": 7.0}, [], [55.0, 147.0]),
        ("seifertite.json", "BM2",
         {"V0": 92.3, "K0": 290.0},
         {"V0": 0.5, "K0": 10.0}, [], [55.0, 147.0]),
        ("pyrope.json", "BM3",
         {"V0": 1506.15, "K0": 163.7, "K0_prime": 6.4},
         {"V0": 0.16, "K0": 1.7, "K0_prime": 0.4},
         [], [0.0, 8.0]),
        ("almandine.json", "BM3",
         {"V0": 1533.52, "K0": 172.6, "K0_prime": 5.8},
         {"V0": 0.1, "K0": 1.5, "K0_prime": 0.5},
         [], [0.0, 8.0]),
        ("fayalite.json", "BM3",
         {"V0": 307.84, "K0": 130.4, "K0_prime": 5.3},
         {"V0": 0.05, "K0": 1.4, "K0_prime": None},
         ["K0_prime"], [0.0, 5.0]),
        ("osmium.json", "BM3",
         {"V0": 27.9766135265, "K0": 395.0, "K0_prime": 4.5},
         {"V0": 0.0188, "K0": 15.0, "K0_prime": 0.5},
         [], [0.0, 58.2]),
        ("manganese_alpha.json", "BM3",
         {"V0": 707.9435488281, "K0": 204.0, "K0_prime": 3.7},
         {"V0": None, "K0": 3.0, "K0_prime": 0.4},
         ["V0"], [14.0, 220.0]),
        ("kcl_b1.json", "Vinet",
         {"V0": 249.44, "K0": 17.1, "K0_prime": 5.5},
         {"V0": None, "K0": None, "K0_prime": None},
         ["K0_prime"], [0.0, 2.6]),
    ],
)
def test_new_phase_eos_records_match_primary_sources(
        filename, eos_type, parameters, errors, fixed, pressure_range):
    record = _document(filename)["eos_records"][0]
    assert record["eos"]["type"] == eos_type
    assert record["eos"]["parameters"] == pytest.approx(parameters)
    assert record["parameter_errors"] == errors
    assert record["fixed_parameters"] == fixed
    assert record["experimental_pressure_range_gpa"] == pressure_range


def test_sokolova_workbook_parameters_match_all_eleven_supplements():
    expected = {
        "silver.json": (68.0820933882075, 100.0, 6.15,
                        [115.0, 1.5, 199.0, 1.5, 0.178, 2.21,
                         0.0, 0.0, 0.19, 22.1]),
        "aluminum.json": (66.28871141603032, 72.8, 4.51,
                          [381.0, 1.5, 202.0, 1.5, -0.242, -0.958,
                           0.0, 0.0, 0.33, 64.1]),
        "gold.json": (67.84961794736972, 167.0, 5.9,
                      [179.5, 1.5, 83.0, 1.5, 0.134, 0.087,
                       0.0, 0.0, 0.0, 0.0]),
        "diamond.json": (45.35396586081546, 441.5, 3.9,
                         [684.0, 0.564, 1561.0, 2.436, -0.506, 1.085,
                          0.0, 0.0, 0.0, 0.0]),
        "copper.json": (47.239009578237244, 133.5, 5.32,
                        [296.0, 1.5, 169.0, 1.5, -0.07, 1.401,
                         0.0, 0.0, 2.18, 27.7]),
        "mgo.json": (74.71096452981054, 160.3, 4.1,
                     [748.0, 3.0, 401.0, 3.0, -0.235, 0.301,
                      -17.4, 4.95, 0.0, 0.0]),
        "molybdenum.json": (31.115177217273953, 260.0, 4.2,
                            [353.0, 1.5, 222.0, 1.5, -0.802, -0.791,
                             0.0, 0.0, 2.66, 143.2]),
        "niobium.json": (35.960629619878574, 170.5, 3.65,
                         [134.0, 1.5, 302.0, 1.5, -0.326, -0.763,
                          0.0, 0.0, 0.9, 115.9]),
        "platinum.json": (60.383835218750676, 275.0, 5.35,
                          [177.0, 1.5, 143.0, 1.5, 0.167, -0.343,
                           0.0, 0.0, 0.06, 80.6]),
        "tantalum.json": (36.07022518484496, 191.0, 3.83,
                          [254.0, 1.5, 101.0, 1.5, -0.101, -0.148,
                           0.0, 0.0, 0.12, 82.3]),
        "tungsten.json": (31.72293444117844, 308.0, 4.12,
                          [172.0, 1.5, 309.0, 1.5, -0.686, -0.591,
                           0.0, 0.0, 2.77, 100.1]),
    }
    keys = ["QE1o", "mE1", "QE2o", "mE2", "delta", "t",
            "a_0", "m", "g", "e_0"]
    for filename, (v0, k0, k0p, values) in expected.items():
        record = next(
            record for record in _document(filename)["eos_records"]
            if (record.get("thermal") or {}).get("type")
            == "Sokolova2016")
        eos_parameters = record["eos"]["parameters"]
        assert record["eos"]["type"] == "Holzapfel"
        assert eos_parameters["V0"] == pytest.approx(v0)
        assert eos_parameters["K0"] == pytest.approx(k0)
        assert eos_parameters["K0_prime"] == pytest.approx(k0p)
        if filename == "mgo.json":
            assert eos_parameters["Z"] == pytest.approx(10.34)
        else:
            assert "Z" not in eos_parameters
        thermal = record["thermal"]["parameters"]
        assert thermal["Tr"] == pytest.approx(298.15)
        assert [thermal[key] for key in keys] == pytest.approx(values)


@pytest.mark.parametrize(
    "filename,temperature,workbook_volume,volume_400gpa_3000k",
    [
        ("silver.json", 1200.0, 72.5307308396824, 36.236626468077255),
        ("aluminum.json", 950.0, 70.35017683917293, 28.239709211578838),
        ("gold.json", 1500.0, 72.46078586859234, 40.255306257699594),
        ("diamond.json", 4000.0, 48.089556592259044, 30.21996428002116),
        ("copper.json", 1300.0, 50.292007869393814, 25.76584394854623),
        ("mgo.json", 3100.0, 86.3129480553911, 39.08137549392482),
        ("molybdenum.json", 2800.0, 33.209220611207876,
         18.59812864118969),
        ("niobium.json", 2700.0, 38.48428770243464, 18.37933155370624),
        ("platinum.json", 2100.0, 64.31270868516619, 38.927909880502085),
        ("tantalum.json", 3300.0, 38.858290868856386, 19.2300741100816),
        ("tungsten.json", 3500.0, 33.912725752180556,
         19.662110185919055),
    ],
)
def test_sokolova_engine_matches_excel_and_vba_at_high_temperature(
        filename, temperature, workbook_volume, volume_400gpa_3000k):
    material = eos.Material.from_dict(_document(filename))
    index = next(
        i for i, record in enumerate(material.eos_records)
        if (record.get("thermal") or {}).get("type") == "Sokolova2016")
    phase = eos.build_jcpds(material, record_index=index)

    # Highest cached zero-pressure/high-temperature row in each original
    # workbook (the available upper temperature differs by material).
    phase.compute_volume(pressure=0.0001, temperature=temperature)
    assert phase.params["v"] == pytest.approx(workbook_volume, abs=2e-4)

    # Independently generated from a literal port of the workbook's xAP2
    # VBA function at the paper's 4 Mbar / 3000 K design limit.
    phase.compute_volume(pressure=400.0, temperature=3000.0)
    assert phase.params["v"] == pytest.approx(
        volume_400gpa_3000k, abs=2e-4)


def test_fortes_lead_record_is_an_explicit_static_pvt_slice():
    record = _document("lead_fcc.json")["eos_records"][0]
    assert record["temperature_ref"] == pytest.approx(300.0)
    assert record["experimental_temperature_range_k"] == [295.0, 788.0]
    assert "temperature-dependent" in record["notes"]
    assert "RAL-TR-2019-002.pdf" in record["notes"]


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
        ("calcite.json", 367.789, 73.46),
    ],
)
def test_publication_second_order_fits_do_not_store_fitted_k0_prime(
        filename, v0, k0):
    record = next(
        record for record in _document(filename)["eos_records"]
        if record["eos"]["type"] == "BM2"
    )
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
        ("bridgmanite.json",
         {"V0": None, "K0": 1.5, "K0_prime": 0.06}, ["V0"]),
        ("mgsio3_post_perovskite.json",
         {"V0": None, "K0": 2.0, "K0_prime": 0.07}, ["V0"]),
    ],
)
def test_mantle_phase_eos_uncertainties_and_constraints(
        filename, errors, fixed):
    record = _document(filename)["eos_records"][0]
    assert record["parameter_errors"] == errors
    assert record["fixed_parameters"] == fixed


def test_tange_bridgmanite_mantle_range_alternative_matches_publication():
    records = _document("bridgmanite.json")["eos_records"]
    assert records[1]["eos"] == {
        "type": "Vinet",
        "parameters": {
            "V0": pytest.approx(162.373),
            "K0": pytest.approx(258.4),
            "K0_prime": pytest.approx(4.10),
        },
    }
    assert records[1]["parameter_errors"] == {
        "V0": None,
        "K0": 1.7,
        "K0_prime": 0.07,
    }
    assert records[1]["fixed_parameters"] == ["V0"]


@pytest.mark.parametrize(
    "index,theta0,gamma0,q",
    [
        (0, 950.0, 1.54, 1.5),
        (1, 940.0, 1.55, 1.1),
    ],
)
def test_tange_bridgmanite_thermal_parameters_match_publication(
        index, theta0, gamma0, q):
    thermal = _document("bridgmanite.json")["eos_records"][index]["thermal"]
    assert thermal == {
        "type": "MieGruneisenDebye",
        "parameters": {
            "Tr": pytest.approx(300.0),
            "theta0": pytest.approx(theta0),
            "gamma0": pytest.approx(gamma0),
            "q": pytest.approx(q),
            "n": 5,
        },
    }


def test_sakai_post_perovskite_multimegabar_fit_matches_publication():
    record = _document("mgsio3_post_perovskite.json")["eos_records"][1]
    assert record["eos"] == {
        "type": "BM3",
        "parameters": {
            "V0": pytest.approx(158.0),
            "K0": pytest.approx(292.0),
            "K0_prime": pytest.approx(3.74),
        },
    }
    assert record["parameter_errors"] == {
        "V0": 1.5,
        "K0": 22.0,
        "K0_prime": 0.13,
    }
    assert record["fixed_parameters"] == []


@pytest.mark.parametrize(
    "filename,index,pressure_range,temperature_range",
    [
        ("bridgmanite.json", 0, [28.0, 108.0], [300.0, 2430.0]),
        ("bridgmanite.json", 1, [28.0, 108.0], [300.0, 2430.0]),
        ("bridgmanite.json", 2, [0.0, 10.0], [300.0, 300.0]),
        ("mgsio3_post_perovskite.json", 0, [111.0, 245.0], None),
        ("mgsio3_post_perovskite.json", 1, [100.0, 265.0], None),
        ("alpha_quartz.json", 0, [0.0, 8.9], [298.0, 298.0]),
        ("calcite.json", 0, [0.0, 1.435], [298.0, 298.0]),
    ],
)
def test_curated_eos_records_report_experimental_domains(
        filename, index, pressure_range, temperature_range):
    record = _document(filename)["eos_records"][index]
    assert record["experimental_pressure_range_gpa"] == pressure_range
    if temperature_range is None:
        assert "experimental_temperature_range_k" not in record
    else:
        assert record["experimental_temperature_range_k"] == temperature_range


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
            reference = eos.reference_text(record["reference"]).lower()
            assert not any(marker in reference for marker in rejected_markers)


def test_retained_references_have_normalized_publication_metadata():
    no_registered_doi = {
        "Levien and Prewitt, American Mineralogist 66, 324-333 (1981)",
        "Hazen and Finger, American Mineralogist 64, 196-201 (1979)",
        "Fortes, STFC Rutherford Appleton Laboratory Technical Report "
        "RAL-TR-2019-002 (2019)",
    }
    references = []
    for path in DATABASE.glob("*.json"):
        references.extend(
            eos.reference_text(record["reference"])
            for record in _document(path.name)["eos_records"]
        )

    assert len(references) == 147
    assert {reference for reference in references if "doi:" not in reference} == (
        no_registered_doi
    )
    assert all("(" in reference and ")" in reference for reference in references)


def test_references_use_structured_format_2_metadata():
    for path in DATABASE.glob("*.json"):
        document = _document(path.name)
        assert document["format_version"] == 2
        for record in document["eos_records"]:
            reference = record["reference"]
            assert isinstance(reference, dict), path.name
            assert reference["authors"], path.name
            assert isinstance(reference["year"], int), path.name
            assert reference["source"], path.name


def test_unpublished_alternatives_were_removed():
    assert len(_document("gold.json")["eos_records"]) == 4
    assert _document("gold.json")["eos_records"][1]["eos"]["type"] == "Vinet"
    assert len(_document("iron.json")["eos_records"]) == 2
