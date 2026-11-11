//! Native phase state. Authored documents retain their source qualifications.
use crate::phase_crystal as crystal;
use serde_json::{Value, json};
use std::{
    path::Path,
    sync::{Arc, OnceLock},
};
#[derive(Clone, PartialEq, serde::Serialize, serde::Deserialize)]
pub(crate) struct Phase {
    pub uid: String,
    pub document: Value,
    pub filename: String,
    pub origin: String,
    pub pressure: f64,
    pub temperature: f64,
    pub visible: bool,
    pub color: String,
    pub reference: Option<usize>,
    pub modified: bool,
    #[serde(with = "crate::history_transfer::arc")]
    pub reflections: Arc<Vec<[f64; 5]>>,
    pub minimum: f64,
    pub cutoff: f64,
    pub current_volume: f64,
    #[serde(skip)]
    pub eos_cache: Option<Arc<peritheos::Material>>,
}
#[derive(Clone, PartialEq, serde::Serialize, serde::Deserialize)]
pub(crate) struct Phases {
    #[serde(with = "crate::history_transfer::vec_arc")]
    pub items: Vec<Arc<Phase>>,
    pub same_conditions: bool,
    pub cold_pressure: bool,
    #[serde(default)]
    pub dac_fraction: crate::phase_dac::DacFraction,
    pub next_uid: u64,
}
impl Default for Phases {
    fn default() -> Self {
        Self {
            items: vec![],
            same_conditions: true,
            cold_pressure: false,
            dac_fraction: Default::default(),
            next_uid: 1,
        }
    }
}
// Qt PhaseModel.add_jcpds_object uses calculate_color(counter + 9):
// HelperModule.py sets hue = (0.19 * (index + 2)) % 1, s = v = 0.8.
// PhaseController converts RGB to hex by truncating each channel to an integer.
fn initial_color(index: u64) -> String {
    let hue = (0.19 * (index as f64 + 11.0)).fract() * 6.0;
    let sector = hue.floor() as u8;
    let fraction = hue - hue.floor();
    let value = 0.8;
    let saturation = 0.8;
    let p = value * (1.0 - saturation);
    let q = value * (1.0 - saturation * fraction);
    let t = value * (1.0 - saturation * (1.0 - fraction));
    let (r, g, b) = match sector {
        0 => (value, t, p),
        1 => (q, value, p),
        2 => (p, value, t),
        3 => (p, q, value),
        4 => (t, p, value),
        _ => (value, p, q),
    };
    format!(
        "#{:02x}{:02x}{:02x}",
        (r * 255.0) as u8,
        (g * 255.0) as u8,
        (b * 255.0) as u8
    )
}

#[cfg(test)]
mod color_tests {
    #[test]
    fn initial_colors_match_qt_phase_model_and_hex_conversion() {
        let expected = [
            "#cc8028", "#5dcc28", "#28ccae", "#282fcc", "#cc28bb", "#cc4f28", "#8dcc28", "#28cc7d",
            "#2860cc", "#ab28cc", "#cc2832", "#becc28",
        ];
        for (index, color) in expected.iter().enumerate() {
            assert_eq!(super::initial_color(index as u64), *color);
        }
    }
}

pub(crate) fn catalog() -> &'static Vec<Value> {
    static C: OnceLock<Vec<Value>> = OnceLock::new();
    C.get_or_init(|| {
        let mut v: Vec<Value> =
            serde_json::from_str(include_str!("../resources/peritheos/materials.json"))
                .expect("checked core material snapshot");
        v.sort_by_key(|d| d["name"].as_str().unwrap_or("").to_lowercase());
        v
    })
}
pub(crate) fn search(query: &str) -> Vec<&'static Value> {
    let text = query.to_lowercase();
    let composition = crate::phase_sites::formula(query)
        .ok()
        .filter(|c| !c.is_empty());
    let mut hits = Vec::new();
    for (index, doc) in catalog().iter().enumerate() {
        let name = doc["name"].as_str().unwrap_or("").to_lowercase();
        let formula = doc["formula"].as_str().unwrap_or("");
        let aliases: Vec<_> = doc["aliases"]
            .as_array()
            .into_iter()
            .flatten()
            .filter_map(Value::as_str)
            .map(str::to_lowercase)
            .collect();
        let formula_rank = composition.as_ref().and_then(|q| {
            let m = crate::phase_sites::formula(formula).ok()?;
            if q.keys().ne(m.keys()) {
                return (q.len() >= 2 && q.keys().all(|k| m.contains_key(k))).then_some(6);
            }
            let qt: f64 = q.values().sum();
            let mt: f64 = m.values().sum();
            Some(
                if q.iter().all(|(k, v)| {
                    let (a, b) = (v / qt, m[k] / mt);
                    (a - b).abs() <= 1e-12 + 1e-9 * a.abs().max(b.abs())
                }) {
                    2
                } else {
                    5
                },
            )
        });
        let strings: Vec<_> = std::iter::once(name.as_str())
            .chain(std::iter::once(formula))
            .chain(aliases.iter().map(String::as_str))
            .map(str::to_lowercase)
            .collect();
        let rank = if text.is_empty() || text == formula.to_lowercase() && !formula.is_empty() {
            Some(0)
        } else if text == name || aliases.contains(&text) {
            Some(1)
        } else if formula_rank == Some(2) {
            formula_rank
        } else if strings.iter().any(|s| s.starts_with(&text)) {
            Some(3)
        } else if strings.iter().any(|s| s.contains(&text)) {
            Some(4)
        } else {
            formula_rank
        };
        if let Some(rank) = rank {
            hits.push((rank, index, doc));
        }
    }
    hits.sort_by_key(|(rank, index, _)| (*rank, *index));
    hits.into_iter().map(|(_, _, doc)| doc).collect()
}
pub(crate) fn working_document(doc: Value) -> Result<Value, String> {
    if doc["format_version"].as_u64() == Some(4) {
        peritheos::eosmat::export_eosmat_v3(&doc).map_err(|e| e.to_string())
    } else {
        Ok(doc)
    }
}
pub(crate) fn records(doc: &Value) -> &[Value] {
    doc["eos_records"].as_array().map_or(&[], Vec::as_slice)
}
pub(crate) fn native_eos_document(doc: &Value) -> Value {
    let mut doc = doc.clone();
    if let Some(records) = doc["eos_records"].as_array_mut() {
        for r in records {
            if r["thermal"]["type"] == "AlphaKT" && r["thermal"]["model"].is_null() {
                r.as_object_mut().unwrap().remove("thermal");
                if r.get("equation_kind").is_some() {
                    r["equation_kind"] = json!("isothermal");
                }
            } else if let Some(thermal) = r.get_mut("thermal").and_then(Value::as_object_mut) {
                // Python constructor metadata keeps choice strings beside numeric
                // parameters. Peritheos Rust dispatch reads them on the component.
                let choices: Vec<_> = thermal
                    .get("parameters")
                    .and_then(Value::as_object)
                    .into_iter()
                    .flatten()
                    .filter(|(_, v)| v.is_string())
                    .map(|(k, v)| (k.clone(), v.clone()))
                    .collect();
                for (key, value) in choices {
                    thermal
                        .get_mut("parameters")
                        .unwrap()
                        .as_object_mut()
                        .unwrap()
                        .remove(&key);
                    thermal.insert(key, value);
                }
            }
        }
    }
    doc
}
pub(crate) fn repair_record_links(doc: &mut Value) {
    let live: std::collections::BTreeSet<_> = records(doc)
        .iter()
        .filter_map(|r| r["identifier"].as_str().map(str::to_string))
        .collect();
    if let Some(datasets) = doc.get_mut("datasets").and_then(Value::as_array_mut) {
        datasets.retain_mut(|dataset| {
            let previously_linked = dataset["used_by_eos_records"]
                .as_array()
                .is_some_and(|a| !a.is_empty())
                || dataset["observation_views"]
                    .as_array()
                    .is_some_and(|a| !a.is_empty());
            if let Some(ids) = dataset
                .get_mut("used_by_eos_records")
                .and_then(Value::as_array_mut)
            {
                ids.retain(|id| id.as_str().is_some_and(|id| live.contains(id)));
            }
            if let Some(reductions) = dataset
                .get_mut("pressure_reductions")
                .and_then(Value::as_array_mut)
            {
                reductions.retain(|r| r["eos_record"].as_str().is_some_and(|id| live.contains(id)));
            }
            if let Some(views) = dataset
                .get_mut("observation_views")
                .and_then(Value::as_array_mut)
            {
                views.retain_mut(|view| {
                    if let Some(ids) = view.get_mut("eos_records").and_then(Value::as_array_mut) {
                        ids.retain(|id| id.as_str().is_some_and(|id| live.contains(id)));
                        !ids.is_empty()
                    } else {
                        false
                    }
                });
            }
            !previously_linked
                || dataset["used_by_eos_records"]
                    .as_array()
                    .is_some_and(|a| !a.is_empty())
                || dataset["observation_views"]
                    .as_array()
                    .is_some_and(|a| !a.is_empty())
        });
    }
}
fn explicitly_selected(r: &Value) -> bool {
    r["catalog_access"] == "explicit_selection"
        || r["scientific_validation"]["usage_recommendation"]
            .as_str()
            .is_some_and(|s| s.starts_with("not_recommended") || s.starts_with("on_hold"))
        || r["reproduction"]["do_not_use"] == true
}
pub(crate) fn default_reference(doc: &Value) -> Option<usize> {
    if doc["recommendation_hold"]["status"] == "on_hold" {
        return None;
    }
    let records = records(doc);
    let preferred = records
        .iter()
        .position(|r| {
            r["default_for"] == "equilibrium"
                || (r["default"] == true && r["equation_kind"] != "hugoniot")
        })
        .or_else(|| {
            records
                .iter()
                .position(|r| r["default"] == true || !r["default_for"].is_null())
        });
    if let Some(i) = preferred {
        (!explicitly_selected(&records[i])).then_some(i)
    } else {
        records.iter().position(|r| !explicitly_selected(r))
    }
}
pub(crate) fn load_error(doc: &Value, reference: Option<usize>) -> String {
    if crystal::cell(doc).is_err()
        || (doc["atom_sites"].as_array().is_none_or(Vec::is_empty)
            && doc["peaks"].as_array().is_none_or(Vec::is_empty))
    {
        return "No crystal structure or reference peak table is available for diffraction phase lines.".into();
    }
    if !records(doc).is_empty() {
        let Some(r) = reference.and_then(|i| records(doc).get(i)) else {
            return doc["recommendation_hold"]
                .as_str()
                .unwrap_or("Select an EoS record explicitly; no automatic default is recommended.")
                .into();
        };
        if doc["format"] == "peritheos.material"
            && r["scientific_validation"]["status"] != "primary_source_validated"
            && !explicitly_selected(r)
        {
            return format!(
                "This record is {} and is retained as source data only.",
                r["scientific_validation"]["status"]
                    .as_str()
                    .unwrap_or("unvalidated")
            );
        }
    }
    String::new()
}
pub(crate) fn label(r: &Value) -> String {
    r["label"]
        .as_str()
        .or_else(|| r["identifier"].as_str())
        .unwrap_or("EoS")
        .into()
}
pub(crate) fn can_assume(doc: &Value) -> bool {
    let id = doc["identifier"].as_str().unwrap_or("");
    ["casio3_perovskite_tetragonal", "ca_perovskite_tetragonal"].contains(&id)
        && doc["formula"] == "CaSiO3"
        && doc["symmetry"] == "TETRAGONAL"
        && doc["formula_units_per_cell"].as_f64()
            == Some(if id == "casio3_perovskite_tetragonal" {
                1.0
            } else {
                4.0
            })
        && doc["atom_sites"].as_array().is_none_or(Vec::is_empty)
        && doc["peaks"].as_array().is_none_or(Vec::is_empty)
}
pub(crate) fn assumed_document(mut doc: Value) -> Result<Value, String> {
    if !can_assume(&doc) {
        return Err("No tetragonal perovskite approximation is available.".into());
    }
    let i = default_reference(&doc)
        .ok_or("An assumed structure needs an explicit reference volume.")?;
    let volume = records(&doc)[i]["eos"]["parameters"]["V0"]
        .as_f64()
        .filter(|v| *v > 0.0)
        .ok_or("An assumed structure needs a positive EOS reference volume.")?;
    let original = json!({"lattice":doc["lattice"],"space_group":doc["space_group"],"space_group_number":doc["space_group_number"],"atom_sites":doc["atom_sites"],"peaks":doc["peaks"]});
    let z = doc["formula_units_per_cell"].as_f64().unwrap();
    let (ratio, tilt, symbol, number, sites, reference, detail) = if z == 1.0 {
        (
            0.996,
            0.0,
            "P4/mmm",
            123,
            vec![
                ("Ca", [0.0, 0.0, 0.0]),
                ("Si", [0.5, 0.5, 0.5]),
                ("O", [0.5, 0.5, 0.0]),
                ("O", [0.5, 0.0, 0.5]),
            ],
            json!({"doi":"10.1029/2002GL016148","location":"paragraph 9; Figure 2","finding":"The c axis is approximately 0.4% shorter than a."}),
            "P4/mmm, Z=1, c/a=0.996; ideal perovskite sites without octahedral tilt.",
        )
    } else {
        let x = (1.0 - 8.0_f64.to_radians().tan()) / 4.0;
        (
            6.9677 / 4.8896,
            8.0,
            "I4/mcm",
            140,
            vec![
                ("Ca", [0.0, 0.5, 0.25]),
                ("Si", [0.0, 0.0, 0.0]),
                ("O", [0.0, 0.0, 0.25]),
                ("O", [x, x + 0.5, 0.0]),
            ],
            json!({"doi":"10.2138/am-2018-6087","location":"Table 1, first I4/mcm row","pressure_gpa":28.824,"a_angstrom":4.8896,"c_angstrom":6.9677,"tilt_deg":8.0}),
            "I4/mcm, Z=4; c/a and 8° tilt seeded from Chen (2018), Table 1 at 28.824 GPa; oxygen sites constructed from ideal perovskite geometry.",
        )
    };
    let a = (volume / ratio).cbrt();
    doc["lattice"] = json!({"a":a,"b":a,"c":a*ratio,"alpha":90.0,"beta":90.0,"gamma":90.0});
    doc["space_group"] = json!(symbol);
    doc["space_group_number"] = json!(number);
    doc["atom_sites"] = json!(
        sites
            .into_iter()
            .map(|(e, p)| json!({"element":e,"x":p[0],"y":p[1],"z":p[2],"occupancy":1.0}))
            .collect::<Vec<_>>()
    );
    doc["name"] = json!(format!(
        "{} (assumed structure)",
        doc["name"].as_str().unwrap_or("Material")
    ));
    let note = format!(
        "Assumed diffraction structure: {detail} The EOS sets the volume; c/a and fractional coordinates are held fixed with pressure and temperature. Intensities are approximate; this is not a refined structure."
    );
    doc["notes"] = json!(format!("{}\n\n{note}", doc["notes"].as_str().unwrap_or("")).trim());
    doc["source"]["assumed_structure"] = json!({"status":"assumed","note":note,"model":"tetragonal_perovskite","c_over_a":ratio,"tilt_deg":tilt,"normalize_to_eos_v0":true,"shape_reference":reference,"original_structure":original});
    Ok(doc)
}
pub(crate) fn reference_details(doc: &Value) -> Value {
    json!(records(doc).iter().enumerate().map(|(i,r)|{let data=crate::phase_references::catalog_record(doc,i,r);json!({"label":data["label"],"assessment":data["assessment"],"detail":data["detail"]})}).collect::<Vec<_>>())
}

impl Phases {
    #[allow(clippy::too_many_arguments)] // The existing import contract names these independent options.
    pub fn add(
        &mut self,
        mut document: Value,
        filename: String,
        origin: &str,
        reference: Option<usize>,
        minimum: f64,
        cutoff: f64,
        wavelength: f64,
    ) -> Result<usize, String> {
        document = working_document(document)?;
        let reference = reference.or_else(|| default_reference(&document));
        if !records(&document).is_empty() && reference.is_none() {
            return Err(load_error(&document, reference));
        }
        let i = self.items.len();
        let (pressure, temperature) = if self.same_conditions {
            self.items
                .first()
                .map_or((0.0, 298.0), |p| (p.pressure, p.temperature))
        } else {
            (0.0, 298.0)
        };
        let mut p = Phase {
            uid: format!("rust-phase-{}", self.next_uid),
            document,
            filename,
            origin: origin.into(),
            pressure,
            temperature,
            visible: true,
            color: initial_color(self.next_uid - 1),
            reference,
            modified: false,
            reflections: Arc::new(vec![]),
            minimum,
            cutoff,
            current_volume: 0.0,
            eos_cache: None,
        };
        if let Err(error) = p.recalculate(wavelength, self.effective_dac_fraction(), true) {
            let fallback = p
                .reference
                .and_then(|i| records(&p.document).get(i))
                .filter(|r| {
                    r["scientific_validation"]["status"] == "primary_source_validated"
                        && !r["thermal"].is_null()
                })
                .and_then(|r| {
                    r["experimental_pressure_range_gpa"][0]
                        .as_f64()
                        .zip(r["temperature_ref"].as_f64())
                });
            if let Some((pressure, temperature)) = fallback.filter(|_| p.pressure == 0.0) {
                p.pressure = pressure;
                p.temperature = temperature;
                p.recalculate(wavelength, self.effective_dac_fraction(), false)?;
            } else {
                return Err(error);
            }
        }
        self.next_uid += 1;
        self.items.push(Arc::new(p));
        Ok(i)
    }
    pub fn details(&self) -> Value {
        json!(self.items.iter().map(|p|json!({"uid":p.uid,"name":p.display_name(),"pressure":p.pressure,"temperature":p.temperature,"thermal":p.has_thermal(),"fileBacked":!p.filename.is_empty()&&Path::new(&p.filename).is_file(),"visible":p.visible,"color":p.color,"references":records(&p.document).iter().map(label).collect::<Vec<_>>(),"reference":p.reference.unwrap_or(0),"referenceDetails":reference_details(&p.document)})).collect::<Vec<_>>())
    }
    pub fn lines(&self, unit: &str, wavelength: f64) -> Value {
        json!(self.items.iter().enumerate().filter(|(_,p)|p.visible).flat_map(|(i,p)|{
            let scale=(p.current_volume/p.reference_volume()).cbrt();
            p.reflections.iter().filter_map(move |r|{let x=crate::pattern::convert_coordinate(p.cell_spacing(r)*scale,"d_A",unit,wavelength*1e-10); x.is_finite().then(||json!({"phaseIndex":i,"x":x,"intensity":r[4],"name":p.legend(self.cold_pressure),"color":p.color,"hkl":&r[..3]}))})
        }).collect::<Vec<_>>())
    }
    pub fn resolve(&self, args: &Value) -> Result<usize, String> {
        if let Some(uid) = args["editor_uid"].as_str() {
            return self.items.iter().position(|p| p.uid == uid).ok_or_else(|| {
                "This phase is no longer in the session. Select a phase in the main window.".into()
            });
        }
        args["index"]
            .as_u64()
            .and_then(|i| usize::try_from(i).ok())
            .filter(|&i| i < self.items.len())
            .ok_or_else(|| "Select a phase.".into())
    }
}
impl Phase {
    pub fn legacy_coefficients(&self) -> [f64; 4] {
        let r = self.reference.and_then(|i| records(&self.document).get(i));
        let old =
            r.filter(|r| r["thermal"]["type"] == "AlphaKT" && r["thermal"]["model"].is_null());
        [
            ("alphat", "alpha0"),
            ("dalphadt", "d_alpha_dT"),
            ("dk0dt", "dK_dT"),
            ("dk0pdt", "dK_prime_dT"),
        ]
        .map(|(key, alias)| {
            old.and_then(|r| r["thermal"]["parameters"][alias].as_f64())
                .or_else(|| self.document["source"]["legacy"][key].as_f64())
                .unwrap_or(0.0)
        })
    }
    pub fn reference_volume(&self) -> f64 {
        self.reference
            .and_then(|i| records(&self.document).get(i))
            .and_then(|r| r["eos"]["parameters"]["V0"].as_f64())
            .unwrap_or_else(|| crystal::volume(crystal::cell(&self.document).unwrap()).unwrap())
    }
    pub fn cell_spacing(&self, r: &[f64; 5]) -> f64 {
        let m = crystal::cell(&self.document)
            .unwrap()
            .geometry()
            .unwrap()
            .reciprocal_metric;
        let mut q = 0.0;
        for i in 0..3 {
            for j in 0..3 {
                q += r[i] * m[i][j] * r[j];
            }
        }
        q.sqrt().recip()
    }

    pub fn name(&self) -> &str {
        self.document["name"].as_str().unwrap_or("Phase")
    }
    pub fn display_name(&self) -> String {
        format!("{}{}", self.name(), if self.modified { "*" } else { "" })
    }
    fn legend(&self, cold: bool) -> String {
        format!(
            "{}{}{}",
            if cold {
                format!("P₀={:.2} GPa ", self.pressure)
            } else if self.pressure != 0.0 {
                format!("{:.2} GPa ", self.pressure)
            } else {
                String::new()
            },
            if ![0.0, 298.0].contains(&self.temperature) {
                format!("{:.2} K ", self.temperature)
            } else {
                String::new()
            },
            self.display_name()
        )
    }
    pub fn editable(&self) -> bool {
        self.origin != "bundled"
    }
    pub fn require_editable(&self) -> Result<(), String> {
        if self.editable() {
            Ok(())
        } else {
            Err("Bundled database materials are read-only. Choose Edit a copy before changing this material.".into())
        }
    }
    pub fn has_thermal(&self) -> bool {
        self.reference
            .and_then(|i| records(&self.document).get(i))
            .is_some_and(|r| {
                !r["thermal"].is_null()
                    && r["thermal"]["type"].as_str().is_some_and(|s| !s.is_empty())
                    && !(r["thermal"]["type"] == "AlphaKT" && r["thermal"]["model"].is_null())
            })
            || self.legacy_coefficients()[..2].iter().any(|a| *a != 0.0)
    }
    pub fn recalculate(
        &mut self,
        wavelength: f64,
        dac_fraction: Option<crate::phase_dac::DacFraction>,
        structure: bool,
    ) -> Result<(), String> {
        let c = crystal::cell(&self.document)?;
        let v0 = crystal::volume(c)?;
        if structure {
            self.reflections = Arc::new(crystal::reflections(
                &self.document,
                self.minimum,
                self.cutoff,
                wavelength,
            )?);
        }
        if self.document["source"]["assumed_structure"]["normalize_to_eos_v0"] == true {
            let reference = self.reference_volume();
            let factor = (reference / v0).cbrt();
            if (reference - v0).abs() > reference * 1e-12 {
                for axis in ["a", "b", "c"] {
                    let value = self.document["lattice"][axis].as_f64().unwrap() * factor;
                    self.document["lattice"][axis] = json!(value);
                }
                for row in Arc::make_mut(&mut self.reflections) {
                    row[3] *= factor;
                }
            }
        }
        let temperature = if self.temperature == 0.0 {
            298.0
        } else {
            self.temperature
        };
        self.current_volume = if let Some(index) = self.reference {
            let native_document = native_eos_document(&self.document);
            if self
                .eos_cache
                .as_ref()
                .is_none_or(|m| m.document != native_document)
            {
                self.eos_cache = Some(Arc::new(
                    peritheos::eosmat::material_from_value(native_document.clone())
                        .map_err(|e| e.to_string())?,
                ));
            }
            let material = self.eos_cache.as_ref().unwrap();
            let record = material
                .eos_records
                .get(index)
                .ok_or("Unknown EOS record.")?;
            if dac_fraction.is_some_and(|f| f64::from(f) != 0.0)
                && record.eos.is_thermal()
                && native_document["eos_records"][index]["thermal"].is_null()
            {
                return Err("DAC confinement is not supported for this thermal EoS model.".into());
            }
            let coefficients = self.legacy_coefficients();
            if self.pressure < 0.0
                || native_document["eos_records"][index]["thermal"].is_null()
                    && (self.pressure == 0.0 || coefficients.iter().any(|v| *v != 0.0))
            {
                let dt = temperature - 298.0;
                let alpha = coefficients[0] + coefficients[1] * dt;
                let k0 = native_document["eos_records"][index]["eos"]["parameters"]["K0"]
                    .as_f64()
                    .unwrap_or(0.0);
                if self.pressure == 0.0 {
                    record.reference_volume() * (1.0 + alpha * dt)
                } else if k0 <= 0.0 {
                    record.reference_volume()
                } else if self.pressure < 0.0 {
                    record.reference_volume() * (1.0 - self.pressure / k0)
                } else {
                    let mut document = native_document;
                    let params = &mut document["eos_records"][index]["eos"]["parameters"];
                    let k = k0 + coefficients[2] * dt;
                    params["K0"] = json!(k);
                    if let Some(kp) = params["K0_prime"].as_f64() {
                        params["K0_prime"] = json!(kp + coefficients[3] * dt);
                    }
                    let material = peritheos::eosmat::material_from_value(document)
                        .map_err(|e| e.to_string())?;
                    material.eos_records[index]
                        .volume(self.pressure - alpha * k * dt, 298.0)
                        .map_err(|e| e.to_string())?
                }
            } else {
                if let Some(fraction) =
                    dac_fraction.filter(|f| f64::from(*f) != 0.0 && self.has_thermal())
                {
                    record.volume_with_dac_confinement(self.pressure, temperature, fraction.into())
                } else {
                    record.volume(self.pressure, temperature)
                }
                .map_err(|e| e.to_string())?
            }
        } else {
            let l = &self.document["source"]["legacy"];
            let k0 = l["k0"].as_f64().unwrap_or(0.0);
            let kp = l["k0p"].as_f64().unwrap_or(4.0);
            let dt = temperature - 298.0;
            let alpha =
                l["alphat"].as_f64().unwrap_or(0.0) + l["dalphadt"].as_f64().unwrap_or(0.0) * dt;
            if self.pressure == 0.0 {
                v0 * (1.0 + alpha * dt)
            } else if k0 <= 0.0 {
                v0
            } else if self.pressure < 0.0 {
                v0 * (1.0 - self.pressure / k0)
            } else {
                use peritheos::IsothermalEos;
                let k = k0 + l["dk0dt"].as_f64().unwrap_or(0.0) * dt;
                let eos = peritheos::isothermal::BM3::new(
                    v0,
                    k,
                    kp + l["dk0pdt"].as_f64().unwrap_or(0.0) * dt,
                )
                .map_err(|e| e.to_string())?;
                eos.volume(self.pressure - alpha * k * dt)
                    .map_err(|e| e.to_string())?
            }
        };
        if !self.current_volume.is_finite() || self.current_volume <= 0.0 {
            return Err("Equation of state returned a non-physical volume.".into());
        }
        Ok(())
    }
    pub fn reflection_rows(&self, wavelength: f64) -> Value {
        let v0 = self.reference_volume();
        let scale = (self.current_volume / v0).cbrt();
        json!(self.reflections.iter().map(|r|{let d=self.cell_spacing(r)*scale;json!({"h":r[0],"k":r[1],"l":r[2],"intensity":r[4],"d0":r[3],"d":d,"twoTheta0":crate::pattern::convert_coordinate(r[3],"d_A","2th_deg",wavelength*1e-10),"twoTheta":crate::pattern::convert_coordinate(d,"d_A","2th_deg",wavelength*1e-10),"q0":std::f64::consts::TAU/r[3],"q":std::f64::consts::TAU/d})}).collect::<Vec<_>>())
    }
}
pub(crate) fn read_file(path: &Path) -> Result<Value, String> {
    if std::fs::metadata(path).map_err(|e| e.to_string())?.len() > 16 * 1024 * 1024 {
        return Err("Material file exceeds 16 MiB.".into());
    }
    match path
        .extension()
        .unwrap_or_default()
        .to_string_lossy()
        .to_lowercase()
        .as_str()
    {
        "eosmat" | "json" => {
            let doc: Value =
                serde_json::from_slice(&std::fs::read(path).map_err(|e| e.to_string())?)
                    .map_err(|e| e.to_string())?;
            let doc = working_document(doc)?;
            peritheos::eosmat::material_from_value(native_eos_document(&doc))
                .map_err(|e| e.to_string())?;
            Ok(doc)
        }
        "cif" => {
            let s = phasesmith_io::read_cif_file(path, None, false, Default::default())
                .map_err(|e| e.to_string())?
                .structure;
            let symbol = s
                .metadata
                .get("space_group_hm")
                .cloned()
                .unwrap_or_default();
            let mut doc = json!({"format_version":2,"name":s.name,"formula":s.metadata.get("chemical_formula_sum").cloned().unwrap_or_default(),"symmetry":format!("{:?}",s.space_group.crystal_system()).to_uppercase(),"space_group":symbol,"lattice":crystal::cell_json(s.cell),"atom_sites":s.sites.iter().map(|a|json!({"element":a.element_symbol,"label":a.source_label,"x":a.fractional_xyz[0],"y":a.fractional_xyz[1],"z":a.fractional_xyz[2],"occupancy":a.occupancy,"u_iso_angstrom2":a.u_iso_angstrom2,"u_aniso_cif_angstrom2":a.anisotropic_displacement.as_ref().map(|u|u.u_cif_angstrom2)})).collect::<Vec<_>>(),"peaks":[],"eos_records":[],"source":{"kind":"cif","text":std::fs::read_to_string(path).map_err(|e|e.to_string())?}});
            if doc["space_group"] == "" {
                if let Some(symbol) = s.metadata.get("space_group_hall") {
                    doc["space_group"] = json!(symbol);
                } else if let Some(number) = s.metadata.get("space_group_number") {
                    doc["space_group"] = json!(crystal::group(number)?.hm_symbol);
                } else {
                    // Exact CIF symmetry operations remain in source.text and are used by PhaseSmith.
                }
            }
            if let Some(number) = s
                .metadata
                .get("space_group_number")
                .and_then(|n| n.parse::<u32>().ok())
                .or_else(|| {
                    crystal::group(doc["space_group"].as_str().unwrap_or(""))
                        .ok()
                        .map(|g| g.number as u32)
                })
            {
                doc["space_group_number"] = json!(number);
            }
            if let Some(z) = s
                .metadata
                .get("formula_units_per_cell")
                .and_then(|v| v.parse::<f64>().ok())
                .filter(|v| v.is_finite() && *v > 0.0 && v.fract() == 0.0)
            {
                doc["formula_units_per_cell"] = json!(z as u64);
            }
            Ok(doc)
        }
        "jcpds" => read_jcpds(path),
        _ => Err("Choose a JCPDS, CIF or EOSMAT phase file.".into()),
    }
}
fn read_jcpds(path: &Path) -> Result<Value, String> {
    let text = std::fs::read_to_string(path).map_err(|e| e.to_string())?;
    let mut doc = json!({"format_version":2,"name":path.file_stem().unwrap_or_default().to_string_lossy(),"formula":"","symmetry":"CUBIC","lattice":{"a":1.0,"b":1.0,"c":1.0,"alpha":90.0,"beta":90.0,"gamma":90.0},"atom_sites":[],"space_group":"","peaks":[],"eos_records":[],"source":{"kind":"jcpds","text":text,"legacy":{"k0":0.0,"k0p":4.0}}});
    let lines: Vec<_> = text.lines().collect();
    let mut peaks = vec![];
    if lines.first().is_some_and(|l| l.trim() == "3") {
        let head = lines
            .get(2)
            .ok_or("Truncated JCPDS header.")?
            .split_whitespace()
            .collect::<Vec<_>>();
        if head.len() < 3 {
            return Err("Truncated JCPDS EOS.".into());
        }
        let symmetry = match head[0] {
            "1" => "CUBIC",
            "2" => "HEXAGONAL",
            "3" => "TETRAGONAL",
            "4" => "ORTHORHOMBIC",
            "5" => "MONOCLINIC",
            "6" => "TRICLINIC",
            _ => return Err("Unknown legacy JCPDS symmetry.".into()),
        };
        doc["symmetry"] = json!(symmetry);
        doc["name"] = json!(lines[1].trim());
        doc["source"]["legacy"]["k0"] = json!(head[1].parse::<f64>().map_err(|_| "Invalid K0.")?);
        doc["source"]["legacy"]["k0p"] =
            json!(head[2].parse::<f64>().map_err(|_| "Invalid K0 prime.")?);
        let lattice = lines
            .get(3)
            .ok_or("Missing JCPDS cell.")?
            .split_whitespace()
            .map(str::parse::<f64>)
            .collect::<Result<Vec<_>, _>>()
            .map_err(|_| "Invalid JCPDS cell.")?;
        for (key, value) in ["a", "b", "c", "alpha", "beta", "gamma"]
            .iter()
            .zip(lattice)
        {
            doc["lattice"][key] = json!(value);
        }
        for line in lines.iter().skip(6) {
            let p = line
                .split_whitespace()
                .map(str::parse::<f64>)
                .collect::<Result<Vec<_>, _>>()
                .map_err(|_| "Invalid reference peak.")?;
            if p.len() >= 5 {
                peaks.push(json!([p[2], p[3], p[4], p[0], p[1]]));
            }
        }
    } else {
        for line in &lines {
            let Some((key, value)) = line.split_once(':') else {
                continue;
            };
            let key = key.trim().to_lowercase();
            let value = value.trim();
            match key.as_str() {
                "comment" => {
                    doc["name"] = json!(value);
                }
                "symmetry" => doc["symmetry"] = json!(value.to_uppercase()),
                "a" | "b" | "c" | "alpha" | "beta" | "gamma" => {
                    doc["lattice"][&key] = json!(
                        value
                            .parse::<f64>()
                            .map_err(|_| "Invalid lattice parameter.")?
                    );
                }
                "dihkl" => {
                    let p = value
                        .split_whitespace()
                        .map(str::parse::<f64>)
                        .collect::<Result<Vec<_>, _>>()
                        .map_err(|_| "Invalid reference peak.")?;
                    if p.len() != 5 {
                        return Err("A reference peak needs d,I,h,k,l.".into());
                    }
                    peaks.push(json!([p[2], p[3], p[4], p[0], p[1]]));
                }
                "k0" | "k0p" | "dk0dt" | "dk0pdt" | "alphat" | "dalphadt" => {
                    doc["source"]["legacy"][key] = json!(
                        value
                            .parse::<f64>()
                            .map_err(|_| "Invalid legacy EOS coefficient.")?
                    );
                }
                _ => {}
            }
        }
    }
    crystal::constrain(&mut doc)?;
    if peaks.is_empty() {
        return Err("The phase contains no reference peaks.".into());
    }
    doc["peaks"] = json!(peaks);
    Ok(doc)
}
