//! Estimate of the first frame start angle and the DAC half-opening from the
//! shadow the cell body casts on the frames. Rotation axis and sense, step,
//! frame width and the cell axis are taken as given.
//!
//! The shadow is measured on coarse blocks of a few frames near both ends of
//! the scan (see `Crystal::estimate_dac`): a block is dark
//! when its median count falls below half of its lit level (a high quantile
//! over the scan). The model is the DAC opening at the block centre and the
//! middle of each exposure; a block is shadowed when its ray or the incoming
//! beam leaves the cone. Agreement is the overlap (intersection over union) of
//! measured and modelled shadow, so shadow left open and lit area masked both
//! count against it.
//!
//! The start and the opening are separable only when the shadow edge moves in
//! from both ends of the scan (or rings the beam). Along one edge only their
//! combination is fixed; then the start is kept and the opening alone fitted.
//!
//! The search only visits starts that are whole multiples of the rotation
//! step and openings that are multiples of 0.5°, so the values it returns lie
//! on those grids and the reported agreement is that of the returned values.
use super::*;
use rayon::prelude::*;
use std::sync::atomic::{AtomicUsize, Ordering};

/// Opening resolution, degrees.
const BIN: f64 = 0.05;
const BINS: usize = 1800;
/// Openings considered, degrees.
const OPENING: [f64; 2] = [1., 89.5];
/// Frames read at each end of the scan, where the shadow edge is, spread
/// over this share of the scan. Measured on the ID11 Eiger scan: 2 per end
/// agree with all 144 frames within 0.6° start / 1.1° opening at 0.07 s.
const PER_END: usize = 2;
const REACH: f64 = 0.1;
/// Frames read between an end without an edge and the middle.
const PROBES: usize = 4;
/// A frame shows the edge when this share up to all but this share is dark.
const EDGE: f64 = 0.02;
/// Coarse blocks along the longer detector side.
const CELLS_ACROSS: usize = 64;
/// A block is dark below this share of its lit level.
const DARK_RATIO: f64 = 0.5;
/// Starts searched around the current one, degrees, and the first grid
/// step. Starts are multiples of the rotation step: the search refines a
/// coarse grid of such multiples down to the step itself.
const SEARCH: f64 = 45.;
const COARSE: f64 = 0.5;
/// Openings are multiples of this, degrees (a whole number of bins).
const OPENING_GRID: f64 = 0.5;
/// Fits within this agreement of the best one count as equally good.
const TOLERANCE: f64 = 0.01;
/// A value is determined when its equally good range is at most this wide.
/// Two edges give about 1-2° (the cone only approximates the cell body);
/// one edge leaves a ridge many degrees long.
const DETERMINED: f64 = 3.;
/// Less measured shadow than this share of the blocks is no shadow.
const MIN_DARK: f64 = 0.005;

fn unit(v: V3) -> Result<V3, String> {
    let n = fft::dot(v, v).sqrt();
    if !n.is_finite() || n < 1e-12 {
        return Err("Axis and beam must be finite and nonzero.".into());
    }
    Ok(v.map(|x| x / n))
}
fn cross(a: V3, b: V3) -> V3 {
    [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]
}

/// The measured shadow: one ray per block, the frames read and a frame-major
/// label per block (1 dark, 0 lit, -1 unknown).
pub(super) struct Shadow {
    pub rays: Vec<V3>,
    pub frames: Vec<usize>,
    pub labels: Vec<i8>,
}
/// The fixed rotation and cell geometry.
#[derive(Clone, Copy)]
pub(super) struct Rotation {
    pub axis: V3,
    pub dac_axis: V3,
    pub beam: V3,
    pub step: f64,
    pub exposure: f64,
}
impl Rotation {
    /// The rotation and cell axis of the settings, with the calibrated beam.
    pub fn new(c: &Config, g: &Geometry) -> Result<Self, String> {
        Ok(Self {
            axis: unit(c.axis)?,
            dac_axis: unit(c.dac_axis)?,
            beam: unit(g.beam)?,
            step: c.omega_step,
            exposure: c.exposure,
        })
    }
    /// Cell axis at the middle of the exposure of `frame`.
    fn cell_axis(&self, start: f64, frame: usize) -> V3 {
        let w = (start + frame as f64 * self.step + self.exposure / 2.).to_radians();
        let along = fft::dot(self.axis, self.dac_axis);
        let side = cross(self.axis, self.dac_axis);
        std::array::from_fn(|j| {
            self.axis[j] * along
                + w.cos() * (self.dac_axis[j] - self.axis[j] * along)
                + w.sin() * side[j]
        })
    }
    /// Angle (degrees) between each block's ray, or the incoming beam if that
    /// is larger, and the cell axis; a block is shadowed when it exceeds the
    /// half-opening. Calls `each(index, angle)` for every known label.
    fn angles(&self, shadow: &Shadow, start: f64, mut each: impl FnMut(usize, f64)) {
        let cells = shadow.rays.len();
        for (i, &frame) in shadow.frames.iter().enumerate() {
            let n = self.cell_axis(start, frame);
            let beam = fft::dot(self.beam, n).abs();
            for (c, ray) in shadow.rays.iter().enumerate() {
                let k = i * cells + c;
                if shadow.labels[k] >= 0 {
                    let cosine = fft::dot(*ray, n).abs().min(beam).min(1.);
                    each(k, cosine.acos().to_degrees());
                }
            }
        }
    }
    /// Per ray: the angle past the DAC opening (degrees; positive outside
    /// the cone, so shadowed by the model, as in `angles`) and the azimuth
    /// around the cell axis in the cell's own frame (degrees), which follows
    /// a feature of the cell body through the rotation.
    pub fn cone_coordinates(
        &self,
        rays: &[V3],
        start: f64,
        opening: f64,
        frame: usize,
    ) -> Vec<[f64; 2]> {
        let n = self.cell_axis(start, frame);
        let beam = fft::dot(self.beam, n).abs();
        let w = -(start + frame as f64 * self.step + self.exposure / 2.).to_radians();
        let a = self.axis;
        let d = self.dac_axis;
        let mut e1 = cross(d, a);
        if fft::dot(e1, e1) < 1e-12 {
            e1 = cross(
                d,
                if d[0].abs() < 0.9 {
                    [1., 0., 0.]
                } else {
                    [0., 1., 0.]
                },
            );
        }
        let e1 = unit(e1).unwrap_or([1., 0., 0.]);
        let e2 = cross(d, e1);
        rays.iter()
            .map(|&r| {
                let cosine = fft::dot(r, n).abs().min(beam).min(1.);
                let past = cosine.acos().to_degrees() - opening;
                // The ray in the cell frame (rotated back by the angle).
                let ar = cross(a, r);
                let along = fft::dot(a, r);
                let mut b: V3 = std::array::from_fn(|j| {
                    r[j] * w.cos() + ar[j] * w.sin() + a[j] * along * (1. - w.cos())
                });
                if fft::dot(b, d) < 0. {
                    b = b.map(|v| -v);
                }
                let azimuth = fft::dot(b, e2)
                    .atan2(fft::dot(b, e1))
                    .to_degrees()
                    .rem_euclid(360.);
                [past, azimuth]
            })
            .collect()
    }
    /// Agreement for every opening `k * BIN` at one start.
    fn curve(&self, shadow: &Shadow, start: f64) -> Vec<f64> {
        let mut dark = vec![0u32; BINS + 1];
        let mut lit = vec![0u32; BINS + 1];
        self.angles(shadow, start, |k, angle| {
            let bin = ((angle / BIN) as usize).min(BINS);
            if shadow.labels[k] == 1 {
                dark[bin] += 1;
            } else {
                lit[bin] += 1;
            }
        });
        let total: f64 = dark.iter().map(|&v| f64::from(v)).sum();
        // Opening k*BIN masks every angle in bin k or above.
        let (mut hit, mut wrong) = (0., 0.);
        let mut out = vec![0.; BINS + 1];
        for k in (0..=BINS).rev() {
            hit += f64::from(dark[k]);
            wrong += f64::from(lit[k]);
            out[k] = if total + wrong > 0. {
                hit / (total + wrong)
            } else {
                0.
            };
        }
        out
    }
    /// Agreement of one start and opening.
    pub fn agreement(&self, shadow: &Shadow, start: f64, opening: f64) -> f64 {
        let (mut hit, mut union) = (0usize, 0usize);
        self.angles(shadow, start, |k, angle| {
            let dark = shadow.labels[k] == 1;
            let masked = angle > opening;
            hit += usize::from(dark && masked);
            union += usize::from(dark || masked);
        });
        if union == 0 {
            0.
        } else {
            hit as f64 / union as f64
        }
    }
}

/// Fit outcome. `start`/`opening` are the values to apply (None: keep).
#[derive(Debug)]
pub(super) struct Estimate {
    pub status: &'static str,
    pub start: Option<f64>,
    pub opening: Option<f64>,
    pub before: f64,
    pub after: f64,
    pub start_range: Option<[f64; 2]>,
    pub opening_range: Option<[f64; 2]>,
    pub dark_share: f64,
}

/// Removes binary noise from a grid value (k × step).
fn tidy(v: f64) -> f64 {
    (v * 1e9).round() / 1e9
}
/// Opening bins on the 0.5° grid.
fn openings() -> impl Iterator<Item = usize> + Clone {
    let every = (OPENING_GRID / BIN).round() as usize;
    ((OPENING[0] / BIN).round() as usize..=(OPENING[1] / BIN).round() as usize).step_by(every)
}
/// Best opening bin of a curve and the range of openings within tolerance.
fn best_opening(curve: &[f64]) -> (usize, f64, [f64; 2]) {
    let (k, best) = openings()
        .map(|k| (k, curve[k]))
        .fold((0, f64::NEG_INFINITY), |a, b| if b.1 > a.1 { b } else { a });
    let good: Vec<_> = openings()
        .filter(|&k| curve[k] >= best - TOLERANCE)
        .collect();
    (
        k,
        best,
        [
            tidy(good[0] as f64 * BIN),
            tidy(good[good.len() - 1] as f64 * BIN),
        ],
    )
}

/// Fit start and opening, or only the opening when the start is not
/// determined. `start`/`opening` are the current settings.
pub(super) fn fit(
    shadow: &Shadow,
    rotation: &Rotation,
    start: f64,
    opening: f64,
    control: &Control,
) -> Result<Estimate, String> {
    let known = shadow.labels.iter().filter(|&&v| v >= 0).count();
    let dark = shadow.labels.iter().filter(|&&v| v == 1).count();
    let dark_share = if known == 0 {
        0.
    } else {
        dark as f64 / known as f64
    };
    let before = rotation.agreement(shadow, start, opening);
    let keep = |status| Estimate {
        status,
        start: None,
        opening: None,
        before,
        after: before,
        start_range: None,
        opening_range: None,
        dark_share,
    };
    if known == 0 || dark_share < MIN_DARK || dark_share > 1. - MIN_DARK {
        return Ok(keep("no_shadow"));
    }
    let step = rotation.step.abs();
    if !step.is_finite() || step < 1e-6 {
        return Ok(keep("undetermined"));
    }
    // Starts are whole multiples k of the step; rows are evaluated once.
    let evaluate = |table: &mut Vec<(i64, f64, Vec<f64>)>, ks: Vec<i64>| -> Result<(), String> {
        let ks: Vec<i64> = ks
            .into_iter()
            .filter(|k| !table.iter().any(|r| r.0 == *k))
            .collect();
        let rows: Result<Vec<_>, String> = crate::worker_pool::install(|| {
            ks.into_par_iter()
                .map(|k| {
                    control.check()?;
                    let s = tidy(k as f64 * step);
                    Ok((k, s, rotation.curve(shadow, s)))
                })
                .collect()
        });
        table.extend(rows?);
        Ok(())
    };
    let profile = |row: &(i64, f64, Vec<f64>)| best_opening(&row.2).1;
    let best_k = |table: &[(i64, f64, Vec<f64>)]| {
        // Ties go to the smaller k, independent of evaluation order.
        table
            .iter()
            .max_by(|a, b| profile(a).total_cmp(&profile(b)).then(b.0.cmp(&a.0)))
            .map(|r| r.0)
            .unwrap()
    };
    let mut stride = ((COARSE / step).ceil() as i64).max(1);
    let reach = ((SEARCH / step).round() as i64).max(stride);
    let centre = (start / step).round() as i64;
    let mut table = vec![];
    evaluate(
        &mut table,
        (-reach / stride..=reach / stride)
            .map(|i| centre + i * stride)
            .collect(),
    )?;
    // Refine around the best start down to single steps.
    while stride > 1 {
        let finer = (stride / 10).max(1);
        let k = best_k(&table);
        evaluate(
            &mut table,
            (-stride / finer..=stride / finer)
                .map(|i| k + i * finer)
                .collect(),
        )?;
        stride = finer;
    }
    let k_best = best_k(&table);
    let (best_start, best_row) = table
        .iter()
        .find(|r| r.0 == k_best)
        .map(|r| (r.1, &r.2))
        .unwrap();
    let (k, best, _) = best_opening(best_row);
    // Equally good starts (profiled over the opening) and openings
    // (profiled over the start).
    let starts: Vec<f64> = table
        .iter()
        .filter(|r| profile(r) >= best - TOLERANCE)
        .map(|r| r.1)
        .collect();
    let start_range = [
        starts.iter().copied().fold(f64::INFINITY, f64::min),
        starts.iter().copied().fold(f64::NEG_INFINITY, f64::max),
    ];
    let good_openings: Vec<usize> = openings()
        .filter(|&j| table.iter().any(|r| r.2[j] >= best - TOLERANCE))
        .collect();
    let opening_range = [
        tidy(good_openings[0] as f64 * BIN),
        tidy(good_openings[good_openings.len() - 1] as f64 * BIN),
    ];
    if start_range[1] - start_range[0] <= DETERMINED
        && opening_range[1] - opening_range[0] <= DETERMINED
    {
        let (s, a) = (best_start, tidy(k as f64 * BIN));
        return Ok(Estimate {
            status: "both",
            start: Some(s),
            opening: Some(a),
            before,
            after: rotation.agreement(shadow, s, a),
            start_range: Some(start_range),
            opening_range: Some(opening_range),
            dark_share,
        });
    }
    // Only their combination is fixed: keep the start, fit the opening.
    let (k, _, range) = best_opening(&rotation.curve(shadow, start));
    if range[1] - range[0] > DETERMINED {
        return Ok(keep("undetermined"));
    }
    let a = tidy(k as f64 * BIN);
    Ok(Estimate {
        status: "opening_only",
        start: None,
        opening: Some(a),
        before,
        after: rotation.agreement(shadow, start, a),
        start_range: Some(start_range),
        opening_range: Some(range),
        dark_share,
    })
}

/// Label blocks from frame-major coarse medians (NaN: unknown). The lit level
/// of a block is a high quantile over the frames read.
pub(super) fn classify(values: &[f64], cells: usize) -> Vec<i8> {
    let frames = values.len() / cells.max(1);
    let lit: Vec<f64> = (0..cells)
        .map(|c| {
            let mut v: Vec<f64> = (0..frames)
                .map(|f| values[f * cells + c])
                .filter(|v| v.is_finite())
                .collect();
            if v.len() < 3 {
                return f64::NAN;
            }
            v.sort_unstable_by(f64::total_cmp);
            v[((v.len() - 1) as f64 * 0.9).round() as usize]
        })
        .collect();
    let mut levels: Vec<f64> = lit.iter().copied().filter(|v| v.is_finite()).collect();
    levels.sort_unstable_by(f64::total_cmp);
    // Blocks that are never lit (beam stop, detector edge) say nothing.
    let floor = levels
        .get(levels.len() / 2)
        .map_or(f64::INFINITY, |m| m * 0.2);
    values
        .iter()
        .enumerate()
        .map(|(i, &v)| {
            let level = lit[i % cells];
            if !v.is_finite() || !level.is_finite() || level <= 0. || level < floor {
                -1
            } else {
                i8::from(v < DARK_RATIO * level)
            }
        })
        .collect()
}

/// Median of the usable pixels of each block; NaN when fewer than half are usable.
/// Usable counts are finite and non-negative, so their bit patterns order like
/// the values and the median is selected with integer comparisons.
pub(super) fn block_medians(
    data: &[f64],
    unusable: &[bool],
    shape: [usize; 2],
    block: usize,
) -> Vec<f64> {
    let [h, w] = shape;
    let (rows, columns) = (h.div_ceil(block), w.div_ceil(block));
    let mut out = vec![f64::NAN; rows * columns];
    let mut scratch: Vec<u64> = Vec::with_capacity(block * block);
    for by in 0..rows {
        let ys = by * block..((by + 1) * block).min(h);
        for bx in 0..columns {
            let xs = bx * block..((bx + 1) * block).min(w);
            scratch.clear();
            for y in ys.clone() {
                let row = y * w;
                for (&v, &u) in data[row + xs.start..row + xs.end]
                    .iter()
                    .zip(&unusable[row + xs.start..row + xs.end])
                {
                    if !u && v >= 0. && v.is_finite() {
                        // Adding zero turns -0 into +0.
                        scratch.push((v + 0.).to_bits());
                    }
                }
            }
            if 2 * scratch.len() >= ys.len() * xs.len() && !scratch.is_empty() {
                let m = scratch.len() / 2;
                out[by * columns + bx] = f64::from_bits(*scratch.select_nth_unstable(m).1);
            }
        }
    }
    out
}

/// Rays through the block centres.
pub(super) fn block_rays(g: &Geometry, shape: [usize; 2], block: usize) -> Result<Vec<V3>, String> {
    let [h, w] = shape;
    let centre = |i: usize, n: usize| (i * block + ((i + 1) * block).min(n)) as f64 / 2. - 0.5;
    let mut rays = vec![];
    for by in 0..h.div_ceil(block) {
        for bx in 0..w.div_ceil(block) {
            let (x, y) = (centre(bx, w), centre(by, h));
            rays.push(unit(std::array::from_fn(|j| {
                g.origin[j] + x * g.fast[j] + y * g.slow[j]
            }))?);
        }
    }
    Ok(rays)
}

/// `per_end` frames at each end of the usable frames, from the end frame to
/// `REACH` of the scan inwards. Frames at one end that are spread apart see
/// the shadow edge at different places, which separates start and opening
/// better than neighbouring frames. All frames when there are too few.
pub(super) fn ends(used: &[usize], per_end: usize) -> Vec<usize> {
    let n = used.len();
    if per_end == 0 || n <= 2 * per_end {
        return used.to_vec();
    }
    let reach = ((REACH * (n - 1) as f64).round() as usize)
        .max(per_end - 1)
        .min((n - 1) / 2);
    let mut picks: Vec<usize> = (0..per_end)
        .map(|i| i * reach / (per_end - 1).max(1))
        .flat_map(|i| [i, n - 1 - i])
        .collect();
    picks.sort_unstable();
    picks.dedup();
    picks.into_iter().map(|i| used[i]).collect()
}

/// Whether a frame shows the shadow edge: some, but not all, of its known
/// blocks dark.
fn shows_edge(labels: &[i8]) -> bool {
    let known = labels.iter().filter(|&&v| v >= 0).count();
    let dark = labels.iter().filter(|&&v| v == 1).count() as f64;
    known > 0 && (EDGE..1. - EDGE).contains(&(dark / known as f64))
}

impl Crystal {
    /// Measure the shadow on a few frames and fit start and opening.
    ///
    /// Round one reads `PER_END` frames at each end and the middle frame (the
    /// lit reference). An end none of whose frames shows the edge (all dark:
    /// the beam itself is blocked; all lit: the shadow is further out) gets a
    /// second round of `PROBES` frames between it and the middle. Each round
    /// is read in parallel; every frame read enters the fit, frames without
    /// an edge as bounds.
    pub(super) fn estimate_dac(&self, control: &Control) -> Result<Value, String> {
        let used: Vec<usize> = (0..self.sources.len())
            .filter(|i| !self.excluded_frames.contains(i))
            .collect();
        let n = used.len();
        let mut frames = ends(&used, PER_END);
        frames.push(used.get(n / 2).copied().unwrap_or_default());
        frames.sort_unstable();
        frames.dedup();
        self.estimate_dac_frames(control, frames, true)
    }
    /// The estimate from the given frames, plus the second round if `probe`.
    pub(super) fn estimate_dac_frames(
        &self,
        control: &Control,
        mut frames: Vec<usize>,
        probe: bool,
    ) -> Result<Value, String> {
        self.sources_check()?;
        let g = self
            .initial_geometry
            .ok_or("Load a detector calibration before estimating the DAC opening.")?;
        let clock = std::time::Instant::now();
        if frames.len() < 3 {
            return Err("At least three frames are needed to estimate the DAC opening.".into());
        }
        let block = self.shape[0]
            .max(self.shape[1])
            .div_ceil(CELLS_ACROSS)
            .max(4);
        let rays = block_rays(&g, self.shape, block)?;
        let cells = rays.len();
        let mut values = self.block_frames(&frames, block, control)?;
        let mut labels = classify(&values, cells);
        if probe {
            let used: Vec<usize> = (0..self.sources.len())
                .filter(|i| !self.excluded_frames.contains(i))
                .collect();
            let middle = used.len() / 2;
            let position = |frame: usize| used.binary_search(&frame).unwrap_or(0);
            let mut extra = vec![];
            for low_end in [true, false] {
                let side: Vec<usize> = frames
                    .iter()
                    .enumerate()
                    .filter(|(_, f)| {
                        let p = position(**f);
                        if low_end { p < middle } else { p > middle }
                    })
                    .map(|(i, _)| i)
                    .collect();
                if side.is_empty()
                    || side
                        .iter()
                        .any(|&i| shows_edge(&labels[i * cells..(i + 1) * cells]))
                {
                    continue;
                }
                // Between the innermost frame read at this end and the middle.
                let inner = side
                    .iter()
                    .map(|&i| position(frames[i]))
                    .min_by_key(|p| p.abs_diff(middle))
                    .unwrap();
                for k in 1..=PROBES {
                    let p = if low_end {
                        inner + (middle - inner) * k / (PROBES + 1)
                    } else {
                        inner - (inner - middle) * k / (PROBES + 1)
                    };
                    extra.push(used[p]);
                }
            }
            extra.retain(|f| !frames.contains(f));
            extra.sort_unstable();
            extra.dedup();
            if !extra.is_empty() {
                values.extend(self.block_frames(&extra, block, control)?);
                frames.extend(extra);
                labels = classify(&values, cells);
            }
        }
        let shadow = Shadow {
            rays,
            frames,
            labels,
        };
        let c = &self.config;
        let rotation = Rotation::new(c, &g)?;
        control.publish(json!({"running":true,"label":"Fitting the DAC opening"}));
        let e = fit(
            &shadow,
            &rotation,
            c.omega_start,
            c.dac_half_opening,
            control,
        )?;
        let mut read = shadow.frames.clone();
        read.sort_unstable();
        Ok(json!({
            "status": e.status,
            "omegaStart": e.start,
            "halfOpening": e.opening,
            "before": e.before,
            "after": e.after,
            "startRange": e.start_range,
            "openingRange": e.opening_range,
            "darkShare": e.dark_share,
            "frames": read,
            "block": block,
            "seconds": clock.elapsed().as_secs_f64(),
        }))
    }
    /// Block medians of the given frames, decoded in parallel, frame-major.
    pub(super) fn block_frames(
        &self,
        frames: &[usize],
        block: usize,
        control: &Control,
    ) -> Result<Vec<f64>, String> {
        let done = AtomicUsize::new(0);
        let measured: Result<Vec<Vec<f64>>, String> = crate::worker_pool::install(|| {
            frames
                .par_iter()
                .map(|&frame| {
                    control.check()?;
                    let medians = self.frame_medians(frame, block)?;
                    let n = done.fetch_add(1, Ordering::Relaxed) + 1;
                    control.publish(json!({"running":true,"current":n,"total":frames.len(),"label":"Measuring the cell shadow"}));
                    Ok(medians)
                })
                .collect()
        });
        Ok(measured?.concat())
    }
}
