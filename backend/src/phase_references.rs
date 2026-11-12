//! Display citations and record-owned documentation links; no inferred validation.
use serde_json::{Value, json};
pub(crate) fn source_annotation(record: &Value) -> Option<&'static Value> {
    if record["scientific_validation"]["status"] == "deferred" {
        return None;
    }
    static ANNOTATIONS: std::sync::OnceLock<Value> = std::sync::OnceLock::new();
    ANNOTATIONS
        .get_or_init(|| {
            serde_json::from_str(include_str!("../resources/peritheos/record-display.json"))
                .expect("checked source annotations")
        })
        .get(record["identifier"].as_str()?)
}
fn scalar(v: &Value) -> String {
    v.as_str().map(str::to_string).unwrap_or_else(|| {
        if v.is_null() {
            String::new()
        } else {
            v.to_string()
        }
    })
}
pub(crate) fn authors(reference: &Value) -> String {
    if let Some(s) = reference.as_str() {
        return s.split(" (").next().unwrap_or(s).into();
    }
    let a: Vec<_> = reference["authors"]
        .as_array()
        .into_iter()
        .flatten()
        .filter_map(Value::as_str)
        .collect();
    if a.len() > 2 || reference["authors_truncated"] == true {
        a.first().map_or(String::new(), |a| format!("{a} et al."))
    } else {
        a.join(" and ")
    }
}
pub(crate) fn year(reference: &Value) -> String {
    if reference.is_object() {
        return scalar(&reference["year"]);
    }
    reference
        .as_str()
        .and_then(|s| s.rsplit_once('('))
        .and_then(|(_, s)| s.strip_suffix(')'))
        .filter(|s| s.len() == 4 && s.bytes().all(|c| c.is_ascii_digit()))
        .unwrap_or("")
        .into()
}
pub(crate) fn text(reference: &Value) -> String {
    if let Some(s) = reference.as_str() {
        return s.into();
    }
    let a: Vec<_> = reference["authors"]
        .as_array()
        .into_iter()
        .flatten()
        .filter_map(Value::as_str)
        .collect();
    let author = if reference["authors_truncated"] == true {
        authors(reference)
    } else if a.len() > 2 {
        format!("{}, and {}", a[..a.len() - 1].join(", "), a[a.len() - 1])
    } else {
        a.join(" and ")
    };
    let mut publication = scalar(&reference["source"]);
    if !reference["volume"].is_null() {
        publication.push_str(&format!(" {}", scalar(&reference["volume"])));
    }
    if !reference["locator"].is_null() {
        publication.push_str(&format!(", {}", scalar(&reference["locator"])));
    }
    let mut text = [author, publication]
        .into_iter()
        .filter(|s| !s.is_empty())
        .collect::<Vec<_>>()
        .join(", ");
    let year = year(reference);
    if !year.is_empty() {
        text.push_str(&format!(" ({year})"));
    }
    for key in ["details", "doi"] {
        if !reference[key].is_null() {
            text.push_str(&format!(", {}", scalar(&reference[key])));
        }
    }
    text
}
pub(crate) fn pressure_range(record: &Value) -> String {
    if let Some(a) = record["experimental_pressure_range_gpa"]
        .as_array()
        .filter(|a| a.len() == 2)
        && let Some((low, high)) = a[0].as_f64().zip(a[1].as_f64())
    {
        return if low == high {
            format!("{low} GPa")
        } else {
            format!("{low}–{high} GPa")
        };
    }
    match record["pressure_range_status"].as_str() {
        Some("theoretical") => "theoretical",
        Some("reference_parameterization") => "reference model",
        Some("reported_qualitatively") => "qualitative limit",
        _ => "",
    }
    .into()
}
pub(crate) fn report_url(record: &Value) -> String {
    let url = record["reproduction"]["assessment"]["report_url"]
        .as_str()
        .unwrap_or("");
    if record["scientific_validation"]["status"] == "deferred" {
        return String::new();
    }
    if url.starts_with("https://") || url.starts_with("http://") {
        url.into()
    } else {
        String::new()
    }
}
pub(crate) fn record_url(record: &Value) -> String {
    let identifier = record["identifier"].as_str().unwrap_or("");
    if identifier.is_empty() || record["scientific_validation"]["status"] == "deferred" {
        return String::new();
    }
    let encoded = identifier
        .bytes()
        .map(|b| {
            if b.is_ascii_alphanumeric() || b"-_.~".contains(&b) {
                (b as char).to_string()
            } else {
                format!("%{b:02X}")
            }
        })
        .collect::<String>();
    format!("https://peritheos.com/eos/{encoded}")
}
pub(crate) fn catalog_record(doc: &Value, index: usize, record: &Value) -> Value {
    let mut result = json!({"label":super::phases::label(record),"eos":record["eos"]["type"].as_str().unwrap_or(""),"thermal":record["thermal"]["type"].as_str().unwrap_or(""),"pressureRange":pressure_range(record),"parameters":record["eos"]["parameters"].as_object().cloned().unwrap_or_default(),"errors":record["parameter_errors"].as_object().cloned().unwrap_or_default(),"fixed":record["fixed_parameters"].as_array().cloned().unwrap_or_default(),"assessment":record["scientific_validation"]["status"].as_str().unwrap_or("Source record"),"detail":format!("{}\n\n{}",text(&record["reference"]),record["notes"].as_str().unwrap_or("")),"loadError":super::phases::load_error(doc,Some(index)),"assumedLoadError":"","authors":authors(&record["reference"]),"year":year(&record["reference"]),"identifier":record["identifier"].as_str().unwrap_or(""),"citation":text(&record["reference"]),"notes":record["notes"].as_str().unwrap_or(""),"temperatureRange":record["experimental_temperature_range_k"],"temperatureRef":record["temperature_ref"],"thermalParameters":record["thermal"]["parameters"].as_object().cloned().unwrap_or_default(),"thermalErrors":record["thermal"]["parameter_errors"].as_object().cloned().unwrap_or_default(),"thermalFixed":record["thermal"]["fixed_parameters"].as_array().cloned().unwrap_or_default(),"reportUrl":report_url(record),"recordUrl":record_url(record),"sourceRecord":record});
    if let Some(annotation) = source_annotation(record) {
        for (key, value) in annotation.as_object().unwrap() {
            result[key] = value.clone();
        }
    }
    result
}
