//! Per-frame exclusion of broad diamond-anvil reflections in a rotation series.
//!
//! A morphology and kinematic-spacing prior, not phase identification: a very
//! bright, broad spot whose intensity-weighted centre lies near a cubic-diamond
//! spacing is excluded together with its halo. A strong sample reflection that
//! happens to sit on a diamond spacing can be excluded as well; weak diamond
//! wings beyond the halo level remain. Source counts are never changed.
use super::*;
use rayon::prelude::*;
use std::collections::BTreeSet;

/// Ambient cubic-diamond lattice parameter, Å.
const DIAMOND_A: f64 = 3.567;
/// Seed level above the frame median, in Poisson standard deviations.
const SEED_SIGMA: f64 = 1000.;
/// Halo level above the frame median, in Poisson standard deviations.
const HALO_SIGMA: f64 = 20.;
/// Guard added around the halo, pixels.
const GUARD: usize = 3;

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

/// Diamond spots of one frame: returns sorted excluded pixels and the number
/// of accepted spots. `excluded` marks pixels that are already unavailable.
pub(super) fn frame_mask(
    values: &[f64],
    excluded: &[bool],
    shape: [usize; 2],
    spacing_of: impl Fn(f64, f64) -> f64,
    lines: &[f64],
    tolerance: f64,
    min_area: usize,
) -> (Vec<u32>, usize) {
    let [h, w] = shape;
    let mut sample: Vec<f64> = values
        .iter()
        .zip(excluded)
        .step_by(7)
        .filter(|(v, m)| !**m && v.is_finite())
        .map(|(v, _)| *v)
        .collect();
    if sample.is_empty() || lines.is_empty() {
        return (vec![], 0);
    }
    let middle = sample.len() / 2;
    let median = *sample.select_nth_unstable_by(middle, f64::total_cmp).1;
    let sigma = median.max(1.).sqrt();
    let (seed, halo) = (median + SEED_SIGMA * sigma, median + HALO_SIGMA * sigma);
    let usable = |i: usize, level: f64| !excluded[i] && values[i] > level;
    let neighbours = move |i: usize| {
        let (x, y) = ((i % w) as isize, (i / w) as isize);
        (-1..=1isize)
            .flat_map(move |dy| (-1..=1isize).map(move |dx| (x + dx, y + dy)))
            .filter(move |&(nx, ny)| nx >= 0 && ny >= 0 && (nx as usize) < w && (ny as usize) < h)
            .map(move |(nx, ny)| ny as usize * w + nx as usize)
    };
    let mut visited = vec![false; values.len()];
    let mut out = vec![];
    let mut regions = 0;
    for start in 0..values.len() {
        if visited[start] || !usable(start, seed) {
            continue;
        }
        visited[start] = true;
        let mut component = vec![start];
        let mut next = 0;
        while next < component.len() {
            for j in neighbours(component[next]) {
                if !visited[j] && usable(j, seed) {
                    visited[j] = true;
                    component.push(j);
                }
            }
            next += 1;
        }
        if component.len() < min_area {
            continue;
        }
        let (mut sx, mut sy, mut sw) = (0., 0., 0.);
        let (mut x0, mut x1, mut y0, mut y1) = (w, 0, h, 0);
        for &i in &component {
            let (x, y) = (i % w, i / w);
            let weight = values[i] - median;
            sx += weight * x as f64;
            sy += weight * y as f64;
            sw += weight;
            (x0, x1, y0, y1) = (x0.min(x), x1.max(x), y0.min(y), y1.max(y));
        }
        let d = spacing_of(sx / sw, sy / sw);
        if !lines.iter().any(|line| (d / line - 1.).abs() <= tolerance) {
            continue;
        }
        regions += 1;
        // The halo grows from the seed but stays in a window about twice the
        // seed's size, so a bright powder ring cannot carry it away.
        let margin = 16.max(x1 - x0).max(y1 - y0);
        let (wx0, wx1) = (x0.saturating_sub(margin), (x1 + margin).min(w - 1));
        let (wy0, wy1) = (y0.saturating_sub(margin), (y1 + margin).min(h - 1));
        let inside = |j: usize| (wx0..=wx1).contains(&(j % w)) && (wy0..=wy1).contains(&(j / w));
        let mut grown: BTreeSet<usize> = component.iter().copied().collect();
        let mut queue = component;
        while let Some(i) = queue.pop() {
            for j in neighbours(i) {
                if inside(j) && usable(j, halo) && grown.insert(j) {
                    queue.push(j);
                }
            }
        }
        for i in grown {
            let (x, y) = (i % w, i / w);
            for yy in y.saturating_sub(GUARD)..=(y + GUARD).min(h - 1) {
                for xx in x.saturating_sub(GUARD)..=(x + GUARD).min(w - 1) {
                    out.push((yy * w + xx) as u32);
                }
            }
        }
    }
    out.sort_unstable();
    out.dedup();
    (out, regions)
}

impl Crystal {
    /// One-line account of the prepared masks, as a share of all scan pixels.
    pub(super) fn mask_summary(&self) -> String {
        if !(self.config.dac_enabled || self.config.seat_enabled || self.config.diamond_enabled) {
            return "No masks".into();
        }
        let pixels = (self.shape[0] * self.shape[1]).max(1) as f64;
        let mut total = 0.;
        for frame in 0..self.sources.len() {
            let mut share = 0.;
            if self.excluded_frames.contains(&frame) {
                share = 1.;
            } else if let Some(s) = &self.shadows {
                if frame < s.first || frame > s.last {
                    share = 1.;
                } else {
                    let on = |v: &[bool], i: usize| v.get(i).copied().unwrap_or(false);
                    share = ((frame - s.first) * s.cells..(frame - s.first + 1) * s.cells)
                        .filter(|&i| on(&s.dac, i) || on(&s.illumination, i))
                        .count() as f64
                        / s.cells as f64;
                }
            }
            if let Some(d) = &self.diamonds {
                share += d.frames.get(frame).map_or(0, Vec::len) as f64 / pixels;
            }
            total += share.min(1.);
        }
        // A no-break space keeps the number and its unit on one line.
        let mut summary = format!(
            "{:.1}\u{a0}% masked",
            100. * total / self.sources.len().max(1) as f64
        );
        if let Some(d) = &self.diamonds {
            let plural = if d.regions == 1 { "" } else { "s" };
            summary += &format!(" · {} diamond spot{plural}", d.regions);
        }
        summary
    }
    /// Exclude broad diamond spots on every processed frame. Shadow masks must
    /// be prepared first so that shadowed pixels never seed a region.
    pub(super) fn prepare_diamonds(&mut self, control: &Control) -> Result<(), String> {
        if self.diamonds.is_some() || !self.config.diamond_enabled {
            return Ok(());
        }
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
        let lines = spacings(d_min / (1. + tolerance));
        let frames: Vec<usize> = (0..self.sources.len()).collect();
        let done = std::sync::atomic::AtomicUsize::new(0);
        let found: Result<Vec<(Vec<u32>, usize)>, String> = crate::worker_pool::install(|| {
            frames
                .par_iter()
                .map(|&frame| {
                    control.check()?;
                    if self.excluded_frames.contains(&frame) {
                        return Ok((vec![], 0));
                    }
                    let raw = self.read(frame)?;
                    let excluded = self.mask_for(&raw, frame);
                    let result = frame_mask(
                        &raw,
                        &excluded,
                        self.shape,
                        |x, y| spacing(&g, x, y),
                        &lines,
                        tolerance,
                        self.config.diamond_min_area,
                    );
                    let n = done.fetch_add(1, std::sync::atomic::Ordering::Relaxed) + 1;
                    control.publish(json!({"running":true,"current":n,"total":frames.len(),"label":"Masking diamond spots"}));
                    Ok(result)
                })
                .collect()
        });
        let found = found?;
        let regions = found.iter().map(|f| f.1).sum();
        self.diamonds = Some(Arc::new(Diamonds {
            frames: found.into_iter().map(|f| f.0).collect(),
            regions,
        }));
        Ok(())
    }
}

#[cfg(test)]
mod tests {
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

    /// A flat frame with a broad bright spot (diamond-like), a small bright
    /// spot and a broad bright spot that is off every diamond spacing.
    #[test]
    fn broad_spots_on_diamond_spacings_are_masked_with_their_halo() {
        let (h, w) = (200, 300);
        let mut values = vec![25.; h * w];
        let mut blob = |cx: f64, cy: f64, radius: f64, peak: f64| {
            for y in 0..h {
                for x in 0..w {
                    let r2 = (x as f64 - cx).powi(2) + (y as f64 - cy).powi(2);
                    values[y * w + x] += peak * (-r2 / (2. * radius * radius)).exp();
                }
            }
        };
        blob(50., 100., 4., 1e6); // broad, on a diamond spacing
        blob(150., 100., 0.5, 1e6); // small sample spot, same spacing
        blob(250., 100., 4., 1e6); // broad, off any diamond spacing
        let excluded = vec![false; h * w];
        let lines = [2.0];
        // Spacing varies with x: 2.0 Å at the left two spots, 2.5 Å at the right.
        let spacing_of = |x: f64, _: f64| if x < 200. { 2.0 } else { 2.5 };
        let (pixels, regions) =
            frame_mask(&values, &excluded, [h, w], spacing_of, &lines, 0.03, 20);
        assert_eq!(regions, 1);
        let masked = |x: usize, y: usize| pixels.binary_search(&((y * w + x) as u32)).is_ok();
        assert!(masked(50, 100));
        // The halo (about 20 sigma above background) and the guard are included.
        assert!(masked(50, 100 + 12));
        assert!(!masked(50, 100 + 30));
        assert!(!masked(150, 100));
        assert!(!masked(250, 100));
        // Already excluded pixels never seed a region.
        let all = vec![true; h * w];
        assert_eq!(
            frame_mask(&values, &all, [h, w], spacing_of, &lines, 0.03, 20).1,
            0
        );
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
                diamond_min_area: 40,
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
                diamond_min_area: 0,
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
}
