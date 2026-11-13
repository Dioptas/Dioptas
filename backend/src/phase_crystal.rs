//! Dioptas powder-line adapter over the native PhaseSmith kernels.
use phasesmith_crystallography::*;
use phasesmith_io::{
    SpaceGroupInfo, space_group_by_hall_symbol, space_group_by_number, space_group_by_symbol,
};
use serde_json::{Value, json};
pub(crate) fn group(symbol: &str) -> Result<SpaceGroupInfo, String> {
    let symbol = match symbol {
        "P21/a" => "P 1 21/a 1",
        "P21/n" => "P 1 21/n 1",
        other => other,
    };
    if symbol == "F d -3 m:2" {
        return space_group_by_hall_symbol("-F 4vw 2vw 3").map_err(|e| e.to_string());
    }
    if let Ok(n) = symbol.parse::<i32>() {
        space_group_by_number(n)
    } else {
        space_group_by_symbol(symbol)
    }
    .map_err(|e| e.to_string())
}
pub(crate) fn cell(doc: &Value) -> Result<UnitCell, String> {
    let l = &doc["lattice"];
    let a = l["a"].as_f64().unwrap_or(0.0);
    let c = UnitCell {
        a_angstrom: a,
        b_angstrom: l["b"].as_f64().unwrap_or(a),
        c_angstrom: l["c"].as_f64().unwrap_or(a),
        alpha_deg: l["alpha"].as_f64().unwrap_or(90.0),
        beta_deg: l["beta"].as_f64().unwrap_or(90.0),
        gamma_deg: l["gamma"].as_f64().unwrap_or(90.0),
    };
    c.geometry().map_err(|e| e.to_string())?;
    Ok(c)
}
pub(crate) fn cell_json(c: UnitCell) -> Value {
    json!({"a":c.a_angstrom,"b":c.b_angstrom,"c":c.c_angstrom,"alpha":c.alpha_deg,"beta":c.beta_deg,"gamma":c.gamma_deg})
}
pub(crate) fn volume(c: UnitCell) -> Result<f64, String> {
    let [a, b, g] = [
        c.alpha_deg.to_radians(),
        c.beta_deg.to_radians(),
        c.gamma_deg.to_radians(),
    ];
    let v = c.a_angstrom
        * c.b_angstrom
        * c.c_angstrom
        * (1.0 + 2.0 * a.cos() * b.cos() * g.cos()
            - a.cos().powi(2)
            - b.cos().powi(2)
            - g.cos().powi(2))
        .sqrt();
    if v.is_finite() && v > 0.0 {
        Ok(v)
    } else {
        Err("Invalid crystal cell volume.".into())
    }
}
pub(crate) fn constrain(doc: &mut Value) -> Result<(), String> {
    let mut c = cell(doc)?;
    match doc["symmetry"]
        .as_str()
        .unwrap_or("")
        .to_uppercase()
        .as_str()
    {
        "CUBIC" => {
            c.b_angstrom = c.a_angstrom;
            c.c_angstrom = c.a_angstrom;
            c.alpha_deg = 90.0;
            c.beta_deg = 90.0;
            c.gamma_deg = 90.0;
        }
        "TETRAGONAL" => {
            c.b_angstrom = c.a_angstrom;
            c.alpha_deg = 90.0;
            c.beta_deg = 90.0;
            c.gamma_deg = 90.0;
        }
        "HEXAGONAL" | "TRIGONAL" => {
            c.b_angstrom = c.a_angstrom;
            c.alpha_deg = 90.0;
            c.beta_deg = 90.0;
            c.gamma_deg = 120.0;
        }
        "RHOMBOHEDRAL" => {
            c.b_angstrom = c.a_angstrom;
            c.c_angstrom = c.a_angstrom;
            c.beta_deg = c.alpha_deg;
            c.gamma_deg = c.alpha_deg;
        }
        "ORTHORHOMBIC" => {
            c.alpha_deg = 90.0;
            c.beta_deg = 90.0;
            c.gamma_deg = 90.0;
        }
        "MONOCLINIC" => {
            c.alpha_deg = 90.0;
            c.gamma_deg = 90.0;
        }
        "TRICLINIC" => {}
        _ => return Err("Unknown lattice symmetry.".into()),
    }
    c.geometry().map_err(|e| e.to_string())?;
    doc["lattice"] = cell_json(c);
    Ok(())
}
pub(crate) fn reflections(
    doc: &Value,
    minimum: f64,
    cutoff: f64,
    wavelength: f64,
) -> Result<Vec<[f64; 5]>, String> {
    let c = cell(doc)?;
    let sites = doc["atom_sites"].as_array().filter(|s| !s.is_empty());
    let cif = if doc["source"]["kind"] == "cif" && doc["source"]["structure_modified"] != true {
        doc["source"]["text"]
            .as_str()
            .map(|text| {
                phasesmith_io::parse_cif_text(text, None, false, Default::default())
                    .map(|r| r.structure)
                    .map_err(|e| e.to_string())
            })
            .transpose()?
    } else {
        None
    };
    if sites.is_none() || (cif.is_none() && doc["space_group"].as_str().unwrap_or("").is_empty()) {
        return doc["peaks"]
            .as_array()
            .unwrap_or(&vec![])
            .iter()
            .map(|p| {
                let p = p
                    .as_array()
                    .filter(|p| p.len() == 5)
                    .ok_or("A peak needs h,k,l,d,intensity.")?;
                let mut a = [0.0; 5];
                for (i, v) in p.iter().enumerate() {
                    a[i] = v.as_f64().ok_or("Invalid peak table number.")?;
                }
                if a[3] <= 0.0 || a[4] < 0.0 || a[..3] == [0.0; 3] {
                    return Err("Invalid reference peak.".into());
                }
                Ok(a)
            })
            .collect();
    }
    if minimum <= wavelength / 2.0 || !(0.0..100.0).contains(&cutoff) {
        return Err(
            "The reflection cutoff must exceed half the wavelength; intensity must be below 100%."
                .into(),
        );
    }
    let space_group = if let Some(cif) = &cif {
        cif.space_group.clone()
    } else {
        let info = group(doc["space_group"].as_str().unwrap())?;
        if doc["space_group_number"]
            .as_i64()
            .is_some_and(|n| n != info.number as i64)
        {
            return Err("Space-group symbol and stored number disagree.".into());
        }
        info.space_group
    };
    let generator = PreparedReflectionGenerator::new(space_group.clone(), true, 2_000_000)
        .map_err(|e| e.to_string())?;
    let generated = generator
        .generate(
            c,
            ReflectionRange::DSpacing {
                min_angstrom: minimum,
                max_angstrom: 100.0_f64
                    .max(10.0 * c.a_angstrom.max(c.b_angstrom).max(c.c_angstrom)),
            },
        )
        .map_err(|e| e.to_string())?;
    if generated.is_empty() {
        return Ok(vec![]);
    }
    let sites = sites.unwrap();
    if sites.len() > 4096 || generated.len().saturating_mul(sites.len()) > 16_000_000 {
        return Err("Reflection/atomic-site calculation exceeds the native resource limit.".into());
    }
    let species: Vec<_> = sites
        .iter()
        .map(|s| {
            let neutral = doc["source"]["kind"] == "cif";
            let e = if neutral {
                s["element"].as_str()
            } else {
                s["type_symbol"].as_str().or_else(|| s["element"].as_str())
            }
            .unwrap_or("");
            match e {
                "D" | "T" => "H".to_string(),
                _ => e.to_string(),
            }
        })
        .collect();
    let s: Vec<_> = generated
        .iter()
        .map(|r| 0.5 / r.d_spacing_angstrom)
        .collect();
    let scattering = PreparedXrayScattering::new(&species)
        .and_then(|p| p.evaluate(&s))
        .map_err(|e| e.to_string())?;
    let hkl: Vec<_> = generated.iter().map(|r| r.hkl).collect();
    let multiplicity: Vec<_> = generated.iter().map(|r| r.multiplicity).collect();
    let q: Vec<_> = generated
        .iter()
        .map(|r| r.reciprocal_length_inverse_angstrom.powi(2))
        .collect();
    let correction = IntegratedIntensityCorrectionModel::BraggBrentanoUnpolarizedLp {
        wavelength_angstrom: wavelength,
    }
    .evaluate(&q)
    .map_err(|e| e.to_string())?;
    let xyz: Vec<_> = sites
        .iter()
        .map(|s| {
            [
                s["x"].as_f64().unwrap_or(f64::NAN),
                s["y"].as_f64().unwrap_or(f64::NAN),
                s["z"].as_f64().unwrap_or(f64::NAN),
            ]
        })
        .collect();
    let occupancy: Vec<_> = sites
        .iter()
        .map(|s| s["occupancy"].as_f64().unwrap_or(1.0))
        .collect();
    let u: Vec<_> = sites
        .iter()
        .map(|s| s["u_iso_angstrom2"].as_f64().unwrap_or(0.0))
        .collect();
    let aniso: Vec<_> = sites
        .iter()
        .map(|s| {
            s["u_aniso_cif_angstrom2"]
                .as_array()
                .filter(|a| a.len() == 6)
                .map(|a| {
                    let mut u = [0.0; 6];
                    for (i, v) in a.iter().enumerate() {
                        u[i] = v.as_f64().unwrap_or(f64::NAN);
                    }
                    u
                })
        })
        .collect();
    let values = calculate_structure_factor_values(
        c,
        &space_group,
        StructureFactorBatchView {
            hkl: &hkl,
            multiplicity: &multiplicity,
            fractional_xyz: &xyz,
            occupancy: &occupancy,
            u_iso_angstrom2: &u,
            anisotropic_mask: &aniso.iter().map(Option::is_some).collect::<Vec<_>>(),
            u_aniso_cif_angstrom2: &aniso
                .iter()
                .map(|u| u.unwrap_or([0.0; 6]))
                .collect::<Vec<_>>(),
            scattering_real: &scattering.real,
            scattering_imag: &scattering.imag,
            d_scattering_real_d_s: &scattering.d_real_d_s,
            d_scattering_imag_d_s: &scattering.d_imag_d_s,
            correction: &correction.values,
            d_correction_d_q_squared: &correction.d_values_d_q_squared,
            scale: 1.0,
            coordinate_tolerance: 1e-10,
        },
    )
    .map_err(|e| e.to_string())?;
    let mut rows: Vec<[f64; 5]> = vec![];
    let mut angle = None;
    for (r, intensity) in generated.iter().zip(values.intensity) {
        let theta = 2.0
            * (wavelength / (2.0 * r.d_spacing_angstrom))
                .asin()
                .to_degrees();
        if angle.is_some_and(|a: f64| (theta - a).abs() < 1e-5) {
            rows.last_mut().unwrap()[4] += intensity;
        } else {
            let h = r.conventional_hkl;
            rows.push([
                h[0] as f64,
                h[1] as f64,
                h[2] as f64,
                r.d_spacing_angstrom,
                intensity,
            ]);
            angle = Some(theta);
        }
    }
    let max = rows.iter().map(|r| r[4]).fold(0.0, f64::max);
    if !max.is_finite() || max <= 0.0 {
        return Err("The structure produced no positive reflection intensities.".into());
    }
    for row in &mut rows {
        row[4] *= 100.0 / max;
    }
    rows.retain(|r| r[4] > cutoff);
    Ok(rows)
}
