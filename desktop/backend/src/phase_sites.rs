//! Derived Wyckoff labels and occupancy-weighted composition in the declared group.
use crate::phase_crystal;
use nalgebra::{Matrix3, Vector3};
use serde_json::{Value, json};
use std::{collections::BTreeMap, sync::OnceLock};
fn hall(s: &str) -> String {
    s.replace('=', "\"")
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
}
fn affine(text: &str) -> Result<(Matrix3<f64>, Vector3<f64>), String> {
    let mut linear = Matrix3::<f64>::zeros();
    let mut origin = Vector3::<f64>::zeros();
    let coordinates: Vec<_> = text.split(',').collect();
    if coordinates.len() != 3 {
        return Err("Invalid Wyckoff representative.".into());
    }
    for (row, expr) in coordinates.iter().enumerate() {
        let expr = expr.replace(' ', "").replace('-', "+-");
        for token in expr.split('+').filter(|t| !t.is_empty()) {
            if let Some(variable) = token.chars().last().filter(|c| "xyz".contains(*c)) {
                let prefix = &token[..token.len() - 1];
                let coefficient = if prefix.is_empty() {
                    1.0
                } else if prefix == "-" {
                    -1.0
                } else {
                    prefix
                        .parse::<f64>()
                        .map_err(|_| "Invalid affine coefficient.")?
                };
                linear[(row, "xyz".find(variable).unwrap())] += coefficient;
            } else {
                let value = if let Some((a, b)) = token.split_once('/') {
                    a.parse::<f64>().map_err(|_| "Invalid rational origin.")?
                        / b.parse::<f64>().map_err(|_| "Invalid rational origin.")?
                } else {
                    token.parse::<f64>().map_err(|_| "Invalid affine origin.")?
                };
                origin[row] += value;
            }
        }
    }
    let pinv = linear
        .svd(true, true)
        .pseudo_inverse(1e-15)
        .map_err(str::to_string)?;
    Ok((Matrix3::identity() - linear * pinv, origin))
}
pub(crate) fn labels(doc: &Value) -> Value {
    let sites = doc["atom_sites"].as_array().cloned().unwrap_or_default();
    let info = phase_crystal::group(doc["space_group"].as_str().unwrap_or(""));
    let Ok(info) = info else {
        return json!(sites.iter().map(|_|json!({"label":null,"multiplicity":null,"detail":"No declared space group."})).collect::<Vec<_>>());
    };
    static TABLE: OnceLock<Value> = OnceLock::new();
    let settings = &TABLE.get_or_init(|| {
        serde_json::from_str(include_str!(
            "../../../dioptas/resources/data/wyckoff/positions.json"
        ))
        .expect("checked Moyo Wyckoff snapshot")
    })["settings"];
    let candidates: Vec<_> = settings
        .as_array()
        .unwrap()
        .iter()
        .filter(|s| {
            s["number"] == info.number
                && s["hall"]
                    .as_str()
                    .is_some_and(|s| hall(s) == hall(&info.hall_symbol))
        })
        .collect();
    let setting = candidates
        .iter()
        .find(|s| s["setting"] == info.setting)
        .copied()
        .or_else(|| (candidates.len() == 1).then(|| candidates[0]));
    json!(sites.iter().map(|site|{
        let xyz=[site["x"].as_f64().unwrap_or(f64::NAN),site["y"].as_f64().unwrap_or(f64::NAN),site["z"].as_f64().unwrap_or(f64::NAN)];let orbit=info.space_group.expand_sites(&[xyz],1e-10);let Ok(orbit)=orbit else{return json!({"label":null,"multiplicity":null,"detail":"Invalid fractional coordinates."});};let multiplicity=orbit.fractional_xyz.len();
        if let Some(setting)=setting{for p in setting["positions"].as_array().unwrap(){if p[0].as_u64()!=Some(multiplicity as u64){continue;}let Ok((projection,origin))=affine(p[3].as_str().unwrap())else{continue;};let matches=orbit.fractional_xyz.iter().any(|point|(-2..=2).any(|a|(-2..=2).any(|b|(-2..=2).any(|c|{let delta=Vector3::new(point[0]+a as f64,point[1]+b as f64,point[2]+c as f64)-origin;(projection*delta).iter().all(|d|d.abs()<=1e-10)}))));if matches{return json!({"label":format!("{}{}",multiplicity,p[1].as_str().unwrap()),"multiplicity":multiplicity,"detail":format!("Calculated from {} (No. {}), Hall {}; site symmetry {}.",info.hm_symbol,info.number,info.hall_symbol,p[2].as_str().unwrap())});}}}
        json!({"label":null,"multiplicity":multiplicity,"detail":"No Wyckoff position matched in this explicit Hall setting at tolerance 1e-10."})
    }).collect::<Vec<_>>())
}
pub(crate) fn formula(text: &str) -> Result<BTreeMap<String, f64>, String> {
    let text = text
        .chars()
        .map(|c| {
            "₀₁₂₃₄₅₆₇₈₉"
                .chars()
                .position(|d| d == c)
                .map_or(c, |i| (b'0' + i as u8) as char)
        })
        .filter(|c| !c.is_whitespace())
        .collect::<String>();
    if text.len() > 4096 {
        return Err("Formula exceeds the supported size.".into());
    }
    fn amount(bytes: &[u8], i: &mut usize) -> Result<f64, String> {
        let start = *i;
        while bytes
            .get(*i)
            .is_some_and(|b| b.is_ascii_digit() || *b == b'.')
        {
            *i += 1;
        }
        if start == *i {
            return Ok(1.0);
        }
        let n = std::str::from_utf8(&bytes[start..*i])
            .unwrap()
            .parse::<f64>()
            .map_err(|_| "Invalid formula amount.")?;
        if !n.is_finite() || n <= 0.0 {
            return Err("Formula amounts must be positive and finite.".into());
        }
        Ok(n)
    }
    fn sequence(
        bytes: &[u8],
        i: &mut usize,
        closing: Option<u8>,
        depth: usize,
    ) -> Result<BTreeMap<String, f64>, String> {
        if depth > 16 {
            return Err("Formula nesting exceeds 16 levels.".into());
        }
        let mut out = BTreeMap::new();
        while *i < bytes.len() {
            let c = bytes[*i];
            if Some(c) == closing {
                *i += 1;
                return Ok(out);
            }
            let group = if c == b'(' || c == b'[' {
                *i += 1;
                sequence(
                    bytes,
                    i,
                    Some(if c == b'(' { b')' } else { b']' }),
                    depth + 1,
                )?
            } else {
                if !c.is_ascii_uppercase() {
                    return Err(
                        "Enter a chemical formula with element symbols and optional groups.".into(),
                    );
                }
                let start = *i;
                *i += 1;
                if bytes.get(*i).is_some_and(u8::is_ascii_lowercase) {
                    *i += 1;
                }
                let name = std::str::from_utf8(&bytes[start..*i]).unwrap();
                let name = if ["D", "T"].contains(&name) {
                    "H"
                } else {
                    name
                };
                if phasesmith_crystallography::xray_species_metadata(name).is_none() {
                    return Err("Unknown formula element.".into());
                }
                BTreeMap::from([(name.into(), 1.0)])
            };
            let n = amount(bytes, i)?;
            for (k, v) in group {
                *out.entry(k).or_insert(0.0) += v * n;
            }
        }
        if closing.is_some() {
            return Err("Unclosed chemical formula group.".into());
        }
        Ok(out)
    }
    let mut i = 0;
    let result = sequence(text.as_bytes(), &mut i, None, 0)?;
    if result.is_empty() {
        return Err("No chemical formula is declared.".into());
    }
    Ok(result)
}
pub(crate) fn composition(doc: &Value) -> (Option<f64>, String, String) {
    let result = (|| {
        let group = phase_crystal::group(
            doc["space_group"]
                .as_str()
                .ok_or("No space group available.")?,
        )?;
        let sites = doc["atom_sites"]
            .as_array()
            .filter(|s| !s.is_empty())
            .ok_or("No atomic sites available.")?;
        let mut counts: BTreeMap<String, f64> = BTreeMap::new();
        let mut orbits: Vec<(Vec<[f64; 3]>, f64)> = vec![];
        for site in sites {
            let xyz = [
                site["x"].as_f64().ok_or("Invalid site coordinate.")?,
                site["y"].as_f64().ok_or("Invalid site coordinate.")?,
                site["z"].as_f64().ok_or("Invalid site coordinate.")?,
            ];
            let occupancy = site["occupancy"].as_f64().unwrap_or(1.0);
            if !(0.0..=1.0).contains(&occupancy) {
                return Err("Site occupancy must be finite and between zero and one.".into());
            }
            let orbit = group
                .space_group
                .expand_sites(&[xyz], 1e-10)
                .map_err(|e| e.to_string())?
                .fractional_xyz;
            if occupancy == 0.0 {
                continue;
            }
            if let Some((_, total)) = orbits.iter_mut().find(|(o, _)| {
                o.iter().any(|p| {
                    p.iter().zip(orbit[0]).all(|(a, b)| {
                        let d = (a - b).abs();
                        d.min((1.0 - d).abs()) <= 1e-10
                    })
                })
            }) {
                *total += occupancy;
                if *total > 1.0 + 1e-8 {
                    return Err("Symmetry-equivalent site rows have total occupancy above one. Check duplicate sites or mixed occupancies.".into());
                }
            } else {
                orbits.push((orbit.clone(), occupancy));
            }
            let element = site["element"].as_str().ok_or("Missing site element.")?;
            let element = if ["D", "T"].contains(&element) {
                "H"
            } else {
                element
            };
            *counts.entry(element.into()).or_insert(0.0) += orbit.len() as f64 * occupancy;
        }
        if counts.is_empty() {
            return Err("All site occupancies are zero.".into());
        }
        let f = formula(doc["formula"].as_str().unwrap_or(""))?;
        if counts.keys().ne(f.keys()) {
            return Ok((
                None,
                "mismatch".into(),
                "Structure and formula contain different elements; no common Z.".into(),
            ));
        }
        let z = f.iter().map(|(k, v)| counts[k] / v).sum::<f64>() / f.len() as f64;
        let consistent = f
            .iter()
            .all(|(k, v)| (counts[k] - z * v).abs() <= 1e-8 + 1e-4 * (z * v).abs());
        let detail = format!(
            "{}\nAtoms per cell: {}\nAtoms per formula: {}\nCell counts use symmetry multiplicity × occupancy. Formula tolerance: 0.01% relative, 1e-8 atoms absolute. Stored Z and EoS parameters are retained.",
            if consistent {
                "The occupancy-weighted cell composition matches the chemical formula."
            } else {
                "Element ratios disagree; no single Z matches the chemical formula."
            },
            counts
                .iter()
                .map(|(k, v)| format!("{k}: {v}"))
                .collect::<Vec<_>>()
                .join(", "),
            f.iter()
                .map(|(k, v)| format!("{k}: {v}"))
                .collect::<Vec<_>>()
                .join(", ")
        );
        Ok((
            consistent.then_some(z),
            if consistent { "consistent" } else { "mismatch" }.into(),
            detail,
        ))
    })();
    result.unwrap_or_else(|e: String| (None, "unavailable".into(), e))
}
