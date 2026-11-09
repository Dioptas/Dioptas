//! Calibration state, workflow commands, and transaction-sized history.
use super::*;
use serde::{Deserialize, Serialize};
use std::io::Read;
include!(concat!(env!("OUT_DIR"), "/calibrants.rs"));
#[cfg(feature = "dioptrin")]
#[path = "calibration_fit.rs"]
mod native;
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
    shape: [usize; 2],
    value: Value,
}

#[derive(Clone, PartialEq, Serialize, Deserialize)]
pub(super) struct Group {
    pub ring: usize,
    pub points: Vec<[f64; 2]>,
}
#[derive(Clone, PartialEq, Serialize, Deserialize)]
pub(super) struct Reference {
    pub name: String,
    pub spacings: Vec<f64>,
    pub content: String,
}
impl Reference {
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
            content: content.into(),
        })
    }
    fn named(name: &str) -> Result<Self, String> {
        let (_, content) = CALIBRANTS
            .iter()
            .find(|(n, _)| *n == name)
            .ok_or("Choose an available calibrant.")?;
        Self::parse(name, content)
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
}
impl Default for Calibration {
    fn default() -> Self {
        Self {
            reference: Reference::named("LaB6").expect("bundled LaB6"),
            custom: None,
            picks: vec![],
            start: [0.2, 0.0, 0.0, 0.0, 0.0, 0.0, 0.3344e-10],
            free: [true, true, true, true, true, true, false],
            confirmed: false,
            dirty: false,
            rms: None,
            source: "none".into(),
            saved: false,
            reference_wavelength: 0.3344e-10,
        }
    }
}
impl Calibration {
    pub fn free_count(&self) -> usize {
        self.free.iter().filter(|&&v| v).count()
    }
    pub fn choose(&self, name: &str) -> Result<Reference, String> {
        if let Some(custom) = &self.custom
            && custom.name == name
        {
            return Ok(custom.clone());
        }
        Reference::named(name)
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
            self.reorient_view(&s.transformations)?;
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
        let before = self.calibration_snapshot();
        let outcome = self.edit_calibration(action, args, defer);
        match outcome {
            Err(error) => Err(error),
            Ok(mut extra) => {
                self.control.check()?;
                if extra["noPeakFound"] == true {
                    // A missed click does not edit calibration or its history.
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
                }
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
                self.calibration.reference_wavelength = self.calibration.start[6];
                self.calibration.dirty = self.settings.calibrated;
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
                        "numberOfRings" => next.number_of_rings = integer(v, key, 1, 100)?,
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
                    "{} (custom)",
                    file.file_stem().unwrap_or_default().to_string_lossy()
                );
                let reference = Reference::parse(&name, &content)?;
                self.calibration.custom = Some(reference.clone());
                self.calibration.reference = reference;
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
                if document["calibrant"]["dSpacingsAngstrom"]
                    != json!(self.calibration.reference.spacings)
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
            _ => unreachable!(),
        }
        Ok(json!({}))
    }
    pub(super) fn calibration_payload(&self) -> Value {
        let c = &self.calibration;
        let g = &self.settings.geometry;
        let angles = c.reference.angles(c.reference_wavelength);
        let mut names: Vec<_> = CALIBRANTS.iter().map(|(n, _)| n.to_string()).collect();
        if let Some(custom) = &c.custom {
            names.push(custom.name.clone());
        }
        let lines:Vec<_>=angles.iter().map(|&(ring,t)|json!({"ring":ring,"x":match self.settings.unit.as_str(){"q_A^-1"=>4.0*std::f64::consts::PI*(t/2.0).sin()/(g.wavelength*1e10),"d_A"=>g.wavelength*1e10/(2.0*(t/2.0).sin()),_=>t.to_degrees()}})).collect();
        json!({"setupConfirmed":c.confirmed,"workflow":self.workflow,"parameters":c.parameters(g),"freeParameterCount":c.free_count(),"polarization":self.settings.polarization,"fitWavelength":c.free[6],
            "geometrySource":c.source,"canUndo":!self.calibration_history.undo.is_empty()||self.integration_history.can_undo(),"canRedo":!self.calibration_history.redo.is_empty()||self.integration_history.can_redo(),"fitTilts":c.free[3],
            "calibrant":c.reference.name,"calibrants":names,"distance":c.start[0]*1000.0,"wavelength":c.start[6]*1e10,"fitDirty":c.dirty,"rmsDegrees":c.rms,"saved":c.saved,"picks":c.picks,
            "rings":angles.iter().map(|&(ring,t)|json!({"ring":ring,"twoTheta":t.to_degrees()})).collect::<Vec<_>>(),"referenceLines":lines,
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
