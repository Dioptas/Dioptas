//! The prepared masks of the lean mode (DAC opening, seat shadow, diamond
//! spots, persistent pixels, and the Mask mode mask applied to every frame)
//! are kept apart. Each part remembers the inputs it was made
//! from; the mask in use is the union of the enabled parts whose inputs still
//! match. Switching one mask or changing its settings leaves the others as
//! they are, and a part switched back on with unchanged inputs returns
//! without recomputation. The DAC mask and the seat shadow take well under a
//! second and are remade inside the settings reply; so are diamond spots for
//! scans up to DIAMOND_REPLY_PIXELS (larger ones wait for Run, with stage 0
//! pending and the valid parts shown).
use super::*;
use rayon::prelude::*;
use std::sync::Mutex;

/// One prepared mask and the inputs it was made from.
#[derive(Serialize, Deserialize)]
pub(super) struct Part<T> {
    pub key: Value,
    pub data: Arc<T>,
}
impl<T> Clone for Part<T> {
    fn clone(&self) -> Self {
        Self {
            key: self.key.clone(),
            data: self.data.clone(),
        }
    }
}
#[derive(Serialize, Deserialize)]
pub(super) struct SeatPart {
    /// Seat field per frame and block (see `Shadows::seat`).
    pub levels: Vec<u8>,
    pub report: Value,
}
/// A mask that is the same on every frame (Mask mode mask in source
/// orientation, persistent pixels), as row-major runs `[start, end)` of masked
/// pixels: compact, cheap to apply to every frame and to compare.
#[derive(Clone, Default, PartialEq, Serialize, Deserialize)]
pub(super) struct PixelRuns {
    pub runs: Vec<[u32; 2]>,
    pub pixels: usize,
}
impl PixelRuns {
    /// None when nothing is masked.
    pub fn from_mask(mask: &[u8]) -> Option<Self> {
        let mut runs: Vec<[u32; 2]> = vec![];
        let mut pixels = 0;
        for (i, &v) in mask.iter().enumerate() {
            if v == 0 {
                continue;
            }
            pixels += 1;
            let i = i as u32;
            match runs.last_mut() {
                Some(last) if last[1] == i => last[1] = i + 1,
                _ => runs.push([i, i + 1]),
            }
        }
        (pixels > 0).then_some(Self { runs, pixels })
    }
    pub fn fill(&self, mask: &mut [bool]) {
        let n = mask.len();
        for &[a, b] in &self.runs {
            mask[(a as usize).min(n)..(b as usize).min(n)].fill(true);
        }
    }
}
/// Why the Mask mode mask is or is not available to this series.
#[derive(Clone, Copy, Default, PartialEq, Serialize)]
#[serde(rename_all = "lowercase")]
pub(super) enum SharedStatus {
    /// No shared image or nothing masked in Mask mode.
    #[default]
    None,
    /// Mask mode holds a mask of another detector shape.
    Shape,
    Ready,
}
/// Block medians of read frames, reused while their inputs stay the same,
/// so a threshold or margin change only re-thresholds.
#[derive(Default)]
pub(super) struct MedianCache {
    pub key: Value,
    pub frames: BTreeMap<usize, Arc<Vec<f64>>>,
}
#[derive(Clone, Default, Serialize, Deserialize)]
pub(super) struct MaskParts {
    pub dac: Option<Part<Vec<bool>>>,
    pub seat: Option<Part<SeatPart>>,
    pub diamonds: Option<Part<Diamonds>>,
    /// The Mask mode mask (key: the detector shape it applies to).
    #[serde(default)]
    pub shared: Option<Part<PixelRuns>>,
    /// Persistent pixels (detector flaws), for the current fraction.
    #[serde(default)]
    pub persistent: Option<Part<PixelRuns>>,
    /// Hit counts of every frame, independent of the fraction.
    #[serde(skip)]
    pub persistent_scan: Option<Part<persistent::Scan>>,
    /// Scans of every frame, independent of the diamond settings: a level,
    /// Min. size, d tolerance or margin change only re-filters them.
    #[serde(skip)]
    pub diamond_candidates: Option<Part<Vec<diamond::Scan>>>,
    #[serde(skip)]
    pub medians: Arc<Mutex<MedianCache>>,
    /// Which part data is in use (pointer identity), to tell whether the
    /// effective mask changed.
    #[serde(skip)]
    pub active: [usize; 5],
}

/// Numbers to 12 significant digits: a calibration rebuilt from its PONI
/// after a reload differs in the last bits and must still match.
fn rounded(v: Value) -> Value {
    match v {
        Value::Number(n) if n.is_f64() => {
            let x = n.as_f64().unwrap_or(0.);
            let r = if x == 0. || !x.is_finite() {
                x
            } else {
                let scale = 10f64.powi(11 - x.abs().log10().floor() as i32);
                (x * scale).round() / scale
            };
            json!(r)
        }
        Value::Array(a) => Value::Array(a.into_iter().map(rounded).collect()),
        Value::Object(o) => Value::Object(o.into_iter().map(|(k, v)| (k, rounded(v))).collect()),
        other => other,
    }
}
/// Largest scan (frames × pixels) whose diamond spots are found inside the
/// settings reply.
const DIAMOND_REPLY_PIXELS: usize = 1_000_000_000;
#[cfg(test)]
thread_local! {
    /// Tests lower it to exercise the large-scan path on small fixtures.
    pub(super) static DIAMOND_REPLY_LIMIT: std::cell::Cell<usize> =
        const { std::cell::Cell::new(DIAMOND_REPLY_PIXELS) };
}
fn diamond_reply_limit() -> usize {
    #[cfg(test)]
    return DIAMOND_REPLY_LIMIT.get();
    #[cfg(not(test))]
    DIAMOND_REPLY_PIXELS
}
fn same<T>(part: &Option<Part<T>>, key: &Value) -> bool {
    part.as_ref().is_some_and(|p| &p.key == key)
}
fn address<T>(part: &Option<Part<T>>) -> usize {
    part.as_ref()
        .map_or(0, |p| Arc::as_ptr(&p.data) as *const u8 as usize)
}

impl Crystal {
    /// Lean masks are independent parts; profile recipes and the omega
    /// background keep the joint stage-0 product.
    pub(super) fn independent_masks(&self) -> bool {
        self.config.integration_method != "profile" && !self.config.background
    }
    /// Frames the masks cover and the inputs every mask depends on.
    fn mask_scope(&self) -> Value {
        json!({
            "frames": self.sources.len(),
            "shape": self.shape,
            "excluded": self.excluded_frames,
            "mask": self.mask,
            "saturation": self.config.saturation,
        })
    }
    /// The calibration as the masks use it (the rotation axis comes from the
    /// settings, not from the stored geometry).
    fn calibration_key(&self) -> Value {
        rounded(self.initial_geometry.map_or(Value::Null, |g| {
            json!([g.origin, g.fast, g.slow, g.beam, g.wavelength])
        }))
    }
    fn rotation_scope(&self) -> Value {
        let c = &self.config;
        json!({
            "geometry": self.calibration_key(),
            "axis": c.axis,
            "start": c.omega_start,
            "step": c.omega_step,
            "exposure": c.exposure,
            "dacAxis": c.dac_axis,
            "opening": c.dac_half_opening,
        })
    }
    pub(super) fn dac_key(&self) -> Value {
        json!({"scope": self.mask_scope(), "block": self.config.shadow_block, "rotation": self.rotation_scope()})
    }
    /// The seat shadow follows the DAC cone between measured frames when
    /// calibrated, so it depends on the rotation as well.
    pub(super) fn seat_key(&self) -> Value {
        json!({
            "scope": self.mask_scope(),
            "block": self.config.shadow_block,
            "rotation": self.rotation_scope(),
            "threshold": self.config.seat_threshold,
            "guard": self.config.seat_guard,
        })
    }
    pub(super) fn diamond_key(&self) -> Value {
        json!({
            "scope": self.mask_scope(),
            "geometry": self.calibration_key(),
            "minSize": self.config.diamond_min_size,
            "tolerance": self.config.diamond_tolerance,
            "margin": self.config.diamond_margin,
            "level": self.config.diamond_level,
        })
    }
    fn candidate_key(&self) -> Value {
        json!({"scope": self.mask_scope(), "geometry": self.calibration_key()})
    }
    /// Make the diamond-spot mask if enabled and stale: filter the cached
    /// candidates, finding them first if `scan` allows reading every frame.
    pub(super) fn ensure_diamonds(&mut self, control: &Control, scan: bool) -> Result<(), String> {
        if !self.config.diamond_on() || self.diamonds_current() {
            return Ok(());
        }
        let key = self.candidate_key();
        if !same(&self.parts.diamond_candidates, &key) {
            if !scan {
                return Ok(());
            }
            let found = self.all_diamond_scans(control)?;
            self.parts.diamond_candidates = Some(Part {
                key,
                data: Arc::new(found),
            });
        }
        let (lines, tolerance) = self.diamond_lines()?;
        let selection = diamond::Selection {
            lines: &lines,
            tolerance,
            min_size: self.config.diamond_min_size,
            margin: self.config.diamond_margin,
            shape: self.shape,
        };
        let scans = self.parts.diamond_candidates.as_ref().unwrap().data.clone();
        let candidates = self.diamond_regions(&scans)?;
        let found: Vec<(Vec<u32>, usize)> = crate::worker_pool::install(|| {
            candidates
                .par_iter()
                .map(|c| diamond::accept(c, &selection))
                .collect()
        });
        let regions = found.iter().map(|f| f.1).sum();
        let d = Diamonds {
            frames: found.into_iter().map(|f| f.0).collect(),
            regions,
        };
        match &self.parts.diamonds {
            // Identical contents keep their identity (no downstream invalidation).
            Some(old) if old.data.frames == d.frames => {
                self.parts.diamonds = Some(Part {
                    key: self.diamond_key(),
                    data: old.data.clone(),
                })
            }
            _ => self.set_diamonds(d),
        }
        Ok(())
    }
    pub(super) fn median_key(&self, block: usize) -> Value {
        json!({"scope": self.mask_scope(), "block": block})
    }
    /// Block medians of the given scan frames, from the cache where possible;
    /// the others are read in parallel and kept.
    pub(super) fn cached_medians(
        &self,
        frames: &[usize],
        block: usize,
        control: &Control,
    ) -> Result<Vec<Arc<Vec<f64>>>, String> {
        let key = self.median_key(block);
        let missing: Vec<usize> = {
            let mut cache = self.parts.medians.lock().unwrap();
            if cache.key != key {
                cache.key = key.clone();
                cache.frames.clear();
            }
            frames
                .iter()
                .copied()
                .filter(|f| !cache.frames.contains_key(f))
                .collect()
        };
        let found: Result<Vec<(usize, Vec<f64>)>, String> = crate::worker_pool::install(|| {
            missing
                .par_iter()
                .map(|&f| {
                    control.check()?;
                    Ok((f, self.frame_medians(f, block)?))
                })
                .collect()
        });
        let mut cache = self.parts.medians.lock().unwrap();
        if cache.key == key {
            for (f, m) in found? {
                cache.frames.insert(f, Arc::new(m));
            }
        }
        frames
            .iter()
            .map(|f| {
                cache
                    .frames
                    .get(f)
                    .cloned()
                    .ok_or_else(|| "Frame medians were replaced while reading.".to_string())
            })
            .collect()
    }
    /// Make the enabled DAC mask and seat shadow that are stale. Returns
    /// each one's outcome. (Run one after the other: both already use every
    /// worker, so running them together gains nothing.)
    pub(super) fn ensure_fast(
        &mut self,
        control: &Control,
    ) -> (Result<(), String>, Result<(), String>) {
        let (dac_key, seat_key) = (self.dac_key(), self.seat_key());
        let need_dac = self.config.dac_on() && !same(&self.parts.dac, &dac_key);
        let need_seat = self.config.seat_on() && !same(&self.parts.seat, &seat_key);
        let dac = need_dac.then(|| self.dac_mask_frames(control));
        let seat = need_seat.then(|| self.seat_data(control));
        let dac = dac.map_or(Ok(()), |found| {
            found.map(|data| {
                // Identical contents keep their identity (no downstream invalidation).
                let data = match &self.parts.dac {
                    Some(old) if *old.data == data => old.data.clone(),
                    _ => Arc::new(data),
                };
                self.parts.dac = Some(Part { key: dac_key, data });
            })
        });
        let seat = seat.map_or(Ok(()), |found| {
            found.map(|(levels, report)| {
                let data = match &self.parts.seat {
                    Some(old) if old.data.levels == levels => old.data.clone(),
                    _ => Arc::new(SeatPart { levels, report }),
                };
                self.parts.seat = Some(Part {
                    key: seat_key,
                    data,
                });
            })
        });
        (dac, seat)
    }
    fn seat_data(&self, control: &Control) -> Result<(Vec<u8>, Value), String> {
        let (first, last) = self.mask_frames()?;
        let dims = self.mask_dims()?;
        self.measure_seat(first, last, dims, self.config.shadow_block, control)
    }
    pub(super) fn diamonds_current(&self) -> bool {
        same(&self.parts.diamonds, &self.diamond_key())
    }
    pub(super) fn set_diamonds(&mut self, d: Diamonds) {
        self.parts.diamonds = Some(Part {
            key: self.diamond_key(),
            data: Arc::new(d),
        });
    }
    /// First and last usable frame.
    pub(super) fn mask_frames(&self) -> Result<(usize, usize), String> {
        let first = (0..self.sources.len())
            .find(|i| !self.excluded_frames.contains(i))
            .ok_or("All frames are excluded.")?;
        let last = (0..self.sources.len())
            .rfind(|i| !self.excluded_frames.contains(i))
            .unwrap();
        Ok((first, last))
    }
    pub(super) fn mask_dims(&self) -> Result<[usize; 2], String> {
        let b = self.config.shadow_block;
        if !(1..=1024).contains(&b) || self.shape.contains(&0) {
            return Err("Invalid shadow block size.".into());
        }
        Ok([self.shape[0].div_ceil(b), self.shape[1].div_ceil(b)])
    }
    pub(super) fn persistent_key(&self) -> Value {
        json!({"scope": self.mask_scope(), "fraction": self.config.persistent_fraction})
    }
    pub(super) fn persistent_current(&self) -> bool {
        same(&self.parts.persistent, &self.persistent_key())
    }
    /// Make the persistent-pixel mask if enabled and stale: filter the cached
    /// hit counts, testing every frame first if `scan` allows it.
    pub(super) fn ensure_persistent(
        &mut self,
        control: &Control,
        scan: bool,
    ) -> Result<(), String> {
        if !self.config.persistent_on() || self.persistent_current() {
            return Ok(());
        }
        let key = self.mask_scope();
        if !same(&self.parts.persistent_scan, &key) {
            if !scan {
                return Ok(());
            }
            let found = self.persistent_scan(control)?;
            self.parts.persistent_scan = Some(Part {
                key,
                data: Arc::new(found),
            });
        }
        let counts = self.parts.persistent_scan.as_ref().unwrap().data.clone();
        let runs = persistent::select(&counts, self.shape, self.config.persistent_fraction)
            .unwrap_or_default();
        let key = self.persistent_key();
        self.parts.persistent = Some(match self.parts.persistent.take() {
            // Identical contents keep their identity (no downstream invalidation).
            Some(old) if *old.data == runs => Part {
                key,
                data: old.data,
            },
            _ => Part {
                key,
                data: Arc::new(runs),
            },
        });
        Ok(())
    }
    pub(super) fn shared_key(&self) -> Value {
        json!({"shape": self.shape})
    }
    /// Take over the Mask mode mask (already in source orientation, None when
    /// unavailable). Identical contents keep their identity, so returning to
    /// the mode with an unchanged mask invalidates nothing. Returns whether
    /// the mask in use or stage 0 changed.
    pub(super) fn set_shared_mask(
        &mut self,
        found: Option<PixelRuns>,
        status: SharedStatus,
        control: &Control,
    ) -> bool {
        self.shared_status = status;
        let key = self.shared_key();
        self.parts.shared = match (found, self.parts.shared.take()) {
            (Some(f), Some(old)) if *old.data == f => Some(Part {
                key,
                data: old.data,
            }),
            (Some(f), _) => Some(Part {
                key,
                data: Arc::new(f),
            }),
            (None, _) => None,
        };
        self.refresh_masks(control)
    }
    /// Use the enabled parts whose inputs match: rebuild the combined shadow
    /// product and the diamond product, and remember which parts these are.
    pub(super) fn activate_masks(&mut self) {
        let c = &self.config;
        let dac = (c.dac_on() && same(&self.parts.dac, &self.dac_key()))
            .then(|| self.parts.dac.clone())
            .flatten();
        let seat = (c.seat_on() && same(&self.parts.seat, &self.seat_key()))
            .then(|| self.parts.seat.clone())
            .flatten();
        let diamonds = (c.diamond_on() && self.diamonds_current())
            .then(|| self.parts.diamonds.clone())
            .flatten();
        let shared = (c.shared_on() && same(&self.parts.shared, &self.shared_key()))
            .then(|| self.parts.shared.clone())
            .flatten();
        let persistent = (c.persistent_on() && self.persistent_current())
            .then(|| self.parts.persistent.clone())
            .flatten();
        self.parts.active = [
            address(&dac),
            address(&seat),
            address(&diamonds),
            address(&shared),
            address(&persistent),
        ];
        self.diamonds = diamonds.map(|d| d.data);
        self.persistent = persistent.map(|p| p.data);
        self.shared = shared.map(|s| s.data);
        self.shadows = if dac.is_none() && seat.is_none() {
            None
        } else {
            self.combined_shadows(dac.map(|d| d.data), seat.map(|s| s.data))
                .ok()
                .map(Arc::new)
        };
    }
    /// Whether every enabled mask is made from the current inputs.
    pub(super) fn masks_current(&self) -> bool {
        let c = &self.config;
        (!c.dac_on() || same(&self.parts.dac, &self.dac_key()))
            && (!c.seat_on() || same(&self.parts.seat, &self.seat_key()))
            && (!c.diamond_on() || self.diamonds_current())
            && (!c.persistent_on() || self.persistent_current())
    }
    /// After a settings change (or a new calibration or restore): remake the
    /// fast masks, use every enabled valid part, mark stage 0 complete when
    /// all enabled masks are valid (pending otherwise, e.g. diamond spots
    /// await Run), and invalidate later steps when the mask in use changed.
    /// Returns whether the mask in use or stage 0 changed.
    pub(super) fn refresh_masks(&mut self, control: &Control) -> bool {
        if !self.independent_masks() || !self.config.confirmed || self.sources.is_empty() {
            return false;
        }
        let clock = std::time::Instant::now();
        let before = (self.parts.active, self.stages[0].status.clone());
        // Fast parts; one that cannot be made (no calibration) stays missing
        // and Run reports why.
        let _ = self.ensure_fast(control);
        // Diamond spots read every frame: in the reply for scans up to
        // DIAMOND_REPLY_PIXELS (about 0.15 s for the 144-frame Eiger scan in
        // the dev build), otherwise on Run. Settings changes only re-filter.
        let pixels = self
            .sources
            .len()
            .saturating_mul(self.shape[0] * self.shape[1]);
        let _ = self.ensure_diamonds(control, pixels <= diamond_reply_limit());
        // Persistent pixels read every frame once too; the fraction re-filters.
        let _ = self.ensure_persistent(control, pixels <= diamond_reply_limit());
        let previous = self.parts.active;
        self.activate_masks();
        let later = self.stages[1..].iter().any(|s| s.status != "pending")
            || !self.peaks.is_empty()
            || !self.cells.is_empty();
        if self.parts.active != previous && later {
            // Later steps used the previous mask.
            let notice = self.notice.take();
            self.invalidate(1);
            self.notice = notice;
        }
        if self.masks_current() {
            // Unchanged masks keep their stage report.
            // A report from before the per-mask numbers (development reload)
            // is renewed too.
            if self.stages[0].status != "complete"
                || self.parts.active != previous
                || self.stages[0].masks.is_none()
            {
                // Counts as a run of stage 0.
                self.revision += 1;
                let (detail, masks) = self.mask_counts();
                self.stages[0] = Stage {
                    status: "complete".into(),
                    detail,
                    seconds: clock.elapsed().as_secs_f64(),
                    masks: Some(masks),
                };
                self.notice = self.dac_warning();
            }
        } else {
            self.stages[0] = Stage::default();
        }
        (self.parts.active, self.stages[0].status.clone()) != before
    }
}
