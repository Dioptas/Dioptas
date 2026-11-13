//! Versioned PhaseSmith protocol boundary. JSON controls are translated to the
//! public typed coordinator; no numerical algorithm is implemented here.
use super::*;
pub(super) fn builtin() -> Value {
    serde_json::from_str(include_str!("../data/scxrd-protocol-v29.json"))
        .expect("bundled pinned PhaseSmith protocol")
}
/// JSON integer/float spelling is not a scientific control change. Only exact
/// numeric equality is accepted; no numerical tolerance is used here.
pub(super) fn same_json(a: &Value, b: &Value) -> bool {
    match (a, b) {
        (Value::Number(x), Value::Number(y)) => {
            if x == y {
                return true;
            }
            let exact_integer = |n: &serde_json::Number| {
                n.as_i64().map_or_else(
                    || n.as_u64().is_none_or(|v| v <= 9_007_199_254_740_992),
                    |v| v.unsigned_abs() <= 9_007_199_254_740_992,
                )
            };
            if !exact_integer(x) || !exact_integer(y) {
                return false;
            }
            match (x.as_f64(), y.as_f64()) {
                (Some(xf), Some(yf)) => xf == yf && xf.abs() <= 9_007_199_254_740_992.,
                _ => false,
            }
        }
        (Value::Array(x), Value::Array(y)) => {
            x.len() == y.len() && x.iter().zip(y).all(|(a, b)| same_json(a, b))
        }
        (Value::Object(x), Value::Object(y)) => {
            x.len() == y.len()
                && x.iter()
                    .all(|(key, a)| y.get(key).is_some_and(|b| same_json(a, b)))
        }
        _ => a == b,
    }
}
pub(super) fn validate(p: &Value) -> Result<(), String> {
    if p["schema"] != "phasesmith.enstatite-raw-workflow.v1" {
        return Err("Unsupported PhaseSmith protocol schema.".into());
    }
    if p.get("space_group_search").is_some() {
        return Err("This Dioptas protocol adapter currently supports supplied-symmetry protocols (including v29). Automatic-symmetry protocols require a separate hypothesis-review adapter; they are not silently converted to a supplied group.".into());
    }
    let hard = number(p, "search", "hard_seconds")?;
    let native = number(p, "search", "native_seconds")?;
    if hard < native || hard <= 0. || hard > 7200. {
        return Err("Protocol hard search budget must cover the native budget and stay within 7200 seconds.".into());
    }
    let frozen = builtin();
    let document = p.as_object().ok_or("Protocol must be an object.")?;
    for key in document.keys() {
        if frozen.get(key).is_none() {
            return Err(format!(
                "Unsupported protocol field {key}; it was not ignored."
            ));
        }
    }
    for section in [
        "acquisition",
        "shadow_mask",
        "frame_input_execution",
        "frame_preparation_execution",
        "profile_execution",
        "search",
    ] {
        let object = p[section]
            .as_object()
            .ok_or_else(|| format!("Protocol section {section} must be an object."))?;
        for key in object.keys() {
            if frozen[section].get(key).is_none() {
                return Err(format!("Unsupported protocol control {section}.{key}."));
            }
        }
    }
    for section in ["illumination", "geometric"] {
        let object = p["shadow_mask"][section]
            .as_object()
            .ok_or("Invalid shadow controls")?;
        for key in object.keys() {
            if frozen["shadow_mask"][section].get(key).is_none() {
                return Err(format!("Unsupported shadow control {section}.{key}."));
            }
        }
    }

    if !same_json(&p["native_coordinator"], &frozen["native_coordinator"]) {
        return Err("Protocol native-coordinator algorithm, null-rotation identity or unsupported controls differ from the pinned PhaseSmith implementation.".into());
    }
    for name in [
        "detection",
        "linking",
        "indexing",
        "selection",
        "geometry",
        "prediction",
        "integration",
        "profiles",
        "reduction",
        "measurement_validity",
        "search_configuration",
        "gates",
        "io",
        "archive_output",
        "numerical_equivalence",
        "execution_equivalence",
        "geometry_backend",
        "profile_fitting_backend",
        "empirical_scaling_backend",
        "numerical_worker_import_policy",
        "baseline_profile_execution",
    ] {
        if !same_json(&p[name], &frozen[name]) {
            return Err(format!(
                "The pinned PhaseSmith orthorhombic-v1 coordinator does not support modified {name} controls. The protocol was not applied."
            ));
        }
    }
    if p["acquisition"]["vertical_flip"] != true
        || p["shadow_mask"]["mode"] != "combined"
        || p["acquisition"]["gain"].as_f64() != Some(1.)
        || p["acquisition"]["read_noise"].as_f64() != Some(0.)
    {
        return Err("Native protocol v1 requires the declared vertical flip, combined DAC/seat masks, unit gain and zero read noise. Unsupported values are never ignored.".into());
    }
    if p["frame_input_execution"]["reuse_verified_digest"]
        != frozen["frame_input_execution"]["reuse_verified_digest"]
    {
        return Err(
            "Protocol digest reuse policy is fixed by the verified original-count source boundary."
                .into(),
        );
    }
    for (section, key) in [("acquisition", "workers"), ("", "detection_workers")] {
        let value = if section.is_empty() {
            &p[key]
        } else {
            &p[section][key]
        };
        if !value.as_u64().is_some_and(|v| (1..=256).contains(&v)) {
            return Err(format!("Protocol requires 1 to 256 {section}.{key}."));
        }
    }
    for (section, names) in [
        (
            "frame_input_execution",
            vec![
                "native_preparation_workers",
                "batch_frames",
                "payload_bytes",
                "decoded_cache_bytes",
            ],
        ),
        (
            "frame_preparation_execution",
            vec!["workers", "max_in_flight_bytes"],
        ),
        ("profile_execution", vec!["workers", "geometry_cache_bytes"]),
    ] {
        for name in names {
            let _ = integer(p, section, name)?;
        }
    }
    Ok(())
}
pub(super) fn integer(p: &Value, section: &str, name: &str) -> Result<usize, String> {
    p[section][name]
        .as_u64()
        .and_then(|n| usize::try_from(n).ok())
        .ok_or_else(|| format!("Protocol requires integer {section}.{name}."))
}
pub(super) fn number(p: &Value, section: &str, name: &str) -> Result<f64, String> {
    p[section][name]
        .as_f64()
        .filter(|x| x.is_finite())
        .ok_or_else(|| format!("Protocol requires finite {section}.{name}."))
}
impl Config {
    pub(super) fn apply_protocol(&mut self, p: Value) -> Result<(usize, usize), String> {
        validate(&p)?;
        let first = integer(&p, "acquisition", "first_frame")?;
        let last = integer(&p, "acquisition", "last_frame_inclusive")?;
        if first > last || last >= MAX_FRAMES {
            return Err("Invalid protocol frame interval.".into());
        }
        self.omega_start = number(&p, "acquisition", "omega_at_original_frame_zero_degrees")?;
        self.omega_step = number(&p, "acquisition", "step_degrees")?;
        self.exposure = number(&p, "acquisition", "exposure_width_degrees")?;
        self.axis = serde_json::from_value(p["acquisition"]["axis"].clone()).map_err(err)?;
        self.saturation = number(&p, "acquisition", "mask_minimum_reserved_uint32")?;
        let shadows = &p["shadow_mask"];
        self.dac_axis = serde_json::from_value(shadows["geometric"]["axis_at_omega_zero"].clone())
            .map_err(err)?;
        self.dac_half_opening = shadows["geometric"]["half_opening_degrees"]
            .as_f64()
            .ok_or("DAC opening missing")?;
        self.shadow_block = shadows["illumination"]["block"]
            .as_u64()
            .ok_or("Shadow block missing")? as usize;
        if shadows["geometric"]["pixel_block"] != json!(self.shadow_block) {
            return Err("This adapter requires matching illumination/DAC block sides.".into());
        }
        self.seat_threshold = shadows["illumination"]["threshold"]
            .as_f64()
            .ok_or("Seat threshold missing")?;
        self.seat_guard = shadows["illumination"]["guard_pixels"]
            .as_u64()
            .ok_or("Seat guard missing")? as usize;
        self.integration_method = "profile".into();
        self.background = false;
        self.scan_scaling = false;
        self.dac_enabled = true;
        self.seat_enabled = true;
        self.refine_geometry = true;
        self.aperture_radius = 7;
        self.omega_radius = 4.5;
        self.polarization = 0.98;
        self.threshold = 5.;
        self.min_pixels = 3;
        self.link_radius = 5.;
        self.gain = 1.;
        self.read_noise = 0.;
        self.search_seconds = number(&p, "search", "native_seconds")?;
        self.protocol = Some(p);
        self.confirmed = false;
        self.check()?;
        Ok((first, last))
    }
    pub(super) fn active_protocol(&self, first: usize, last: usize) -> Result<Value, String> {
        let mut p = self.protocol.clone().unwrap_or_else(builtin);
        // Acquisition/mask edits are explicit overrides and are frozen into the
        // effective protocol and its hash, never silently dropped.
        let a = &mut p["acquisition"];
        a["first_frame"] = json!(first);
        a["last_frame_inclusive"] = json!(last);
        a["omega_at_original_frame_zero_degrees"] = json!(self.omega_start);
        a["step_degrees"] = json!(self.omega_step);
        a["exposure_width_degrees"] = json!(self.exposure);
        a["axis"] = json!(self.axis);
        a["mask_minimum_reserved_uint32"] = json!(self.saturation.ceil() as u32);
        a["gain"] = json!(self.gain);
        a["read_noise"] = json!(self.read_noise);
        p["shadow_mask"]["geometric"]["axis_at_omega_zero"] = json!(self.dac_axis);
        p["shadow_mask"]["geometric"]["half_opening_degrees"] = json!(self.dac_half_opening);
        p["shadow_mask"]["geometric"]["pixel_block"] = json!(self.shadow_block);
        p["shadow_mask"]["illumination"]["block"] = json!(self.shadow_block);
        p["shadow_mask"]["illumination"]["threshold"] = json!(self.seat_threshold);
        p["shadow_mask"]["illumination"]["guard_pixels"] = json!(self.seat_guard);
        p["search"]["native_seconds"] = json!(self.search_seconds);
        validate(&p)?;
        Ok(p)
    }
}
