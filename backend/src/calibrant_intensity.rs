//! PhaseSmith-backed CIF calibrant loader for Dioptas.
//! Built-in calibrants come directly from `dioptrin::calibration::Calibrant`.

use phasesmith_crystallography::{
    IntegratedIntensityCorrectionModel, PreparedReflectionGenerator, PreparedXrayScattering,
    ReflectionRange, SpaceGroup, StructureFactorBatchView, UnitCell,
    calculate_structure_factor_values,
};

struct SiteSpec<'a> {
    element: &'a str,
    xyz: [f64; 3],
    occupancy: f64,
    u_iso: f64,
    u_aniso: Option<[f64; 6]>,
}

fn calculate_powder_reflections(
    cell: UnitCell,
    space_group: &SpaceGroup,
    sites: &[SiteSpec<'_>],
    min_d_angstrom: f64,
    wavelength_angstrom: f64,
) -> Result<Vec<(f64, f64)>, String> {
    if sites.is_empty() {
        return Err("Calibrant CIF has no atomic sites.".into());
    }
    let wavelength = wavelength_angstrom.clamp(0.05, 10.0);
    let minimum = min_d_angstrom.max(wavelength / 2.0 + 1e-4);
    let generator = PreparedReflectionGenerator::new(space_group.clone(), true, 2_000_000)
        .map_err(|e| e.to_string())?;
    let generated = generator
        .generate(
            cell,
            ReflectionRange::DSpacing {
                min_angstrom: minimum,
                max_angstrom: 100.0_f64
                    .max(10.0 * cell.a_angstrom.max(cell.b_angstrom).max(cell.c_angstrom)),
            },
        )
        .map_err(|e| e.to_string())?;
    if generated.is_empty() {
        return Err("Calibrant structure produced no reflections in range.".into());
    }
    if sites.len() > 4096 || generated.len().saturating_mul(sites.len()) > 16_000_000 {
        return Err("Reflection/atomic-site calculation exceeds the native resource limit.".into());
    }
    let species: Vec<String> = sites
        .iter()
        .map(|s| match s.element {
            "D" | "T" => "H".to_string(),
            other => other.to_string(),
        })
        .collect();
    let s: Vec<f64> = generated
        .iter()
        .map(|r| 0.5 / r.d_spacing_angstrom)
        .collect();
    let scattering = PreparedXrayScattering::new(&species)
        .and_then(|p| p.evaluate(&s))
        .map_err(|e| e.to_string())?;
    let hkl: Vec<[i32; 3]> = generated.iter().map(|r| r.hkl).collect();
    let multiplicity: Vec<usize> = generated.iter().map(|r| r.multiplicity).collect();
    let q: Vec<f64> = generated
        .iter()
        .map(|r| r.reciprocal_length_inverse_angstrom.powi(2))
        .collect();
    let correction = IntegratedIntensityCorrectionModel::BraggBrentanoUnpolarizedLp {
        wavelength_angstrom: wavelength,
    }
    .evaluate(&q)
    .map_err(|e| e.to_string())?;
    let xyz: Vec<[f64; 3]> = sites.iter().map(|s| s.xyz).collect();
    let occupancy: Vec<f64> = sites.iter().map(|s| s.occupancy).collect();
    let u: Vec<f64> = sites.iter().map(|s| s.u_iso).collect();
    let aniso_mask: Vec<bool> = sites.iter().map(|s| s.u_aniso.is_some()).collect();
    let aniso_vals: Vec<[f64; 6]> = sites
        .iter()
        .map(|s| s.u_aniso.unwrap_or([0.0; 6]))
        .collect();
    let values = calculate_structure_factor_values(
        cell,
        space_group,
        StructureFactorBatchView {
            hkl: &hkl,
            multiplicity: &multiplicity,
            fractional_xyz: &xyz,
            occupancy: &occupancy,
            u_iso_angstrom2: &u,
            anisotropic_mask: &aniso_mask,
            u_aniso_cif_angstrom2: &aniso_vals,
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

    let mut pairs: Vec<(f64, f64)> = generated
        .iter()
        .zip(values.intensity)
        .filter(|(_, i)| i.is_finite() && *i > 0.0)
        .map(|(r, i)| (r.d_spacing_angstrom, i))
        .collect();
    pairs.sort_by(|a, b| b.0.total_cmp(&a.0));

    let mut grouped: Vec<(f64, f64)> = Vec::new();
    for (d, intensity) in pairs {
        if let Some(last) = grouped.last_mut()
            && (d - last.0).abs() < 1e-5
        {
            last.1 += intensity;
        } else {
            grouped.push((d, intensity));
        }
    }
    let max = grouped.iter().map(|(_, i)| *i).fold(0.0_f64, f64::max);
    if !max.is_finite() || max <= 0.0 {
        return Err("Calibrant structure produced no positive reflection intensities.".into());
    }
    for (_, intensity) in &mut grouped {
        *intensity /= max;
    }
    grouped.retain(|(_, i)| *i > 1e-4);
    Ok(grouped)
}

/// Parse a CIF file into `(d_spacings_angstrom, normalized_intensities)` using PhaseSmith.
pub(super) fn parse_cif(
    text: &str,
    wavelength_angstrom: f64,
) -> Result<(Vec<f64>, Vec<f64>), String> {
    let parsed = phasesmith_io::parse_cif_text(text, None, false, Default::default())
        .map_err(|e| format!("Invalid CIF calibrant: {e}"))?
        .structure;
    let sites: Vec<SiteSpec<'_>> = parsed
        .sites
        .iter()
        .map(|s| SiteSpec {
            element: s.element_symbol.as_str(),
            xyz: s.fractional_xyz,
            occupancy: s.occupancy,
            u_iso: s.u_iso_angstrom2.unwrap_or(0.0),
            u_aniso: s
                .anisotropic_displacement
                .as_ref()
                .map(|u| u.u_cif_angstrom2),
        })
        .collect();
    let min_d = (wavelength_angstrom / 2.0 + 1e-4).max(0.25);
    let mut grouped = calculate_powder_reflections(
        parsed.cell,
        &parsed.space_group,
        &sites,
        min_d,
        wavelength_angstrom,
    )?;
    if grouped.is_empty() {
        return Err("CIF calibrant produced no usable reflections.".into());
    }
    if grouped.len() > 10_000 {
        grouped.truncate(10_000);
    }
    let (spacings, intensities) = grouped.into_iter().unzip();
    Ok((spacings, intensities))
}
