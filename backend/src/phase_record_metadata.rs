//! Field-level publication metadata edits. Never deserialize/rebuild scientific coefficients.
use serde_json::{Value, json};

pub(crate) fn token(record: &Value) -> String {
    blake3::hash(&serde_json::to_vec(record).expect("JSON record serialization"))
        .to_hex()
        .to_string()
}

fn text(value: &Value) -> Result<String, String> {
    let s = value.as_str().ok_or("Expected text.")?.trim();
    if s.len() > 65536 || s.chars().any(|c| c.is_control() && c != '\n' && c != '\t') {
        return Err("Text is too long or contains unsupported control characters.".into());
    }
    Ok(s.into())
}
fn number(value: &Value) -> Result<f64, String> {
    value
        .as_f64()
        .filter(|n| n.is_finite())
        .ok_or("Enter a finite number.".into())
}
fn optional(target: &mut Value, key: &str, value: Value) -> Result<(), String> {
    let map = target
        .as_object_mut()
        .ok_or("Metadata container is not an object; retained unchanged.")?;
    if value.is_null() || value == "" || value == false || value == json!([]) {
        map.remove(key);
    } else {
        map.insert(key.into(), value);
    }
    Ok(())
}

/// Validate everything on an owned clone, then commit atomically. Untouched keys retain their
/// original representation, including strings, nulls, unsupported metadata and source conventions.
pub(crate) fn edited(record: &Value, args: &Value) -> Result<Value, String> {
    if args["expected_record_token"].as_str() != Some(token(record).as_str()) {
        return Err("This record changed while you were editing. Cancel the draft and review the current record before trying again.".into());
    }
    let changes = args["changes"]
        .as_object()
        .ok_or("Supply metadata changes.")?;
    let mut next = record.clone();
    for (key, value) in changes {
        match key.as_str() {
            "notes" => optional(&mut next, key, json!(text(value)?))?,
            "temperature_ref" => {
                if !value.is_null() && number(value)? < 0.0 {
                    return Err("Reference temperature must be nonnegative (K).".into());
                }
                optional(&mut next, key, value.clone())?;
            }
            "reference" => {
                let fields = value
                    .as_object()
                    .ok_or("Supply structured reference fields.")?;
                let mut reference = if let Some(s) = next["reference"].as_str() {
                    if s.is_empty() {
                        json!({})
                    } else {
                        json!({"details":s})
                    }
                } else if next["reference"].is_null() {
                    json!({})
                } else {
                    next["reference"].clone()
                };
                for (field, v) in fields {
                    let validated = match field.as_str() {
                        "authors" => json!(
                            v.as_array()
                                .ok_or("Authors must be a list.")?
                                .iter()
                                .map(text)
                                .collect::<Result<Vec<_>, _>>()?
                                .into_iter()
                                .filter(|s| !s.is_empty())
                                .collect::<Vec<_>>()
                        ),
                        "authors_truncated" => json!(
                            v.as_bool()
                                .ok_or("Truncated-author flag must be boolean.")?
                        ),
                        "year" => {
                            if !v.is_null() && !v.as_u64().is_some_and(|y| y <= 9999) {
                                return Err(
                                    "Year must be an integer from 0 to 9999, or blank.".into()
                                );
                            }
                            v.clone()
                        }
                        "source" | "volume" | "locator" | "doi" | "details" => json!(text(v)?),
                        _ => return Err("Unknown literature field.".into()),
                    };
                    optional(&mut reference, field, validated)?;
                }
                next["reference"] = if reference.as_object().is_some_and(|r| r.is_empty()) {
                    json!("")
                } else {
                    reference
                };
            }
            "ranges" => {
                for (field, v) in value.as_object().ok_or("Supply ranges.")? {
                    if ![
                        "experimental_pressure_range_gpa",
                        "experimental_temperature_range_k",
                        "pressure_gpa",
                        "temperature_k",
                    ]
                    .contains(&field.as_str())
                    {
                        return Err("Unknown range.".into());
                    }
                    if !v.is_null() {
                        let a = v
                            .as_array()
                            .filter(|a| a.len() == 2)
                            .ok_or("Supply both range limits, or clear both.")?;
                        let (low, high) = (number(&a[0])?, number(&a[1])?);
                        if low > high || (field.contains("temperature") && low < 0.0) {
                            return Err(
                                "Enter ordered range limits; temperatures must be nonnegative."
                                    .into(),
                            );
                        }
                    }
                    let target = if field.starts_with("experimental_") {
                        &mut next
                    } else {
                        if next["validity"].is_null() {
                            next["validity"] = json!({});
                        }
                        &mut next["validity"]
                    };
                    optional(target, field, v.clone())?;
                }
            }
            "parameters" => {
                for row in value.as_array().ok_or("Supply parameter metadata rows.")? {
                    let scope = row["scope"].as_str().ok_or("Missing parameter scope.")?;
                    if !["eos", "thermal"].contains(&scope) {
                        return Err("Unknown parameter scope.".into());
                    }
                    let name = row["key"].as_str().ok_or("Missing parameter name.")?;
                    let original = if scope == "eos" {
                        record
                    } else {
                        &record["thermal"]
                    };
                    let parameters = &record[scope]["parameters"];
                    let known = parameters.get(name).is_some()
                        || original["parameter_errors"].get(name).is_some()
                        || original["fixed_parameters"]
                            .as_array()
                            .is_some_and(|a| a.iter().any(|n| n == name));
                    if !known {
                        return Err("Unknown parameter; coefficients cannot be added through publication metadata.".into());
                    }
                    let target = if scope == "eos" {
                        &mut next
                    } else {
                        &mut next["thermal"]
                    };
                    if let Some(error) = row.get("error") {
                        if !error.is_null() {
                            number(error)?;
                        }
                        if target["parameter_errors"].is_null() {
                            target["parameter_errors"] = json!({});
                        }
                        // Qt represents an explicitly cleared reported error as null. Signed
                        // errors are accepted, preserving the publication's own convention.
                        target["parameter_errors"]
                            .as_object_mut()
                            .ok_or("Reported errors are not an object.")?
                            .insert(name.into(), error.clone());
                    }
                    if let Some(fixed) = row.get("fixed") {
                        let fixed = fixed
                            .as_bool()
                            .ok_or("Publication-fixed must be boolean.")?;
                        if target["fixed_parameters"].is_null() {
                            target["fixed_parameters"] = json!([]);
                        }
                        let names = target["fixed_parameters"]
                            .as_array_mut()
                            .ok_or("Fixed parameters are not a list.")?;
                        if fixed {
                            if !names.iter().any(|n| n == name) {
                                names.push(json!(name));
                            }
                        } else {
                            names.retain(|n| n != name);
                        }
                    }
                    if row.as_object().is_none_or(|r| {
                        r.keys()
                            .any(|k| !["scope", "key", "error", "fixed"].contains(&k.as_str()))
                    }) {
                        return Err("Unknown parameter metadata field.".into());
                    }
                }
            }
            _ => return Err("Unknown publication metadata field.".into()),
        }
    }
    if next != *record && next["scientific_validation"]["status"] == "primary_source_validated" {
        if next.get("source_scientific_validation").is_none() {
            next["source_scientific_validation"] = next["scientific_validation"].clone();
        }
        // Preserve unknown audit fields, but never present an edited source record as
        // primary-source validated merely because its original source was validated.
        next["scientific_validation"]["status"] = json!("deferred");
        next["scientific_validation"]["note"] = json!(
            "User-edited publication record; original source attribution and validation are retained."
        );
    }
    Ok(next)
}

/// The numerical engine requires authors AND year in a structured citation.
/// Qt/user records allow either to be unknown. Adapt only the disposable engine
/// document to its supported free-text representation; the owned EOSMAT/.dio
/// document keeps the full structured citation, unknown fields and blank semantics.
pub(crate) fn prepare_reference_for_engine(record: &mut Value) {
    let reference = &record["reference"];
    if reference.is_object()
        && (!reference["authors"]
            .as_array()
            .is_some_and(|a| !a.is_empty())
            || !reference["year"].is_u64())
    {
        let mut parts = Vec::new();
        if let Some(authors) = reference["authors"].as_array() {
            parts.push(
                authors
                    .iter()
                    .filter_map(Value::as_str)
                    .collect::<Vec<_>>()
                    .join(", "),
            );
        }
        for key in [
            "year", "title", "source", "volume", "locator", "doi", "details",
        ] {
            if let Some(s) = reference.get(key).filter(|v| !v.is_null()) {
                parts.push(
                    s.as_str()
                        .map(str::to_owned)
                        .unwrap_or_else(|| s.to_string()),
                );
            }
        }
        record["reference"] = json!(
            parts
                .into_iter()
                .filter(|s| !s.is_empty())
                .collect::<Vec<_>>()
                .join(" · ")
        );
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn source_audits_free_text_and_optional_nulls_survive_metadata_edits() {
        let record = json!({"reference":"Original free-text citation","eos":{"parameters":{"V0":12.0,"K0":100.0}},"thermal":{"parameters":{"Tr":null,"unused":null}},"scientific_validation":{"status":"primary_source_validated","note":"Original audit","unknown_audit":{"verbatim":true}},"parameter_error_confidence":{"unknown_convention":"as reported"},"unknown_integer":9007199254740993_u64});
        let next = edited(
            &record,
            &json!({"expected_record_token":token(&record),"changes":{"notes":"User note"}}),
        )
        .unwrap();
        for key in [
            "eos",
            "thermal",
            "reference",
            "parameter_error_confidence",
            "unknown_integer",
        ] {
            assert_eq!(next[key], record[key]);
        }
        assert_eq!(
            next["source_scientific_validation"],
            record["scientific_validation"]
        );
        assert_eq!(
            next["scientific_validation"]["unknown_audit"],
            record["scientific_validation"]["unknown_audit"]
        );
        assert_eq!(next["scientific_validation"]["status"], "deferred");
        let structured=edited(&next,&json!({"expected_record_token":token(&next),"changes":{"reference":{"authors":["Author"]}}})).unwrap();
        assert_eq!(structured["reference"]["details"], record["reference"]);
        assert_eq!(structured["reference"]["authors"], json!(["Author"]));
        assert_ne!(token(&next), token(&structured));
    }
}
