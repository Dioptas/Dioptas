use super::*;
use phasesmith_crystallography::UnitCell;
use rayon::prelude::*;
use std::sync::{
    Mutex,
    atomic::{AtomicUsize, Ordering},
};
fn length(v: V3) -> f64 {
    fft::dot(v, v).sqrt()
}
fn cross(a: V3, b: V3) -> V3 {
    [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]
}
pub(super) fn det(b: M3) -> f64 {
    fft::dot(b[0], cross(b[1], b[2]))
}
pub(super) fn parameters(b: M3) -> [f64; 6] {
    let l = b.map(length);
    let angle = |i: usize, j: usize| {
        (fft::dot(b[i], b[j]) / (l[i] * l[j]))
            .clamp(-1., 1.)
            .acos()
            .to_degrees()
    };
    [l[0], l[1], l[2], angle(1, 2), angle(0, 2), angle(0, 1)]
}
fn image<'a>(
    data: &'a [f64],
    mask: &'a [bool],
    variance: Option<&'a [f64]>,
    shape: [usize; 2],
    c: &Config,
) -> spots::Image<'a> {
    spots::Image {
        values: data,
        height: shape[0],
        width: shape[1],
        mask,
        variance,
        gain: c.gain,
        read_noise: c.read_noise,
        saturation: Some(c.saturation),
    }
}
impl Crystal {
    pub(super) fn process(
        &mut self,
        stage: usize,
        control: &Control,
        automatic: bool,
    ) -> Result<String, String> {
        control.check()?;
        if self.config.integration_method == "profile" && stage <= 5 {
            return self.profile_run(control, stage);
        }
        match stage {
            0 => self.background(control),
            1 => self.detect(control),
            2 => self.cells(control, automatic),
            3 => self.refine_lattices(),
            4 => self.refine_pose(control),
            5 => self.integrate(control),
            6 => self.scale(control),
            7 => self.solve(control),
            _ => unreachable!(),
        }
    }
    fn background(&mut self, control: &Control) -> Result<String, String> {
        self.prepare_shadows(control)?;
        self.prepare_diamonds(control)?;
        // Persistent pixels are otherwise made only by a settings reply; a
        // run straight after an edit (frames, rectangles) needs them too.
        if self.independent_masks() && self.config.persistent_on() {
            self.ensure_persistent(control, true)?;
            self.activate_masks();
        }
        self.notice = self.dac_warning();
        if !self.config.background {
            self.background = None;
            return Ok(self.mask_summary());
        }
        let nf = self.sources.len();
        let pixels = self.shape[0] * self.shape[1];
        let size = pixels
            .checked_mul(nf)
            .and_then(|v| v.checked_mul(8))
            .ok_or("Scan scratch size overflow.")?;
        if size > SCRATCH_BYTES / 2 {
            return Err("Omega background needs two scratch arrays and this scan exceeds the 16 GiB scratch limit. Disable omega background or load fewer frames; original-count local-background integration remains available.".into());
        }
        let mut raw = tempfile::tempfile().map_err(err)?;
        let baseline = tempfile::NamedTempFile::new().map_err(err)?;
        baseline.as_file().set_len(size as u64).map_err(err)?;
        for i in 0..nf {
            control.check()?;
            let data = self.read(i)?;
            let bytes: Vec<u8> = data.iter().flat_map(|v| v.to_le_bytes()).collect();
            raw.write_all(&bytes).map_err(err)?;
            control.publish(json!({"running":true,"current":i+1,"total":nf,"label":"Reading original counts for omega background"}));
        }
        let engine = spots::omega_background::Engine::new(2)?;
        let tile = (2_000_000 / nf).clamp(1, 4096);
        let mut out = baseline.reopen().map_err(err)?;
        let mut converged = 0;
        let mut fitted = 0;
        for first in (0..pixels).step_by(tile) {
            control.check()?;
            let count = tile.min(pixels - first);
            let mut data = vec![0.; count * nf];
            let mut mask = vec![false; count * nf];
            let mut bytes = vec![0u8; count * 8];
            for frame in 0..nf {
                raw.seek(SeekFrom::Start(((frame * pixels + first) * 8) as u64))
                    .map_err(err)?;
                raw.read_exact(&mut bytes).map_err(err)?;
                for (j, b) in bytes.as_chunks::<8>().0.iter().enumerate() {
                    let v = f64::from_le_bytes(*b);
                    let k = j * nf + frame;
                    let pixel = first + j;
                    let (x, y) = (pixel % self.shape[1], pixel / self.shape[1]);
                    data[k] = v;
                    mask[k] = self
                        .shadows
                        .as_ref()
                        .is_some_and(|s| s.excluded(frame, pixel, self.shape[1]))
                        || self.excluded_frames.contains(&frame)
                        || !v.is_finite()
                        || v < 0.
                        || v >= self.config.saturation
                        || self
                            .mask
                            .iter()
                            .any(|&[x0, y0, x1, y1]| x >= x0 && x < x1 && y >= y0 && y < y1);
                }
            }
            let fit = engine.baselines(
                &data,
                nf,
                Some(&mask),
                spots::omega_background::Parameters {
                    smoothness: self.config.smoothness,
                    tolerance: 0.01,
                    max_iterations: 30,
                },
                3,
            )?;
            converged += fit.converged.iter().filter(|&&c| c).count();
            fitted += fit
                .baseline
                .chunks_exact(nf)
                .filter(|row| row.iter().any(|v| v.is_finite()))
                .count();
            for frame in 0..nf {
                out.seek(SeekFrom::Start(((frame * pixels + first) * 8) as u64))
                    .map_err(err)?;
                bytes.clear();
                for j in 0..count {
                    bytes.extend_from_slice(&fit.baseline[j * nf + frame].to_le_bytes());
                }
                out.write_all(&bytes).map_err(err)?;
            }
            control.publish(json!({"running":true,"current":first+count,"total":pixels,"label":"Fitting omega background · positions only"}));
        }
        self.background = Some(Arc::new(baseline));
        Ok(format!(
            "arPLS: {converged}/{fitted} fitted pixels converged. Positions only; intensities retain original counts."
        ))
    }
    fn detect(&mut self, control: &Control) -> Result<String, String> {
        let n = self.sources.len();
        // The observations depend on fewer settings than the tracks: a Link
        // radius change links the kept observations again, and a Minimum
        // area change measures the kept components again.
        let key = self.detection_key();
        let min_pixels = self.config.min_pixels;
        let kept = self.detections.clone().filter(|d| d.key == key);
        let observed = match kept {
            Some(d) if d.min_pixels == min_pixels => d.peaks.clone(),
            kept => {
                let cached = kept.and_then(|d| d.components.clone());
                let (peaks, found) = self.observe(control, cached.as_deref().map(Vec::as_slice))?;
                let peaks = Arc::new(peaks);
                self.detections = Some(Arc::new(Detections {
                    key,
                    components: cached.or_else(|| found.map(Arc::new)),
                    min_pixels,
                    peaks: peaks.clone(),
                }));
                peaks
            }
        };
        let mut peaks: Vec<Peak> = observed.as_ref().clone();
        if peaks.len() < 12 {
            return Err(format!(
                "Only {} peaks found; at least 12 are required. Lower the threshold, check background and masks, or verify the scan.",
                peaks.len()
            ));
        }
        let frames: Vec<_> = peaks.iter().map(|p| p.frame as u32).collect();
        let xy: Vec<_> = peaks.iter().map(|p| p.xy).collect();
        let segments = vec![0u32; n];
        let ids =
            spots::rotation::link(&frames, &xy, &segments, self.config.link_radius, 20_000_000)
                .map_err(err)?;
        let mut groups: BTreeMap<usize, Vec<usize>> = BTreeMap::new();
        for (i, id) in ids.into_iter().enumerate() {
            peaks[i].track = id as usize;
            groups.entry(id as usize).or_default().push(i);
        }
        let mut tracks = Vec::new();
        for (_id, rows) in groups {
            let samples: Vec<_> = rows
                .iter()
                .map(|&i| {
                    [
                        peaks[i].xy[0],
                        peaks[i].xy[1],
                        self.config.omega_start
                            + (peaks[i].frame as f64) * self.config.omega_step
                            + self.config.exposure / 2.,
                        peaks[i].intensity.max(1e-9),
                    ]
                })
                .collect();
            let summary = spots::rotation::summarize(&samples).map_err(err)?;
            let first = peaks[rows[0]].frame;
            let last = peaks[*rows.last().unwrap()].frame;
            let mut bounds = [usize::MAX, usize::MAX, 0, 0];
            let mut flags = 0;
            let id = tracks.len();
            for i in rows {
                peaks[i].track = id;
                let b = peaks[i].bounds;
                bounds = [
                    bounds[0].min(b[0]),
                    bounds[1].min(b[1]),
                    bounds[2].max(b[2]),
                    bounds[3].max(b[3]),
                ];
                flags |= peaks[i].flags;
            }
            if first == 0
                || last == n - 1
                || self
                    .excluded_frames
                    .iter()
                    .any(|&i| i + 1 == first || i == last + 1)
            {
                flags |= 1024;
            }
            tracks.push(Track {
                native: false,
                observed: [summary[0], summary[1], summary[2]],
                first,
                last,
                bounds,
                flags,
                excluded: false,
            });
        }
        let description = format!(
            "{} observations linked into {} tracks. Flagged tracks are retained for inspection.",
            peaks.len(),
            tracks.len()
        );
        self.peaks = peaks;
        self.tracks = tracks;
        Ok(description)
    }
    /// What Find spots observations depend on, besides the frames' counts.
    fn detection_key(&self) -> DetectionKey {
        let c = &self.config;
        DetectionKey {
            settings: [c.threshold, c.gain, c.read_noise, c.saturation],
            shape: self.shape,
            sources: self
                .sources
                .iter()
                .map(|s| (s.path.clone(), s.frame, s.digest.clone()))
                .collect(),
            excluded: self.excluded_frames.clone(),
            mask: self.mask.clone(),
            shadows: self.shadows.clone(),
            diamonds: self.diamonds.clone(),
            shared: self.shared.clone(),
            persistent: self.persistent.clone(),
            background: self.background.clone(),
        }
    }
    /// Spots of every frame that is not excluded, in frame order (not linked),
    /// and the components they were measured from, per frame. With
    /// `cached` components (of the same frames, detection settings and
    /// masks) only the measurement runs; it equals a fresh detection.
    /// Components are not returned when they would take more than
    /// [`COMPONENTS_KEPT`] entries.
    fn observe(
        &self,
        control: &Control,
        cached: Option<&[Vec<spots::Component>]>,
    ) -> Result<(Vec<Peak>, Option<FrameComponents>), String> {
        let options = spots::Options {
            threshold_sigma: self.config.threshold,
            min_pixels: self.config.min_pixels,
            ..Default::default()
        };
        let n = self.sources.len();
        let frames: Vec<usize> = (0..n)
            .filter(|frame| !self.excluded_frames.contains(frame))
            .collect();
        let (done, total) = (AtomicUsize::new(0), AtomicUsize::new(0));
        // Live view: the shown frame as soon as it is done; then at most one
        // worker at a time renders the frame it just finished, a few times
        // per second and never stepping backwards.
        let shown: Mutex<(Option<std::time::Instant>, usize)> = Mutex::new((None, 0));
        let found_components = AtomicUsize::new(0);
        // Frame position i among `frames`.
        let one = |i: usize, first: bool| -> Result<(Vec<Peak>, Vec<spots::Component>), String> {
            let frame = frames[i];
            control.check()?;
            let raw = self.read(frame)?;
            let mut mask = self.mask_for(&raw, frame);
            // Count variance of the original counts. Without a background
            // the counts are the values, and the detector's own default
            // (the same expression) saves a frame-sized array per worker.
            let baseline = self.baseline(frame)?;
            let variance: Option<Vec<_>> = baseline.as_ref().map(|_| {
                raw.iter()
                    .map(|v| {
                        (v.max(0.) / self.config.gain + self.config.read_noise.powi(2)).max(1.)
                    })
                    .collect()
            });
            let mut values = raw;
            if let Some(bg) = baseline {
                for ((v, m), b) in values.iter_mut().zip(&mut mask).zip(bg) {
                    if !b.is_finite() {
                        *m = true;
                    } else {
                        *v -= b;
                    }
                }
            }
            let image = image(
                &values,
                &mask,
                variance.as_deref(),
                self.shape,
                &self.config,
            );
            // `detect` is exactly these two steps.
            let (measured, components) = match cached {
                Some(c) => (
                    spots::measure_components(&image, &c[i], options),
                    Vec::new(),
                ),
                None => {
                    let found = spots::detect_components(&image, options).map_err(err)?;
                    let n =
                        found_components.fetch_add(found.len(), Ordering::Relaxed) + found.len();
                    let measured = spots::measure_components(&image, &found, options);
                    (
                        measured,
                        if n <= COMPONENTS_KEPT {
                            found
                        } else {
                            Vec::new()
                        },
                    )
                }
            };
            let peaks: Vec<Peak> = measured
                .map_err(err)?
                .spots
                .into_iter()
                .filter(|s| s.values[..2].iter().all(|v| v.is_finite()))
                .map(|s| Peak {
                    frame,
                    xy: [s.values[0], s.values[1]],
                    intensity: s.values[2].max(0.),
                    flags: s.flags,
                    bounds: [s.bounds.x0, s.bounds.y0, s.bounds.x1, s.bounds.y1],
                    track: 0,
                })
                .collect();
            let all = total.fetch_add(peaks.len(), Ordering::Relaxed) + peaks.len();
            if all > 200000 {
                return Err("More than 200,000 spot observations: raise the threshold or mask powder/diamond regions.".into());
            }
            let current = done.fetch_add(1, Ordering::Relaxed) + 1;
            let lock = if first {
                shown.lock().ok()
            } else {
                shown.try_lock().ok()
            };
            if let Some(mut shown) = lock
                && (first
                    || frame >= shown.1 && shown.0.is_none_or(|t| t.elapsed().as_millis() >= 200))
            {
                for (v, m) in values.iter_mut().zip(&mask) {
                    if *m {
                        *v = f64::NAN;
                    }
                }
                let raster = Raster::image(&values, self.shape);
                control.publish_preview(
                    "scxrdPreview",
                    json!({"raster":raster.metadata,"frame":frame,"spots":all,
                        "peaks":peaks.iter().map(|p|json!({"x":p.xy[0],"y":p.xy[1],"flags":p.flags})).collect::<Vec<_>>()}),
                    raster.buffer,
                );
                *shown = (Some(std::time::Instant::now()), frame);
            }
            control.publish(json!({"running":true,"current":current,"total":frames.len(),"label":"Finding spots"}));
            Ok((peaks, components))
        };
        // The shown frame first, so its spots appear at once; the other
        // frames run in parallel meanwhile. Frames are independent and the
        // results keep frame order, so the outcome is that of a sequential
        // search.
        let first = frames.iter().position(|&f| f == self.frame);
        let rest = |skip: Option<usize>| {
            frames
                .par_iter()
                .enumerate()
                .filter(|&(i, _)| Some(i) != skip)
                .map(|(i, _)| one(i, false))
                .collect::<Result<Vec<_>, String>>()
        };
        type Found = Vec<(Vec<Peak>, Vec<spots::Component>)>;
        let found = crate::worker_pool::install(|| -> Result<Found, String> {
            match first {
                Some(i) => {
                    let (shown, others) = rayon::join(|| one(i, true), || rest(Some(i)));
                    let (shown, mut others) = (shown?, others?);
                    others.insert(i, shown);
                    Ok(others)
                }
                None => rest(None),
            }
        })?;
        let (peaks, components): (Vec<_>, Vec<_>) = found.into_iter().unzip();
        let kept = cached.is_none() && found_components.load(Ordering::Relaxed) <= COMPONENTS_KEPT;
        Ok((
            peaks.into_iter().flatten().collect(),
            kept.then_some(components),
        ))
    }
    /// Reciprocal positions of the usable tracks. For lattice finding
    /// (`positions`) a masked pixel in the aperture does not matter: it biases
    /// the intensity, not the position, so those tracks take part. Geometry
    /// refinement keeps to fully unflagged tracks.
    pub(super) fn cloud(&self, positions: bool) -> Result<(Vec<usize>, Vec<V3>), String> {
        let allowed = if positions { spots::MASKED } else { 0 };
        let mut g = self
            .geometry
            .ok_or("Load a PONI calibration in Frames before cell finding.")?
            .native();
        g.axis = self.config.axis;
        let available: Vec<_> = self
            .tracks
            .iter()
            .enumerate()
            .filter(|(_, t)| !t.excluded && t.flags & !allowed == 0)
            .map(|(i, _)| i)
            .collect();
        let ids: Vec<_> = available
            .iter()
            .step_by(available.len().div_ceil(10000).max(1))
            .copied()
            .collect();
        let xyz: Vec<_> = ids.iter().map(|&i| self.tracks[i].observed).collect();
        let q = g.convert(&xyz).map_err(err)?;
        if q.len() < 25 {
            return Err(format!(
                "{} unflagged tracks; at least 25 are required for independent cell validation. Inspect masks, threshold and scan coverage.",
                q.len()
            ));
        }
        Ok((ids, q))
    }
    fn cells(&mut self, control: &Control, _automatic: bool) -> Result<String, String> {
        if self.cells.is_empty() {
            let (_, q) = self.cloud(true)?;
            self.cells = lattices::find(&q, &self.config, control)?;
            let retired = std::mem::take(&mut self.retired);
            if !carry_ticks(&retired, &mut self.cells) {
                pretick(&mut self.cells);
            }
            self.selected = None;
        }
        if self.cells.is_empty() {
            return Err("No lattice passed independent withheld-position gates. Check geometry, spindle axis and omega sign, lower the peak threshold, or exclude diamond/powder regions.".into());
        }
        self.selected = self.cells.iter().position(|c| c.kept);
        let Some(first) = self.selected else {
            return Err(format!(
                "{} found; none explains a clear share of the spots. Tick the lattices to keep.",
                lattice_count(self.cells.len())
            ));
        };
        let kept = self.cells.iter().filter(|c| c.kept).count();
        let cell = &self.cells[first];
        Ok(format!(
            "{} found, {kept} kept. First kept: {}/{} tracks indexed; withheld reciprocal RMS {:.5} Å⁻¹.",
            lattice_count(self.cells.len()),
            cell.indexed,
            cell.total,
            cell.rms
        ))
    }
    /// Lattice owning each track (1-based; 0 none or ambiguous), as Find
    /// lattices assigns spots: nearest node within tolerance, clearly nearer
    /// than any other lattice's.
    pub(super) fn lattice_owners(&self, tracks: &[usize]) -> Vec<usize> {
        let none = vec![0; tracks.len()];
        let Some(geometry) = self.geometry.filter(|_| !self.cells.is_empty()) else {
            return none;
        };
        let mut g = geometry.native();
        g.axis = self.config.axis;
        let xyz: Vec<_> = tracks
            .iter()
            .map(|&t| self.tracks.get(t).map_or([0.; 3], |t| t.observed))
            .collect();
        match g.convert(&xyz) {
            Ok(q) => self.owners(&q),
            Err(_) => none,
        }
    }
    /// Lattice owning each reciprocal position (1-based; 0 none or
    /// ambiguous); see [`Self::lattice_owners`].
    pub(super) fn owners(&self, q: &[V3]) -> Vec<usize> {
        let models: Vec<(M3, M3)> = self
            .cells
            .iter()
            .filter_map(|c| Some((c.direct, fft::inverse_transpose(c.direct).ok()?)))
            .collect();
        if models.is_empty() || models.len() != self.cells.len() {
            return vec![0; q.len()];
        }
        q.iter()
            .map(|&p| {
                let (mut best, mut second, mut owner) = (f64::INFINITY, f64::INFINITY, 0);
                for (i, &(a, b)) in models.iter().enumerate() {
                    let (h, d) = fft::indexed(p, a, b);
                    let d = if h == [0.; 3] { f64::INFINITY } else { d };
                    if d < best {
                        (second, best, owner) = (best, d, i + 1);
                    } else if d < second {
                        second = d;
                    }
                }
                if best < self.config.tolerance && best <= lattices::AMBIGUITY * second {
                    owner
                } else {
                    0
                }
            })
            .collect()
    }
    fn solve(&mut self, control: &Control) -> Result<String, String> {
        let elements: Vec<_> = self
            .config
            .elements
            .split(|c: char| c == ',' || c.is_whitespace())
            .filter(|s| !s.is_empty())
            .map(str::to_owned)
            .collect();
        if elements.is_empty() {
            return Err("Enter the element symbols and explicitly supplied space group to search for structure candidates, or export the integrated reflections.".into());
        }
        let cell = self.cell()?;
        let group = phasesmith_io::space_group_by_number(i32::from(self.config.group))
            .map_err(err)?
            .space_group;
        let observations: Vec<_> = self
            .reflections
            .iter()
            .filter(|r| r.usable())
            .map(|r| solution::Observation {
                hkl: r.hkl.map(|v| v as i32),
                intensity: r.intensity,
                sigma: r.sigma,
            })
            .collect();
        let token = solution::Cancellation::default();
        let finished = Arc::new(std::sync::atomic::AtomicBool::new(false));
        let options = solution::SolveOptions {
            seed: 0,
            trials: 4,
            cycles: 800,
            phasing: solution::PhasingMethod::DualSpace,
            refinement: Some(if self.config.adp == "anisotropic" {
                solution::AdpMode::Anisotropic
            } else {
                solution::AdpMode::Isotropic
            }),
            max_seconds: self.config.search_seconds,
            cancellation: Some(token.clone()),
            completion: false,
            ..Default::default()
        };
        let native_options = if self.config.integration_method == "profile" {
            let mut o = (**self
                .profile_options
                .as_ref()
                .ok_or("Run native protocol Intensities before searching.")?)
            .clone();
            let shadows = self
                .shadows
                .as_ref()
                .ok_or("Prepare native masks before search.")?;
            let effective = self.config.active_protocol(shadows.first, shadows.last)?;
            o.priors.elements = elements.clone();
            o.search_seconds = protocol::number(&effective, "search", "native_seconds")?;
            o.cancellation = token.clone();
            Some(o)
        } else {
            None
        };
        let actual_seed = native_options.as_ref().map_or(options.seed, |o| o.seed);
        let hard_deadline = if native_options.is_some() {
            let shadows = self.shadows.as_ref().ok_or("Prepare masks first.")?;
            let p = self.config.active_protocol(shadows.first, shadows.last)?;
            Some(
                std::time::Instant::now()
                    + std::time::Duration::from_secs_f64(protocol::number(
                        &p,
                        "search",
                        "hard_seconds",
                    )?),
            )
        } else {
            None
        };
        let result = std::thread::scope(|scope| {
            let done = finished.clone();
            scope.spawn(move || {
                while !done.load(std::sync::atomic::Ordering::Acquire) {
                    if control.check().is_err()
                        || hard_deadline
                            .is_some_and(|deadline| std::time::Instant::now() >= deadline)
                    {
                        let _ = token.cancel();
                        break;
                    }
                    std::thread::sleep(std::time::Duration::from_millis(20));
                }
            });
            let _completion = SearchCompletion(finished.clone());
            let result = if let Some(o) = &native_options {
                phasesmith_workflows::single_crystal::search_observations(&observations, o)
                    .map(|(result, _)| result)
                    .map_err(err)
            } else {
                solution::solve_elements(
                    &observations,
                    cell,
                    &group,
                    &elements,
                    &options,
                    &solution::SharedSearchOptions::default(),
                )
                .map_err(err)
            };
            finished.store(true, std::sync::atomic::Ordering::Release);
            result
        })
        .map_err(err)?;
        control.check()?;
        let best=result.candidates.first().ok_or("No structure candidate found within the declared budget; export observations or increase the search budget.")?;
        let (mode, parameters, termination) = best
            .refinement
            .as_ref()
            .map(|r| (r.mode.to_owned(), r.parameter_count, r.termination))
            .unwrap_or(("P1".into(), 0, "not refined"));
        self.structure = json!({"r1":best.r1,"mode":mode,"parameters":parameters,"termination":termination,"searchTermination":result.termination,"targetMet":result.target_met,"atoms":best.species.len(),"species":best.species,"xyz":best.fractional_xyz,"group":self.config.group,"observations":observations.len(),"families":result.data.family_count,"absentObservations":result.data.absent_observations,"seed":actual_seed,"engine":ENGINE});
        self.structure["elements"] = json!(elements);
        self.structure["searchSeconds"] = json!(self.config.search_seconds);
        if native_options.is_some() {
            let shadows = self
                .shadows
                .as_ref()
                .ok_or("Prepare native masks before search.")?;
            let effective = self.config.active_protocol(shadows.first, shadows.last)?;
            let identity = json!({"reductionIdentity":self.profile_report["runIdentitySha256"],"effectiveProtocol":effective,"elements":elements,"seed":actual_seed});
            self.structure["effectiveProtocol"] = effective;
            self.structure["searchIdentitySha256"] = json!(format!(
                "{:x}",
                Sha256::digest(serde_json::to_vec(&identity).map_err(err)?)
            ));
        }

        let cp = [
            cell.a_angstrom,
            cell.b_angstrom,
            cell.c_angstrom,
            cell.alpha_deg,
            cell.beta_deg,
            cell.gamma_deg,
        ];
        let mut cif = format!(
            "data_dioptas_candidate\n# Candidate search; not a fully validated structure refinement\n_cell_length_a {}\n_cell_length_b {}\n_cell_length_c {}\n_cell_angle_alpha {}\n_cell_angle_beta {}\n_cell_angle_gamma {}\n_symmetry_space_group_name_H-M 'P 1'\nloop_\n_atom_site_label\n_atom_site_type_symbol\n_atom_site_fract_x\n_atom_site_fract_y\n_atom_site_fract_z\n_atom_site_U_iso_or_equiv\n",
            cp[0], cp[1], cp[2], cp[3], cp[4], cp[5]
        );
        for (i, (s, p)) in best.species.iter().zip(&best.fractional_xyz).enumerate() {
            cif.push_str(&format!(
                "{s}{} {s} {} {} {} {}\n",
                i + 1,
                p[0],
                p[1],
                p[2],
                best.refinement
                    .as_ref()
                    .and_then(|r| r.full_u_equiv.get(i).copied())
                    .unwrap_or(best.u_iso)
            ));
        }
        if self.config.integration_method == "profile"
            && let Some(refined) = &best.refinement
            && !refined.full_u_cif.is_empty()
        {
            cif.push_str("loop_\n_atom_site_aniso_label\n_atom_site_aniso_U_11\n_atom_site_aniso_U_22\n_atom_site_aniso_U_33\n_atom_site_aniso_U_23\n_atom_site_aniso_U_13\n_atom_site_aniso_U_12\n");
            for (i, (species, u)) in best.species.iter().zip(&refined.full_u_cif).enumerate() {
                cif.push_str(&format!(
                    "{species}{} {} {} {} {} {} {}\n",
                    i + 1,
                    u[0],
                    u[1],
                    u[2],
                    u[3],
                    u[4],
                    u[5]
                ));
            }
        }
        self.cif = Some(cif);
        Ok(format!(
            "Candidate R1 {:.3}% · {} ADPs · {parameters} parameters · {termination}. Candidate assessment only; lower R1 does not establish correctness.",
            best.r1 * 100.,
            mode
        ))
    }
    pub(super) fn cell(&self) -> Result<UnitCell, String> {
        let basis = self
            .basis
            .ok_or("Validate geometry before using cell metrics.")?;
        let p = parameters(fft::inverse_transpose(basis)?);
        {
            let c = UnitCell {
                a_angstrom: p[0],
                b_angstrom: p[1],
                c_angstrom: p[2],
                alpha_deg: p[3],
                beta_deg: p[4],
                gamma_deg: p[5],
            };
            c.geometry().map_err(err)?;
            Ok(c)
        }
    }
    /// Kept lattices changed: the following steps start again from the
    /// first kept one; Find lattices is done while one is kept.
    fn ticks_changed(&mut self) {
        self.invalidate(3);
        self.selected = self.cells.iter().position(|c| c.kept);
        let kept = self.cells.iter().filter(|c| c.kept).count();
        let stage = &mut self.stages[2];
        if kept == 0 {
            stage.status = "attention".into();
            stage.detail = "No lattice kept. Tick the lattices to keep.".into();
        } else {
            stage.status = "complete".into();
            stage.detail = format!(
                "{} found, {kept} kept by the user.",
                lattice_count(self.cells.len())
            );
        }
    }
    pub(super) fn edit(&mut self, args: &Value) -> Result<(), String> {
        match args["operation"].as_str() {
            Some("cell") => {
                // Keep exactly this lattice.
                let index = args["index"].as_u64().ok_or("Choose a cell candidate.")? as usize;
                if index >= self.cells.len() {
                    return Err("Cell candidate no longer exists.".into());
                }
                for (i, c) in self.cells.iter_mut().enumerate() {
                    c.kept = i == index;
                }
                self.ticks_changed();
            }
            Some("keep") => {
                let index = args["index"].as_u64().ok_or("Choose a lattice.")? as usize;
                let keep = args["keep"]
                    .as_bool()
                    .ok_or("Say whether to keep the lattice.")?;
                let cell = self
                    .cells
                    .get_mut(index)
                    .ok_or("Lattice no longer exists.")?;
                if cell.kept != keep {
                    cell.kept = keep;
                    self.ticks_changed();
                }
            }
            Some("symmetry") => {
                let lattice = args["index"].as_u64().ok_or("Choose a lattice.")? as usize;
                let choice = args["choice"]
                    .as_u64()
                    .ok_or("Choose a lattice type.")? as usize;
                self.choose_symmetry(lattice, choice)?;
            }
            Some("show") => {
                let index = args["index"].as_u64().map(|i| i as usize);
                if index.is_some_and(|i| i >= self.cells.len()) {
                    return Err("Lattice no longer exists.".into());
                }
                self.shown = index;
            }
            Some("track") => {
                let id = args["index"].as_u64().ok_or("Choose a track.")? as usize;
                if id >= self.tracks.len() {
                    return Err("Track no longer exists.".into());
                }
                self.tracks[id].excluded = !self.tracks[id].excluded;
                self.invalidate(2);
            }
            Some("frame") => {
                if self.config.integration_method == "profile" {
                    return Err("Edit the contiguous protocol first/last frame in Frames; individual frame toggles are available in exploratory summation.".into());
                }
                let id = args["index"].as_u64().ok_or("Choose a frame.")? as usize;
                if id >= self.sources.len() {
                    return Err("Frame no longer exists.".into());
                }
                if self.excluded_frames.contains(&id) {
                    self.excluded_frames.retain(|&x| x != id);
                } else {
                    self.excluded_frames.push(id);
                }
                self.invalidate(0);
                self.preview("raw")?;
            }
            Some("exclude_frames") => {
                // Frames to leave out of every step (the busy-frame notice's
                // action) or to take back. Prepare masks counts frames too
                // (persistent pixels), so everything is made again.
                if self.config.integration_method == "profile" {
                    return Err("Edit the contiguous protocol first/last frame in Frames; individual frame toggles are available in exploratory summation.".into());
                }
                let frames: Vec<usize> = serde_json::from_value(args["frames"].clone())
                    .map_err(|_| "Choose the frames to exclude.")?;
                let exclude = args["exclude"]
                    .as_bool()
                    .ok_or("Say whether to exclude the frames.")?;
                if frames.iter().any(|&f| f >= self.sources.len()) {
                    return Err("Frame no longer exists.".into());
                }
                let before = self.excluded_frames.clone();
                self.excluded_frames.retain(|f| !frames.contains(f));
                if exclude {
                    self.excluded_frames.extend(&frames);
                    self.excluded_frames.sort_unstable();
                    self.excluded_frames.dedup();
                }
                if self.excluded_frames != before {
                    self.invalidate(0);
                    self.preview("raw")?;
                }
            }
            Some("mask") => {
                let b: [usize; 4] = serde_json::from_value(args["bounds"].clone()).map_err(err)?;
                if b[0] >= b[2] || b[1] >= b[3] || b[2] > self.shape[1] || b[3] > self.shape[0] {
                    return Err("Mask rectangle must lie inside the detector.".into());
                }
                self.mask.push(b);
                self.invalidate(0);
                self.preview("raw")?;
            }
            Some("remove_mask") => {
                let i = args["index"].as_u64().ok_or("Choose a mask region.")? as usize;
                if i >= self.mask.len() {
                    return Err("Mask region no longer exists.".into());
                }
                self.mask.remove(i);
                self.invalidate(0);
                self.preview("raw")?;
            }
            Some("clear_mask") => {
                self.mask.clear();
                self.invalidate(0);
                self.preview("raw")?;
            }
            Some("rerun") => {
                let stage = args["index"]
                    .as_u64()
                    .filter(|v| *v < 8)
                    .ok_or("Choose a processing stage.")? as usize;
                self.invalidate(stage);
            }
            _ => return Err("Unknown workflow edit.".into()),
        }
        Ok(())
    }
}
impl Crystal {
    /// Frames with far more spots than the scan's typical frame (see
    /// [`unusual_frames`]), once Find spots is complete; excluded frames do
    /// not count.
    pub(super) fn busy_frames(&self) -> Vec<usize> {
        if self.stages[1].status != "complete" {
            return vec![];
        }
        let mut counts = vec![0usize; self.sources.len()];
        for p in &self.peaks {
            if let Some(n) = counts.get_mut(p.frame) {
                *n += 1;
            }
        }
        let frames: Vec<(usize, usize)> = counts
            .into_iter()
            .enumerate()
            .filter(|(f, _)| !self.excluded_frames.contains(f))
            .collect();
        unusual_frames(&frames)
    }
}
/// Fewest frames for a typical spot count.
pub(super) const BUSY_MIN_FRAMES: usize = 8;
/// A busy frame has more than this many times the median count ...
pub(super) const BUSY_FACTOR: f64 = 10.;
/// ... more than the median plus this many robust standard deviations ...
pub(super) const BUSY_SPREAD: f64 = 10.;
/// ... and at least this many spots.
pub(super) const BUSY_MIN_SPOTS: usize = 50;
/// Frames (`(frame, spots)`) whose spot count is far above the scan's
/// typical frame: more than `BUSY_FACTOR` × the median, more than the median
/// plus `BUSY_SPREAD` robust standard deviations (1.4826 × median absolute
/// deviation), and at least `BUSY_MIN_SPOTS`. Needs `BUSY_MIN_FRAMES` frames.
pub(super) fn unusual_frames(counts: &[(usize, usize)]) -> Vec<usize> {
    if counts.len() < BUSY_MIN_FRAMES {
        return vec![];
    }
    let median = |mut v: Vec<f64>| {
        v.sort_by(f64::total_cmp);
        let n = v.len();
        if n % 2 == 1 {
            v[n / 2]
        } else {
            (v[n / 2 - 1] + v[n / 2]) / 2.
        }
    };
    let m = median(counts.iter().map(|c| c.1 as f64).collect());
    let mad = 1.4826 * median(counts.iter().map(|c| (c.1 as f64 - m).abs()).collect());
    let limit = (BUSY_FACTOR * m)
        .max(m + BUSY_SPREAD * mad)
        .max(BUSY_MIN_SPOTS as f64);
    counts
        .iter()
        .filter(|c| c.1 as f64 > limit)
        .map(|c| c.0)
        .collect()
}
fn lattice_count(n: usize) -> String {
    format!("{n} lattice{}", if n == 1 { "" } else { "s" })
}
/// Share of all spots, and of the strongest lattice's spots, a lattice must
/// index to be ticked after a search; a diamond-like cell (the anvils) never is.
pub(super) const KEEP_SHARE_OF_ALL: f64 = 0.05;
pub(super) const KEEP_SHARE_OF_BEST: f64 = 0.1;
/// A rerun that finds the same lattices as before keeps the user's ticks.
/// Returns whether it did.
pub(super) fn carry_ticks(retired: &[Cell], cells: &mut [Cell]) -> bool {
    let same = !retired.is_empty()
        && retired.len() == cells.len()
        && retired
            .iter()
            .zip(cells.iter())
            .all(|(old, new)| lattices::related(old.direct, new.direct));
    if same {
        for (new, old) in cells.iter_mut().zip(retired) {
            new.kept = old.kept;
        }
    }
    same
}
/// Tick the lattices that explain a clear share of the spots. Weaker ones
/// (twins, supercells, few spots) stay listed, unticked.
pub(super) fn pretick(cells: &mut [Cell]) {
    let best = cells.iter().map(|c| c.indexed).max().unwrap_or(0) as f64;
    for c in cells {
        let n = c.indexed as f64;
        c.kept = n >= KEEP_SHARE_OF_ALL * c.total as f64
            && n >= KEEP_SHARE_OF_BEST * best
            && !diamond_like(c.parameters);
    }
}
/// Components per detected frame, in frame order.
type FrameComponents = Vec<Vec<spots::Component>>;
/// At most this many components (40 bytes each, so 80 MB) are kept for
/// Minimum area changes; a detection with more measures anew on such a change.
const COMPONENTS_KEPT: usize = 2_000_000;
/// Find spots observations before linking, the components they were
/// measured from and what they were found with.
pub(super) struct Detections {
    key: DetectionKey,
    /// Every component per detected frame, before the Minimum area rule;
    /// None when there were more than [`COMPONENTS_KEPT`].
    pub(super) components: Option<Arc<FrameComponents>>,
    min_pixels: usize,
    peaks: Arc<Vec<Peak>>,
}
/// Everything Find spots components depend on besides the counts: the
/// detection settings but Minimum area, the frames and the masks in use (by identity; the key
/// holds them, so an identical pointer is the same mask; the combined cell
/// shadows by content).
pub(super) struct DetectionKey {
    settings: [f64; 4],
    shape: [usize; 2],
    sources: Vec<(PathBuf, usize, Arc<OnceLock<String>>)>,
    excluded: Vec<usize>,
    mask: Vec<[usize; 4]>,
    shadows: Option<Arc<Shadows>>,
    diamonds: Option<Arc<Diamonds>>,
    shared: Option<Arc<masks::PixelRuns>>,
    persistent: Option<Arc<masks::PixelRuns>>,
    background: Option<Arc<tempfile::NamedTempFile>>,
}
impl PartialEq for DetectionKey {
    fn eq(&self, o: &Self) -> bool {
        fn same<T>(a: &Option<Arc<T>>, b: &Option<Arc<T>>) -> bool {
            match (a, b) {
                (Some(a), Some(b)) => Arc::ptr_eq(a, b),
                (None, None) => true,
                _ => false,
            }
        }
        self.settings.map(f64::to_bits) == o.settings.map(f64::to_bits)
            && self.shape == o.shape
            && self.sources.len() == o.sources.len()
            && self
                .sources
                .iter()
                .zip(&o.sources)
                .all(|(a, b)| a.0 == b.0 && a.1 == b.1 && Arc::ptr_eq(&a.2, &b.2))
            && self.excluded == o.excluded
            && self.mask == o.mask
            // Remade from the same parts on every settings command: equal
            // when its mask fields are.
            && match (&self.shadows, &o.shadows) {
                (Some(a), Some(b)) => Arc::ptr_eq(a, b) || a.same_mask(b),
                (None, None) => true,
                _ => false,
            }
            && same(&self.diamonds, &o.diamonds)
            && same(&self.shared, &o.shared)
            && same(&self.persistent, &o.persistent)
            && same(&self.background, &o.background)
    }
}
fn diamond_like(p: [f64; 6]) -> bool {
    (p[..3].iter().all(|l| (*l - 3.567).abs() < 0.15)
        && p[3..].iter().all(|a| (*a - 90.).abs() < 3.))
        || (p[..3]
            .iter()
            .all(|l| (*l - 3.567 / 2f64.sqrt()).abs() < 0.12)
            && p[3..]
                .iter()
                .all(|a| (*a - 60.).abs() < 3. || (*a - 120.).abs() < 3.))
}

pub(super) struct SearchCompletion(pub(super) Arc<std::sync::atomic::AtomicBool>);
impl Drop for SearchCompletion {
    fn drop(&mut self) {
        self.0.store(true, std::sync::atomic::Ordering::Release);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn diamond_cells_are_recognised() {
        assert!(diamond_like([2.522, 2.522, 2.522, 60., 60., 60.]));
        assert!(diamond_like([3.567, 3.567, 3.567, 90., 90., 90.]));
        assert!(!diamond_like([7., 9., 11., 90., 90., 90.]));
    }
    /// Find lattices takes tracks whose only flag is a masked pixel in the
    /// aperture (their position is sound); geometry refinement and every
    /// other flag keep them out.
    #[test]
    fn lattice_positions_include_masked_aperture_tracks() {
        let mut c = Crystal {
            geometry: Some(Geometry {
                origin: [-0.01, -0.01, 0.1],
                fast: [1e-4, 0., 0.],
                slow: [0., 1e-4, 0.],
                beam: [0., 0., 1.],
                axis: [1., 0., 0.],
                wavelength: 0.3,
            }),
            ..Default::default()
        };
        let flags = [
            (0, 30),
            (spots::MASKED, 5),
            (spots::MASKED | spots::OVERLAP, 4),
            (spots::OVERLAP, 3),
            (spots::MASKED | 1024, 2),
            (spots::BACKGROUND | spots::NO_CENTROID, 2),
        ];
        for (flag, n) in flags {
            for i in 0..n {
                c.tracks.push(Track {
                    native: false,
                    observed: [10. + 3. * i as f64, 20. + flag as f64, i as f64],
                    first: 0,
                    last: 0,
                    bounds: [0; 4],
                    flags: flag,
                    excluded: false,
                });
            }
        }
        c.tracks[1].excluded = true;
        c.tracks[30].excluded = true;
        assert_eq!(c.cloud(true).unwrap().0.len(), 29 + 4);
        assert_eq!(c.cloud(false).unwrap().0.len(), 29);
        assert!(
            c.cloud(true)
                .unwrap()
                .0
                .iter()
                .all(|&i| c.tracks[i].flags & !spots::MASKED == 0)
        );
    }
}
