//! Full-resolution display copies; statistics always use scientific f64 values.
use crate::protocol::Buffer;
use serde_json::{Value, json};
use std::{collections::HashMap, sync::Arc};

#[derive(Clone)]
pub struct Raster {
    pub metadata: Value,
    pub buffer: Buffer,
    statistics: Option<Arc<ImageStatistics>>,
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
        let statistics = (values.len() >= 4096)
            .then(|| ImageStatistics::new(values, shape))
            .flatten()
            .map(Arc::new);
        trace.mark("shared count distribution");
        let mut metadata = base(shape, "f32le", &buffer);
        metadata["limits"] = json!(
            statistics
                .as_ref()
                .and_then(|s| s.levels("percentile", 2.5, true))
                .or_else(|| levels(values, shape, "percentile", 2.5, true))
                .unwrap_or([0.0, 1.0])
        );
        trace.mark("exact auto levels");
        metadata["autoLevels"] = json!({"mode":"percentile","percentile":2.5,"filter_gaps":true});
        metadata["histogram"] = statistics
            .as_ref()
            .map_or_else(|| histogram(values), |s| s.histogram());
        trace.mark("full pixel histogram");
        Self {
            metadata,
            buffer,
            statistics,
        }
    }
    pub fn mask(values: &[u8], shape: [usize; 2]) -> Self {
        let buffer = Buffer::new(values.to_vec());
        Self {
            metadata: base(shape, "u8", &buffer),
            buffer,
            statistics: None,
        }
    }
    pub fn cached_levels(&self, mode: &str, clipping: f64, filter_gaps: bool) -> Option<[f64; 2]> {
        self.statistics
            .as_ref()?
            .levels(mode, clipping, filter_gaps)
    }
}

/// Lossless counts shared by the display histogram and exact order statistics.
/// Common detector counts use a bounded dense table; rare high/negative counts
/// use a bounded sparse table. Fractional or high-cardinality data fall back to
/// the general source-precision implementation rather than being approximated.
struct ImageStatistics {
    counts: Vec<(f64, u64)>,
    gap: Option<f64>,
}
struct CountTable {
    dense: Vec<u64>,
    sparse: HashMap<u64, u64>,
}
impl CountTable {
    fn new(values: &[f64]) -> Option<Self> {
        let mut result = Self {
            dense: vec![0; 65_537],
            sparse: HashMap::new(),
        };
        for &value in values {
            if !value.is_finite() {
                continue;
            }
            // Preserve signed-zero behavior through the general implementation.
            if value.trunc() != value || value.to_bits() == (-0.0f64).to_bits() {
                return None;
            }
            if (-1.0..=65_535.0).contains(&value) {
                result.dense[(value + 1.) as usize] += 1;
            } else {
                *result.sparse.entry(value.to_bits()).or_default() += 1;
                if result.sparse.len() > 4096 {
                    return None;
                }
            }
        }
        Some(result)
    }
}
impl ImageStatistics {
    fn new(values: &[f64], shape: [usize; 2]) -> Option<Self> {
        let workers = if values.len() >= 1_000_000 {
            std::thread::available_parallelism()
                .map_or(1, |n| n.get())
                .min(8)
        } else {
            1
        };
        let mut table = if workers == 1 {
            CountTable::new(values)?
        } else {
            std::thread::scope(|scope| {
                let handles: Vec<_> = values
                    .chunks(values.len().div_ceil(workers))
                    .map(|part| scope.spawn(move || CountTable::new(part)))
                    .collect();
                // Join every worker before deciding whether to use the fallback.
                let tables: Option<Vec<_>> = handles
                    .into_iter()
                    .map(|handle| handle.join().unwrap())
                    .collect();
                let mut tables = tables?.into_iter();
                let mut result = tables.next()?;
                for table in tables {
                    for (a, b) in result.dense.iter_mut().zip(table.dense) {
                        *a += b;
                    }
                    for (key, count) in table.sparse {
                        *result.sparse.entry(key).or_default() += count;
                    }
                }
                Some(result)
            })?
        };
        // Keep the retained cache bounded even if different workers saw disjoint
        // sparse values. Dense and sparse domains never overlap.
        if table.sparse.len() > 4096 {
            return None;
        }
        let mut counts: Vec<_> = table
            .dense
            .into_iter()
            .enumerate()
            .filter(|(_, n)| *n != 0)
            .map(|(index, n)| (index as f64 - 1., n))
            .chain(
                table
                    .sparse
                    .drain()
                    .map(|(bits, n)| (f64::from_bits(bits), n)),
            )
            .collect();
        counts.sort_unstable_by(|a, b| a.0.total_cmp(&b.0));
        Some(Self {
            counts,
            gap: gap_value(values, shape),
        })
    }
    fn levels(&self, mode: &str, clipping: f64, filter_gaps: bool) -> Option<[f64; 2]> {
        if mode == "mean3std" {
            return None;
        }
        let gap = filter_gaps.then_some(self.gap).flatten();
        let selected = || self.counts.iter().filter(|(v, _)| Some(*v) != gap);
        let low = selected().next()?.0;
        let high = selected().next_back()?.0;
        let (low, high) = if mode == "minmax" {
            (low, high)
        } else {
            let count: u64 = selected().map(|(_, n)| n).sum();
            let quantile = |p: f64| {
                let rank = (count - 1) as f64 * p / 100.;
                let index = rank.floor() as u64;
                let fraction = rank - index as f64;
                let mut cumulative = 0;
                let mut first = None;
                for &(value, n) in selected() {
                    cumulative += n;
                    if cumulative > index && first.is_none() {
                        first = Some(value);
                    }
                    if cumulative > index + 1 {
                        return first.unwrap() * (1. - fraction) + value * fraction;
                    }
                }
                first.unwrap_or(high)
            };
            (quantile(clipping), quantile(100. - clipping))
        };
        Some(padded_levels(low, high))
    }
    fn histogram(&self) -> Value {
        let count = self.counts.iter().map(|(_, n)| n).sum::<u64>();
        let (low, high) = histogram_range(
            self.counts.first().map_or(f64::INFINITY, |v| v.0),
            self.counts.last().map_or(f64::NEG_INFINITY, |v| v.0),
            count,
        );
        let mut counts = vec![0u64; 256];
        for &(value, n) in &self.counts {
            let index = (((value.asinh() - low) / (high - low) * 256.) as usize).min(255);
            counts[index] += n;
        }
        histogram_metadata(low, high, counts, count)
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
    Some(padded_levels(low, high))
}
fn padded_levels(low: f64, high: f64) -> [f64; 2] {
    [
        low,
        if high <= low {
            low + 1.0_f64.max(low.abs() * 1e-6)
        } else {
            high
        },
    ]
}
fn histogram(values: &[f64]) -> Value {
    let mut low = f64::INFINITY;
    let mut high = f64::NEG_INFINITY;
    let mut count = 0u64;
    for value in values.iter().filter(|v| v.is_finite()) {
        low = low.min(*value);
        high = high.max(*value);
        count += 1;
    }
    let (low, high) = histogram_range(low, high, count);
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
    histogram_metadata(low, high, counts, count)
}
fn histogram_range(low: f64, high: f64, count: u64) -> (f64, f64) {
    // asinh is monotone: transform the two extrema, not all pixels twice.
    let (mut low, mut high) = (low.asinh(), high.asinh());
    if count == 0 {
        (0., 1.)
    } else {
        let padding = low.abs().max(high.abs()).max(1.) * 1e-6;
        if high - low < padding {
            low -= padding;
            high += padding;
        }
        (low, high)
    }
}
fn histogram_metadata(low: f64, high: f64, counts: Vec<u64>, count: u64) -> Value {
    let edges: Vec<_> = (0..=256)
        .map(|i| (low + (high - low) * i as f64 / 256.0).sinh())
        .collect();
    json!({"edges": edges, "counts": counts, "finitePixels": count})
}

#[cfg(test)]
mod statistics_tests {
    use super::*;
    #[test]
    fn shared_integer_counts_preserve_full_histogram_and_filtered_exact_levels() {
        let shape = [96, 128];
        for marker in [0., -1., i32::MAX as f64, u32::MAX as f64] {
            let mut values: Vec<_> = (0..shape[0] * shape[1])
                .map(|i| ((i * 997) % 1000) as f64 - 40.)
                .collect();
            for row in 0..shape[0] {
                values[row * shape[1] + 40..row * shape[1] + 44].fill(marker);
            }
            values[9] = 6_383_154.;
            values[10] = f64::NAN;
            values[11] = f64::INFINITY;
            let statistics = ImageStatistics::new(&values, shape).unwrap();
            assert_eq!(statistics.histogram(), histogram(&values));
            for filter in [false, true] {
                assert_eq!(
                    statistics.levels("minmax", 2.5, filter),
                    levels(&values, shape, "minmax", 2.5, filter)
                );
                for percentile in [0., 0.4, 2.5, 25., 49.999999] {
                    assert_eq!(
                        statistics.levels("percentile", percentile, filter),
                        levels(&values, shape, "percentile", percentile, filter)
                    );
                }
            }
        }
        for values in [vec![120.; 4096], vec![f64::NAN; 4096]] {
            let statistics = ImageStatistics::new(&values, [64, 64]).unwrap();
            assert_eq!(statistics.histogram(), histogram(&values));
            assert_eq!(
                statistics.levels("percentile", 2.5, true),
                levels(&values, [64, 64], "percentile", 2.5, true)
            );
        }
    }
    #[test]
    fn parallel_counts_preserve_every_sample_and_fallback_is_bounded() {
        let mut values: Vec<_> = (0..1_048_576).map(|i| ((i * 997) % 1024) as f64).collect();
        values[40] = u32::MAX as f64;
        let statistics = ImageStatistics::new(&values, [1024, 1024]).unwrap();
        assert_eq!(statistics.histogram(), histogram(&values));
        assert_eq!(
            statistics.levels("percentile", 2.5, true),
            levels(&values, [1024, 1024], "percentile", 2.5, true)
        );
        values[41] = 0.5;
        assert!(ImageStatistics::new(&values, [1024, 1024]).is_none());
        assert!(ImageStatistics::new(&[-0., 0.], [1, 2]).is_none());
        let wide: Vec<_> = (0..4097).map(|i| i as f64 + 65_536.).collect();
        assert!(ImageStatistics::new(&wide, [1, 4097]).is_none());
    }
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
