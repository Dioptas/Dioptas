use crate::control::Control;
use crate::{
    display::{self, Raster},
    geometry::Geometry,
    image::Image,
    protocol::{Reply, Request},
};
use serde_json::{Value, json};
use std::path::{Path, PathBuf};
use std::sync::Arc;
#[path = "batch_export.rs"]
mod batch_export;
#[path = "batch_workflow.rs"]
mod batch_workflow;
#[path = "calibration.rs"]
mod calibration;
#[path = "checkpoint.rs"]
mod checkpoint;
#[path = "combination.rs"]
mod combination;
#[path = "file_workflow.rs"]
mod file_workflow;
#[path = "geometric_mask.rs"]
mod geometric_mask;
#[path = "image_batch.rs"]
mod image_batch;
#[path = "image_change.rs"]
mod image_change;
#[path = "image_transform.rs"]
mod image_transform;
#[path = "integration_history.rs"]
mod integration_history;
#[path = "linked.rs"]
mod linked;
#[path = "map_workflow.rs"]
mod map_workflow;
#[path = "mask_io.rs"]
mod mask_io;
#[path = "phase_workflow.rs"]
mod phase_workflow;
#[path = "project.rs"]
mod project;
use crate::mask_plugins::{Plugins, State as PluginState};
use calibration::{Calibration, History, Workflow};
#[cfg(feature = "dioptrin")]
use std::time::Instant;

type DetectorMaskSource = (
    PathBuf,
    Option<crate::image::FileIdentity>,
    String,
    Value,
    bool,
);
struct DetectorMaskCache {
    detector: Arc<dioptrin::detector::Detector>,
    shape: [usize; 2],
    source: Option<DetectorMaskSource>,
    probe_frame: Option<usize>,
    mask: Arc<Vec<u8>>,
}
#[cfg(feature = "dioptrin")]
type NativeGeometryCache = (Geometry, [usize; 2], dioptrin::geometry::Geometry);
#[derive(Clone, PartialEq, serde::Serialize, serde::Deserialize)]
struct Settings {
    transformations: Vec<crate::transform::Transform>,
    original_pixels: Option<[f64; 2]>,
    #[serde(with = "crate::history_transfer::optional_arc")]
    original_detector: Option<Arc<dioptrin::detector::Detector>>,
    geometry: Geometry,
    calibrated: bool,
    calibration_name: Option<String>,
    calibration_path: Option<String>,
    unit: String,
    bins: usize,
    cake_bins: usize,
    use_mask: bool,
    transparent_mask: bool,
    polarization: f64,
    errors: bool,
    automatic_binning: bool,
    supersampling: usize,
    #[serde(default)]
    pyfai_splitting: bool,
    solid_angle: bool,
    azimuth: Option<[f64; 2]>,
    cake_azimuth: Option<[f64; 2]>,
    trim_zeros: bool,
    spread: bool,
    csc: bool,
    #[serde(default)]
    auto_layout: bool,
    roi: Option<[usize; 4]>,
    auto_save: bool,
    formats: Vec<String>,
}
impl Default for Settings {
    fn default() -> Self {
        Self {
            transformations: vec![],
            original_pixels: None,
            original_detector: None,
            geometry: Geometry::default(),
            calibrated: false,
            calibration_name: None,
            calibration_path: None,
            unit: "2th_deg".into(),
            bins: 1000,
            cake_bins: 360,
            use_mask: true,
            transparent_mask: false,
            polarization: 0.99,
            errors: false,
            automatic_binning: false,
            supersampling: 1,
            pyfai_splitting: false,
            solid_angle: true,
            azimuth: None,
            cake_azimuth: None,
            trim_zeros: true,
            spread: false,
            csc: false,
            auto_layout: false,
            roi: None,
            auto_save: false,
            formats: vec![".xy".into()],
        }
    }
}

/// A session is constructed and used exclusively on the processing worker.
pub struct Session {
    root: PathBuf,
    settings: Settings,
    project: project::Project,
    combination: combination::State,
    #[cfg(feature = "dioptrin")]
    combination_plans: Option<combination::Plans>,
    image: Option<Image>,
    image_raster: Option<Raster>,
    processed_raster: Option<Raster>,
    processed_values: Option<Arc<Vec<f64>>>,
    scientific_generation: u64,
    processing: crate::processing::Processing,
    patterns: crate::pattern::Patterns,
    phases: crate::phases::Phases,
    batch: Option<crate::series::Series>,
    scan: Option<crate::scan::Scan>,
    image_batch_mode: String,
    actions: crate::custom_actions::Actions,
    files: file_workflow::Files,
    integration_history: integration_history::IntegrationHistory,
    inspection: Option<linked::Inspection>,
    inspection_contour: std::cell::RefCell<Option<linked::ContourCache>>,
    inspection_field: std::cell::RefCell<Option<linked::FieldCache>>,
    mask: Arc<Vec<u8>>,
    mask_filename: Option<String>,
    mask_mode: bool,
    effective_mask: Arc<Vec<u8>>,
    #[cfg(feature = "dioptrin")]
    native_geometry_cache: std::cell::RefCell<Option<NativeGeometryCache>>,
    detector_mask: std::cell::RefCell<Option<DetectorMaskCache>>,
    plugins: Plugins,
    image_generation: u64,
    mask_raster: Option<Raster>,
    undo: Vec<MaskSnapshot>,
    redo: Vec<MaskSnapshot>,
    revision: u64,
    elapsed_ms: Option<f64>,
    pattern: Option<Arc<Value>>,
    cake: Option<Raster>,
    cake_values: Option<Arc<Vec<f64>>>,
    calibration: Calibration,
    workflow: Workflow,
    calibration_history: History,
    control: Arc<Control>,
    #[cfg(feature = "dioptrin")]
    ring_cache: std::cell::RefCell<Option<calibration::RingCache>>,
    #[cfg(feature = "dioptrin")]
    massif_cache: std::cell::RefCell<Option<calibration::MassifCache>>,
    #[cfg(feature = "dioptrin")]
    sigma: Option<Vec<f64>>,
    #[cfg(feature = "dioptrin")]
    engine: crate::integration::Engine,
    #[cfg(feature = "dioptrin")]
    prepared: Option<crate::integration::Prepared>,
}
#[derive(Clone, PartialEq, serde::Serialize, serde::Deserialize)]
struct MaskSnapshot {
    mode: bool,
    #[serde(with = "crate::history_transfer::arc")]
    user: Arc<Vec<u8>>,
    plugins: Vec<PluginState>,
}
impl Session {
    fn example_path(&self) -> PathBuf {
        let packaged = self.root.join("examples/CeO2_Pilatus1M.tif");
        if packaged.is_file() {
            packaged
        } else {
            // Explicit source-root clients and reference tests retain their fixture layout.
            self.root.join("dioptas/tests/data/CeO2_Pilatus1M.tif")
        }
    }
    pub fn new(root: PathBuf) -> Self {
        Self {
            root,
            settings: Settings::default(),
            project: project::Project::default(),
            combination: Default::default(),
            #[cfg(feature = "dioptrin")]
            combination_plans: None,
            image: None,
            image_raster: None,
            processed_raster: None,
            processed_values: None,
            scientific_generation: 0,
            processing: Default::default(),
            patterns: Default::default(),
            phases: Default::default(),
            batch: None,
            scan: None,
            image_batch_mode: "integrate".into(),
            actions: Default::default(),
            files: Default::default(),
            integration_history: Default::default(),
            inspection: None,
            inspection_contour: Default::default(),
            inspection_field: Default::default(),
            mask: Arc::new(vec![]),
            mask_filename: None,
            mask_mode: true,
            effective_mask: Arc::new(vec![]),
            detector_mask: Default::default(),
            #[cfg(feature = "dioptrin")]
            native_geometry_cache: Default::default(),
            plugins: Plugins::default(),
            image_generation: 0,
            mask_raster: None,
            undo: vec![],
            redo: vec![],
            revision: 0,
            elapsed_ms: None,
            pattern: None,
            cake: None,
            cake_values: None,
            calibration: Calibration::default(),
            workflow: Workflow::default(),
            calibration_history: History::default(),
            control: Arc::new(Control::default()),
            #[cfg(feature = "dioptrin")]
            ring_cache: Default::default(),
            #[cfg(feature = "dioptrin")]
            massif_cache: Default::default(),
            #[cfg(feature = "dioptrin")]
            sigma: None,
            #[cfg(feature = "dioptrin")]
            engine: Default::default(),
            #[cfg(feature = "dioptrin")]
            prepared: None,
        }
    }
    pub fn invoke(&mut self, request: &Request) -> Reply {
        self.invoke_controlled(request, Arc::new(Control::default()))
    }
    pub fn invoke_controlled(&mut self, request: &Request, control: Arc<Control>) -> Reply {
        self.control = control;
        if let Err(error) = request.validate() {
            return Reply::error(error);
        }
        let mut payload = std::borrow::Cow::Borrowed(&request.payload);
        if let Some(products) = request.payload.get("requested_products") {
            if !products.is_object()
                || !products["cake"].is_boolean()
                || products.as_object().unwrap().iter().any(|(key, value)| {
                    !["cake", "rings"].contains(&key.as_str()) || !value.is_boolean()
                })
            {
                return Reply::error(
                    "Requested products must contain a cake boolean and optional rings boolean.",
                );
            }
            self.control
                .request_cake(products["cake"].as_bool().unwrap());
            self.control
                .request_calibration_rings(products["rings"].as_bool().unwrap_or(true));
            payload
                .to_mut()
                .as_object_mut()
                .unwrap()
                .remove("requested_products");
        } else {
            self.control.request_cake(true);
            self.control.request_calibration_rings(true);
        }
        let project_checkpoint = self.project.clone();
        let shared_before = (
            self.phases.clone(),
            self.patterns.overlays.clone(),
            self.patterns.separation,
        );
        let checkpoint = (!matches!(
            request.action.as_str(),
            "state"
                | "pixel"
                | "image_levels"
                | "__host__"
                | "integration_diagnostics"
                | "integration_phase_guides"
        ))
        .then(|| self.checkpoint());
        let integration_before =
            integration_history::is_edit(&request.action).then(|| self.integration_snapshot());
        if matches!(
            request.action.as_str(),
            "undo_calibration" | "redo_calibration"
        ) {
            self.integration_history.break_group();
        }
        let before = matches!(
            request.action.as_str(),
            "manual_geometry" | "open_calibration"
        )
        .then(|| self.calibration_snapshot());
        let calibration_head = self.calibration_history.undo.last().cloned();
        let dispatched = self
            .dispatch(&request.action, &payload)
            .and_then(|mut reply| {
                self.update_combination_reply(&mut reply, &request.action, &payload)?;
                Ok(reply)
            });
        match dispatched {
            Ok(mut reply) => {
                if request.action != "development_restore"
                    && (self.phases != shared_before.0
                        || self.patterns.overlays != shared_before.1
                        || self.patterns.separation != shared_before.2)
                {
                    self.forget_other_shared_history();
                }
                if let Some(before) = before {
                    let after = self.calibration_snapshot();
                    self.calibration_history
                        .record(&request.action, before, after, self.revision);
                    if reply.result["state"].is_object() {
                        for (key, value) in self.calibration_payload().as_object().unwrap() {
                            reply.result["state"]["calibration"][key] = value.clone();
                        }
                    }
                }
                if let Some(before) = integration_before {
                    let after = self.integration_snapshot();
                    let cal_seq = self.calibration_history.undo.last().map_or(0, |e| e.3);
                    let changed = self.integration_history.record(
                        before,
                        after,
                        &request.action,
                        &request.payload,
                        self.revision,
                        cal_seq,
                    );
                    if changed {
                        self.calibration_history.redo.clear();
                    }
                } else if !matches!(
                    request.action.as_str(),
                    "undo_calibration"
                        | "redo_calibration"
                        | "development_restore"
                        | "configuration"
                ) && self.calibration_history.undo.last().is_some_and(|entry| {
                    calibration_head
                        .as_ref()
                        .is_none_or(|previous| !Arc::ptr_eq(entry, previous))
                }) {
                    self.integration_history.clear_redo();
                }
                if reply.result["state"].is_object() {
                    reply.result["state"]["calibration"]["canUndo"] = json!(
                        !self.calibration_history.undo.is_empty()
                            || self.integration_history.can_undo()
                    );
                    reply.result["state"]["calibration"]["canRedo"] = json!(
                        !self.calibration_history.redo.is_empty()
                            || self.integration_history.can_redo()
                    );
                }
                if let Some(path) = request.payload.get("path").filter(|p| p.is_string()) {
                    reply.result["activity"] = json!({"path":path});
                } else if let Some(paths) = request.payload["paths"].as_array() {
                    reply.result["activity"] = json!({"paths":paths.iter().take(8).collect::<Vec<_>>(),"count":paths.len()});
                }
                reply
            }
            Err(error) => {
                self.project = project_checkpoint;
                if let Some(checkpoint) = checkpoint {
                    self.restore_checkpoint(checkpoint);
                }
                if error.starts_with("Operation cancelled")
                    && (request.action.starts_with("batch_")
                        || request.action.starts_with("map_")
                        || request.action == "open_project"
                        || request.action == "save_project"
                        || request.action == "configuration"
                        || request.action == "mask_edit"
                        || request.action == "image_transform"
                        || request.action == "integration_batch"
                        || (request.action == "open_image"
                            && request.payload["paths"]
                                .as_array()
                                .is_some_and(|p| p.len() > 1)))
                {
                    Reply::metadata(json!({"ok":true,"cancelled":true}))
                } else {
                    let mut reply = Reply::error(error);
                    reply.result["errorContext"] = json!({
                        "action": request.action,
                        "path": request.payload.get("path"),
                        "dataset": request.payload.get("dataset"),
                        "frame": request.payload.get("frame")
                    });
                    reply
                }
            }
        }
    }
    fn dispatch(&mut self, action: &str, args: &Value) -> Result<Reply, String> {
        if let Some(reply) = self.combination_command(action, args)? {
            return Ok(reply);
        }
        if let Some(reply) = self.project_command(action, args)? {
            return Ok(reply);
        }
        if action == "mask_file" {
            return self.mask_file(args);
        }
        if action == "custom_command" {
            let image = self.image.as_ref();
            let context = json!({"image_path":image.map(|i|&i.path),"image_name":image.and_then(|i|i.path.file_name()).map(|n|n.to_string_lossy()),"image_directory":image.and_then(|i|i.path.parent()),"frame_index":image.map(|i|i.frame),"frame_number":image.map(|i|i.frame+1),"dataset":image.and_then(|i|i.options.get("dataset")),"calibration_path":self.settings.calibration_path,"project_path":self.project.path,"wavelength_angstrom":if self.settings.calibrated{Some(self.settings.geometry.wavelength*1e10)}else{None}});
            return Ok(Reply::metadata(self.actions.invoke(args, context)?));
        }
        if action == "open_image" && args.get("paths").is_some() {
            let paths = batch_workflow::source_paths(args)?;
            if paths.len() > 1 {
                return self.image_batch(paths, args);
            }
            let mut single = args.clone();
            for key in ["paths", "multiple", "batch_mode", "output_directory"] {
                single.as_object_mut().unwrap().remove(key);
            }
            single["path"] = json!(paths[0]);
            return self.dispatch("open_image", &single);
        }
        if let Some(reply) = self.integration_history_command(action)? {
            return Ok(reply);
        }
        if let Some(reply) = self.file_command(action, args)? {
            return Ok(reply);
        }
        if let Some(reply) = self.phase_command(action, args)? {
            return Ok(reply);
        }
        if let Some(reply) = self.batch_command(action, args)? {
            return Ok(reply);
        }
        if let Some(reply) = self.map_command(action, args)? {
            return Ok(reply);
        }
        if calibration::is_command(action) {
            let defer = args
                .get("defer_integration")
                .map(|v| boolean(v, "Defer integration"))
                .transpose()?
                .unwrap_or(false);
            return self.calibration_command(action, args, defer);
        }
        let defer = args
            .get("defer_integration")
            .map(|v| boolean(v, "Defer integration"))
            .transpose()?
            .unwrap_or(false);
        match action {
            "__host__" => {
                return Ok(Reply::metadata(
                    json!({"ok": true, "protocol": 2, "transport": "stdio", "runtime": "rust", "pid": std::process::id(), "qtApplication": false,
                "engine": if cfg!(feature="dioptrin") { Some("dioptrin") } else { None },
                "capabilities": ["requested-products", "image-input", "hdf5-image-sources", "frame-navigation", "binary-rasters", "display-statistics", "mask-brush", "mask-history", "mask-plugins", "calibration-peaks", "calibration-history", "uniform-poni", "manual-pyfai-geometry", "xy-export", "project-format-2", "configuration-management", "image-transformations", "geometric-masks", "mask-lacosmic","detector-definitions","detector-orientations","distortion-splines","fit2d-geometry"]}),
                ));
            }
            "state" => return Ok(self.snapshot(true)),
            "display_products" => {
                check_keys(args, &["cake", "rings"])?;
                let cake = boolean(&args["cake"], "Request cake")?;
                self.control.request_cake(cake);
                if let Some(rings) = args.get("rings") {
                    self.control
                        .request_calibration_rings(boolean(rings, "Request calibration rings")?);
                }
                if cake {
                    self.ensure_cake()?;
                }
                return Ok(self.snapshot(false));
            }
            "example" => {
                let path = self.example_path();
                let candidate = Image::open(&path, &json!({}))?;
                let mut settings = Settings::default();
                settings.geometry.pixel1 = 172e-6;
                settings.geometry.pixel2 = 172e-6;
                settings.geometry.wavelength = 0.406626e-10;
                self.settings = settings;
                self.calibration = Calibration::default();
                self.calibration.reference = self.calibration.choose("CeO2")?;
                self.calibration.start[6] = self.settings.geometry.wavelength;
                self.calibration.reference_wavelength = self.settings.geometry.wavelength;
                self.calibration.confirmed = true;
                self.workflow = Workflow::default();
                self.plugins = Plugins::default();
                self.processing = Default::default();
                self.patterns = Default::default();
                self.calibration_history = History::default();
                self.undo.clear();
                self.redo.clear();
                self.image = None;
                self.publish_image(candidate)?;
                self.refresh_masks(&Control::default())?;
            }
            "select_image_source" => {
                check_keys(args, &["dataset", "defer_integration"])?;
                let dataset = args["dataset"].as_str().ok_or("Choose an image source.")?;
                let image = self.image.as_ref().ok_or("Open an image first.")?;
                if !(dataset.is_empty() && image.automatic_source)
                    && !image.sources.iter().any(|s| s.dataset == dataset)
                {
                    return Err("This image source is not available in the current file.".into());
                }
                let frame = image.frame;
                let mut options = image.options.clone();
                options["path"] = json!(image.path);
                options.as_object_mut().unwrap().remove("dataset");
                if !dataset.is_empty() {
                    options["dataset"] = json!(dataset);
                }
                self.control.check()?;
                let candidate = Image::prepare(&image.path, &options)?;
                // Qt retains the frame position, clamping to a shorter series.
                options["frame"] = json!(frame.min(candidate.frames - 1));
                options["defer_integration"] = json!(defer);
                return self.dispatch("open_image", &options);
            }
            "open_image" => {
                if let Some(reply) = self.open_image_model(args, defer)? {
                    return Ok(reply);
                }
            }
            "reset_calibration" => {
                check_keys(args, &[])?;
                self.reset_detector_state()?;
                self.calculate(defer)?;
                self.revision += 1;
                let mut reply = self.snapshot(true);
                reply.result["calibrationReset"] = json!(true);
                return Ok(reply);
            }
            "next_image" => {
                check_keys(
                    args,
                    &["direction", "step", "files_only", "defer_integration"],
                )?;
                let files_only = args
                    .get("files_only")
                    .map(|v| boolean(v, "Files only"))
                    .transpose()?
                    .unwrap_or(false);
                let direction = args
                    .get("direction")
                    .map(|v| v.as_i64().ok_or("direction must be an integer."))
                    .transpose()?
                    .unwrap_or(1);
                let step = args
                    .get("step")
                    .map(|v| {
                        v.as_u64()
                            .filter(|v| *v > 0 && *v <= 100_000)
                            .ok_or("step must be a positive integer.")
                    })
                    .transpose()?
                    .unwrap_or(1);
                let image = self.image.as_ref().ok_or("Open an image first.")?;
                let index = (image.frame as i64)
                    .checked_add(
                        direction
                            .checked_mul(step as i64)
                            .ok_or("Frame step exceeds range.")?,
                    )
                    .ok_or("Frame step exceeds range.")?;
                if files_only || index < 0 || index >= image.frames as i64 {
                    let Some(target) = file_workflow::neighbor(
                        &image.path,
                        &self.files.image_mode,
                        direction.signum() * step as i64,
                    )?
                    else {
                        // At the current end of acquisition, leave all session state
                        // intact. A later click must still look for newly arrived files.
                        return Ok(Reply::metadata(json!({"ok":true,"imageUnavailable":true})));
                    };
                    let mut options = image.options.clone();
                    options["path"] = json!(target);
                    if files_only {
                        // Qt's file iterator opens the first frame of the new file.
                        // Never carry a frame index into a shorter destination stack.
                        options["frame"] = json!(0);
                    }
                    options["defer_integration"] = json!(defer);
                    return self.dispatch("open_image", &options);
                }
                if image.frame_source_shape(index as usize)? != image.source_shape {
                    let mut options = image.options.clone();
                    options["path"] = json!(image.path);
                    options["frame"] = json!(index);
                    options["defer_integration"] = json!(defer);
                    return self.dispatch("open_image", &options);
                }
                #[cfg(feature = "dioptrin")]
                let options = self.integration_options();
                #[cfg(feature = "dioptrin")]
                let load_mask = if self.settings.calibrated && !defer && !self.processing.active() {
                    image
                        .combined_source(index as usize)?
                        .map(|source| self.integration_mask(source.shape))
                        .unwrap_or_default()
                } else {
                    Vec::new()
                };
                let image = self.image.as_mut().unwrap();
                let previous_shape = image.shape;
                #[cfg(feature = "dioptrin")]
                {
                    self.prepared = self.engine.load_frame(
                        image,
                        index as usize,
                        (self.settings.calibrated && !defer && !self.processing.active())
                            .then_some((&self.settings.geometry, load_mask.as_slice(), &options)),
                        &self.control,
                    )?;
                }
                #[cfg(not(feature = "dioptrin"))]
                image.read(index as usize)?;
                self.image_generation += 1;
                // A new intensity frame does not change the physical click.
                let shape = image.shape;
                if image.shape != previous_shape {
                    self.mask = Arc::new(vec![0; image.values.len()]);
                    self.undo.clear();
                    self.redo.clear();
                    self.mask_raster = None;
                }
                self.image_raster = Some(Raster::image(&image.values, image.shape));
                self.retain_inspection(shape);
                self.calibration.picks.clear();
                self.calibration.rms = None;
                self.calibration_history = History::default();
                self.calculate(defer)?;
            }
            "open_calibration" => {
                check_keys(args, &["path", "defer_integration"])?;
                let file = path(args)?;
                let mut candidate = Geometry::load(file)?;
                if let Some(image) = &self.image {
                    candidate.sync_shape(image.shape)?;
                }
                self.settings.geometry = candidate;
                self.settings.original_pixels = None;
                self.settings.calibration_path = Some(file.to_string_lossy().into_owned());
                self.settings.calibrated = true;
                self.settings.calibration_name = Some(
                    file.file_name()
                        .unwrap_or_default()
                        .to_string_lossy()
                        .into_owned(),
                );
                self.rebase_detector_reset()?;
                self.loaded_geometry("loaded");
                self.calculate(defer)?;
            }
            "manual_geometry" => {
                check_keys(args, &["convention", "values", "defer_integration"])?;
                let (mut geometry, polarization) = match args["convention"].as_str() {
                    Some("pyfai") => Geometry::manual(&args["values"])?,
                    Some("fit2d") => Geometry::manual_fit2d(&args["values"])?,
                    _ => return Err("Choose pyFAI or Fit2D geometry convention.".into()),
                };
                geometry.detector = self.settings.geometry.detector.clone();
                geometry.frame_pixels = self.settings.geometry.frame_pixels;
                geometry.detector_file = self.settings.geometry.detector_file.clone();
                geometry.distortion_file = self.settings.geometry.distortion_file.clone();
                geometry.set_pixels(
                    [geometry.pixel1, geometry.pixel2],
                    self.image.as_ref().map(|i| i.shape),
                )?;
                if let Some(image) = &self.image {
                    geometry.validate_shape(image.shape)?;
                }
                self.settings.geometry = geometry;
                self.settings.original_pixels = None;
                self.settings.polarization = polarization;
                self.settings.calibrated = true;
                self.settings.calibration_name = Some("manual".into());
                self.settings.calibration_path = None;
                self.rebase_detector_reset()?;
                self.loaded_geometry("manual");
                self.calculate(defer)?;
            }
            "save_calibration" => {
                check_keys(args, &["path"])?;
                if !self.settings.calibrated {
                    return Err("Load or enter a calibration first.".into());
                }
                if self.calibration.dirty {
                    return Err(
                        "Fit the current ring selections before saving the calibration.".into(),
                    );
                }
                let file = path(args)?;
                self.settings.geometry.save_to(file)?;
                self.calibration.saved = true;
                self.settings.calibration_path = Some(file.to_string_lossy().into_owned());
                self.settings.calibration_name = Some(
                    file.file_name()
                        .unwrap_or_default()
                        .to_string_lossy()
                        .into_owned(),
                );
                let mut reply = self.snapshot(false);
                reply.result["savedPath"] = json!(file);
                return Ok(reply);
            }
            "settings" | "integration_settings" => {
                let mut candidate = self.settings.clone();
                for (key, value) in args.as_object().expect("validated arguments") {
                    match key.as_str() {
                        "unit" => {
                            candidate.unit = match value.as_str() {
                                Some(v @ ("2th_deg" | "q_A^-1" | "d_A")) => v.into(),
                                _ => return Err("Unsupported integration unit.".into()),
                            }
                        }
                        "bins" => {
                            candidate.automatic_binning = value.is_null();
                            if !value.is_null() {
                                candidate.bins = integer(value, "Radial bins", 1, 100000)?;
                            }
                        }
                        "cake_bins" => candidate.cake_bins = integer(value, "Cake bins", 1, 10000)?,
                        "use_mask" => candidate.use_mask = boolean(value, key)?,
                        "transparent_mask" => candidate.transparent_mask = boolean(value, key)?,
                        "polarization" => {
                            candidate.polarization = finite(value, "Polarization", -1.0, 1.0)?
                        }
                        "poisson_errors" => candidate.errors = boolean(value, key)?,
                        "solid_angle" => candidate.solid_angle = boolean(value, key)?,
                        "supersampling" => candidate.supersampling = integer(value, key, 1, 20)?,
                        "method" => { /* Applied after the sampling factor, independently of JSON key order. */
                        }
                        "trim_zeros" => candidate.trim_zeros = boolean(value, key)?,
                        "auto_save" => candidate.auto_save = boolean(value, key)?,
                        "azimuthal_std" => candidate.spread = boolean(value, key)?,
                        "sparse_layout" => {
                            candidate.csc = match value.as_str() {
                                Some("csc" | "auto") => true,
                                Some("csr") => false,
                                _ => {
                                    return Err(
                                        "Choose automatic, CSC or CSR sparse layout.".into()
                                    );
                                }
                            };
                            candidate.auto_layout = value.as_str() == Some("auto");
                        }
                        "azimuth_range" => candidate.azimuth = optional_azimuth(value)?,
                        "cake_azimuth_range" => candidate.cake_azimuth = optional_azimuth(value)?,
                        "formats" => {
                            let entries = value
                                .as_array()
                                .filter(|a| !a.is_empty())
                                .ok_or("Choose at least one pattern format.")?;
                            candidate.formats = entries
                                .iter()
                                .map(|v| {
                                    v.as_str()
                                        .filter(|s| {
                                            [".xy", ".xye", ".chi", ".dat", ".fxye"].contains(s)
                                        })
                                        .map(str::to_string)
                                        .ok_or("Choose a supported pattern format.")
                                })
                                .collect::<Result<_, _>>()?;
                        }
                        "defer_integration" => {
                            boolean(value, key)?;
                        }
                        _ => {
                            return Err(format!(
                                "Option {key} is not supported by the native backend yet; the previous settings were retained."
                            ));
                        }
                    }
                }
                if let Some(method) = args.get("method") {
                    match method.as_str() {
                        Some("polygon") => {
                            candidate.pyfai_splitting = false;
                            candidate.supersampling = 1;
                        }
                        Some("subpixel") => {
                            candidate.pyfai_splitting = false;
                            candidate.supersampling = candidate.supersampling.max(2);
                        }
                        Some("pyfai_full" | "pyfai") => {
                            candidate.pyfai_splitting = true;
                            candidate.supersampling = 1;
                        }
                        _ => {
                            return Err(
                                "Choose polygon, pyFAI-compatible or subpixel integration.".into(),
                            );
                        }
                    }
                } else if args.get("supersampling").is_some() {
                    candidate.pyfai_splitting = false;
                }
                if candidate
                    .bins
                    .checked_mul(candidate.cake_bins)
                    .is_none_or(|n| n > 4_000_000)
                {
                    return Err("Cake output exceeds four million bins.".into());
                }
                if !candidate.errors
                    && candidate
                        .formats
                        .iter()
                        .any(|v| v == ".xye" || v == ".fxye")
                {
                    return Err("Enable Calculate Poisson errors for XYE/FXYE output.".into());
                }
                if candidate.unit != self.settings.unit {
                    self.patterns
                        .convert_unit(&candidate.unit, candidate.geometry.wavelength)?;
                }
                self.settings = candidate;
                self.calculate(defer)?;
            }
            "integrate" => {
                if self.image.is_none() || !self.settings.calibrated {
                    return Err("Open an image and load or enter its calibration first.".into());
                }
                if !cfg!(feature = "dioptrin") {
                    return Err("This native processor has no numerical engine. Build with --features dioptrin; Python will not be started.".into());
                }
                self.calculate(false)?;
            }
            "integration_roi" => {
                check_keys(args, &["limits", "defer_integration"])?;
                self.require_image()?;
                self.settings.roi = if args["limits"].is_null() {
                    None
                } else {
                    let a = args["limits"]
                        .as_array()
                        .filter(|a| a.len() == 4)
                        .ok_or("ROI needs row minimum/maximum and column minimum/maximum.")?;
                    let shape = self.image.as_ref().unwrap().shape;
                    let mut r = [0; 4];
                    for i in 0..4 {
                        r[i] = integer(&a[i], "ROI bound", 0, shape[if i < 2 { 0 } else { 1 }])?;
                    }
                    if r[0] >= r[1] || r[2] >= r[3] {
                        return Err("ROI minimum must be below maximum.".into());
                    }
                    Some(r)
                };
                self.calculate(defer)?;
            }
            "integration_image_background"
            | "integration_flat_field"
            | "integration_transfer"
            | "integration_correction" => {
                self.require_image()?;
                let shape = self.image.as_ref().unwrap().source_shape;
                match action {
                    "integration_image_background" => {
                        check_keys(
                            args,
                            &[
                                "path",
                                "reset",
                                "scale",
                                "offset",
                                "poisson",
                                "defer_integration",
                            ],
                        )?;
                        self.processing.background(args, shape)?;
                    }
                    "integration_transfer" => {
                        check_keys(
                            args,
                            &["source", "path", "enabled", "reset", "defer_integration"],
                        )?;
                        self.processing.transfer(args, shape)?;
                    }
                    "integration_flat_field" => {
                        check_keys(args, &["path", "enabled", "reset", "defer_integration"])?;
                        self.processing.flat_field(args, shape)?;
                    }
                    _ => {
                        check_keys(
                            args,
                            &[
                                "kind",
                                "enabled",
                                "parameters",
                                "material",
                                "container",
                                "defer_integration",
                            ],
                        )?;
                        self.processing.correction(args, self.settings.calibrated)?;
                    }
                }
                self.calculate(defer)?;
            }
            "integration_background" => {
                check_keys(
                    args,
                    &["enabled", "smoothing", "iterations", "order", "range"],
                )?;
                self.patterns.configure_background(args)?;
                self.rebuild_pattern()?;
            }
            "validation_position" => return self.validation_position(args),
            "integration_clear_background" => {
                self.patterns.clear_background();
                self.rebuild_pattern()?;
            }
            "integration_overlay" => {
                self.patterns.edit_overlay(args, self.pattern.as_deref())?;
                self.rebuild_pattern()?;
                self.revision += 1;
                let mut reply = self.snapshot(false);
                reply.buffers.clear();
                for key in [
                    "image", "rawImage", "mask", "cake", "rings", "linked", "batch", "map",
                ] {
                    reply.result.as_object_mut().unwrap().remove(key);
                }
                reply.result["patternOnly"] = json!(true);
                return Ok(reply);
            }
            "integration_open_pattern" => {
                check_keys(args, &["path", "direction", "step", "directory"])?;
                let mut file = if let Some(direction) = args.get("direction") {
                    let direction = direction
                        .as_i64()
                        .filter(|d| *d == 1 || *d == -1)
                        .ok_or("Pattern direction must be -1 or 1.")?;
                    let step = args
                        .get("step")
                        .map(|v| integer(v, "Pattern file step", 1, 100000))
                        .transpose()?
                        .unwrap_or(1);
                    if !self.patterns.imported {
                        return Err("Load a pattern file before browsing files.".into());
                    }
                    file_workflow::neighbor(
                        Path::new(
                            self.patterns
                                .path
                                .as_ref()
                                .ok_or("Load a pattern file first.")?,
                        ),
                        &self.patterns.file_mode,
                        direction * step as i64,
                    )?
                    .ok_or(if self.patterns.file_mode == "time" {
                        "No further file in time order."
                    } else {
                        "No further numbered file."
                    })?
                } else {
                    path(args)?.to_path_buf()
                };
                if !file.is_absolute()
                    && let Some(dir) = args.get("directory").and_then(Value::as_str)
                {
                    file = Path::new(dir).join(file);
                }
                let curve = crate::pattern::Curve::read(&file)?;
                let name = file
                    .file_stem()
                    .unwrap_or_default()
                    .to_string_lossy()
                    .into_owned();
                self.patterns.ingest(
                    curve,
                    &self.settings.unit,
                    &name,
                    Some(file.to_string_lossy().into_owned()),
                    true,
                );
                self.rebuild_pattern()?;
            }
            "integration_pattern_navigation" => {
                check_keys(args, &["mode"])?;
                self.patterns.file_mode = args["mode"]
                    .as_str()
                    .filter(|s| ["number", "time"].contains(s))
                    .ok_or("Choose number or time file order.")?
                    .into();
            }
            "image_levels" => {
                check_keys(args, &["source", "mode", "percentile", "filter_gaps"])?;
                let mode = args
                    .get("mode")
                    .and_then(Value::as_str)
                    .unwrap_or("percentile");
                if !["percentile", "minmax", "mean3std"].contains(&mode) {
                    return Err("Unknown Auto levels mode.".into());
                }
                let percentile = args
                    .get("percentile")
                    .map(|v| finite(v, "Percentile", 0.0, 49.999999))
                    .transpose()?
                    .unwrap_or(2.5);
                let filter = args
                    .get("filter_gaps")
                    .map(|v| boolean(v, "Filter gaps"))
                    .transpose()?
                    .unwrap_or(true);
                let source = args
                    .get("source")
                    .and_then(Value::as_str)
                    .unwrap_or("detector");
                let (data, shape, display) = match source {
                    "detector" | "raw_detector" => {
                        let Some(image) = self.image.as_ref() else {
                            return Ok(Reply::metadata(
                                json!({"ok":true,"display":"detector","levels":null}),
                            ));
                        };
                        (
                            if source == "raw_detector" {
                                image.values.as_slice()
                            } else {
                                self.processed_values
                                    .as_ref()
                                    .unwrap_or(&image.values)
                                    .as_slice()
                            },
                            image.shape,
                            "detector",
                        )
                    }
                    "cake" => {
                        let Some(data) = self.displayed_cake_values() else {
                            return Ok(Reply::metadata(
                                json!({"ok":true,"display":"cake","levels":null}),
                            ));
                        };
                        (
                            data.as_slice(),
                            [
                                self.settings.cake_bins,
                                if self.settings.automatic_binning {
                                    self.automatic_bins()
                                } else {
                                    self.settings.bins
                                },
                            ],
                            "cake",
                        )
                    }
                    _ => return Err("Choose detector, raw_detector or cake display.".into()),
                };
                let raster = match source {
                    "raw_detector" => self.image_raster.as_ref(),
                    "detector" => self
                        .processed_raster
                        .as_ref()
                        .or(self.image_raster.as_ref()),
                    "cake" => self.displayed_cake(),
                    _ => None,
                };
                let levels = raster
                    .and_then(|raster| raster.cached_levels(mode, percentile, filter))
                    .or_else(|| display::levels(data, shape, mode, percentile, filter));
                return Ok(Reply::metadata(
                    json!({"ok": true, "display": display, "levels": levels}),
                ));
            }
            "pixel" => {
                let image = self.image.as_ref().ok_or("Open an image first.")?;
                let x = finite(&args["x"], "x", 0.0, image.shape[1] as f64 - f64::EPSILON)?.floor()
                    as usize;
                let y = finite(&args["y"], "y", 0.0, image.shape[0] as f64 - f64::EPSILON)?.floor()
                    as usize;
                if x >= image.shape[1] || y >= image.shape[0] {
                    return Err("Pixel is outside the detector.".into());
                }
                let data = if args["source"] == "raw_detector" {
                    image.values.clone()
                } else {
                    self.scientific_values()
                };
                let pixel = json!({"x":x,"y":y,"value":data[y*image.shape[1]+x]});
                #[cfg(feature = "dioptrin")]
                let pixel = {
                    let mut pixel = pixel;
                    if self.settings.calibrated {
                        let geometry = self.native_geometry(image.shape)?;
                        let row_next = if y + 1 < image.shape[0] {
                            y + 1
                        } else {
                            y.saturating_sub(1)
                        };
                        let col_next = if x + 1 < image.shape[1] {
                            x + 1
                        } else {
                            x.saturating_sub(1)
                        };
                        let rows = [y as f64 + 0.5, y as f64 + 0.5, row_next as f64 + 0.5];
                        let cols = [x as f64 + 0.5, col_next as f64 + 0.5, x as f64 + 0.5];
                        // This native API consumes physical pixel-grid positions;
                        // unlike pyFAI.tth it does not add a half-pixel internally.
                        let (angles, _) = geometry.calc_tth_and_azimuth(&rows, &cols);
                        pixel["twoTheta"] = json!(angles[0].to_degrees());
                        pixel["twoThetaResolution"] = json!(
                            (angles[1] - angles[0])
                                .abs()
                                .max((angles[2] - angles[0]).abs())
                                .to_degrees()
                        );
                    }
                    pixel
                };
                return Ok(Reply::metadata(json!({"ok":true,"pixel":pixel})));
            }
            "image_transform" => {
                return self.image_transform(args, defer);
            }
            "mask_edit" => {
                return self.geometric_mask(args, defer);
            }
            "mask_stroke" => {
                check_keys(args, &["points", "radius", "erase", "defer_integration"])?;
                let image = self
                    .image
                    .as_ref()
                    .ok_or("Open an image before editing its mask.")?;
                let radius = finite(&args["radius"], "Brush radius", 1.0, 300.0)?;
                let erase = args
                    .get("erase")
                    .map(|v| boolean(v, "Erase"))
                    .transpose()?
                    .unwrap_or(false);
                let points = args["points"]
                    .as_array()
                    .filter(|p| !p.is_empty() && p.len() <= 10000)
                    .ok_or("A stroke requires 1–10000 points.")?;
                let mut parsed = Vec::new();
                for point in points {
                    let point = point
                        .as_array()
                        .filter(|p| p.len() == 2)
                        .ok_or("A brush point needs x and y.")?;
                    let x = finite(&point[0], "x", 0.0, image.shape[1] as f64)?;
                    let y = finite(&point[1], "y", 0.0, image.shape[0] as f64)?;
                    if x >= image.shape[1] as f64 || y >= image.shape[0] as f64 {
                        return Err("Brush point is outside the detector.".into());
                    }
                    parsed.push((x, y));
                }
                let mut mask = self.mask.as_ref().clone();
                for (x, y) in parsed {
                    for row in ((y - radius).max(0.0) as usize)
                        ..((y + radius + 1.0).ceil() as usize).min(image.shape[0])
                    {
                        for col in ((x - radius).max(0.0) as usize)
                            ..((x + radius + 1.0).ceil() as usize).min(image.shape[1])
                        {
                            if (col as f64 - x).powi(2) + (row as f64 - y).powi(2)
                                <= radius * radius
                            {
                                mask[row * image.shape[1] + col] = u8::from(!erase);
                            }
                        }
                    }
                }
                self.replace_mask_mode(mask, !erase);
                self.settings.use_mask = true;
                self.calculate(defer)?;
            }
            "clear_mask" => {
                self.require_image()?;
                self.replace_mask(vec![0; self.mask.len()]);
                self.calculate(defer)?;
            }
            "undo_mask" | "redo_mask" => {
                self.require_image()?;
                let current = self.mask_snapshot();
                let (source, destination) = if action == "undo_mask" {
                    (&mut self.undo, &mut self.redo)
                } else {
                    (&mut self.redo, &mut self.undo)
                };
                let previous = source.pop().ok_or("No mask edit to undo/redo.")?;
                destination.push(current);
                self.mask = previous.user;
                self.mask_mode = previous.mode;
                self.plugins.states = previous.plugins;
                self.calculate(defer)?;
            }
            "mask_plugin" => {
                return self.mask_plugin(args, defer);
            }
            "integration_phase_guides" => {
                return self.phase_guides();
            }
            #[cfg(feature = "dioptrin")]
            "integration_diagnostics" => {
                let mut diagnostics = self.engine.diagnostics();
                diagnostics
                    .as_object_mut()
                    .unwrap()
                    .extend(self.processing.diagnostics().as_object().unwrap().clone());
                return Ok(Reply::metadata(
                    json!({"ok":true,"integrationDiagnostics":diagnostics}),
                ));
            }
            "custom_command" if args["operation"] == "list" => {
                return Ok(Reply::metadata(
                    json!({"ok": true, "customCommands": [], "customCommandRuns": {}}),
                ));
            }
            _ => {
                return Err(format!(
                    "Command {action} is not migrated to the Rust backend yet. No Python fallback was used."
                ));
            }
        }
        self.revision += 1;
        Ok(self.snapshot(true))
    }
    fn require_image(&self) -> Result<(), String> {
        if self.image.is_some() {
            Ok(())
        } else {
            Err("Open an image first.".into())
        }
    }
    pub(super) fn open_image_model(
        &mut self,
        args: &Value,
        defer: bool,
    ) -> Result<Option<Reply>, String> {
        check_keys(
            args,
            &[
                "path",
                "frame",
                "dataset",
                "follow_external_links",
                "cbf_dialect",
                "defer_integration",
                "directory",
                "pattern_only",
                "multiple",
                "batch_mode",
                "output_directory",
                "reset_calibration",
            ],
        )?;
        let file = path(args)?;
        let file = if !file.is_absolute() {
            args["directory"]
                .as_str()
                .map_or_else(|| file.to_path_buf(), |d| Path::new(d).join(file))
        } else {
            file.to_path_buf()
        };
        let mut trace =
            crate::frame_trace::FrameTrace::new("open-image", args["frame"].as_u64().unwrap_or(0));
        let mut image = Image::prepare(&file, args)?;
        trace.mark("metadata");
        if let Some(reply) = self.image_change(&image, args)? {
            return Ok(Some(reply));
        }
        if args["reset_calibration"].as_bool() == Some(true) {
            self.reset_detector_state()?;
        }
        self.assign_image_detector(&image)?;

        image.orient(&self.settings.transformations, &self.control)?;
        self.settings.geometry.sync_shape(image.shape)?;
        #[cfg(feature = "dioptrin")]
        let prepared = {
            let options = self.integration_options();
            let load_mask = if self.settings.calibrated && !defer && !self.processing.active() {
                image
                    .combined_source(image.frame)?
                    .map(|source| self.integration_mask(source.shape))
                    .unwrap_or_default()
            } else {
                Vec::new()
            };
            self.engine.load_frame(
                &mut image,
                args.get("frame").and_then(Value::as_u64).unwrap_or(0) as usize,
                (self.settings.calibrated && !defer && !self.processing.active()).then_some((
                    &self.settings.geometry,
                    load_mask.as_slice(),
                    &options,
                )),
                &self.control,
            )?
        };
        #[cfg(not(feature = "dioptrin"))]
        image.read(image.frame)?;
        trace.mark("decode and warm-plan handoff");
        self.publish_image(image)?;
        trace.mark("display preparation");
        #[cfg(feature = "dioptrin")]
        {
            self.prepared = prepared;
        }
        self.calculate_products(
            defer,
            !args
                .get("pattern_only")
                .map_or(Ok(false), |v| boolean(v, "Pattern only"))?,
        )?;
        trace.mark("processing masks and integration");
        if args["reset_calibration"].as_bool() == Some(true) {
            self.revision += 1;
            let mut reply = self.snapshot(true);
            reply.result["calibrationReset"] = json!(true);
            return Ok(Some(reply));
        }
        Ok(None)
    }
    fn assign_image_detector(&mut self, image: &Image) -> Result<(), String> {
        if self.settings.geometry.auto_assign
            && !self.settings.calibrated
            && self.settings.transformations.is_empty()
        {
            let (description, pixels) = image.detector_hints();
            let found = dioptrin::detector::identify(image.source_shape, pixels, &description);
            let g = &mut self.settings.geometry;
            if let Some(d) = found.selected {
                d.binning(image.source_shape)?;
                [g.pixel1, g.pixel2] = d.effective_pixels(image.source_shape);
                g.detector = Some(Arc::new(d));
            }
            g.auto_assign = false;
            g.assignment = Some(found.reason);
            g.candidates = found.candidates;
        }
        Ok(())
    }
    fn publish_image(&mut self, mut image: Image) -> Result<(), String> {
        image.orient(&self.settings.transformations, &self.control)?;
        self.integration_history = Default::default();
        // Opening a reference image must not redirect an active acquisition
        // watcher. Folder selection is the explicit boundary for changing it.
        if !self.files.auto_process {
            self.files.image_directory = image
                .path
                .parent()
                .unwrap_or(Path::new("."))
                .to_string_lossy()
                .into_owned();
        }
        #[cfg(feature = "dioptrin")]
        {
            self.prepared = None;
        }
        self.image_generation += 1;
        self.retain_inspection(image.shape);
        self.processed_values = None;
        self.processed_raster = None;
        self.calibration.picks.clear();
        self.calibration.rms = None;
        self.calibration_history = History::default();
        self.image_raster = Some(Raster::image(&image.values, image.shape));
        if self
            .image
            .as_ref()
            .is_none_or(|old| old.shape != image.shape)
        {
            self.settings.roi = None;
            self.mask = Arc::new(vec![0; image.values.len()]);
            self.undo.clear();
            self.redo.clear();
        }
        // calculate_products refreshes the effective mask before publishing the
        // reply. Retain a same-shape mask for comparison instead of hashing an
        // intermediate user-only mask that would immediately be replaced.
        if self
            .image
            .as_ref()
            .is_none_or(|old| old.shape != image.shape)
        {
            self.mask_raster = None;
        }
        self.image = Some(image);
        self.pattern = None;
        self.cake = None;
        self.cake_values = None;
        self.elapsed_ms = None;
        Ok(())
    }
    fn replace_mask(&mut self, mask: Vec<u8>) {
        self.replace_mask_mode(mask, self.mask_mode);
    }
    fn replace_mask_mode(&mut self, mask: Vec<u8>, mode: bool) {
        // Bound history payloads to 128 MiB, including redo. No unbounded list
        // of full-resolution masks is retained.
        let before = self.mask_snapshot();
        self.mask = Arc::new(mask);
        self.mask_mode = mode;
        self.record_mask(before);
    }
    fn mask_snapshot(&self) -> MaskSnapshot {
        MaskSnapshot {
            mode: self.mask_mode,
            user: self.mask.clone(),
            plugins: self.plugins.states.clone(),
        }
    }
    fn record_mask(&mut self, before: MaskSnapshot) {
        if before == self.mask_snapshot() {
            return;
        }
        self.undo.push(before);
        self.redo.clear();
        while self.undo.len() > 1
            && (self.undo.len() > 128
                || self.undo.iter().map(|s| s.user.len() + 4096).sum::<usize>() > 128 * 1024 * 1024)
        {
            self.undo.remove(0);
        }
    }
    #[cfg(feature = "dioptrin")]
    fn native_geometry(&self, shape: [usize; 2]) -> Result<dioptrin::geometry::Geometry, String> {
        let mut cache = self.native_geometry_cache.borrow_mut();
        if let Some((parameters, size, g)) = cache.as_ref()
            && parameters == &self.settings.geometry
            && *size == shape
        {
            return Ok(g.clone());
        }
        let g = self.settings.geometry.native_geometry(shape)?;
        *cache = Some((self.settings.geometry.clone(), shape, g.clone()));
        Ok(g)
    }
    fn physical_mask(&self, shape: [usize; 2]) -> Result<Option<Arc<Vec<u8>>>, String> {
        self.physical_mask_for(shape, self.image.as_ref())
    }
    fn physical_mask_for(
        &self,
        shape: [usize; 2],
        image: Option<&Image>,
    ) -> Result<Option<Arc<Vec<u8>>>, String> {
        let Some(d) = &self.settings.geometry.detector else {
            return Ok(None);
        };
        let mut cache = self.detector_mask.borrow_mut();
        let source = image
            .filter(|i| i.shape == shape && d.name.starts_with("Eiger"))
            .map(|i| {
                (
                    i.path.clone(),
                    crate::image::FileIdentity::read(&i.path).ok(),
                    i.source_dtype.clone(),
                    i.options.clone(),
                    i.derived,
                )
            });
        if let Some(entry) = cache.as_ref()
            && entry.shape == shape
            && Arc::ptr_eq(d, &entry.detector)
            && entry.source == source
            && entry
                .probe_frame
                .is_none_or(|frame| image.is_some_and(|i| i.frame == frame))
        {
            return Ok(Some(entry.mask.clone()));
        }
        let mut values = d.builtin_mask(shape)?;
        let established = if source.is_some()
            && let Some(image) = image
        {
            crate::detector_mask::extend_gaps(
                &mut values,
                &image.values,
                shape,
                &image.source_dtype,
            )
        } else {
            true
        };
        let values = Arc::new(values);
        *cache = Some(DetectorMaskCache {
            detector: d.clone(),
            shape,
            source,
            probe_frame: if established {
                None
            } else {
                image.map(|i| i.frame)
            },
            mask: values.clone(),
        });
        Ok(Some(values))
    }
    fn refresh_masks(&mut self, control: &Control) -> Result<(), String> {
        if let Some(image) = &self.image {
            // Publish caches, display and effective mask together only after
            // all enabled plugins have completed successfully.
            let mut plugins = self.plugins.clone();
            self.settings.geometry.validate_shape(image.shape)?;
            let mut combined = plugins.refresh(
                &self.scientific_values(),
                image.shape,
                self.scientific_generation,
                self.settings.calibrated.then_some(&self.settings.geometry),
                &self.mask,
                control,
            )?;
            if let Some(built) = self.physical_mask(image.shape)? {
                for (v, b) in combined.iter_mut().zip(built.iter()) {
                    *v |= *b;
                }
            }
            self.plugins = plugins;
            let combined = Arc::new(combined);
            if self.mask_raster.as_ref().is_none_or(|raster| {
                raster.metadata["width"].as_u64() != Some(image.shape[1] as u64)
                    || raster.metadata["height"].as_u64() != Some(image.shape[0] as u64)
                    || raster.buffer.bytes.as_slice() != combined.as_slice()
            }) {
                self.mask_raster = Some(Raster::shared_mask(combined.clone(), image.shape));
            }
            // Equal masks share the same immutable owner as the display/count
            // cache; temporary bulk-workflow masks still use the count fallback.
            self.effective_mask = self.mask_raster.as_ref().unwrap().buffer.bytes.clone();
        }
        Ok(())
    }
    fn mask_plugin(&mut self, args: &Value, defer: bool) -> Result<Reply, String> {
        self.require_image()?;
        check_keys(
            args,
            &[
                "name",
                "enabled",
                "settings",
                "imprint",
                "defer_integration",
            ],
        )?;
        let name = args["name"].as_str().ok_or("Choose a mask plugin.")?;
        let imprint = args
            .get("imprint")
            .map(|v| boolean(v, "Imprint"))
            .transpose()?
            .unwrap_or(false);
        let mut plugins = self.plugins.clone();
        let index = plugins.edit(name, args.get("enabled"), args.get("settings"))?;
        let image = self.image.as_ref().unwrap();
        let mut user = self.mask.as_ref().clone();
        let control = self.control.clone();
        plugins.refresh(
            &self.scientific_values(),
            image.shape,
            self.scientific_generation,
            self.settings.calibrated.then_some(&self.settings.geometry),
            &user,
            &control,
        )?;
        if imprint {
            if !plugins.states[index].enabled {
                return Err("Enable the plugin before imprinting its mask.".into());
            }
            for (out, &v) in user.iter_mut().zip(plugins.mask(index).unwrap()) {
                *out |= v;
            }
            plugins.states[index].enabled = false;
        }
        control.check()?;
        let before = self.mask_snapshot();
        let old_plugins = std::mem::replace(&mut self.plugins, plugins);
        self.mask = Arc::new(user);
        let old_use = self.settings.use_mask;
        self.settings.use_mask = true;
        let previous = (
            self.pattern.take(),
            self.cake.take(),
            self.cake_values.take(),
            self.elapsed_ms,
            self.mask_raster.clone(),
            self.effective_mask.clone(),
        );
        #[cfg(feature = "dioptrin")]
        let previous_sigma = self.sigma.take();
        let outcome = self.calculate(defer).and_then(|_| control.check());
        control.finish();
        if let Err(error) = outcome {
            self.mask = before.user;
            self.plugins = old_plugins;
            self.settings.use_mask = old_use;
            (
                self.pattern,
                self.cake,
                self.cake_values,
                self.elapsed_ms,
                self.mask_raster,
                self.effective_mask,
            ) = previous;
            #[cfg(feature = "dioptrin")]
            {
                self.sigma = previous_sigma;
            }
            return Err(error);
        }
        self.record_mask(before);
        self.revision += 1;
        Ok(self.snapshot(false))
    }
    fn calculate(&mut self, defer: bool) -> Result<(), String> {
        self.calculate_products(defer, true)
    }
    pub(super) fn ensure_cake(&mut self) -> Result<(), String> {
        self.control.request_cake(true);
        self.require_image()?;
        if !self.settings.calibrated {
            return Err("Load a calibration before requesting a cake.".into());
        }
        #[cfg(feature = "dioptrin")]
        {
            if self.combination.cakes {
                if self.combination.cake.is_none() {
                    self.refresh_combination()?;
                }
                return Ok(());
            }
            if self.cake.is_none() {
                self.control.check()?;
                self.prepare_processing()?;
                self.refresh_masks(&self.control.clone())?;
                let shape = self.image.as_ref().unwrap().shape;
                let (cake, values) = self.engine.integrate_cake(
                    &self.scientific_values(),
                    shape,
                    &self.settings.geometry,
                    &self.integration_mask(shape),
                    &self.integration_options(),
                )?;
                self.control.check()?;
                self.cake = Some(cake);
                self.cake_values = Some(Arc::new(values));
            }
            Ok(())
        }
        #[cfg(not(feature = "dioptrin"))]
        Err("Cake calculation requires the native Dioptrin engine.".into())
    }
    fn calculate_products(&mut self, defer: bool, include_cake: bool) -> Result<(), String> {
        let include_cake = include_cake && self.control.cake_requested();
        self.control.check()?;
        if let Some(image) = &self.image {
            self.settings.geometry.sync_shape(image.shape)?;
        }
        self.prepare_processing()?;
        self.refresh_masks(&self.control.clone())?;
        if self.image.is_none() && self.patterns.imported && !defer {
            return self.rebuild_pattern();
        }
        self.pattern = None;
        self.cake = None;
        self.cake_values = None;
        self.elapsed_ms = None;
        #[cfg(feature = "dioptrin")]
        {
            self.sigma = None;
        }
        if defer {
            self.patterns.raw = None;
            self.patterns.extracted = None;
            return Ok(());
        }
        #[cfg(feature = "dioptrin")]
        {
            self.sigma = None;
            if let Some(image) = &self.image
                && self.settings.calibrated
            {
                let start = Instant::now();
                let mask = self.integration_mask(image.shape);
                let (pattern, sigma, cake, cake_values) = if include_cake {
                    let products = self.engine.integrate_with_variance(
                        &self.scientific_values(),
                        self.scientific_variance().as_deref().map(|v| v.as_slice()),
                        image.shape,
                        &self.settings.geometry,
                        &mask,
                        &self.integration_options(),
                        self.prepared.take(),
                    )?;
                    (
                        products.pattern,
                        products.sigma,
                        Some(products.cake),
                        Some(Arc::new(products.cake_values)),
                    )
                } else {
                    let (pattern, sigma) = self.engine.integrate_pattern_with_variance(
                        &self.scientific_values(),
                        self.scientific_variance().as_deref().map(|v| v.as_slice()),
                        image.shape,
                        &self.settings.geometry,
                        &mask,
                        &self.integration_options(),
                        self.prepared.take(),
                    )?;
                    (pattern, sigma, None, None)
                };
                self.control.check()?;
                let mut raw = crate::pattern::Curve::from_json(&pattern)?;
                raw.sigma = sigma.as_ref().map(|s| Arc::new(s.clone()));
                self.patterns.ingest(
                    raw,
                    &self.settings.unit,
                    &if image.frames > 1 {
                        format!(
                            "{}_{:05}",
                            image.path.file_stem().unwrap_or_default().to_string_lossy(),
                            image.frame
                        )
                    } else {
                        image
                            .path
                            .file_stem()
                            .unwrap_or_default()
                            .to_string_lossy()
                            .into_owned()
                    },
                    None,
                    false,
                );
                self.rebuild_pattern()?;
                self.cake = cake;
                self.cake_values = cake_values;
                self.sigma = sigma;
                self.elapsed_ms = Some(start.elapsed().as_secs_f64() * 1000.0);
                self.auto_save()?;
            }
        }
        Ok(())
    }
    fn rebuild_pattern(&mut self) -> Result<(), String> {
        let mut pattern = self.patterns.build(&self.control)?;
        if let Some(p) = &mut pattern {
            p["phaseLines"] = self.phases.lines(
                &self.patterns.unit,
                self.settings.geometry.wavelength * 1e10,
            );
        }
        self.pattern = pattern.map(Arc::new);
        Ok(())
    }
    #[cfg(feature = "dioptrin")]
    fn integration_options(&self) -> crate::integration::Options {
        crate::integration::Options {
            automatic_bins: self.settings.automatic_binning,
            bins: if self.settings.automatic_binning {
                self.automatic_bins()
            } else {
                self.settings.bins
            },
            cake_bins: self.settings.cake_bins,
            unit: self.settings.unit.clone(),
            polarization: self.settings.polarization,
            errors: self.settings.errors,
            supersampling: self.settings.supersampling,
            pyfai: self.settings.pyfai_splitting,
            solid_angle: self.settings.solid_angle,
            azimuth: self.settings.azimuth,
            cake_azimuth: self.settings.cake_azimuth,
            trim: self.settings.trim_zeros,
            spread: self.settings.spread,
            dynamic_mask: self.settings.use_mask && self.plugins.states.iter().any(|p| p.enabled),
            csc: self.settings.csc,
            auto_layout: self.settings.auto_layout,
        }
    }
    #[cfg(feature = "dioptrin")]
    fn integration_mask(&self, shape: [usize; 2]) -> Vec<u8> {
        let mut m = if self.settings.use_mask && self.effective_mask.len() == shape[0] * shape[1] {
            self.effective_mask.as_ref().clone()
        } else {
            vec![0; shape[0] * shape[1]]
        };
        if !(self.settings.use_mask && self.effective_mask.len() == shape[0] * shape[1])
            && let Ok(Some(built)) = self.physical_mask(shape)
        {
            for (v, b) in m.iter_mut().zip(built.iter()) {
                *v |= *b;
            }
        }
        if let Some([r0, r1, c0, c1]) = self.settings.roi {
            for row in 0..shape[0] {
                for col in 0..shape[1] {
                    if row < r0 || row >= r1 || col < c0 || col >= c1 {
                        m[row * shape[1] + col] = 1;
                    }
                }
            }
        }
        m
    }
    fn scientific_values(&self) -> Arc<Vec<f64>> {
        self.processed_values
            .as_ref()
            .cloned()
            .or_else(|| self.image.as_ref().map(|i| i.values.clone()))
            .unwrap_or_else(|| Arc::new(vec![]))
    }
    fn scientific_variance(&self) -> Option<Arc<Vec<f64>>> {
        self.settings
            .errors
            .then(|| {
                self.processing
                    .variance()
                    .or_else(|| self.image.as_ref().and_then(|i| i.input_variance()))
            })
            .flatten()
    }
    fn prepare_processing(&mut self) -> Result<(), String> {
        if let Some(image) = &self.image {
            let values = self.processing.values(
                image,
                self.image_generation,
                &self.settings.geometry,
                &self.control,
            )?;
            if self
                .processed_values
                .as_ref()
                .is_none_or(|old| !Arc::ptr_eq(old, &values))
            {
                self.scientific_generation += 1;
                self.processed_raster = if Arc::ptr_eq(&values, &image.values) {
                    self.image_raster.clone()
                } else {
                    Some(Raster::image(&values, image.shape))
                };
                self.processed_values = Some(values);
            }
        }
        Ok(())
    }
    fn automatic_bins(&self) -> usize {
        let Some(image) = &self.image else {
            return self.settings.bins;
        };
        self.settings.geometry.automatic_bins(image.shape)
    }
    fn snapshot(&self, include_image: bool) -> Reply {
        self.snapshot_products(include_image, true)
    }
    fn snapshot_products(&self, include_image: bool, include_rings: bool) -> Reply {
        let mut trace = crate::frame_trace::FrameTrace::new(
            "snapshot",
            self.image.as_ref().map_or(0, |i| i.frame as u64),
        );
        let s = &self.settings;
        let g = &s.geometry;
        let shape = self.image.as_ref().map(|i| i.shape);
        let engine = if cfg!(feature = "dioptrin") {
            "dioptrin"
        } else {
            "none"
        };
        let engine_label = if cfg!(feature = "dioptrin") {
            "Dioptrin · native Rust"
        } else {
            "Native Rust · no integration engine"
        };
        let name = self
            .image
            .as_ref()
            .and_then(|i| i.path.file_name())
            .map(|s| s.to_string_lossy().into_owned());
        let image_path = self
            .image
            .as_ref()
            .map(|i| i.path.to_string_lossy().into_owned());
        let mut parameters = json!({});
        for (key, value) in [
            ("dist", g.dist * 1000.0),
            ("poni1", g.poni1 * 1000.0),
            ("poni2", g.poni2 * 1000.0),
            ("rot1", g.rot1),
            ("rot2", g.rot2),
            ("rot3", g.rot3),
            ("wavelength", g.wavelength * 1e10),
        ] {
            parameters[key] = json!({"value": value, "refine": key != "wavelength"});
        }
        let image_directory = self
            .image
            .as_ref()
            .and_then(|i| i.path.parent())
            .map(|p| p.to_string_lossy().into_owned())
            .unwrap_or_default();
        let mut result = json!({"ok": true, "backend": {"runtime": "rust", "experimental": true}, "state": {
            "supportsRequestedProducts": true,
            "revision": self.revision, "hasImage": self.image.is_some(), "imageName": name, "imagePath": image_path, "shape": shape,
            "imageSources":self.image.as_ref().map(|i|&i.sources),
            "selectedImageSource":self.image.as_ref().and_then(|i|i.options.get("dataset")),
            "automaticImageSource":self.image.as_ref().is_some_and(|i|i.automatic_source),
            "imageSourceError":self.image.as_ref().and_then(|i|i.source_discovery_error.as_ref()),
            "calibrationName": s.calibration_name, "calibrated": s.calibrated, "projectName": self.project.path.as_ref().and_then(|p|p.file_name()).map(|p|p.to_string_lossy()), "unit": s.unit,
            "bins": if s.automatic_binning {Value::Null}else{json!(s.bins)}, "useMask": s.use_mask, "transparentMask": s.transparent_mask,
            "maskedPixels": self.mask_raster.as_ref().and_then(|r|r.cached_mask_count(&self.effective_mask)).unwrap_or_else(||self.effective_mask.iter().filter(|&&v| v != 0).count()), "canUndoMask": !self.undo.is_empty(), "canRedoMask": !self.redo.is_empty(),
            "maskDetails": {"mode": self.mask_mode, "filename": null, "plugins": self.plugins.details()}, "exampleAvailable": self.example_path().is_file(),
            "elapsedMs": self.elapsed_ms, "integrationDirty": self.image.is_some() && s.calibrated && self.pattern.is_none(), "configurationCount": self.project.configurations.len(), "configurationIndex": self.project.selected,
            "configurationLabels": self.project.labels(),"configurationContext":self.project.active_id,
            "geometry": {"dist":g.dist,"poni1":g.poni1,"poni2":g.poni2,"rot1":g.rot1,"rot2":g.rot2,"rot3":g.rot3,"wavelength":g.wavelength},
            "integration": {
                "roi":s.roi, "automaticBinning": s.automatic_binning, "actualBins": if s.automatic_binning {self.automatic_bins()}else{s.bins}, "supersampling":s.supersampling, "method":if s.pyfai_splitting {"pyfai_full"} else if s.supersampling > 1 {"subpixel"} else {"polygon"}, "azimuthRange":s.azimuth, "cakeAzimuthRange":s.cake_azimuth,
                "sparseLayout":if s.auto_layout {"auto"}else if s.csc {"csc"}else{"csr"},
                "cakeBins": s.cake_bins, "solidAngle":s.solid_angle, "polarization":s.polarization, "poissonErrors":s.errors, "trimZeros":s.trim_zeros,
                "autoSave":s.auto_save, "formats":s.formats, "outputDirectory":"", "imageBackground":{"filename":null,"scale":1,"offset":0},
                "patternBackground":{"enabled":false,"smoothing":1,"iterations":1,"order":1,"range":null,"overlay":false},
                "flatField":{"filename":null,"enabled":false}, "corrections":serde_json::from_str::<Value>(include_str!("correction_defaults.json")).expect("checked correction schema"), "overlayDirectory":"", "waterfallSeparation":0, "overlays":[], "sameConditions":true,
                "phaseColdPressure":false, "phases":[], "batchFrames":0, "patternName":name.clone().unwrap_or_default(), "patternPath":"", "patternFileIteration":"number",
                "originalPatternColor":"#ffffff", "originalPatternVisible":true, "fileInfo":"", "fileIteration":"number", "imageDirectory":image_directory,
                "autoProcess":false,"autoProcessError":"", "frame":self.image.as_ref().map(|i|i.frame+1).unwrap_or(0), "frames":self.image.as_ref().map(|i|i.frames).unwrap_or(0)
            },
            "calibration": {
                "setupConfirmed":s.calibrated, "detectorIsCustom":g.detector.as_ref().is_none_or(|d|d.name=="Detector"), "referenceLines":[],
                "workflow":{"autoIncrement":true,"searchSize":10,"automaticRefinement":false,"algorithm":"Massif","deltaTth":0.5,"meanFactor":3,"intensityLimit":55000,"numberOfRings":15},
                "parameters":parameters,"freeParameterCount":6,"polarization":s.polarization,"fitWavelength":false,"detectorFile":g.detector_file,"distortionFile":g.distortion_file.as_deref().or_else(||g.detector.as_ref().filter(|d|d.has_spline()).map(|_|"Embedded detector spline")),"transformations":s.transformations,
                "pyfai":g.manual_values(s.polarization),"fit2d":g.fit2d_values(s.polarization),"steps":["available","unavailable","unavailable","available"],"geometrySource":if s.calibrated {"loaded"} else {"none"},
                "canUndo":false,"canRedo":false,"engine":engine,"engineLabel":engine_label,"engines":[{"id":engine,"label":engine_label,"available":true}],
                "calibrant":"LaB6","calibrants":["LaB6"],"detectors":std::iter::once("Custom").chain(dioptrin::detector::catalog().iter().map(|d|d.name.as_str())).collect::<Vec<_>>(),"detector":g.detector.as_ref().map(|d|if d.name=="Detector" {"Custom"}else{d.name.as_str()}).unwrap_or("Custom"),"pixelX":g.pixel2*1e6,"pixelY":g.pixel1*1e6,"detectorOrientation":g.detector.as_ref().map(|d|d.orientation).unwrap_or(3),"detectorAssignment":g.assignment,"detectorCandidates":g.candidates,
                "distance":g.dist*1000.0,"wavelength":g.wavelength*1e10,"fitTilts":true,"fitDirty":false,"rmsDegrees":null,"saved":false,"picks":[],"rings":[]
            }
        }, "pattern":self.pattern, "cake":null, "rings":[], "linked":null, "batch":null, "map":null});
        trace.mark("base state");
        let mut buffers = Vec::new();
        for (key, value) in self.patterns.details().as_object().unwrap() {
            result["state"]["integration"][key] = value.clone();
        }
        result["state"]["integration"]["imageDirectory"] = json!(self.files.image_directory);
        result["state"]["integration"]["outputDirectory"] = json!(self.files.output_directory);
        result["state"]["integration"]["fileIteration"] = json!(self.files.image_mode);
        result["state"]["integration"]["autoProcess"] = json!(self.files.auto_process);
        result["state"]["integration"]["autoProcessError"] = json!(self.files.auto_error);
        result["state"]["integration"]["fileInfo"] = json!(
            self.image
                .as_ref()
                .map(|i| i.file_info.as_str())
                .unwrap_or("")
        );
        result["linked"] = self.linked_snapshot();
        result["state"]["integration"]["phases"] = self.phases.details();
        result["state"]["integration"]["batchFrames"] =
            json!(self.batch.as_ref().map_or(0, |b| b.count()));
        result["state"]["imageBatchMode"] = json!(self.image_batch_mode);
        result["state"]["integration"]["imageBatchMode"] = json!(self.image_batch_mode);
        result["state"]["maskDetails"]["filename"] = json!(self.mask_filename);
        result["state"]["integration"]["sameConditions"] = json!(self.phases.same_conditions);
        result["state"]["integration"]["phaseColdPressure"] = json!(self.phases.cold_pressure);
        for (key, value) in self.processing.details().as_object().unwrap() {
            result["state"]["integration"][key] = value.clone();
        }
        for (key, value) in self.calibration_payload().as_object().unwrap() {
            result["state"]["calibration"][key] = value.clone();
        }
        trace.mark("processing and calibration metadata");
        #[cfg(feature = "dioptrin")]
        if self.settings.calibrated && include_rings && self.control.calibration_rings_requested() {
            result["rings"] = self.calibration_rings();
        }
        #[cfg(not(feature = "dioptrin"))]
        let _ = include_rings;
        trace.mark("ring display metadata");
        if let Some(image) = &self.image {
            result["nativeSource"] = json!({"dtype":image.source_dtype,"storedOrientationPreserved":true,"scientificRowOrder":"bottom-up","frame":image.frame,"frames":image.frames,"ordinaryDecodes":image.ordinary_decodes,"loadPath":if image.parallel_pixels{"parallel-hdf5"}else if image.combined{"combined-hdf5"}else{"native-reader"}});
        }
        if include_image && let Some(raster) = &self.image_raster {
            result["rawImage"] = raster.metadata.clone();
            buffers.push(raster.buffer.clone());
            let processed = self.processed_raster.as_ref().unwrap_or(raster);
            result["image"] = processed.metadata.clone();
            buffers.push(processed.buffer.clone());
        }
        if let Some(raster) = &self.mask_raster {
            result["mask"] = raster.metadata.clone();
            buffers.push(raster.buffer.clone());
        }
        if let Some(raster) = self.cake.as_ref().filter(|_| self.control.cake_requested()) {
            result["cake"] = raster.metadata.clone();
            buffers.push(raster.buffer.clone());
        }
        let mut reply = Reply { result, buffers };
        self.attach_batch(&mut reply);
        self.attach_map(&mut reply);
        trace.mark("display buffers and series metadata");
        reply
    }
}

fn path(args: &Value) -> Result<&Path, String> {
    args["path"]
        .as_str()
        .filter(|s| !s.is_empty())
        .map(Path::new)
        .ok_or("Choose a file in the desktop application.".into())
}
fn check_keys(args: &Value, allowed: &[&str]) -> Result<(), String> {
    if let Some(key) = args
        .as_object()
        .ok_or("Command arguments must be an object.")?
        .keys()
        .find(|key| !allowed.contains(&key.as_str()))
    {
        return Err(format!(
            "Argument {key} is not supported by the native backend yet."
        ));
    }
    Ok(())
}
fn boolean(value: &Value, label: &str) -> Result<bool, String> {
    value.as_bool().ok_or(format!("{label} must be a boolean."))
}
fn optional_azimuth(value: &Value) -> Result<Option<[f64; 2]>, String> {
    if value.is_null() {
        return Ok(None);
    }
    let a = value
        .as_array()
        .filter(|a| a.len() == 2)
        .ok_or("Azimuth range needs two angles or full range.")?;
    let range = [
        finite(&a[0], "Azimuth (°)", -180.0, 180.0)?,
        finite(&a[1], "Azimuth (°)", -180.0, 180.0)?,
    ];
    if range[0] == range[1] {
        return Err("Azimuth endpoints must differ.".into());
    }
    Ok(Some(range))
}
fn finite(value: &Value, label: &str, low: f64, high: f64) -> Result<f64, String> {
    value
        .as_f64()
        .filter(|v| v.is_finite() && *v >= low && *v <= high)
        .ok_or(format!(
            "{label} must be finite and between {low} and {high}."
        ))
}
fn integer(value: &Value, label: &str, low: usize, high: usize) -> Result<usize, String> {
    value
        .as_u64()
        .and_then(|n| usize::try_from(n).ok())
        .filter(|n| *n >= low && *n <= high)
        .ok_or(format!(
            "{label} must be an integer between {low} and {high}."
        ))
}
pub(crate) fn atomic_write(path: &Path, bytes: &[u8]) -> Result<(), String> {
    use std::io::Write;
    let mut temp = tempfile::NamedTempFile::new_in(
        path.parent()
            .filter(|p| !p.as_os_str().is_empty())
            .unwrap_or(Path::new(".")),
    )
    .map_err(|e| e.to_string())?;
    temp.write_all(bytes)
        .and_then(|_| temp.as_file().sync_all())
        .map_err(|e| e.to_string())?;
    temp.persist(path).map_err(|e| e.to_string())?;
    Ok(())
}

#[cfg(test)]
mod detector_mask_cache_tests {
    use super::*;
    #[test]
    fn source_gap_mask_is_reused_across_frames_and_invalidated_for_new_sources() {
        let mut session = Session::new(PathBuf::new());
        session
            .settings
            .geometry
            .select_detector("Eiger2 CdTe 500k")
            .unwrap();
        let [h, w] = [256, 514];
        let mut data = vec![120.; h * w];
        for r in 0..h {
            for c in 254..260 {
                data[r * w + c] = 0.;
            }
        }
        session.image = Some(
            Image::from_cached(
                PathBuf::from("unavailable-source.h5"),
                0,
                3,
                [h, w],
                data,
                json!({}),
            )
            .unwrap(),
        );
        let first = session.physical_mask([h, w]).unwrap().unwrap();
        session.image.as_mut().unwrap().frame = 1;
        let second = session.physical_mask([h, w]).unwrap().unwrap();
        assert!(Arc::ptr_eq(&first, &second));
        session.image.as_mut().unwrap().path = PathBuf::from("another-source.h5");
        let changed = session.physical_mask([h, w]).unwrap().unwrap();
        assert!(!Arc::ptr_eq(&first, &changed));
        assert_eq!(first.as_ref(), changed.as_ref());
        let bright = session.image.as_ref().unwrap().values.clone();
        let image = session.image.as_mut().unwrap();
        image.path = PathBuf::from("initially-dark.h5");
        image.frame = 0;
        image.values = Arc::new(vec![0.; h * w]);
        let dark = session.physical_mask([h, w]).unwrap().unwrap();
        let image = session.image.as_mut().unwrap();
        image.frame = 1;
        image.values = bright;
        let learned = session.physical_mask([h, w]).unwrap().unwrap();
        assert!(
            learned.iter().filter(|&&v| v != 0).count() > dark.iter().filter(|&&v| v != 0).count()
        );
        session.image.as_mut().unwrap().frame = 2;
        assert!(Arc::ptr_eq(
            &learned,
            &session.physical_mask([h, w]).unwrap().unwrap()
        ));
    }
}
