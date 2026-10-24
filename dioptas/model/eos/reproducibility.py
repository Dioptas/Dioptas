# SPDX-License-Identifier: MIT
"""Conservative presentation of catalog reproduction assessments.

Source verification, parameter agreement, curve checks and original-fit
reproduction are separate claims. Only explicit assessment fields determine
the summary; prose and the presence of data are not treated as a pass/fail test.
"""

from urllib.parse import urlparse


def _metadata(value):
    return value if isinstance(value, dict) else {}


def _audit_notes(value):
    """Keep the source's scope and qualifications readable without raw JSON."""
    notes = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"note", "notes", "finding", "reason", "limitation",
                       "qualification", "assessment", "conclusion", "selection",
                       "scope", "method", "objective", "result", "display_label"}:
                if isinstance(item, str) and not item.startswith(("docs/", "scripts/")):
                    notes.append(item)
            if isinstance(item, (dict, list)):
                notes.extend(_audit_notes(item))
    elif isinstance(value, list):
        for item in value:
            notes.extend(_audit_notes(item))
    return list(dict.fromkeys(notes))


_ASSESSMENTS = {
    "reproduced": "Reproduced",
    "fit_reproduced": "Reproduced",
    "parity": "Parameter parity",
    "parity_accepted": "Parameter parity",
    "parameter_and_curve_parity_accepted": "Parameter parity",
    "parameters_reproduced_within_reported_uncertainties": "Parameter parity",
    "similar": "Similar",
    "near_parity": "Similar",
    "method_dependent_near_parity": "Similar",
    "parity_within_figure_digitization": "Limited check",
    "curve_data_parity_accepted": "Curve parity",
    "not_reproduced": "Not reproduced",
    "parity_not_achieved": "Not reproduced",
    "not_refittable": "Not refittable",
    "fit_protocol_limited": "Limited check",
    "approximate_internal_consistency_reproduced": "Limited check",
    "published_equation_verified_equal_weight_subset_checked": "Limited check",
    "published_surface_executable_fit_not_independently_reproducible": "Not refittable",
    "published_surface_parity_fit_not_independently_reproducible": "Not refittable",
    "final_input_parity_upstream_reduction_partial": "Limited check",
}


def _is_user_copy(record, origin):
    validation = _metadata(record.get("scientific_validation"))
    return (origin == "custom" or (
        validation.get("status") == "deferred"
        and str(validation.get("note", "")).startswith("User-owned copy;")))


def reconstruction_report_url(record, *, origin=None):
    """A user-clicked web report, never an inherited claim for edited values."""
    if _is_user_copy(record, origin):
        return ""
    assessment = _metadata(_metadata(record.get("reproduction")).get("assessment"))
    url = assessment.get("report_url")
    if not isinstance(url, str):
        return ""
    try:
        parsed = urlparse(url)
        return url if parsed.scheme in {"http", "https"} and parsed.hostname else ""
    except ValueError:
        return ""


def _scoped_assessment(record, assessment):
    validation = _metadata(record.get("scientific_validation"))
    reproduction = _metadata(record.get("reproduction"))
    scope = assessment.get("scope")
    scope_name = {
        "parameter_agreement": "Parameter agreement",
        "source_equation": "Source equation reconstruction",
        "independent_refit": "Independent refit check",
    }.get(scope, "Scoped numerical check")
    status = assessment.get("status")
    label = _ASSESSMENTS.get(status, "Check documented")
    if scope not in {"parameter_agreement", "source_equation", "independent_refit"}:
        label = "Check documented"
    if scope == "source_equation" and status in {"parity", "source_reconstruction"}:
        label = "Equation reconstruction"
    elif record.get("record_kind") == "refit":
        label = ("Provisional refit" if validation.get("refit_status") == "provisional"
                 else "Independent refit")
    if reproduction.get("do_not_use") is True:
        label = "Do not use"
    source = str(validation.get("status") or "not recorded").replace("_", " ")
    recommendation = validation.get("usage_recommendation")
    if not isinstance(recommendation, str):
        recommendation = None
    recommendation = {
        "not_recommended_for_quantitative_use": "Not recommended for quantitative use",
        "on_hold_not_recommended_pending_source_mapping_review": "On hold pending source mapping review",
    }.get(recommendation, recommendation)
    # Full source wording remains in the details; keep the visible overview short.
    recommendation_label = (recommendation if recommendation in {
        "Not recommended for quantitative use", "On hold pending source mapping review",
    } else "Qualified; see details" if recommendation else "Not recorded")
    if recommendation and recommendation.upper().startswith("DO NOT USE"):
        label = "Do not use"
        recommendation_label = recommendation.partition(". ")[0].rstrip(".")
    workflow_status = validation.get("original_publication_reproduction_status")
    if record.get("record_kind") != "refit":
        workflow_status = (workflow_status or reproduction.get("fit_status")
                           or validation.get("fit_reproduction_status"))
    workflow = (str(workflow_status).replace("_", " ") if workflow_status
                else "Not established by this scoped numerical assessment")
    overview = (f"{scope_name}: {label}.\nSource validation: {source}.\n"
                f"Original-author fit reproduction: {workflow}.\n"
                f"Recommendation: {recommendation_label}.")
    notes = [str(assessment.get("basis") or "No comparison basis recorded.")]
    qualifications = assessment.get("qualifications") or []
    if isinstance(qualifications, list):
        notes.extend(note for note in qualifications if isinstance(note, str))
    notes.extend(_audit_notes(_metadata(validation.get("primary_data_check"))))
    notes.extend(note for note in (
        validation.get("fit_reproduction_note"), recommendation,
        validation.get("recommendation_reason"),
    ) if isinstance(note, str) and note)
    if record.get("record_kind") == "refit":
        notes.append("This independent refit does not establish reproduction of the source-author fit.")
    notes.append("Source verification alone does not establish fit reproduction, physical accuracy or recommendation for use.")
    return label, "\n\n".join([overview, *dict.fromkeys(notes)])


def record_reproduction(record, *, origin=None):
    """Return a display label and explanation without changing the record."""
    validation = _metadata(record.get("scientific_validation"))
    reproduction = _metadata(record.get("reproduction"))
    summary = _metadata(validation.get("reproduction_summary"))
    refit = _metadata(validation.get("independent_refit"))
    numerical = _metadata(validation.get("numerical_reproduction"))
    protocol = _metadata(validation.get("refit_reproduction"))
    provenance = _metadata(record.get("fit_provenance"))
    published = _metadata(record.get("published_fit_provenance"))
    statuses = [
        validation.get("status"), validation.get("fit_reproduction_status"),
        summary.get("status"), reproduction.get("fit_status"),
        reproduction.get("summary_status"),
        protocol.get("status"),
        *[refit.get(key) for key in ("status", "result", "classification")],
        numerical.get("result"),
        *[_metadata(p.get("reproduction")).get(key)
          for p in (provenance, published) for key in ("status", "scope_status")],
    ]
    for check in (validation.get("reproduction"), numerical.get("independent_refit"),
                  numerical.get("independent_300_k_refit")):
        statuses.extend(_metadata(check).get(key)
                        for key in ("status", "result", "classification", "conclusion"))
    statuses = [value for value in statuses if isinstance(value, str)]
    label = "Not assessed"
    explanation = "No explicit fit-reproduction assessment is recorded."
    if _is_user_copy(record, origin):
        return (label, "Reproduction: Not assessed.\nUser-edited coefficients do "
                "not inherit the source record's reproduction assessment.")
    assessment = _metadata(reproduction.get("assessment"))
    if assessment:
        return _scoped_assessment(record, assessment)
    if reproduction.get("do_not_use") is True:
        label, explanation = "Do not use", "The source audit marks this record for diagnostic inspection only."
    elif any(_ASSESSMENTS.get(value) == "Not reproduced" for value in statuses):
        label, explanation = "Not reproduced", "Reproduction of the published fit is not established in the documented audit."
    elif record.get("record_kind") == "refit":
        label = "Independent refit"
        explanation = "This is a separate refit with its own coefficients; it does not establish reproduction of the original publication's fit."
        if validation.get("refit_status") == "provisional":
            label = "Provisional refit"
        if validation.get("original_publication_reproduction_status") == "not_reproduced":
            explanation += " The source-author fit was not reproduced."
    else:
        # Compatibility with older catalogs that predate structured warnings.
        # This published record's primary_data_check explicitly retains the
        # non-parity audit; its independent Peritheos refit is a separate record.
        data_check = _metadata(validation.get("primary_data_check"))
        if (record.get("identifier") == "ca_perovskite_fu_2023_bm3_mgd_refit"
                and not any(value in _ASSESSMENTS for value in statuses)
                and data_check.get("observation_count") == 174
                and "non-parity audit" in str(data_check.get("finding", ""))):
            label = "Not reproduced"
            explanation = ("The published coefficients and equation are source verified, "
                           "but the joint Sun (2016)–Gréaux (2019) fit reported by Fu "
                           "(2023) was not reproduced from the 174 candidate observations. "
                           "The original selection, objective and weights remain undisclosed.")
        else:
            label = next((_ASSESSMENTS[value] for value in statuses
                          if value in _ASSESSMENTS), label)
            if label == "Parameter parity":
                explanation = "Published parameters agree with the documented independent check. This does not establish recovery of the original weights, covariance or complete fitting protocol."
            elif label == "Reproduced":
                explanation = "The source records reproduction of the fit; the scope and qualifications below still apply."
            elif label == "Similar":
                explanation = "The documented check gives similar results; strict reproduction has not been established."
            elif label == "Curve parity":
                explanation = "The published curve agrees with the checked data. This does not establish reproduction of the original regression."
            elif label == "Not refittable":
                explanation = "The available inputs do not permit an independent reproduction of the original fit."
            elif label == "Limited check":
                explanation = "A qualified or partial numerical check is documented; full original-fit reproduction is not established."
            elif numerical or refit or record.get("numerical_reproduction") or record.get("reproduction_audit"):
                label, explanation = "Check documented", "Numerical checks are recorded without an explicit overall reproduction outcome."
    notes = []
    for metadata in (reproduction, summary, refit, numerical, protocol,
                     _metadata(validation.get("reproduction")),
                     _metadata(provenance.get("reproduction")),
                     _metadata(published.get("reproduction")),
                     _metadata(record.get("numerical_reproduction")),
                     _metadata(record.get("reproduction_audit"))):
        notes.extend(_audit_notes(metadata))
    notes.extend(value for value in (
        validation.get("fit_reproduction_note"), validation.get("usage_notes"),
        _metadata(validation.get("primary_data_check")).get("finding"),
    ) if isinstance(value, str) and value)
    if (label in {"Independent refit", "Provisional refit"}
            and isinstance(record.get("notes"), str) and record["notes"]):
        notes.append(record["notes"])
    source_status = validation.get("status")
    source_status = (source_status.replace("_", " ") if
                     isinstance(source_status, str) else "not recorded")
    detail = [f"Reproduction: {label}. {explanation}",
              f"Source validation: {source_status}. Source verification alone does not establish fit reproduction.",
              *dict.fromkeys(notes)]
    return label, "\n\n".join(detail)
