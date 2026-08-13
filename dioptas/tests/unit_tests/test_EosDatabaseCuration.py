# -*- coding: utf-8 -*-
"""Regression checks for the publication audit of imported JCPDS EoS data."""
import json
from pathlib import Path

import pytest

from ...model import eos


DATABASE = Path(eos.eos_database_path)


def _document(filename):
    with (DATABASE / filename).open(encoding="utf-8") as stream:
        return json.load(stream)


@pytest.mark.parametrize(
    "filename,index,eos_type,v0,k0,k0_prime",
    [
        ("aragonite.json", 0, "BM3", 227.14, 65.4, 2.7),
        ("boron_nitride.json", 0, "Vinet", 47.2496, 395.0, 3.62),
        ("diamond.json", 0, "Vinet", 45.3864, 443.0, 3.97),
        ("e_feooh.json", 0, "BM2", 66.3, 158.0, None),
        ("feh2.json", 0, "Vinet", 67.8895, 127.2, 5.0),
        ("feh3.json", 0, "Vinet", 18.5499, 190.1, 5.0),
        ("kcl.json", 1, "BM3", 53.53, 23.7, 4.4),
        ("magnesite.json", 0, "BM3", 279.28, 117.0, 2.3),
        ("mgo.json", 1, "BM3", 74.71, 160.2, 3.99),
        ("cobalt_hcp.json", 0, "BM3", 22.4685, 199.0, 3.6),
        ("nacl_b2.json", 0, "BM3", 41.67, 36.2, 4.0),
        ("tungsten.json", 1, "Vinet", 31.724, 295.2, 4.32),
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


def test_phase_only_materials_have_explicit_card_references():
    expected = {
        "alumina.json": "JCPDS 0-173",
        "b4c.json": "JCPDS/PDF 6-0555",
        "copper.json": "JCPDS 04-0836",
        "fe.json": "JCPDS 6-0696",
        "fe2o3.json": "JCPDS 33-664",
        "fe_fcc.json": "JCPDS 4-0829",
        "graphite.json": "JCPDS 41-1487",
        "rhenium.json": "JCPDS 5-0702",
    }
    actual = {}
    for path in DATABASE.glob("*.json"):
        document = _document(path.name)
        if not document["eos_records"]:
            actual[path.name] = document["notes"]

    assert set(actual) == set(expected)
    for filename, card in expected.items():
        assert card in actual[filename]
        assert "eos" not in actual[filename].lower()


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

    assert len(references) == 76
    assert {reference for reference in references if "doi:" not in reference} == (
        no_registered_doi
    )
    assert all("(" in reference and ")" in reference for reference in references)


def test_unpublished_alternatives_were_removed():
    assert len(_document("gold.json")["eos_records"]) == 2
    assert _document("gold.json")["eos_records"][1]["eos"]["type"] == "Vinet"
    assert len(_document("iron.json")["eos_records"]) == 1
