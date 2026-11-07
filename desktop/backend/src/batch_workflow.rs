//! The owning integration engine is reused by image navigation, Batch and Map.
use super::*;
#[cfg(feature = "dioptrin")]
use crate::series::Entry;
use crate::series::Series;
pub(super) fn source_paths(args: &Value) -> Result<Vec<String>, String> {
    let list = if let Some(p) = args["paths"].as_array() {
        p.clone()
    } else if args["paths"].is_string() {
        vec![args["paths"].clone()]
    } else {
        return Err("Choose an ordered list of detector images.".into());
    };
    if list.is_empty() || list.len() > 100_000 {
        return Err("Choose 1–100000 source files.".into());
    }
    list.iter()
        .map(|p| {
            p.as_str()
                .filter(|s| !s.is_empty())
                .map(str::to_string)
                .ok_or_else(|| "Choose image paths.".into())
        })
        .collect()
}
pub(super) fn folder_paths(folder: &Path) -> Result<Vec<String>, String> {
    let mut paths = std::fs::read_dir(folder)
        .map_err(|e| e.to_string())?
        .filter_map(Result::ok)
        .map(|e| e.path())
        .filter(|p| p.is_file() && file_workflow::image_file(p))
        .collect::<Vec<_>>();
    paths.sort_by(|a, b| {
        natural_cmp(
            &a.file_name().unwrap().to_string_lossy(),
            &b.file_name().unwrap().to_string_lossy(),
        )
    });
    if paths.is_empty() {
        return Err("No supported detector images were found in this folder.".into());
    }
    Ok(paths
        .iter()
        .map(|p| p.to_string_lossy().into_owned())
        .collect())
}
fn natural_cmp(a: &str, b: &str) -> std::cmp::Ordering {
    let (mut ai, mut bi) = (a.as_bytes(), b.as_bytes());
    while !ai.is_empty() && !bi.is_empty() {
        let an = ai.iter().take_while(|c| c.is_ascii_digit()).count();
        let bn = bi.iter().take_while(|c| c.is_ascii_digit()).count();
        if an > 0 && bn > 0 {
            let aa = std::str::from_utf8(&ai[..an])
                .unwrap()
                .trim_start_matches('0');
            let bb = std::str::from_utf8(&bi[..bn])
                .unwrap()
                .trim_start_matches('0');
            let c = aa.len().cmp(&bb.len()).then_with(|| aa.cmp(bb));
            if c != std::cmp::Ordering::Equal {
                return c;
            }
            ai = &ai[an..];
            bi = &bi[bn..];
        } else {
            let c = ai[0].to_ascii_lowercase().cmp(&bi[0].to_ascii_lowercase());
            if c != std::cmp::Ordering::Equal {
                return c;
            }
            ai = &ai[1..];
            bi = &bi[1..];
        }
    }
    ai.len().cmp(&bi.len())
}
impl Session {
    pub(super) fn integrate_series(
        &mut self,
        paths: Vec<String>,
        args: &Value,
    ) -> Result<Series, String> {
        if !self.settings.calibrated {
            return Err("Load a PONI calibration before integrating a series.".into());
        }
        #[cfg(not(feature = "dioptrin"))]
        {
            let _ = (paths, args);
            Err("Batch integration requires the optional Dioptrin engine.".into())
        }
        #[cfg(feature = "dioptrin")]
        {
            let checkpoint = self.checkpoint();
            let outcome = (|| {
                let mut images = Vec::new();
                let mut total = 0usize;
                let mut expected = self.image.as_ref().map(|i| i.shape);
                let options = self
                    .image
                    .as_ref()
                    .map(|i| i.options.clone())
                    .unwrap_or(json!({}));
                for (i, p) in paths.iter().enumerate() {
                    self.control.check()?;
                    self.control.publish(json!({"running":true,"current":i,"total":paths.len(),"label":"Reading series metadata"}));
                    let mut image = Image::prepare(Path::new(p), &options)?;
                    if image.shape == [0, 0] {
                        image.read(0)?;
                    }
                    if expected.is_some_and(|s| s != image.shape) {
                        return Err("Series images must have the current detector shape.".into());
                    }
                    expected = Some(image.shape);
                    total = total
                        .checked_add(image.frames)
                        .filter(|t| *t <= 1_000_000)
                        .ok_or("The series exceeds one million frames.")?;
                    let fingerprint = image.source_fingerprint()?;
                    images.push((image.path.clone(), image.frames, image.shape, fingerprint));
                }
                let start = args
                    .get("start")
                    .map_or(Ok(1), |v| integer(v, "First frame", 1, total))?
                    - 1;
                let stop = args
                    .get("stop")
                    .filter(|v| !v.is_null())
                    .map_or(Ok(total), |v| integer(v, "Last frame", start + 1, total))?;
                let step = args
                    .get("step")
                    .map_or(Ok(1), |v| integer(v, "Frame stride", 1, 1_000_000))?;
                let count = (stop - start).div_ceil(step);
                if self.image.is_none() {
                    let shape = expected.unwrap();
                    self.mask = Arc::new(vec![0; shape[0] * shape[1]]);
                    self.effective_mask = self.mask.clone();
                }
                let mut global = 0usize;
                let mut x = None;
                let mut data = vec![];
                let mut spread: Option<Vec<f64>> = None;
                let mut entries = vec![];
                for (source, frames, shape, fingerprint) in &images {
                    for (path, identity) in fingerprint {
                        if crate::image::FileIdentity::read(path)? != *identity {
                            return Err("A series source changed after metadata discovery.".into());
                        }
                    }
                    let mut image = Image::prepare(source, &options)?;
                    if image.frames != *frames
                        || image.shape != *shape
                        || image.source_fingerprint()? != *fingerprint
                    {
                        return Err("A series source changed after metadata discovery.".into());
                    }

                    for frame in 0..image.frames {
                        let selected = global >= start
                            && global < stop
                            && (global - start).is_multiple_of(step);
                        global += 1;
                        if !selected {
                            continue;
                        }
                        self.control.check()?;
                        self.control.publish(json!({"running":true,"current":entries.len(),"total":count,"label":"Integrating series"}));
                        let mut options = self.integration_options();
                        if options.automatic_bins {
                            options.bins = self.settings.geometry.automatic_bins(image.shape);
                        }
                        let mask = self.integration_mask(image.shape);
                        let prepared = if !self.processing.active() {
                            self.engine.load_combined(
                                &mut image,
                                frame,
                                &self.settings.geometry,
                                &mask,
                                &options,
                                &self.control,
                            )?
                        } else {
                            None
                        };
                        if prepared.is_none() && (image.frame != frame || image.values.is_empty()) {
                            image.read(frame)?;
                        }
                        if Some(image.shape) != expected {
                            return Err("Series frames must have one detector shape.".into());
                        }
                        self.image_generation += 1;
                        self.image = Some(image.clone());
                        self.processed_values = None;
                        self.prepare_processing()?;
                        self.refresh_masks(&self.control.clone())?;
                        let options = self.integration_options();
                        let mask = self.integration_mask(image.shape);
                        let (pattern, _) = self.engine.integrate_pattern(
                            &self.scientific_values(),
                            image.shape,
                            &self.settings.geometry,
                            &mask,
                            &options,
                            prepared,
                        )?;
                        self.control.check()?;
                        let curve = crate::pattern::Curve::from_json(&pattern)?;
                        if let Some(previous) = &x {
                            if *previous != curve.x {
                                return Err("Series radial axes differ; use fixed binning or disable zero trimming.".into());
                            }
                        } else {
                            x = Some(curve.x.clone());
                        }
                        if data
                            .len()
                            .checked_add(curve.y.len())
                            .is_none_or(|n| n > 64_000_000)
                        {
                            return Err("Processed series exceeds 64 million samples.".into());
                        }
                        data.extend(curve.y.iter().copied());
                        if let Some(values) = pattern["azimuthalStd"].as_array() {
                            let target = spread.get_or_insert_with(Vec::new);
                            for v in values {
                                target.push(v.as_f64().unwrap_or(f64::NAN));
                            }
                        }
                        entries.push(Entry {
                            path: image.path.to_string_lossy().into_owned(),
                            frame,
                        });
                    }
                }
                for (_, _, _, fingerprint) in &images {
                    for (path, identity) in fingerprint {
                        if crate::image::FileIdentity::read(path)? != *identity {
                            return Err("A series source changed during integration; no partial series was published.".into());
                        }
                    }
                }
                let mut series = Series::new(
                    x.ok_or("No frames were integrated.")?.as_ref().clone(),
                    data,
                    self.settings.unit.clone(),
                    Some(self.settings.geometry.wavelength),
                    entries,
                    images
                        .iter()
                        .map(|(p, _, _, _)| p.to_string_lossy().into_owned())
                        .collect(),
                    total,
                )?;
                series.file_counts = images.iter().map(|(_, frames, _, _)| *frames).collect();
                series.spread = spread.map(Arc::new);
                series.raw_spread = series.spread.clone();
                series.calibration = self.settings.calibration_name.clone().unwrap_or_default();
                series.mask = self.mask_filename.clone().unwrap_or_default();
                Ok(series)
            })();
            self.restore_checkpoint(checkpoint);
            outcome
        }
    }
    pub(super) fn attach_batch(&self, reply: &mut Reply) {
        if let Some(b) = &self.batch {
            reply.result["batch"] = b.metadata(
                &self.settings.unit,
                self.phases
                    .lines("d_A", self.settings.geometry.wavelength * 1e10),
            );
            reply.buffers.push(b.raster.buffer.clone());
        } else {
            reply.result["batch"] = Value::Null;
        }
    }
    pub(super) fn select_series(
        &mut self,
        series: &Series,
        index: usize,
        defer: bool,
        stored: bool,
        stored_unit: Option<&str>,
    ) -> Result<Reply, String> {
        let entry = series
            .entries
            .get(index)
            .ok_or("Select a frame within the series.")?;
        let available = !entry.path.is_empty() && Path::new(&entry.path).is_file();
        let mut warning = Value::Null;
        if available {
            let checkpoint = self.checkpoint();
            let mut args = self
                .image
                .as_ref()
                .map(|i| i.options.clone())
                .unwrap_or(json!({}));
            args["path"] = json!(entry.path);
            args["frame"] = json!(entry.frame);
            args["defer_integration"] = json!(defer);
            let auto = self.settings.auto_save;
            self.settings.auto_save = false;
            let loaded = self.dispatch("open_image", &args);
            self.settings.auto_save = auto;
            if let Err(error) = loaded {
                self.restore_checkpoint(checkpoint);
                warning = json!(format!("Raw detector image unavailable: {error}"));
                self.image = None;
            }
        } else {
            self.image = None;
            warning = json!("Raw detector image unavailable; showing the stored pattern.");
        }
        if self.image.is_none() {
            self.image_raster = None;
            self.processed_raster = None;
            self.processed_values = None;
            self.cake = None;
            self.cake_values = None;
            self.inspection = None;
        }
        if stored {
            let unit = if let Some(unit) = stored_unit {
                unit.to_string()
            } else if series.wavelength.is_none()
                && series.unit != self.settings.unit
                && [series.unit.as_str(), self.settings.unit.as_str()].contains(&"2th_deg")
            {
                series.unit.clone()
            } else {
                self.settings.unit.clone()
            };
            let curve = series.profile(index, &unit)?;
            self.patterns.ingest(
                curve,
                &unit,
                Path::new(&entry.path)
                    .file_name()
                    .unwrap_or_default()
                    .to_string_lossy()
                    .as_ref(),
                Some(entry.path.clone()),
                false,
            );
            self.rebuild_pattern()?;
        }
        self.revision += 1;
        let mut reply = self.snapshot(self.image.is_some());
        reply.result["clearImage"] = json!(self.image.is_none());
        reply.result["batchWarning"] = warning;
        Ok(reply)
    }
    pub(super) fn batch_command(
        &mut self,
        action: &str,
        args: &Value,
    ) -> Result<Option<Reply>, String> {
        match action {
            "image_batch_mode" => {
                let mode = args["mode"]
                    .as_str()
                    .filter(|s| ["integrate", "add", "average", "save"].contains(s))
                    .ok_or("Choose integrate, add, average or save.")?;
                self.image_batch_mode = mode.into();
                self.revision += 1;
                return Ok(Some(self.snapshot(false)));
            }
            "batch_load" | "batch_load_data" | "batch_folder" | "integration_batch" => {
                let paths = if action == "batch_folder" || action == "integration_batch" {
                    folder_paths(path(args)?)?
                } else if args["reintegrate"] == true {
                    self.batch
                        .as_ref()
                        .ok_or("Load raw images first.")?
                        .paths
                        .clone()
                } else {
                    source_paths(args)?
                };
                if action == "batch_load_data"
                    && paths.len() == 1
                    && is_processed(Path::new(&paths[0]))
                {
                    self.batch = Some(Series::load(Path::new(&paths[0]))?);
                } else {
                    self.batch = Some(self.integrate_series(paths, args)?);
                }
                self.batch.as_mut().unwrap().selected = 0;
                let b = self.batch.as_ref().unwrap().clone();
                let mut reply = self.select_series(&b, 0, false, true, None)?;
                self.attach_batch(&mut reply);
                reply.result["batchOpened"] = json!(true);
                return Ok(Some(reply));
            }
            "batch_open" => {
                self.batch = Some(Series::load(path(args)?)?);
                self.batch.as_mut().unwrap().selected = 0;
                let b = self.batch.as_ref().unwrap().clone();
                let mut reply = self.select_series(&b, 0, false, true, None)?;
                self.attach_batch(&mut reply);
                reply.result["batchOpened"] = json!(true);
                return Ok(Some(reply));
            }
            "batch_snapshot" => {
                let mut reply = Reply::metadata(json!({"ok":true}));
                self.attach_batch(&mut reply);
                return Ok(Some(reply));
            }
            "integration_save_batch" => {
                let file = path(args)?;
                let file = if file.extension().is_none() {
                    file.with_extension("h5")
                } else {
                    file.to_path_buf()
                };
                if !["csv", "h5", "hdf5", "nxs"].contains(
                    &file
                        .extension()
                        .unwrap_or_default()
                        .to_string_lossy()
                        .to_lowercase()
                        .as_str(),
                ) {
                    return Err("Save a batch as HDF5 or CSV.".into());
                }
                self.batch
                    .as_ref()
                    .ok_or("Integrate a batch first.")?
                    .save(&file)?;
                return Ok(Some(Reply::metadata(json!({"ok":true,"savedPath":file}))));
            }
            "batch_select" => {
                let b = self
                    .batch
                    .as_ref()
                    .ok_or("Load and integrate batch images first.")?;
                let i = integer(&args["index"], "Batch frame", 0, b.count() - 1)?;
                self.batch.as_mut().unwrap().selected = i;
                let b = self.batch.as_ref().unwrap().clone();
                let mut reply = self.select_series(&b, i, false, true, None)?;
                reply.result["batchSelection"] = json!(i);
                if let Some(p) = args.get("position") {
                    let unit = p["unit"]
                        .as_str()
                        .filter(|u| ["2th_deg", "q_A^-1", "d_A"].contains(u))
                        .ok_or("Choose a valid batch radial position.")?;
                    let x = finite(&p["x"], "Position", -1e12, 1e12)?;
                    reply.result["batchPosition"] = json!({"x":x,"unit":unit});
                    reply.result["batchWavelength"] = json!(b.wavelength);
                    if let Some(wavelength) = b.wavelength
                        && self.image.is_some()
                        && self.settings.calibrated
                    {
                        let tth = linked::convert(x, unit, "2th_deg", wavelength);
                        if tth.is_finite() && (0.0..=180.0).contains(&tth) {
                            let inspection =
                                self.validation_position(&json!({"source":"cake","x":tth}))?;
                            reply.result["linked"] = inspection.result["linked"].clone();
                        }
                    }
                }
                return Ok(Some(reply));
            }
            "batch_unit" => {
                let unit = args["unit"]
                    .as_str()
                    .filter(|u| ["2th_deg", "q_A^-1", "d_A"].contains(u))
                    .ok_or("Choose 2theta, Q or d.")?;
                let b = self.batch.as_ref().ok_or("Load a series first.")?;
                b.profile(b.selected, unit)?;
                self.settings.unit = unit.into();
                let b = b.clone();
                let mut reply = self.select_series(&b, b.selected, false, true, None)?;
                self.attach_batch(&mut reply);
                return Ok(Some(reply));
            }
            "batch_normalize" | "batch_normalization_settings" => {
                let b = self
                    .batch
                    .as_mut()
                    .ok_or("Load and integrate batch images first.")?;
                let zero = action == "batch_normalization_settings";
                let start = args.get("start").map_or(
                    Ok(if zero { b.normalization[0] } else { 1 }),
                    |v| {
                        integer(
                            v,
                            "First bin",
                            if zero { 0 } else { 1 },
                            b.x.len() - usize::from(zero),
                        )
                    },
                )? - usize::from(!zero);
                let stop = args.get("stop").filter(|v| !v.is_null()).map_or(
                    Ok(if zero {
                        b.normalization[1] - 1
                    } else {
                        b.x.len()
                    }),
                    |v| {
                        integer(
                            v,
                            "Last bin",
                            if zero { 0 } else { 1 },
                            b.x.len() - usize::from(zero),
                        )
                    },
                )? + usize::from(zero);
                let reference =
                    args.get("reference")
                        .map_or(Ok(if zero { b.reference } else { 1 }), |v| {
                            integer(
                                v,
                                "Reference frame",
                                if zero { 0 } else { 1 },
                                b.count() - usize::from(zero),
                            )
                        })?
                        - usize::from(!zero);
                let enabled = if zero {
                    b.normalized
                } else {
                    args.get("enabled")
                        .map_or(Ok(true), |v| boolean(v, "Normalize"))?
                };
                if start >= stop {
                    return Err("Choose increasing inclusive normalization bins.".into());
                }
                b.normalize(enabled, [start, stop], reference)?;
                let b = b.clone();
                let mut reply = self.select_series(&b, b.selected, false, true, None)?;
                self.attach_batch(&mut reply);
                return Ok(Some(reply));
            }
            "batch_levels" => {
                let b = self.batch.as_ref().ok_or("Load a series first.")?;
                return Ok(Some(Reply::metadata(
                    json!({"ok":true,"batchLevels":series_levels(&b.data,[b.count(),b.x.len()],args)?}),
                )));
            }
            "batch_folder_step" => {
                let b = self.batch.as_ref().ok_or("Load raw batch files first.")?;
                let first = b.paths.first().ok_or("No raw source paths.")?;
                let folder = Path::new(first).parent().ok_or("No source folder.")?;
                let direction = args["direction"]
                    .as_i64()
                    .filter(|d| [-1, 1].contains(d))
                    .ok_or("Choose previous or next folder.")?;
                let target = file_workflow::numbered(folder, direction)
                    .ok_or("No numbered neighboring scan folder.")?;
                let paths = folder_paths(&target)?;
                self.batch = Some(self.integrate_series(paths, &json!({}))?);
                self.batch.as_mut().unwrap().selected = 0;
                let b = self.batch.as_ref().unwrap().clone();
                let mut reply = self.select_series(&b, 0, false, true, None)?;
                self.attach_batch(&mut reply);
                return Ok(Some(reply));
            }
            _ => {}
        }
        Ok(None)
    }
}
pub(super) fn series_levels(
    data: &[f64],
    shape: [usize; 2],
    args: &Value,
) -> Result<Value, String> {
    let mode = args["mode"].as_str().unwrap_or("percentile");
    if !["percentile", "minmax", "mean3std"].contains(&mode) {
        return Err("Choose a supported intensity range mode.".into());
    }
    let clipping = args
        .get("clipping")
        .or_else(|| args.get("percentile"))
        .map_or(Ok(2.5), |v| finite(v, "Clipping", 0.0, 49.999999))?;
    let filter = args
        .get("filter_gaps")
        .map_or(Ok(true), |v| boolean(v, "Filter gaps"))?;
    Ok(json!(display::levels(data, shape, mode, clipping, filter)))
}
pub(super) fn is_processed(path: &Path) -> bool {
    hdf5::File::open(path).ok().is_some_and(|f| {
        f.link_exists("processed/result") || (f.link_exists("data") && f.link_exists("binning"))
    })
}
