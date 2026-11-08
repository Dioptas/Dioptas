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
        let mut trace = crate::frame_trace::FrameTrace::new("raster", values.len() as u64);
        let bytes = values
            .iter()
            .flat_map(|&v| (v as f32).to_le_bytes())
            .collect();
        let buffer = Buffer::new(bytes);
        trace.mark("f32 conversion and SHA256");
        let mut metadata = base(shape, "f32le", &buffer);
        metadata["limits"] =
            json!(levels(values, shape, "percentile", 2.5, true).unwrap_or([0.0, 1.0]));
        trace.mark("exact auto levels");
        metadata["autoLevels"] = json!({"mode":"percentile","percentile":2.5,"filter_gaps":true});
        metadata["histogram"] = histogram(values);
        trace.mark("full pixel histogram");
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
// Exact order statistics for bounded integer counts. Every pixel contributes;
// floating/corrected or wide-range data retain the general selection algorithm.
fn integer_percentiles(
    values: impl Iterator<Item = f64>,
    count: usize,
    low: f64,
    high: f64,
    clipping: f64,
) -> Option<(f64, f64)> {
    let span = high - low;
    if low.fract() != 0. || high.fract() != 0. {
        return None;
    }
    let bins = span.min(65_536.) as usize + 1;
    if bins > count.saturating_mul(4) {
        return None;
    }
    let mut counts = vec![0usize; bins];
    let mut overflow = 0;
    for v in values {
        if v.fract() != 0. {
            return None;
        }
        let offset = v - low;
        if offset < bins as f64 {
            counts[offset as usize] += 1;
        } else {
            overflow += 1;
        }
    }
    let quantile = |p: f64| {
        let rank = (count - 1) as f64 * p / 100.;
        let index = rank.floor() as usize;
        let fraction = rank - index as f64;
        let mut cumulative = 0;
        let mut first = None;
        for (offset, &n) in counts.iter().enumerate() {
            cumulative += n;
            if cumulative > index && first.is_none() {
                first = Some(low + offset as f64);
            }
            if cumulative > index + 1 {
                return Some(first.unwrap() * (1. - fraction) + (low + offset as f64) * fraction);
            }
        }
        if overflow == 0 {
            Some(first.unwrap_or(high))
        } else {
            None
        }
    };
    Some((quantile(clipping)?, quantile(100. - clipping)?))
}
fn compensated_sum(values: impl Iterator<Item = f64>) -> f64 {
    let (mut sum, mut correction) = (0., 0.);
    for value in values {
        let adjusted = value - correction;
        let next = sum + adjusted;
        correction = (next - sum) - adjusted;
        sum = next;
    }
    sum
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
    let selected = || {
        values
            .iter()
            .copied()
            .filter(move |v| v.is_finite() && Some(*v) != gap)
    };
    let (mut count, mut min, mut max) = (0usize, f64::INFINITY, f64::NEG_INFINITY);
    for value in selected() {
        count += 1;
        if value.total_cmp(&min).is_lt() {
            min = value;
        }
        if value.total_cmp(&max).is_gt() {
            max = value;
        }
    }
    if count == 0 {
        return None;
    }
    let (low, high) = match mode {
        "minmax" => (min, max),
        "mean3std" => {
            let mut finite: Vec<_> = selected().collect();
            finite.sort_by(f64::total_cmp);
            // Shifted population variance avoids cancellation at large offsets.
            let offset = min;
            let mean_shift =
                compensated_sum(finite.iter().map(|v| v - offset)) / finite.len() as f64;
            let mean = offset + mean_shift;
            let std = (compensated_sum(finite.iter().map(|v| (v - offset - mean_shift).powi(2)))
                / finite.len() as f64)
                .sqrt();
            (min.max(mean - 3.0 * std), max.min(mean + 3.0 * std))
        }
        _ => integer_percentiles(selected(), count, min, max, clipping).unwrap_or_else(|| {
            let mut finite: Vec<_> = selected().collect();
            (
                percentile(&mut finite, clipping),
                percentile(&mut finite, 100.0 - clipping),
            )
        }),
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
        low = low.min(*value);
        high = high.max(*value);
        count += 1;
    }
    // asinh is monotone: transform the two extrema, not all pixels twice.
    low = low.asinh();
    high = high.asinh();
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
    let buckets = |values: &[f64]| {
        let mut counts = vec![0_u64; 256];
        for value in values.iter().filter(|v| v.is_finite()) {
            let index = (((value.asinh() - low) / (high - low) * 256.0) as usize).min(255);
            counts[index] += 1;
        }
        counts
    };
    let counts = if values.len() >= 1_000_000 {
        let workers = std::thread::available_parallelism()
            .map_or(1, |n| n.get())
            .min(8);
        std::thread::scope(|scope| {
            let handles: Vec<_> = values
                .chunks(values.len().div_ceil(workers))
                .map(|part| scope.spawn(move || buckets(part)))
                .collect();
            let mut result = vec![0_u64; 256];
            for handle in handles {
                for (a, b) in result.iter_mut().zip(handle.join().unwrap()) {
                    *a += b;
                }
            }
            result
        })
    } else {
        buckets(values)
    };
    let edges: Vec<_> = (0..=256)
        .map(|i| (low + (high - low) * i as f64 / 256.0).sinh())
        .collect();
    json!({"edges": edges, "counts": counts, "finitePixels": count})
}

#[cfg(test)]
mod statistics_tests {
    use super::*;
    #[test]
    fn dense_order_statistics_match_known_interpolated_quantiles_and_reject_float_data() {
        // NumPy's linear percentiles of sorted [0,0,1,1,3,5,8,10].
        let values = [8., 0., 1., 5., 10., 0., 1., 3.];
        assert_eq!(
            integer_percentiles(values.into_iter(), values.len(), 0., 10., 25.),
            Some((0.75, 5.75))
        );
        let outliers: Vec<_> = std::iter::repeat_n(0., 10_000)
            .chain(std::iter::repeat_n(1., 10_000))
            .chain([6_000_000.])
            .collect();
        assert_eq!(
            integer_percentiles(
                outliers.iter().copied(),
                outliers.len(),
                0.,
                6_000_000.,
                25.
            ),
            Some((0., 1.))
        );
        let dominated: Vec<_> = std::iter::repeat_n(0., 10_000)
            .chain(std::iter::repeat_n(6_000_000., 10_001))
            .collect();
        assert_eq!(
            integer_percentiles(
                dominated.iter().copied(),
                dominated.len(),
                0.,
                6_000_000.,
                25.
            ),
            None
        );
        let negative: Vec<_> = values.iter().map(|v| v - 7.).collect();
        assert_eq!(
            integer_percentiles(negative.iter().copied(), negative.len(), -7., 3., 25.),
            Some((-6.25, -1.25))
        );
        assert_eq!(
            integer_percentiles([0., 0.5, 1.].into_iter(), 3, 0., 1., 25.),
            None
        );
        assert_eq!(
            integer_percentiles([0., 2_000_000.].into_iter(), 2, 0., 2_000_000., 25.),
            None
        );
    }
    #[test]
    fn mean_limits_use_population_variance_without_large_offset_cancellation() {
        let mut values = vec![0.; 1000];
        values[0] = -100.;
        values[1] = 100.;
        let result = levels(&values, [100, 10], "mean3std", 2.5, false).unwrap();
        assert!((result[0] + 3. * 20f64.sqrt()).abs() < 1e-12);
        assert!((result[1] - 3. * 20f64.sqrt()).abs() < 1e-12);
    }
}
