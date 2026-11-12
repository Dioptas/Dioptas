//! SCXRD session orchestration. PhaseSmith owns all numerical kernels; source
//! counts, angular metadata, stage invalidation and review decisions belong here.
use super::*;
use phasesmith_single_crystal::{solution, spots};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use spots::{fft, geometry_refinement as fitting, reciprocal};
use std::{
    collections::BTreeMap,
    fs::File,
    io::{Read, Seek, SeekFrom, Write},
};
#[path = "single_crystal_files.rs"]
mod files;
#[path = "single_crystal_processing.rs"]
mod processing;
#[path = "single_crystal_scaling.rs"]
mod scaling;
const ENGINE: &str = "PhaseSmith 0.8.1 / e47507f4";
fn adapter_identity() -> &'static str {
    static ID: std::sync::OnceLock<String> = std::sync::OnceLock::new();
    ID.get_or_init(|| {
        let mut hash = Sha256::new();
        let sources: [&[u8]; 8] = [
            include_bytes!("single_crystal.rs"),
            include_bytes!("single_crystal_processing.rs"),
            include_bytes!("single_crystal_scaling.rs"),
            include_bytes!("single_crystal_files.rs"),
            include_bytes!("image.rs"),
            include_bytes!("geometry.rs"),
            include_bytes!("transform.rs"),
            include_bytes!("../Cargo.lock"),
        ];
        for source in sources {
            hash.update(source);
        }
        format!("{:x}", hash.finalize())
    })
}
const TITLES: [&str; 7] = [
    "Background",
    "Find peaks",
    "Find cell",
    "Refine geometry",
    "Integrate",
    "Scaling and symmetry",
    "Structure search",
];
const MAX_FRAMES: usize = 10000;
const MAX_PIXELS: usize = 20_000_000;
const SCRATCH_BYTES: usize = 16 * 1024 * 1024 * 1024;
type V3 = [f64; 3];
type M3 = [V3; 3];
#[derive(Clone, Serialize, Deserialize, PartialEq)]
#[serde(default, deny_unknown_fields)]
pub(super) struct Config {
    pub omega_start: f64,
    pub omega_step: f64,
    pub exposure: f64,
    pub axis: V3,
    pub background: bool,
    pub smoothness: f64,
    pub threshold: f64,
    pub min_pixels: usize,
    pub link_radius: f64,
    pub tolerance: f64,
    pub min_cell: f64,
    pub max_cell: f64,
    pub group: u16,
    pub elements: String,
    pub adp: String,
    pub search_seconds: f64,
    pub aperture_radius: usize,
    pub omega_radius: f64,
    pub saturation: f64,
    pub metric: Option<[f64; 6]>,
    pub scan_scaling: bool,
    pub polarization: f64,
    pub confirmed: bool,
    pub gain: f64,
    pub read_noise: f64,
    pub refine_geometry: bool,
}
impl Default for Config {
    fn default() -> Self {
        Self {
            omega_start: 0.,
            omega_step: 0.1,
            exposure: 0.1,
            axis: [1., 0., 0.],
            background: true,
            smoothness: 1e4,
            threshold: 5.,
            min_pixels: 3,
            link_radius: 3.,
            tolerance: 0.015,
            min_cell: 2.,
            max_cell: 30.,
            group: 1,
            elements: String::new(),
            adp: "isotropic".into(),
            search_seconds: 60.,
            aperture_radius: 6,
            omega_radius: 1.5,
            saturation: 4294967294.,
            metric: None,
            scan_scaling: false,
            polarization: 0.99,
            confirmed: false,
            gain: 1.,
            read_noise: 0.,
            refine_geometry: false,
        }
    }
}
impl Config {
    fn check(&self) -> Result<(), String> {
        if [
            self.omega_start,
            self.omega_step,
            self.exposure,
            self.smoothness,
            self.threshold,
            self.link_radius,
            self.tolerance,
            self.min_cell,
            self.max_cell,
            self.search_seconds,
            self.polarization,
            self.gain,
            self.read_noise,
            self.saturation,
            self.omega_radius,
        ]
        .iter()
        .any(|x| !x.is_finite())
            || self.axis.iter().any(|x| !x.is_finite())
            || fft::dot(self.axis, self.axis) < 1e-12
        {
            return Err("Acquisition and processing values must be finite; the spindle axis must be nonzero.".into());
        }
        if let Some(p) = self.metric {
            let c = phasesmith_crystallography::UnitCell {
                a_angstrom: p[0],
                b_angstrom: p[1],
                c_angstrom: p[2],
                alpha_deg: p[3],
                beta_deg: p[4],
                gamma_deg: p[5],
            };
            c.geometry().map_err(err)?;
        }
        if self.omega_step <= 0.
            || self.omega_step > 10.
            || self.exposure <= 0.
            || self.exposure > self.omega_step * 1.001
            || self.omega_start.abs() > 10000.
        {
            return Err("Use a positive rotation step up to 10° and an exposure width no larger than the step. Reverse scans must be reordered with matching angles.".into());
        }
        if !(2..=64).contains(&self.aperture_radius)
            || !(0.01..=10.).contains(&self.omega_radius)
            || self.saturation <= 0.
            || self.saturation > f64::from(u32::MAX)
            || self.gain <= 0.
            || self.gain > 1e6
            || self.read_noise < 0.
            || self.read_noise > 1e6
            || !(1e-6..=1e9).contains(&self.smoothness)
            || !(1.0..=100.).contains(&self.threshold)
            || !(1..=1000).contains(&self.min_pixels)
            || !(0.1..=30.).contains(&self.link_radius)
            || !(0.001..=0.1).contains(&self.tolerance)
            || !(1.5..=100.).contains(&self.min_cell)
            || self.max_cell < self.min_cell
            || self.max_cell > 100.
            || !(1..=230).contains(&self.group)
            || !["isotropic", "anisotropic"].contains(&self.adp.as_str())
            || !(1.0..=600.).contains(&self.search_seconds)
            || !(0.0..=1.).contains(&self.polarization)
        {
            return Err(
                "Processing settings exceed the supported bounds. Check the entered settings."
                    .into(),
            );
        }
        Ok(())
    }
    fn first_changed(&self, n: &Self) -> usize {
        if self.omega_start != n.omega_start
            || self.omega_step != n.omega_step
            || self.exposure != n.exposure
            || self.saturation != n.saturation
            || self.background != n.background
            || self.smoothness != n.smoothness
        {
            0
        } else if self.gain != n.gain
            || self.read_noise != n.read_noise
            || self.threshold != n.threshold
            || self.min_pixels != n.min_pixels
            || self.link_radius != n.link_radius
        {
            1
        } else if self.axis != n.axis
            || self.min_cell != n.min_cell
            || self.max_cell != n.max_cell
            || self.tolerance != n.tolerance
        {
            2
        } else if self.metric != n.metric || self.refine_geometry != n.refine_geometry {
            3
        } else if self.aperture_radius != n.aperture_radius
            || self.omega_radius != n.omega_radius
            || self.polarization != n.polarization
        {
            4
        } else if self.group != n.group || self.scan_scaling != n.scan_scaling {
            5
        } else if self.elements != n.elements
            || self.adp != n.adp
            || self.search_seconds != n.search_seconds
        {
            6
        } else {
            7
        }
    }
}
#[derive(Clone, Serialize, Deserialize)]
struct Source {
    path: PathBuf,
    frame: usize,
    digest: String,
}
#[derive(Clone, Serialize, Deserialize)]
struct Stage {
    status: String,
    detail: String,
    seconds: f64,
}
impl Default for Stage {
    fn default() -> Self {
        Self {
            status: "pending".into(),
            detail: String::new(),
            seconds: 0.,
        }
    }
}
#[derive(Clone, Serialize, Deserialize)]
struct Peak {
    frame: usize,
    xy: [f64; 2],
    intensity: f64,
    flags: u32,
    bounds: [usize; 4],
    track: usize,
}
#[derive(Clone, Serialize, Deserialize)]
struct Track {
    observed: V3,
    first: usize,
    last: usize,
    bounds: [usize; 4],
    flags: u32,
    excluded: bool,
}
#[derive(Clone, Serialize, Deserialize)]
struct Cell {
    direct: M3,
    parameters: [f64; 6],
    indexed: usize,
    total: usize,
    rms: f64,
    validation: usize,
}
#[derive(Clone, Serialize, Deserialize)]
struct Reflection {
    hkl: [i64; 3],
    omega: f64,
    intensity: f64,
    sigma: f64,
    flags: u32,
    track: usize,
    correction: f64,
}
#[derive(Clone, Copy, Serialize, Deserialize)]
struct Geometry {
    origin: V3,
    fast: V3,
    slow: V3,
    beam: V3,
    axis: V3,
    wavelength: f64,
}
impl Geometry {
    fn native(self) -> reciprocal::Geometry {
        reciprocal::Geometry {
            origin: self.origin,
            fast: self.fast,
            slow: self.slow,
            beam: self.beam,
            axis: self.axis,
            wavelength: self.wavelength,
        }
    }
}
impl From<reciprocal::Geometry> for Geometry {
    fn from(g: reciprocal::Geometry) -> Self {
        Self {
            origin: g.origin,
            fast: g.fast,
            slow: g.slow,
            beam: g.beam,
            axis: g.axis,
            wavelength: g.wavelength,
        }
    }
}
#[derive(Clone, Default)]
pub(super) struct Crystal {
    config: Config,
    sources: Vec<Source>,
    protected_sources: Vec<PathBuf>,
    shape: [usize; 2],
    frame: usize,
    stages: [Stage; 7],
    geometry: Option<Geometry>,
    initial_geometry: Option<Geometry>,
    poni: Option<crate::geometry::Geometry>,
    calibration_source: Option<PathBuf>,
    background: Option<Arc<tempfile::NamedTempFile>>,
    peaks: Vec<Peak>,
    tracks: Vec<Track>,
    cells: Vec<Cell>,
    selected: Option<usize>,
    basis: Option<M3>,
    geometry_report: Value,
    reflections: Vec<Reflection>,
    unscaled_reflections: Vec<Reflection>,
    scaling: Value,
    structure: Value,
    cif: Option<String>,
    mask: Vec<[usize; 4]>,
    excluded_frames: Vec<usize>,
    error: Option<String>,
    notice: Option<String>,
    preview: Option<Raster>,
    preview_values: Option<Arc<Vec<f64>>>,
    preview_kind: String,
    saved_exports: Vec<PathBuf>,
    history_label: String,
    revision: u64,
    track_offset: usize,
    reflection_offset: usize,
}
impl Crystal {
    pub(super) fn has_sources(&self) -> bool {
        !self.sources.is_empty()
    }
    fn invalidate(&mut self, from: usize) {
        for s in &mut self.stages[from..] {
            *s = Stage::default();
        }
        if from == 0 {
            self.background = None;
        }
        if from <= 1 {
            self.peaks.clear();
            self.tracks.clear();
            self.track_offset = 0;
        }
        if from <= 2 {
            self.cells.clear();
            self.selected = None;
        }
        if from <= 3 {
            self.basis = None;
            self.geometry = self.initial_geometry;
            self.geometry_report = Value::Null;
        }
        if from <= 4 {
            self.reflections.clear();
            self.unscaled_reflections.clear();
            self.reflection_offset = 0;
        } else if from == 5 {
            self.reflections = self.unscaled_reflections.clone();
        }
        if from <= 5 {
            self.scaling = Value::Null;
        }
        if from <= 6 {
            self.structure = Value::Null;
            self.cif = None;
        }
        self.saved_exports.clear();
        self.error = None;
        self.notice = None;
        self.revision += 1;
    }
    fn sources_check(&self) -> Result<(), String> {
        if self.sources.is_empty() {
            return Err("Load a rotation series first.".into());
        }
        Ok(())
    }
    fn read(&self, index: usize) -> Result<Vec<f64>, String> {
        let s = self
            .sources
            .get(index)
            .ok_or("Frame is outside the loaded series.")?;
        let i = Image::open(&s.path, &json!({"frame":s.frame}))?;
        if i.shape != self.shape {
            return Err("Detector dimensions changed. Reload the scan.".into());
        }
        let data = i.values.as_ref();
        if digest(data) != s.digest {
            return Err(format!(
                "Decoded source counts changed: {} frame {}. Reload the scan before processing.",
                s.path.display(),
                s.frame + 1
            ));
        }
        Ok(data.clone())
    }
    fn mask_for(&self, data: &[f64], frame: usize) -> Vec<bool> {
        let [h, w] = self.shape;
        let mut mask: Vec<_> = data
            .iter()
            .map(|&v| !v.is_finite() || v < 0. || v >= self.config.saturation)
            .collect();
        if self.excluded_frames.contains(&frame) {
            mask.fill(true);
        }
        for &[x0, y0, x1, y1] in &self.mask {
            for y in y0..y1.min(h) {
                mask[y * w + x0..y * w + x1.min(w)].fill(true);
            }
        }
        mask
    }
    fn baseline(&self, frame: usize) -> Result<Option<Vec<f64>>, String> {
        let Some(file) = &self.background else {
            return Ok(None);
        };
        let n = self.shape[0] * self.shape[1];
        let mut data = vec![0u8; n * 8];
        let mut f = file.reopen().map_err(|e| e.to_string())?;
        f.seek(SeekFrom::Start((frame * n * 8) as u64))
            .map_err(|e| e.to_string())?;
        f.read_exact(&mut data).map_err(|e| e.to_string())?;
        Ok(Some(
            data.as_chunks::<8>()
                .0
                .iter()
                .map(|b| f64::from_le_bytes(*b))
                .collect(),
        ))
    }
    fn preview(&mut self, kind: &str) -> Result<(), String> {
        if !["raw", "background", "corrected"].contains(&kind) {
            return Err("Unknown single-crystal image kind.".into());
        }
        let mut raw = self.read(self.frame)?;
        let mask = self.mask_for(&raw, self.frame);
        if kind != "raw" {
            let b = self
                .baseline(self.frame)?
                .ok_or("Run Background first, or select Original counts.")?;
            for (r, b) in raw.iter_mut().zip(b) {
                *r = if kind == "background" { b } else { *r - b };
            }
        }
        for (v, m) in raw.iter_mut().zip(mask) {
            if m {
                *v = f64::NAN;
            }
        }
        self.preview = Some(Raster::image(&raw, self.shape));
        self.preview_values = Some(Arc::new(raw));
        self.preview_kind = kind.into();
        Ok(())
    }
    fn peak_frames(&self) -> Vec<usize> {
        let mut counts = vec![0; self.sources.len()];
        for peak in &self.peaks {
            counts[peak.frame] += 1;
        }
        counts
    }
    fn predicted_markers(&self) -> Vec<Value> {
        let Some(geometry) = self.geometry else {
            return vec![];
        };
        let basis = self.basis.or_else(|| {
            self.selected
                .and_then(|i| self.cells.get(i))
                .and_then(|c| fft::inverse_transpose(c.direct).ok())
        });
        let Some(basis) = basis else { return vec![] };
        let Ok(direct) = fft::inverse_transpose(basis) else {
            return vec![];
        };
        let peaks: Vec<_> = self
            .peaks
            .iter()
            .filter(|p| p.frame == self.frame)
            .take(10000)
            .collect();
        let mut g = geometry.native();
        g.axis = self.config.axis;
        let samples: Vec<V3> = peaks
            .iter()
            .map(|p| [p.xy[0], p.xy[1], self.tracks[p.track].observed[2]])
            .collect();
        let Ok(q) = g.convert(&samples) else {
            return vec![];
        };
        let hkl: Vec<_> = q
            .into_iter()
            .map(|q| fft::indexed(q, direct, basis).0.map(|v| v as i64))
            .collect();
        let hints: Vec<_> = samples.iter().map(|p| p[2]).collect();
        let Ok(predictions) = spots::prediction::predict(g, basis, &hkl, &hints, false) else {
            return vec![];
        };
        predictions
            .iter()
            .zip(peaks)
            .filter(|(p, _)| p.flags == 0)
            .map(|(p, source)| json!({"x":p.values[0],"y":p.values[1],"track":source.track}))
            .collect()
    }
    fn reply(&self) -> Reply {
        let shown:Vec<_>=self.peaks.iter().filter(|p|p.frame==self.frame).take(10000).map(|p|json!({"x":p.xy[0],"y":p.xy[1],"track":p.track,"flags":p.flags,"excluded":self.tracks.get(p.track).is_some_and(|t|t.excluded)})).collect();
        let tracks:Vec<_>=self.tracks.iter().enumerate().skip(self.track_offset).take(200).map(|(id,t)|json!({"id":id,"observed":t.observed,"first":t.first,"last":t.last,"flags":t.flags,"excluded":t.excluded})).collect();
        let state = json!({"engine":ENGINE,"adapter":adapter_identity(),"exported":!self.saved_exports.is_empty(),"revision":self.revision,"config":self.config,"frames":self.sources.len(),"frame":self.frame,"firstSource":self.sources.first().map(|s|s.path.to_string_lossy()),"lastSource":self.sources.last().map(|s|s.path.to_string_lossy()),"filename":self.sources.get(self.frame).map(|s|s.path.file_name().unwrap_or_default().to_string_lossy()),"shape":self.shape,"stages":self.stages,"geometry":self.geometry,"geometryReport":self.geometry_report,"peaks":shown,"predictions":self.predicted_markers(),"peakCount":self.peaks.len(),"peakFrames":self.peak_frames(),"tracks":tracks,"trackOffset":self.track_offset,"reflectionOffset":self.reflection_offset,"trackCount":self.tracks.len(),"cells":self.cells,"selected":self.selected,"reflections":self.reflections.iter().skip(self.reflection_offset).take(200).collect::<Vec<_>>(),"reflectionCount":self.reflections.len(),"usableReflections":self.reflections.iter().filter(|r|r.flags==0).count(),"scaling":self.scaling,"structure":self.structure,"mask":self.mask,"excludedFrames":self.excluded_frames,"error":self.error,"notice":self.notice,"previewKind":if self.preview_kind.is_empty(){"raw"}else{&self.preview_kind},"image":self.preview.as_ref().map(|r|&r.metadata)});
        Reply {
            result: json!({"ok":true,"scxrd":state}),
            buffers: self.preview.iter().map(|r| r.buffer.clone()).collect(),
        }
    }
}
fn digest(data: &[f64]) -> String {
    let mut hash = Sha256::new();
    for v in data {
        hash.update(v.to_le_bytes());
    }
    format!("{:x}", hash.finalize())
}
fn err(e: impl std::fmt::Display) -> String {
    e.to_string()
}
impl Session {
    pub(super) fn scxrd_command(&mut self, action: &str, args: &Value) -> Result<Reply, String> {
        let history = (matches!(action, "scxrd_settings" | "scxrd_edit")
            || (action == "scxrd_file"
                && matches!(
                    args["operation"].as_str(),
                    Some("calibration" | "use_calibration" | "preset")
                )))
            && !matches!(args["operation"].as_str(), Some("undo" | "redo"));
        if action == "scxrd_run" {
            self.scxrd_redo.clear();
        }
        let before = history.then(|| {
            let mut snapshot = self.scxrd.clone();
            snapshot.history_label = if args["operation"] == "preset" {
                "recipe settings".into()
            } else if action == "scxrd_settings" {
                "processing settings".into()
            } else {
                args["operation"]
                    .as_str()
                    .unwrap_or(action)
                    .replace('_', " ")
            };
            snapshot
        });
        if action == "scxrd_edit" && args["operation"] == "undo" {
            if let Some(mut previous) = self.scxrd_undo.last().cloned() {
                let label = previous.history_label.clone();
                previous.frame = self
                    .scxrd
                    .frame
                    .min(previous.sources.len().saturating_sub(1));
                if !previous.sources.is_empty() {
                    previous.preview("raw")?;
                }
                self.scxrd_undo.pop();
                let mut current = std::mem::replace(&mut self.scxrd, previous);
                current.history_label = label.clone();
                self.scxrd_redo.push(current);
                self.scxrd.notice = Some(format!(
                    "Undid: {label}. Applied results restored; up to three edits retained."
                ));
            }
        } else if action == "scxrd_edit" && args["operation"] == "redo" {
            if let Some(mut next) = self.scxrd_redo.last().cloned() {
                let label = next.history_label.clone();
                next.frame = self.scxrd.frame.min(next.sources.len().saturating_sub(1));
                if !next.sources.is_empty() {
                    next.preview("raw")?;
                }
                self.scxrd_redo.pop();
                let mut current = std::mem::replace(&mut self.scxrd, next);
                current.history_label = label.clone();
                self.scxrd_undo.push(current);
                self.scxrd.notice = Some(format!("Redid: {label}. Applied results restored."));
            }
        } else {
            let result = self.scxrd_dispatch(action, args);
            if let Err(e) = result {
                if let Some(before) = before {
                    self.scxrd = before;
                }
                return Err(e);
            }
            let mut reply = result.unwrap();
            if let Some(before) = before
                && before.revision != self.scxrd.revision
            {
                self.scxrd_undo.push(before);
                self.scxrd_redo.clear();
                while self.scxrd_undo.len() > 3 {
                    self.scxrd_undo.remove(0);
                }
            }
            if action == "scxrd_load" || (action == "scxrd_file" && args["operation"] == "open") {
                self.scxrd_undo.clear();
                self.scxrd_redo.clear();
            }
            if reply.result["scxrd"].is_object() {
                reply.result["scxrd"]["undoLabel"] =
                    json!(self.scxrd_undo.last().map(|c| &c.history_label));
                reply.result["scxrd"]["redoLabel"] =
                    json!(self.scxrd_redo.last().map(|c| &c.history_label));
                reply.result["scxrd"]["canUndo"] = json!(!self.scxrd_undo.is_empty());
                reply.result["scxrd"]["canRedo"] = json!(!self.scxrd_redo.is_empty());
            }
            return Ok(reply);
        }
        let mut reply = self.scxrd.reply();
        reply.result["scxrd"]["undoLabel"] =
            json!(self.scxrd_undo.last().map(|c| &c.history_label));
        reply.result["scxrd"]["redoLabel"] =
            json!(self.scxrd_redo.last().map(|c| &c.history_label));
        reply.result["scxrd"]["canUndo"] = json!(!self.scxrd_undo.is_empty());
        reply.result["scxrd"]["canRedo"] = json!(!self.scxrd_redo.is_empty());
        Ok(reply)
    }
    fn scxrd_dispatch(&mut self, action: &str, args: &Value) -> Result<Reply, String> {
        let allowed: &[&str] = match action {
            "scxrd_snapshot" => &[],
            "scxrd_load" => &["path", "paths"],
            "scxrd_settings" => &["config"],
            "scxrd_frame" => &["frame", "kind"],
            "scxrd_run" => &["stage", "automatic"],
            "scxrd_edit" => &["operation", "index", "bounds"],
            "scxrd_table" => &["kind", "offset"],
            "scxrd_levels" => &["mode", "percentile", "filter_gaps"],
            "scxrd_pixel" => &["x", "y"],
            "scxrd_file" => &["operation", "path", "directory", "suggested_name"],
            _ => return Err("Unknown SCXRD command.".into()),
        };
        check_keys(args, allowed)?;
        match action {
            "scxrd_table" => {
                let offset = args["offset"]
                    .as_u64()
                    .ok_or("Table offset must be an integer.")?
                    as usize;
                match args["kind"].as_str() {
                    Some("tracks") => {
                        if offset >= self.scxrd.tracks.len() && offset != 0 {
                            return Err("Track page is out of range.".into());
                        }
                        self.scxrd.track_offset = offset;
                    }
                    Some("reflections") => {
                        if offset >= self.scxrd.reflections.len() && offset != 0 {
                            return Err("Reflection page is out of range.".into());
                        }
                        self.scxrd.reflection_offset = offset;
                    }
                    _ => return Err("Unknown SCXRD table.".into()),
                }
            }
            "scxrd_levels" => {
                let mode = args["mode"].as_str().unwrap_or("percentile");
                let percentile = args["percentile"].as_f64().unwrap_or(2.5);
                if !["percentile", "minmax", "mean3std"].contains(&mode)
                    || !percentile.is_finite()
                    || !(0.01..=25.).contains(&percentile)
                {
                    return Err("Invalid auto-level settings.".into());
                }
                let values = self
                    .scxrd
                    .preview_values
                    .as_ref()
                    .ok_or("Load a frame first.")?;
                self.scxrd.preview = Some(Raster::correction(
                    values,
                    self.scxrd.shape,
                    mode,
                    percentile,
                ));
            }
            "scxrd_pixel" => {
                let x = args["x"].as_u64().ok_or("Invalid pixel x.")? as usize;
                let y = args["y"].as_u64().ok_or("Invalid pixel y.")? as usize;
                let c = &self.scxrd;
                if x >= c.shape[1] || y >= c.shape[0] {
                    return Err("Pixel outside SCXRD detector.".into());
                }
                let value = c
                    .preview_values
                    .as_ref()
                    .and_then(|v| v.get(y * c.shape[1] + x))
                    .filter(|v| v.is_finite());
                let two_theta = c.geometry.map(|g| {
                    let ray: V3 = std::array::from_fn(|i| {
                        g.origin[i] + x as f64 * g.fast[i] + y as f64 * g.slow[i]
                    });
                    let cosine = fft::dot(ray, g.beam)
                        / (fft::dot(ray, ray) * fft::dot(g.beam, g.beam)).sqrt();
                    cosine.clamp(-1., 1.).acos().to_degrees()
                });
                return Ok(Reply::metadata(
                    json!({"ok":true,"scxrdPixel":{"x":x,"y":y,"value":value,"twoTheta":two_theta}}),
                ));
            }
            "scxrd_snapshot" => {}
            "scxrd_load" => {
                self.scxrd_load(args)?;
            }
            "scxrd_settings" => {
                let c: Config = serde_json::from_value(args["config"].clone()).map_err(err)?;
                c.check()?;
                if c != self.scxrd.config {
                    let at = self.scxrd.config.first_changed(&c);
                    self.scxrd.config = c;
                    self.scxrd.invalidate(at);
                    if at == 0 && !self.scxrd.sources.is_empty() {
                        self.scxrd.preview("raw")?;
                    }
                }
            }
            "scxrd_frame" => {
                let frame = args["frame"]
                    .as_u64()
                    .ok_or("Frame must be a nonnegative integer.")?
                    as usize;
                if frame >= self.scxrd.sources.len() {
                    return Err("Frame is outside the loaded series.".into());
                }
                let previous = self.scxrd.frame;
                self.scxrd.frame = frame;
                if let Err(e) = self.scxrd.preview(args["kind"].as_str().unwrap_or("raw")) {
                    self.scxrd.frame = previous;
                    return Err(e);
                }
            }
            "scxrd_run" => {
                let target = args["stage"]
                    .as_u64()
                    .filter(|v| *v < 7)
                    .ok_or("Unknown processing stage.")? as usize;
                let automatic = args["automatic"].as_bool().unwrap_or(false);
                self.scxrd.sources_check()?;
                self.scxrd.config.check()?;
                if !self.scxrd.config.confirmed {
                    return Err("Confirm acquisition angles, spindle axis and count gain in Frames before processing.".into());
                }
                self.scxrd.error = None;
                self.scxrd.notice = None;
                for (stage, title) in TITLES.iter().enumerate().take(target + 1) {
                    if self.scxrd.stages[stage].status == "complete" {
                        continue;
                    }
                    self.control.publish(
                        json!({"running":true,"label":format!("{title} · stage {} of {}",stage+1,target+1)}),
                    );
                    let start = std::time::Instant::now();
                    let result = self.scxrd.process(stage, &self.control, automatic);
                    match result {
                        Ok(detail) => {
                            self.scxrd.stages[stage] = Stage {
                                status: "complete".into(),
                                detail,
                                seconds: start.elapsed().as_secs_f64(),
                            };
                            self.scxrd.revision += 1;
                        }
                        Err(e) => {
                            let cancelled = self.control.check().is_err();
                            let e = if cancelled {
                                format!(
                                    "Stopped during {title}. Completed stages and current settings are retained; rerun this stage to continue."
                                )
                            } else {
                                e
                            };
                            self.scxrd.stages[stage] = Stage {
                                status: if cancelled { "paused" } else { "attention" }.into(),
                                detail: e.clone(),
                                seconds: start.elapsed().as_secs_f64(),
                            };
                            self.scxrd.error = Some(e);
                            self.scxrd.revision += 1;
                            break;
                        }
                    }
                }
                let kind = if self.scxrd.background.is_none() {
                    "raw".to_owned()
                } else {
                    self.scxrd.preview_kind.clone()
                };
                if let Err(e) = self.scxrd.preview(&kind) {
                    self.scxrd.error = Some(e);
                }
            }
            "scxrd_edit" => self.scxrd.edit(args)?,
            "scxrd_file" => return self.scxrd_file(args),
            _ => return Err(format!("Unknown SCXRD command: {action}")),
        }
        Ok(self.scxrd.reply())
    }
    fn scxrd_load(&mut self, args: &Value) -> Result<(), String> {
        let mut paths: Vec<String> = if args["paths"].is_array() {
            serde_json::from_value(args["paths"].clone()).map_err(err)?
        } else {
            vec![
                args["path"]
                    .as_str()
                    .ok_or("Choose detector frames or a multi-frame file.")?
                    .into(),
            ]
        };
        if paths.is_empty() || paths.len() > MAX_FRAMES {
            return Err("Select between 1 and 10,000 source files.".into());
        }
        if paths.len() > 1 {
            let numbered: Option<Vec<_>> =
                paths.iter().map(|p| frame_number(Path::new(p))).collect();
            if let Some(mut numbers) = numbered
                && numbers.iter().all(|p| p.0 == numbers[0].0)
            {
                numbers.sort_by_key(|p| p.1);
                if numbers
                    .windows(2)
                    .any(|p| p[0].1.checked_add(1) != Some(p[1].1))
                {
                    return Err("Missing or duplicate numbered frames. Select a contiguous sequence; acquisition angles must not be compressed across gaps.".into());
                }
                paths.sort_by_key(|p| frame_number(Path::new(p)).unwrap().1);
            }
        }
        let mut next = Crystal {
            config: self.scxrd.config.clone(),
            initial_geometry: self.scxrd.initial_geometry,
            geometry: self.scxrd.initial_geometry,
            poni: self.scxrd.poni.clone(),
            calibration_source: self.scxrd.calibration_source.clone(),
            ..Default::default()
        };
        // Numbered series are ordered numerically with continuity checked above.
        // Other names retain caller order and require acquisition confirmation.
        for path in paths {
            self.control.check()?;
            let path = PathBuf::from(path);
            let mut image = Image::open(&path, &json!({}))?;
            let frames = image.frames;
            for (source, _) in image.source_fingerprint()? {
                if !next.protected_sources.contains(&source) {
                    next.protected_sources.push(source);
                }
            }
            if frames == 0 || frames + next.sources.len() > MAX_FRAMES {
                return Err("The selected scan exceeds 10,000 frames.".into());
            }
            if next.shape == [0, 0] {
                next.shape = image.shape;
                next.config.saturation = match image.source_dtype.to_lowercase().as_str() {
                    "u8" => 255.,
                    "u16" => 65535.,
                    "i16" => 32767.,
                    "i32" => f64::from(i32::MAX),
                    _ => f64::from(u32::MAX - 1),
                };
            }
            if next.shape != image.shape || image.values.len() > MAX_PIXELS {
                return Err(
                    "All frames must share dimensions and contain at most 20 million pixels."
                        .into(),
                );
            }
            for frame in 0..frames {
                self.control.check()?;
                if frame > 0 {
                    image.read(frame)?;
                }
                if image.shape != next.shape {
                    return Err("Frame dimensions vary within the scan.".into());
                }
                next.sources.push(Source {
                    path: path.clone(),
                    frame,
                    digest: digest(&image.values),
                });
                self.control.publish(json!({"running":true,"current":next.sources.len(),"total":null,"label":"Verifying original frames"}));
            }
        }
        if next.sources.len() < 3 {
            return Err("A rotation scan needs at least three frames.".into());
        }
        if let Some(poni) = next.poni.clone() {
            if next.set_poni(&poni).is_err() {
                next.geometry = None;
                next.initial_geometry = None;
                next.poni = None;
                next.calibration_source = None;
            }
        } else if next.shape != self.scxrd.shape {
            next.geometry = None;
            next.initial_geometry = None;
        }
        if let Some(path) = &next.calibration_source {
            next.protected_sources.push(path.clone());
        }
        next.config.confirmed = false;
        next.notice = Some(
            "Confirm the file order, omega start, step and spindle axis before processing.".into(),
        );
        next.preview("raw")?;
        self.scxrd = next;
        Ok(())
    }
}

fn frame_number(path: &Path) -> Option<(String, u64)> {
    let stem = path.file_stem()?.to_str()?;
    let start = stem
        .rfind(|c: char| !c.is_ascii_digit())
        .map_or(0, |i| i + 1);
    let count = stem.get(start..)?.parse().ok()?;
    Some((
        format!(
            "{}/{}.{}",
            path.parent()?.display(),
            &stem[..start],
            path.extension()?.to_str()?
        ),
        count,
    ))
}
#[cfg(test)]
#[path = "single_crystal_tests.rs"]
mod tests;
