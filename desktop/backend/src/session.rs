use crate::{
    display::{self, Raster},
    geometry::Geometry,
    image::Image,
    protocol::{Reply, Request},
};
use serde_json::{Value, json};
use std::path::{Path, PathBuf};
#[cfg(feature = "dioptrin")]
use std::time::Instant;

#[derive(Clone)]
struct Settings {
    geometry: Geometry,
    calibrated: bool,
    calibration_name: Option<String>,
    unit: String,
    bins: usize,
    cake_bins: usize,
    use_mask: bool,
    transparent_mask: bool,
    polarization: f64,
    errors: bool,
}
impl Default for Settings {
    fn default() -> Self {
        Self {
            geometry: Geometry::default(),
            calibrated: false,
            calibration_name: None,
            unit: "2th_deg".into(),
            bins: 1000,
            cake_bins: 360,
            use_mask: true,
            transparent_mask: false,
            polarization: 0.99,
            errors: false,
        }
    }
}

/// A session is constructed and used exclusively on the processing worker.
pub struct Session {
    root: PathBuf,
    settings: Settings,
    image: Option<Image>,
    image_raster: Option<Raster>,
    mask: Vec<u8>,
    mask_raster: Option<Raster>,
    undo: Vec<Vec<u8>>,
    redo: Vec<Vec<u8>>,
    revision: u64,
    elapsed_ms: Option<f64>,
    pattern: Option<Value>,
    cake: Option<Raster>,
    cake_values: Option<Vec<f64>>,
    #[cfg(feature = "dioptrin")]
    sigma: Option<Vec<f64>>,
}
impl Session {
    pub fn new(root: PathBuf) -> Self {
        Self {
            root,
            settings: Settings::default(),
            image: None,
            image_raster: None,
            mask: vec![],
            mask_raster: None,
            undo: vec![],
            redo: vec![],
            revision: 0,
            elapsed_ms: None,
            pattern: None,
            cake: None,
            cake_values: None,
            #[cfg(feature = "dioptrin")]
            sigma: None,
        }
    }
    pub fn invoke(&mut self, request: &Request) -> Reply {
        if let Err(error) = request.validate() {
            return Reply::error(error);
        }
        match self.dispatch(&request.action, &request.payload) {
            Ok(reply) => reply,
            Err(error) => Reply::error(error),
        }
    }
    fn dispatch(&mut self, action: &str, args: &Value) -> Result<Reply, String> {
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
                "capabilities": ["image-input", "frame-navigation", "binary-rasters", "display-statistics", "mask-brush", "mask-history", "uniform-poni", "manual-pyfai-geometry", "xy-export"]}),
                ));
            }
            "state" => return Ok(self.snapshot(true)),
            "example" => {
                let path = self.root.join("dioptas/tests/data/CeO2_Pilatus1M.tif");
                let candidate = Image::open(&path, &json!({}))?;
                let mut settings = Settings::default();
                settings.geometry.pixel1 = 172e-6;
                settings.geometry.pixel2 = 172e-6;
                settings.geometry.wavelength = 0.406626e-10;
                self.settings = settings;
                self.undo.clear();
                self.redo.clear();
                self.image = None;
                self.publish_image(candidate);
            }
            "open_image" => {
                check_keys(
                    args,
                    &[
                        "path",
                        "frame",
                        "dataset",
                        "follow_external_links",
                        "cbf_dialect",
                        "defer_integration",
                    ],
                )?;
                let image = Image::open(path(args)?, args)?;
                self.publish_image(image);
                self.calculate(defer)?;
            }
            "next_image" => {
                check_keys(args, &["direction", "step", "defer_integration"])?;
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
                let image = self.image.as_mut().ok_or("Open an image first.")?;
                let index = (image.frame as i64)
                    .checked_add(
                        direction
                            .checked_mul(step as i64)
                            .ok_or("Frame step exceeds range.")?,
                    )
                    .ok_or("Frame step exceeds range.")?;
                if index < 0 || index >= image.frames as i64 {
                    return Err("No further frame in this source. Neighboring-file navigation is not migrated yet.".into());
                }
                let previous_shape = image.shape;
                image.read(index as usize)?;
                if image.shape != previous_shape {
                    self.mask = vec![0; image.values.len()];
                    self.undo.clear();
                    self.redo.clear();
                    self.mask_raster = Some(Raster::mask(&self.mask, image.shape));
                }
                self.image_raster = Some(Raster::image(&image.values, image.shape));
                self.calculate(defer)?;
            }
            "open_calibration" => {
                check_keys(args, &["path", "defer_integration"])?;
                let file = path(args)?;
                let candidate = Geometry::load(file)?;
                self.settings.geometry = candidate;
                self.settings.calibrated = true;
                self.settings.calibration_name = Some(
                    file.file_name()
                        .unwrap_or_default()
                        .to_string_lossy()
                        .into_owned(),
                );
                self.calculate(defer)?;
            }
            "manual_geometry" => {
                check_keys(args, &["convention", "values", "defer_integration"])?;
                if args["convention"] != "pyfai" {
                    return Err("Fit2D conversion is not migrated yet; use the pyFAI geometry fields or a supported PONI file.".into());
                }
                let (geometry, polarization) = Geometry::manual(&args["values"])?;
                self.settings.geometry = geometry;
                self.settings.polarization = polarization;
                self.settings.calibrated = true;
                self.settings.calibration_name = Some("manual".into());
                self.calculate(defer)?;
            }
            "save_calibration" => {
                check_keys(args, &["path"])?;
                if !self.settings.calibrated {
                    return Err("Load or enter a calibration first.".into());
                }
                let file = path(args)?;
                atomic_write(file, self.settings.geometry.save_text().as_bytes())?;
                return Ok(Reply::metadata(json!({"ok": true, "savedPath": file})));
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
                        "bins" => candidate.bins = integer(value, "Radial bins", 1, 10000)?,
                        "cake_bins" => candidate.cake_bins = integer(value, "Cake bins", 1, 1440)?,
                        "use_mask" => candidate.use_mask = boolean(value, key)?,
                        "transparent_mask" => candidate.transparent_mask = boolean(value, key)?,
                        "polarization" => {
                            candidate.polarization = finite(value, "Polarization", -1.0, 1.0)?
                        }
                        "poisson_errors" => candidate.errors = boolean(value, key)?,
                        "solid_angle" if value == true => {}
                        "supersampling" if value.as_u64() == Some(1) => {}
                        "trim_zeros" | "auto_save" if value == false => {}
                        "azimuth_range" | "cake_azimuth_range" if value.is_null() => {}
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
                if candidate
                    .bins
                    .checked_mul(candidate.cake_bins)
                    .is_none_or(|n| n > 4_000_000)
                {
                    return Err("Cake output exceeds four million bins.".into());
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
                        (image.values.as_slice(), image.shape, "detector")
                    }
                    "cake" => {
                        let Some(data) = self.cake_values.as_ref() else {
                            return Ok(Reply::metadata(
                                json!({"ok":true,"display":"cake","levels":null}),
                            ));
                        };
                        (
                            data.as_slice(),
                            [self.settings.cake_bins, self.settings.bins],
                            "cake",
                        )
                    }
                    _ => return Err("Choose detector, raw_detector or cake display.".into()),
                };
                return Ok(Reply::metadata(
                    json!({"ok": true, "display": display, "levels": display::levels(data, shape, mode, percentile, filter)}),
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
                let pixel = json!({"x":x,"y":y,"value":image.values[y*image.shape[1]+x]});
                #[cfg(feature = "dioptrin")]
                let pixel = {
                    let mut pixel = pixel;
                    if self.settings.calibrated {
                        let geometry = dioptrin::geometry::Geometry::new(
                            image.shape[0],
                            image.shape[1],
                            self.settings.geometry.native_poni(),
                        );
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
                let mut mask = self.mask.clone();
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
                self.replace_mask(mask);
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
                let (source, destination) = if action == "undo_mask" {
                    (&mut self.undo, &mut self.redo)
                } else {
                    (&mut self.redo, &mut self.undo)
                };
                let previous = source.pop().ok_or("No mask edit to undo/redo.")?;
                destination.push(std::mem::replace(&mut self.mask, previous));
                self.mask_raster =
                    Some(Raster::mask(&self.mask, self.image.as_ref().unwrap().shape));
                self.calculate(defer)?;
            }
            "export_pattern" | "integration_save_pattern" => {
                check_keys(args, &["path"])?;
                let file = path(args)?;
                if file.extension().and_then(|s| s.to_str()) != Some("xy") {
                    return Err("Only XY export is migrated so far; choose a .xy file.".into());
                }
                let pattern = self
                    .pattern
                    .as_ref()
                    .ok_or("Integrate an image before saving a pattern.")?;
                let mut text = format!(
                    "# Dioptas native backend; radial unit: {}\n",
                    self.settings.unit
                );
                for (x, y) in pattern["x"]
                    .as_array()
                    .unwrap()
                    .iter()
                    .zip(pattern["y"].as_array().unwrap())
                {
                    let x = x
                        .as_f64()
                        .ok_or("Pattern contains a nonfinite coordinate.")?;
                    let y = y
                        .as_f64()
                        .ok_or("Pattern contains a nonfinite intensity.")?;
                    text.push_str(&format!("{x:.17e} {y:.17e}\n"));
                }
                atomic_write(file, text.as_bytes())?;
                return Ok(Reply::metadata(json!({"ok": true, "savedPath": file})));
            }
            "integration_phase_guides" => {
                return Ok(Reply::metadata(json!({"ok": true, "phaseGuides": []})));
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
    fn publish_image(&mut self, image: Image) {
        self.image_raster = Some(Raster::image(&image.values, image.shape));
        if self
            .image
            .as_ref()
            .is_none_or(|old| old.shape != image.shape)
        {
            self.mask = vec![0; image.values.len()];
            self.undo.clear();
            self.redo.clear();
        }
        self.mask_raster = Some(Raster::mask(&self.mask, image.shape));
        self.image = Some(image);
        self.pattern = None;
        self.cake = None;
        self.cake_values = None;
        self.elapsed_ms = None;
    }
    fn replace_mask(&mut self, mask: Vec<u8>) {
        // Bound history payloads to 128 MiB, including redo. No unbounded list
        // of full-resolution masks is retained.
        self.undo.push(std::mem::replace(&mut self.mask, mask));
        self.redo.clear();
        while self.undo.len() > 1
            && self.undo.iter().map(Vec::len).sum::<usize>() > 128 * 1024 * 1024
        {
            self.undo.remove(0);
        }
        self.mask_raster = Some(Raster::mask(&self.mask, self.image.as_ref().unwrap().shape));
    }
    fn calculate(&mut self, defer: bool) -> Result<(), String> {
        self.pattern = None;
        self.cake = None;
        self.cake_values = None;
        self.elapsed_ms = None;
        if defer {
            return Ok(());
        }
        #[cfg(feature = "dioptrin")]
        {
            self.sigma = None;
            if let Some(image) = &self.image
                && self.settings.calibrated
            {
                let start = Instant::now();
                let clear = vec![];
                let mask = if self.settings.use_mask {
                    &self.mask
                } else {
                    &clear
                };
                let unmasked;
                let mask = if mask.is_empty() {
                    unmasked = vec![0; image.values.len()];
                    &unmasked
                } else {
                    mask
                };
                let products = crate::integration::integrate(
                    image,
                    &self.settings.geometry,
                    mask,
                    crate::integration::Options {
                        bins: self.settings.bins,
                        cake_bins: self.settings.cake_bins,
                        unit: &self.settings.unit,
                        polarization: self.settings.polarization,
                        errors: self.settings.errors,
                    },
                );
                self.pattern = Some(products.pattern);
                self.cake = Some(products.cake);
                self.cake_values = Some(products.cake_values);
                self.sigma = products.sigma;
                self.elapsed_ms = Some(start.elapsed().as_secs_f64() * 1000.0);
            }
        }
        Ok(())
    }
    fn snapshot(&self, include_image: bool) -> Reply {
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
            "revision": self.revision, "hasImage": self.image.is_some(), "imageName": name, "imagePath": image_path, "shape": shape,
            "calibrationName": s.calibration_name, "calibrated": s.calibrated, "projectName": null, "unit": s.unit,
            "bins": s.bins, "useMask": s.use_mask, "transparentMask": s.transparent_mask,
            "maskedPixels": self.mask.iter().filter(|&&v| v != 0).count(), "canUndoMask": !self.undo.is_empty(), "canRedoMask": !self.redo.is_empty(),
            "maskDetails": {"mode": true, "filename": null, "plugins": []}, "exampleAvailable": self.root.join("dioptas/tests/data/CeO2_Pilatus1M.tif").is_file(),
            "elapsedMs": self.elapsed_ms, "integrationDirty": self.image.is_some() && s.calibrated && self.pattern.is_none(), "configurationCount": 1, "configurationIndex": 0,
            "geometry": {"dist":g.dist,"poni1":g.poni1,"poni2":g.poni2,"rot1":g.rot1,"rot2":g.rot2,"rot3":g.rot3,"wavelength":g.wavelength},
            "integration": {
                "roi":null, "automaticBinning": false, "actualBins": s.bins, "supersampling":1, "azimuthRange":null, "cakeAzimuthRange":null,
                "cakeBins": s.cake_bins, "solidAngle":true, "polarization":s.polarization, "poissonErrors":s.errors, "trimZeros":false,
                "autoSave":false, "formats":[".xy"], "outputDirectory":"", "imageBackground":{"filename":null,"scale":1,"offset":0},
                "patternBackground":{"enabled":false,"smoothing":1,"iterations":1,"order":1,"range":null,"overlay":false},
                "flatField":{"filename":null,"enabled":false}, "corrections":serde_json::from_str::<Value>(include_str!("correction_defaults.json")).expect("checked correction schema"), "overlayDirectory":"", "waterfallSeparation":0, "overlays":[], "sameConditions":true,
                "phaseColdPressure":false, "phases":[], "batchFrames":0, "patternName":name.clone().unwrap_or_default(), "patternPath":"", "patternFileIteration":"number",
                "originalPatternColor":"#ffffff", "originalPatternVisible":true, "fileInfo":"", "fileIteration":"number", "imageDirectory":image_directory,
                "autoProcess":false,"autoProcessError":"", "frame":self.image.as_ref().map(|i|i.frame).unwrap_or(0), "frames":self.image.as_ref().map(|i|i.frames).unwrap_or(0)
            },
            "calibration": {
                "setupConfirmed":s.calibrated, "detectorIsCustom":true, "referenceLines":[],
                "workflow":{"autoIncrement":true,"searchSize":10,"automaticRefinement":false,"algorithm":"Massif","deltaTth":0.5,"meanFactor":3,"intensityLimit":55000,"numberOfRings":15},
                "parameters":parameters,"freeParameterCount":6,"polarization":s.polarization,"fitWavelength":false,"detectorFile":null,"distortionFile":null,"transformations":[],
                "pyfai":g.manual_values(s.polarization),"fit2d":{},"steps":["available","unavailable","unavailable","available"],"geometrySource":if s.calibrated {"loaded"} else {"none"},
                "canUndo":false,"canRedo":false,"engine":engine,"engineLabel":engine_label,"engines":[{"id":engine,"label":engine_label,"available":true}],
                "calibrant":"LaB6","calibrants":["LaB6"],"detectors":["Custom"],"detector":"Custom","pixelX":g.pixel2*1e6,"pixelY":g.pixel1*1e6,
                "distance":g.dist*1000.0,"wavelength":g.wavelength*1e10,"fitTilts":true,"fitDirty":false,"rmsDegrees":null,"saved":false,"picks":[],"rings":[]
            }
        }, "pattern":self.pattern, "cake":null, "rings":[], "linked":null, "batch":null, "map":null});
        let mut buffers = Vec::new();
        if let Some(image) = &self.image {
            result["nativeSource"] = json!({"dtype":image.source_dtype,"storedOrientationPreserved":true,"scientificRowOrder":"bottom-up","frame":image.frame,"frames":image.frames});
        }
        if include_image && let Some(raster) = &self.image_raster {
            result["image"] = raster.metadata.clone();
            result["rawImage"] = raster.metadata.clone();
            buffers.push(raster.buffer.clone());
        }
        if let Some(raster) = &self.mask_raster {
            result["mask"] = raster.metadata.clone();
            buffers.push(raster.buffer.clone());
        }
        if let Some(raster) = &self.cake {
            result["cake"] = raster.metadata.clone();
            buffers.push(raster.buffer.clone());
        }
        #[cfg(feature = "dioptrin")]
        if let Some(sigma) = &self.sigma
            && result["pattern"].is_object()
        {
            result["pattern"]["sigma"] = json!(sigma);
        }
        Reply { result, buffers }
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
fn atomic_write(path: &Path, bytes: &[u8]) -> Result<(), String> {
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
