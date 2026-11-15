//! Transfer of the single-crystal session to another processor: across a
//! live development backend reload, and through the automatic recovery
//! checkpoint across an application restart. The receiving processor may run
//! other code, so it re-derives what is cheap (calibration geometry, geometric
//! DAC mask, shown image) and carries only measured products whose inputs are
//! unchanged. Anything it cannot read, or whose inputs moved, is dropped and
//! its step left pending: SC state never fails the transfer or restores a
//! stale product. Frames are never hashed or decoded beyond the shown one.
use super::*;

/// Bump when the layout or meaning of carried fields changes. A recovery file
/// of another version restores nothing of the SC session (and says so).
const VERSION: u32 = 1;

/// Where the session goes. Recovery files outlive the build that wrote them.
#[derive(Clone, Copy, PartialEq)]
pub(in crate::session) enum Transfer {
    /// Development backend reload: same session, newer code.
    Development,
    /// Application restart from the automatic recovery checkpoint.
    Recovery,
}
/// Serialised session: the series/settings part and the step results part.
pub(in crate::session) struct Saved {
    pub essentials: Vec<u8>,
    pub products: Vec<u8>,
}
#[derive(Deserialize)]
struct Header {
    version: u32,
    generation: String,
}
/// Numerical code identity; step results from other code are not restored
/// after a restart (a development reload follows its own geometry check).
fn identity() -> String {
    format!("{ENGINE} / {}", adapter_identity())
}

fn essentials_path(base: &Path) -> PathBuf {
    base.with_extension("scxrd.msgpack")
}
fn products_path(base: &Path) -> PathBuf {
    base.with_extension("scxrd-products.msgpack")
}

/// The loaded series, calibration and settings: what the workspace shows.
#[derive(Serialize, Deserialize)]
struct Essentials {
    version: u32,
    generation: String,
    /// Kept as a value so a renamed or removed setting falls back field by field.
    config: Value,
    sources: Vec<Source>,
    protected_sources: Vec<PathBuf>,
    shape: [usize; 2],
    frame: usize,
    poni: Option<crate::geometry::Geometry>,
    calibration_source: Option<PathBuf>,
    initial_geometry: Option<Geometry>,
    mask: Vec<[usize; 4]>,
    excluded_frames: Vec<usize>,
    error: Option<String>,
    notice: Option<String>,
    revision: u64,
    track_offset: usize,
    reflection_filter: String,
    /// Results beyond Find lattices existed (not carried).
    later_results: bool,
    /// Undo or redo steps existed (not carried).
    history: bool,
}

/// Step results of Prepare masks, Find spots and Find lattices.
#[derive(Serialize)]
struct SavedProducts<'a> {
    version: u32,
    generation: &'a str,
    identity: String,
    initial_geometry: Option<Geometry>,
    stages: &'a [Stage],
    background: bool,
    shadows: Option<&'a Shadows>,
    diamonds: Option<&'a Diamonds>,
    masks: &'a masks::MaskParts,
    peaks: &'a [Peak],
    tracks: &'a [Track],
    cells: &'a [Cell],
    selected: Option<usize>,
    shown: Option<usize>,
}
#[derive(Deserialize)]
struct Products {
    version: u32,
    generation: String,
    #[serde(default)]
    identity: String,
    initial_geometry: Option<Geometry>,
    stages: Vec<Stage>,
    background: bool,
    shadows: Option<Shadows>,
    diamonds: Option<Diamonds>,
    #[serde(default)]
    masks: Option<masks::MaskParts>,
    peaks: Vec<Peak>,
    tracks: Vec<Track>,
    cells: Vec<Cell>,
    selected: Option<usize>,
    #[serde(default)]
    shown: Option<usize>,
}

fn encode(value: &impl Serialize) -> Result<Vec<u8>, String> {
    let mut bytes = Vec::new();
    value
        .serialize(&mut rmp_serde::Serializer::new(&mut bytes).with_struct_map())
        .map_err(err)?;
    Ok(bytes)
}
fn decode<T: serde::de::DeserializeOwned>(bytes: &[u8]) -> Result<T, String> {
    rmp_serde::from_slice(bytes).map_err(err)
}
/// Same detector geometry for the carried steps. These steps take the spindle
/// axis from the settings, so the axis stored at calibration time is ignored.
fn same(a: Option<Geometry>, b: Option<Geometry>) -> bool {
    let key =
        |g: Option<Geometry>| g.map(|g| [g.origin, g.fast, g.slow, g.beam, [g.wavelength; 3]]);
    key(a) == key(b)
}

/// Settings saved under a former name: (former, current).
const RENAMED_SETTINGS: [(&str, &str); 1] = [("masks_enabled", "cell_masks_enabled")];
impl Config {
    /// Saved settings over the current defaults; unknown keys are ignored and
    /// an unreadable or now-invalid set falls back to the defaults.
    pub(super) fn from_development(saved: Value, dropped: &mut Vec<String>) -> Config {
        let mut merged = serde_json::to_value(Config::default()).unwrap_or_default();
        let mut ignored = vec![];
        if let (Some(target), Value::Object(mut saved)) = (merged.as_object_mut(), saved) {
            // Renamed settings keep their value (as the serde aliases do).
            for (old, new) in RENAMED_SETTINGS {
                if let Some(value) = saved.remove(old) {
                    saved.entry(new).or_insert(value);
                }
            }
            for (key, value) in saved {
                match target.get_mut(&key) {
                    Some(slot) => *slot = value,
                    None => ignored.push(key),
                }
            }
        }
        if !ignored.is_empty() {
            dropped.push(format!("removed settings ({})", ignored.join(", ")));
        }
        match serde_json::from_value::<Config>(merged).map_err(err) {
            Ok(c) => match c.check() {
                Ok(()) => return c,
                Err(e) => dropped.push(format!("processing settings ({e})")),
            },
            Err(e) => dropped.push(format!("processing settings ({e})")),
        }
        Config::default()
    }
}

impl Crystal {
    /// Serialise the session. Nothing is hashed or decoded.
    pub(in crate::session) fn transfer(
        &self,
        generation: &str,
        history: bool,
    ) -> Result<Saved, String> {
        let essentials = Essentials {
            version: VERSION,
            generation: generation.into(),
            config: serde_json::to_value(&self.config).map_err(err)?,
            sources: self.sources.clone(),
            protected_sources: self.protected_sources.clone(),
            shape: self.shape,
            frame: self.frame,
            poni: self.poni.clone(),
            calibration_source: self.calibration_source.clone(),
            initial_geometry: self.initial_geometry,
            mask: self.mask.clone(),
            excluded_frames: self.excluded_frames.clone(),
            error: self.error.clone(),
            notice: self.notice.clone(),
            revision: self.revision,
            track_offset: self.track_offset,
            reflection_filter: self.reflection_filter.clone(),
            later_results: self.stages[3..].iter().any(|s| s.status != "pending")
                || !self.reflections.is_empty()
                || !self.structure.is_null(),
            history,
        };
        Ok(Saved {
            essentials: encode(&essentials)?,
            products: encode(&SavedProducts {
                version: VERSION,
                generation,
                identity: identity(),
                initial_geometry: self.initial_geometry,
                stages: &self.stages[..3],
                background: self.background.is_some(),
                shadows: self.shadows.as_deref(),
                diamonds: self.diamonds.as_deref(),
                masks: &self.parts,
                peaks: &self.peaks,
                tracks: &self.tracks,
                cells: &self.cells,
                selected: self.selected,
                shown: self.shown,
            })?,
        })
    }

    /// Write the development transfer files beside `base`.
    pub(in crate::session) fn save_development(
        &self,
        base: &Path,
        generation: &str,
        history: bool,
    ) -> Result<(), String> {
        let saved = self.transfer(generation, history)?;
        std::fs::write(essentials_path(base), saved.essentials).map_err(err)?;
        std::fs::write(products_path(base), saved.products).map_err(err)
    }

    /// Rebuild the session written by `save_development`.
    pub(in crate::session) fn restore_development(
        base: &Path,
        generation: &str,
        control: &Control,
    ) -> Crystal {
        let read = |p: PathBuf| std::fs::read(p).map_err(err);
        Self::restore(
            read(essentials_path(base)),
            read(products_path(base)),
            generation,
            Transfer::Development,
            control,
        )
        .0
    }

    /// Rebuild a transferred session. Never fails: an unreadable transfer
    /// yields an empty workspace that says so. Also returns a short summary
    /// of what was not restored, if anything.
    pub(in crate::session) fn restore(
        essentials: Result<Vec<u8>, String>,
        products: Result<Vec<u8>, String>,
        generation: &str,
        kind: Transfer,
        control: &Control,
    ) -> (Crystal, Option<String>) {
        let essentials = essentials
            .and_then(|bytes| {
                let header: Header = decode(&bytes)?;
                if header.version != VERSION {
                    return Err(format!(
                        "saved in format {} by another Dioptas version; this one reads format {VERSION}",
                        header.version
                    ));
                }
                if header.generation != generation {
                    return Err("it belongs to another checkpoint".into());
                }
                decode::<Essentials>(&bytes)
            })
            .and_then(|e| Self::from_essentials(e, products, kind, control));
        match essentials {
            Ok(restored) => restored,
            Err(e) => {
                let summary = format!(
                    "The single-crystal session could not be restored ({e}). Reopen the rotation frames; your files are unchanged."
                );
                let c = Crystal {
                    notice: Some(summary.clone()),
                    revision: 1,
                    ..Default::default()
                };
                (c, Some(summary))
            }
        }
    }

    fn from_essentials(
        e: Essentials,
        products: Result<Vec<u8>, String>,
        kind: Transfer,
        control: &Control,
    ) -> Result<(Crystal, Option<String>), String> {
        let n = e.sources.len();
        if n > MAX_FRAMES
            || (n > 0
                && (e.shape.contains(&0)
                    || e.shape[0]
                        .checked_mul(e.shape[1])
                        .is_none_or(|p| p > MAX_PIXELS)))
            || e.excluded_frames.iter().any(|&f| f >= n)
            || e.mask
                .iter()
                .any(|b| b[0] >= b[2] || b[1] >= b[3] || b[2] > e.shape[1] || b[3] > e.shape[0])
        {
            return Err("frame, detector or region limits are inconsistent".into());
        }
        let mut dropped = vec![];
        let config = Config::from_development(e.config, &mut dropped);
        // After a restart the frames may have moved: keep settings and
        // calibration, drop the series, never fail the session restore.
        if kind == Transfer::Recovery {
            let mut missing: Vec<_> = e
                .sources
                .iter()
                .map(|s| &s.path)
                .filter(|p| !p.is_file())
                .collect();
            missing.dedup();
            if !missing.is_empty() {
                let shown: Vec<_> = missing
                    .iter()
                    .take(3)
                    .map(|p| p.display().to_string())
                    .collect();
                let more = if missing.len() > 3 {
                    format!(" and {} more", missing.len() - 3)
                } else {
                    String::new()
                };
                return Ok(Self::without_series(
                    config,
                    e.poni,
                    e.calibration_source,
                    format!(
                        "The rotation frames are no longer available ({}{more}).",
                        shown.join(", ")
                    ),
                ));
            }
        }
        let mut c = Crystal {
            config: config.clone(),
            sources: e.sources,
            protected_sources: e.protected_sources,
            shape: e.shape,
            frame: e.frame.min(n.saturating_sub(1)),
            mask: e.mask,
            excluded_frames: e.excluded_frames,
            reflection_filter: e.reflection_filter,
            ..Default::default()
        };
        // Re-derive the detector geometry with the current code; products made
        // with a geometry that now converts differently are not carried.
        if let Some(poni) = e.poni.clone() {
            match c.set_poni(&poni) {
                Ok(()) => c.calibration_source = e.calibration_source.clone(),
                Err(error) => dropped.push(format!("the detector calibration ({error})")),
            }
        } else if let Some(g) = e.initial_geometry {
            c.initial_geometry = Some(g);
            c.geometry = Some(g);
        }
        match products.and_then(|bytes| decode::<Products>(&bytes)) {
            Ok(p) if p.version != VERSION || p.generation != e.generation => {
                dropped.push("step results (they belong to another checkpoint)".into())
            }
            Ok(p) if kind == Transfer::Recovery && p.identity != identity() => {
                if p.stages.iter().any(|s| s.status == "complete") {
                    dropped.push("step results (made by another Dioptas build)".into());
                }
            }
            Ok(p) if !same(p.initial_geometry, c.initial_geometry) => {
                if p.stages.iter().any(|s| s.status == "complete") {
                    dropped.push("step results (the calibration converts differently now)".into());
                }
            }
            Ok(p) => {
                if let Err(reason) = c.adopt(p) {
                    dropped.push(reason);
                }
            }
            Err(error) => dropped.push(format!("step results ({error})")),
        }
        if e.later_results {
            dropped.push("refined geometry, intensities, scaling and structure".into());
        }
        if e.history {
            dropped.push("undo history".into());
        }
        c.error = e.error;
        c.track_offset = if e.track_offset < c.tracks.len() {
            e.track_offset
        } else {
            0
        };
        c.revision = e.revision.max(c.revision) + 1;
        // A remade stage 0 reports as after an explicit run of it.
        let current = if c.refresh_masks(control) {
            c.notice.take()
        } else {
            e.notice
        };
        if c.has_sources()
            && let Err(error) = c.preview("raw")
        {
            if kind == Transfer::Recovery {
                return Ok(Self::without_series(
                    config,
                    e.poni,
                    e.calibration_source,
                    format!("The rotation frames could not be read ({error})."),
                ));
            }
            c.error = Some(error);
        }
        let summary = (!dropped.is_empty()).then(|| {
            format!(
                "{} Run the affected steps again.",
                match kind {
                    Transfer::Development =>
                        format!("Backend updated. Not transferred: {}.", dropped.join("; ")),
                    Transfer::Recovery => format!(
                        "Previous single-crystal session restored. Not restored: {}.",
                        dropped.join("; ")
                    ),
                }
            )
        });
        c.notice = match (&summary, current) {
            (None, current) => current,
            (Some(s), None) => Some(s.clone()),
            (Some(s), Some(n)) => Some(format!("{s} {n}")),
        };
        Ok((c, summary))
    }

    /// Settings and calibration only, with a short reason to reopen frames.
    fn without_series(
        config: Config,
        poni: Option<crate::geometry::Geometry>,
        calibration_source: Option<PathBuf>,
        reason: String,
    ) -> (Crystal, Option<String>) {
        let mut c = Crystal {
            config,
            revision: 1,
            ..Default::default()
        };
        if let Some(poni) = poni
            && c.set_poni(&poni).is_ok()
        {
            c.calibration_source = calibration_source.clone();
            c.protected_sources.extend(calibration_source);
        }
        // A reopened series must be confirmed again before processing.
        c.config.confirmed = false;
        let summary =
            format!("{reason} Reopen them; single-crystal settings and calibration were kept.");
        c.notice = Some(summary.clone());
        (c, Some(summary))
    }

    /// Whether stage 0 holds nothing but the geometric DAC opening mask.
    fn geometric_masks_only(&self) -> bool {
        let c = &self.config;
        c.dac_on()
            && !c.seat_on()
            && !c.diamond_on()
            && !c.background
            && c.integration_method != "profile"
    }

    /// Take over carried step results after checking they fit this series.
    fn adopt(&mut self, p: Products) -> Result<(), String> {
        let n = self.sources.len();
        let pixels = self.shape[0] * self.shape[1];
        if p.peaks
            .iter()
            .any(|k| k.frame >= n || k.track >= p.tracks.len())
            || p.tracks.iter().any(|t| t.first > t.last || t.last >= n)
            || p.selected.is_some_and(|s| s >= p.cells.len())
            || p.shown.is_some_and(|s| s >= p.cells.len())
            || p.shadows
                .as_ref()
                .is_some_and(|s| s.block == 0 || s.first > s.last || s.last >= n || s.cells == 0)
            || p.diamonds.as_ref().is_some_and(|d| {
                d.frames.len() > n || d.frames.iter().flatten().any(|&i| i as usize >= pixels)
            })
        {
            return Err("step results (they do not match the loaded series)".into());
        }
        let Ok([mask, spots, lattices]) = <[Stage; 3]>::try_from(p.stages) else {
            return Err("step results (unexpected step count)".into());
        };
        if mask.status == "complete" && p.background {
            return Err("the omega background and all step results (rerun Prepare masks)".into());
        }
        // The DAC opening is pure geometry: remade from the settings instead.
        if let Some(parts) = p.masks.filter(|_| self.independent_masks()) {
            // Separate parts with their inputs: use the ones that still fit.
            self.parts = parts;
            self.activate_masks();
            self.stages[0] = mask;
        } else if !(mask.status == "complete" && self.geometric_masks_only()) {
            self.stages[0] = mask;
            self.shadows = p.shadows.map(Arc::new);
            self.diamonds = p.diamonds.map(Arc::new);
        }
        self.stages[1] = spots;
        self.stages[2] = lattices;
        self.peaks = p.peaks;
        self.tracks = p.tracks;
        self.cells = p.cells;
        self.selected = p.selected;
        self.shown = p.shown;
        // Saved before lattices had ticks: the chosen one is the kept one.
        if let Some(s) = self.selected.filter(|_| !self.cells.iter().any(|c| c.kept)) {
            self.cells[s].kept = true;
        }
        Ok(())
    }
}
