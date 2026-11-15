//! Per-frame exclusion of diamond-anvil reflections in a rotation series.
//!
//! Diamond reflections are found by shape and behaviour, not by brightness:
//! they are broad (on the ID11 Eiger scan about 20 px wide at half maximum,
//! from barely above background to millions of counts), they stay on the
//! detector for several frames of the rotation, and their centre lies near a
//! cubic-diamond spacing (+0.4…+1.2 % on that scan, the anvils sit off the
//! sample position). Sample reflections are compact (a few pixels) and seen
//! on one or two frames, so they are kept. Regions are significant excess
//! counts in 4×4-pixel bins over a local background (32 px block medians).
//! Source counts are never changed.
use super::*;
use rayon::prelude::*;
use std::collections::{BTreeMap, BTreeSet};

/// Ambient cubic-diamond lattice parameter, Å.
const DIAMOND_A: f64 = 3.567;
/// Pixels along a bin side, and along a background block side.
const BIN: usize = 4;
const BLOCK: usize = 32;
/// Count histogram length for the background medians.
const HISTOGRAM: usize = 4096;
/// Lowest detection level (excess counts of a bin in Poisson deviations of its
/// background): every bin above it is kept, so any level from here up is a
/// re-filter of the same scan.
pub(super) const MIN_LEVEL: f64 = 3.;
/// A 3×3-scale region is diffuse (a broad spot) when no bin holds more than
/// this share of its excess; sharp spots hold most of it in one bin (Eiger
/// scan: sample spots 0.5-0.9, broad diamond blobs 0.05-0.1).
const MAX_PEAK_SHARE: f64 = 0.3;
/// A region continues on the next frame within this distance, pixels.
const LINK: f64 = 24.;
/// Diamond reflections are seen on at least this many consecutive frames.
pub(super) const MIN_FRAMES: usize = 2;

#[derive(Serialize, Deserialize)]
pub(super) struct Diamonds {
    /// Per scan frame, sorted excluded pixel indices.
    pub frames: Vec<Vec<u32>>,
    /// Number of accepted diamond spots over the scan.
    pub regions: usize,
}

/// Distinct d-spacings (Å) of kinematically allowed cubic-diamond reflections
/// down to `d_min`: unmixed parity, and h+k+l divisible by four when even.
pub(super) fn spacings(d_min: f64) -> Vec<f64> {
    let ratio = DIAMOND_A / d_min;
    let limit = ratio.ceil() as i64;
    let mut norms = BTreeSet::new();
    for h in 0..=limit {
        for k in 0..=h {
            for l in 0..=k {
                let n = h * h + k * k + l * l;
                if n == 0 || h % 2 != k % 2 || k % 2 != l % 2 {
                    continue;
                }
                if h % 2 == 0 && (h + k + l) % 4 != 0 {
                    continue;
                }
                if n as f64 <= ratio * ratio {
                    norms.insert(n);
                }
            }
        }
    }
    norms
        .into_iter()
        .map(|n| DIAMOND_A / (n as f64).sqrt())
        .collect()
}

/// Detector-pixel spacing in Å from the calibrated affine geometry.
fn spacing(g: &reciprocal::Geometry, x: f64, y: f64) -> f64 {
    let ray: V3 = std::array::from_fn(|k| g.origin[k] + x * g.fast[k] + y * g.slow[k]);
    let unit = |v: V3| {
        let n = fft::dot(v, v).sqrt();
        v.map(|c| c / n)
    };
    let cos = fft::dot(unit(ray), unit(g.beam)).clamp(-1., 1.);
    g.wavelength / (2. * (cos.acos() / 2.).sin())
}

/// Pixels of one frame in detector order, with their usability (not an
/// unusable or masked pixel). Implemented for decoded counts with their base
/// mask and for stored integer rows, so both give the same regions.
pub(super) trait FramePixels: Sync {
    fn value(&self, i: usize) -> f64;
    fn usable(&self, i: usize) -> bool;
    /// One detector row; unusable pixels as NaN.
    fn row(&self, y: usize, width: usize, out: &mut [f64]) {
        for (x, v) in out.iter_mut().enumerate() {
            let i = y * width + x;
            *v = if self.usable(i) {
                self.value(i)
            } else {
                f64::NAN
            };
        }
    }
}
pub(super) struct Decoded<'a> {
    pub values: &'a [f64],
    pub excluded: &'a [bool],
}
impl FramePixels for Decoded<'_> {
    fn value(&self, i: usize) -> f64 {
        self.values[i]
    }
    fn usable(&self, i: usize) -> bool {
        !self.excluded[i] && self.values[i].is_finite()
    }
}

/// A broad region of one frame, independent of the diamond settings: its
/// area (usable pixels of its significant bins), its centre (excess weighted
/// over the bins above half maximum, detector pixels), the d-spacing there, its pixels (sorted; the
/// margin is added when it is accepted) and on how many consecutive frames
/// it is seen (set when all frames are known, see `link`).
#[derive(Clone)]
pub(super) struct Candidate {
    pub size: usize,
    pub centre: [f64; 2],
    pub spacing: f64,
    pub pixels: Vec<u32>,
    pub frames: usize,
    /// Largest size along its run of frames (a reflection entering or
    /// leaving is small on its first and last frame).
    pub track_size: usize,
}

/// Median of finite values (NaN without any).
fn median(values: &mut [f32]) -> f32 {
    if values.is_empty() {
        return f32::NAN;
    }
    let m = values.len() / 2;
    *values.select_nth_unstable_by(m, f32::total_cmp).1
}

/// A bin of a frame above MIN_LEVEL on its own or with its neighbours: its
/// index (bin rows of `width / BIN`), significances, excess counts, usable
/// pixels (count and 4×4 bit mask).
#[derive(Clone, Copy)]
pub(super) struct Bin {
    pub index: u32,
    pub level: f32,
    /// Significance of the 3×3 bins around it (12×12 px): broad diffuse
    /// spots stand out here while single bins stay near the noise.
    pub smooth: f32,
    pub excess: f64,
    pub count: u8,
    pub usable: u16,
}
/// One frame's bins above MIN_LEVEL, sorted by index.
#[derive(Clone, Default)]
pub(super) struct Scan {
    pub bins: Vec<Bin>,
}

/// Bin sums of one frame over a local background (32 px block medians);
/// keeps every bin above MIN_LEVEL.
pub(super) fn scan(frame: &impl FramePixels, [h, w]: [usize; 2]) -> Scan {
    let (hb, wb) = (h.div_ceil(BIN), w.div_ceil(BIN));
    let (hk, wk) = (h.div_ceil(BLOCK), w.div_ceil(BLOCK));
    let mut sum = vec![0f64; hb * wb];
    let mut count = vec![0u32; hb * wb];
    let mut blocks = vec![f32::NAN; hk * wk];
    // Block medians from count histograms (background counts are small whole
    // numbers; larger values only count towards the upper half).
    let mut tally = vec![0u16; wk * HISTOGRAM];
    let mut tallied = vec![0usize; wk];
    let mut row = vec![0f64; w];
    for y in 0..h {
        frame.row(y, w, &mut row);
        let base = (y / BIN) * wb;
        for (k, pixels) in row.chunks(BLOCK).enumerate() {
            let counts = &mut tally[k * HISTOGRAM..(k + 1) * HISTOGRAM];
            // The background median samples every other pixel of every other row.
            let sampled = y % 2 == 0;
            for (j, bin) in pixels.chunks(BIN).enumerate() {
                let (mut total, mut n) = (0., 0u32);
                for (i, &v) in bin.iter().enumerate() {
                    if v.is_finite() {
                        total += v;
                        n += 1;
                        if sampled && i % 2 == 0 {
                            counts[(v.max(0.) as usize).min(HISTOGRAM - 1)] += 1;
                            tallied[k] += 1;
                        }
                    }
                }
                let b = base + k * (BLOCK / BIN) + j;
                sum[b] += total;
                count[b] += n;
            }
        }
        if (y + 1) % BLOCK == 0 || y + 1 == h {
            for k in 0..wk {
                let counts = &mut tally[k * HISTOGRAM..(k + 1) * HISTOGRAM];
                if tallied[k] > 0 {
                    let half = tallied[k] / 2;
                    let mut seen = 0usize;
                    for (v, &c) in counts.iter().enumerate() {
                        seen += usize::from(c);
                        if seen > half {
                            blocks[(y / BLOCK) * wk + k] = v as f32;
                            break;
                        }
                    }
                }
                counts.fill(0);
                tallied[k] = 0;
            }
        }
    }
    let mut known: Vec<f32> = blocks.iter().copied().filter(|v| v.is_finite()).collect();
    let typical = median(&mut known);
    if !typical.is_finite() {
        return Scan::default();
    }
    for v in &mut blocks {
        if !v.is_finite() {
            *v = typical;
        }
    }
    // Background of each bin: block medians interpolated bilinearly at the
    // bin centre (first along x for every block row, then along y).
    let weights = |bins: usize, blocks: usize| -> Vec<(usize, usize, f64)> {
        (0..bins)
            .map(|i| {
                let f = ((i * BIN) as f64 + BIN as f64 / 2.) / BLOCK as f64 - 0.5;
                let low = f.floor().clamp(0., (blocks - 1) as f64) as usize;
                let high = (low + 1).min(blocks - 1);
                (low, high, (f - low as f64).clamp(0., 1.))
            })
            .collect()
    };
    let (wx, wy) = (weights(wb, wk), weights(hb, hk));
    let across: Vec<f64> = (0..hk)
        .flat_map(|by| {
            let blocks = &blocks;
            wx.iter().map(move |&(x0, x1, t)| {
                let (a, b) = (
                    f64::from(blocks[by * wk + x0]),
                    f64::from(blocks[by * wk + x1]),
                );
                a + (b - a) * t
            })
        })
        .collect();
    let mut background = vec![0f64; hb * wb];
    for (by, &(y0, y1, t)) in wy.iter().enumerate() {
        for bx in 0..wb {
            let (a, b) = (across[y0 * wb + bx], across[y1 * wb + bx]);
            background[by * wb + bx] = (a + (b - a) * t) * f64::from(count[by * wb + bx]);
        }
    }
    let excess: Vec<f64> = (0..hb * wb).map(|b| sum[b] - background[b]).collect();
    // 3×3-bin sums of excess and background over fully usable bins (bins cut
    // by module gaps or masks, with their bright edge pixels, stay out):
    // separable box sums, rows then columns.
    let full = |b: usize| count[b] as usize == BIN * BIN;
    let box3 = |values: &[f64]| -> Vec<f64> {
        let mut across = vec![0f64; hb * wb];
        for y in 0..hb {
            for x in 0..wb {
                let mut t = 0.;
                for xx in x.saturating_sub(1)..=(x + 1).min(wb - 1) {
                    let i = y * wb + xx;
                    if full(i) {
                        t += values[i];
                    }
                }
                across[y * wb + x] = t;
            }
        }
        let mut out = vec![0f64; hb * wb];
        for y in 0..hb {
            for x in 0..wb {
                let mut t = 0.;
                for yy in y.saturating_sub(1)..=(y + 1).min(hb - 1) {
                    t += across[yy * wb + x];
                }
                out[y * wb + x] = t;
            }
        }
        out
    };
    let (excess3, background3) = (box3(&excess), box3(&background));
    let mut bins = vec![];
    for b in 0..hb * wb {
        // Only fully usable bins away from module gaps and masks: the edge
        // rows of the modules are slightly brighter.
        let (by, bx) = (b / wb, b % wb);
        let interior = full(b)
            && (by == 0 || full(b - wb))
            && (by + 1 == hb || full(b + wb))
            && (bx == 0 || full(b - 1))
            && (bx + 1 == wb || full(b + 1));
        if !interior {
            continue;
        }
        let level = excess[b] / background[b].max(1.).sqrt();
        let smooth = excess3[b] / background3[b].max(1.).sqrt();
        if level <= MIN_LEVEL && smooth <= MIN_LEVEL {
            continue;
        }
        let (by, bx) = (b / wb, b % wb);
        let mut usable = 0u16;
        for y in by * BIN..((by + 1) * BIN).min(h) {
            for x in bx * BIN..((bx + 1) * BIN).min(w) {
                if frame.usable(y * w + x) {
                    usable |= 1 << ((y - by * BIN) * BIN + x - bx * BIN);
                }
            }
        }
        bins.push(Bin {
            index: b as u32,
            level: level as f32,
            smooth: smooth as f32,
            excess: excess[b],
            count: count[b] as u8,
            usable,
        });
    }
    Scan { bins }
}

/// The regions of one frame at a detection level (see `Candidate`): the
/// connected bins above it, and diffuse regions above it on the 3×3-bin
/// scale. The same as scanning at that level.
pub(super) fn regions(
    scan: &Scan,
    [h, w]: [usize; 2],
    level: f64,
    spacing_of: impl Fn(f64, f64) -> f64,
) -> Vec<Candidate> {
    let (hb, wb) = (h.div_ceil(BIN), w.div_ceil(BIN));
    let bins = &scan.bins;
    let find = |index: usize| bins.binary_search_by_key(&(index as u32), |b| b.index).ok();
    // Connected stored bins that pass `inside`, in index order.
    let components = |inside: &dyn Fn(usize) -> bool| {
        let mut seen = vec![false; bins.len()];
        let mut groups: Vec<Vec<usize>> = vec![];
        for start in 0..bins.len() {
            if seen[start] || !inside(start) {
                continue;
            }
            seen[start] = true;
            let mut region = vec![start];
            let mut next = 0;
            while next < region.len() {
                let b = bins[region[next]].index as usize;
                let (by, bx) = ((b / wb) as isize, (b % wb) as isize);
                for dy in -1..=1isize {
                    for dx in -1..=1isize {
                        let (ny, nx) = (by + dy, bx + dx);
                        if ny < 0 || nx < 0 || ny >= hb as isize || nx >= wb as isize {
                            continue;
                        }
                        if let Some(j) = find(ny as usize * wb + nx as usize)
                            && !seen[j]
                            && inside(j)
                        {
                            seen[j] = true;
                            region.push(j);
                        }
                    }
                }
                next += 1;
            }
            groups.push(region);
        }
        groups
    };
    // Regions of single bins above the level ...
    let mut groups = components(&|i| f64::from(bins[i].level) > level);
    let mut owner: Vec<Option<usize>> = vec![None; bins.len()];
    for (g, region) in groups.iter().enumerate() {
        for &i in region {
            owner[i] = Some(g);
        }
    }
    // ... and diffuse regions above it on the 3×3-bin scale: broad spots
    // whose light is spread too thin for single bins. A region with most of
    // its excess in one bin is a sharp spot seen through the smoothing, not
    // a broad one. A diffuse region joins the single-bin region it overlaps.
    for region in components(&|i| f64::from(bins[i].smooth) > level) {
        let total: f64 = region.iter().map(|&i| bins[i].excess.max(0.)).sum();
        let largest = region.iter().map(|&i| bins[i].excess).fold(0., f64::max);
        if total <= 0. || largest > MAX_PEAK_SHARE * total {
            continue;
        }
        match region.iter().find_map(|&i| owner[i]) {
            Some(g) => {
                for &i in &region {
                    if owner[i].is_none() {
                        owner[i] = Some(g);
                        groups[g].push(i);
                    }
                }
            }
            None => {
                let g = groups.len();
                for &i in &region {
                    owner[i] = Some(g);
                }
                groups.push(region);
            }
        }
    }
    let mut out = vec![];
    for mut region in groups {
        region.sort_unstable();
        let peak = region
            .iter()
            .map(|&i| bins[i].excess)
            .fold(f64::NEG_INFINITY, f64::max);
        // Size: usable pixels of the whole significant region (an intense
        // spot's half maximum covers only its core); centre: excess-weighted
        // over the bins above half maximum.
        let size = region.iter().map(|&i| usize::from(bins[i].count)).sum();
        let (mut sx, mut sy, mut sw) = (0., 0., 0.);
        for &i in region.iter().filter(|&&i| bins[i].excess >= peak / 2.) {
            let b = bins[i].index as usize;
            let (cy, cx) = (((b / wb) * BIN) as f64 + 1.5, ((b % wb) * BIN) as f64 + 1.5);
            sx += bins[i].excess * cx;
            sy += bins[i].excess * cy;
            sw += bins[i].excess;
        }
        let centre = [sx / sw, sy / sw];
        let mut pixels = vec![];
        for &i in &region {
            let b = bins[i].index as usize;
            let (by, bx) = (b / wb, b % wb);
            for y in by * BIN..((by + 1) * BIN).min(h) {
                for x in bx * BIN..((bx + 1) * BIN).min(w) {
                    if bins[i].usable & (1 << ((y - by * BIN) * BIN + x - bx * BIN)) != 0 {
                        pixels.push((y * w + x) as u32);
                    }
                }
            }
        }
        pixels.sort_unstable();
        out.push(Candidate {
            size,
            centre,
            spacing: spacing_of(centre[0], centre[1]),
            pixels,
            frames: 1,
            track_size: size,
        });
    }
    out
}

/// The regions of one frame at a detection level, scanned directly.
#[cfg(test)]
pub(super) fn candidates(
    frame: &impl FramePixels,
    shape: [usize; 2],
    level: f64,
    spacing_of: impl Fn(f64, f64) -> f64,
) -> Vec<Candidate> {
    regions(&scan(frame, shape), shape, level, spacing_of)
}

/// Set how many consecutive frames each candidate is seen on: a region
/// continues on the next frame where a region's centre lies within LINK
/// pixels (the nearest one, each used once).
pub(super) fn link(frames: &mut [Vec<Candidate>]) {
    let n = frames.len();
    let mut next: Vec<Vec<Option<usize>>> = frames.iter().map(|f| vec![None; f.len()]).collect();
    let mut prev: Vec<Vec<Option<usize>>> = next.clone();
    for f in 0..n.saturating_sub(1) {
        // Regions of the next frame by LINK-sized cell: only neighbouring
        // cells can hold a region within LINK.
        let cell = |c: &Candidate| {
            (
                (c.centre[0] / LINK).floor() as i64,
                (c.centre[1] / LINK).floor() as i64,
            )
        };
        let mut cells: BTreeMap<(i64, i64), Vec<usize>> = BTreeMap::new();
        for (j, b) in frames[f + 1].iter().enumerate() {
            cells.entry(cell(b)).or_default().push(j);
        }
        let mut pairs: Vec<(f64, usize, usize)> = vec![];
        for (i, a) in frames[f].iter().enumerate() {
            let (cx, cy) = cell(a);
            for dy in -1..=1 {
                for dx in -1..=1 {
                    for &j in cells
                        .get(&(cx + dx, cy + dy))
                        .map_or(&[][..], Vec::as_slice)
                    {
                        let b = &frames[f + 1][j];
                        let d = (a.centre[0] - b.centre[0]).hypot(a.centre[1] - b.centre[1]);
                        if d <= LINK {
                            pairs.push((d, i, j));
                        }
                    }
                }
            }
        }
        pairs.sort_by(|a, b| a.0.total_cmp(&b.0).then(a.1.cmp(&b.1)).then(a.2.cmp(&b.2)));
        for (_, i, j) in pairs {
            if next[f][i].is_none() && prev[f + 1][j].is_none() {
                next[f][i] = Some(j);
                prev[f + 1][j] = Some(i);
            }
        }
    }
    // Chain length before (inclusive) and after each candidate.
    let mut before: Vec<Vec<usize>> = frames.iter().map(|f| vec![1; f.len()]).collect();
    for f in 1..n {
        for j in 0..frames[f].len() {
            if let Some(i) = prev[f][j] {
                before[f][j] = before[f - 1][i] + 1;
            }
        }
    }
    let mut after: Vec<Vec<usize>> = frames.iter().map(|f| vec![0; f.len()]).collect();
    for f in (0..n.saturating_sub(1)).rev() {
        for i in 0..frames[f].len() {
            if let Some(j) = next[f][i] {
                after[f][i] = after[f + 1][j] + 1;
            }
        }
    }
    // Largest size before (inclusive) and after, along the same runs.
    let mut big_before: Vec<Vec<usize>> = frames
        .iter()
        .map(|f| f.iter().map(|c| c.size).collect())
        .collect();
    for f in 1..n {
        for j in 0..frames[f].len() {
            if let Some(i) = prev[f][j] {
                big_before[f][j] = big_before[f][j].max(big_before[f - 1][i]);
            }
        }
    }
    let mut big_after: Vec<Vec<usize>> = frames.iter().map(|f| vec![0; f.len()]).collect();
    for f in (0..n.saturating_sub(1)).rev() {
        for i in 0..frames[f].len() {
            if let Some(j) = next[f][i] {
                big_after[f][i] = big_after[f + 1][j].max(frames[f + 1][j].size);
            }
        }
    }
    for f in 0..n {
        for (i, c) in frames[f].iter_mut().enumerate() {
            c.frames = before[f][i] + after[f][i];
            c.track_size = big_before[f][i].max(big_after[f][i]);
        }
    }
}

/// The diamond settings applied to cached candidates.
pub(super) struct Selection<'a> {
    /// Diamond spacings that can reach the detector, Å.
    pub lines: &'a [f64],
    /// Allowed relative deviation from a spacing.
    pub tolerance: f64,
    /// Smallest region area, pixels.
    pub min_size: usize,
    /// Round border added around each accepted spot, pixels.
    pub margin: usize,
    pub shape: [usize; 2],
}

/// `pixels` (sorted) grown by a disc of `radius` pixels, sorted. Only edge
/// pixels can be nearest to a pixel outside the region, so each edge pixel
/// adds its disc as one interval per row; the intervals are merged per row.
pub(super) fn grow(pixels: &[u32], radius: usize, [h, w]: [usize; 2]) -> Vec<u32> {
    if radius == 0 || pixels.is_empty() {
        return pixels.to_vec();
    }
    let inside = |i: usize| pixels.binary_search(&(i as u32)).is_ok();
    let half: Vec<usize> = (0..=radius)
        .map(|dy| ((radius * radius - dy * dy) as f64).sqrt().floor() as usize)
        .collect();
    let mut rows: BTreeMap<usize, Vec<(usize, usize)>> = BTreeMap::new();
    for &p in pixels {
        let p = p as usize;
        let (x, y) = (p % w, p / w);
        let edge = (x > 0 && !inside(p - 1))
            || (x + 1 < w && !inside(p + 1))
            || (y > 0 && !inside(p - w))
            || (y + 1 < h && !inside(p + w));
        if !edge {
            rows.entry(y).or_default().push((x, x));
            continue;
        }
        for yy in y.saturating_sub(radius)..=(y + radius).min(h - 1) {
            let r = half[yy.abs_diff(y)];
            rows.entry(yy)
                .or_default()
                .push((x.saturating_sub(r), (x + r).min(w - 1)));
        }
    }
    let mut out = vec![];
    for (y, mut spans) in rows {
        spans.sort_unstable();
        let (mut a, mut b) = spans[0];
        for &(s0, s1) in &spans[1..] {
            if s0 > b + 1 {
                out.extend((a..=b).map(|x| (y * w + x) as u32));
                (a, b) = (s0, s1);
            } else {
                b = b.max(s1);
            }
        }
        out.extend((a..=b).map(|x| (y * w + x) as u32));
    }
    out
}

/// Accepted diamond spots among a frame's candidates: at least `min_size`
/// pixels of significant region on some frame of its run, seen on MIN_FRAMES consecutive frames, centre near
/// a diamond spacing; each grown by the margin. Returns the sorted excluded
/// pixels and the number of spots.
pub(super) fn accept(candidates: &[Candidate], s: &Selection) -> (Vec<u32>, usize) {
    let mut out = vec![];
    let mut regions = 0;
    for c in candidates {
        if c.track_size < s.min_size
            || c.frames < MIN_FRAMES
            || !s
                .lines
                .iter()
                .any(|line| (c.spacing / line - 1.).abs() <= s.tolerance)
        {
            continue;
        }
        regions += 1;
        out.extend(grow(&c.pixels, s.margin, s.shape));
    }
    out.sort_unstable();
    out.dedup();
    (out, regions)
}

impl Crystal {
    /// Diamond spacings that can reach the detector within the tolerance,
    /// and the tolerance as a fraction.
    pub(super) fn diamond_lines(&self) -> Result<(Vec<f64>, f64), String> {
        let g = self
            .initial_geometry
            .ok_or("Load a calibration before masking diamond spots.")?
            .native();
        let [h, w] = self.shape;
        let d_min = [
            (0., 0.),
            (w as f64 - 1., 0.),
            (0., h as f64 - 1.),
            (w as f64 - 1., h as f64 - 1.),
        ]
        .into_iter()
        .map(|(x, y)| spacing(&g, x, y))
        .fold(f64::INFINITY, f64::min);
        let tolerance = self.config.diamond_tolerance / 100.;
        Ok((spacings(d_min / (1. + tolerance)), tolerance))
    }
    /// Settings-independent scans of every frame, read in parallel.
    pub(super) fn all_diamond_scans(&self, control: &Control) -> Result<Vec<Scan>, String> {
        let frames: Vec<usize> = (0..self.sources.len()).collect();
        let done = std::sync::atomic::AtomicUsize::new(0);
        crate::worker_pool::install(|| {
            frames
                .par_iter()
                .map(|&frame| {
                    control.check()?;
                    let found = self.diamond_scan(frame)?;
                    let n = done.fetch_add(1, std::sync::atomic::Ordering::Relaxed) + 1;
                    control.publish(json!({"running":true,"current":n,"total":frames.len(),"label":"Masking diamond spots"}));
                    Ok(found)
                })
                .collect()
        })
    }
    /// The regions of every frame at the detection level, with their
    /// persistence over the frames.
    pub(super) fn diamond_regions(&self, scans: &[Scan]) -> Result<Vec<Vec<Candidate>>, String> {
        let g = self
            .initial_geometry
            .ok_or("Load a calibration before masking diamond spots.")?
            .native();
        let level = self.config.diamond_level;
        let mut found: Vec<Vec<Candidate>> = crate::worker_pool::install(|| {
            scans
                .par_iter()
                .map(|s| regions(s, self.shape, level, |x, y| spacing(&g, x, y)))
                .collect()
        });
        link(&mut found);
        Ok(found)
    }
    /// One-line account of the prepared masks, as a share of all scan pixels.
    pub(super) fn mask_summary(&self) -> String {
        self.mask_counts().0
    }
    /// The one-line account and the numbers of each mask in use, for the
    /// mask rows: `total` (% of all scan pixels, overlaps counted once),
    /// `dac` and `seat` (% of all scan pixels by shadow cell centre, each on
    /// its own), `diamonds` (spots), `persistent` and `shared` (pixels), and
    /// the DAC `warning` when the mask misses the measured shadow.
    /// Works on the cell grid and pixel runs already in memory; no frame is
    /// read.
    pub(super) fn mask_counts(&self) -> (String, Value) {
        let c = &self.config;
        if !(c.dac_on()
            || c.seat_on()
            || c.diamond_on()
            || self.shared.is_some()
            || self.persistent.is_some())
        {
            return ("No masks".into(), json!({"total": 0.}));
        }
        let pixels = (self.shape[0] * self.shape[1]).max(1) as f64;
        let frames = self.sources.len().max(1) as f64;
        // Mask mode pixels per shadow cell, so pixels already in a shadowed
        // cell are not counted twice.
        let fixed: Vec<_> = self.shared.iter().chain(&self.persistent).collect();
        let shared_cells = (!fixed.is_empty()).then(|| {
            let block = self.shadows.as_ref().map_or(0, |s| s.block);
            let columns = self.shadows.as_ref().map_or(1, |s| s.columns);
            let mut cells = vec![0usize; self.shadows.as_ref().map_or(1, |s| s.cells)];
            for &[a, b] in fixed.iter().flat_map(|m| &m.runs) {
                for i in a as usize..b as usize {
                    let (y, x) = (i / self.shape[1], i % self.shape[1]);
                    let cell = y.checked_div(block).map_or(0, |r| r * columns + x / block);
                    if let Some(c) = cells.get_mut(cell) {
                        *c += 1;
                    }
                }
            }
            cells
        });
        let mut total = 0.;
        // Shadow cells of each kind over the scan (frames outside the cell
        // opening count as fully DAC-masked).
        let (mut dac_cells, mut seat_cells) = (0usize, 0usize);
        for frame in 0..self.sources.len() {
            let mut share = 0.;
            if self.excluded_frames.contains(&frame) {
                share = 1.;
            } else if let Some(s) = &self.shadows {
                if frame < s.first || frame > s.last {
                    share = 1.;
                } else {
                    let on = |v: &[bool], i: usize| v.get(i).copied().unwrap_or(false);
                    let mut open = 0;
                    share = ((frame - s.first) * s.cells..(frame - s.first + 1) * s.cells)
                        .filter(|&i| {
                            let dac = on(&s.dac, i);
                            let seat = on(&s.illumination, i);
                            dac_cells += usize::from(dac);
                            seat_cells += usize::from(seat);
                            let shadowed = dac || seat;
                            if !shadowed && let Some(c) = &shared_cells {
                                open +=
                                    c.get(i - (frame - s.first) * s.cells).copied().unwrap_or(0);
                            }
                            shadowed
                        })
                        .count() as f64
                        / s.cells as f64;
                    share += open as f64 / pixels;
                }
            } else if let Some(c) = &shared_cells {
                share = c.iter().sum::<usize>() as f64 / pixels;
            }
            if let Some(d) = &self.diamonds {
                share += d.frames.get(frame).map_or(0, Vec::len) as f64 / pixels;
            }
            total += share.min(1.);
        }
        let total = 100. * total / frames;
        let mut counts = json!({"total": total});
        if let Some(s) = &self.shadows {
            let outside = self
                .sources
                .len()
                .saturating_sub((s.last + 1).saturating_sub(s.first));
            let all = s.cells.max(1) as f64 * frames;
            if c.dac_on() {
                counts["dac"] = json!(100. * (dac_cells as f64 + (outside * s.cells) as f64) / all);
            }
            if c.seat_on() {
                counts["seat"] = json!(100. * seat_cells as f64 / all);
            }
        }
        // A no-break space keeps the number and its unit on one line.
        let mut summary = format!("{total:.1}\u{a0}% masked");
        if let Some(d) = &self.diamonds {
            let plural = if d.regions == 1 { "" } else { "s" };
            summary += &format!(" · {} diamond spot{plural}", d.regions);
            counts["diamonds"] = json!(d.regions);
        }
        if let Some(p) = &self.persistent {
            summary += &format!(" · {} hot px", p.pixels);
            counts["persistent"] = json!(p.pixels);
        }
        if let Some(m) = &self.shared {
            counts["shared"] = json!(m.pixels);
        }
        if let Some(warning) = self.dac_warning() {
            summary += &format!(" · {warning}");
            counts["warning"] = json!(warning);
        }
        (summary, counts)
    }
    /// The geometric DAC mask must cover the seat shadow measured in the same
    /// frames; otherwise the declared rotation (most often the axis) is wrong
    /// and the DAC mask would hide illuminated data instead of the shadow.
    pub(super) fn dac_warning(&self) -> Option<String> {
        let agreement = self.shadows.as_ref()?.dac_agreement()?;
        (agreement < 0.8).then(|| {
            format!(
                "DAC mask covers only {:.0}\u{a0}% of the measured shadow: check the rotation axis",
                100. * agreement
            )
        })
    }
    /// Exclude broad diamond spots on every processed frame. Lean masks are
    /// independent parts (only unusable pixels are left out, see
    /// `ensure_diamonds`); the joint product of profile recipes prepares the
    /// shadow masks first, so shadowed pixels never seed a region.
    pub(super) fn prepare_diamonds(&mut self, control: &Control) -> Result<(), String> {
        if !self.config.diamond_on() {
            return Ok(());
        }
        let independent = self.independent_masks();
        if independent {
            self.ensure_diamonds(control, true)?;
            self.activate_masks();
            return Ok(());
        }
        if self.diamonds.is_some() {
            return Ok(());
        }
        let scans = self.all_diamond_scans(control)?;
        let found = self.diamond_regions(&scans)?;
        let (lines, tolerance) = self.diamond_lines()?;
        let selection = Selection {
            lines: &lines,
            tolerance,
            min_size: self.config.diamond_min_size,
            margin: self.config.diamond_margin,
            shape: self.shape,
        };
        let found: Vec<(Vec<u32>, usize)> = found.iter().map(|c| accept(c, &selection)).collect();
        let regions = found.iter().map(|f| f.1).sum();
        let d = Diamonds {
            frames: found.into_iter().map(|f| f.0).collect(),
            regions,
        };
        self.diamonds = Some(Arc::new(d));
        Ok(())
    }
}

#[cfg(test)]
pub(super) mod tests {
    use super::*;

    #[test]
    fn diamond_spacings_follow_the_extinction_rules() {
        let d = spacings(1.0);
        let expect = |n: f64| DIAMOND_A / n.sqrt();
        // 111, 220, 311 are allowed; 200 and 222 are absent.
        for n in [3., 8., 11.] {
            assert!(d.iter().any(|v| (v - expect(n)).abs() < 1e-12), "{n}");
        }
        for n in [4., 12.] {
            assert!(d.iter().all(|v| (v - expect(n)).abs() > 1e-6), "{n}");
        }
        assert!(d.iter().all(|&v| v >= 1.0));
    }

    /// Six 200×300 frames, background 30 counts with pixel noise: a faint
    /// broad blob (sigma 8 px, +80 counts) drifting 3 px per frame on frames
    /// 0-4 near a diamond spacing; a very faint one (+8 counts) on frames 0-3; a sharp bright spot (sigma 0.8 px, 5000
    /// counts) on frames 2-3; a faint broad blob on frame 3 only; a faint
    /// broad blob on all frames off every spacing (x > 230).
    pub(in crate::session::single_crystal) fn spot_frames() -> Vec<Vec<f64>> {
        let (h, w) = (200usize, 300usize);
        let mut noise = 11u64;
        (0..6)
            .map(|f| {
                let mut v: Vec<f64> = (0..h * w)
                    .map(|_| {
                        noise = noise
                            .wrapping_mul(6364136223846793005)
                            .wrapping_add(1442695040888963407);
                        30. + ((noise >> 40) % 11) as f64 - 5.
                    })
                    .collect();
                let mut blob = |cx: f64, cy: f64, sigma: f64, peak: f64| {
                    for y in 0..h {
                        for x in 0..w {
                            let r2 = (x as f64 - cx).powi(2) + (y as f64 - cy).powi(2);
                            v[y * w + x] += (peak * (-r2 / (2. * sigma * sigma)).exp()).round();
                        }
                    }
                };
                if f <= 4 {
                    blob(60. + 3. * f as f64, 60., 8., 80.);
                }
                if f == 2 || f == 3 {
                    blob(150., 150., 0.8, 5000.);
                }
                if f == 3 {
                    blob(120., 60., 8., 80.);
                }
                if f <= 3 {
                    blob(100., 150., 8., 8.);
                }
                blob(260., 120., 8., 80.);
                v
            })
            .collect()
    }
    /// Spacing 2.0 Å (+0.6 %) everywhere except right of x = 230 (2.5 Å).
    pub(in crate::session::single_crystal) fn spot_spacing(x: f64, _: f64) -> f64 {
        if x < 230. { 2.012 } else { 2.5 }
    }
    type Found = (Vec<Vec<Candidate>>, Vec<(Vec<u32>, usize)>);
    fn found_frames(min_size: usize, margin: usize) -> Found {
        found_at(min_size, margin, 10.)
    }
    fn found_at(min_size: usize, margin: usize, level: f64) -> Found {
        let (h, w) = (200usize, 300usize);
        let excluded = vec![false; h * w];
        let mut all: Vec<Vec<Candidate>> = spot_frames()
            .iter()
            .map(|v| {
                candidates(
                    &Decoded {
                        values: v,
                        excluded: &excluded,
                    },
                    [h, w],
                    level,
                    spot_spacing,
                )
            })
            .collect();
        link(&mut all);
        let lines = [2.0];
        let selection = Selection {
            lines: &lines,
            tolerance: 0.03,
            min_size,
            margin,
            shape: [h, w],
        };
        let masks = all.iter().map(|c| accept(c, &selection)).collect();
        (all, masks)
    }

    /// The faint broad diamond-like blob is found on every frame it is on;
    /// the sharp bright spot, the one-frame blob and the off-spacing blob are
    /// left alone.
    #[test]
    fn broad_persistent_spots_near_diamond_spacings_are_masked() {
        let w = 300usize;
        let (all, masks) = found_frames(120, 0);
        let masked =
            |f: usize, x: usize, y: usize| masks[f].0.binary_search(&((y * w + x) as u32)).is_ok();
        for (f, m) in masks.iter().enumerate().take(5) {
            assert!(masked(f, 60 + 3 * f, 60), "frame {f}: broad blob");
            assert_eq!(m.1, 1, "frame {f}: one spot");
        }
        assert_eq!(masks[5].1, 0);
        for f in [2, 3] {
            assert!(
                !masked(f, 150, 150),
                "frame {f}: sharp sample-like spot kept"
            );
        }
        assert!(
            !masked(3, 120, 60),
            "a broad blob on one frame is not a diamond reflection"
        );
        for f in 0..6 {
            assert!(!masked(f, 260, 120), "frame {f}: off every diamond spacing");
        }
        // The candidates behind it: the drifting blob is linked over 5 frames,
        // the sharp spot is small, the one-frame blob seen once.
        let at = |f: usize, x: f64, y: f64| {
            all[f]
                .iter()
                .find(|c| (c.centre[0] - x).abs() < 6. && (c.centre[1] - y).abs() < 6.)
                .unwrap()
        };
        assert_eq!(at(2, 66., 60.).frames, 5);
        assert!(at(2, 66., 60.).size >= 200, "{}", at(2, 66., 60.).size);
        assert!(at(2, 150., 150.).size < 120, "{}", at(2, 150., 150.).size);
        assert_eq!(at(3, 120., 60.).frames, 1);
        assert_eq!(at(3, 260., 120.).frames, 6);
    }

    /// A lower detection level finds the very faint broad blob that the
    /// default level misses; the sharp spot stays unmasked at either level.
    #[test]
    fn a_lower_level_finds_fainter_broad_spots() {
        let w = 300usize;
        let hit = |masks: &[(Vec<u32>, usize)], f: usize, x: usize, y: usize| {
            masks[f].0.binary_search(&((y * w + x) as u32)).is_ok()
        };
        let (_, default) = found_at(64, 4, 10.);
        let (_, low) = found_at(64, 4, 4.);
        for f in 0..=3 {
            assert!(!hit(&default, f, 100, 150), "frame {f}: missed at 10 sigma");
            assert!(hit(&low, f, 100, 150), "frame {f}: found at 4 sigma");
            assert!(hit(&low, f, 60 + 3 * f, 60));
        }
        for f in [2, 3] {
            assert!(
                !hit(&low, f, 150, 150),
                "frame {f}: sharp spot kept at 4 sigma"
            );
        }
    }

    /// A diffuse broad blob (sigma 9 px, +10 counts on 30: no single 4×4
    /// bin reaches the level) is found at the default level on the
    /// 3×3-bin scale; a sharp bright spot on three frames is not, although
    /// the smoothing makes it look large.
    #[test]
    fn diffuse_broad_spots_are_found_on_the_coarser_scale() {
        let (h, w) = (200usize, 300usize);
        let mut noise = 5u64;
        let excluded = vec![false; h * w];
        let mut all: Vec<Vec<Candidate>> = (0..5)
            .map(|f| {
                let mut v: Vec<f64> = (0..h * w)
                    .map(|_| {
                        noise = noise
                            .wrapping_mul(6364136223846793005)
                            .wrapping_add(1442695040888963407);
                        30. + ((noise >> 40) % 11) as f64 - 5.
                    })
                    .collect();
                for y in 0..h {
                    for x in 0..w {
                        let d2 = |cx: f64, cy: f64, s: f64| {
                            ((x as f64 - cx).powi(2) + (y as f64 - cy).powi(2)) / (2. * s * s)
                        };
                        v[y * w + x] += (10. * (-d2(150. + 2. * f as f64, 100., 9.)).exp()).round();
                        if (1..=3).contains(&f) {
                            v[y * w + x] += (3000. * (-d2(60., 150., 0.8)).exp()).round();
                        }
                    }
                }
                let found = candidates(
                    &Decoded {
                        values: &v,
                        excluded: &excluded,
                    },
                    [h, w],
                    10.,
                    spot_spacing,
                );
                // No single bin of the diffuse blob is significant.
                let single = scan(
                    &Decoded {
                        values: &v,
                        excluded: &excluded,
                    },
                    [h, w],
                )
                .bins
                .iter()
                .filter(|b| {
                    let i = b.index as usize;
                    let (bx, by) = ((i % (w / BIN)) * BIN, (i / (w / BIN)) * BIN);
                    (bx as f64 - 150.).abs() < 30. && (by as f64 - 100.).abs() < 30.
                })
                .map(|b| b.level)
                .fold(0f32, f32::max);
                assert!(single < 10., "frame {f}: brightest single bin {single}");
                found
            })
            .collect();
        link(&mut all);
        let lines = [2.0];
        let selection = Selection {
            lines: &lines,
            tolerance: 0.03,
            min_size: 120,
            margin: 0,
            shape: [h, w],
        };
        for (f, c) in all.iter().enumerate() {
            let (pixels, _) = accept(c, &selection);
            let masked = |x: usize, y: usize| pixels.binary_search(&((y * w + x) as u32)).is_ok();
            assert!(masked(150 + 2 * f, 100), "frame {f}: diffuse blob");
            assert!(!masked(60, 150), "frame {f}: sharp spot");
        }
    }

    /// The margin is round and only grows accepted spots: margin 0 is the
    /// region itself, each larger margin strictly adds pixels.
    #[test]
    fn the_margin_grows_accepted_spots_round() {
        let w = 300usize;
        let areas: Vec<usize> = [0, 3, 10, 20]
            .map(|m| found_frames(120, m).1[2].0.len())
            .to_vec();
        assert!(areas.windows(2).all(|a| a[0] < a[1]), "{areas:?}");
        let (all, m0) = found_frames(120, 0);
        let blob = all[2]
            .iter()
            .find(|c| (c.centre[0] - 66.).abs() < 6.)
            .unwrap();
        assert_eq!(m0[2].0, blob.pixels);
        let grown = &found_frames(120, 20).1[2].0;
        let right = blob.pixels.iter().map(|&p| p as usize % w).max().unwrap();
        let row = blob
            .pixels
            .iter()
            .find(|&&p| p as usize % w == right)
            .unwrap()
            / w as u32;
        assert!(
            grown
                .binary_search(&(row * w as u32 + (right + 20) as u32))
                .is_ok()
        );
        let top = blob.pixels[0] as usize / w;
        let top_right = blob
            .pixels
            .iter()
            .filter(|&&p| p as usize / w == top)
            .map(|&p| p as usize % w)
            .max()
            .unwrap();
        assert!(
            grown
                .binary_search(&(((top - 20) * w + top_right + 20) as u32))
                .is_err(),
            "round, not square"
        );
        assert!(
            !grown.binary_search(&((150 * w + 150) as u32)).is_ok(),
            "rejected spots never grow"
        );
    }

    /// Growth by edge-pixel row intervals equals a brute-force disc.
    #[test]
    fn grown_regions_equal_a_brute_force_disc() {
        let (h, w) = (60usize, 80usize);
        let mut region = vec![];
        for y in 0..20usize {
            for x in 30..55usize {
                if (x as i32 - 40).pow(2) + (y as i32 - 5).pow(2) * 3 <= 60 || (x == 54 && y == 12)
                {
                    region.push((y * w + x) as u32);
                }
            }
        }
        for r in [0usize, 1, 3, 10, 25] {
            let mut brute = std::collections::BTreeSet::new();
            for &p in &region {
                let (x, y) = ((p as usize % w) as isize, (p as usize / w) as isize);
                let r = r as isize;
                for dy in -r..=r {
                    for dx in -r..=r {
                        let (xx, yy) = (x + dx, y + dy);
                        if dx * dx + dy * dy <= r * r
                            && xx >= 0
                            && yy >= 0
                            && (xx as usize) < w
                            && (yy as usize) < h
                        {
                            brute.insert((yy as usize * w + xx as usize) as u32);
                        }
                    }
                }
            }
            assert_eq!(
                grow(&region, r, [h, w]),
                brute.into_iter().collect::<Vec<_>>(),
                "radius {r}"
            );
        }
    }

    #[test]
    fn diamond_settings_restart_masks_and_are_validated() {
        let base = Config::default();
        for changed in [
            Config {
                diamond_enabled: true,
                ..Config::default()
            },
            Config {
                diamond_min_size: 40,
                ..Config::default()
            },
            Config {
                diamond_margin: 20,
                ..Config::default()
            },
            Config {
                diamond_tolerance: 2.,
                ..Config::default()
            },
        ] {
            assert_eq!(base.first_changed(&changed), 0);
        }
        assert!(
            Config {
                diamond_tolerance: 0.,
                ..Config::default()
            }
            .check()
            .is_err()
        );
        assert!(
            Config {
                diamond_min_size: 0,
                ..Config::default()
            }
            .check()
            .is_err()
        );
        let mut c = Crystal::default();
        assert_eq!(c.mask_summary(), "No masks");
        c.config.diamond_enabled = true;
        c.diamonds = Some(Arc::new(Diamonds {
            frames: vec![],
            regions: 2,
        }));
        assert_eq!(c.mask_summary(), "0.0\u{a0}% masked · 2 diamond spots");
    }

    /// Coarse DAC cells masked at one frame, split into image halves:
    /// [low rows, high rows, low columns, high columns].
    fn dac_halves(axis: V3, frame: usize) -> [usize; 4] {
        let p = 7.5e-4;
        let (h, w) = (224, 208);
        let mut c = Crystal {
            shape: [h, w],
            ..Default::default()
        };
        c.sources = (0..144)
            .map(|frame| Source {
                path: PathBuf::new(),
                frame,
                digest: Default::default(),
            })
            .collect();
        c.config.omega_start = -36.;
        c.config.omega_step = 0.5;
        c.config.exposure = 0.5;
        c.config.axis = axis;
        c.config.dac_enabled = true;
        // As Crystal::set_poni builds it: slow along detector rows, fast along
        // columns, beam centre in the middle of the image.
        c.initial_geometry = Some(Geometry {
            origin: [p / 2. - h as f64 * p / 2., p / 2. - w as f64 * p / 2., 0.15],
            fast: [0., p, 0.],
            slow: [p, 0., 0.],
            beam: [0., 0., 1.],
            axis,
            wavelength: 0.2846,
        });
        c.prepare_shadows(&Control::default()).unwrap();
        let s = c.shadows.unwrap();
        let rows = s.cells / s.columns;
        let mut halves = [0; 4];
        for cell in 0..s.cells {
            if s.dac[frame * s.cells + cell] {
                let (row, column) = (cell / s.columns, cell % s.columns);
                halves[usize::from(row >= rows / 2)] += 1;
                // 13 columns: the middle one straddles the beam centre.
                if column != s.columns / 2 {
                    halves[2 + usize::from(column > s.columns / 2)] += 1;
                }
            }
        }
        halves
    }

    /// Measured on the ID11 Eiger enstatite scan (axis -slow, start -36 deg):
    /// at negative omega the cell body darkens the high-column side and the
    /// shadow edge sweeps across columns, symmetric between top and bottom.
    /// An axis along the columns instead moves the shadow up and down.
    #[test]
    fn dac_shadow_sweeps_across_the_rotation_axis() {
        let [top, bottom, left, right] = dac_halves([-1., 0., 0.], 35);
        assert!(right > 0 && left == 0, "{left} {right}");
        assert_eq!(top, bottom);
        let [top, bottom, left, right] = dac_halves([-1., 0., 0.], 108);
        assert!(left > 0 && right == 0, "{left} {right}");
        assert_eq!(top, bottom);
        let [top, bottom, left, right] = dac_halves([0., 1., 0.], 35);
        assert!(top.abs_diff(bottom) > 0 && left == right, "{top} {bottom}");
    }

    #[test]
    fn a_dac_mask_away_from_the_measured_shadow_asks_to_check_the_axis() {
        let shadows = |dac: Vec<bool>| Shadows {
            first: 0,
            last: 1,
            block: 16,
            columns: 2,
            cells: 4,
            // Frame 0: the left column is dark. Frame 1: closed by the DAC
            // mask, which carries no information.
            illumination: vec![true, false, true, false, true, true, true, true],
            seat: vec![],
            dac,
            report: Value::Null,
        };
        let agreeing = shadows(vec![true, false, true, true, true, true, true, true]);
        assert_eq!(agreeing.dac_agreement(), Some(1.));
        let crossed = shadows(vec![false, false, true, true, true, true, true, true]);
        assert_eq!(crossed.dac_agreement(), Some(0.5));
        let mut c = Crystal::default();
        c.config.dac_enabled = true;
        c.config.seat_enabled = true;
        c.shadows = Some(Arc::new(agreeing));
        assert!(c.dac_warning().is_none());
        c.shadows = Some(Arc::new(crossed));
        assert!(c.mask_summary().ends_with("check the rotation axis"));
    }

    /// Measured on the ID11 Eiger scan: the seat shadow edge is sharp, but
    /// powder rings and omega-dependent background raise the estimator's
    /// per-frame scale (its 90th-percentile ratio). At the old 0.85 level
    /// fully lit cells next to the shadow then counted as shadow; at half
    /// the lit level only the shadow itself does.
    #[test]
    fn seat_level_at_half_lit_keeps_lit_cells_beside_a_brighter_band() {
        use spots::frame_validity as validity;
        let shape = validity::Shape {
            height: 128,
            width: 512,
            block: 16,
        };
        let (h, w, frames) = (8, 32, 10);
        let mut coarse = vec![100.; frames * h * w];
        for y in 0..h {
            for x in 0..w {
                // Frame 0: the right quarter lies in the seat shadow, the
                // left quarter is a quarter brighter than in the references.
                coarse[y * w + x] = match x {
                    24.. => 5.,
                    ..8 => 125.,
                    _ => 100.,
                };
            }
        }
        let available = vec![true; frames];
        let masked = |threshold: f64| {
            let e = validity::estimate(
                &coarse,
                &available,
                shape,
                validity::SeatOptions {
                    threshold,
                    guard_pixels: 16,
                    ..Default::default()
                },
            )
            .unwrap();
            let lit = (0..h * w).filter(|i| (8..22).contains(&(i % w)) && e.excluded[*i]);
            let dark = (0..h * w).filter(|i| i % w >= 24 && e.excluded[*i]);
            (lit.count(), dark.count())
        };
        let (lit, dark) = masked(0.85);
        // Smoothing may round off a shadow corner cell or two.
        assert!(lit > 4 * h && dark + 2 >= 8 * h, "{lit} {dark}");
        let (lit, dark) = masked(0.5);
        assert!(lit == 0 && dark + 2 >= 8 * h, "{lit} {dark}");
    }
}
