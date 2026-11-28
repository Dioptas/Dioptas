//! Calibration state, workflow commands, and transaction-sized history.
use super::*;
use serde::{Deserialize, Serialize};
use std::io::Read;
#[cfg(feature = "dioptrin")]
#[path = "calibration_fit.rs"]
mod native;
#[cfg(feature = "dioptrin")]
pub(super) use native::MassifCache;
const KEYS: [&str; 7] = [
    "dist",
    "poni1",
    "poni2",
    "rot1",
    "rot2",
    "rot3",
    "wavelength",
];
const MAX_POINTS: usize = 100_000;

#[cfg(feature = "dioptrin")]
#[derive(Clone)]
pub(super) struct RingCache {
    geometry: Geometry,
    targets: Vec<(usize, f64)>,
    intensities: Option<Vec<f64>>,
    shape: [usize; 2],
    value: Value,
}

#[cfg(feature = "dioptrin")]
#[derive(Clone)]
pub(super) struct PendingDistortion {
    pub(super) detector: Arc<dioptrin::detector::Detector>,
    pub(super) spline_text: Option<String>,
    pub(super) model_label: String,
    pub(super) configs: Vec<(usize, dioptrin::poni::Poni, f64)>,
}

#[derive(Clone, PartialEq, Serialize, Deserialize)]
pub(super) struct Group {
    pub ring: usize,
    pub points: Vec<[f64; 2]>,
}
const CUSTOM_SUFFIX: &str = " (custom)";
#[derive(Clone, PartialEq, Serialize, Deserialize)]
pub(super) struct Reference {
    pub name: String,
    pub spacings: Vec<f64>,
    #[serde(default)]
    pub intensities: Option<Vec<f64>>,
    pub content: String,
}
impl Reference {
    /// Name written to PONI files: custom calibrants drop the display suffix
    /// so the file names the spacings file itself.
    pub(super) fn recorded_name(&self) -> &str {
        self.name.strip_suffix(CUSTOM_SUFFIX).unwrap_or(&self.name)
    }
    pub(super) fn intensity(&self, ring: usize) -> Option<f64> {
        self.intensities
            .as_ref()?
            .get(ring.checked_sub(1)?)
            .copied()
            .filter(|v| v.is_finite())
    }
    pub(super) fn parse(name: &str, content: &str) -> Result<Self, String> {
        if content.len() > 1024 * 1024 {
            return Err("Calibrant files must be smaller than 1 MiB.".into());
        }
        let mut spacings = vec![];
        for line in content.lines() {
            let text = line.split('#').next().unwrap().trim();
            if text.is_empty() {
                continue;
            }
            let value: f64 = text
                .split_whitespace()
                .next()
                .unwrap()
                .parse()
                .map_err(|_| "Invalid calibrant d spacing.")?;
            if !value.is_finite() || value <= 0.0 {
                return Err("Calibrants require finite positive d spacings in Å.".into());
            }
            spacings.push(value);
        }
        spacings.sort_by(|a, b| b.total_cmp(a));
        spacings.dedup();
        if spacings.is_empty() || spacings.len() > 10_000 {
            return Err("A calibrant needs 1–10000 positive d spacings.".into());
        }
        Ok(Self {
            name: name.into(),
            spacings,
            intensities: None,
            content: content.into(),
        })
    }
    pub(super) fn parse_cif(
        name: &str,
        content: &str,
        wavelength_angstrom: f64,
    ) -> Result<Self, String> {
        if content.len() > 1024 * 1024 {
            return Err("Calibrant files must be smaller than 1 MiB.".into());
        }
        let (spacings, intensities) =
            crate::calibrant_intensity::parse_cif(content, wavelength_angstrom)?;
        Ok(Self {
            name: name.into(),
            spacings,
            intensities: Some(intensities),
            content: content.into(),
        })
    }
    fn named(name: &str) -> Result<Self, String> {
        let cal = dioptrin::calibration::Calibrant::builtin(name)
            .map_err(|_| "Choose an available calibrant.".to_string())?;
        let content = dioptrin::calibration::Calibrant::builtin_str(&cal.name)
            .unwrap_or_default()
            .to_string();
        let max_intensity = cal
            .intensities
            .iter()
            .flatten()
            .copied()
            .filter(|v| v.is_finite() && *v > 0.0)
            .fold(0.0_f64, f64::max);
        let intensities = (max_intensity > 0.0).then(|| {
            cal.intensities
                .iter()
                .map(|v| {
                    v.filter(|x| x.is_finite() && *x >= 0.0)
                        .map_or(0.0, |x| (x / max_intensity).clamp(0.0, 1.0))
                })
                .collect()
        });
        Ok(Self {
            name: cal.name,
            spacings: cal.d_spacings,
            intensities,
            content,
        })
    }
    pub fn angles(&self, wavelength: f64) -> Vec<(usize, f64)> {
        self.spacings
            .iter()
            .enumerate()
            .filter_map(|(i, d)| {
                let a = wavelength * 1e10 / (2.0 * d);
                (a > 0.0 && a <= 1.0).then(|| (i + 1, 2.0 * a.asin()))
            })
            .collect()
    }
}

#[derive(Clone, PartialEq, Serialize, Deserialize)]
pub(super) struct Calibration {
    pub reference: Reference,
    pub custom: Option<Reference>,
    pub picks: Vec<Group>,
    pub start: [f64; 7],
    pub free: [bool; 7],
    pub confirmed: bool,
    pub dirty: bool,
    pub rms: Option<f64>,
    pub source: String,
    pub saved: bool,
    pub reference_wavelength: f64,
    /// The reference was chosen, fitted against, or read from a file, rather
    /// than left at the session default; only then is it recorded in PONI files.
    #[serde(default)]
    pub reference_chosen: bool,
}
impl Default for Calibration {
    fn default() -> Self {
        Self {
            reference: Reference::named("LaB6").expect("bundled LaB6"),
            custom: None,
            picks: vec![],
            start: [0.2, 0.0, 0.0, 0.0, 0.0, 0.0, 0.3344e-10],
            free: [true, true, true, true, true, false, false],
            confirmed: false,
            dirty: false,
            rms: None,
            source: "none".into(),
            saved: false,
            reference_wavelength: 0.3344e-10,
            reference_chosen: false,
        }
    }
}
impl Calibration {
    pub fn free_count(&self) -> usize {
        self.free.iter().filter(|&&v| v).count()
    }
    pub fn choose(&self, name: &str) -> Result<Reference, String> {
        if let Some(custom) = &self.custom
            && (custom.name == name || custom.recorded_name() == name)
        {
            return Ok(custom.clone());
        }
        Reference::named(name)
    }
    pub(super) fn reference_from_filename(&self, path: &Path) -> Option<Reference> {
        let stem = path
            .file_stem()?
            .to_str()?
            .to_ascii_lowercase()
            .replace('-', "_");
        let names = dioptrin::calibration::Calibrant::builtin_names()
            .iter()
            .map(|&name| (name, name))
            .chain(
                self.custom
                    .iter()
                    .map(|reference| (reference.recorded_name(), reference.name.as_str())),
            );
        let mut matches = Vec::new();
        for (label, name) in names {
            let label = label.to_ascii_lowercase().replace('-', "_");
            for (start, matched) in stem.match_indices(&label) {
                let end = start + matched.len();
                if !stem[..start].ends_with(char::is_alphanumeric)
                    && !stem[end..].starts_with(char::is_alphanumeric)
                {
                    matches.push((start, end, name));
                }
            }
        }
        // An SRM name includes the base calibrant. Keep the specific match,
        // but require all remaining matches to identify the same reference.
        let mut names = matches.iter().filter_map(|&(start, end, name)| {
            (!matches.iter().any(|&(other_start, other_end, _)| {
                other_start <= start && end <= other_end && (other_start < start || end < other_end)
            }))
            .then_some(name)
        });
        let name = names.next()?;
        if names.all(|other| other == name) {
            self.choose(name).ok()
        } else {
            None
        }
    }
    pub fn modified(&mut self) {
        self.dirty = true;
        self.rms = None;
        self.saved = false;
    }
    pub fn parameters(&self, g: &Geometry) -> Value {
        let live = [
            g.dist,
            g.poni1,
            g.poni2,
            g.rot1,
            g.rot2,
            g.rot3,
            g.wavelength,
        ];
        let mut output = json!({});
        for (i, &key) in KEYS.iter().enumerate() {
            let value = if i == 0 || i == 6 || !self.free[i] {
                self.start[i]
            } else {
                live[i]
            };
            output[key] = json!({"value":value*if i==6 {1e10} else if i<3 {1000.0} else {1.0},"refine":self.free[i]});
        }
        output
    }
    fn fit_parameters(
        &mut self,
        parameters: &Value,
        polarization: &mut f64,
        value: Option<&Value>,
    ) -> Result<(), String> {
        let parameters = parameters
            .as_object()
            .ok_or("Fit parameters must be an object.")?;
        for (key, entry) in parameters {
            let i = KEYS
                .iter()
                .position(|k| *k == key)
                .ok_or("Unknown fit parameter.")?;
            check_keys(entry, &["value", "refine"])?;
            let free = boolean(&entry["refine"], "Refine checkbox")?;
            let (low, high) = if i == 6 {
                (0.01, 10.0)
            } else if i == 0 {
                (1.0, 10000.0)
            } else if i < 3 {
                (-1e5, 1e5)
            } else {
                (-std::f64::consts::TAU, std::f64::consts::TAU)
            };
            let v = finite(&entry["value"], key, low, high)?;
            self.start[i] = v * if i == 6 {
                1e-10
            } else if i < 3 {
                1e-3
            } else {
                1.0
            };
            self.free[i] = free;
        }
        if parameters.len() == 7 {
            self.confirmed = true;
        }
        if let Some(value) = value {
            *polarization = finite(value, "Polarization", -1.0, 1.0)?;
        }
        self.reference_wavelength = self.start[6];
        self.modified();
        Ok(())
    }
}

#[derive(Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub(super) struct Workflow {
    pub auto_increment: bool,
    pub search_size: usize,
    pub automatic_refinement: bool,
    pub algorithm: String,
    pub delta_tth: f64,
    pub mean_factor: f64,
    pub intensity_limit: f64,
    pub number_of_rings: usize,
}
impl Default for Workflow {
    fn default() -> Self {
        Self {
            auto_increment: true,
            search_size: 10,
            automatic_refinement: true,
            algorithm: "Massif".into(),
            delta_tth: 0.1,
            mean_factor: 3.0,
            intensity_limit: 55000.0,
            number_of_rings: 15,
        }
    }
}

#[derive(Clone, PartialEq, serde::Serialize, serde::Deserialize)]
pub(super) struct Snapshot {
    transformations: Vec<crate::transform::Transform>,
    original_pixels: Option<[f64; 2]>,
    #[serde(with = "crate::history_transfer::optional_arc")]
    original_detector: Option<Arc<dioptrin::detector::Detector>>,
    roi: Option<[usize; 4]>,
    geometry: Geometry,
    calibrated: bool,
    name: Option<String>,
    polarization: f64,
    data: Calibration,
}
#[derive(Default, Clone, serde::Serialize, serde::Deserialize)]
pub(super) struct History {
    #[serde(with = "crate::history_transfer::vec_arc")]
    pub(super) undo: Vec<Arc<(String, Snapshot, Snapshot, u64)>>,
    #[serde(with = "crate::history_transfer::vec_arc")]
    pub(super) redo: Vec<Arc<(String, Snapshot, Snapshot, u64)>>,
}
impl History {
    pub(super) fn record(&mut self, label: &str, before: Snapshot, after: Snapshot, sequence: u64) {
        if before == after {
            return;
        }
        self.redo.clear();
        self.undo
            .push(Arc::new((label.into(), before, after, sequence)));
        let reference_cost = |r: &Reference| r.content.len() + r.spacings.len() * 8 + r.name.len();
        let cost = |s: &Snapshot| {
            s.data
                .picks
                .iter()
                .map(|g| g.points.len() * 16 + 32)
                .sum::<usize>()
                + reference_cost(&s.data.reference)
                + s.data.custom.as_ref().map_or(0, reference_cost)
                + 1024
        };
        while self.undo.len() > 1
            && (self.undo.len() > 128
                || self
                    .undo
                    .iter()
                    .map(|entry| cost(&entry.1) + cost(&entry.2))
                    .sum::<usize>()
                    > 64 * 1024 * 1024)
        {
            self.undo.remove(0);
        }
    }
}

pub(super) fn is_command(action: &str) -> bool {
    matches!(
        action,
        "calibration_setup"
            | "workflow_settings"
            | "fit_parameters"
            | "pick_peak"
            | "remove_pick"
            | "remove_picks"
            | "clear_peaks"
            | "reassign_pick"
            | "calibrate"
            | "auto_calibrate"
            | "estimate_rot3"
            | "estimate_distortion"
            | "apply_distortion"
            | "save_distortion"
            | "detect_detector_modules"
            | "undo_calibration"
            | "redo_calibration"
            | "open_calibrant"
            | "validation_calibrant"
            | "save_peaks"
            | "load_peaks"
            | "calibration_engine"
            | "detector_file"
            | "distortion_file"
    )
}
impl Session {
    pub(super) fn calibration_snapshot(&self) -> Snapshot {
        Snapshot {
            transformations: self.settings.transformations.clone(),
            original_pixels: self.settings.original_pixels,
            original_detector: self.settings.original_detector.clone(),
            roi: self.settings.roi,
            geometry: self.settings.geometry.clone(),
            calibrated: self.settings.calibrated,
            name: self.settings.calibration_name.clone(),
            polarization: self.settings.polarization,
            data: self.calibration.clone(),
        }
    }
    fn restore_calibration(&mut self, s: Snapshot) -> Result<(), String> {
        if s.transformations != self.settings.transformations {
            // A loaded PONI can set the view before any image is open; there
            // are then no pixels to permute.
            if self.image.is_some() {
                self.reorient_view(&s.transformations)?;
            } else {
                self.settings.transformations = s.transformations;
            }
            self.settings.roi = s.roi;
        }
        self.settings.original_pixels = s.original_pixels;
        self.settings.original_detector = s.original_detector;
        self.settings.geometry = s.geometry;
        self.settings.calibrated = s.calibrated;
        self.settings.calibration_name = s.name;
        self.settings.polarization = s.polarization;
        self.calibration = s.data;
        Ok(())
    }
    pub(super) fn loaded_geometry(&mut self, source: &str) {
        self.inspection = None;
        let g = &self.settings.geometry;
        self.calibration.start = [
            g.dist,
            g.poni1,
            g.poni2,
            g.rot1,
            g.rot2,
            g.rot3,
            g.wavelength,
        ];
        self.calibration.confirmed = true;
        self.calibration.source = source.into();
        self.calibration.dirty = false;
        self.calibration.rms = None;
        self.calibration.saved = source == "loaded";
        self.calibration.reference_wavelength = g.wavelength;
    }
    pub(super) fn calibration_command(
        &mut self,
        action: &str,
        args: &Value,
        defer: bool,
    ) -> Result<Reply, String> {
        if action == "detect_detector_modules" {
            let mut extra = self.detect_detector_modules_transaction(args)?;
            extra["ok"] = json!(true);
            return Ok(Reply::metadata(extra));
        }
        let before = self.calibration_snapshot();
        let outcome = self.edit_calibration(action, args, defer);
        match outcome {
            Err(error) => Err(error),
            Ok(mut extra) => {
                self.control.check()?;
                if extra["noPeakFound"] == true || extra["autoCalibrateFailed"] == true {
                    // A missed click or unconverged auto-calibration does not edit calibration or its history.
                    extra["ok"] = json!(true);
                    return Ok(Reply::metadata(extra));
                }
                if let Some(image) = &self.image {
                    self.settings.geometry.sync_shape(image.shape)?;
                }
                let oriented = self.settings.transformations != before.transformations;
                if self.settings.geometry != before.geometry
                    || self.settings.calibrated != before.calibrated
                {
                    self.refresh_masks(&crate::control::Control::default())?;
                }
                if !matches!(
                    action,
                    "workflow_settings"
                        | "save_peaks"
                        | "estimate_distortion"
                        | "save_distortion"
                        | "undo_calibration"
                        | "redo_calibration"
                        | "calibration_engine"
                ) {
                    let after = self.calibration_snapshot();
                    self.calibration_history
                        .record(action, before, after, self.revision + 1);
                }
                self.revision += 1;
                let mut reply = self.snapshot(oriented);
                if let Some(extra) = extra.as_object_mut() {
                    for (key, value) in extra.iter() {
                        reply.result[key] = value.clone();
                    }
                }
                Ok(reply)
            }
        }
    }
    fn edit_calibration(
        &mut self,
        action: &str,
        args: &Value,
        defer: bool,
    ) -> Result<Value, String> {
        match action {
            "calibration_setup" => {
                check_keys(
                    args,
                    &[
                        "calibrant",
                        "wavelength",
                        "distance",
                        "pixel_x",
                        "pixel_y",
                        "detector",
                        "orientation",
                        "fit_tilts",
                    ],
                )?;
                if let Some(name) = args.get("calibrant") {
                    self.calibration.reference = self
                        .calibration
                        .choose(name.as_str().ok_or("Calibrant needs a name.")?)?;
                    self.calibration.reference_chosen = true;
                }
                // Choosing only the calibrant leaves a loaded or fitted geometry
                // valid; it needs a refit only when ring picks depend on it.
                let calibrant_only = args
                    .as_object()
                    .is_some_and(|keys| keys.len() == 1 && keys.contains_key("calibrant"));
                if let Some(v) = args.get("detector") {
                    self.settings
                        .geometry
                        .select_detector(v.as_str().ok_or("Choose a detector.")?)?;
                }

                if args.get("detector").is_some()
                    && let (Some(image), Some(d)) = (&self.image, &self.settings.geometry.detector)
                {
                    d.binning(image.shape)?;
                    [self.settings.geometry.pixel1, self.settings.geometry.pixel2] =
                        d.effective_pixels(image.shape);
                }
                if let Some(v) = args.get("orientation") {
                    let orientation = integer(v, "Detector orientation", 0, 4)? as u8;
                    let g = &mut self.settings.geometry;
                    let d = g.detector.get_or_insert_with(|| {
                        Arc::new(dioptrin::detector::Detector::custom(g.pixel1, g.pixel2))
                    });
                    Arc::make_mut(d).orientation = orientation;
                    g.auto_assign = false;
                }
                if let Some(v) = args.get("wavelength") {
                    self.calibration.start[6] = finite(v, "Wavelength (Å)", 0.01, 10.0)? * 1e-10;
                }
                if let Some(v) = args.get("distance") {
                    self.calibration.start[0] = finite(v, "Distance (mm)", 1.0, 10000.0)? * 1e-3;
                }
                if let Some(v) = args.get("pixel_x") {
                    self.settings.geometry.pixel2 =
                        finite(v, "Pixel width (µm)", 0.1, 5000.0)? * 1e-6;
                }
                if let Some(v) = args.get("pixel_y") {
                    self.settings.geometry.pixel1 =
                        finite(v, "Pixel height (µm)", 0.1, 5000.0)? * 1e-6;
                }
                if args.get("pixel_x").is_some() || args.get("pixel_y").is_some() {
                    let g = &mut self.settings.geometry;
                    g.auto_assign = false;
                    g.set_pixels([g.pixel1, g.pixel2], self.image.as_ref().map(|i| i.shape))?;
                }
                if let Some(v) = args.get("fit_tilts") {
                    let tilts = boolean(v, "Fit tilts")?;
                    for i in 3..6 {
                        self.calibration.free[i] = tilts && i != 5;
                        self.calibration.start[i] = 0.0;
                    }
                }
                if ["wavelength", "distance", "pixel_x", "pixel_y"]
                    .iter()
                    .all(|k| args.get(k).is_some())
                {
                    self.calibration.confirmed = true;
                }
                if ["detector", "orientation", "pixel_x", "pixel_y"]
                    .iter()
                    .any(|k| args.get(*k).is_some())
                {
                    self.rebase_detector_reset()?;
                }
                if calibrant_only {
                    self.calibration.reference_wavelength = if self.settings.calibrated {
                        self.settings.geometry.wavelength
                    } else {
                        self.calibration.start[6]
                    };
                    self.calibration.dirty =
                        self.settings.calibrated && !self.calibration.picks.is_empty();
                } else {
                    self.calibration.reference_wavelength = self.calibration.start[6];
                    self.calibration.dirty = self.settings.calibrated;
                }
                self.calibration.rms = None;
                self.calibration.saved = false;
            }
            "detector_file" | "distortion_file" => {
                check_keys(args, &["path", "reset", "defer_integration"])?;
                if args["reset"] == true {
                    if action == "detector_file" {
                        self.settings.geometry.select_detector("Custom")?;
                    } else {
                        self.settings.geometry.reset_spline();
                        if let Some(d) = &mut self.settings.original_detector {
                            Arc::make_mut(d).clear_spline();
                        }
                    }
                } else {
                    let file = path(args)?;
                    if action == "detector_file" {
                        self.settings.geometry.load_detector_file(file)?;
                    } else {
                        self.settings.geometry.frame_pixels = None;
                        self.settings.geometry.load_spline(file)?;
                    }
                }
                if let Some(image) = &self.image {
                    self.settings.geometry.validate_shape(image.shape)?;
                }
                self.settings.original_pixels = None;
                self.rebase_detector_reset()?;
                self.calibration.dirty = self.settings.calibrated;
                self.calibration.rms = None;
                self.calibration.saved = false;
            }
            "workflow_settings" => {
                let mut next = self.workflow.clone();
                for (key, v) in args.as_object().unwrap() {
                    match key.as_str() {
                        "autoIncrement" => next.auto_increment = boolean(v, key)?,
                        "automaticRefinement" => next.automatic_refinement = boolean(v, key)?,
                        "algorithm" => {
                            next.algorithm = match v.as_str() {
                                Some(s @ ("Massif" | "Blob")) => s.into(),
                                _ => return Err("Choose Massif or Blob peak search.".into()),
                            }
                        }
                        "searchSize" => next.search_size = integer(v, key, 1, 1000)?,
                        "numberOfRings" => next.number_of_rings = integer(v, key, 1, 500)?,
                        "deltaTth" => next.delta_tth = finite(v, key, 0.00001, 1e15)?,
                        "meanFactor" => next.mean_factor = finite(v, key, 0.00001, 1e15)?,
                        "intensityLimit" => next.intensity_limit = finite(v, key, 0.00001, 1e15)?,
                        _ => return Err(format!("Unknown calibration setting {key}.")),
                    }
                }
                self.workflow = next;
            }
            "fit_parameters" => {
                check_keys(args, &["parameters", "polarization"])?;
                self.calibration.fit_parameters(
                    &args["parameters"],
                    &mut self.settings.polarization,
                    args.get("polarization"),
                )?;
                self.calibration.dirty = self.settings.calibrated;
            }
            "calibration_engine" => {
                check_keys(args, &["engine"])?;
                if args["engine"]
                    != if cfg!(feature = "dioptrin") {
                        "dioptrin"
                    } else {
                        "none"
                    }
                {
                    return Err(
                        "Only compiled native engines are available; Python will not be started."
                            .into(),
                    );
                }
            }
            "pick_peak" => {
                check_keys(args, &["x", "y", "ring", "automatic", "search_size"])?;
                let image = self.image.as_ref().ok_or("Open a calibrant image first.")?;
                let values = self.scientific_values();
                let x = finite(&args["x"], "x", 0.0, image.shape[1] as f64 - 1.0)?;
                let y = finite(&args["y"], "y", 0.0, image.shape[0] as f64 - 1.0)?;
                let rings = self
                    .calibration
                    .reference
                    .angles(self.calibration.reference_wavelength);
                let ring = integer(&args["ring"], "Ring number", 1, rings.len())?;
                let automatic = args
                    .get("automatic")
                    .map(|v| boolean(v, "Automatic peak search"))
                    .transpose()?
                    .unwrap_or(true);
                let points = if automatic {
                    self.seeded_peaks([y, x])?
                } else {
                    let size = args
                        .get("search_size")
                        .map(|v| integer(v, "Search size", 1, 1000))
                        .transpose()?
                        .unwrap_or(self.workflow.search_size);
                    let row = (y - size as f64 * 0.5).round_ties_even().max(0.0) as usize;
                    let col = (x - size as f64 * 0.5).round_ties_even().max(0.0) as usize;
                    let mut best = None;
                    for yy in row..(row + size).min(image.shape[0]) {
                        for xx in col..(col + size).min(image.shape[1]) {
                            let value = values[yy * image.shape[1] + xx];
                            if value.is_finite()
                                && (!self.settings.use_mask
                                    || self.effective_mask[yy * image.shape[1] + xx] == 0)
                                && best.is_none_or(|(_, _, v)| value > v)
                            {
                                best = Some((yy, xx, value));
                            }
                        }
                    }
                    best.map(|(r, c, _)| vec![[r as f64, c as f64]])
                        .unwrap_or_default()
                };
                if points.is_empty() {
                    return Ok(json!({"pickedCount":0,"noPeakFound":true}));
                }
                if self
                    .calibration
                    .picks
                    .iter()
                    .map(|g| g.points.len())
                    .sum::<usize>()
                    + points.len()
                    > MAX_POINTS
                {
                    return Err("Calibration exceeds 100000 picked points.".into());
                }
                let count = points.len();
                self.calibration.picks.push(Group { ring, points });
                self.calibration.modified();
                return Ok(
                    json!({"pickedCount":count,"nextRing":if self.workflow.auto_increment {(ring+1).min(rings.len())} else {ring}}),
                );
            }
            "remove_pick" | "remove_picks" | "reassign_pick" => {
                let n = self.calibration.picks.len();
                if n == 0 {
                    return Err("No picked peak groups.".into());
                }
                if action == "reassign_pick" {
                    check_keys(args, &["index", "ring"])?;
                    let i = integer(&args["index"], "Selection index", 0, n - 1)?;
                    let ring = integer(
                        &args["ring"],
                        "Ring number",
                        1,
                        self.calibration
                            .reference
                            .angles(self.calibration.reference_wavelength)
                            .len(),
                    )?;
                    self.calibration.picks[i].ring = ring;
                } else {
                    let mut indices = if action == "remove_pick" {
                        check_keys(args, &["index"])?;
                        vec![integer(&args["index"], "Selection index", 0, n - 1)?]
                    } else {
                        check_keys(args, &["indices"])?;
                        args["indices"]
                            .as_array()
                            .ok_or("Select peak groups to remove.")?
                            .iter()
                            .map(|v| integer(v, "Selection index", 0, n - 1))
                            .collect::<Result<Vec<_>, _>>()?
                    };
                    indices.sort_unstable();
                    indices.dedup();
                    for i in indices.into_iter().rev() {
                        self.calibration.picks.remove(i);
                    }
                }
                self.calibration.modified();
            }
            "clear_peaks" => {
                check_keys(args, &[])?;
                self.calibration.picks.clear();
                self.calibration.modified();
            }
            "open_calibrant" => {
                check_keys(args, &["path", "validation"])?;
                let file = path(args)?;
                let content = read_text(file, 1024 * 1024)?;
                let name = format!(
                    "{}{CUSTOM_SUFFIX}",
                    file.file_stem().unwrap_or_default().to_string_lossy()
                );
                let is_cif = file
                    .extension()
                    .and_then(|e| e.to_str())
                    .is_some_and(|e| e.eq_ignore_ascii_case("cif"));
                let wavelength_angstrom = if self.settings.calibrated {
                    self.settings.geometry.wavelength
                } else {
                    self.calibration.start[6]
                } * 1e10;
                let reference = if is_cif {
                    Reference::parse_cif(&name, &content, wavelength_angstrom)?
                } else {
                    Reference::parse(&name, &content)?
                };
                self.calibration.custom = Some(reference.clone());
                self.calibration.reference = reference;
                self.calibration.reference_chosen = true;
                self.calibration.rms = None;
                self.calibration.dirty = self.settings.calibrated
                    && !args
                        .get("validation")
                        .map(|v| boolean(v, "Validation"))
                        .transpose()?
                        .unwrap_or(false);
                self.calibration.reference_wavelength = if self.settings.calibrated {
                    self.settings.geometry.wavelength
                } else {
                    self.calibration.start[6]
                };
            }
            "validation_calibrant" => {
                check_keys(args, &["calibrant"])?;
                self.calibration.reference = self
                    .calibration
                    .choose(args["calibrant"].as_str().ok_or("Choose a calibrant.")?)?;
                self.calibration.reference_chosen = true;
                self.calibration.reference_wavelength = if self.settings.calibrated {
                    self.settings.geometry.wavelength
                } else {
                    self.calibration.start[6]
                };
                self.calibration.rms = None;
            }
            "save_peaks" => {
                check_keys(args, &["path"])?;
                self.require_image()?;
                if self.calibration.picks.is_empty() {
                    return Err("Pick calibration peaks before saving them.".into());
                }
                let mut file = path(args)?.to_path_buf();
                if file.extension().is_none() {
                    file.set_extension("json");
                }
                let document = json!({"format":"dioptas-calibration-peaks","version":1,"coordinates":"row-column-bottom-left","imageShape":self.image.as_ref().unwrap().shape,
                    "imageTransformations":self.settings.transformations,"calibrant":{"name":self.calibration.reference.name,"dSpacingsAngstrom":self.calibration.reference.spacings},"groups":self.calibration.picks});
                atomic_write(
                    &file,
                    format!(
                        "{}\n",
                        serde_json::to_string_pretty(&document).map_err(|e| e.to_string())?
                    )
                    .as_bytes(),
                )?;
                return Ok(json!({"savedPath":file}));
            }
            "load_peaks" => {
                check_keys(args, &["path"])?;
                self.require_image()?;
                let document: Value =
                    serde_json::from_str(&read_text(path(args)?, 16 * 1024 * 1024)?)
                        .map_err(|e| e.to_string())?;
                if document["format"] != "dioptas-calibration-peaks"
                    || document["version"].as_u64() != Some(1)
                    || document["coordinates"] != "row-column-bottom-left"
                {
                    return Err("Choose a Dioptas calibration peaks file (version 1).".into());
                }
                let shape = self.image.as_ref().unwrap().shape;
                if document["imageShape"] != json!(shape)
                    || document["imageTransformations"] != json!(self.settings.transformations)
                {
                    return Err(
                        "The saved peaks require the same image dimensions and orientation.".into(),
                    );
                }
                let saved_spacings = document["calibrant"]["dSpacingsAngstrom"]
                    .as_array()
                    .filter(|arr| {
                        !arr.is_empty() && arr.len() <= self.calibration.reference.spacings.len()
                    })
                    .ok_or("Choose the saved peaks' calibrant before loading them.")?;
                if !saved_spacings
                    .iter()
                    .zip(&self.calibration.reference.spacings)
                    .all(|(saved, current)| {
                        saved
                            .as_f64()
                            .is_some_and(|v| (v - current).abs() <= 1e-9 * current.max(1.0))
                    })
                {
                    return Err("Choose the saved peaks' calibrant before loading them.".into());
                }
                let groups: Vec<Group> = serde_json::from_value(document["groups"].clone())
                    .map_err(|e| e.to_string())?;
                validate_groups(&groups, shape, self.calibration.reference.spacings.len())?;
                self.calibration.picks = groups;
                self.calibration.modified();
            }
            "undo_calibration" | "redo_calibration" => {
                check_keys(args, &["defer_integration"])?;
                let (source, destination) = if action == "undo_calibration" {
                    (
                        &mut self.calibration_history.undo,
                        &mut self.calibration_history.redo,
                    )
                } else {
                    (
                        &mut self.calibration_history.redo,
                        &mut self.calibration_history.undo,
                    )
                };
                let entry = source
                    .last()
                    .ok_or("No calibration edit to undo/redo.")?
                    .clone();
                let snapshot = if action == "undo_calibration" {
                    entry.1.clone()
                } else {
                    entry.2.clone()
                };
                source.pop();
                destination.push(entry);
                self.restore_calibration(snapshot)?;
                self.calculate(defer)?;
                let ring = self
                    .calibration
                    .picks
                    .iter()
                    .map(|p| p.ring)
                    .max()
                    .unwrap_or(0)
                    + 1;
                return Ok(
                    json!({"nextRing":ring.min(self.calibration.reference.angles(self.calibration.reference_wavelength).len().max(1))}),
                );
            }
            "calibrate" => {
                self.fit_transaction(args, defer)?;
            }
            "auto_calibrate" => {
                return self.auto_calibrate_transaction(args, defer);
            }
            "estimate_rot3" => {
                return self.estimate_rot3_transaction(args, defer);
            }
            "estimate_distortion" => {
                return self.estimate_distortion_transaction(args);
            }
            "apply_distortion" => {
                return self.apply_distortion_transaction(args, defer);
            }
            "save_distortion" => {
                return self.save_distortion_transaction(args);
            }
            _ => unreachable!(),
        }
        Ok(json!({}))
    }
    pub(super) fn calibration_payload(&self) -> Value {
        let c = &self.calibration;
        let g = &self.settings.geometry;
        let angles = c.reference.angles(c.reference_wavelength);
        let mut names: Vec<_> = dioptrin::calibration::Calibrant::builtin_names()
            .iter()
            .map(|&n| n.to_string())
            .collect();
        if let Some(custom) = &c.custom {
            names.push(custom.name.clone());
        }
        let lines: Vec<_> = angles
            .iter()
            .map(|&(ring, t)| {
                let x = match self.settings.unit.as_str() {
                    "q_A^-1" => {
                        4.0 * std::f64::consts::PI * (t / 2.0).sin() / (g.wavelength * 1e10)
                    }
                    "d_A" => g.wavelength * 1e10 / (2.0 * (t / 2.0).sin()),
                    _ => t.to_degrees(),
                };
                match c.reference.intensity(ring) {
                    Some(intensity) => json!({"ring": ring, "x": x, "intensity": intensity}),
                    None => json!({"ring": ring, "x": x}),
                }
            })
            .collect();
        let cake_rings: Vec<_> = angles
            .iter()
            .map(|&(ring, t)| match c.reference.intensity(ring) {
                Some(intensity) => {
                    let strength = intensity.clamp(0.0, 1.0).sqrt();
                    json!({
                        "ring": ring,
                        "twoTheta": t.to_degrees(),
                        "intensity": intensity,
                        "lineWidth": 1.2 + 2.8 * strength,
                        "opacity": 0.35 + 0.45 * strength,
                    })
                }
                None => json!({"ring": ring, "twoTheta": t.to_degrees()}),
            })
            .collect();
        json!({"setupConfirmed":c.confirmed,"workflow":self.workflow,"parameters":c.parameters(g),"freeParameterCount":c.free_count(),"polarization":self.settings.polarization,"fitWavelength":c.free[6],
            "geometrySource":c.source,"canUndo":!self.calibration_history.undo.is_empty()||self.integration_history.can_undo(),"canRedo":!self.calibration_history.redo.is_empty()||self.integration_history.can_redo(),"fitTilts":c.free[3],
            "calibrant":c.reference.name,"calibrants":names,"distance":c.start[0]*1000.0,"wavelength":c.start[6]*1e10,"fitDirty":c.dirty,"rmsDegrees":c.rms,"saved":c.saved,"picks":c.picks,
            "rings":cake_rings,"referenceLines":lines,
            "steps":[if self.image.is_some(){"done"}else{"attention"},if !c.picks.is_empty(){"done"}else if self.settings.calibrated{"skipped"}else{"attention"},if self.settings.calibrated{"done"}else if !c.picks.is_empty(){"attention"}else{"pending"},if self.settings.calibrated{"done"}else{"pending"}]})
    }
    #[cfg(not(feature = "dioptrin"))]
    fn seeded_peaks(&self, _seed: [f64; 2]) -> Result<Vec<[f64; 2]>, String> {
        Err("Automatic picking requires a compiled native engine; build with --features dioptrin. No Python fallback was used.".into())
    }
    #[cfg(not(feature = "dioptrin"))]
    fn fit_transaction(&mut self, _args: &Value, _defer: bool) -> Result<(), String> {
        Err("Calibration fitting requires a compiled native engine; build with --features dioptrin. No Python fallback was used.".into())
    }
    #[cfg(not(feature = "dioptrin"))]
    fn auto_calibrate_transaction(&mut self, _args: &Value, _defer: bool) -> Result<Value, String> {
        Err("Automatic calibration requires a compiled native engine; build with --features dioptrin. No Python fallback was used.".into())
    }
    #[cfg(not(feature = "dioptrin"))]
    fn estimate_rot3_transaction(&mut self, _args: &Value, _defer: bool) -> Result<Value, String> {
        Err("Polarization rot3 estimation requires a compiled native engine; build with --features dioptrin. No Python fallback was used.".into())
    }
    #[cfg(not(feature = "dioptrin"))]
    fn estimate_distortion_transaction(&mut self, _args: &Value) -> Result<Value, String> {
        Err("Distortion estimation requires a compiled native engine; build with --features dioptrin. No Python fallback was used.".into())
    }
    #[cfg(not(feature = "dioptrin"))]
    fn apply_distortion_transaction(
        &mut self,
        _args: &Value,
        _defer: bool,
    ) -> Result<Value, String> {
        Err("Distortion estimation requires a compiled native engine; build with --features dioptrin. No Python fallback was used.".into())
    }
    #[cfg(not(feature = "dioptrin"))]
    fn save_distortion_transaction(&mut self, _args: &Value) -> Result<Value, String> {
        Err("Distortion export requires a compiled native engine; build with --features dioptrin. No Python fallback was used.".into())
    }
    fn detect_detector_modules_transaction(&self, args: &Value) -> Result<Value, String> {
        check_keys(args, &[])?;
        let image = self
            .image
            .as_ref()
            .ok_or("Open a detector image before detecting modules.")?;
        // Use the raw oriented detector values without user-drawn masks so that
        // background subtraction or beamstop masks cannot create or hide gap bands.
        let detected = detect_detector_modules_in_image(
            &image.values,
            image.shape,
            Some(&image.source_dtype),
            true,
        );
        match detected {
            Some(layout) => {
                let notice = format!(
                    "Detected {}×{} modules ({}×{} px, gap {}×{} px) from image gaps.",
                    layout.module_rows,
                    layout.module_cols,
                    layout.module_height,
                    layout.module_width,
                    layout.gap_height,
                    layout.gap_width,
                );
                Ok(json!({
                    "detectedModules": {
                        "detected": true,
                        "moduleHeight": layout.module_height,
                        "moduleWidth": layout.module_width,
                        "gapHeight": layout.gap_height,
                        "gapWidth": layout.gap_width,
                        "moduleRows": layout.module_rows,
                        "moduleCols": layout.module_cols,
                        "notice": notice,
                    }
                }))
            }
            None => Ok(json!({
                "detectedModules": {
                    "detected": false,
                    "notice": "No regular inter-module gap rows or columns were detected in the active image.",
                }
            })),
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) struct DetectedModuleLayout {
    pub module_height: usize,
    pub module_width: usize,
    pub gap_height: usize,
    pub gap_width: usize,
    pub module_rows: usize,
    pub module_cols: usize,
}

/// Detect regular tiled-detector module dimensions and inter-module gaps by
/// locating full rows and columns dominated by sentinel gap pixels (negative
/// values like Pilatus `-1`, non-finite values, upper-sentinel values like
/// Eiger `u32::MAX` / `65535` / `i16::MAX`, or optionally all-zero gap bands on
/// dense images when `allow_zero_gaps` is true).
pub(crate) fn detect_detector_modules_in_image(
    values: &[f64],
    shape: [usize; 2],
    source_dtype: Option<&str>,
    allow_zero_gaps: bool,
) -> Option<DetectedModuleLayout> {
    let [rows, cols] = shape;
    if rows < 32 || cols < 32 || values.len() != rows * cols {
        return None;
    }

    let exact_upper: &[f64] = match source_dtype {
        Some("U16") => &[u16::MAX as f64],
        Some("I16") => &[i16::MAX as f64],
        Some("U32") => &[u32::MAX as f64, i32::MAX as f64, u16::MAX as f64],
        Some("I32") => &[i32::MAX as f64],
        _ => &[],
    };
    let mut max_finite = f64::NEG_INFINITY;
    if exact_upper.is_empty() {
        for &v in values {
            if v.is_finite() && v > max_finite {
                max_finite = v;
            }
        }
    }
    let has_upper_sentinel =
        exact_upper.is_empty() && max_finite.is_finite() && max_finite >= 65_535.0;
    let upper_threshold = max_finite - (max_finite * 1e-6).max(1.0);

    let mut row_strict = vec![0usize; rows];
    let mut col_strict = vec![0usize; cols];
    let mut row_zero = vec![0usize; rows];
    let mut col_zero = vec![0usize; cols];
    let mut row_positive = vec![0usize; rows];

    for r in 0..rows {
        let row_offset = r * cols;
        for c in 0..cols {
            let idx = row_offset + c;
            let v = values[idx];
            let is_upper = if !exact_upper.is_empty() {
                exact_upper.contains(&v)
            } else {
                has_upper_sentinel && v.is_finite() && v >= upper_threshold
            };
            let is_strict = !v.is_finite() || v < 0.0 || is_upper;
            if is_strict {
                row_strict[r] += 1;
                col_strict[c] += 1;
                row_zero[r] += 1;
                col_zero[c] += 1;
            } else if v == 0.0 {
                row_zero[r] += 1;
                col_zero[c] += 1;
            } else {
                row_positive[r] += 1;
            }
        }
    }

    let row_gap_strict: Vec<bool> = row_strict.iter().map(|&n| n * 100 >= cols * 95).collect();
    let col_gap_strict: Vec<bool> = col_strict.iter().map(|&n| n * 100 >= rows * 95).collect();

    let mut row_tiling = detect_axis_tiling(&row_gap_strict);
    let mut col_tiling = detect_axis_tiling(&col_gap_strict);

    if allow_zero_gaps && (row_tiling.is_none() || col_tiling.is_none()) {
        let mut positive_fracs: Vec<usize> = row_positive.clone();
        positive_fracs.sort_unstable();
        let median_positive = positive_fracs[rows / 2];
        // Only fall back to zero-valued gaps when active rows are reasonably dense.
        if median_positive * 100 >= cols * 30 {
            if row_tiling.is_none() {
                let row_gap_zero: Vec<bool> =
                    row_zero.iter().map(|&n| n * 100 >= cols * 98).collect();
                row_tiling = detect_axis_tiling(&row_gap_zero);
            }
            if col_tiling.is_none() {
                let col_gap_zero: Vec<bool> =
                    col_zero.iter().map(|&n| n * 100 >= rows * 98).collect();
                col_tiling = detect_axis_tiling(&col_gap_zero);
            }
        }
    }

    match (row_tiling, col_tiling) {
        (None, None) => None,
        (Some((mh, gh, mr)), Some((mw, gw, mc))) => Some(DetectedModuleLayout {
            module_height: mh,
            module_width: mw,
            gap_height: gh,
            gap_width: gw,
            module_rows: mr,
            module_cols: mc,
        }),
        (Some((mh, gh, mr)), None) => Some(DetectedModuleLayout {
            module_height: mh,
            module_width: cols,
            gap_height: gh,
            gap_width: 0,
            module_rows: mr,
            module_cols: 1,
        }),
        (None, Some((mw, gw, mc))) => Some(DetectedModuleLayout {
            module_height: rows,
            module_width: mw,
            gap_height: 0,
            gap_width: gw,
            module_rows: 1,
            module_cols: mc,
        }),
    }
}

/// Build a binary mask (`1` = gap, `0` = active) for a detected regular tiled
/// detector layout.
pub(crate) fn gap_mask_for_layout(
    layout: DetectedModuleLayout,
    [rows, cols]: [usize; 2],
) -> Vec<u8> {
    let pitch_r = layout.module_height + layout.gap_height;
    let pitch_c = layout.module_width + layout.gap_width;
    let mut mask = vec![0u8; rows * cols];
    for r in 0..rows {
        if layout.gap_height > 0 && (r % pitch_r) >= layout.module_height {
            mask[r * cols..(r + 1) * cols].fill(1);
            continue;
        }
        if layout.gap_width > 0 {
            let row_offset = r * cols;
            for c in 0..cols {
                if (c % pitch_c) >= layout.module_width {
                    mask[row_offset + c] = 1;
                }
            }
        }
    }
    mask
}

/// Extract a regular `(module_size, gap_size, module_count)` tiling from a 1D
/// per-row or per-column gap indicator slice.
fn detect_axis_tiling(is_gap: &[bool]) -> Option<(usize, usize, usize)> {
    let len = is_gap.len();
    let mut interior_bands = Vec::new();
    let mut i = 0;
    while i < len {
        if is_gap[i] {
            let start = i;
            while i < len && is_gap[i] {
                i += 1;
            }
            let end = i;
            if start > 0 && end < len {
                interior_bands.push((start, end));
            }
        } else {
            i += 1;
        }
    }
    if interior_bands.is_empty() {
        return None;
    }

    if let Some(found) = try_regular_bands(&interior_bands, len) {
        return Some(found);
    }

    // If stray thin dead lines broke regularity, retry with bands matching the widest interior gap.
    let max_gap = interior_bands
        .iter()
        .map(|&(s, e)| e - s)
        .max()
        .unwrap_or(0);
    if max_gap >= 2 {
        let filtered: Vec<(usize, usize)> = interior_bands
            .iter()
            .copied()
            .filter(|&(s, e)| (e - s).abs_diff(max_gap) <= 2)
            .collect();
        if !filtered.is_empty() && filtered.len() < interior_bands.len() {
            return try_regular_bands(&filtered, len);
        }
    }
    None
}

fn try_regular_bands(bands: &[(usize, usize)], len: usize) -> Option<(usize, usize, usize)> {
    if bands.is_empty() {
        return None;
    }
    let k = bands.len() + 1;
    let mut active = Vec::with_capacity(k);
    let mut gaps = Vec::with_capacity(bands.len());

    active.push(bands[0].0);
    for (idx, &(s, e)) in bands.iter().enumerate() {
        gaps.push(e - s);
        if idx + 1 < bands.len() {
            active.push(bands[idx + 1].0.checked_sub(e)?);
        }
    }
    active.push(len.checked_sub(bands[bands.len() - 1].1)?);

    let min_a = *active.iter().min()?;
    let max_a = *active.iter().max()?;
    let min_g = *gaps.iter().min()?;
    let max_g = *gaps.iter().max()?;

    // Inter-module gaps must be at least 2 px wide (ignores isolated single dead lines),
    // strictly narrower than the modules themselves, and consistent in width & pitch.
    if min_a < 16 || max_a - min_a > 2 || min_g < 2 || max_g - min_g > 2 || max_g >= min_a {
        return None;
    }

    active.sort_unstable();
    gaps.sort_unstable();
    let mut mod_s = active[active.len() / 2];
    let gap_s = gaps[gaps.len() / 2];

    if len > (k - 1) * gap_s && (len - (k - 1) * gap_s).is_multiple_of(k) {
        let exact = (len - (k - 1) * gap_s) / k;
        if exact.abs_diff(mod_s) <= 2 {
            mod_s = exact;
        }
    }

    let total = k * mod_s + (k - 1) * gap_s;
    if total.abs_diff(len) > k {
        return None;
    }
    Some((mod_s, gap_s, k))
}

fn read_text(path: &Path, limit: usize) -> Result<String, String> {
    let mut content = String::new();
    std::fs::File::open(path)
        .map_err(|e| e.to_string())?
        .take(limit as u64 + 1)
        .read_to_string(&mut content)
        .map_err(|e| e.to_string())?;
    if content.len() > limit {
        return Err("Calibration file exceeds its size limit.".into());
    }
    Ok(content)
}
fn validate_groups(groups: &[Group], shape: [usize; 2], rings: usize) -> Result<(), String> {
    if groups.is_empty()
        || groups.len() > 10_000
        || groups.iter().map(|g| g.points.len()).sum::<usize>() > MAX_POINTS
    {
        return Err("Invalid number of picked peak groups/points.".into());
    }
    for group in groups {
        if group.ring == 0
            || group.ring > rings
            || group.points.is_empty()
            || group.points.iter().any(|p| {
                !p[0].is_finite()
                    || !p[1].is_finite()
                    || p[0] < 0.0
                    || p[1] < 0.0
                    || p[0] > shape[0] as f64 - 1.0
                    || p[1] > shape[1] as f64 - 1.0
            })
        {
            return Err("Peak coordinates and integer ring assignments must be valid for this image and calibrant.".into());
        }
    }
    Ok(())
}

#[cfg(test)]
mod module_detection_tests {
    use super::*;

    fn synthetic_tiled(
        layout: DetectedModuleLayout,
        bg: f64,
        gap_val: f64,
    ) -> (Vec<f64>, [usize; 2]) {
        let h = layout.module_rows * layout.module_height
            + (layout.module_rows - 1) * layout.gap_height;
        let w =
            layout.module_cols * layout.module_width + (layout.module_cols - 1) * layout.gap_width;
        let pitch_r = layout.module_height + layout.gap_height;
        let pitch_c = layout.module_width + layout.gap_width;
        let mut data = vec![bg; h * w];
        for r in 0..h {
            let in_row_gap = layout.gap_height > 0 && (r % pitch_r) >= layout.module_height;
            for c in 0..w {
                let in_col_gap = layout.gap_width > 0 && (c % pitch_c) >= layout.module_width;
                if in_row_gap || in_col_gap {
                    data[r * w + c] = gap_val;
                }
            }
        }
        (data, [h, w])
    }

    #[test]
    fn detects_eiger_max_intensity_gaps_with_hot_pixels() {
        let expected = DetectedModuleLayout {
            module_height: 64,
            module_width: 80,
            gap_height: 12,
            gap_width: 6,
            module_rows: 3,
            module_cols: 2,
        };
        let (mut data, shape) = synthetic_tiled(expected, 120.0, u32::MAX as f64);
        // Add scattered saturated hot pixels inside active modules.
        data[10 * shape[1] + 15] = u32::MAX as f64;
        data[20 * shape[1] + 40] = u32::MAX as f64;
        let detected = detect_detector_modules_in_image(&data, shape, Some("U32"), false).unwrap();
        assert_eq!(detected, expected);
    }

    #[test]
    fn detects_single_axis_gaps_and_zero_gaps() {
        let expected = DetectedModuleLayout {
            module_height: 48,
            module_width: 120,
            gap_height: 8,
            gap_width: 0,
            module_rows: 3,
            module_cols: 1,
        };
        let (data, shape) = synthetic_tiled(expected, 50.0, 0.0);
        // Zero gaps are detected when allow_zero_gaps = true (Per-module dialog),
        // but rejected in strict mode (auto-masking on load).
        assert_eq!(
            detect_detector_modules_in_image(&data, shape, Some("F64"), true),
            Some(expected)
        );
        assert_eq!(
            detect_detector_modules_in_image(&data, shape, Some("F64"), false),
            None
        );
    }

    #[test]
    fn ignores_stray_single_dead_row_alongside_real_gaps() {
        let expected = DetectedModuleLayout {
            module_height: 64,
            module_width: 80,
            gap_height: 10,
            gap_width: 6,
            module_rows: 3,
            module_cols: 2,
        };
        let (mut data, shape) = synthetic_tiled(expected, 200.0, -1.0);
        // Add a 1-px dead row inside the first module.
        for c in 0..shape[1] {
            data[30 * shape[1] + c] = -1.0;
        }
        let detected = detect_detector_modules_in_image(&data, shape, Some("I32"), false).unwrap();
        assert_eq!(detected, expected);
    }

    #[test]
    fn rejects_circular_zero_corner_detector_and_single_dead_line() {
        let h = 256;
        let w = 256;
        let mut circular = vec![0.0; h * w];
        let cx = 128.0_f64;
        let cy = 128.0_f64;
        for r in 0..h {
            for c in 0..w {
                if (r as f64 - cy).hypot(c as f64 - cx) <= 122.0 {
                    circular[r * w + c] = 500.0;
                }
            }
        }
        assert_eq!(
            detect_detector_modules_in_image(&circular, [h, w], Some("U16"), true),
            None
        );

        let mut flat = vec![100.0; h * w];
        for c in 0..w {
            flat[128 * w + c] = -1.0;
        }
        assert_eq!(
            detect_detector_modules_in_image(&flat, [h, w], Some("I32"), true),
            None
        );
        assert_eq!(
            detect_detector_modules_in_image(&vec![10.0; 16 * 16], [16, 16], None, true),
            None
        );
    }

    #[test]
    fn detects_nan_i16_u16_max_gaps_and_mixed_chip_gaps() {
        let nan_layout = DetectedModuleLayout {
            module_height: 64,
            module_width: 64,
            gap_height: 16,
            gap_width: 8,
            module_rows: 2,
            module_cols: 2,
        };
        let (nan_data, nan_shape) = synthetic_tiled(nan_layout, 80.0, f64::NAN);
        assert_eq!(
            detect_detector_modules_in_image(&nan_data, nan_shape, Some("F32"), false),
            Some(nan_layout)
        );

        // Signed 16-bit max sentinel (i16::MAX = 32767).
        let (i16_data, i16_shape) = synthetic_tiled(nan_layout, 80.0, i16::MAX as f64);
        assert_eq!(
            detect_detector_modules_in_image(&i16_data, i16_shape, Some("I16"), false),
            Some(nan_layout)
        );

        // Eiger-like 16-bit max sentinel (65535) with 2-px inter-chip gaps inside modules.
        let eiger_layout = DetectedModuleLayout {
            module_height: 128,
            module_width: 128,
            gap_height: 36,
            gap_width: 12,
            module_rows: 2,
            module_cols: 2,
        };
        let (mut data, shape) = synthetic_tiled(eiger_layout, 100.0, 65_535.0);
        // Add 2-px inter-chip gap rows inside each module (should be ignored in favor of 36-px module gap).
        for chip_r in [63, 64, 128 + 36 + 63, 128 + 36 + 64] {
            for c in 0..shape[1] {
                data[chip_r * shape[1] + c] = 65_535.0;
            }
        }
        assert_eq!(
            detect_detector_modules_in_image(&data, shape, Some("U16"), false),
            Some(eiger_layout)
        );
    }

    #[test]
    fn rejects_sparse_zero_image_with_accidental_zero_rows() {
        // Sparse photon-counting image (< 30% positive pixels per row) with periodic zero rows.
        let layout = DetectedModuleLayout {
            module_height: 48,
            module_width: 120,
            gap_height: 8,
            gap_width: 0,
            module_rows: 3,
            module_cols: 1,
        };
        let (mut data, shape) = synthetic_tiled(layout, 0.0, 0.0);
        // Sprinkle 5% nonzero counts on active rows.
        for r in 0..shape[0] {
            if (r % (48 + 8)) < 48 {
                for c in (0..shape[1]).step_by(20) {
                    data[r * shape[1] + c] = 1.0;
                }
            }
        }
        assert_eq!(
            detect_detector_modules_in_image(&data, shape, Some("U32"), true),
            None
        );
    }
}
