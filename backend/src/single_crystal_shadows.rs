//! Shared original-count seat/illumination and full-exposure DAC masks.
//! The DAC cone uses PhaseSmith's kernel; the measured seat shadow of the
//! lean mode is estimated natively (see `seat_levels`).
use super::*;
use rayon::prelude::*;
use spots::frame_validity as validity;
#[derive(Clone, Serialize, Deserialize)]
pub(super) struct Shadows {
    pub first: usize,
    pub last: usize,
    pub block: usize,
    pub columns: usize,
    pub cells: usize,
    /// Cells (frame-major) whose centre lies in the measured seat shadow.
    pub illumination: Vec<bool>,
    pub dac: Vec<bool>,
    /// Native seat-shadow field per frame and cell: below `SEAT_EDGE` is
    /// shadow. Pixels interpolate it bilinearly, so the mask edge follows the
    /// shadow smoothly instead of in block steps. Empty for profile masks,
    /// which use `illumination` per block.
    #[serde(default)]
    pub seat: Vec<u8>,
    pub report: Value,
}
/// Seat field level of the shadow edge; kept cells lie below, lit cells above.
const SEAT_EDGE: f32 = 127.;
/// Detector columns `start..end` in block `column` that interpolate between
/// the seat cell columns `x`.
#[derive(Clone, Copy)]
struct Run {
    start: usize,
    end: usize,
    column: usize,
    x: [usize; 2],
}
impl Shadows {
    /// Whether both exclude the same pixels on every frame (the report aside).
    pub fn same_mask(&self, o: &Self) -> bool {
        (self.first, self.last, self.block, self.columns, self.cells)
            == (o.first, o.last, o.block, o.columns, o.cells)
            && self.dac == o.dac
            && self.illumination == o.illumination
            && self.seat == o.seat
    }
    pub fn excluded(&self, frame: usize, pixel: usize, width: usize) -> bool {
        if frame < self.first || frame > self.last {
            return true;
        }
        let (y, x) = (pixel / width, pixel % width);
        let cell =
            (frame - self.first) * self.cells + (y / self.block) * self.columns + x / self.block;
        self.dac.get(cell).copied().unwrap_or(false)
            || if self.seat.is_empty() {
                self.illumination.get(cell).copied().unwrap_or(false)
            } else {
                let [y0, y1, wy] = self.weights(y, self.cells / self.columns);
                let [x0, x1, wx] = self.weights(x, self.columns);
                self.seat_at(frame - self.first, [y0, y1], wy, [x0, x1], wx) < SEAT_EDGE
            }
    }
    /// Neighbouring cell centres of one pixel coordinate and the weight of the second.
    fn weights(&self, i: usize, cells: usize) -> [usize; 3] {
        // Fixed point (1/256) keeps pixel interpolation exact and fast.
        let c = ((2 * i + 1) * 128 / self.block).saturating_sub(128);
        let low = (c / 256).min(cells - 1);
        [low, (low + 1).min(cells - 1), c % 256]
    }
    fn seat_at(&self, local: usize, y: [usize; 2], wy: usize, x: [usize; 2], wx: usize) -> f32 {
        let row = |r: usize| {
            let at = |c: usize| f32::from(self.seat[local * self.cells + r * self.columns + c]);
            at(x[0]) + (at(x[1]) - at(x[0])) * wx as f32 / 256.
        };
        row(y[0]) + (row(y[1]) - row(y[0])) * wy as f32 / 256.
    }
    /// Add this frame's shadows to a full detector mask (row-major). Same
    /// pixels as `excluded` for every pixel.
    ///
    /// A row is walked in runs of pixels that share their block (DAC cell)
    /// and their pair of interpolation columns. The bilinear seat value of a
    /// pixel is a convex combination of its four neighbouring cell values and
    /// is computed exactly (the field holds integers and the weights are
    /// multiples of 1/256, so no product or sum rounds). A run whose four
    /// values all lie on one side of the edge is therefore wholly lit or
    /// wholly shadow and needs no interpolation; only runs across the edge
    /// interpolate per pixel.
    pub fn fill(&self, frame: usize, mask: &mut [bool], width: usize) {
        if frame < self.first || frame > self.last {
            mask.fill(true);
            return;
        }
        let local = frame - self.first;
        let rows = self.cells / self.columns;
        let runs = self.runs(width);
        for (y, row) in mask.chunks_mut(width).enumerate() {
            let base = local * self.cells + (y / self.block) * self.columns;
            let [y0, y1, wy] = self.weights(y, rows);
            for &Run {
                start,
                end,
                column,
                x: [x0, x1],
            } in &runs
            {
                let cell = base + column;
                let row = &mut row[start..end];
                if self.dac.get(cell).copied().unwrap_or(false) {
                    row.fill(true);
                    continue;
                }
                if self.seat.is_empty() {
                    if self.illumination.get(cell).copied().unwrap_or(false) {
                        row.fill(true);
                    }
                    continue;
                }
                let at = |r: usize, c: usize| self.seat[local * self.cells + r * self.columns + c];
                let corners = [at(y0, x0), at(y0, x1), at(y1, x0), at(y1, x1)];
                // u8 field: `>= 127` is the same test as `f32 >= SEAT_EDGE`.
                let edge = SEAT_EDGE as u8;
                if corners.iter().all(|&v| v >= edge) {
                    continue;
                }
                if corners.iter().all(|&v| v < edge) {
                    row.fill(true);
                    continue;
                }
                for (x, m) in (start..end).zip(row) {
                    let [_, _, wx] = self.weights(x, self.columns);
                    *m |= self.seat_at(local, [y0, y1], wy, [x0, x1], wx) < SEAT_EDGE;
                }
            }
        }
    }
    /// Runs of detector columns with the same block and the same pair of
    /// interpolation columns, left to right.
    fn runs(&self, width: usize) -> Vec<Run> {
        let mut runs: Vec<Run> = Vec::new();
        for x in 0..width {
            let [x0, x1, _] = self.weights(x, self.columns);
            let column = x / self.block;
            match runs.last_mut() {
                Some(r) if r.column == column && r.x == [x0, x1] => r.end = x + 1,
                _ => runs.push(Run {
                    start: x,
                    end: x + 1,
                    column,
                    x: [x0, x1],
                }),
            }
        }
        runs
    }
    /// Share of the measured seat-shadow cells that the geometric DAC mask
    /// also excludes. Both describe the same cell body, so a low share means
    /// the declared rotation axis, angles or DAC axis disagree with the data.
    /// Frames the DAC mask closes completely carry no information. None
    /// without both masks or with too little measured shadow to judge.
    pub fn dac_agreement(&self) -> Option<f64> {
        if self.dac.is_empty() || self.illumination.is_empty() || self.cells == 0 {
            return None;
        }
        let (mut both, mut seat) = (0, 0);
        for (dac, measured) in self
            .dac
            .chunks(self.cells)
            .zip(self.illumination.chunks(self.cells))
        {
            if dac.iter().all(|&v| v) {
                continue;
            }
            for (&d, &m) in dac.iter().zip(measured) {
                seat += usize::from(m);
                both += usize::from(m && d);
            }
        }
        (seat >= self.cells / 10).then(|| both as f64 / seat as f64)
    }
}
pub(super) fn fingerprint(values: &[bool]) -> String {
    let mut hash = Sha256::new();
    for chunk in values.chunks(65536) {
        hash.update(chunk.iter().map(|&b| u8::from(b)).collect::<Vec<_>>());
    }
    format!("{:x}", hash.finalize())
}
/// Frames read for the seat shadow: with the DAC cone model (placed where
/// the predicted shadow moves), and evenly spread for plain interpolation.
/// On the ID11 Eiger scan (144 frames), against measuring every frame: 32
/// cone frames differ by 5 px along the edge on average and miss 0.14 % of
/// the shadow; 40 interpolated frames 7 px and 0.07 %. Multiples of the
/// usual worker count keep every worker busy.
const SEAT_FRAMES_CONE: usize = 32;
const SEAT_FRAMES: usize = 40;
/// Smoothing of the block medians, in blocks (Gaussian sigma).
const SEAT_SIGMA: f64 = 2.0;
/// Quantile over frames that gives each block its lit level.
const LIT_QUANTILE: f64 = 0.9;
/// Blocks whose lit level stays below this share of the typical lit level are
/// never lit (beam stop, dead areas) and are not classified by themselves.
const NEVER_LIT: f64 = 0.2;

/// Measured seat (cell-body) shadow from the block medians of some frames.
///
/// Each block's lit level is a high quantile of its smoothed level over the
/// measured frames, so blocks that are lit in only part of the scan are
/// judged against their own background, whatever its absolute count. The lit
/// ratio of a frame that was not measured is interpolated linearly between
/// the nearest measured frames before and after it (the soft shadow edge
/// moves smoothly with the rotation). A block is shadowed when its ratio falls
/// below `threshold`. The shadow enters from the detector edge: shadowed
/// regions that reach the edge are kept, holes in them are filled, and the
/// edge is moved outward by `guard_cells` (fractional blocks). Unusable blocks (module gaps,
/// masked pixels; NaN) are filled by the normalised smoothing, so the shadow
/// continues across module gaps.
pub(super) struct SeatRatios {
    rows: usize,
    columns: usize,
    /// Measured frames (scan-local, ascending) and their lit ratios.
    frames: Vec<usize>,
    ratios: Vec<Vec<f64>>,
    /// Blocks that are lit in some frame; the others stay unknown.
    known: Vec<bool>,
    /// Geometric model for frames that were not measured.
    model: Option<ConeModel>,
}
impl SeatRatios {
    /// `measured` pairs scan-local frame indices (ascending) with medians.
    pub fn new(
        measured: &[(usize, Vec<f64>)],
        [rows, columns]: [usize; 2],
        parallel: bool,
    ) -> Result<Self, String> {
        let cells = rows * columns;
        if cells == 0
            || measured.is_empty()
            || measured.iter().any(|m| m.1.len() != cells)
            || measured.windows(2).any(|w| w[0].0 >= w[1].0)
        {
            return Err("Invalid block medians for the seat shadow.".into());
        }
        let smoothed = map(parallel, measured.len(), &|f| {
            smooth(&measured[f].1, rows, columns)
        });
        // Lit level per block (a row of blocks per task).
        let lit = map(parallel, rows, &|band| -> Vec<f64> {
            let mut values = Vec::with_capacity(smoothed.len());
            (band * columns..(band + 1) * columns)
                .map(|i| {
                    values.clear();
                    values.extend(smoothed.iter().map(|f| f[i]).filter(|v| v.is_finite()));
                    quantile(&mut values, LIT_QUANTILE)
                })
                .collect()
        })
        .concat();
        let mut levels: Vec<f64> = lit.iter().copied().filter(|v| *v > 0.).collect();
        if levels.is_empty() {
            return Err("No frame is lit: the seat shadow cannot be measured.".into());
        }
        let typical = quantile(&mut levels, 0.5);
        let known: Vec<bool> = lit.iter().map(|&l| l >= NEVER_LIT * typical).collect();
        let ratios = smoothed
            .iter()
            .map(|f| {
                f.iter()
                    .zip(&lit)
                    .map(|(&v, &l)| {
                        if l >= NEVER_LIT * typical && v.is_finite() {
                            v / l
                        } else {
                            f64::NAN
                        }
                    })
                    .collect()
            })
            .collect();
        Ok(Self {
            rows,
            columns,
            frames: measured.iter().map(|m| m.0).collect(),
            ratios,
            known,
            model: None,
        })
    }
    /// Predict frames that were not measured from the DAC cone: the lit
    /// ratio as a function of the angle past the cone and the azimuth around
    /// the cell axis, learned from the measured frames. `coordinates[frame]`
    /// gives both per block for every frame (see `Rotation::cone_coordinates`).
    pub fn with_cone(mut self, coordinates: Arc<Vec<Vec<[f32; 2]>>>) -> Self {
        let mut sum = vec![0.; PAST_BINS * AZIMUTH_BINS];
        let mut count = vec![0usize; PAST_BINS * AZIMUTH_BINS];
        for (f, ratio) in self.frames.iter().zip(&self.ratios) {
            for (r, &[past, azimuth]) in ratio.iter().zip(&coordinates[*f]) {
                let (past, azimuth) = (f64::from(past), f64::from(azimuth));
                if r.is_finite() {
                    let i = past_bin(past).round() as usize * AZIMUTH_BINS
                        + azimuth_bin(azimuth).round() as usize % AZIMUTH_BINS;
                    sum[i] += r;
                    count[i] += 1;
                }
            }
        }
        let mut table: Vec<f64> = sum
            .iter()
            .zip(&count)
            .map(|(&s, &n)| {
                if n >= MODEL_MIN {
                    s / n as f64
                } else {
                    f64::NAN
                }
            })
            .collect();
        fill_table(&mut table);
        let mut model = ConeModel {
            coordinates,
            table,
            residuals: vec![],
        };
        // Measured deviation from the model on each measured frame.
        model.residuals = self
            .frames
            .iter()
            .zip(&self.ratios)
            .map(|(&f, r)| model.ratios(f).iter().zip(r).map(|(g, r)| r - g).collect())
            .collect();
        self.model = Some(model);
        self
    }
    /// Lit ratio of any frame: measured, or interpolated between the nearest
    /// measured frames (held constant beyond the first and last).
    pub fn ratio(&self, frame: usize) -> Vec<f64> {
        let after = self.frames.partition_point(|&f| f < frame);
        if after < self.frames.len() && self.frames[after] == frame {
            return self.ratios[after].clone();
        }
        if let Some(m) = &self.model {
            let here = m.ratios(frame);
            // Model plus the measured deviation from it, interpolated
            // between the nearest measured frames.
            let residual = |i: usize| -> &Vec<f64> { &m.residuals[i] };
            let (before, after_r, t) = if after == 0 {
                (residual(0), None, 0.)
            } else if after == self.frames.len() {
                (residual(after - 1), None, 0.)
            } else {
                let (a, b) = (self.frames[after - 1], self.frames[after]);
                (
                    residual(after - 1),
                    Some(residual(after)),
                    (frame - a) as f64 / (b - a) as f64,
                )
            };
            return (0..here.len())
                .map(|i| {
                    if !self.known[i] {
                        return f64::NAN;
                    }
                    let x = before[i];
                    let d = match after_r {
                        Some(y) => match (x.is_nan(), y[i].is_nan()) {
                            (false, false) => x + (y[i] - x) * t,
                            (true, false) => y[i],
                            (false, true) => x,
                            (true, true) => 0.,
                        },
                        None => {
                            if x.is_nan() {
                                0.
                            } else {
                                x
                            }
                        }
                    };
                    here[i] + d
                })
                .collect();
        }
        if after == 0 {
            return self.ratios[0].clone();
        }
        if after == self.frames.len() {
            return self.ratios[after - 1].clone();
        }
        let (a, b) = (self.frames[after - 1], self.frames[after]);
        let t = (frame - a) as f64 / (b - a) as f64;
        self.ratios[after - 1]
            .iter()
            .zip(&self.ratios[after])
            .map(|(&x, &y)| match (x.is_nan(), y.is_nan()) {
                (false, false) => x + (y - x) * t,
                (true, _) => y,
                (false, true) => x,
            })
            .collect()
    }
    /// Leave-one-out check of the cone model: each inner measured frame is
    /// predicted from its neighbours, by plain interpolation and by the cone
    /// model plus interpolated deviation. Returns the blocks classified
    /// wrongly by each (interpolation, cone). Without a model both are equal.
    pub fn held_out_errors(&self, threshold: f64) -> (usize, usize) {
        let Some(m) = &self.model else {
            return (0, 0);
        };
        let inner = self.frames.len().saturating_sub(2);
        let counts = map(true, inner, &|k| -> (usize, usize) {
            let i = k + 1;
            let (a, f, b) = (self.frames[i - 1], self.frames[i], self.frames[i + 1]);
            let t = (f - a) as f64 / (b - a) as f64;
            let gf = m.ratios(f);
            let (ra, rb) = (&m.residuals[i - 1], &m.residuals[i + 1]);
            let (mut plain, mut cone) = (0, 0);
            for c in 0..gf.len() {
                let (x, r, y) = (
                    self.ratios[i - 1][c],
                    self.ratios[i][c],
                    self.ratios[i + 1][c],
                );
                if !(x.is_finite() && r.is_finite() && y.is_finite()) {
                    continue;
                }
                let shadow = r < threshold;
                plain += usize::from((x + (y - x) * t < threshold) != shadow);
                let d = ra[c] + (rb[c] - ra[c]) * t;
                cone += usize::from((gf[c] + d < threshold) != shadow);
            }
            (plain, cone)
        });
        counts.iter().fold((0, 0), |s, c| (s.0 + c.0, s.1 + c.1))
    }
    pub fn measured(&self) -> &[usize] {
        &self.frames
    }
    /// Seat field (see `Shadows::seat`) of frames `0..frames`, frame-major.
    pub fn levels(
        &self,
        frames: usize,
        threshold: f64,
        guard_cells: f64,
        parallel: bool,
    ) -> Vec<u8> {
        map(parallel, frames, &|f| -> Vec<u8> {
            frame_field(
                &self.ratio(f),
                self.rows,
                self.columns,
                threshold,
                guard_cells,
            )
            .iter()
            .map(|&v| (v / threshold * 128.).clamp(0., 255.) as u8)
            .collect()
        })
        .concat()
    }
}

/// Cone model table: angle past the cone from -PAST_RANGE to +PAST_RANGE in
/// PAST_STEP bins, azimuth in AZIMUTH_BINS around the circle.
const PAST_RANGE: f64 = 20.;
const PAST_STEP: f64 = 0.25;
const PAST_BINS: usize = (2. * PAST_RANGE / PAST_STEP) as usize + 1;
const AZIMUTH_BINS: usize = 72;
/// Blocks needed for a table bin.
const MODEL_MIN: usize = 3;
fn past_bin(past: f64) -> f64 {
    ((past + PAST_RANGE) / PAST_STEP).clamp(0., (PAST_BINS - 1) as f64)
}
fn azimuth_bin(azimuth: f64) -> f64 {
    azimuth.rem_euclid(360.) / 360. * AZIMUTH_BINS as f64
}
struct ConeModel {
    coordinates: Arc<Vec<Vec<[f32; 2]>>>,
    table: Vec<f64>,
    /// Measured minus modelled ratio of each measured frame.
    residuals: Vec<Vec<f64>>,
}
impl ConeModel {
    /// Modelled ratio of every block of one frame.
    fn ratios(&self, frame: usize) -> Vec<f64> {
        self.coordinates[frame]
            .iter()
            .map(|&[p, a]| self.at(f64::from(p), f64::from(a)))
            .collect()
    }
    /// Bilinear lookup (azimuth wraps around).
    fn at(&self, past: f64, azimuth: f64) -> f64 {
        let p = past_bin(past);
        let a = azimuth_bin(azimuth);
        let (p0, a0) = (p.floor() as usize, a.floor() as usize);
        let (p1, a1) = ((p0 + 1).min(PAST_BINS - 1), (a0 + 1) % AZIMUTH_BINS);
        let (tp, ta) = (p - p0 as f64, a - a0 as f64);
        let v = |p: usize, a: usize| self.table[p * AZIMUTH_BINS + a % AZIMUTH_BINS];
        let low = v(p0, a0) + (v(p0, a1) - v(p0, a0)) * ta;
        let high = v(p1, a0) + (v(p1, a1) - v(p1, a0)) * ta;
        low + (high - low) * tp
    }
}
/// Fill empty bins: along the angle past the cone within each azimuth
/// (linear, held at the ends), then empty azimuths from their neighbours
/// around the circle; an empty table becomes lit inside / dark outside.
fn fill_table(table: &mut [f64]) {
    let mut filled = [false; AZIMUTH_BINS];
    for a in 0..AZIMUTH_BINS {
        let known: Vec<usize> = (0..PAST_BINS)
            .filter(|&p| table[p * AZIMUTH_BINS + a].is_finite())
            .collect();
        if known.is_empty() {
            continue;
        }
        filled[a] = true;
        for p in 0..PAST_BINS {
            let after = known.partition_point(|&k| k < p);
            let v = if after == 0 {
                table[known[0] * AZIMUTH_BINS + a]
            } else if after == known.len() {
                table[known[after - 1] * AZIMUTH_BINS + a]
            } else {
                let (k0, k1) = (known[after - 1], known[after]);
                let (v0, v1) = (table[k0 * AZIMUTH_BINS + a], table[k1 * AZIMUTH_BINS + a]);
                v0 + (v1 - v0) * (p - k0) as f64 / (k1 - k0) as f64
            };
            table[p * AZIMUTH_BINS + a] = v;
        }
    }
    let have: Vec<usize> = (0..AZIMUTH_BINS).filter(|&a| filled[a]).collect();
    for a in (0..AZIMUTH_BINS).filter(|&a| !filled[a]) {
        if have.is_empty() {
            for p in 0..PAST_BINS {
                table[p * AZIMUTH_BINS + a] = if p * 2 < PAST_BINS { 1. } else { 0. };
            }
            continue;
        }
        let after = have.partition_point(|&k| k < a);
        let (lo, hi) = (
            have[(after + have.len() - 1) % have.len()],
            have[after % have.len()],
        );
        let span = (hi + AZIMUTH_BINS - lo) % AZIMUTH_BINS;
        let t = if span == 0 {
            0.
        } else {
            ((a + AZIMUTH_BINS - lo) % AZIMUTH_BINS) as f64 / span as f64
        };
        for p in 0..PAST_BINS {
            let (x, y) = (table[p * AZIMUTH_BINS + lo], table[p * AZIMUTH_BINS + hi]);
            table[p * AZIMUTH_BINS + a] = x + (y - x) * t;
        }
    }
}

/// `count` frames to measure, denser where the predicted shadow changes
/// fast: the first, middle and last frame, the rest at equal steps of the
/// accumulated change of the predicted shadow share (`predicted[f]`, the
/// share of blocks outside the DAC cone on frame f).
pub(super) fn seat_sample_by_motion(predicted: &[f64], count: usize) -> Vec<usize> {
    let n = predicted.len();
    let mut picked = vec![0, n / 2, n - 1];
    let mut total = vec![0.; n];
    for f in 1..n {
        total[f] = total[f - 1] + (predicted[f] - predicted[f - 1]).abs();
    }
    let last = total[n - 1];
    let k = count.saturating_sub(3);
    for i in 1..=k {
        let target = last * i as f64 / (k + 1) as f64;
        picked.push(total.partition_point(|&v| v < target).min(n - 1));
    }
    picked.sort_unstable();
    picked.dedup();
    // Fill up duplicates with the middle of the widest gaps.
    while picked.len() < count.min(n) {
        let (i, _) = picked
            .windows(2)
            .enumerate()
            .max_by_key(|(_, w)| w[1] - w[0])
            .unwrap();
        let mid = (picked[i] + picked[i + 1]) / 2;
        if mid == picked[i] {
            break;
        }
        picked.insert(i + 1, mid);
    }
    picked
}

fn map<T: Send>(parallel: bool, n: usize, f: &(dyn Fn(usize) -> T + Sync)) -> Vec<T> {
    if parallel {
        crate::worker_pool::install(|| (0..n).into_par_iter().map(f).collect())
    } else {
        (0..n).map(f).collect()
    }
}

/// Normalised separable Gaussian: NaN blocks carry no weight.
fn smooth(values: &[f64], rows: usize, columns: usize) -> Vec<f64> {
    let radius = (3. * SEAT_SIGMA).ceil() as isize;
    let kernel: Vec<f64> = (-radius..=radius)
        .map(|d| (-0.5 * (d as f64 / SEAT_SIGMA).powi(2)).exp())
        .collect();
    let pass = |sum: &[f64], weight: &[f64], along_rows: bool| {
        let (mut s, mut w) = (vec![0.; sum.len()], vec![0.; sum.len()]);
        for y in 0..rows {
            for x in 0..columns {
                for (k, &g) in kernel.iter().enumerate() {
                    let d = k as isize - radius;
                    let (yy, xx) = if along_rows {
                        (y as isize, x as isize + d)
                    } else {
                        (y as isize + d, x as isize)
                    };
                    if yy < 0 || xx < 0 || yy >= rows as isize || xx >= columns as isize {
                        continue;
                    }
                    let j = yy as usize * columns + xx as usize;
                    s[y * columns + x] += g * sum[j];
                    w[y * columns + x] += g * weight[j];
                }
            }
        }
        (s, w)
    };
    let weight: Vec<f64> = values
        .iter()
        .map(|v| f64::from(u8::from(v.is_finite())))
        .collect();
    let sum: Vec<f64> = values
        .iter()
        .map(|&v| if v.is_finite() { v } else { 0. })
        .collect();
    let (sum, weight) = pass(&sum, &weight, true);
    let (sum, weight) = pass(&sum, &weight, false);
    sum.iter()
        .zip(&weight)
        .map(|(&s, &w)| if w > 1e-3 { s / w } else { f64::NAN })
        .collect()
}

/// Linear-interpolated quantile; NaN for no values.
fn quantile(values: &mut [f64], q: f64) -> f64 {
    if values.is_empty() {
        return f64::NAN;
    }
    values.sort_unstable_by(f64::total_cmp);
    let at = q * (values.len() - 1) as f64;
    let low = at.floor() as usize;
    let high = at.ceil() as usize;
    values[low] + (values[high] - values[low]) * (at - low as f64)
}

/// One frame's seat field from its lit ratios (NaN: unknown): below
/// `threshold` is shadow.
fn frame_field(ratio: &[f64], rows: usize, columns: usize, threshold: f64, guard: f64) -> Vec<f64> {
    let cells = rows * columns;
    let border = |i: usize| {
        i < columns
            || i >= cells - columns
            || i.is_multiple_of(columns)
            || i % columns == columns - 1
    };
    let neighbours = |i: usize| {
        let (y, x) = (i / columns, i % columns);
        [
            (y > 0).then(|| i - columns),
            (y + 1 < rows).then(|| i + columns),
            (x > 0).then(|| i - 1),
            (x + 1 < columns).then(|| i + 1),
        ]
        .into_iter()
        .flatten()
    };
    // Flood from the detector edge through cells that pass `open`.
    let flood = |open: &dyn Fn(usize) -> bool| {
        let mut seen = vec![false; cells];
        let mut queue: std::collections::VecDeque<usize> =
            (0..cells).filter(|&i| border(i) && open(i)).collect();
        for &i in &queue {
            seen[i] = true;
        }
        while let Some(i) = queue.pop_front() {
            for j in neighbours(i) {
                if !seen[j] && open(j) {
                    seen[j] = true;
                    queue.push_back(j);
                }
            }
        }
        seen
    };
    let dark = |i: usize| ratio[i] < threshold;
    // Shadow reached from the edge; unknown blocks may connect it.
    let reached = flood(&|i| dark(i) || ratio[i].is_nan());
    let kept: Vec<bool> = (0..cells).map(|i| reached[i] && dark(i)).collect();
    // Everything the lit area cannot reach from the edge is enclosed shadow.
    let outside = flood(&|i| !kept[i]);
    let mut field: Vec<f64> = (0..cells)
        .map(|i| {
            if outside[i] {
                if ratio[i].is_nan() {
                    1.
                } else {
                    ratio[i].max(threshold)
                }
            } else if ratio[i].is_nan() {
                0.
            } else {
                ratio[i].min(0.99 * threshold)
            }
        })
        .collect();
    if guard > 0. {
        // Minimum over a disc moves the edge outward, keeping its shape. A
        // margin between whole blocks blends the discs of the neighbouring
        // radii: the field only decreases with the margin, and the edge moves
        // about one pixel per pixel of margin.
        let erode = |field: &[f64], g: isize| -> Vec<f64> {
            if g == 0 {
                return field.to_vec();
            }
            let offsets: Vec<(isize, isize)> = (-g..=g)
                .flat_map(|dy| (-g..=g).map(move |dx| (dy, dx)))
                .filter(|(dy, dx)| dy * dy + dx * dx <= g * g)
                .collect();
            (0..cells)
                .map(|i| {
                    let (y, x) = ((i / columns) as isize, (i % columns) as isize);
                    offsets
                        .iter()
                        .filter_map(|(dy, dx)| {
                            let (yy, xx) = (y + dy, x + dx);
                            (yy >= 0 && xx >= 0 && yy < rows as isize && xx < columns as isize)
                                .then(|| field[yy as usize * columns + xx as usize])
                        })
                        .fold(f64::INFINITY, f64::min)
                })
                .collect()
        };
        let whole = guard.floor();
        let part = guard - whole;
        let inner = erode(&field, whole as isize);
        field = if part > 1e-9 {
            let outer = erode(&field, whole as isize + 1);
            inner
                .iter()
                .zip(&outer)
                .map(|(a, b)| a + (b - a) * part)
                .collect()
        } else {
            inner
        };
    }
    field
}

impl Crystal {
    /// Seat field of frames `first..=last` from a few measured frames.
    ///
    /// With a calibration, `SEAT_FRAMES_CONE` frames are read where the DAC
    /// cone predicts the shadow to move most, and the others follow the cone
    /// model plus the measured deviation from it. A leave-one-out check on the
    /// measured frames keeps that only when it predicts them better than plain
    /// interpolation (wrong axis, angles or no cell body shadow otherwise);
    /// then, as without a calibration, `SEAT_FRAMES` evenly spread frames are
    /// read and interpolated. Short scans are measured on every frame.
    pub(super) fn measure_seat(
        &self,
        first: usize,
        last: usize,
        dims: [usize; 2],
        block: usize,
        control: &Control,
    ) -> Result<(Vec<u8>, Value), String> {
        let clock = std::time::Instant::now();
        let frames = last - first + 1;
        let (threshold, guard) = (
            self.config.seat_threshold,
            // The margin in blocks, fractional: it acts in pixels.
            self.config.seat_guard as f64 / block as f64,
        );
        let usable = |f: usize| !self.excluded_frames.contains(&(first + f));
        // Nearest usable frames to the wanted ones, each once.
        let choose = |wanted: Vec<usize>, have: &[usize]| -> Vec<usize> {
            let mut out: Vec<usize> = vec![];
            for w in wanted {
                if let Some(f) = (0..frames)
                    .filter(|&f| usable(f) && !have.contains(&f) && !out.contains(&f))
                    .min_by_key(|&f| (f.abs_diff(w), f))
                {
                    out.push(f);
                }
            }
            out
        };
        let mut measured: Vec<(usize, Vec<f64>)> = vec![];
        let read =
            |list: Vec<usize>, measured: &mut Vec<(usize, Vec<f64>)>| -> Result<(), String> {
                let scan: Vec<usize> = list.iter().map(|f| first + f).collect();
                let found = self.cached_medians(&scan, block, control)?;
                measured.extend(list.into_iter().zip(found).map(|(f, m)| (f, (*m).clone())));
                measured.sort_unstable_by_key(|m| m.0);
                Ok(())
            };
        // Cone coordinates of every block on every frame, when calibrated.
        let cone = self.initial_geometry.and_then(|g| {
            let rotation = dac_fit::Rotation::new(&self.config, &g).ok()?;
            let rays = dac_fit::block_rays(&g, self.shape, block).ok()?;
            let (start, opening) = (self.config.omega_start, self.config.dac_half_opening);
            Some(Arc::new(map(true, frames, &|f| -> Vec<[f32; 2]> {
                rotation
                    .cone_coordinates(&rays, start, opening, first + f)
                    .iter()
                    .map(|&[p, a]| [p as f32, a as f32])
                    .collect()
            })))
        });
        let evenly = |count: usize| -> Vec<usize> {
            (0..count.min(frames))
                .map(|i| i * (frames - 1) / (count.min(frames) - 1).max(1))
                .collect()
        };
        let mut route = "interpolated";
        let mut held_out = Value::Null;
        let ratios = if frames <= SEAT_FRAMES {
            read(choose((0..frames).collect(), &[]), &mut measured)?;
            route = "every frame";
            SeatRatios::new(&measured, dims, true)?
        } else if let Some(coordinates) = cone {
            let predicted: Vec<f64> = coordinates
                .iter()
                .map(|c| c.iter().filter(|c| c[0] > 0.).count() as f64 / c.len() as f64)
                .collect();
            read(
                choose(seat_sample_by_motion(&predicted, SEAT_FRAMES_CONE), &[]),
                &mut measured,
            )?;
            let modelled = SeatRatios::new(&measured, dims, true)?.with_cone(coordinates);
            let (plain, by_cone) = modelled.held_out_errors(threshold);
            held_out = json!({"interpolation": plain, "cone": by_cone});
            if by_cone <= plain {
                route = "DAC cone model";
                modelled
            } else {
                let have: Vec<usize> = measured.iter().map(|m| m.0).collect();
                read(choose(evenly(SEAT_FRAMES), &have), &mut measured)?;
                SeatRatios::new(&measured, dims, true)?
            }
        } else {
            read(choose(evenly(SEAT_FRAMES), &[]), &mut measured)?;
            SeatRatios::new(&measured, dims, true)?
        };
        let reading = clock.elapsed().as_secs_f64();
        control.check()?;
        let levels = ratios.levels(frames, threshold, guard, true);
        let report = json!({
            "route": route,
            "frames": ratios.measured().iter().map(|f| f + first).collect::<Vec<_>>(),
            "heldOutErrors": held_out,
            "seconds": {"read": reading, "estimate": clock.elapsed().as_secs_f64() - reading},
        });
        Ok((levels, report))
    }
    /// Prepare the enabled DAC mask and seat shadow and use them.
    pub(super) fn prepare_shadows(&mut self, control: &Control) -> Result<(), String> {
        if !(self.config.dac_on() || self.config.seat_on()) {
            if self.independent_masks() {
                self.activate_masks();
            }
            return Ok(());
        }
        if self.independent_masks() {
            let (dac, seat) = self.ensure_fast(control);
            dac?;
            seat?;
            self.activate_masks();
            return Ok(());
        }
        if self.shadows.is_some() {
            return Ok(());
        }
        let dac = if self.config.dac_on() {
            Some(Arc::new(self.dac_mask_frames(control)?))
        } else {
            None
        };
        let seat = if self.config.seat_on() {
            let (first, last) = self.mask_frames()?;
            let dims = self.mask_dims()?;
            let (levels, report) =
                self.measure_seat(first, last, dims, self.config.shadow_block, control)?;
            Some(Arc::new(masks::SeatPart { levels, report }))
        } else {
            None
        };
        self.shadows = Some(Arc::new(self.combined_shadows(dac, seat)?));
        Ok(())
    }
    /// The full-exposure DAC opening mask of every usable frame, frame-major.
    pub(super) fn dac_mask_frames(&self, control: &Control) -> Result<Vec<bool>, String> {
        let (first, last) = self.mask_frames()?;
        let shape = self.mask_shape()?;
        let mut g = self
            .initial_geometry
            .ok_or("Load a detector calibration before preparing DAC shadows.")?
            .native();
        g.axis = self.config.axis;
        let config = &self.config;
        // Frames are independent pure geometry; order is kept.
        let frames: Result<Vec<Vec<bool>>, String> = crate::worker_pool::install(|| {
            (first..=last)
                .into_par_iter()
                .map(|frame| {
                    control.check()?;
                    let low = config.omega_start + frame as f64 * config.omega_step;
                    validity::dac_mask(
                        g,
                        [low, low + config.exposure],
                        shape,
                        validity::DacOptions {
                            axis_at_zero: config.dac_axis,
                            half_opening_degrees: config.dac_half_opening,
                        },
                    )
                    .map(|mask| mask.excluded)
                    .map_err(err)
                })
                .collect()
        });
        Ok(frames?.concat())
    }
    fn mask_shape(&self) -> Result<validity::Shape, String> {
        let shape = validity::Shape {
            height: self.shape[0],
            width: self.shape[1],
            block: self.config.shadow_block,
        };
        let [rows, columns] = shape.coarse().map_err(err)?;
        let (first, last) = self.mask_frames()?;
        if (last - first + 1)
            .checked_mul(rows * columns)
            .is_none_or(|n| n > validity::MAX_CELLS)
        {
            return Err("Shadow mask exceeds the native coarse-cell budget; increase block size or reduce scan length.".into());
        }
        Ok(shape)
    }
    /// One shadow product from the DAC mask and the seat shadow in use.
    pub(super) fn combined_shadows(
        &self,
        dac: Option<Arc<Vec<bool>>>,
        seat: Option<Arc<masks::SeatPart>>,
    ) -> Result<Shadows, String> {
        let (first, last) = self.mask_frames()?;
        let shape = self.mask_shape()?;
        let [rows, columns] = shape.coarse().map_err(err)?;
        let dac: Vec<bool> = dac.map(|d| (*d).clone()).unwrap_or_default();
        let (levels, seat_report) = seat.map_or((vec![], Value::Null), |s| {
            (s.levels.clone(), s.report.clone())
        });
        let illumination: Vec<bool> = levels.iter().map(|&v| f32::from(v) < SEAT_EDGE).collect();
        let report = json!({"first":first,"last":last,"block":shape.block,"coarseShape":[rows,columns],"illuminationSha256":fingerprint(&illumination),"dacSha256":fingerprint(&dac),"illuminationExcluded":illumination.iter().filter(|&&v|v).count(),"dacExcluded":dac.iter().filter(|&&v|v).count(),"seat":"native: smoothed block medians relative to each block's lit level; measured frames plus DAC cone model or interpolation; edge-connected, holes filled, bilinear pixel edge","seatThreshold":self.config.seat_threshold,"seatGuard":self.config.seat_guard,"seatMeasurement":seat_report,"geometry":"initial calibrated affine geometry; whole closed exposure and whole block footprint","intensities":"original counts, never divided by illumination scale"});
        Ok(Shadows {
            first,
            last,
            block: shape.block,
            columns,
            cells: rows * columns,
            illumination,
            dac,
            seat: levels,
            report,
        })
    }
}
