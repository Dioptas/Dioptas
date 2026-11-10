//! Qt rectangle slicing over the owned Batch matrix; no integration/resampling.
use crate::{control::Control, pattern::Curve, series::Series};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::sync::Arc;

#[derive(Clone, PartialEq, Serialize, Deserialize)]
pub(crate) struct Source {
    pub series: String,
    pub row: usize,
    pub path: String,
    pub frame: usize,
    pub bins: [usize; 2],
    pub unit: String,
    pub wavelength: Option<f64>,
    pub normalized: bool,
}
impl Source {
    pub fn coordinates(&self, x: &[f64], unit: &str) -> Result<Vec<f64>, String> {
        if !["2th_deg", "q_A^-1", "q_nm^-1", "d_A"].contains(&self.unit.as_str())
            || self.wavelength.is_some_and(|v| !v.is_finite() || v <= 0.0)
        {
            return Err("Invalid Batch overlay source unit or wavelength.".into());
        }
        if self.unit == unit {
            return Ok(x.to_vec());
        }
        if [self.unit.as_str(), unit].contains(&"2th_deg") && self.wavelength.is_none() {
            return Err(
                "This Batch overlay has no recorded wavelength for angular conversion.".into(),
            );
        }
        let converted: Vec<_> = x
            .iter()
            .map(|&v| {
                crate::pattern::convert_coordinate(
                    v,
                    &self.unit,
                    unit,
                    self.wavelength.unwrap_or(1e-10),
                )
            })
            .collect();
        if converted.iter().any(|v| !v.is_finite()) {
            return Err(
                "The Batch overlay axis cannot be converted at its recorded wavelength.".into(),
            );
        }
        Ok(converted)
    }
}

/// Bind queued selections to scientific coordinates and source identities as well
/// as intensities. Two acquisitions can have identical display raster bytes.
pub(crate) fn identity(series: &Series) -> String {
    let mut hash = blake3::Hasher::new();
    hash.update(series.raster.buffer.id.as_bytes());
    hash.update(series.unit.as_bytes());
    hash.update(&series.wavelength.unwrap_or(0.0).to_le_bytes());
    hash.update(&[u8::from(series.normalized)]);
    // Display rasters are f32; scientific f64 changes must also invalidate a
    // pending rectangle even when their rounded display pixels are identical.
    let mut bytes = Vec::with_capacity(65536);
    for values in [
        Some(series.x.as_ref()),
        Some(series.data.as_ref()),
        series.sigma.as_deref(),
        series.spread.as_deref(),
    ] {
        hash.update(&[u8::from(values.is_some())]);
        if let Some(values) = values {
            hash.update(&(values.len() as u64).to_le_bytes());
            for chunk in values.chunks(8192) {
                bytes.clear();
                for value in chunk {
                    bytes.extend_from_slice(&value.to_le_bytes());
                }
                hash.update(&bytes);
            }
        }
    }
    for e in series.entries.iter() {
        hash.update(&(e.path.len() as u64).to_le_bytes());
        hash.update(e.path.as_bytes());
        hash.update(&(e.frame as u64).to_le_bytes());
    }
    hash.finalize().to_hex().to_string()
}

pub(crate) fn extract(
    series: &Series,
    args: &Value,
    unit: &str,
    control: &Control,
) -> Result<Vec<(Curve, String, Source)>, String> {
    let identity = identity(series);
    if args["series"].as_str() != Some(identity.as_str()) {
        return Err("The Batch series changed; select a new waterfall region.".into());
    }
    let range = |key: &str, count: usize| -> Result<[usize; 2], String> {
        let a = args[key]
            .as_array()
            .filter(|v| v.len() == 2)
            .ok_or("Choose two rectangle endpoints for each axis.")?;
        let mut v = [0.0; 2];
        for i in 0..2 {
            v[i] = a[i]
                .as_f64()
                .filter(|v| v.is_finite())
                .ok_or("Rectangle coordinates must be finite.")?
                .trunc();
        }
        v.sort_by(f64::total_cmp);
        let result = [
            v[0].clamp(0., count as f64) as usize,
            v[1].clamp(0., count as f64) as usize,
        ];
        if result[0] == result[1] {
            return Err(
                "The waterfall rectangle must include at least one row and radial bin.".into(),
            );
        }
        Ok(result)
    };
    let bins = range("bins", series.x.len())?;
    let rows = range("rows", series.count())?;
    let step = args["step"]
        .as_u64()
        .filter(|n| (1..=1_000_000).contains(n))
        .ok_or("Choose a positive integer waterfall step.")? as usize;
    if (rows[1] - rows[0]).div_ceil(step) > 1000 {
        return Err(
            "Select at most 1000 waterfall curves; increase Step or reduce the rectangle.".into(),
        );
    }
    let slice = |v: &Option<Arc<Vec<f64>>>, row: usize| {
        v.as_ref().map(|v| {
            Arc::new(v[row * series.x.len() + bins[0]..row * series.x.len() + bins[1]].to_vec())
        })
    };
    let x = Arc::new(series.x[bins[0]..bins[1]].to_vec());
    let mut curves = vec![];
    for row in (rows[0]..rows[1]).step_by(step) {
        control.check()?;
        let e = &series.entries[row];
        let source = Source {
            series: identity.clone(),
            row,
            path: e.path.clone(),
            frame: e.frame,
            bins,
            unit: series.unit.clone(),
            wavelength: series.wavelength,
            normalized: series.normalized,
        };
        source.coordinates(&x, unit)?; // Validate before replacing any existing overlays.
        let name = if e.path.is_empty() {
            "Stored pattern".into()
        } else {
            std::path::Path::new(&e.path)
                .file_name()
                .unwrap_or_default()
                .to_string_lossy()
                .into_owned()
        };
        curves.push((
            Curve {
                x: x.clone(),
                y: Arc::new(
                    series.data[row * series.x.len() + bins[0]..row * series.x.len() + bins[1]]
                        .to_vec(),
                ),
                sigma: slice(&series.sigma, row),
                spread: slice(&series.spread, row),
            },
            format!("{name}, {}", e.frame),
            source,
        ));
    }
    Ok(curves)
}
