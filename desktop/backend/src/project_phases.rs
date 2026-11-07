//! CrystalState adapters preserve source documents and stored reflection tables.
use super::*;
use crate::{
    phase_crystal as crystal,
    phases::{self, Phase},
};
pub(super) fn load(s: &mut Session, document: &Value) -> Result<(), String> {
    let options = with_defaults("phase", &document["phase"]);
    s.phases.same_conditions = boolean(&options["same_conditions"], "Same conditions")?;
    s.phases.cold_pressure = boolean(
        &options["dac_thermal_pressure_enabled"],
        "DAC thermal pressure",
    )?;
    if s.phases.cold_pressure && options["dac_thermal_pressure_factor"].as_f64() != Some(0.25) {
        return Err("This project's DAC thermal-pressure factor is not supported by the current native phase adapter.".into());
    }
    let rows = document["phases"].as_array().cloned().unwrap_or_default();
    if rows.len() > 1000 {
        return Err("Project contains too many phases.".into());
    }
    let mut ids = std::collections::BTreeSet::new();
    for (i, row) in rows.iter().enumerate() {
        let state = with_defaults("crystal", &row["crystal"]);
        let display = &row["params"];
        let has_document = state["material_document"]
            .as_object()
            .is_some_and(|v| !v.is_empty());
        let mut doc = if has_document {
            phases::working_document(state["material_document"].clone())?
        } else {
            json!({"format_version":2,"name":row["name"],"formula":state["chemistry"],"lattice":{},"eos_records":[],"peaks":[],"source":{"kind":"jcpds","legacy":{}}})
        };
        doc["name"] = row["name"].clone();
        doc["symmetry"] = state["symmetry"].clone();
        doc["lattice"] = json!({"a":state["a0"],"b":state["b0"],"c":state["c0"],"alpha":state["alpha0"],"beta":state["beta0"],"gamma":state["gamma0"]});
        doc["eos_records"] = state["eos_records"].clone();
        if !state["zc"].is_null() {
            doc["formula_units_per_cell"] = state["zc"].clone();
        }
        if !doc["source"].is_object() {
            doc["source"] = json!({});
        }
        for (from, to) in [
            ("k0", "k0"),
            ("k0p0", "k0p"),
            ("alpha_t0", "alphat"),
            ("d_alpha_dt", "dalphadt"),
            ("dk0dt", "dk0dt"),
            ("dk0pdt", "dk0pdt"),
            ("n", "n"),
            ("z", "z"),
        ] {
            // CrystalState fills absent coefficients with zero. Keep that
            // absence in authored CIF/material documents unless the flat
            // state actually supplies an edit or a legacy coefficient.
            if !has_document
                || doc["source"]["legacy"].get(to).is_some()
                || state[from] != defaults()["crystal"][from]
            {
                if !doc["source"]["legacy"].is_object() {
                    doc["source"]["legacy"] = json!({});
                }
                doc["source"]["legacy"][to] = state[from].clone();
            }
        }
        if state["eos_records_modified"] == true {
            phases::repair_record_links(&mut doc);
        }
        let source_rows = row["reflections"]
            .as_array()
            .ok_or("Missing project reflection table.")?;
        if source_rows.len() > 2_000_000 {
            return Err("Project reflection table is too large.".into());
        }
        let mut reflections = vec![];
        for r in source_rows {
            let a = r
                .as_array()
                .filter(|a| a.len() == 5)
                .ok_or("Invalid project reflection row.")?;
            let mut v = [0.; 5];
            for j in 0..5 {
                v[j] = finite(&a[j], "Reflection", -1e12, 1e12)?;
            }
            if v[4] <= 0.0 || v[3] < 0.0 {
                return Err("Project reflection spacings/intensities are invalid.".into());
            }
            reflections.push([v[0], v[1], v[2], v[4], v[3]]);
        }
        let uid = display["uid"]
            .as_str()
            .map(str::to_string)
            .unwrap_or_else(|| format!("project-phase-{i}"));
        if uid.is_empty() || !ids.insert(uid.clone()) {
            return Err("Project phase IDs must be unique.".into());
        }
        let color = display["color"]
            .as_array()
            .filter(|a| a.len() == 3)
            .ok_or("Invalid phase color.")?;
        let rgb = color
            .iter()
            .map(|v| integer(v, "Phase color", 0, 255))
            .collect::<Result<Vec<_>, _>>()?;
        let count = phases::records(&doc).len();
        let reference = if count == 0 {
            None
        } else {
            Some(integer(
                &state["eos_current_index"],
                "Phase reference",
                0,
                count - 1,
            )?)
        };
        let q = state["reflection_q_max"].as_f64().unwrap_or(0.0);
        let mut p = Phase {
            uid,
            document: doc,
            filename: text(&row["filename"]),
            origin: state["material_origin"].as_str().unwrap_or("legacy").into(),
            pressure: finite(&state["pressure"], "Pressure", -9_999_999., 9_999_999.)?,
            temperature: finite(&state["temperature"], "Temperature", 0., 9_999_999.)?,
            visible: display["visible"].as_bool().unwrap_or(true),
            color: format!("#{:02x}{:02x}{:02x}", rgb[0], rgb[1], rgb[2]),
            reference,
            modified: state["modified"].as_bool().unwrap_or(false),
            reflections: Arc::new(reflections),
            minimum: if q > 0.0 {
                std::f64::consts::TAU / q
            } else {
                0.5
            },
            cutoff: state["reflection_intensity_cutoff"].as_f64().unwrap_or(0.5),
            current_volume: 0.,
            eos_cache: None,
        };
        p.recalculate(
            s.settings.geometry.wavelength * 1e10,
            s.phases.cold_pressure,
            false,
        )?;
        s.phases.items.push(Arc::new(p));
    }
    s.phases.next_uid = s
        .phases
        .items
        .iter()
        .filter_map(|p| p.uid.strip_prefix("rust-phase-")?.parse::<u64>().ok())
        .max()
        .unwrap_or(0)
        .saturating_add(1);

    Ok(())
}
pub(super) fn save(s: &Session, doc: &mut Value) -> Result<(), String> {
    doc["phase"] = with_defaults("phase", &doc["phase"]);
    doc["phase"]["same_conditions"] = json!(s.phases.same_conditions);
    doc["phase"]["dac_thermal_pressure_enabled"] = json!(s.phases.cold_pressure);
    let old = doc["phases"].as_array().cloned().unwrap_or_default();
    let mut rows = vec![];
    for p in &s.phases.items {
        let mut row = old
            .iter()
            .find(|r| r["params"]["uid"] == p.uid)
            .cloned()
            .unwrap_or(json!({}));
        if !row["params"].is_object() {
            row["params"] = json!({});
        }
        let color = (1..7)
            .step_by(2)
            .map(|i| u8::from_str_radix(&p.color[i..i + 2], 16).unwrap())
            .collect::<Vec<_>>();
        merge(
            &mut row["params"],
            &json!({"uid":p.uid,"visible":p.visible,"color":color}),
        );
        row["filename"] = json!(p.filename);
        row["name"] = json!(p.name());
        let mut state = with_defaults("crystal", &row["crystal"]);
        let c = crystal::cell(&p.document)?;
        merge(
            &mut state,
            &json!({"version":4,"chemistry":p.document["formula"],"symmetry":p.document["symmetry"],"a0":c.a_angstrom,"b0":c.b_angstrom,"c0":c.c_angstrom,
            "alpha0":c.alpha_deg,"beta0":c.beta_deg,"gamma0":c.gamma_deg,"v0":p.reference_volume(),"pressure":p.pressure,"temperature":p.temperature,
            "material_document":p.document,"material_origin":p.origin,"eos_records":phases::records(&p.document),"eos_current_index":p.reference.unwrap_or(0),
            "eos_default_index":phases::default_reference(&p.document).map(|i|i as i64).unwrap_or(-1),"eos_records_modified":p.modified,
            "modified":p.modified,"reflection_q_max":std::f64::consts::TAU/p.minimum,"reflection_wavelength":s.settings.geometry.wavelength*1e10,
            "reflection_intensity_cutoff":p.cutoff,"zc":p.document["formula_units_per_cell"]}),
        );
        let coefficients = p.legacy_coefficients();
        for (key, v) in ["alpha_t0", "d_alpha_dt", "dk0dt", "dk0pdt"]
            .iter()
            .zip(coefficients)
        {
            state[key] = json!(v);
        }
        let record = p
            .reference
            .and_then(|i| phases::records(&p.document).get(i));
        for (field, param) in [
            ("k0", "K0"),
            ("k0p0", "K0_prime"),
            ("k0pp0", "K0_double_prime"),
            ("p0", "P0"),
            ("n", "n"),
            ("z", "Z"),
        ] {
            state[field] = record
                .and_then(|r| r["eos"]["parameters"].get(param))
                .cloned()
                .or_else(|| {
                    p.document["source"]["legacy"]
                        .get(if field == "k0p0" { "k0p" } else { field })
                        .cloned()
                })
                .unwrap_or_else(|| defaults()["crystal"][field].clone());
        }
        state["eos_type"] = json!(
            record
                .and_then(|r| r["eos"]["type"].as_str())
                .unwrap_or("BM3")
        );
        if let Some(r) = record.filter(|r| {
            !r["thermal"].is_null()
                && !(r["thermal"]["type"] == "AlphaKT" && r["thermal"]["model"].is_null())
        }) {
            state["thermal_type"] = r["thermal"]["type"].clone();
            state["thermal_parameters"] = r["thermal"]["parameters"].clone();
            if let Some(fields) = r["thermal"].as_object() {
                for (key, value) in fields {
                    if value.is_string() && !["type", "model"].contains(&key.as_str()) {
                        state["thermal_parameters"][key] = value.clone();
                    }
                }
            }
        } else {
            state["thermal_type"] = json!("");
            state["thermal_parameters"] = json!({});
        }
        row["crystal"] = state;
        row["reflections"] = json!(
            p.reflections
                .iter()
                .map(|r| [r[0], r[1], r[2], r[4], r[3]])
                .collect::<Vec<_>>()
        );
        rows.push(row);
    }
    doc["phases"] = json!(rows);
    Ok(())
}
