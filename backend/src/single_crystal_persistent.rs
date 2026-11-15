//! Persistent pixels: detector flaws (hot pixels, hot runs along module
//! edges) that stand out from their surroundings at the same pixels on most
//! frames. A reflection lasts a few frames, a diamond reflection about
//! fifteen; a flaw is bright throughout the scan.
//!
//! Each frame is tested once, independently of the settings: a pixel is a
//! hit when it exceeds the median of its 16 px block by `LEVEL` Poisson
//! deviations and, to reject smooth gradients such as the beam-stop shadow
//! edge, also the median of its own 7×7 neighbourhood. Unusable pixels (module
//! gaps, saturation) are left out of both medians, so the rows next to a gap
//! are tested like any other. The hit counts per pixel are cached; the
//! fraction setting only re-filters them.
use super::*;
use rayon::prelude::*;

/// Significance of a hit, in Poisson deviations of the local background.
pub(super) const LEVEL: f64 = 5.;
/// Block of the coarse background (same as the seat-shadow medians).
pub(super) const BLOCK: usize = 16;
/// Half width of the neighbourhood that confirms a hit (7×7).
const HALF: usize = 3;
/// Clusters of at least this many pixels are grown by one pixel (their
/// wings); single hot pixels are masked alone.
const GROW_FROM: usize = 3;

/// Hit counts of the whole scan (settings independent).
#[derive(Clone, Default)]
pub(super) struct Scan {
    /// Frames tested.
    pub frames: usize,
    /// Pixels hit on two frames or more, and how often (by pixel index).
    pub counts: Vec<(u32, u16)>,
}

/// Counts of one frame as stored: rows-up (as decoded) or, for raw chunks,
/// bottom row first; unusable counts are NaN, saturated or in `rects`.
pub(super) struct Frame<'a, T> {
    pub data: &'a [T],
    pub shape: [usize; 2],
    pub flipped: bool,
    pub saturation: f64,
    pub rects: &'a [[usize; 4]],
}
impl<T: Copy + Into<f64>> Frame<'_, T> {
    fn row(&self, y: usize) -> &[T] {
        let [h, w] = self.shape;
        let r = if self.flipped { h - 1 - y } else { y };
        &self.data[r * w..(r + 1) * w]
    }
    fn usable(&self, v: f64, x: usize, y: usize) -> bool {
        v >= 0.
            && v < self.saturation
            && !self
                .rects
                .iter()
                .any(|&[x0, y0, x1, y1]| x >= x0 && x < x1 && y >= y0 && y < y1)
    }
}

/// Hits of one frame (pixel indices, rows-up); `medians` are its block
/// medians over the usable pixels.
pub(super) fn frame_hits<T: Copy + Into<f64>>(frame: &Frame<T>, medians: &[f64]) -> Vec<u32> {
    let [h, w] = frame.shape;
    let columns = w.div_ceil(BLOCK);
    let level = |b: f64| b + LEVEL * b.max(1.).sqrt();
    let mut out = vec![];
    let mut thresholds = vec![f64::NAN; columns];
    let mut window: Vec<f64> = Vec::with_capacity((2 * HALF + 1).pow(2));
    for y in 0..h {
        if y % BLOCK == 0 {
            // NaN (no background) never compares above.
            for (t, &b) in thresholds.iter_mut().zip(&medians[(y / BLOCK) * columns..]) {
                *t = level(b);
            }
        }
        for (bx, chunk) in frame.row(y).chunks(BLOCK).enumerate() {
            let t = thresholds[bx];
            for (k, &p) in chunk.iter().enumerate() {
                let v: f64 = p.into();
                // NaN (unusable count or no background) is never above.
                if v.partial_cmp(&t) != Some(std::cmp::Ordering::Greater) {
                    continue;
                }
                let x = bx * BLOCK + k;
                if !frame.usable(v, x, y) {
                    continue;
                }
                window.clear();
                for yy in y.saturating_sub(HALF)..(y + HALF + 1).min(h) {
                    let x0 = x.saturating_sub(HALF);
                    let row = &frame.row(yy)[x0..(x + HALF + 1).min(w)];
                    for (xx, &p) in (x0..).zip(row) {
                        let u: f64 = p.into();
                        if (yy, xx) != (y, x) && frame.usable(u, xx, yy) {
                            window.push(u);
                        }
                    }
                }
                if window.len() < 12 {
                    continue;
                }
                let n = window.len() / 2;
                let m = *window.select_nth_unstable_by(n, f64::total_cmp).1;
                if v > level(m) {
                    out.push((y * w + x) as u32);
                }
            }
        }
    }
    out
}

/// The mask for a fraction of frames (percent): pixels hit on at least that
/// share of the tested frames; clusters grown by one pixel.
pub(super) fn select(scan: &Scan, shape: [usize; 2], fraction: f64) -> Option<masks::PixelRuns> {
    let [h, w] = shape;
    let need = ((fraction / 100. * scan.frames as f64).ceil() as usize).max(2);
    let chosen: std::collections::HashSet<usize> = scan
        .counts
        .iter()
        .filter(|c| c.1 as usize >= need)
        .map(|c| c.0 as usize)
        .collect();
    let mut mask = vec![0u8; h * w];
    let mut seen = std::collections::HashSet::new();
    for &start in &chosen {
        if !seen.insert(start) {
            continue;
        }
        let mut stack = vec![start];
        let mut cluster = vec![];
        while let Some(i) = stack.pop() {
            cluster.push(i);
            let (y, x) = (i / w, i % w);
            for yy in y.saturating_sub(1)..(y + 2).min(h) {
                for xx in x.saturating_sub(1)..(x + 2).min(w) {
                    let j = yy * w + xx;
                    if chosen.contains(&j) && seen.insert(j) {
                        stack.push(j);
                    }
                }
            }
        }
        let grow = usize::from(cluster.len() >= GROW_FROM);
        for i in cluster {
            let (y, x) = (i / w, i % w);
            for yy in y.saturating_sub(grow)..(y + grow + 1).min(h) {
                mask[yy * w + x.saturating_sub(grow)..yy * w + (x + grow + 1).min(w)].fill(1);
            }
        }
    }
    masks::PixelRuns::from_mask(&mask)
}

impl Crystal {
    /// Test every usable frame in parallel and count the hits per pixel.
    pub(super) fn persistent_scan(&self, control: &Control) -> Result<Scan, String> {
        let frames: Vec<usize> = (0..self.sources.len())
            .filter(|f| !self.excluded_frames.contains(f))
            .collect();
        let hits: Result<Vec<Vec<u32>>, String> = crate::worker_pool::install(|| {
            frames
                .par_iter()
                .map(|&f| {
                    control.check()?;
                    self.persistent_hits(f)
                })
                .collect()
        });
        let mut counts = vec![0u16; self.shape[0] * self.shape[1]];
        for frame in hits? {
            for i in frame {
                counts[i as usize] = counts[i as usize].saturating_add(1);
            }
        }
        Ok(Scan {
            frames: frames.len(),
            counts: counts
                .into_iter()
                .enumerate()
                .filter(|c| c.1 >= 2)
                .map(|(i, n)| (i as u32, n))
                .collect(),
        })
    }
}
