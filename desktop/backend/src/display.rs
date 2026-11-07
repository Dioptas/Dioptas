//! Full-resolution display copies; statistics always use scientific f64 values.
use crate::protocol::Buffer;
use serde_json::{Value, json};

#[derive(Clone)]
pub struct Raster {
    pub metadata: Value,
    pub buffer: Buffer,
}
impl Raster {
    pub fn image(values: &[f64], shape: [usize; 2]) -> Self {
        let bytes = values
            .iter()
            .flat_map(|&v| (v as f32).to_le_bytes())
            .collect();
        let buffer = Buffer::new(bytes);
        let mut metadata = base(shape, "f32le", &buffer);
        metadata["limits"] =
            json!(levels(values, shape, "percentile", 2.5, true).unwrap_or([0.0, 1.0]));
        metadata["histogram"] = histogram(values);
        Self { metadata, buffer }
    }
    pub fn mask(values: &[u8], shape: [usize; 2]) -> Self {
        let buffer = Buffer::new(values.to_vec());
        Self {
            metadata: base(shape, "u8", &buffer),
            buffer,
        }
    }
}
fn base([height, width]: [usize; 2], dtype: &str, buffer: &Buffer) -> Value {
    json!({"width": width, "height": height, "fullWidth": width, "fullHeight": height,
        "step": 1, "dtype": dtype, "limits": [0, 1], "bufferId": buffer.id})
}
fn percentile(values: &mut [f64], p: f64) -> f64 {
    let rank = (values.len() - 1) as f64 * p / 100.0;
    let i = rank.floor() as usize;
    let fraction = rank - i as f64;
    let (_, value, right) = values.select_nth_unstable_by(i, f64::total_cmp);
    let next = right
        .iter()
        .min_by(|a, b| a.total_cmp(b))
        .copied()
        .unwrap_or(*value);
    *value * (1.0 - fraction) + next * fraction
}
/// Same gap rule as the existing desktop: repeated constant columns, then rows.
fn gap_value(values: &[f64], [height, width]: [usize; 2]) -> Option<f64> {
    for transpose in [false, true] {
        let (rows, cols) = if transpose {
            (width, height)
        } else {
            (height, width)
        };
        let at = |r, c| {
            values[if transpose {
                c * width + r
            } else {
                r * width + c
            }]
        };
        let mut candidates: Vec<f64> = (0..cols)
            .filter(|&c| (0..rows).all(|r| at(r, c) == at(0, c)))
            .map(|c| at(0, c))
            .collect();
        candidates.sort_by(f64::total_cmp);
        let mut best = None;
        let mut best_count = 1;
        let mut i = 0;
        while i < candidates.len() {
            let mut end = i + 1;
            while end < candidates.len() && candidates[end] == candidates[i] {
                end += 1;
            }
            if end - i > best_count && end - i < cols {
                best = Some(candidates[i]);
                best_count = end - i;
            }
            i = end;
        }
        if best.is_some() {
            return best;
        }
    }
    None
}
pub fn levels(
    values: &[f64],
    shape: [usize; 2],
    mode: &str,
    clipping: f64,
    filter_gaps: bool,
) -> Option<[f64; 2]> {
    let gap = filter_gaps.then(|| gap_value(values, shape)).flatten();
    let mut finite: Vec<_> = values
        .iter()
        .copied()
        .filter(|v| v.is_finite() && Some(*v) != gap)
        .collect();
    if finite.is_empty() {
        return None;
    }
    let min = *finite.iter().min_by(|a, b| a.total_cmp(b)).unwrap();
    let max = *finite.iter().max_by(|a, b| a.total_cmp(b)).unwrap();
    let (low, high) = match mode {
        "minmax" => (min, max),
        "mean3std" => {
            finite.sort_by(f64::total_cmp);
            // Shifted population variance avoids cancellation at large offsets.
            let offset = min;
            let mean_shift = finite.iter().map(|v| v - offset).sum::<f64>() / finite.len() as f64;
            let mean = offset + mean_shift;
            let std = (finite
                .iter()
                .map(|v| (v - offset - mean_shift).powi(2))
                .sum::<f64>()
                / finite.len() as f64)
                .sqrt();
            (min.max(mean - 3.0 * std), max.min(mean + 3.0 * std))
        }
        _ => (
            percentile(&mut finite, clipping),
            percentile(&mut finite, 100.0 - clipping),
        ),
    };
    Some([
        low,
        if high <= low {
            low + 1.0_f64.max(low.abs() * 1e-6)
        } else {
            high
        },
    ])
}
fn histogram(values: &[f64]) -> Value {
    let mut low = f64::INFINITY;
    let mut high = f64::NEG_INFINITY;
    let mut count = 0;
    for value in values.iter().filter(|v| v.is_finite()) {
        let t = value.asinh();
        low = low.min(t);
        high = high.max(t);
        count += 1;
    }
    if count == 0 {
        low = 0.0;
        high = 1.0;
    } else {
        let padding = low.abs().max(high.abs()).max(1.0) * 1e-6;
        if high - low < padding {
            low -= padding;
            high += padding;
        }
    }
    let mut counts = vec![0_u64; 256];
    for value in values.iter().filter(|v| v.is_finite()) {
        let index = (((value.asinh() - low) / (high - low) * 256.0) as usize).min(255);
        counts[index] += 1;
    }
    let edges: Vec<_> = (0..=256)
        .map(|i| (low + (high - low) * i as f64 / 256.0).sinh())
        .collect();
    json!({"edges": edges, "counts": counts, "finitePixels": count})
}
