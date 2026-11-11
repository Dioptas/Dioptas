//! Existing phase command/editor contract; no detector or cake rebuild on edits.
use super::*;
use crate::{
    phase_crystal as crystal,
    phases::{self, Phase},
};
fn schema() -> &'static Value {
    static SCHEMA: std::sync::OnceLock<Value> = std::sync::OnceLock::new();
    SCHEMA.get_or_init(|| {
        serde_json::from_str(include_str!("../resources/phase-editor-schema.json"))
            .expect("checked editor metadata")
    })
}
fn compatibility(eos: &str, thermal: &str, parameters: &Value) -> String {
    if !["", "none", "alphakt"].contains(&thermal) && eos == "LinearUsUpHugoniot" {
        return "A Hugoniot reference cannot have a thermal correction.".into();
    }
    if ["DoubleDebyeHelmholtz", "DoubleDebyeLogMomentHelmholtz"].contains(&thermal)
        && !["BM2", "BM3", "BM4", "Vinet"].contains(&eos)
    {
        return "Double-Debye requires BM2, BM3, BM4, or Vinet.".into();
    }
    if thermal == "ThermalModifiedTait" && eos != "ModifiedTait" {
        return "Thermal Modified Tait requires a Modified Tait reference EOS.".into();
    }
    if thermal == "AlphaKT"
        && parameters["kprime_log_coefficient"]
            .as_f64()
            .is_some_and(|v| v != 0.0)
        && ![
            "BM3",
            "Baonza",
            "Murnaghan",
            "Morse3",
            "NaturalStrain3",
            "SunMorse3",
            "SunMorse4",
            "Vinet",
        ]
        .contains(&eos)
    {
        return format!(
            "This AlphaKT model has a temperature-dependent K′ shift, which Peritheos does not support with {eos}. Set kprime_log_coefficient to zero or choose a compatible EOS."
        );
    }
    String::new()
}
fn key_name(key: &str) -> &str {
    match key {
        "k0" => "K0",
        "k0p0" => "K0_prime",
        "k0pp0" => "K0_double_prime",
        "p0" => "P0",
        "z" => "Z",
        "zc" => "Zc",
        other => other,
    }
}
fn legacy_key(key: &str) -> &str {
    match key {
        "k0p0" => "k0p",
        "alpha_t0" => "alphat",
        "d_alpha_dt" => "dalphadt",
        other => other,
    }
}
fn lattice_key(key: &str) -> Option<&str> {
    match key {
        "a0" => Some("a"),
        "b0" => Some("b"),
        "c0" => Some("c"),
        "alpha0" => Some("alpha"),
        "beta0" => Some("beta"),
        "gamma0" => Some("gamma"),
        _ => None,
    }
}
fn lattice_keys(symmetry: &str) -> Vec<&'static str> {
    match symmetry {
        "CUBIC" => vec!["a0"],
        "TETRAGONAL" | "HEXAGONAL" | "TRIGONAL" => vec!["a0", "c0"],
        "RHOMBOHEDRAL" => vec!["a0", "alpha0"],
        "ORTHORHOMBIC" => vec!["a0", "b0", "c0"],
        "MONOCLINIC" => vec!["a0", "b0", "c0", "beta0"],
        _ => vec!["a0", "b0", "c0", "alpha0", "beta0", "gamma0"],
    }
}
fn record_mut(p: &mut Phase) -> Result<&mut Value, String> {
    let i = p
        .reference
        .ok_or("Add an EoS record before editing this field.")?;
    p.document["eos_records"]
        .as_array_mut()
        .and_then(|r| r.get_mut(i))
        .ok_or_else(|| "Unknown EoS record.".into())
}
fn custom_record(p: &Phase) -> Value {
    let mut record = json!({"identifier":format!("{}_custom",p.uid),"label":"Custom EoS","reference":"User-created EoS","parameter_errors":{},"fixed_parameters":[],"eos":{"type":"BM3","model":"birch_murnaghan_3","parameters":{"V0":crystal::volume(crystal::cell(&p.document).unwrap()).unwrap(),"K0":p.document["source"]["legacy"]["k0"].as_f64().unwrap_or(100.0),"K0_prime":p.document["source"]["legacy"]["k0p"].as_f64().unwrap_or(4.0)}},"temperature_ref":298.15,"scientific_validation":{"status":"deferred","note":"User-created EoS; not primary-source validated."}});
    for key in ["n", "z"] {
        if let Some(v) = material_number(p, key) {
            record["eos"]["parameters"][key_name(key)] = json!(v);
        }
    }
    record
}
fn material_number(p: &Phase, key: &str) -> Option<f64> {
    let r = p
        .reference
        .and_then(|i| phases::records(&p.document).get(i));
    if key == "zc" {
        return p.document["formula_units_per_cell"].as_f64();
    }
    if let Some(v) = r
        .and_then(|r| r["eos"]["parameters"][key_name(key)].as_f64())
        .or_else(|| p.document["source"]["legacy"][key].as_f64())
    {
        return Some(v);
    }
    let formula = crate::phase_sites::formula(p.document["formula"].as_str().unwrap_or("")).ok()?;
    if key == "n" {
        return Some(formula.values().sum());
    }
    let elements: Value =
        serde_json::from_str(include_str!("../resources/elements.json")).expect("checked elements");
    formula
        .iter()
        .map(|(element, count)| {
            elements
                .as_array()
                .unwrap()
                .iter()
                .find(|e| e["symbol"] == *element)
                .and_then(|e| e["number"].as_f64())
                .map(|n| n * count)
        })
        .collect::<Option<Vec<_>>>()
        .map(|v| v.iter().sum())
}
fn thermal_defaults(p: &Phase, kind: &str) -> Result<Value, String> {
    let metadata = &schema()["thermal"][kind];
    let fields = metadata["fields"]
        .as_array()
        .ok_or("Unsupported thermal model.")?;
    let record = p
        .reference
        .and_then(|i| phases::records(&p.document).get(i));
    let k0 = record
        .and_then(|r| r["eos"]["parameters"]["K0"].as_f64())
        .unwrap_or(100.0);
    let n = material_number(p, "n").unwrap_or(1.0);
    let molar = p.reference_volume() * 0.060221415 / material_number(p, "zc").unwrap_or(1.0);
    let tr = record
        .and_then(|r| r["temperature_ref"].as_f64())
        .unwrap_or(298.15);
    let mut values = json!({});
    for field in fields {
        let key = field["key"].as_str().unwrap();
        let initial = field["initial"].clone();
        if initial.is_null() {
            continue;
        }
        values[key] = if key == "n" {
            json!(n)
        } else if field["required"] == true {
            match key {
                "Tr" => json!(tr),
                "dK_dT" | "dK_dT_V" => json!(-1e-4 * k0),
                "alpha_KT" | "alpha_KT_ref" | "c2" => json!(3e-5 * k0),
                "mE1" | "mE2" => json!(1.5 * n),
                "m_B1" | "m_B2" | "m_E1" | "m_E2" => json!(0.75 * n),
                "Vp" => json!(molar),
                _ => initial,
            }
        } else {
            initial
        };
    }
    Ok(values)
}
fn mark_record(p: &mut Phase) {
    if let Ok(r) = record_mut(p) {
        if r.get("equation_kind").is_some() {
            r["equation_kind"] = json!(if !r["thermal"].is_null() {
                "thermal"
            } else if r["eos"]["type"] == "LinearUsUpHugoniot" {
                "hugoniot"
            } else {
                "isothermal"
            });
        }
        if r["scientific_validation"]["status"] == "primary_source_validated" {
            let original = r["scientific_validation"].clone();
            r["source_scientific_validation"] = original;
        }
        r["scientific_validation"] = json!({"status":"deferred","note":"User-edited EoS; source provenance is retained, edited values are not primary-source validated."});
    }
}
fn parameter(p: &mut Phase, key: &str, v: &Value) -> Result<bool, String> {
    p.require_editable()?;
    if key == "symmetry" {
        let symmetry = v
            .as_str()
            .ok_or("Choose a crystal symmetry.")?
            .to_uppercase();
        p.document["symmetry"] = json!(symmetry);
        update_cell(p)?;
        return Ok(true);
    }
    if let Some(k) = lattice_key(key) {
        if !lattice_keys(p.document["symmetry"].as_str().unwrap_or("")).contains(&key) {
            return Err("This lattice parameter is fixed by symmetry.".into());
        }
        p.document["lattice"][k] = json!(finite(
            v,
            key,
            if k.len() == 1 { 1e-6 } else { 0.001 },
            if k.len() == 1 { 99999.0 } else { 179.999 }
        )?);
        update_cell(p)?;
        return Ok(true);
    }
    let (low, high) = match key {
        "k0" => (0.0, 1e6),
        "k0p0" | "k0pp0" | "dk0dt" | "dk0pdt" => (-100.0, 100.0),
        "p0" => (-1e6, 1e6),
        "n" | "z" | "zc" => (1e-9, 1e6),
        "alpha_t0" | "d_alpha_dt" => (-1.0, 1.0),
        _ => return Err("Parameter is not part of the selected model.".into()),
    };
    let number = finite(v, key, low, high)?;
    if ["alpha_t0", "d_alpha_dt", "dk0dt", "dk0pdt"].contains(&key) {
        if let Some(r) = p
            .reference
            .and_then(|i| phases::records(&p.document).get(i))
            && r["thermal"]["type"].as_str().is_some_and(|s| !s.is_empty())
            && !(r["thermal"]["type"] == "AlphaKT" && r["thermal"]["model"].is_null())
        {
            return Err("Use the selected constructor's thermal fields.".into());
        }
        p.document["source"]["legacy"][legacy_key(key)] = json!(number);
        if let Ok(r) = record_mut(p)
            && r["thermal"]["type"] == "AlphaKT"
            && r["thermal"]["model"].is_null()
        {
            let alias = match key {
                "alpha_t0" => "alpha0",
                "d_alpha_dt" => "d_alpha_dT",
                "dk0dt" => "dK_dT",
                _ => "dK_prime_dT",
            };
            r["thermal"]["parameters"][alias] = json!(number);
        }
        mark_record(p);
        return Ok(false);
    }
    if key == "zc" {
        let z = integer(v, key, 1, 1_000_000)?;
        p.document["formula_units_per_cell"] = json!(z);
    } else if p.reference.is_some() {
        let r = record_mut(p)?;
        let names = schema()["eos"][r["eos"]["type"].as_str().unwrap_or("")]
            .as_array()
            .cloned()
            .unwrap_or_default();
        if !names.iter().any(|n| n == key_name(key)) && !matches!(key, "n" | "z") {
            return Err("Parameter is not part of the selected equation of state.".into());
        }
        r["eos"]["parameters"][key_name(key)] = json!(number);
        mark_record(p);
    } else {
        p.document["source"]["legacy"][legacy_key(key)] = json!(number);
    }
    Ok(false)
}
fn update_cell(p: &mut Phase) -> Result<(), String> {
    crystal::constrain(&mut p.document)?;
    let cell = crystal::cell(&p.document)?;
    let metric = cell
        .geometry()
        .map_err(|e| e.to_string())?
        .reciprocal_metric;
    if let Some(peaks) = p.document["peaks"].as_array_mut() {
        for r in peaks {
            let h = [
                r[0].as_f64().ok_or("Invalid Miller index.")?,
                r[1].as_f64().ok_or("Invalid Miller index.")?,
                r[2].as_f64().ok_or("Invalid Miller index.")?,
            ];
            let mut q = 0.0;
            for a in 0..3 {
                for b in 0..3 {
                    q += h[a] * metric[a][b] * h[b];
                }
            }
            if q <= 0.0 {
                return Err("A reflection requires a nonzero Miller index.".into());
            }
            r[3] = json!(q.sqrt().recip());
        }
    }
    let volume = crystal::volume(cell)?;
    if let Ok(r) = record_mut(p) {
        r["eos"]["parameters"]["V0"] = json!(volume);
        mark_record(p);
    }
    p.document["source"]["structure_modified"] = json!(true);
    Ok(())
}
#[cfg(feature = "dioptrin")]
pub(super) struct GuideFieldCache {
    geometry: Geometry,
    shape: [usize; 2],
    field: crate::contours::IndexedField,
    contours: std::collections::HashMap<u64, Value>,
    buffers: std::collections::HashMap<String, GuideBuffer>,
}
#[cfg(feature = "dioptrin")]
struct GuideBuffer {
    targets: Vec<u64>,
    buffer: crate::protocol::Buffer,
}

impl Session {
    pub(super) fn phase_guides(&self, args: &Value) -> Result<Reply, String> {
        let mut trace = crate::frame_trace::FrameTrace::new("phase-guides", self.revision);
        #[allow(unused_mut)] // Geometry guides are populated only with the optional engine.
        let mut guides: Vec<Value> = vec![];
        let binary = args["binary"].as_bool().unwrap_or(false);
        let mut buffers = vec![];
        #[cfg(feature = "dioptrin")]
        if let Some(image) = &self.image
            && self.settings.calibrated
        {
            // Pressure, temperature, lattice and style edits change targets,
            // not detector geometry. Reuse the exact display sample grid and
            // its strip bounds; do not scan every detector pixel per reflection.
            let mut cached = self.phase_guide_field.borrow_mut();
            if !cached
                .as_ref()
                .is_some_and(|c| c.geometry == self.settings.geometry && c.shape == image.shape)
            {
                let native = self.native_geometry(image.shape)?;
                let step = image.shape[0].max(image.shape[1]).div_ceil(512).max(1);
                *cached = Some(GuideFieldCache {
                    geometry: self.settings.geometry.clone(),
                    shape: image.shape,
                    field: crate::contours::IndexedField::sampled(
                        native.calc_tth_all(),
                        image.shape,
                        step,
                    ),
                    contours: Default::default(),
                    buffers: Default::default(),
                });
            }
            let cached = cached.as_mut().unwrap();
            trace.mark("field");
            let mut previous = std::mem::take(&mut cached.contours);
            let mut next = std::collections::HashMap::new();
            let field = &cached.field;
            let mut lines = vec![];
            let mut requested = std::collections::HashSet::new();
            let mut missing = vec![];
            for (i, p) in self
                .phases
                .items
                .iter()
                .enumerate()
                .filter(|(_, p)| p.visible)
            {
                let maximum = p.reflections.iter().map(|r| r[4]).fold(0.0, f64::max);
                let scale = (p.current_volume / p.reference_volume()).cbrt();
                for (j, r) in p.reflections.iter().enumerate() {
                    let t = crate::pattern::convert_coordinate(
                        p.cell_spacing(r) * scale,
                        "d_A",
                        "2th_deg",
                        self.settings.geometry.wavelength,
                    );
                    if !t.is_finite() {
                        continue;
                    }
                    let target = t.to_radians();
                    // Other phases usually retain their angles during an edit.
                    // Keep only the latest request's targets, so scrubbing
                    // pressure cannot accumulate an unbounded contour history.
                    let key = target.to_bits();
                    if requested.insert(key) {
                        if let Some(paths) = previous.remove(&key) {
                            next.insert(key, paths);
                        } else {
                            missing.push((key, target));
                        }
                    }
                    let intensity = if maximum > 0.0 { r[4] / maximum } else { 0.0 };
                    lines.push((i, j, t, &p.color, intensity, key));
                }
            }
            trace.mark("targets");
            let targets: Vec<_> = missing.iter().map(|(_, target)| *target).collect();
            for ((key, _), paths) in missing.into_iter().zip(field.contours(&targets)) {
                next.insert(key, paths);
            }
            trace.mark("contours");
            let mut retained = std::collections::HashMap::new();
            for phase in lines.chunk_by(|a, b| a.0 == b.0) {
                let i = phase[0].0;
                let mut point_offset = 0;
                let packed = if binary {
                    let uid = &self.phases.items[i].uid;
                    let targets: Vec<_> = phase.iter().map(|line| line.5).collect();
                    let hit = cached.buffers.remove(uid).filter(|b| b.targets == targets);
                    let packed = hit.unwrap_or_else(|| {
                        let mut bytes = vec![];
                        for line in phase {
                            for path in next[&line.5].as_array().unwrap() {
                                for point in path["points"].as_array().unwrap() {
                                    for coordinate in point.as_array().unwrap() {
                                        bytes.extend_from_slice(
                                            &coordinate.as_f64().unwrap().to_le_bytes(),
                                        );
                                    }
                                }
                            }
                        }
                        GuideBuffer {
                            targets,
                            buffer: crate::protocol::Buffer::new(bytes),
                        }
                    });
                    let descriptor = (packed.buffer.id.clone(), packed.buffer.bytes.len() / 16);
                    if descriptor.1 > 0 {
                        buffers.push(packed.buffer.clone());
                    }
                    retained.insert(uid.clone(), packed);
                    Some(descriptor)
                } else {
                    None
                };
                for &(i, j, t, color, intensity, key) in phase {
                    for path in next[&key].as_array().unwrap() {
                        let points = if let Some((id, count)) = &packed {
                            let length = path["points"].as_array().unwrap().len();
                            let descriptor = json!({"bufferId":id,"dtype":"xy-f64le","count":count,"offset":point_offset,"length":length});
                            point_offset += length;
                            descriptor
                        } else {
                            path["points"].clone()
                        };
                        let mut guide = json!({"ring":0,"twoTheta":t,"color":color,"phaseIndex":i,"reflectionIndex":j,"lineWidth":1.0+3.0*intensity,"opacity":0.3+0.4*intensity});
                        guide["points"] = points;
                        guides.push(guide);
                    }
                }
            }
            cached.buffers = retained;
            trace.mark("metadata");
            cached.contours = next;
        }
        // Move the large array into the reply; json! on Vec<Value> recursively
        // clones every coordinate for a second time.
        let mut result = json!({"ok":true});
        result["phaseGuides"] = Value::Array(guides);
        trace.mark("reply");
        let _ = binary; // Diagnostic builds return the same empty metadata.
        Ok(Reply { result, buffers })
    }
    fn phase_minimum(&self) -> f64 {
        self.patterns
            .raw
            .as_ref()
            .and_then(|p| {
                p.x.iter()
                    .map(|&x| {
                        crate::pattern::convert_coordinate(
                            x,
                            &self.patterns.unit,
                            "q_A^-1",
                            self.settings.geometry.wavelength,
                        )
                    })
                    .filter(|q| q.is_finite() && *q > 0.0)
                    .reduce(f64::max)
            })
            .map_or(0.5, |q| {
                std::f64::consts::TAU
                    / (q * 1.05).min(
                        (4.0 * std::f64::consts::PI / (self.settings.geometry.wavelength * 1e10))
                            * (1.0 - f64::EPSILON),
                    )
            })
    }
    pub(super) fn phase_response(&self) -> Reply {
        let mut reply = self.snapshot(false);
        reply.buffers.clear();
        for key in [
            "image", "rawImage", "mask", "cake", "rings", "linked", "batch", "map",
        ] {
            reply.result.as_object_mut().unwrap().remove(key);
        }
        reply.result["patternOnly"] = json!(true);
        reply.result["phaseOnly"] = json!(true);
        reply.result["batchPhaseLines"] = self
            .phases
            .lines("d_A", self.settings.geometry.wavelength * 1e10);
        reply
    }
    pub(super) fn phase_command(
        &mut self,
        action: &str,
        args: &Value,
    ) -> Result<Option<Reply>, String> {
        let wavelength = self.settings.geometry.wavelength * 1e10;
        match action {
            "integration_phase_state" => return Ok(Some(self.phase_response())),
            "integration_phase_files" => {
                let paths = if let Some(p) = args.get("paths") {
                    p.clone()
                } else {
                    json!([path(args)?])
                };
                return Ok(Some(Reply::metadata(
                    json!({"ok":true,"phaseImport":{"paths":paths,"minimumDSpacing":self.phase_minimum()}}),
                )));
            }
            "integration_phase_catalog" => {
                let query = args["query"].as_str().unwrap_or("").trim();
                let mut entries = vec![];
                for source in phases::search(query) {
                    let doc = phases::working_document(source.clone())?;
                    let diffraction = crystal::cell(&doc).is_ok()
                        && (doc["atom_sites"].as_array().is_some_and(|s| !s.is_empty())
                            || doc["peaks"].as_array().is_some_and(|s| !s.is_empty()));
                    let assumed = if phases::can_assume(&doc) {
                        Some(phases::assumed_document(doc.clone())?)
                    } else {
                        None
                    };
                    let refs: Vec<_> = phases::records(&doc)
                        .iter()
                        .enumerate()
                        .map(|(i, r)| {
                            let mut record = crate::phase_references::catalog_record(&doc, i, r);
                            if let Some(d) = &assumed {
                                record["assumedLoadError"] = json!(phases::load_error(d, Some(i)));
                            }
                            record
                        })
                        .collect();
                    entries.push(json!({"id":doc["identifier"],"name":doc["name"],"formula":doc["formula"],"spaceGroup":doc["space_group"],"diffraction":diffraction,"diffractionStatus":if diffraction{"Crystal structure"}else if assumed.is_some(){"Assumption required"}else{"EoS only"},"canAssumeStructure":assumed.is_some(),"assumptionNote":assumed.as_ref().and_then(|d|d["source"]["assumed_structure"]["note"].as_str()).unwrap_or(""),"defaultReference":phases::default_reference(&doc).map_or(if phases::records(&doc).is_empty(){0}else{-1},|i|i as i64),"hold":doc["recommendation_hold"]["reason"].as_str().unwrap_or(""),"notes":doc["notes"].as_str().unwrap_or(""),"references":refs}));
                }
                return Ok(Some(Reply::metadata(
                    json!({"ok":true,"phaseCatalog":entries}),
                )));
            }
            "integration_phase_editor" => {
                let i = self.phases.resolve(args)?;
                return Ok(Some(Reply::metadata(
                    json!({"ok":true,"phaseRevision":self.revision,"phaseEditor":self.phase_editor(i)?}),
                )));
            }
            "integration_phase_documentation" => {
                let source = phases::catalog()
                    .iter()
                    .find(|d| d["identifier"] == args["material_id"])
                    .ok_or("Unknown database material.")?;
                let doc = phases::working_document(source.clone())?;
                let i = integer(
                    &args["reference"],
                    "Reference",
                    0,
                    phases::records(&doc)
                        .len()
                        .checked_sub(1)
                        .ok_or("No EoS records.")?,
                )?;
                let record = &phases::records(&doc)[i];
                let metadata = crate::phase_references::catalog_record(&doc, i, record);
                let key = match args["kind"].as_str() {
                    Some("report") => "reportUrl",
                    Some("record") => "recordUrl",
                    _ => return Err("Unknown documentation kind.".into()),
                };
                let url = metadata[key]
                    .as_str()
                    .filter(|s| s.starts_with("https://") || s.starts_with("http://"))
                    .filter(|s| !s.contains(['\n', '\r', '\0']))
                    .ok_or("No documentation is recorded for this selection.")?;
                return Ok(Some(Reply::metadata(
                    json!({"ok":true,"documentationUrl":url}),
                )));
            }
            "integration_phase_export" => return self.phase_export(args).map(Some),
            "integration_phase_list" => return self.phase_list(args).map(Some),
            "integration_phase" => {}
            _ => return Ok(None),
        }
        let transaction = args["operation"] == "editor_transaction";
        let before = self.phases.clone();
        let result = self.phase_edit(args, wavelength);
        let index = match result {
            Ok(i) => i,
            Err(error) => {
                if !transaction {
                    return Err(error);
                }
                self.phases = before;
                let i = self.phases.resolve(args)?;
                let mut editor = self.phase_editor(i)?;
                editor["editError"] = json!(error);
                let mut reply = if args["editor_only"] == true {
                    Reply::metadata(json!({"ok":true}))
                } else {
                    self.phase_response()
                };
                reply.result["phaseEditor"] = editor;
                return Ok(Some(reply));
            }
        };
        self.rebuild_pattern()?;
        self.revision += 1;
        let mut reply = if args["editor_only"] == true {
            Reply::metadata(json!({"ok":true}))
        } else {
            self.phase_response()
        };
        if args["editor"] == true
            && let Some(i) = index.filter(|&i| i < self.phases.items.len())
        {
            reply.result["phaseEditor"] = self.phase_editor(i)?;
            reply.result["phaseRevision"] = json!(self.revision);
        }
        Ok(Some(reply))
    }
    fn phase_edit(&mut self, args: &Value, wavelength: f64) -> Result<Option<usize>, String> {
        let op = if args["operation"] == "editor_transaction" {
            args["edit_operation"].as_str()
        } else {
            args["operation"].as_str()
        }
        .ok_or("Choose a phase operation.")?;
        match op {
            "load" => {
                let paths = args["paths"]
                    .as_array()
                    .cloned()
                    .unwrap_or_else(|| vec![args["path"].clone()]);
                let minimum = args
                    .get("minimum_d_spacing")
                    .map_or(Ok(self.phase_minimum()), |v| {
                        finite(v, "Minimum d spacing", 0.01, 100.0)
                    })?;
                let cutoff = args.get("intensity_cutoff").map_or(Ok(0.5), |v| {
                    finite(v, "Intensity cutoff", 0.0, 100.0 - f64::EPSILON)
                })?;
                for p in paths {
                    self.control.check()?;
                    let file = Path::new(p.as_str().ok_or("Choose a phase file.")?);
                    let doc = phases::read_file(file)?;
                    self.phases.add(
                        doc,
                        file.to_string_lossy().into_owned(),
                        "file",
                        None,
                        minimum,
                        cutoff,
                        wavelength,
                    )?;
                }
                return Ok(None);
            }
            "load_database" => {
                let source = phases::catalog()
                    .iter()
                    .find(|d| d["identifier"] == args["material_id"])
                    .ok_or("Unknown database material.")?
                    .clone();
                let doc = phases::working_document(source)?;
                let doc = if args
                    .get("assume_structure")
                    .map_or(Ok(false), |v| boolean(v, "Assume structure"))?
                {
                    phases::assumed_document(doc)?
                } else {
                    doc
                };
                let reference = if phases::records(&doc).is_empty() {
                    None
                } else {
                    Some(integer(
                        &args["reference"],
                        "Reference",
                        0,
                        phases::records(&doc).len() - 1,
                    )?)
                };
                let error = phases::load_error(&doc, reference);
                if !error.is_empty() {
                    return Err(error);
                }
                let i = self.phases.add(
                    doc,
                    String::new(),
                    "bundled",
                    reference,
                    self.phase_minimum(),
                    0.5,
                    wavelength,
                )?;
                return Ok(Some(i));
            }
            "same_conditions" => {
                self.phases.same_conditions = boolean(&args["enabled"], "Same conditions")?;
                return Ok(None);
            }
            "clear" => {
                self.phases.items.clear();
                return Ok(None);
            }
            "visibility_all" => {
                let enabled = boolean(&args["visible"], "Visibility")?;
                for p in &mut self.phases.items {
                    Arc::make_mut(p).visible = enabled;
                }
                return Ok(None);
            }
            _ => {}
        }
        let mut i = self.phases.resolve(args)?;
        if op == "remove" {
            self.phases.items.remove(i);
            return Ok(None);
        }
        if op == "editor_copy" {
            let mut p = self.phases.items[i].as_ref().clone();
            let source_name = p.name().to_string();
            p.uid = format!("rust-phase-{}", self.phases.next_uid);
            self.phases.next_uid += 1;
            let mut name = format!("{source_name} (custom)");
            let mut n = 2;
            while self.phases.items.iter().any(|p| p.name() == name) {
                name = format!("{source_name} (custom {n})");
                n += 1;
            }
            p.document["source"]["copied_from"] = json!({"material_identifier":p.document["identifier"],"phase_name":source_name,"filename":p.filename,"scientific_validation":phases::records(&p.document).iter().map(|r|r["scientific_validation"].clone()).collect::<Vec<_>>()});
            p.document["name"] = json!(name);
            p.document["identifier"] = json!(p.uid);
            p.origin = "custom".into();
            p.filename.clear();
            p.modified = true;
            if let Some(records) = p.document["eos_records"].as_array_mut() {
                for r in records {
                    r["scientific_validation"] = json!({"status":"deferred","note":"Editable material copy; source values are retained, subsequent edits are not primary-source validated."});
                }
            }
            self.phases.items.push(Arc::new(p));
            i = self.phases.items.len() - 1;
            return Ok(Some(i));
        }
        if op == "reload" {
            let p = &self.phases.items[i];
            let doc = phases::read_file(Path::new(&p.filename))?;
            let p = Arc::make_mut(&mut self.phases.items[i]);
            p.document = doc;
            p.modified = false;
            p.recalculate(wavelength, self.phases.cold_pressure, true)?;
            return Ok(Some(i));
        }
        let p = Arc::make_mut(&mut self.phases.items[i]);
        let mut structure = false;
        match op {
            "update" => {
                for (k, v) in args.as_object().unwrap() {
                    match k.as_str() {
                        "pressure" => p.pressure = finite(v, k, -9999999.0, 9999999.0)?,
                        "temperature" => p.temperature = finite(v, k, 0.0, 9999999.0)?,
                        "reference" => {
                            p.reference = Some(integer(
                                v,
                                k,
                                0,
                                phases::records(&p.document)
                                    .len()
                                    .checked_sub(1)
                                    .ok_or("No EoS records.")?,
                            )?);
                        }
                        "visible" => p.visible = boolean(v, k)?,
                        "color" => p.color = crate::pattern::color(v)?,
                        "operation" | "index" | "editor_uid" | "editor" | "editor_only"
                        | "edit_operation" => {}
                        _ => return Err("Unknown phase option.".into()),
                    }
                }
            }
            "parameter" | "editor_parameter" => {
                structure = parameter(
                    p,
                    args["parameter"].as_str().ok_or("Choose a parameter.")?,
                    &args["value"],
                )?
            }
            "editor_name" => {
                p.require_editable()?;
                p.document["name"] = json!(printable(&args["value"], "Material name")?);
            }
            "editor_ratio" => {
                p.require_editable()?;
                let (key, reference) = match args["parameter"].as_str() {
                    Some("a/b") => ("a0", "b"),
                    Some("c/a") => ("c0", "a"),
                    Some("c/b") => ("c0", "b"),
                    _ => return Err("Unknown lattice ratio.".into()),
                };
                let value = finite(&args["value"], "Ratio", 1e-9, 1e9)?
                    * p.document["lattice"][reference]
                        .as_f64()
                        .ok_or("Missing reference cell length.")?;
                structure = parameter(p, key, &json!(value))?;
            }
            "reflection" => {
                p.require_editable()?;
                let mut rows = p.reflections.as_ref().clone();
                match args["action"].as_str() {
                    Some("add") => rows.push([1.0, 0.0, 0.0, 1.0, 100.0]),
                    Some("clear") => rows.clear(),
                    Some("remove") => {
                        let mut remove = vec![];
                        for r in args["rows"].as_array().ok_or("Choose reflection rows.")? {
                            remove.push(integer(
                                r,
                                "Reflection row",
                                0,
                                rows.len().checked_sub(1).ok_or("No reflections.")?,
                            )?);
                        }
                        rows = rows
                            .into_iter()
                            .enumerate()
                            .filter_map(|(i, r)| (!remove.contains(&i)).then_some(r))
                            .collect();
                    }
                    Some("update") => {
                        let row = integer(
                            &args["row"],
                            "Reflection row",
                            0,
                            rows.len().checked_sub(1).ok_or("No reflections.")?,
                        )?;
                        let key = args["parameter"]
                            .as_str()
                            .ok_or("Choose a reflection field.")?;
                        let k = match key {
                            "h" => 0,
                            "k" => 1,
                            "l" => 2,
                            "intensity" => 4,
                            _ => return Err("Only h,k,l and intensity are editable.".into()),
                        };
                        rows[row][k] = finite(
                            &args["value"],
                            key,
                            if k == 4 { 0.0 } else { -10000.0 },
                            if k == 4 { 1e9 } else { 10000.0 },
                        )?;
                        if rows[row][..3] == [0.0; 3] {
                            return Err("A reflection requires a nonzero Miller index.".into());
                        }
                    }
                    _ => return Err("Unknown reflection action.".into()),
                }
                let metric = crystal::cell(&p.document)?
                    .geometry()
                    .map_err(|e| e.to_string())?
                    .reciprocal_metric;
                for r in &mut rows {
                    let q: f64 = (0..3)
                        .flat_map(|a| (0..3).map(move |b| (a, b)))
                        .map(|(a, b)| r[a] * metric[a][b] * r[b])
                        .sum();
                    r[3] = 1.0 / q.sqrt();
                }
                p.document["peaks"] = json!(rows);
                p.reflections = Arc::new(rows);
            }
            "editor_eos_type" => {
                p.require_editable()?;
                ensure_record(p);
                let kind = args["value"].as_str().ok_or("Choose an EoS.")?;
                let names = schema()["eos"][kind]
                    .as_array()
                    .cloned()
                    .ok_or("Unsupported editable equation of state.")?;
                let atoms = material_number(p, "n").unwrap_or(1.0);
                let electrons = material_number(p, "z").unwrap_or(1.0);
                let r = record_mut(p)?;
                let old = r["eos"]["parameters"].clone();
                let mut params = json!({"V0":old["V0"]});
                for n in names {
                    let key = n.as_str().unwrap();
                    params[key] = old.get(key).cloned().unwrap_or_else(|| {
                        json!(if key == "K0" {
                            100.0
                        } else if key == "K0_prime" {
                            4.0
                        } else if key == "n" {
                            atoms
                        } else if key == "Z" {
                            electrons
                        } else if key == "K0_double_prime" {
                            -old["K0_prime"].as_f64().unwrap_or(4.0)
                                / old["K0"].as_f64().filter(|k| *k != 0.0).unwrap_or(100.0)
                        } else {
                            0.0
                        })
                    });
                }
                r["eos"] =
                    json!({"type":kind,"model":schema()["eosModels"][kind],"parameters":params});
                mark_record(p);
            }
            "editor_thermal_type" => {
                p.require_editable()?;
                ensure_record(p);
                let kind = args["value"].as_str().ok_or("Choose a thermal model.")?;
                if kind == "none" || kind == "alphakt" {
                    let coefficients = p.legacy_coefficients();
                    for (key, value) in ["alphat", "dalphadt", "dk0dt", "dk0pdt"]
                        .iter()
                        .zip(coefficients)
                    {
                        p.document["source"]["legacy"][key] = json!(value);
                    }
                    record_mut(p)?.as_object_mut().unwrap().remove("thermal");
                    if kind == "none" {
                        for key in ["alphat", "dalphadt", "dk0dt", "dk0pdt"] {
                            p.document["source"]["legacy"][key] = json!(0.0);
                        }
                    }
                } else {
                    if ![
                        "AlphaKT",
                        "LinearThermalPressure",
                        "LogVolumeThermalPressure",
                        "SecondOrderTaylorThermalPressure",
                    ]
                    .contains(&kind)
                    {
                        if material_number(p, "zc").is_none() {
                            p.document["formula_units_per_cell"] = json!(1);
                        }
                        if material_number(p, "n").is_none() {
                            record_mut(p)?["eos"]["parameters"]["n"] = json!(1.0);
                        }
                    }
                    let parameters = thermal_defaults(p, kind)?;
                    let model = &schema()["thermal"][kind]["model"];
                    let mut component = json!({"type":kind,"model":model,"parameters":parameters});
                    let choices: Vec<_> = component["parameters"]
                        .as_object()
                        .unwrap()
                        .iter()
                        .filter(|(_, v)| v.is_string())
                        .map(|(k, v)| (k.clone(), v.clone()))
                        .collect();
                    for (key, value) in choices {
                        component["parameters"]
                            .as_object_mut()
                            .unwrap()
                            .remove(&key);
                        component[&key] = value;
                    }
                    record_mut(p)?["thermal"] = component;
                }
                mark_record(p);
            }
            "editor_thermal_parameter" => {
                p.require_editable()?;
                let r = record_mut(p)?;
                let kind = r["thermal"]["type"]
                    .as_str()
                    .ok_or("Choose a thermal model first.")?;
                let key = args["parameter"]
                    .as_str()
                    .ok_or("Choose a thermal parameter.")?;
                let field = schema()["thermal"][kind]["fields"]
                    .as_array()
                    .and_then(|f| f.iter().find(|f| f["key"] == key))
                    .cloned()
                    .ok_or("Unknown thermal parameter.")?;
                if args["value"].is_null() {
                    if field["required"] == true {
                        return Err("This thermal coefficient is required.".into());
                    }
                    r["thermal"]["parameters"]
                        .as_object_mut()
                        .unwrap()
                        .remove(key);
                } else if field["choices"].as_array().is_some_and(|c| !c.is_empty()) {
                    if !field["choices"]
                        .as_array()
                        .unwrap()
                        .contains(&args["value"])
                    {
                        return Err("Unknown thermal configuration.".into());
                    }
                    r["thermal"]["parameters"]
                        .as_object_mut()
                        .unwrap()
                        .remove(key);
                    r["thermal"][key] = args["value"].clone();
                } else {
                    r["thermal"]["parameters"][key] =
                        json!(finite(&args["value"], key, -1e30, 1e30)?);
                }
                mark_record(p);
            }
            "editor_record" => {
                p.require_editable()?;
                let action = args["action"].as_str().ok_or("Choose a record action.")?;
                let current = p.reference;
                match action {
                    "add" | "duplicate" => {
                        let mut r = if action == "duplicate" {
                            current
                                .and_then(|i| phases::records(&p.document).get(i))
                                .cloned()
                                .ok_or("No EoS record to copy.")?
                        } else {
                            let mut record = current
                                .and_then(|i| phases::records(&p.document).get(i))
                                .cloned()
                                .unwrap_or_else(|| custom_record(p));
                            record["label"] = json!("Custom EoS");
                            record
                        };
                        let n = phases::records(&p.document).len();
                        let identifier = (1..)
                            .map(|suffix| format!("{}_record_{suffix}", p.uid))
                            .find(|id| {
                                !phases::records(&p.document)
                                    .iter()
                                    .any(|r| r["identifier"] == *id)
                            })
                            .unwrap();
                        r["identifier"] = json!(identifier);
                        r["default"] = json!(false);
                        r.as_object_mut().unwrap().remove("default_for");
                        r["scientific_validation"] = json!({"status":"deferred","note":"User-created record, not primary-source validated."});
                        p.document["eos_records"]
                            .as_array_mut()
                            .ok_or("Missing record array.")?
                            .push(r);
                        p.reference = Some(n);
                    }
                    "delete" => {
                        let i = current.ok_or("No selected EoS record.")?;
                        let identifier = phases::records(&p.document)[i]["identifier"]
                            .as_str()
                            .unwrap_or("");
                        if !identifier.is_empty()
                            && phases::records(&p.document)
                                .iter()
                                .enumerate()
                                .any(|(j, r)| {
                                    j != i
                                        && (r["derived_from_record"] == identifier
                                            || r["pressure_scale_variant_of"] == identifier)
                                })
                        {
                            return Err(
                                "Delete derived EoS records before their source record.".into()
                            );
                        }
                        p.document["eos_records"].as_array_mut().unwrap().remove(i);
                        p.reference = (!phases::records(&p.document).is_empty())
                            .then_some(i.min(phases::records(&p.document).len().saturating_sub(1)));
                    }
                    "clear" => {
                        p.document["eos_records"] = json!([]);
                        p.reference = None;
                    }
                    "default" => {
                        let i = current.ok_or("Select an EoS record.")?;
                        for (j, r) in p.document["eos_records"]
                            .as_array_mut()
                            .unwrap()
                            .iter_mut()
                            .enumerate()
                        {
                            r["default"] = json!(i == j);
                        }
                    }
                    "rename" => {
                        record_mut(p)?["label"] = json!(printable(&args["value"], "Record label")?)
                    }
                    _ => return Err("Unknown record action.".into()),
                }
            }
            "editor_ranges" => {
                p.require_editable()?;
                let r = record_mut(p)?;
                let ranges = args["ranges"]
                    .as_object()
                    .filter(|r| r.len() == 4)
                    .ok_or("Supply all four experimental and validity ranges.")?;
                for key in [
                    "experimental_pressure_range_gpa",
                    "experimental_temperature_range_k",
                    "pressure_gpa",
                    "temperature_k",
                ] {
                    let v = ranges.get(key).ok_or("Missing material range.")?;
                    let target = if key.starts_with("experimental_") {
                        &mut *r
                    } else {
                        if !r["validity"].is_object() {
                            r["validity"] = json!({});
                        }
                        &mut r["validity"]
                    };
                    if v.is_null() {
                        target.as_object_mut().unwrap().remove(key);
                    } else {
                        let a = v
                            .as_array()
                            .filter(|a| a.len() == 2)
                            .ok_or("A range needs a minimum and maximum, or neither.")?;
                        let low = if key.contains("temperature") {
                            0.0
                        } else {
                            -1e9
                        };
                        let x = finite(&a[0], key, low, 1e9)?;
                        let y = finite(&a[1], key, low, 1e9)?;
                        if x > y {
                            return Err("Range minimum exceeds its maximum.".into());
                        }
                        target[key] = json!([x, y]);
                    }
                }
                mark_record(p);
            }
            "editor_space_group" => {
                p.require_editable()?;
                let value = args["value"]
                    .as_str()
                    .map(str::to_string)
                    .unwrap_or_else(|| args["value"].to_string());
                let info = crystal::group(&value)?;
                p.document["space_group"] = json!(if value.parse::<i32>().is_ok() {
                    info.hall_symbol
                } else {
                    value
                });
                p.document["space_group_number"] = json!(info.number);
                p.document["symmetry"] =
                    json!(format!("{:?}", info.space_group.crystal_system()).to_uppercase());
                structure = true;
            }
            "editor_site" => {
                p.require_editable()?;
                let mut sites = p.document["atom_sites"]
                    .as_array()
                    .cloned()
                    .unwrap_or_default();
                match args["action"].as_str() {
                    Some("add") => {
                        let mut site = args["site"]
                            .as_object()
                            .cloned()
                            .ok_or("Supply an atomic site.")?;
                        if site
                            .keys()
                            .any(|k| !["element", "x", "y", "z", "occupancy"].contains(&k.as_str()))
                        {
                            return Err("Unknown atomic-site property.".into());
                        }
                        site.entry("occupancy").or_insert(json!(1.0));
                        sites.push(json!(site));
                    }
                    Some("remove") => {
                        let mut remove = vec![];
                        for v in args["rows"].as_array().ok_or("Select atomic sites.")? {
                            remove.push(integer(
                                v,
                                "Atomic site",
                                0,
                                sites.len().checked_sub(1).ok_or("No atomic sites.")?,
                            )?);
                        }
                        sites = sites
                            .into_iter()
                            .enumerate()
                            .filter_map(|(i, s)| (!remove.contains(&i)).then_some(s))
                            .collect();
                    }
                    Some("update") => {
                        let row = integer(
                            &args["row"],
                            "Atomic site",
                            0,
                            sites.len().checked_sub(1).ok_or("No atomic sites.")?,
                        )?;
                        let key = args["parameter"]
                            .as_str()
                            .filter(|k| ["element", "x", "y", "z", "occupancy"].contains(k))
                            .ok_or("Unknown atomic-site property.")?;
                        sites[row][key] = args["value"].clone();
                        sites[row].as_object_mut().unwrap().remove("type_symbol");
                    }
                    _ => return Err("Unknown atomic-site action.".into()),
                }
                for s in &mut sites {
                    let element = s["element"].as_str().ok_or("Choose an element.")?;
                    if phasesmith_crystallography::xray_species_metadata(
                        if ["D", "T"].contains(&element) {
                            "H"
                        } else {
                            element
                        },
                    )
                    .is_none()
                    {
                        return Err("Choose an element with X-ray scattering data.".into());
                    }
                    for key in ["x", "y", "z"] {
                        s[key] = json!(finite(&s[key], key, -1e9, 1e9)?.rem_euclid(1.0));
                    }
                    s["occupancy"] = json!(finite(&s["occupancy"], "Occupancy", 0.0, 1.0)?);
                }
                p.document["atom_sites"] = json!(sites);
                p.document["source"]["structure_modified"] = json!(true);
                structure = true;
            }
            _ => return Err("Unknown phase operation.".into()),
        }
        if op == "editor_record" && ["delete", "clear"].iter().any(|a| args["action"] == *a) {
            phases::repair_record_links(&mut p.document);
            if phases::records(&p.document).is_empty() {
                for key in ["k0", "k0p", "alphat", "dalphadt", "dk0dt", "dk0pdt"] {
                    p.document["source"]["legacy"][key] = json!(0.0);
                }
            }
        }
        if op != "update" {
            p.modified = true;
        }
        p.recalculate(wavelength, self.phases.cold_pressure, structure)?;
        if op == "update"
            && self.phases.same_conditions
            && (args.get("pressure").is_some() || args.get("temperature").is_some())
        {
            let (pressure, temperature) = (p.pressure, p.temperature);
            for other in &mut self.phases.items {
                let other = Arc::make_mut(other);
                other.pressure = pressure;
                other.temperature = temperature;
                other.recalculate(wavelength, self.phases.cold_pressure, false)?;
            }
        }
        Ok(Some(i))
    }
    fn phase_editor(&self, i: usize) -> Result<Value, String> {
        let p = &self.phases.items[i];
        let c = crystal::cell(&p.document)?;
        let v0 = p.reference_volume();
        let scale = (p.current_volume / v0).cbrt();
        let record = p
            .reference
            .and_then(|i| phases::records(&p.document).get(i))
            .cloned()
            .unwrap_or(Value::Null);
        let kind = record["eos"]["type"].as_str().unwrap_or("BM3");
        let thermal =
            if record["thermal"]["type"] == "AlphaKT" && record["thermal"]["model"].is_null() {
                ""
            } else {
                record["thermal"]["type"].as_str().unwrap_or("")
            };
        let metadata = schema();
        let fields:Vec<_>=metadata["eos"][kind].as_array().unwrap_or(&vec![]).iter().filter_map(|n|{let name=n.as_str()?;let key=match name{"K0"=>"k0","K0_prime"=>"k0p0","K0_double_prime"=>"k0pp0","P0"=>"p0","Z"=>"z",other=>other};Some(json!({"key":key,"label":name,"unit":if name=="K0"||name=="P0"{"GPa"}else{""},"value":record["eos"]["parameters"][name].as_f64().or_else(||p.document["source"]["legacy"][legacy_key(key)].as_f64()),"min":if name=="K0"{0.0}else{-1e6},"max":1e6,"integer":false}))}).collect();
        let mut thermal_fields: Vec<_> = metadata["thermal"][thermal]["fields"]
            .as_array()
            .unwrap_or(&vec![])
            .iter()
            .filter(|f| f["key"] != "n")
            .map(|f| {
                let mut f = f.clone();
                let key = f["key"].as_str().unwrap().to_string();
                f["value"] = record["thermal"]["parameters"]
                    .get(&key)
                    .or_else(|| record["thermal"].get(&key))
                    .or_else(|| record["thermal"]["configuration"].get(&key))
                    .unwrap_or(&f["default"])
                    .clone();
                f["isDefault"] = json!(record["thermal"]["parameters"].get(&key).is_none());
                f
            })
            .collect();
        if thermal.is_empty() {
            thermal_fields=[("alpha_t0","α(T₀)","K⁻¹",-1.0,1.0),("d_alpha_dt","dα/dT","K⁻²",-1.0,1.0),("dk0dt","dK₀/dT","GPa/K",-100.0,100.0),("dk0pdt","dK₀′/dT","K⁻¹",-100.0,100.0)].iter().map(|(key,label,unit,min,max)|json!({"key":key,"label":label,"unit":unit,"value":p.legacy_coefficients()[match *key{"alpha_t0"=>0,"d_alpha_dt"=>1,"dk0dt"=>2,_=>3}],"min":min,"max":max,"required":true})).collect();
        }
        let material_fields:Vec<_>=[("n","n","atoms/formula"),("z","Z electrons","e/formula"),("zc","Z cell","formula/cell")].iter().filter(|(key,_,_)|!fields.iter().any(|f|f["key"]==*key)).map(|(key,label,unit)|json!({"key":key,"label":label,"unit":unit,"value":material_number(p,key),"min":if *key=="zc"{1.0}else{1e-9},"max":1e6,"integer":*key=="zc"})).collect();
        static GROUPS: std::sync::OnceLock<Vec<Value>> = std::sync::OnceLock::new();
        let groups = if let Some(groups) = GROUPS.get() {
            groups
        } else {
            let groups: Vec<_> = (1..=230)
                .map(|n| {
                    phasesmith_io::space_group_by_number(n)
                        .map(|g| json!({"number":n,"symbol":g.hm_symbol}))
                        .map_err(|e| e.to_string())
                })
                .collect::<Result<_, _>>()?;
            let _ = GROUPS.set(groups);
            GROUPS.get().unwrap()
        };
        let (calculated_z, composition_status, composition_detail) =
            crate::phase_sites::composition(&p.document);
        let site_labels = crate::phase_sites::labels(&p.document);
        Ok(
            json!({"uid":p.uid,"index":i,"filename":p.filename,"editable":p.editable(),"eosEditable":p.editable(),"canReload":!p.filename.is_empty()&&Path::new(&p.filename).is_file(),"canSaveCurrent":p.editable()&&p.filename.to_lowercase().ends_with(".eosmat"),"copiedFrom":p.document["source"]["copied_from"]["phase_name"].as_str().unwrap_or(""),"materialName":p.name(),"name":p.display_name(),"pressure":p.pressure,"temperature":p.temperature,"coldPressure":self.phases.cold_pressure,"modified":p.modified,"origin":p.origin,"recordOrigin":p.origin,"recordLabel":record["label"].as_str().unwrap_or(""),"defaultReference":phases::default_reference(&p.document),"symmetry":p.document["symmetry"].as_str().unwrap_or("").to_lowercase(),"lattice":{"a0":c.a_angstrom,"b0":c.b_angstrom,"c0":c.c_angstrom,"alpha0":c.alpha_deg,"beta0":c.beta_deg,"gamma0":c.gamma_deg,"v0":v0,"a":c.a_angstrom*scale,"b":c.b_angstrom*scale,"c":c.c_angstrom*scale,"v":p.current_volume},"latticeEditable":lattice_keys(p.document["symmetry"].as_str().unwrap_or("")),"eosType":kind,"thermalType":thermal,"eosParameters":{},"eosFields":fields,"thermalFields":thermal_fields,"materialFields":material_fields,"recordData":record,"thermalSelection":if thermal.is_empty(){if p.legacy_coefficients().iter().any(|c|*c!=0.0){"alphakt"}else{"none"}}else{thermal},"eosOptions":metadata["eos"].as_object().unwrap().keys().map(|k|json!({"value":k,"error":compatibility(k,thermal,&record["thermal"]["parameters"])})).collect::<Vec<_>>(),"thermalOptions":(["none","alphakt"].into_iter().chain(metadata["thermal"].as_object().unwrap().keys().map(String::as_str)).map(|k|json!({"value":k,"error":compatibility(kind,k,&Value::Null)})).collect::<Vec<_>>()),"references":phases::reference_details(&p.document),"reference":p.reference.unwrap_or(0),"reflections":p.reflection_rows(self.settings.geometry.wavelength*1e10),"structure":{"spaceGroup":p.document["space_group"].as_str().unwrap_or(""),"spaceGroupNumber":p.document["space_group_number"],"siteWyckoff":site_labels,"elements":serde_json::from_str::<Value>(include_str!("../resources/elements.json")).expect("checked element metadata"),"groups":groups,"sites":p.document["atom_sites"].as_array().cloned().unwrap_or_default(),"formula":p.document["formula"].as_str().unwrap_or(""),"storedZ":p.document["formula_units_per_cell"],"calculatedZ":calculated_z,"compositionStatus":composition_status,"compositionDetail":composition_detail,"modified":p.document["source"]["structure_modified"]==true,"assumption":p.document["source"]["assumed_structure"]["note"].as_str().unwrap_or("")}}),
        )
    }
    fn phase_export(&mut self, args: &Value) -> Result<Reply, String> {
        let index = if args.get("index").is_some() || args.get("editor_uid").is_some() {
            Some(self.phases.resolve(args)?)
        } else {
            None
        };
        let file = if args["save_current"] == true {
            let i = index.ok_or("Select a material to save.")?;
            let p = &self.phases.items[i];
            p.require_editable()?;
            if !p.filename.ends_with(".eosmat") {
                return Err("Use Save As to choose an EOSMAT file.".into());
            }
            PathBuf::from(&p.filename)
        } else {
            path(args)?.to_path_buf()
        };
        let file = if file.extension().is_none() {
            file.with_extension(if args["format"] == "txt" {
                "txt"
            } else {
                "eosmat"
            })
        } else {
            file
        };
        let mut doc = if let Some(id) = args["material_id"].as_str() {
            phases::catalog()
                .iter()
                .find(|d| d["identifier"] == id)
                .cloned()
                .ok_or("Unknown database material.")?
        } else {
            self.phases.items[index.ok_or("Select a phase.")?]
                .document
                .clone()
        };
        if let Some(i) = index {
            let phase = &self.phases.items[i];
            if phases::records(&doc).is_empty()
                && doc["source"]["legacy"]["k0"]
                    .as_f64()
                    .is_some_and(|k| k > 0.0)
            {
                doc["eos_records"] = json!([custom_record(phase)]);
            }
            if let Some(reference) = phase
                .reference
                .or_else(|| (!phases::records(&doc).is_empty()).then_some(0))
            {
                let c = phase.legacy_coefficients();
                if c.iter().any(|c| *c != 0.0) && doc["eos_records"][reference]["thermal"].is_null()
                {
                    doc["eos_records"][reference]["thermal"] = json!({"type":"AlphaKT","parameters":{"Tr":298.15,"alpha0":c[0],"d_alpha_dT":c[1],"dK_dT":c[2],"dK_prime_dT":c[3]}});
                }
            }
        }
        let bytes = match file
            .extension()
            .unwrap_or_default()
            .to_string_lossy()
            .to_lowercase()
            .as_str()
        {
            "jcpds" => {
                let p = &self.phases.items[index.ok_or("Select a phase.")?];
                if !phases::records(&p.document).is_empty()
                    || p.document["atom_sites"]
                        .as_array()
                        .is_some_and(|s| !s.is_empty())
                {
                    return Err("JCPDS stores legacy BM3 peak tables and cannot retain this phase's EoS models, material records or atomic structure. Save as .eosmat instead.".into());
                }
                let mut text = format!(
                    "VERSION: 4\nCOMMENT: {}\nSYMMETRY: {}\n",
                    p.name(),
                    p.document["symmetry"].as_str().unwrap_or("CUBIC")
                );
                let c = crystal::cell(&p.document)?;
                for (k, v) in [
                    ("A", c.a_angstrom),
                    ("B", c.b_angstrom),
                    ("C", c.c_angstrom),
                    ("ALPHA", c.alpha_deg),
                    ("BETA", c.beta_deg),
                    ("GAMMA", c.gamma_deg),
                ] {
                    text.push_str(&format!("{k}: {v:.17e}\n"));
                }
                for key in ["k0", "k0p", "alphat", "dalphadt", "dk0dt", "dk0pdt"] {
                    text.push_str(&format!(
                        "{}: {:.17e}\n",
                        key.to_uppercase(),
                        p.document["source"]["legacy"][key]
                            .as_f64()
                            .unwrap_or(if key == "k0p" { 4.0 } else { 0.0 })
                    ));
                }
                for r in p.reflections.iter() {
                    text.push_str(&format!(
                        "DIHKL: {:.17e} {:.17e} {:.17e} {:.17e} {:.17e}\n",
                        r[3], r[4], r[0], r[1], r[2]
                    ));
                }
                text.into_bytes()
            }
            "eosmat" => {
                peritheos::eosmat::validate_eosmat_document(&phases::native_eos_document(&doc))
                    .map_err(|e| e.to_string())?;
                (serde_json::to_string_pretty(&doc).map_err(|e| e.to_string())? + "\n").into_bytes()
            }
            "txt" => {
                let p = &self.phases.items[index.ok_or("Select a phase.")?];
                let mut text = String::from(
                    "h\tk\tl\tIntensity\td0 (Å)\td (Å)\t2θ0 (°)\t2θ (°)\tQ0 (Å⁻¹)\tQ (Å⁻¹)\n",
                );
                for r in p
                    .reflection_rows(self.settings.geometry.wavelength * 1e10)
                    .as_array()
                    .unwrap()
                {
                    text.push_str(
                        &[
                            "h",
                            "k",
                            "l",
                            "intensity",
                            "d0",
                            "d",
                            "twoTheta0",
                            "twoTheta",
                            "q0",
                            "q",
                        ]
                        .iter()
                        .map(|k| r[*k].as_f64().map_or(String::new(), |v| format!("{v:.17}")))
                        .collect::<Vec<_>>()
                        .join("\t"),
                    );
                    text.push('\n');
                }
                text.into_bytes()
            }
            _ => return Err("Choose an EOSMAT material or TXT reflection table.".into()),
        };
        atomic_write(&file, &bytes)?;
        if let Some(i) = index
            && self.phases.items[i].editable()
            && file.extension().is_some_and(|s| s == "eosmat")
        {
            let p = Arc::make_mut(&mut self.phases.items[i]);
            p.filename = file.to_string_lossy().into_owned();
            p.modified = false;
        }
        self.revision += 1;
        let mut reply = if args["editor_only"] == true {
            Reply::metadata(json!({"ok":true}))
        } else {
            self.phase_response()
        };
        reply.result["savedPath"] = json!(file);
        if let Some(i) = index {
            reply.result["phaseEditor"] = self.phase_editor(i)?;
        }
        Ok(reply)
    }
    fn phase_list(&mut self, args: &Value) -> Result<Reply, String> {
        let file = path(args)?;
        if args["save"] == true {
            let mut writer = csv::WriterBuilder::new()
                .has_headers(false)
                .from_writer(Vec::new());
            for p in &self.phases.items {
                if !Path::new(&p.filename).is_file() {
                    return Err("Phase lists reference files on disk. Save each material before saving the list.".into());
                }
                writer
                    .write_record([
                        p.filename.clone(),
                        if p.visible { "True" } else { "False" }.into(),
                        p.color.clone(),
                        p.name().into(),
                        p.pressure.to_string(),
                        p.temperature.to_string(),
                    ])
                    .map_err(|e| e.to_string())?;
            }
            let bytes = writer.into_inner().map_err(|e| e.to_string())?;
            atomic_write(file, &bytes)?;
            return Ok(Reply::metadata(json!({"ok":true,"savedPath":file})));
        }
        let mut reader = csv::ReaderBuilder::new()
            .has_headers(false)
            .from_path(file)
            .map_err(|e| e.to_string())?;
        let minimum = self.phase_minimum();
        let wavelength = self.settings.geometry.wavelength * 1e10;
        for row in reader.records() {
            let row = row.map_err(|e| e.to_string())?;
            if row.len() != 6 {
                return Err("A phase list needs six columns.".into());
            }
            let filename = Path::new(&row[0]);
            let filename = if filename.is_absolute() {
                filename.to_path_buf()
            } else {
                file.parent().unwrap_or(Path::new(".")).join(filename)
            };
            let doc = phases::read_file(&filename)?;
            let same = self.phases.same_conditions;
            self.phases.same_conditions = false;
            let i = self.phases.add(
                doc,
                filename.to_string_lossy().into_owned(),
                "file",
                None,
                minimum,
                0.5,
                wavelength,
            )?;
            self.phases.same_conditions = same;
            let p = Arc::make_mut(&mut self.phases.items[i]);
            p.document["name"] = json!(&row[3]);
            p.color = crate::pattern::color(&json!(&row[2]))?;
            p.visible = match &row[1] {
                "True" | "1" => true,
                "False" | "0" => false,
                _ => return Err("Phase visibility must be True or False.".into()),
            };
            p.pressure = finite(
                &json!(row[4].parse::<f64>().map_err(|_| "Invalid pressure.")?),
                "Pressure",
                -9999999.0,
                9999999.0,
            )?;
            p.temperature = finite(
                &json!(row[5].parse::<f64>().map_err(|_| "Invalid temperature.")?),
                "Temperature",
                0.0,
                9999999.0,
            )?;
            p.recalculate(wavelength, self.phases.cold_pressure, false)?;
        }
        self.rebuild_pattern()?;
        self.revision += 1;
        Ok(self.phase_response())
    }
}
fn printable(v: &Value, name: &str) -> Result<String, String> {
    let text = v
        .as_str()
        .ok_or_else(|| format!("{name} needs printable text."))?
        .trim();
    if text.is_empty() || text.chars().count() > 250 || text.chars().any(char::is_control) {
        Err(format!("{name} needs 1–250 printable characters."))
    } else {
        Ok(text.into())
    }
}

fn ensure_record(p: &mut Phase) {
    if p.reference.is_none() {
        let r = custom_record(p);
        p.document["eos_records"] = json!([r]);
        p.reference = Some(0);
    }
}

#[cfg(all(test, feature = "dioptrin"))]
mod guide_tests {
    use super::*;

    fn call(s: &mut Session, action: &str, payload: Value) {
        let reply = s.invoke(&crate::protocol::Request {
            id: 1,
            action: action.into(),
            payload,
            cached_buffers: vec![],
        });
        assert_eq!(reply.result["ok"], true, "{}", reply.result);
    }

    // Compare against the preceding uncached algorithm, including exact point
    // order, source-pixel interpolation, reflection identity and line styling.
    fn check(s: &Session) -> Value {
        let image = s.image.as_ref().unwrap();
        let angles = s.native_geometry(image.shape).unwrap().calc_tth_all();
        let step = image.shape[0].max(image.shape[1]).div_ceil(512).max(1);
        let mut expected = vec![];
        for (i, p) in s.phases.items.iter().enumerate().filter(|(_, p)| p.visible) {
            let maximum = p.reflections.iter().map(|r| r[4]).fold(0.0, f64::max);
            let scale = (p.current_volume / p.reference_volume()).cbrt();
            for (j, r) in p.reflections.iter().enumerate() {
                let t = crate::pattern::convert_coordinate(
                    p.cell_spacing(r) * scale,
                    "d_A",
                    "2th_deg",
                    s.settings.geometry.wavelength,
                );
                if !t.is_finite() {
                    continue;
                }
                let paths = crate::contours::contours_at_step(
                    &angles,
                    image.shape,
                    &[(0, t.to_radians())],
                    step,
                );
                let intensity = if maximum > 0.0 { r[4] / maximum } else { 0.0 };
                for path in paths.as_array().unwrap() {
                    expected.push(json!({"ring":0,"twoTheta":t,"color":p.color,"points":path["points"],"phaseIndex":i,"reflectionIndex":j,"lineWidth":1.0+3.0*intensity,"opacity":0.3+0.4*intensity}));
                }
            }
        }
        let actual = s.phase_guides(&json!({})).unwrap().result["phaseGuides"].clone();
        assert_eq!(actual, json!(expected));
        let packed = s.phase_guides(&json!({"binary":true})).unwrap();
        assert_eq!(
            packed.result["phaseGuides"].as_array().unwrap().len(),
            actual.as_array().unwrap().len()
        );
        for (line, reference) in packed.result["phaseGuides"]
            .as_array()
            .unwrap()
            .iter()
            .zip(actual.as_array().unwrap())
        {
            let points = &line["points"];
            let buffer = packed
                .buffers
                .iter()
                .find(|b| b.id == points["bufferId"].as_str().unwrap())
                .unwrap();
            assert_eq!(
                buffer.bytes.len(),
                points["count"].as_u64().unwrap() as usize * 16
            );
            assert_eq!(
                points["length"].as_u64().unwrap() as usize,
                reference["points"].as_array().unwrap().len()
            );
            let offset = points["offset"].as_u64().unwrap() as usize * 16;
            for (i, pair) in reference["points"].as_array().unwrap().iter().enumerate() {
                for axis in 0..2 {
                    let at = offset + i * 16 + axis * 8;
                    let value = f64::from_le_bytes(buffer.bytes[at..at + 8].try_into().unwrap());
                    assert_eq!(value.to_bits(), pair[axis].as_f64().unwrap().to_bits());
                }
            }
            let mut metadata = line.clone();
            metadata["points"] = reference["points"].clone();
            assert_eq!(&metadata, reference);
        }
        actual
    }

    #[test]
    fn shared_phase_levels_match_legacy_for_individual_and_all_phase_edits() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
        let mut s = Session::new(root.clone());
        call(
            &mut s,
            "integration_settings",
            json!({"bins":128,"cake_bins":36}),
        );
        call(
            &mut s,
            "integration_phase",
            json!({"operation":"same_conditions","enabled":false}),
        );
        call(
            &mut s,
            "open_calibration",
            json!({"path":root.join("dioptas/tests/data/CeO2_Pilatus1M.poni")}),
        );
        call(
            &mut s,
            "open_image",
            json!({"path":root.join("dioptas/tests/data/CeO2_Pilatus1M.tif")}),
        );
        for index in 0..10 {
            let name = ["mo.jcpds", "au_version3.jcpds", "pt.jcpds"][index % 3];
            call(
                &mut s,
                "integration_phase",
                json!({"operation":"load","path":root.join("dioptas/tests/data/jcpds").join(name)}),
            );
            let a0 = crystal::cell(&s.phases.items[index].document)
                .unwrap()
                .a_angstrom;
            call(
                &mut s,
                "integration_phase",
                json!({"operation":"parameter","index":index,"parameter":"a0","value":a0*(1.+index as f64*0.002)}),
            );
        }
        let original = check(&s);
        assert_eq!(check(&s), original);
        let packed = s.phase_guides(&json!({"binary":true})).unwrap();
        let known: Vec<_> = packed.buffers.iter().map(|b| b.id.clone()).collect();
        let warm = s.phase_guides(&json!({"binary":true})).unwrap();
        for (a, b) in packed.buffers.iter().zip(&warm.buffers) {
            assert!(Arc::ptr_eq(&a.bytes, &b.bytes));
        }
        let packet = warm.encode(1, &known).unwrap();
        let length = u32::from_le_bytes(packet[..4].try_into().unwrap()) as usize;
        assert_eq!(
            packet.len(),
            4 + length,
            "Unchanged phases transfer metadata only"
        );
        call(
            &mut s,
            "integration_phase",
            json!({"operation":"update","index":0,"pressure":12.0}),
        );
        let changed = check(&s);
        assert_ne!(changed, original);
        let unchanged = |v: &Value| {
            v.as_array()
                .unwrap()
                .iter()
                .filter(|g| g["phaseIndex"] != 0)
                .cloned()
                .collect::<Vec<_>>()
        };
        assert_eq!(unchanged(&changed), unchanged(&original));
        let packed = s.phase_guides(&json!({"binary":true})).unwrap();
        let packet = packed.encode(1, &known).unwrap();
        let length = u32::from_le_bytes(packet[..4].try_into().unwrap()) as usize;
        let header: Value = serde_json::from_slice(&packet[4..4 + length]).unwrap();
        assert_eq!(
            header["buffers"].as_array().unwrap().len(),
            1,
            "Only the edited phase transfers new coordinates"
        );
        call(
            &mut s,
            "integration_phase",
            json!({"operation":"same_conditions","enabled":true}),
        );
        call(
            &mut s,
            "integration_phase",
            json!({"operation":"update","index":0,"pressure":15.0}),
        );
        let all = check(&s);
        assert_ne!(unchanged(&all), unchanged(&original));
        call(
            &mut s,
            "integration_phase",
            json!({"operation":"update","index":2,"visible":false}),
        );
        assert!(
            check(&s)
                .as_array()
                .unwrap()
                .iter()
                .all(|g| g["phaseIndex"] != 2)
        );
        // Identical angles share geometry but keep their own phase identity and
        // styling in the reply.
        s.phases.items.push(s.phases.items[0].clone());
        check(&s);
    }

    #[test]
    fn detector_guides_reuse_samples_and_follow_phase_geometry_and_shape_changes() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
        let mut s = Session::new(root.clone());
        call(
            &mut s,
            "integration_settings",
            json!({"bins":128,"cake_bins":36}),
        );
        call(
            &mut s,
            "open_calibration",
            json!({"path":root.join("dioptas/tests/data/CeO2_Pilatus1M.poni")}),
        );
        call(
            &mut s,
            "open_image",
            json!({"path":root.join("dioptas/tests/data/CeO2_Pilatus1M.tif")}),
        );
        call(
            &mut s,
            "integration_phase",
            json!({"operation":"load","path":root.join("dioptas/tests/data/jcpds/mo.jcpds")}),
        );
        let original = check(&s);
        assert!(!original.as_array().unwrap().is_empty());
        assert_eq!(check(&s), original);
        for payload in [
            json!({"operation":"update","index":0,"pressure":12.0}),
            json!({"operation":"update","index":0,"temperature":600.0}),
            json!({"operation":"parameter","index":0,"parameter":"a0","value":3.2}),
            json!({"operation":"parameter","index":0,"parameter":"k0","value":280.0}),
            json!({"operation":"update","index":0,"color":"#123456"}),
        ] {
            call(&mut s, "integration_phase", payload);
            assert_ne!(check(&s), original);
            assert!(
                s.phase_guide_field
                    .borrow()
                    .as_ref()
                    .unwrap()
                    .contours
                    .len()
                    <= s.phases.items[0].reflections.len()
            );
        }
        call(&mut s, "undo_calibration", json!({}));
        check(&s);
        call(&mut s, "redo_calibration", json!({}));
        check(&s);

        // Exercise the guide cache's geometry and shape keys directly without
        // invoking unrelated image reintegration or size-confirmation dialogs.
        s.settings.geometry.rot1 += 0.03;
        let rotated = check(&s);
        assert_ne!(rotated, original);
        s.settings.geometry.detector = None;
        s.image.as_mut().unwrap().shape = [620, 550];
        let resized = check(&s);
        assert_ne!(resized, rotated);
        let cache = s.phase_guide_field.borrow();
        assert_eq!(cache.as_ref().unwrap().shape, [620, 550]);
    }
}
