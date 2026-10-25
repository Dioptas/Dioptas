# SPDX-License-Identifier: MIT

from copy import deepcopy

import pytest

from ...model import eos


def test_peritheos_record_link_targets_the_selected_catalog_record():
    record = {"identifier": "gold_fei_2007_vinet_2"}
    assert eos.peritheos_record_url("gold", record) == (
        "https://peritheos.readthedocs.io/en/latest/material-summaries/"
        "gold/#record-gold_fei_2007_vinet_2")
    assert not eos.peritheos_record_url("gold", record, origin="custom")
    record["scientific_validation"] = {
        "status": "deferred", "note": "User-owned copy; coefficients changed."}
    assert not eos.peritheos_record_url("gold", record)


@pytest.mark.parametrize("material,record", [
    (None, {"identifier": "gold_fei_2007_vinet_2"}),
    ("", {"identifier": "gold_fei_2007_vinet_2"}),
    ("gold", {}),
    ("gold", {"identifier": "custom_record"}),
    ("palladium", {"identifier": "gold_fei_2007_vinet_2"}),
    ("unknown-material", {"identifier": "custom_record"}),
])
def test_non_catalog_records_have_no_peritheos_link(material, record):
    assert not eos.peritheos_record_url(material, record)


def test_source_verification_and_data_do_not_imply_reproduction():
    record = {"scientific_validation": {
        "status": "primary_source_validated",
        "primary_data_check": {"status": "bundled", "finding": "All source rows are available."},
        "verified_fields": ["equation", "parameters"],
    }}
    before = deepcopy(record)
    label, detail = eos.record_reproduction(record)
    assert label == "Not assessed"
    assert "Source verification alone" in detail
    assert "All source rows" in detail
    assert record == before


@pytest.mark.parametrize("status,expected", [
    ("parity", "Parameter parity"), ("similar", "Similar"),
    ("parity_not_achieved", "Not reproduced"),
    ("curve_data_parity_accepted", "Curve parity"),
    ("fit_protocol_limited", "Limited check"),
    ("not_refittable", "Not refittable"),
    ("future_unrecognized_assessment", "Check documented"),
])
def test_explicit_assessments_retain_qualification(status, expected):
    record = {"scientific_validation": {
        "status": "primary_source_validated",
        "independent_refit": {"result": status, "notes": "The source weights are unpublished."},
    }}
    label, detail = eos.record_reproduction(record)
    assert label == expected
    assert "The source weights are unpublished." in detail


def test_equation_parity_does_not_override_failed_fit_reproduction():
    record = {"reproduction": {
        "equation_status": "reproduced", "fit_status": "not_reproduced",
        "summary_status": "approximate_internal_consistency_reproduced",
        "display_label": "Approximate internal consistency only",
        "reason": "Original fit rows were not recovered.",
    }}
    label, detail = eos.record_reproduction(record)
    assert label == "Not reproduced"
    assert "Original fit rows" in detail
    assert "Approximate internal consistency only" in detail


def test_independent_child_does_not_claim_reproduction_of_published_parent():
    record = {"record_kind": "refit", "scientific_validation": {
        "status": "primary_source_validated",
        "original_publication_reproduction_status": "not_reproduced",
    }}
    label, detail = eos.record_reproduction(record)
    assert label == "Independent refit"
    assert "source-author fit was not reproduced" in detail


def test_user_copy_does_not_inherit_a_reproduction_pass():
    record = {"reproduction": {"fit_status": "reproduced"}}
    assert eos.record_reproduction(record, origin="custom")[0] == "Not assessed"
    record["scientific_validation"] = {
        "status": "deferred", "note": "User-owned copy; parameters changed."}
    assert eos.record_reproduction(record)[0] == "Not assessed"


def test_explicit_do_not_use_takes_precedence_over_positive_parity():
    record = {"reproduction": {"do_not_use": True, "fit_status": "reproduced",
                               "reason": "Use for diagnostic inspection only."}}
    assert eos.record_reproduction(record)[0] == "Do not use"


def test_installed_fu_published_record_and_independent_refit_stay_distinct():
    material = next(m for m in eos.load_materials() if m.identifier == "ca_perovskite")
    records = {r["identifier"]: r for r in material.eos_records}
    published = records["ca_perovskite_fu_2023_bm3_mgd_refit"]
    before = deepcopy(published)
    label, detail = eos.record_reproduction(published)
    assert label == "Not reproduced"
    assert "174 reconstructed candidate observations" in detail
    assert "does not disclose the exact row manifest, objective, or weights" in detail
    assert published == before
    assert eos.record_reproduction(records[
        "ca_perovskite_fu_2023_candidate_data_unweighted_bm3_mgd_refit"])[0] == "Independent refit"


def test_new_explicit_assessment_supersedes_historical_catalog_notice():
    record = {"identifier": "ca_perovskite_fu_2023_bm3_mgd_refit",
              "scientific_validation": {"fit_reproduction_status": "reproduced"}}
    assert eos.record_reproduction(record)[0] == "Reproduced"


def test_nullable_or_unsupported_metadata_does_not_imply_a_pass():
    record = {"scientific_validation": {"status": None, "note": None},
              "reproduction": None, "numerical_reproduction": None}
    assert eos.record_reproduction(record)[0] == "Not assessed"


@pytest.mark.parametrize("scope,status,expected", [
    ("parameter_agreement", "parity", "Parameter parity"),
    ("parameter_agreement", "not_reproduced", "Not reproduced"),
    ("source_equation", "source_reconstruction", "Equation reconstruction"),
    ("new_scope", "new_status", "Check documented"),
])
def test_scoped_assessment_preserves_basis_limits_and_separate_recommendation(scope, status, expected):
    record = {"scientific_validation": {
        "status": "primary_source_validated",
        "usage_recommendation": "not_recommended_for_quantitative_use",
        "recommendation_reason": "Unresolved high-temperature discrepancy.",
    }, "reproduction": {"fit_status": "not_reproduced", "assessment": {
        "scope": scope, "status": status, "basis": "Reported error widths.",
        "qualifications": ["Conditional subset only.", "Original weights unknown."],
        "report_url": "https://example.org/report/#record",
    }}}
    before = deepcopy(record)
    label, detail = eos.record_reproduction(record)
    assert label == expected
    assert "Reported error widths" in detail
    assert "Conditional subset only" in detail
    assert "Original weights unknown" in detail
    assert "Original-author fit reproduction: not reproduced" in detail
    assert "Source validation: primary source validated" in detail
    assert "Recommendation: Not recommended for quantitative use" in detail
    assert "Unresolved high-temperature discrepancy" in detail
    assert record == before


@pytest.mark.parametrize("url,accepted", [
    ("https://example.org/report/#record", True),
    ("file:///tmp/report.html", False), ("javascript:alert(1)", False),
    ("docs/report.md", False), (None, False),
    ("https://[malformed-host", False),
])
def test_report_action_uses_web_urls_and_does_not_inherit_edited_claim(url, accepted):
    record = {"reproduction": {"assessment": {"report_url": url}}}
    assert eos.reconstruction_report_url(record) == (url if accepted else "")
    assert eos.reconstruction_report_url(record, origin="custom") == ""


def test_installed_gold_scoped_parameter_parity_is_not_original_workflow_reproduction():
    from peritheos import get_material_document
    record = next(r for r in get_material_document("gold")["eos_records"]
                  if r["identifier"] == "gold_fei_2007_vinet_2")
    label, detail = eos.record_reproduction(record)
    assert label == "Parameter parity"
    assert "Original-author fit reproduction: Not established" in detail
    assert "Conditional numerical parity" in detail
    assert eos.reconstruction_report_url(record).startswith("https://peritheos.readthedocs.io/")


def test_refit_replay_does_not_override_original_author_failure():
    record = {"record_kind": "refit", "scientific_validation": {
        "original_publication_reproduction_status": "not_reproduced",
    }, "reproduction": {"fit_status": "reproduced", "assessment": {
        "status": "parity", "scope": "independent_refit",
    }}}
    label, detail = eos.record_reproduction(record)
    assert label == "Independent refit"
    assert "Original-author fit reproduction: not reproduced" in detail


def test_explicit_source_do_not_use_recommendation_is_visible_without_hover():
    record = {"scientific_validation": {
        "usage_recommendation": "DO NOT USE for scientific predictions or pressure calibration. Diagnostic comparison only.",
    }, "reproduction": {"assessment": {"status": "similar", "scope": "parameter_agreement"}}}
    label, detail = eos.record_reproduction(record)
    assert label == "Do not use"
    assert "DO NOT USE for scientific predictions" in detail.split("\n\n", 1)[0]
