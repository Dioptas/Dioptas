//! The owning integration engine is reused by image navigation, Batch and Map.
use super::*;
#[cfg(feature = "dioptrin")]
use crate::series::Entry;
use crate::series::Series;
#[cfg(feature = "dioptrin")]
struct MapProgress {
    windows: Vec<(crate::scan::Roi, crate::map_math::Window)>,
    active: String,
    expression: Option<crate::map_math::Expression>,
    shape: [usize; 2],
    values: Vec<f64>,
    updated: Option<std::time::Instant>,
}
#[cfg(feature = "dioptrin")]
impl MapProgress {
    fn new(
        x: &[f64],
        count: usize,
        unit: &str,
        wavelength: f64,
        previous: Option<&crate::scan::Scan>,
    ) -> Result<Self, String> {
        let analysis = crate::scan::Scan::analysis(x, unit, wavelength, previous)?;
        let expression = analysis
            .expressions
            .iter()
            .find(|(name, _)| *name == analysis.active)
            .map(|(_, text)| crate::map_math::Expression::parse(text))
            .transpose()?;
        Ok(Self {
            windows: analysis
                .rois
                .into_iter()
                .map(|roi| {
                    let window = crate::map_math::Window::new(
                        x,
                        roi.min,
                        roi.max,
                        &roi.reduction,
                        roi.background,
                    );
                    (roi, window)
                })
                .collect(),
            active: analysis.active,
            expression,
            shape: crate::scan::dimensions(count)[0],
            values: vec![f64::NAN; count],
            updated: None,
        })
    }
    fn push(
        &mut self,
        index: usize,
        curve: &crate::pattern::Curve,
        unit: &str,
        control: &crate::control::Control,
        patterns: &crate::pattern::Patterns,
    ) -> Result<(), String> {
        let layers: std::collections::BTreeMap<_, _> = self
            .windows
            .iter()
            .map(|(roi, window)| (roi.name.clone(), vec![window.reduce(&curve.y)]))
            .collect();
        self.values[index] = if let Some(expression) = &self.expression {
            expression.evaluate(&layers, 1, &|overlay, window| {
                let roi = self
                    .windows
                    .iter()
                    .find(|(roi, _)| roi.name == window)
                    .map(|(roi, _)| roi)
                    .ok_or("Unknown overlay window.")?;
                let curve = patterns
                    .overlays
                    .iter()
                    .find(|o| o.name == overlay)
                    .map(|o| o.curve(unit))
                    .transpose()?
                    .ok_or_else(|| format!("Unknown overlay {overlay}."))?;
                Ok(crate::map_math::reduce(
                    &curve.x,
                    &curve.y,
                    roi.min,
                    roi.max,
                    &roi.reduction,
                    roi.background,
                ))
            })?[0]
        } else {
            layers.get(&self.active).ok_or("Unknown preview layer.")?[0]
        };
        let now = std::time::Instant::now();
        if self
            .updated
            .is_some_and(|t| now.duration_since(t).as_millis() < 150)
            && index + 1 < self.values.len()
        {
            return Ok(());
        }
        let pixels: Vec<_> = self
            .values
            .chunks_exact(self.shape[1])
            .rev()
            .flatten()
            .copied()
            .collect();
        let raster = Raster::image(&pixels, self.shape);
        control.publish_map_preview(json!({"raster":raster.metadata,"completed":index+1,"total":self.values.len(),"active":self.active,"unit":unit,
            "pattern":{"x":curve.x,"y":curve.y,"unit":unit}}),raster.buffer);
        self.updated = Some(now);
        Ok(())
    }
}
#[cfg(feature = "dioptrin")]
struct RowContext<'a> {
    control: &'a crate::control::Control,
    settings: &'a Settings,
    scan: Option<&'a crate::scan::Scan>,
    patterns: &'a crate::pattern::Patterns,
}
#[cfg(feature = "dioptrin")]
struct SeriesRows {
    started: std::time::Instant,
    x: Option<Arc<Vec<f64>>>,
    data: Vec<f64>,
    sigma: Option<Vec<f64>>,
    spread: Option<Vec<f64>>,
    entries: Vec<Entry>,
    preview: Option<MapProgress>,
    preview_enabled: bool,
    count: usize,
}
#[cfg(feature = "dioptrin")]
impl SeriesRows {
    fn publish_progress(&self, control: &crate::control::Control) {
        let elapsed = self.started.elapsed().as_secs_f64();
        control.publish(
            json!({"running":true,"current":self.entries.len(),"total":self.count,
            "label":"Integrating series","elapsedSeconds":elapsed,
            "fps":self.entries.len() as f64 / elapsed.max(f64::EPSILON)}),
        );
    }
    fn push(
        &mut self,
        context: &RowContext<'_>,
        source: &Path,
        frame: usize,
        pattern: &Value,
    ) -> Result<(), String> {
        context.control.check()?;
        let curve = crate::pattern::Curve::from_json(pattern)?;
        if self.preview_enabled {
            if self.preview.is_none() {
                self.preview = Some(MapProgress::new(
                    &curve.x,
                    self.count,
                    &context.settings.unit,
                    context.settings.geometry.wavelength,
                    context.scan,
                )?);
            }
            self.preview.as_mut().unwrap().push(
                self.entries.len(),
                &curve,
                &context.settings.unit,
                context.control,
                context.patterns,
            )?;
        }
        if let Some(previous) = &self.x {
            if *previous != curve.x {
                return Err("Series radial axes differ; use fixed binning.".into());
            }
        } else {
            self.x = Some(curve.x.clone());
        }
        if self
            .data
            .len()
            .checked_add(curve.y.len())
            .is_none_or(|n| n > 64_000_000)
        {
            return Err("Processed series exceeds 64 million samples.".into());
        }
        self.data.extend(curve.y.iter().copied());
        if let Some(target) = &mut self.sigma {
            target.extend(
                curve
                    .sigma
                    .as_ref()
                    .ok_or("Series counting errors were not returned by the integrator.")?
                    .iter()
                    .copied(),
            );
        }
        if let Some(values) = pattern["azimuthalStd"].as_array() {
            let target = self.spread.get_or_insert_with(Vec::new);
            for v in values {
                target.push(v.as_f64().unwrap_or(f64::NAN));
            }
        }
        self.entries.push(Entry {
            path: source.to_string_lossy().into_owned(),
            frame,
        });
        self.publish_progress(context.control);
        Ok(())
    }
}
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
            let started = std::time::Instant::now();
            let checkpoint = self.checkpoint();
            let outcome = (|| {
                // Batch and Map rows need one shared grid even when exposures
                // have different zero edges. Restore the display preference
                // with the checkpoint after processing, including on failure.
                self.settings.trim_zeros = false;
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
                    image.orient(&self.settings.transformations, &self.control)?;
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
                let mut rows = SeriesRows {
                    started,
                    x: None,
                    data: vec![],
                    sigma: self.settings.errors.then(Vec::new),
                    spread: None,
                    entries: vec![],
                    preview: None,
                    preview_enabled: args["preview_map"] == true,
                    count,
                };
                rows.publish_progress(&self.control);
                for (source, frames, shape, fingerprint) in &images {
                    for (path, identity) in fingerprint {
                        if crate::image::FileIdentity::read(path)? != *identity {
                            return Err("A series source changed after metadata discovery.".into());
                        }
                    }
                    let mut image = Image::prepare(source, &options)?;
                    image.orient(&self.settings.transformations, &self.control)?;
                    if image.frames != *frames
                        || image.shape != *shape
                        || image.source_fingerprint()? != *fingerprint
                    {
                        return Err("A series source changed after metadata discovery.".into());
                    }

                    let mut bulk_options = self.integration_options();
                    if bulk_options.automatic_bins {
                        bulk_options.bins = self.settings.geometry.automatic_bins(image.shape);
                    }
                    let static_mask = {
                        self.settings.geometry.sync_shape(image.shape)?;
                        let matching = self.image.as_ref().is_some_and(|i| {
                            i.path == image.path && i.shape == image.shape && !i.values.is_empty()
                        });
                        if self
                            .settings
                            .geometry
                            .detector
                            .as_ref()
                            .is_some_and(|d| d.name.starts_with("Eiger"))
                            && !matching
                            && !self.engine.load_pixels(&mut image, 0, &self.control)?
                        {
                            image.read(0)?;
                        }
                        let basis = if matching {
                            self.image.as_ref()
                        } else {
                            Some(&image)
                        };
                        let mut mask = if self.settings.use_mask
                            && self.mask.len() == image.shape[0] * image.shape[1]
                        {
                            self.mask.as_ref().clone()
                        } else {
                            vec![0; image.shape[0] * image.shape[1]]
                        };
                        if let Some(built) = self.physical_mask_for(image.shape, basis)? {
                            for (value, detector) in mask.iter_mut().zip(built.iter()) {
                                *value |= *detector;
                            }
                        }
                        if let Some([r0, r1, c0, c1]) = self.settings.roi {
                            for r in 0..image.shape[0] {
                                for c in 0..image.shape[1] {
                                    if r < r0 || r >= r1 || c < c0 || c >= c1 {
                                        mask[r * image.shape[1] + c] = 1;
                                    }
                                }
                            }
                        }
                        // A dark first exposure cannot establish acquisition
                        // margins; use per-frame refresh until evidence exists.
                        if self.detector_mask.borrow().as_ref().is_some_and(|entry| {
                            entry.probe_frame.is_some()
                                && self
                                    .settings
                                    .geometry
                                    .detector
                                    .as_ref()
                                    .is_some_and(|d| std::sync::Arc::ptr_eq(d, &entry.detector))
                        }) {
                            None
                        } else {
                            Some(mask)
                        }
                    };
                    let combined_plan = if let Some(mask) = static_mask
                        .as_ref()
                        .filter(|_| image.single_dataset_series() && !self.processing.active())
                    {
                        self.engine.prepare_combined_series(
                            &mut image,
                            0,
                            &self.settings.geometry,
                            mask,
                            &bulk_options,
                            &self.control,
                        )?
                    } else {
                        None
                    };

                    let selected_frames: Vec<_> = (0..image.frames)
                        .filter(|&frame| {
                            let index = global + frame;
                            index >= start && index < stop && (index - start).is_multiple_of(step)
                        })
                        .collect();
                    global += image.frames;
                    if std::env::var("DIOPTAS_SERIES_PARALLEL").as_deref() != Ok("0")
                        && !selected_frames.is_empty()
                        && image.single_dataset_series()
                        && (self.processing.active()
                            || bulk_options.dynamic_mask
                            || bulk_options.pyfai)
                        && let Some(base_mask) = static_mask.as_ref()
                        && let Some(plan) = self.engine.prepare_processed_series(
                            &image,
                            &self.settings.geometry,
                            base_mask,
                            &bulk_options,
                            self.processing.active(),
                        )?
                    {
                        rows.publish_progress(&self.control);
                        let processing = self
                            .processing
                            .active()
                            .then(|| {
                                self.processing.series_snapshot(
                                    &image,
                                    &self.settings.geometry,
                                    &self.control,
                                )
                            })
                            .transpose()?;
                        let plugins = if bulk_options.dynamic_mask {
                            self.plugins.series_snapshot(
                                &self.settings.geometry,
                                image.shape,
                                &self.mask,
                            )?
                        } else {
                            Plugins::default()
                        };
                        let frame_context = crate::integration::SeriesFrameContext {
                            processing,
                            plugins,
                            user_mask: self.mask.clone(),
                            base_mask: Arc::new(base_mask.clone()),
                        };
                        let context = RowContext {
                            control: &self.control,
                            settings: &self.settings,
                            scan: self.scan.as_ref(),
                            patterns: &self.patterns,
                        };
                        self.engine.parallel_processed_series(
                            &image,
                            &selected_frames,
                            &plan,
                            &frame_context,
                            &self.control,
                            |frame, pattern| rows.push(&context, &image.path, frame, &pattern),
                        )?;
                        continue;
                    }
                    if let Some(plan) = combined_plan.as_ref().filter(|_| {
                        std::env::var("DIOPTAS_SERIES_PARALLEL").as_deref() != Ok("0")
                            && !selected_frames.is_empty()
                    }) {
                        let context = RowContext {
                            control: &self.control,
                            settings: &self.settings,
                            scan: self.scan.as_ref(),
                            patterns: &self.patterns,
                        };
                        self.engine.parallel_series_patterns(
                            &image,
                            &selected_frames,
                            plan,
                            &self.control,
                            |frame, pattern| rows.push(&context, &image.path, frame, &pattern),
                        )?;
                        continue;
                    }
                    for frame in selected_frames {
                        self.control.check()?;
                        rows.publish_progress(&self.control);
                        let direct = if let Some(plan) = &combined_plan {
                            Some(self.engine.combined_series_pattern(
                                &mut image,
                                frame,
                                plan,
                                &self.control,
                            )?)
                        } else {
                            None
                        };
                        let pattern = if let Some(pattern) = direct {
                            pattern
                        } else {
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
                            if prepared.is_none()
                                && (image.frame != frame || image.values.is_empty())
                                && !self.engine.load_pixels(&mut image, frame, &self.control)?
                            {
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
                            let (mut pattern, sigma) =
                                self.engine.integrate_pattern_with_variance(
                                    &self.scientific_values(),
                                    self.scientific_variance().as_deref().map(|v| v.as_slice()),
                                    image.shape,
                                    &self.settings.geometry,
                                    &mask,
                                    &options,
                                    prepared,
                                )?;
                            pattern["sigma"] = json!(sigma);
                            pattern
                        };
                        rows.push(
                            &RowContext {
                                control: &self.control,
                                settings: &self.settings,
                                scan: self.scan.as_ref(),
                                patterns: &self.patterns,
                            },
                            &image.path,
                            frame,
                            &pattern,
                        )?;
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
                    rows.x.ok_or("No frames were integrated.")?.as_ref().clone(),
                    rows.data,
                    self.settings.unit.clone(),
                    Some(self.settings.geometry.wavelength),
                    rows.entries,
                    images
                        .iter()
                        .map(|(p, _, _, _)| p.to_string_lossy().into_owned())
                        .collect(),
                    total,
                )?;
                series.file_counts = images.iter().map(|(_, frames, _, _)| *frames).collect();
                series.sigma = rows.sigma.map(Arc::new);
                series.raw_sigma = series.sigma.clone();
                series.spread = rows.spread.map(Arc::new);
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
            reply.buffers.push(b.background_raster().buffer.clone());
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
        self.select_series_mode(series, index, defer, stored, stored_unit, false)
    }
    pub(super) fn select_series_mode(
        &mut self,
        series: &Series,
        index: usize,
        defer: bool,
        stored: bool,
        stored_unit: Option<&str>,
        pattern_only: bool,
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
            args["pattern_only"] = json!(pattern_only);
            let auto = self.settings.auto_save;
            self.settings.auto_save = false;
            // The outer selection publishes the completed state. Building an
            // intermediate open-image reply duplicates metadata and ring paths.
            let loaded = self.open_image_model(&args, defer).and_then(|reply| {
                if reply.is_some() { Err("Detector dimensions changed; open this image manually to reset calibration.".into()) }
                else { Ok(()) }
            });
            if loaded.is_ok() {
                self.revision += 1;
            }
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
        let mut reply = self.snapshot_products(self.image.is_some(), !pattern_only);
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
                    self.batch = Some(Series::load_processed(Path::new(&paths[0]))?);
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
                self.batch = Some(Series::load_processed(path(args)?)?);
                self.batch.as_mut().unwrap().selected = 0;
                let b = self.batch.as_ref().unwrap().clone();
                let mut reply = self.select_series(&b, 0, false, true, None)?;
                self.attach_batch(&mut reply);
                reply.result["batchOpened"] = json!(true);
                return Ok(Some(reply));
            }
            "batch_waterfall" => {
                check_keys(args, &["series", "bins", "rows", "step"])?;
                let series = self.batch.as_ref().ok_or("Load a Batch series first.")?;
                let curves = crate::batch_waterfall::extract(
                    series,
                    args,
                    &self.patterns.unit,
                    &self.control,
                )?;
                self.patterns.replace_batch_waterfall(curves)?;
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
                reply.result["batchWaterfallCreated"] = json!(true);
                return Ok(Some(reply));
            }
            "batch_snapshot" => {
                let mut reply = Reply::metadata(json!({"ok":true}));
                self.attach_batch(&mut reply);
                return Ok(Some(reply));
            }
            "integration_save_batch" => {
                return self.save_batch_export(args).map(Some);
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
                let converted;
                let args = if args.get("minimum").is_some() || args.get("maximum").is_some() {
                    converted = super::batch_background_commands::normalization_bins(b, args)?;
                    &converted
                } else {
                    args
                };
                let zero = action == "batch_normalization_settings";
                let start = args.get("start").map_or(
                    Ok(if zero {
                        b.normalization[0]
                    } else {
                        b.normalization[0] + 1
                    }),
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
                        b.normalization[1]
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
                let reference = args.get("reference").map_or(
                    Ok(if zero { b.reference } else { b.reference + 1 }),
                    |v| {
                        integer(
                            v,
                            "Reference frame",
                            if zero { 0 } else { 1 },
                            b.count() - usize::from(zero),
                        )
                    },
                )? - usize::from(!zero);
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
            "batch_background_settings"
            | "batch_background_extract"
            | "batch_background_display" => {
                return self.batch_background_command(action, args).map(Some);
            }
            "batch_levels" => {
                let b = self.batch.as_ref().ok_or("Load a series first.")?;
                return Ok(Some(Reply::metadata(
                    json!({"ok":true,"batchLevels":series_levels(b.background_data(),[b.count(),b.background_bins()[1]-b.background_bins()[0]],args)?}),
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

#[cfg(all(test, feature = "dioptrin"))]
mod map_progress_tests {
    use super::*;
    use crate::{
        pattern::{Curve, Patterns},
        scan::Scan,
        series::{Entry, Series},
    };
    use std::sync::Arc;
    #[test]
    fn incremental_map_matches_finished_layers_and_keeps_unfinished_cells_blank() {
        let x: Vec<_> = (0..32).map(|i| i as f64).collect();
        let patterns = Patterns::default();
        for kind in crate::map_math::REDUCTIONS {
            for background in [false, true] {
                for expression in [false, true] {
                    let data: Vec<_> = (0..12)
                        .flat_map(|frame| {
                            (0..32).map(move |bin| {
                                let t = (bin as f64 - 15.) / 4.;
                                100. + 3. * bin as f64 + (frame + 1) as f64 * 100. * (-t * t).exp()
                            })
                        })
                        .collect();
                    let series = Series::new(
                        x.clone(),
                        data,
                        "q_A^-1".into(),
                        Some(4e-11),
                        (0..12)
                            .map(|frame| Entry {
                                path: "scan.h5".into(),
                                frame,
                            })
                            .collect(),
                        vec!["scan.h5".into()],
                        12,
                    )
                    .unwrap();
                    let mut old = Scan::new(series.clone(), &patterns).unwrap();
                    old.rois[0].min = 6.5;
                    old.rois[0].max = 24.5;
                    old.rois[0].reduction = kind.into();
                    old.rois[0].background = background;
                    if expression {
                        old.expressions = vec![("Contrast".into(), "A*2+3".into())];
                        old.active = "Contrast".into();
                    }
                    old.rebuild(true, &patterns).unwrap();
                    let mut preview =
                        MapProgress::new(&x, 12, "q_A^-1", 4e-11, Some(&old)).unwrap();
                    let control = crate::control::Control::default();
                    control.publish(json!({"running":true,"current":0,"total":12}));
                    for frame in 0..12 {
                        let curve = Curve {
                            x: Arc::new(x.clone()),
                            y: Arc::new(series.data[frame * 32..(frame + 1) * 32].to_vec()),
                            sigma: None,
                            spread: None,
                        };
                        preview
                            .push(frame, &curve, "q_A^-1", &control, &patterns)
                            .unwrap();
                        if frame == 0 {
                            let r = control.progress_reply();
                            let values: Vec<_> = r.buffers[0]
                                .bytes
                                .as_chunks::<4>()
                                .0
                                .iter()
                                .map(|b| f32::from_le_bytes(*b))
                                .collect();
                            assert_eq!(values.iter().filter(|v| v.is_finite()).count(), 1);
                            assert_eq!(r.result["progress"]["mapPreview"]["completed"], 1);
                            assert_eq!(r.result["progress"]["mapPreview"]["active"], old.active);
                        }
                    }
                    let finished = Scan::new_with_analysis(series, &patterns, Some(&old)).unwrap();
                    assert_eq!(
                        control.progress_reply().buffers[0].bytes,
                        finished.raster.buffer.bytes,
                        "{kind}, background={background}, expression={expression}"
                    );
                    control.finish();
                    assert!(control.progress_reply().buffers.is_empty());
                    assert!(
                        control.progress_reply().result["progress"]
                            .get("mapPreview")
                            .is_none()
                    );
                }
            }
        }
    }
}
